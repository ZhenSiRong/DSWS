#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stream_gif.py —— 真跑第 8 页：起 MySQL 3307 + uvicorn 8000，在**真 pty** 里跑
`curl -sN …/api/stream`，按字节真实到达时间逐帧渲染成终端 GIF：
12 条 progress 逐条冒出来，最后 result 停在 41099.5。

在仓库根目录一条命令重跑：

    python3 tutorial/shots/stream_gif.py

输出（只新增这一个文件，不动已有 PNG）：

    tutorial/images/page-08-stream.gif   约 5.6 秒循环，含末尾结果停留约 2.7 秒

它做四件事（复用 web_shots.py / term_render.py 的思路，不改原脚本）：

1. 在 /tmp 建临时工作区：软链 `system/backend/`（复用仓库 venv），拷入 `system/fixtures/dw.sql`
   和 `.env.example`，写 `lab/app.py`（复用 term_render.py 的 APP_PAGE_08，即第 3–8 页
   产物的最终形态）。
2. 起两层环境（容器名带 shots- 前缀，与用户自己的 lab-* 栈隔离）：
   `shots-web-mysql`（127.0.0.1:3307）→ uvicorn `--host 0.0.0.0 --port 8000`。
   不启 nginx（第 8 页只用 curl 直连）。
3. 用 Python `pty` + `select` 跑第 8 页那条命令
   `curl -sN -G 'http://127.0.0.1:8000/api/stream' --data-urlencode 'q=华北销售额'`
   （与页面逐字一致），记录**每个字节 chunk 的真实到达时间**。
4. 按到达时间生成帧：每 ~120ms 一帧，帧内容 = 截至该时刻的终端输出；
   用 term_render.py 的深色终端 CSS/HTML 渲成 1100px 宽的 PNG（与现有
   page-08-stream.png 同宽同风格）；再用 convert 合成 GIF——
   流帧 12.5fps（-delay 8），开头命令停留 1.6s、末尾结果停留约 2.7s，
   整条循环约 5.6 秒。跑完自动 `docker rm -f` 容器、停 uvicorn、删临时工作区。

自检（脚本里真做，失败即退出码 1）：
  - pty 里真收到 12 条 `progress` + 1 条 `result`，result 里 sales = 41099.5；
  - 相邻 progress 到达间隔中位数约 150ms（12 条走完约 1.8s）；
  - 首 / 中 / 末三帧 `compare -metric AE` 证明画面确实在逐条刷新；
  - 末帧 tesseract OCR 必须读出 `progress` / `result`（并含 41099.5）；
  - GIF 尺寸 / 帧数 / 字节数打印出来，目标 ≤ 2MB。

依赖（本机已装，不新装）：docker、python pty/select（标准库）、google-chrome、
ImageMagick、tesseract；仓库的 `system/backend/.venv`。
端口只用 3307 / 8000，不碰用户的 dsws-lab-ui-* 栈（18081 等）。
"""

from __future__ import annotations

import getpass
import importlib.util
import json
import os
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- 常量

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"

WINDOW_W = 1100          # 与 page-08-stream.png 同宽（term_render.py 的窗宽）
FONT_PX = 14             # term_render.py 的等宽字号
LINE_HEIGHT = FONT_PX * 1.62   # term_render.py CSS 的 line-height

MYSQL_PORT = 3307
API_PORT = 8000
MYSQL_CONTAINER = "shots-web-mysql"
MYSQL_IMAGE_FALLBACK = "docker.m.daocloud.io/library/mysql:8.0"

GIF = IMAGES / "page-08-stream.gif"
GIF_MAX_BYTES = 2_000_000
SAMPLE_MS = 120          # 每 120ms 采一帧
GIF_DELAY = 8            # 8/100 秒 = 12.5fps
INITIAL_HOLD_CS = 160    # 开头「只有命令行、还没输出」停留 1.6s
TARGET_TOTAL_CS = 560    # 整条循环约 5.6s（5–8s 区间内）

# 第 8 页「动手」里那条命令，与 tutorial/page-08.md 逐字一致。
CURL_STREAM = ("curl -sN -G 'http://127.0.0.1:8000/api/stream' "
               "--data-urlencode 'q=华北销售额'")

# ---------------------------------------------------------------- 载入 term_render.py


def load_term_render():
    """借 term_render.py 的终端 CSS / HTML 渲染 / Chrome 截图，保证与现有 p8 PNG 同风格。"""
    path = HERE / "term_render.py"
    spec = importlib.util.spec_from_file_location("manual_term_render", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    for attr in ("CSS", "build_html", "chrome_screenshot", "trim_png", "WINDOW_W"):
        if not hasattr(module, attr):
            raise RuntimeError(f"{path} 里没有 {attr}")
    return module


def load_app_py(tr) -> str:
    app_py = getattr(tr, "APP_PAGE_08", None)
    if not isinstance(app_py, str) or not app_py.strip():
        raise RuntimeError("term_render.py 里没有 APP_PAGE_08")
    if "text/event-stream" not in app_py or "/api/stream" not in app_py:
        raise RuntimeError("term_render.py 的 APP_PAGE_08 不是第 8 页最终形态（缺 /api/stream）")
    return app_py


# ---------------------------------------------------------------- 小工具

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def say(msg: str = "") -> None:
    print(msg, flush=True)


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_port_closed(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not port_open(port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"端口 {port} 一直没释放")


def run_cmd(args: list[str], timeout: float = 120.0, cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"命令失败（exit={proc.returncode}）：{' '.join(args)}\n{detail[-3000:]}")
    return proc


def docker_names() -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def docker_id_set() -> dict[str, str]:
    """容器名 → ID（用于证明用户自己的容器前后没被动过）。"""
    proc = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.ID}}"],
        capture_output=True, text=True, timeout=30,
    )
    mapping: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "\t" in line:
            name, cid = line.split("\t", 1)
            mapping[name.strip()] = cid.strip()
    return mapping


def http_get(url: str, timeout: float = 2.0) -> tuple[int, str] | None:
    try:
        with _OPENER.open(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception:
        return None


def wait_until(what: str, predicate, timeout: float, interval: float = 0.25) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise RuntimeError(f"等待超时：{what}（{timeout:.0f}s）")


def image_size(path: Path) -> tuple[int, int]:
    out = run_cmd(["identify", "-format", "%w %h", str(path)], timeout=60).stdout.strip()
    width, height = out.split()
    return int(width), int(height)


def image_from_env(key: str, fallback: str) -> str:
    env_file = REPO / ".env.example"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    return fallback


def mysql_image() -> str:
    return image_from_env("MYSQL_IMAGE", MYSQL_IMAGE_FALLBACK)


# ---------------------------------------------------------------- uvicorn 后台进程


class UvicornServer:
    """第 8 页的服务：uvicorn --host 0.0.0.0 --port 8000（在临时工作区里跑）。"""

    def __init__(self, work: Path):
        self.work = work
        self.proc: subprocess.Popen | None = None
        self.lines: list[str] = []
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    @property
    def command(self) -> str:
        return f"system/backend/.venv/bin/python -m uvicorn lab.app:app --host 0.0.0.0 --port {API_PORT}"

    def start(self, timeout: float = 60.0) -> None:
        self.lines = []
        self.proc = subprocess.Popen(
            self.command.split(), cwd=self.work,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            start_new_session=True,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

        def healthy() -> bool:
            assert self.proc is not None
            if self.proc.poll() is not None:
                raise RuntimeError("uvicorn 没起来就退出了：\n" + "\n".join(self.logs()))
            got = http_get(f"http://127.0.0.1:{API_PORT}/health")
            return bool(got and got[0] == 200 and '"ok"' in got[1])

        try:
            wait_until("uvicorn /health 就绪", healthy, timeout, interval=0.15)
        except RuntimeError:
            raise RuntimeError("等 uvicorn 启动超时：\n" + "\n".join(self.logs()))

    def _pump(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            with self._lock:
                self.lines.append(line.rstrip("\n"))

    def logs(self) -> list[str]:
        with self._lock:
            return list(self.lines)

    def startup_log(self) -> list[str]:
        logs = self.logs()
        for i, line in enumerate(logs):
            if "Uvicorn running on" in line:
                return logs[: i + 1]
        return logs

    def stop(self) -> None:
        proc = self.proc
        if proc is None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=5)
        finally:
            if self._reader is not None:
                self._reader.join(timeout=5)
            self.proc = None
        if port_open(API_PORT):
            wait_port_closed(API_PORT)


# ---------------------------------------------------------------- 环境准备 / 清理


def preflight() -> None:
    missing = [tool for tool in ("docker", "google-chrome", "convert", "identify")
               if shutil.which(tool) is None]
    if missing:
        sys.exit(f"缺少依赖：{', '.join(missing)}（本脚本不装新依赖）")
    for path in (REPO / "backend" / ".venv" / "bin" / "python", REPO / "fixtures" / "dw.sql"):
        if not path.exists():
            sys.exit(f"缺少仓库产物：{path}")
    for port in (MYSQL_PORT, API_PORT):
        if port_open(port):
            sys.exit(
                f"端口 {port} 已被占用；本脚本不杀别人的进程。"
                f"先停掉占用它的服务再重跑。"
            )
    if MYSQL_CONTAINER in docker_names():
        say(f"发现上一轮残留的容器 {MYSQL_CONTAINER}，先删除（脚本自己会清理，正常不应出现）")
        subprocess.run(["docker", "rm", "-f", MYSQL_CONTAINER], capture_output=True, timeout=60)
    IMAGES.mkdir(parents=True, exist_ok=True)


def prepare_workdir(tr) -> Path:
    work = Path(tempfile.mkdtemp(prefix="manual-stream-gif-"))
    os.symlink(REPO / "backend", work / "backend", target_is_directory=True)
    (work / "fixtures").mkdir()
    shutil.copy2(REPO / "fixtures" / "dw.sql", work / "fixtures" / "dw.sql")
    shutil.copy2(REPO / ".env.example", work / ".env.example")
    (work / "lab").mkdir()
    (work / "lab" / "app.py").write_text(load_app_py(tr), encoding="utf-8")
    return work


def start_mysql(work: Path) -> None:
    image = mysql_image()
    run_cmd([
        "docker", "run", "-d", "--name", MYSQL_CONTAINER,
        "-p", f"127.0.0.1:{MYSQL_PORT}:3306",
        "-e", "LANG=C.UTF-8",
        "-e", "MYSQL_ROOT_PASSWORD=labpass",
        "-e", "MYSQL_USER=didilili",
        "-e", "MYSQL_PASSWORD=labpass",
        "-v", f"{work}/fixtures/dw.sql:/docker-entrypoint-initdb.d/10-dw.sql:ro",
        image,
    ], timeout=180)

    def data_ready() -> bool:
        proc = subprocess.run(
            ["docker", "exec", MYSQL_CONTAINER, "mysql", "-uroot", "-plabpass",
             "-N", "-B", "dw", "-e", "SELECT COUNT(*) FROM fact_order;"],
            capture_output=True, text=True, timeout=60,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "115"

    try:
        wait_until("MySQL 灌完 system/fixtures/dw.sql（fact_order = 115）", data_ready,
                   timeout=300, interval=1.0)
    except RuntimeError:
        logs = subprocess.run(
            ["docker", "logs", "--tail", "40", MYSQL_CONTAINER],
            capture_output=True, text=True, timeout=60,
        )
        raise RuntimeError("MySQL 没等到数据：\n" + (logs.stdout + logs.stderr)[-3000:])


# ---------------------------------------------------------------- pty 里真跑 curl


def capture_stream_pty(work: Path, timeout: float = 60.0) -> dict:
    """在真 pty 里跑第 8 页的 curl -sN，记录每个字节 chunk 的真实到达时间。"""
    import pty
    import termios

    master, slave = pty.openpty()
    # 关掉输出后处理（OPOST）：不把 \n 翻成 \r\n，帧里保留 curl 原样字节。
    attrs = termios.tcgetattr(slave)
    attrs[1] &= ~termios.OPOST
    termios.tcsetattr(slave, termios.TCSANOW, attrs)

    proc = subprocess.Popen(
        CURL_STREAM, shell=True, cwd=work,
        stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True,
    )
    os.close(slave)
    t0 = time.monotonic()
    chunks: list[dict] = []
    try:
        while True:
            if proc.poll() is not None:
                break
            ready, _, _ = select.select([master], [], [], timeout)
            if not ready:
                proc.kill()
                raise RuntimeError(f"curl 流式请求超时（{timeout:.0f}s）")
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append({"t": round((time.monotonic() - t0) * 1000.0, 1),
                           "data": data.decode("utf-8", "replace")})
        # 子进程退出后再把 pty 缓冲里剩下的读干净
        while True:
            ready, _, _ = select.select([master], [], [], 0.2)
            if not ready:
                break
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append({"t": round((time.monotonic() - t0) * 1000.0, 1),
                           "data": data.decode("utf-8", "replace")})
    finally:
        try:
            os.close(master)
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if proc.returncode != 0:
        raise RuntimeError(f"curl 失败（exit={proc.returncode}）")
    if not chunks:
        raise RuntimeError("pty 里一个字节都没收到")
    return {"chunks": chunks, "duration_ms": round((time.monotonic() - t0) * 1000.0, 1)}


def stream_lines_at(chunks: list[dict], upto_ms: float) -> list[str]:
    """截至 t=upto_ms 时终端上应该显示的完整行（行尾未到的半个 chunk 也算上去）。"""
    text = "".join(chunk["data"] for chunk in chunks if chunk["t"] <= upto_ms)
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def analyze_stream(chunks: list[dict]) -> dict:
    """从 chunk 到达时间里解析 12 条 progress / 1 条 result，并核对节奏。"""
    events: list[dict] = []
    pending = ""
    for chunk in chunks:
        pending += chunk["data"]
        while "\n\n" in pending:
            raw, pending = pending.split("\n\n", 1)
            line = raw.splitlines()[0] if raw.strip() else ""
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: "):])
            events.append({"t": chunk["t"], "event": event})
    progress = [e for e in events if e["event"].get("type") == "progress"]
    results = [e for e in events if e["event"].get("type") == "result"]
    if len(progress) != 12:
        raise RuntimeError(f"progress 事件 {len(progress)} 条，不是 12 条：{[e['event'] for e in progress]}")
    if len(results) != 1:
        raise RuntimeError(f"result 事件 {len(results)} 条，不是 1 条")
    sales = results[0]["event"].get("data", {}).get("rows", [{}])[0].get("sales")
    if sales != 41099.5:
        raise RuntimeError(f"result 里 sales = {sales!r}，不是 41099.5")
    gaps = [round(b["t"] - a["t"], 1) for a, b in zip(progress, progress[1:])]
    gaps_sorted = sorted(gaps)
    median = gaps_sorted[len(gaps_sorted) // 2]
    total = round(results[0]["t"] - progress[0]["t"], 1)
    if not (100 <= median <= 400):
        raise RuntimeError(f"progress 相邻间隔中位数 {median}ms，不像每步 sleep 0.15s")
    if not (1200 <= total <= 3000):
        raise RuntimeError(f"12 条 progress 到 result 用时 {total}ms，不像约 1.8s")
    return {
        "progress": progress,
        "result": results[0],
        "gaps_ms": gaps,
        "median_gap_ms": median,
        "first_progress_t": progress[0]["t"],
        "result_t": results[0]["t"],
        "total_ms": total,
    }


# ---------------------------------------------------------------- 终端帧渲染 / GIF


def build_terminal_html(tr, lines: list[str], min_content_lines: int) -> str:
    """与 term_render.build_html 相同的终端面板，只是给 <pre> 加固定最小高度。"""
    records = {0: {"cmd": CURL_STREAM, "lines": lines}}
    panes = [{
        "title": "终端 2",
        "items": [{"step": 0, "part": "cmd"}, {"step": 0, "part": "out"}],
    }]
    html_text = tr.build_html(panes, records)
    # 固定高度多留半行：Chrome 的行盒高度有小数舍入，留余量保证每帧同高
    min_height = (min_content_lines + 0.5) * LINE_HEIGHT
    pre_style = f'<pre style="min-height:{min_height:.1f}px">'
    if "<pre>" not in html_text:
        raise RuntimeError("term_render.build_html 输出里找不到 <pre>")
    return html_text.replace("<pre>", pre_style, 1)


def render_terminal_frames(tr, states: list[list[str]], work: Path,
                           min_content_lines: int) -> list[Path]:
    """每个唯一状态渲一张 PNG（1100px 宽，深色终端风，所有帧同高）。"""
    out: list[Path] = []
    profile = work / "chrome-profile"
    for i, lines in enumerate(states):
        html_path = work / f"state-{i:03d}.html"
        html_path.write_text(build_terminal_html(tr, lines, min_content_lines),
                             encoding="utf-8")
        raw = work / f"state-{i:03d}.raw.png"
        png = work / f"state-{i:03d}.png"
        tr.chrome_screenshot(html_path, raw, profile)
        tr.trim_png(raw, png)
        out.append(png)
    return out


def write_gif(frames: list[Path], delays_cs: list[int], out: Path) -> None:
    """按每帧自己的 delay（1/100 秒）合成 GIF；末尾帧可停留更久。"""
    if len(frames) != len(delays_cs):
        raise RuntimeError("帧数与 delay 数不一致")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["convert", "-loop", "0"]
    for path, delay in zip(frames, delays_cs):
        cmd += ["-delay", str(int(delay)), str(path)]
    cmd += ["-layers", "Optimize", str(out)]
    run_cmd(cmd, timeout=600)


def gif_info(path: Path) -> tuple[int, int, int, int]:
    out = run_cmd(["identify", "-format", "%w %h %n\n", str(path)], timeout=120).stdout
    first = out.splitlines()[0].split()
    w, h, n = (int(x) for x in first)
    return w, h, n, path.stat().st_size


def extract_gif_frames(gif: Path, out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(["convert", str(gif), "-coalesce", str(out_dir / "frame-%03d.png")], timeout=300)
    frames = sorted(out_dir.glob("frame-*.png"))
    if len(frames) < 3:
        raise RuntimeError("抽帧失败")
    return frames[0], frames[len(frames) // 3], frames[-1]


def frame_ae(a: Path, b: Path) -> int:
    proc = subprocess.run(
        ["compare", "-metric", "AE", str(a), str(b), "null:"],
        capture_output=True, text=True, timeout=120,
    )
    raw = (proc.stderr or proc.stdout or "").strip().split()
    if not raw:
        return 0
    try:
        return int(float(raw[0]))
    except ValueError:
        return -1


def ocr_text(png: Path) -> str:
    """深色终端图反色后 OCR（与 render_page_shots.py 同一套做法）；PSM 6/11 各跑一次取并集。"""
    if shutil.which("tesseract") is None:
        return ""
    tmp = png.with_name(png.stem + ".ocr.png")
    try:
        try:
            from PIL import Image, ImageOps
            with Image.open(png) as image:
                ImageOps.expand(ImageOps.invert(image.convert("L")),
                                border=24, fill=255).save(tmp)
            source = tmp
        except Exception:
            source = png
        texts = []
        for psm in ("6", "11"):
            proc = subprocess.run(
                ["tesseract", str(source), "stdout", "-l", "eng", "--psm", psm],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180,
            )
            texts.append(proc.stdout or "")
        return "\n".join(texts)
    finally:
        tmp.unlink(missing_ok=True)


def check_no_secrets(label: str, text: str) -> None:
    forbidden = ["/home/", "/tmp/", "/root/", "/Users/", getpass.getuser(),
                 socket.gethostname()]
    hits = [needle for needle in forbidden if needle and needle in text]
    if hits:
        raise RuntimeError(f"{label} 里出现禁止字符串 {hits}：\n{text[:1000]}")
    say(f"    ✅ 敏感串检查（{label}）：0 命中（用户名 / 主机名 / 绝对路径）")


# ---------------------------------------------------------------- 主流程


def cleanup(work: Path | None, server: UvicornServer | None) -> None:
    if server is not None:
        try:
            server.stop()
        except Exception:
            pass
    try:
        subprocess.run(["docker", "rm", "-f", MYSQL_CONTAINER], capture_output=True, timeout=60)
    except Exception:
        pass
    if work is not None:
        shutil.rmtree(work, ignore_errors=True)


def build_gif_plan(chunks: list[dict], analysis: dict) -> dict:
    """按到达时间做 120ms 采样；开头命令停留、末尾结果停留单独给 delay。"""
    stream_end = max(chunk["t"] for chunk in chunks)
    ticks: list[float] = []
    tick = 0.0
    while tick <= stream_end:
        ticks.append(tick)
        tick += SAMPLE_MS
    ticks.append(stream_end)

    states: list[list[str]] = []
    state_index: dict[tuple[str, ...], int] = {}
    timeline: list[int] = []
    for t in ticks:
        lines = tuple(stream_lines_at(chunks, t))
        if lines not in state_index:
            state_index[lines] = len(states)
            states.append(list(lines))
        timeline.append(state_index[lines])

    delays = [GIF_DELAY] * len(timeline)
    delays[0] = INITIAL_HOLD_CS
    total_stream_cs = (len(timeline) - 1) * GIF_DELAY
    final_delay = max(100, TARGET_TOTAL_CS - INITIAL_HOLD_CS - total_stream_cs)
    delays[-1] = final_delay
    return {
        "states": states,
        "timeline": timeline,
        "delays": delays,
        "total_cs": sum(delays),
        "final_hold_s": final_delay / 100.0,
        "ticks": len(timeline),
        "stream_end_ms": stream_end,
        "result_t": analysis["result_t"],
    }


def main() -> int:
    started = time.monotonic()
    say("=" * 78)
    say("stream_gif.py —— 真跑第 8 页 curl -sN 流，按字节到达时间渲染终端 GIF")
    say(f"仓库：{REPO}")
    say(f"输出：{GIF.relative_to(REPO)}")
    say("=" * 78)

    before_ids = docker_id_set()
    preflight()
    tr = load_term_render()

    work: Path | None = None
    server: UvicornServer | None = None
    try:
        work = prepare_workdir(tr)
        say(f"临时工作区：{work}（命令里的相对路径在这里，图里不出现绝对路径）")
        say("    lab/app.py = term_render.py 的 APP_PAGE_08（第 3–8 页产物的最终形态）")
        if not hasattr(tr, "html_out_line"):
            raise RuntimeError("term_render.py 里没有 html_out_line（渲染 SSE 行要用）")

        say("")
        say("── 环境 1/2：MySQL 容器 shots-web-mysql（127.0.0.1:3307）──")
        start_mysql(work)
        say("    ✅ fact_order = 115（system/fixtures/dw.sql 已灌入）")

        say("")
        say("── 环境 2/2：uvicorn 8000（第 8 页的服务）──")
        server = UvicornServer(work)
        server.start()
        say(f"    $ {server.command}")
        for line in server.startup_log():
            say(f"      {line}")
        say("    ✅ /health 就绪")

        say("")
        say("── 真跑：pty 里执行第 8 页的 curl -sN，记录逐字节到达时间 ──")
        say(f"    $ {CURL_STREAM}")
        capture = capture_stream_pty(work)
        chunks = capture["chunks"]
        analysis = analyze_stream(chunks)
        say(f"    ✅ 收到 {len(analysis['progress'])} 条 progress + 1 条 result，"
            f"result.sales = 41099.5")
        say(f"    ⏱  相邻 progress 间隔 {analysis['gaps_ms']} ms（中位 {analysis['median_gap_ms']}ms），"
            f"12 条到 result 共 {analysis['total_ms']}ms")
        if not (len(chunks) >= 10):
            raise RuntimeError(f"pty 只收到 {len(chunks)} 个 chunk，不像逐条到达")

        stream_hits = [line for line in server.logs() if "/api/stream" in line]
        if not any("200 OK" in line for line in stream_hits):
            raise RuntimeError(f"uvicorn 访问日志里没有 200 的 /api/stream：{stream_hits[-3:]}")
        say(f"    ✅ uvicorn 访问日志：{stream_hits[-1].strip()}")

        # ---- 规划帧：120ms 采样 + 开头/结尾停留
        say("")
        say("── 渲染终端帧：120ms 采样，末端面板固定高度，GIF 不抖 ──")
        plan = build_gif_plan(chunks, analysis)
        all_lines = stream_lines_at(chunks, 10 ** 9)
        # 面板里除了输出行还有一行命令行（`$ curl …`），固定高度要一起算
        min_content_lines = 1 + max(len(state) for state in plan["states"])
        if min_content_lines < 1 + len(all_lines):
            raise RuntimeError("固定高度比最终帧还矮")
        check_no_secrets("终端输出文本", "\n".join(all_lines))
        say(f"    采样 {plan['ticks']} 帧（唯一内容状态 {len(plan['states'])} 个），"
            f"最终终端 {len(all_lines)} 行，面板按 {min_content_lines} 行固定高度")
        say(f"    播放计划：开头停留 {INITIAL_HOLD_CS / 100:.1f}s ＋ 流帧 "
            f"{(plan['ticks'] - 1) * GIF_DELAY / 100:.1f}s ＋ 末尾停留 {plan['final_hold_s']:.1f}s "
            f"= {plan['total_cs'] / 100:.1f}s")
        if not (500 <= plan["total_cs"] <= 800):
            raise RuntimeError(f"GIF 循环 {plan['total_cs'] / 100:.1f}s，不在 5–8s 区间")
        if plan["final_hold_s"] < 1.0:
            raise RuntimeError(f"末尾停留 {plan['final_hold_s']:.1f}s < 1s")

        rendered = render_terminal_frames(tr, plan["states"], work, min_content_lines)
        w, h = image_size(rendered[0])
        for png in rendered:
            if image_size(png) != (w, h):
                raise RuntimeError(f"{png.name} 尺寸不是所有帧统一的 {w}x{h}")
        if w != WINDOW_W:
            raise RuntimeError(f"帧宽 {w}px ≠ {WINDOW_W}px（要与 page-08-stream.png 一致）")
        say(f"    ✅ {len(rendered)} 个唯一状态都渲成 {w}x{h}")

        # ---- 合成 GIF
        say("")
        say("── 合成 GIF：convert 逐帧 delay → -layers Optimize ──")
        gif_frames = [rendered[i] for i in plan["timeline"]]
        write_gif(gif_frames, plan["delays"], GIF)
        gw, gh, gn, gbytes = gif_info(GIF)
        say(f"    🖼  {GIF.relative_to(REPO)}  {gw}x{gh}  帧数 {gn}  {gbytes / 1024:.0f} KB")
        if gbytes > GIF_MAX_BYTES:
            raise RuntimeError(f"GIF {gbytes} 字节 > 上限 {GIF_MAX_BYTES}")
        if (gw, gh) != (w, h):
            raise RuntimeError(f"GIF 尺寸 {gw}x{gh} ≠ 帧尺寸 {w}x{h}")

        # ---- 自检：帧真的有变化 + 末帧 OCR
        say("")
        say("── 自检：首/中/末帧对比 + 末帧 OCR ──")
        check_dir = work / "gif-check"
        first, mid, last = extract_gif_frames(GIF, check_dir)
        ae_first_mid = frame_ae(first, mid)
        ae_mid_last = frame_ae(mid, last)
        say(f"    compare -metric AE：首↔中 {ae_first_mid}  中↔末 {ae_mid_last}（0 = 相同）")
        if ae_first_mid <= 0 or ae_mid_last <= 0:
            raise RuntimeError("GIF 首/中/末帧相同，没有逐条刷新的动画效果")
        ocr_last = ocr_text(last)
        ocr_lower = ocr_last.lower()
        missing = [needle for needle in ("progress", "result") if needle not in ocr_lower]
        if missing:
            raise RuntimeError(f"末帧 OCR 没读出 {missing}：{ocr_last[-800:]!r}")
        say("    ✅ 末帧 OCR 读出 progress / result"
            + (" / 41099.5" if "41099.5" in "".join(ocr_last.split()) else ""))
        if "41099.5" not in "".join(ocr_last.split()):
            say("    ⚠️  OCR 没稳定读出 41099.5（长 JSON 行 OCR 有噪声；原始输出里已核对过）")
        check_no_secrets("末帧 OCR 文本", ocr_last)

        # ---- 收尾证据：用户栈容器 ID 集合不变
        after_ids = docker_id_set()
        own = {MYSQL_CONTAINER}
        user_before = {k: v for k, v in before_ids.items() if k not in own}
        user_after = {k: v for k, v in after_ids.items() if k not in own}
        if user_before != user_after:
            raise RuntimeError("用户栈容器前后不一致（本脚本不应碰它们）")
        say("")
        say(f"    ✅ 用户栈容器 {len(user_before)} 个，前后 ID 集合一致（未动 dsws-lab-ui-* 等）")

        say("")
        say("=" * 78)
        say("完成：")
        ident = run_cmd(["identify", "-format", "%f  %wx%h  %n帧\n", str(GIF)],
                        timeout=60).stdout.splitlines()[0]
        say(f"  {ident.strip()}")
        say(f"  {GIF.stat().st_size / 1024:.0f} KB（上限 {GIF_MAX_BYTES // 1024} KB）")
        say(f"用时 {time.monotonic() - started:.1f}s；重跑：python3 tutorial/shots/stream_gif.py")
        return 0
    except KeyboardInterrupt:
        say("\n被 Ctrl+C 中断，开始清理……")
        return 130
    except Exception as exc:  # noqa: BLE001
        say(f"\n❌ 出错：{exc}")
        return 1
    finally:
        say("清理：删容器 / 停 uvicorn / 删临时工作区 ...")
        cleanup(work, server)


if __name__ == "__main__":
    sys.exit(main())
