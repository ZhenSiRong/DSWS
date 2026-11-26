#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_l3_pages.py —— 真跑练本 L3 第 14/15/16/17 页的命令，渲染 6 张终端运行截图。

一条命令重跑全部图（在仓库根目录）：

    python3 tutorial/shots/render_l3_pages.py

做四件事：

1. 在 `/tmp/shots-l3b` 建一个**临时副本**（rsync 仓库，排除 `.git` / `node_modules` /
   缓存），并把副本 `.env` 的 5 个 host 端口改成隔离端口：mysql 13337 / ES 19237 /
   Qdrant 16357 / backend 18137 / frontend 18077，`FRONTEND_BIND=127.0.0.1`。
   页面里的默认端口（8080）只在**执行时**替换成 18077，**渲染进图的命令仍是页面原文**
   （与 render_l2_pages.py 换容器名的做法一致）。
2. 用 `docker compose -p shotsl3b up -d --no-build` 起隔离栈，**复用**
   `shopkeeper-rebuild/backend:local`、`shopkeeper-rebuild/frontend:local` 镜像，
   不重建、不碰用户栈（`dsws-*`、`lab-*` 一律不动）。磁盘水位触发时，只改
   隔离 ES 的 cluster settings（`cluster.routing.allocation.disk.threshold_enabled=false`），
   让 init 能建索引；`down -v` 后随卷一起消失，不落仓库。
3. 按页真跑命令（PTY 捕获，保留学生终端里的真实输出顺序）：
   - 第 14 页：`make stage3`（S2 对账 → 20 题黄金集 → 全量回归）
     → `stop elasticsearch` → `curl /api/query` 仍回 41099.5
     → 黄金集 `18 passed, 23 errors` → `start elasticsearch` 等回 healthy；
   - 第 15 页：`make baseline` 绿（10/10）→ 改**副本**契约的 GMV 公式 → 红（8/10）
     → `toolbox/scripts/lab reset p15-before --yes` → 再跑回绿；
   - 第 16 页：`pytest test_guard.py` 26 passed → `failures --check` S6 PASS
     → `probe_correction` total 20 / mismatch 0 + 码分布；
   - 第 17 页：`pytest test_correct.py` 14 passed → `failures --check` S6 PASS
     → `corrected` 期望 result / 实际 result + 9·11 重试标记统计
     → 拆一刀（关掉纠正入口）→ pytest 5 failed / 失败矩阵 FAIL: 1 项 / 语料 mismatch 0
     → `toolbox/scripts/lab reset p17-before --yes` → 回绿。
4. 渲染 6 张 3200×…（宽 3200 = 1600 CSS px @2x，高按内容自适应：内容+80px 留白，下限 600、上限 7200）深色终端图，并做图文
   一致性自检：页面「## 你应该看到」的样例块逐行对账（`…` 当通配符）、OCR 关键字
   抽检、禁止字符串（用户名 / 主机名 / 绝对路径 / 隔离端口）、PNG 尺寸。

输出（只写这 6 个文件）：

    tutorial/images/page-14-stage3.png     第 14 页 `make stage3` 的 S2/S3 输出
    tutorial/images/page-14-stop-es.png    第 14 页停 ES 后：查数 41099.5 + 黄金集 23 errors
    tutorial/images/page-15-baseline.png   第 15 页 `make baseline` 绿 / 拆一刀后红（两屏对照）
    tutorial/images/page-16-guard.png      第 16 页 26 passed + S6 PASS + mismatch 0
    tutorial/images/page-17-correct.png    第 17 页 14 passed + S6 PASS + 9/11 统计
    tutorial/images/page-17-ablation.png   第 17 页拆一刀后的红（pytest / 矩阵 / 语料）

几条约定：

- 页面命令里的 `docker compose` 在副本里执行时加 `-p shotsl3b`，`8080` 换成 18077；
  图里显示的仍是页面原文。临时容器 / 卷 / 网络跑完 `down -v` 清掉。
- 仓库文件一个都不改：改契约、拆纠错代码只发生在 `/tmp/shots-l3b` 副本里，跑完用
  副本里的 `toolbox/scripts/lab reset` 还原；仓库 `system/backend/uv.lock` 若被改会 `git checkout --`。
- 依赖（本机已有，不新装）：docker、google-chrome、ImageMagick convert/identify、
  rsync、仓库自带 `system/backend/.venv`；OCR 自检可选依赖 tesseract + Pillow（没装就跳过，
  主对账用渲染前原文完成）。

调试用（不参与正常流程）：

    python3 tutorial/shots/render_l3_pages.py --keep            留 /tmp/shots-l3b 和栈
    python3 tutorial/shots/render_l3_pages.py --render-only FILE 用捕获缓存只重渲染图
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- 常量

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"
PAGE_MD = {
    14: REPO / "manual" / "page-14.md",
    15: REPO / "manual" / "page-15.md",
    16: REPO / "manual" / "page-16.md",
    17: REPO / "manual" / "page-17.md",
}

WORK = Path("/tmp/shots-l3b")                    # 临时副本（隔离，跑完删）
PROJECT = "shotsl3b"                             # compose project（不碰用户栈）
CAPTURES = Path("/tmp/shots-l3b-captures.json")  # 捕获缓存（调试；正常跑完删）
SERVICES = ("mysql", "elasticsearch", "qdrant", "backend", "frontend")
IMAGE_BACKEND = "shopkeeper-rebuild/backend:local"
IMAGE_FRONTEND = "shopkeeper-rebuild/frontend:local"

# 隔离端口（任务约定；页面默认值 3306/9200/6333/8100/8080 不占）
HOST_PORTS = {
    "MYSQL_HOST_PORT": 13337,
    "ES_HOST_PORT": 19237,
    "QDRANT_HOST_PORT": 16357,
    "BACKEND_HOST_PORT": 18137,
    "FRONTEND_HOST_PORT": 18077,
}
DISPLAY_FRONTEND_PORT = 8080                    # 页面原文端口（渲染进图）
EXEC_ENV_PREFIX = "source toolbox/scripts/export-docker-env.sh"
UV_OFFLINE = "1"                                # 副本里 uv run 不联网

WINDOW_W_CSS = 1600                             # 窗宽 1600 CSS px
DEVICE_SCALE = 2                                # @2x：PNG 宽 3200 px
WINDOW_H_CSS = 3600                             # 先渲高一点，再 -trim 到内容
MIN_PNG_H = 600                                 # 高度下限（@2x）；旧值 1800 会给矮内容补出大半黑边（Q4 改）
PAD_PX = 80                                     # 内容上下留白合计（@2x，约 40 CSS px），居中补在内容外
MAX_PNG_H = WINDOW_H_CSS * DEVICE_SCALE         # 高度上限＝chrome 窗高，防溢出
PAGE_BG = "#04070b"                             # 与 term_render.CSS 的 --page-bg 一致

# 每次运行都会变、但对账时不该当差异的东西
FORBIDDEN = [
    "/home/", "/root/", "/Users/", "/tmp/", "/var/", "zhensirong", ".dsh",
    "shots-l3", "shotsl3", "uv.lock", "MSYS",
    str(HOST_PORTS["MYSQL_HOST_PORT"]), str(HOST_PORTS["ES_HOST_PORT"]),
    str(HOST_PORTS["QDRANT_HOST_PORT"]), str(HOST_PORTS["BACKEND_HOST_PORT"]),
    str(HOST_PORTS["FRONTEND_HOST_PORT"]),
]

# 每张图的 OCR 关键字（tesseract 只有 eng 语言包：英文/数字可信，中文靠渲染前对账）
OCR_KEYWORDS = {
    "page-14-stage3.png": ["S2 VERIFY PASS", "41 passed", "813 passed", "S3 PASS"],
    "page-14-stop-es.png": ["41099.5", "18 passed", "23 errors", "mysql"],
    "page-15-baseline.png": ["10/10", "8/10", "FAIL", "SQL_UNKNOWN_COLUMN"],
    "page-16-guard.png": ["26 passed", "S6 PASS", "mismatch", "SQL_REJECTED", "16"],
    "page-17-correct.png": ["14 passed", "S6 PASS", "corrected", "retryable"],
    "page-17-ablation.png": ["5 failed", "9 passed", "FAIL: 1", "mismatch", "SQL_SYNTAX"],
}

# 页面里必须能找到的图片嵌入行（脚本不写页面，只核对；图与页对不上就报红）
EMBED_LINES = {
    14: [
        "![第 14 页 · `make stage3` 真输出：S2 VERIFY PASS → 41 passed → 813 passed, 30 skipped → S3 PASS](images/page-14-stage3.png)",
        "![第 14 页 · 停掉 Elasticsearch 后：POST /api/query 仍回 41099.5；20 题黄金集 18 passed, 23 errors](images/page-14-stop-es.png)",
    ],
    15: [
        "![第 15 页 · `make baseline` 两段对照：绿 基线：10/10 通过（拒答 2）→ 拆一刀后红 基线：8/10 通过（拒答 2）](images/page-15-baseline.png)",
    ],
    16: [
        '![第 16 页 · 三条离线判据：26 passed + 失败矩阵 S6 PASS + 语料对账 {"total": 20, "mismatch": 0}](images/page-16-guard.png)',
    ],
    17: [
        "![第 17 页 · 14 passed + S6 PASS（corrected 期望 result 实际 result）+ 9、11 重试标记统计](images/page-17-correct.png)",
        "![第 17 页 · 拆一刀关掉纠错后：pytest 5 failed, 9 passed + 失败矩阵只红 corrected + 语料 mismatch 0（哪条判据抓到了、哪条没抓到）](images/page-17-ablation.png)",
    ],
}

# ---------------------------------------------------------------- 复用 term_render

sys.dont_write_bytecode = True                  # 不在 tutorial/shots 里写 __pycache__
sys.path.insert(0, str(HERE))
import term_render as tr  # noqa: E402

# term_render 的 CSS 按窗宽 1100 写死，这里只把窗宽换成 1600，字体/配色/版式不变；
# 另加一个 .dim 用于「…（省略）」标注行。
tr.CSS = tr.CSS.replace("1100px", f"{WINDOW_W_CSS}px")
if "1100px" in tr.CSS:
    raise RuntimeError("term_render.CSS 的窗宽没替换干净")
CSS = tr.CSS + "\n.dim { color: var(--dim); }  /* …（省略）标注 */\n"

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>]")

# ---------------------------------------------------------------- 小工具


def say(msg: str = "") -> None:
    print(msg, flush=True)


def section(title: str) -> None:
    say("")
    say("─" * 78)
    say(title)
    say("─" * 78)


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def docker_names() -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def docker_snapshot() -> list[str]:
    """用户栈快照：起栈前 / 清理后各拍一次，证明没碰别人的容器。"""
    out = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True, text=True, timeout=30,
    ).stdout
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith(f"{PROJECT}-"):
            rows.append(line)
    return sorted(rows)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def decode(raw: bytes) -> str:
    return strip_ansi(raw.decode("utf-8", "replace")).replace("\r\n", "\n")


def run_pipe(cmd: str, cwd: Path, timeout: float,
             allowed: tuple[int, ...] = (0,),
             env_extra: dict | None = None) -> tuple[list[str], int]:
    """非交互命令：合并 stdout/stderr，按退出码校验。"""
    env = os.environ.copy()
    env["UV_OFFLINE"] = UV_OFFLINE
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["bash", "-c", cmd], cwd=cwd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, env=env,
    )
    lines = (proc.stdout or "").splitlines()
    if proc.returncode not in allowed:
        raise RuntimeError(
            f"命令失败（exit={proc.returncode}，允许 {allowed}）：{cmd}\n"
            "--- 输出 ---\n" + "\n".join(lines[-30:])
        )
    return lines, proc.returncode


def run_pty(cmd: str, cwd: Path, timeout: float,
            allowed: tuple[int, ...] = (0,),
            env_extra: dict | None = None) -> tuple[list[str], int]:
    """交互式命令：用 PTY 捕获，保留学生终端里的真实输出顺序（stdout/stderr 交织）。

    `make` 的 banner（stdout）和 `uv run` / pytest 的进度（stdout/stderr）混在一起时，
    用管道捕获会因缓冲导致顺序错乱；PTY 让子进程以为自己在终端里，顺序与真终端一致。
    """
    env = os.environ.copy()
    env.update({"UV_OFFLINE": UV_OFFLINE, "TERM": "dumb", "NO_COLOR": "1"})
    if env_extra:
        env.update(env_extra)
    master, slave = pty.openpty()
    # 给个宽终端，避免程序按 80 列截断/换行
    import fcntl
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 200, 240, 0, 0))
    proc = subprocess.Popen(
        ["bash", "-c", cmd], cwd=cwd, stdin=slave, stdout=slave,
        stderr=slave, close_fds=True, env=env, start_new_session=True,
    )
    os.close(slave)
    chunks: list[bytes] = []
    deadline = time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=10)
                raise RuntimeError(f"命令超时（{timeout}s）：{cmd}")
            try:
                ready, _, _ = select.select([master], [], [], 0.5)
            except OSError:
                break
            if not ready:
                if proc.poll() is not None:
                    # 进程退出后把 PTY 缓冲读干净
                    try:
                        while True:
                            data = os.read(master, 65536)
                            if not data:
                                break
                            chunks.append(data)
                    except OSError:
                        pass
                    break
                continue
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
    finally:
        try:
            os.close(master)
        except OSError:
            pass
    code = proc.wait(timeout=timeout)
    lines = decode(b"".join(chunks)).split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if code not in allowed:
        raise RuntimeError(
            f"命令失败（exit={code}，允许 {allowed}）：{cmd}\n"
            "--- 输出末 30 行 ---\n" + "\n".join(lines[-30:])
        )
    return lines, code


def exec_cmd(display_cmd: str) -> str:
    """页面命令 → 隔离环境执行命令：compose 加 `-p shotsl3b`，8080 换隔离前端端口。"""
    out = re.sub(r"\bdocker compose\b", f"docker compose -p {PROJECT}", display_cmd)
    out = out.replace(f"127.0.0.1:{DISPLAY_FRONTEND_PORT}",
                      f"127.0.0.1:{HOST_PORTS['FRONTEND_HOST_PORT']}")
    return out


def captures_run(records: dict, key: str, display_cmd: str, cwd: Path,
                 timeout: float, allowed: tuple[int, ...] = (0,),
                 with_env: bool = False, quiet: bool = False) -> list[str]:
    """真跑一条命令：记录「页面原文命令 + 真实输出」，供渲染和自检。"""
    cmd = exec_cmd(display_cmd)
    if with_env and not display_cmd.lstrip().startswith("source "):
        cmd = f"{EXEC_ENV_PREFIX}\n{cmd}"
    if quiet:
        say(f"    $ {display_cmd}")
    else:
        say(f"    $ {display_cmd}" + ("" if cmd == display_cmd else f"   （执行：{cmd!r}）"))
    t0 = time.monotonic()
    lines, code = run_pty(cmd, cwd, timeout, allowed)
    records[key] = {"cmd": display_cmd, "lines": lines, "exit": code}
    say(f"      → exit {code}，{len(lines)} 行输出（{time.monotonic() - t0:.1f}s）")
    return lines


def run_quiet(records: dict, key: str, display_cmd: str, cwd: Path,
              timeout: float, allowed: tuple[int, ...] = (0,)) -> list[str]:
    """不上图的辅助命令（快照 / reset / compose stop|start），用管道捕获。"""
    cmd = exec_cmd(display_cmd)
    say(f"    $ {display_cmd}")
    lines, code = run_pipe(cmd, cwd, timeout, allowed)
    records[key] = {"cmd": display_cmd, "lines": lines, "exit": code}
    say(f"      → exit {code}，{len(lines)} 行输出")
    return lines


# ---------------------------------------------------------------- 工作区 / 隔离栈


def preflight() -> None:
    missing = [tool for tool in ("docker", "rsync", "google-chrome", "convert", "identify")
               if shutil.which(tool) is None]
    if missing:
        sys.exit(f"缺少依赖：{', '.join(missing)}（本脚本不装新依赖）")
    if not (REPO / "backend" / ".venv" / "bin" / "python").exists():
        sys.exit("system/backend/.venv 不存在；先按第 0 页准备好环境")
    if not (REPO / ".env").is_file():
        sys.exit("缺少 .env；先按第 13 页 `make docker-env` 生成")
    for image in (IMAGE_BACKEND, IMAGE_FRONTEND):
        if subprocess.run(["docker", "image", "inspect", image],
                          capture_output=True, timeout=60).returncode != 0:
            sys.exit(f"本机没有 {image} 镜像；第 13 页 `make docker-up` 建过一次即可复用")
    for port in HOST_PORTS.values():
        if port_open(port):
            sys.exit(f"端口 {port} 被占用；本脚本不杀别人的进程，先停掉占用者再重跑")


def prepare_workdir() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    excludes = [".git", ".lab", "node_modules", "__pycache__", ".pytest_cache",
                ".mypy_cache", ".ruff_cache", ".venv-*", "*.pyc", "neg1.pid"]
    cmd = ["rsync", "-a"]
    for item in excludes:
        cmd += ["--exclude", item]
    cmd += [str(REPO) + "/", str(WORK) + "/"]
    subprocess.run(cmd, check=True, timeout=600)

    env_path = WORK / ".env"
    text = (REPO / ".env").read_text(encoding="utf-8")
    for var, port in HOST_PORTS.items():
        text, n = re.subn(rf"^{var}=.*$", f"{var}={port}", text, flags=re.M)
        if n != 1:
            raise RuntimeError(f"副本 .env 里找不到 {var}= 这一行")
    text, n = re.subn(r"^FRONTEND_BIND=.*$", "FRONTEND_BIND=127.0.0.1", text, flags=re.M)
    if n != 1:
        raise RuntimeError("副本 .env 里找不到 FRONTEND_BIND= 这一行")
    env_path.write_text(text, encoding="utf-8")
    say(f"临时副本：{WORK}（.env 端口改为隔离端口；页面命令执行时才替换）")
    return WORK


def compose(work: Path, args: str, timeout: float,
            allowed: tuple[int, ...] = (0,)) -> tuple[list[str], int]:
    cmd = f"docker compose -p {PROJECT} {args}"
    proc = subprocess.run(
        ["bash", "-c", cmd], cwd=work, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", timeout=timeout,
    )
    lines = (proc.stdout or "").splitlines()
    if proc.returncode not in allowed:
        raise RuntimeError(
            f"compose 命令失败（exit={proc.returncode}）：{cmd}\n"
            + "\n".join(lines[-40:])
        )
    return lines, proc.returncode


def container_health(name: str) -> str:
    """docker daemon 忙的时候 inspect 会偶发超时：重试几次，拿不到就返回 unknown。"""
    for _ in range(3):
        try:
            out = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{if .State.Health}}{{.State.Health.Status}}"
                 "{{else}}{{.State.Status}}{{end}}", name],
                capture_output=True, text=True, timeout=60,
            )
            return out.stdout.strip()
        except subprocess.TimeoutExpired:
            time.sleep(1)
    return "unknown"


def wait_healthy(names: tuple[str, ...], timeout: float = 240.0,
                 say_every: float = 0.0) -> None:
    t0 = time.monotonic()
    last = ""
    while time.monotonic() - t0 < timeout:
        states = {name: container_health(name) for name in names}
        last = " ".join(f"{name.replace(PROJECT + '-', '').replace('-1', '')}={s}"
                        for name, s in states.items())
        if all(state == "healthy" for state in states.values()):
            say(f"      → 全部 healthy（{time.monotonic() - t0:.0f}s）")
            return
        if say_every and time.monotonic() - t0 >= say_every:
            say(f"      … 等待中 {last}")
            say_every = 0.0
        time.sleep(2)
    raise RuntimeError(f"{timeout}s 内没有全部 healthy：{last}")


def es_disk_percent() -> int | None:
    try:
        url = f"http://127.0.0.1:{HOST_PORTS['ES_HOST_PORT']}/_cat/allocation?format=json"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(float(data[0]["disk.percent"]))
    except Exception:  # noqa: BLE001
        return None


def es_disable_watermark() -> None:
    url = (f"http://127.0.0.1:{HOST_PORTS['ES_HOST_PORT']}/_cluster/settings")
    body = json.dumps({"persistent": {
        "cluster.routing.allocation.disk.threshold_enabled": False}}).encode()
    req = urllib.request.Request(url, data=body, method="PUT",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def start_isolated_stack(work: Path, records: dict, extra: list[str]) -> None:
    """起隔离栈：先三存储（可关 ES 水位），再 init/backend/frontend。"""
    say("起隔离栈（project=shotsl3b，--no-build 复用 shopkeeper-rebuild/* 镜像）")
    compose(work, f"up -d --no-build {' '.join(('mysql', 'elasticsearch', 'qdrant'))}",
            timeout=180)
    wait_healthy(tuple(f"{PROJECT}-{s}-1" for s in ("mysql", "elasticsearch", "qdrant")),
                 timeout=240, say_every=30)
    pct = es_disk_percent()
    if pct is not None and pct >= 85:
        es_disable_watermark()
        extra.append(
            f"隔离 ES 磁盘 {pct}% 触发 disk watermark（本机根分区已 88%，ES 默认 low=85%）→ 在 shotsl3b 的 cluster settings "
            "里临时关闭 disk threshold（只存隔离卷，down -v 后消失）"
        )
        say(f"      磁盘 {pct}%：已临时关闭隔离 ES 的 disk watermark（只影响 shotsl3b）")
    else:
        say(f"      ES 磁盘 {pct}%：未触发水位，不动 cluster settings")

    for attempt in range(1, 4):
        say(f"起 init / backend / frontend（第 {attempt} 次）")
        lines, _ = compose(work, "up -d --no-build", timeout=600)
        init_code = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.ExitCode}}", f"{PROJECT}-init-1"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        if init_code == "0":
            log = subprocess.run(["docker", "logs", f"{PROJECT}-init-1"],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=60)
            text = (log.stdout or "") + (log.stderr or "")
            if "S2 VERIFY PASS" not in text:
                raise RuntimeError("init 退出 0 但日志里没有 S2 VERIFY PASS")
            say("      → init Exited (0)，S2 VERIFY PASS")
            break
        tail = "\n".join(lines[-15:])
        say(f"      → init 失败（exit={init_code}），重试；末 15 行：\n{tail}")
        time.sleep(5)
    else:
        raise RuntimeError("init 连续 3 次失败，隔离栈起不来")
    wait_healthy(tuple(f"{PROJECT}-{s}-1" for s in SERVICES), timeout=300, say_every=30)


def stop_isolated_stack(work: Path | None, records: dict) -> None:
    if work is None or not work.exists():
        return
    try:
        lines, _ = compose(work, "down -v --remove-orphans", timeout=300)
        records["cleanup_down"] = {"cmd": f"docker compose -p {PROJECT} down -v",
                                   "lines": lines[-5:], "exit": 0}
        say(f"  ✅ down -v：{len(lines)} 行输出（容器 / 卷 / 网络一起删）")
    except Exception as exc:  # noqa: BLE001
        say(f"  ⚠️ down -v 失败：{exc}")


# ---------------------------------------------------------------- 页面解析 / 自检


def page_text(page: int) -> str:
    return PAGE_MD[page].read_text(encoding="utf-8")


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    return re.findall(
        r"^```([A-Za-z]*)[ \t]*\n(.*?)^```[ \t]*$", text, re.S | re.M
    )


def section_text(page: int, heading: str) -> str:
    """取页面某个二级标题（`## 你应该看到` / `## 拆一刀`）的正文。"""
    text = page_text(page)
    m = re.search(rf"^{re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise RuntimeError(f"page-{page}.md 里找不到「{heading}」段")
    return m.group(1)


def blocks_of(page: int, heading: str) -> list[list[str]]:
    blocks = fenced_blocks(section_text(page, heading))
    return [[line.rstrip() for line in body.rstrip("\n").split("\n")]
            for _, body in blocks]


def find_block(blocks: list[list[str]], needle: str) -> list[str]:
    for block in blocks:
        if any(needle in line for line in block):
            return block
    raise RuntimeError(f"找不到含 {needle!r} 的代码块")


def norm_line(line: str) -> str:
    """对账用的归一化：去 ANSI、把连续空白压成一个空格、去首尾空白。"""
    return re.sub(r"[ \t\u00a0]+", " ", strip_ansi(line)).strip()


def block_segments(block: list[str]) -> list[list[str]]:
    """把样例块切成段：空行 / `#` 注释行 / 单独的 `...` `…` 都是分段标记。"""
    segments: list[list[str]] = []
    current: list[str] = []
    for line in block:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text in ("...", "…", "……"):
            if current:
                segments.append(current)
                current = []
            continue
        current.append(line)
    if current:
        segments.append(current)
    return segments


def wildcard_regex(expected: str) -> re.Pattern:
    # 秒数每次不同（页面也说明「秒数因机器而异」）：统一当通配符
    text = re.sub(r"in \d+\.\d+s", "in …", norm_line(expected))
    pattern = re.escape(text)
    pattern = pattern.replace(re.escape("…"), ".+?")
    return re.compile(pattern)


def check_expected(block: list[str], actual_lines: list[str]) -> tuple[bool, str]:
    """页面样例块 ↔ 真跑输出：每段里的行按顺序出现（可跳过真跑里的无关行）。"""
    actual = [norm_line(line) for line in actual_lines if norm_line(line)]
    pos = 0
    checked = 0
    for segment in block_segments(block):
        for line in segment:
            regex = wildcard_regex(line)
            found = False
            while pos < len(actual):
                if regex.search(actual[pos]):
                    found = True
                    pos += 1
                    break
                pos += 1
            if not found:
                return False, f"真跑输出里找不到：{line!r}"
            checked += 1
    return True, f"{checked} 行按顺序命中真跑输出（{len(actual)} 行）"


def check_key_lines(keys: list[str], actual_lines: list[str]) -> tuple[bool, str]:
    actual = [norm_line(line) for line in actual_lines if norm_line(line)]
    missing = []
    for key in keys:
        regex = wildcard_regex(key)
        if not any(regex.search(line) for line in actual):
            missing.append(key)
    if missing:
        return False, "未命中：" + " / ".join(repr(x) for x in missing)
    flat = [norm_line(x) for x in keys if norm_line(x)]
    return True, f"{len(flat)} 个关键字全部命中"


def check_presence(block: list[str], actual_lines: list[str]) -> tuple[bool, str]:
    """页面节选块 ↔ 真跑输出：每行都出现即可，**不要求顺序**。

    只用于「节选顺序 ≠ 终端顺序」的那一块：page-14 的拆一刀样例把
    `18 passed, 23 errors` 汇总行写在 `Failed:` 明细前面（方便阅读），
    而 pytest -q 的真实输出是错误明细在前、汇总在最后。这里验的是
    「页面上写的每一行，真跑输出里都有」，顺序交给渲染后的图去看。
    """
    actual = [norm_line(line) for line in actual_lines if norm_line(line)]
    missing: list[str] = []
    checked = 0
    for segment in block_segments(block):
        for line in segment:
            regex = wildcard_regex(line)
            if not any(regex.search(item) for item in actual):
                missing.append(line)
            checked += 1
    if missing:
        return False, "真跑输出里找不到：" + " / ".join(repr(x) for x in missing[:3])
    return True, f"{checked} 行全部命中真跑输出（{len(actual)} 行；节选顺序不参与对账）"


def ocr_text(png: Path, tmpdir: Path) -> str:
    """把深色终端图反色后 OCR；没装 tesseract / Pillow 就返回空串。"""
    if shutil.which("tesseract") is None:
        return ""
    try:
        from PIL import Image, ImageOps
    except Exception:  # noqa: BLE001
        return ""
    tmp = tmpdir / f"{png.stem}.ocr.png"
    with Image.open(png) as im:
        gray = ImageOps.invert(im.convert("L"))
        ImageOps.expand(gray, border=24, fill=255).save(tmp)
    try:
        chunks = []
        for psm in ("6", "11"):
            proc = subprocess.run(
                ["tesseract", str(tmp), "stdout", "--psm", psm],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180,
            )
            chunks.append(proc.stdout or "")
        return "\n".join(chunks)
    finally:
        tmp.unlink(missing_ok=True)


def squash(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z.]", "", text)


def check_forbidden(shot_texts: dict[str, list[str]],
                    passwords: list[str]) -> list[str]:
    hits = []
    for name, lines in shot_texts.items():
        for needle in FORBIDDEN + passwords:
            if needle and any(needle in line for line in lines):
                hits.append(f"{name}: {needle!r}")
    return hits


# ---------------------------------------------------------------- 截图 / 渲染


def chrome_screenshot(html_path: Path, png_path: Path, profile_dir: Path) -> None:
    png_path.unlink(missing_ok=True)
    cmd = [
        "google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
        "--hide-scrollbars", f"--force-device-scale-factor={DEVICE_SCALE}",
        f"--window-size={WINDOW_W_CSS},{WINDOW_H_CSS}",
        f"--user-data-dir={profile_dir}", f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError("chrome 截图失败：\n"
                           + (proc.stderr or proc.stdout or "")[-4000:])


def identify_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["identify", "-format", "%w %h", str(path)],
        check=True, capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    w, h = (int(x) for x in out.split())
    return w, h


def build_html(panes: list[dict]) -> str:
    chunks = []
    for pane in panes:
        rows: list[str] = []
        for item in pane["items"]:
            kind = item["kind"]
            if kind == "cmd":
                rows.extend(tr.html_cmd_lines(item["text"]))
            elif kind == "out":
                rows.extend(tr.html_out_line(line) for line in item["lines"])
            elif kind == "note":
                rows.append(f'<span class="dim">{tr.esc(item["text"])}</span>')
            else:
                raise ValueError(kind)
        chunks.append(
            f'<div class="pane"><div class="titlebar">{tr.esc(pane["title"])}</div>'
            f'<pre>{"\n".join(rows)}</pre></div>'
        )
    body = "\n".join(chunks)
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f"<style>{CSS}</style></head><body>"
        f'<div class="wrap">{body}</div></body></html>\n'
    )


def render_shot(shot: dict, records: dict, tmpdir: Path) -> Path:
    html_text = build_html(shot["panes"])
    stem = Path(shot["file"]).stem
    html_path = tmpdir / f"{stem}.html"
    html_path.write_text(html_text, encoding="utf-8")

    raw = tmpdir / f"{stem}.raw.png"
    chrome_screenshot(html_path, raw, tmpdir / f"chrome-{stem}")
    raw_w, _ = identify_size(raw)
    if raw_w != WINDOW_W_CSS * DEVICE_SCALE:
        raise RuntimeError(f"截图宽 {raw_w}px，不是 {WINDOW_W_CSS * DEVICE_SCALE}px")

    trimmed = tmpdir / f"{stem}.trim.png"
    subprocess.run(["convert", str(raw), "-trim", "+repage", str(trimmed)],
                   check=True, capture_output=True, timeout=120)
    _, h = identify_size(trimmed)
    target_h = min(max(h + PAD_PX, MIN_PNG_H), MAX_PNG_H)
    target = IMAGES / shot["file"]
    subprocess.run(
        ["convert", str(trimmed), "-gravity", "center",
         "-background", PAGE_BG, "-extent",
         f"{WINDOW_W_CSS * DEVICE_SCALE}x{target_h}", str(target)],
        check=True, capture_output=True, timeout=120,
    )
    final_w, final_h = identify_size(target)
    if final_w != WINDOW_W_CSS * DEVICE_SCALE or final_h < MIN_PNG_H:
        raise RuntimeError(f"{target.name} 尺寸 {final_w}x{final_h} 不符合 @2x 约定")
    say(f"    🖼  {target.relative_to(REPO)}  {final_w}x{final_h}")
    return target


# ---------------------------------------------------------------- 输出行选择（节选）

def find_line(lines: list[str], needle: str) -> str:
    for line in lines:
        if needle in line:
            return line
    raise RuntimeError(f"输出里找不到 {needle!r}；末 10 行：\n" + "\n".join(lines[-10:]))


def find_lines(lines: list[str], needle: str) -> list[str]:
    return [line for line in lines if needle in line]


def first_lines(lines: list[str], n: int) -> list[str]:
    return lines[:n]


def last_nonempty(lines: list[str]) -> str:
    for line in reversed(lines):
        if line.strip():
            return line
    raise RuntimeError("输出是空的")


def note(text: str) -> dict:
    return {"kind": "note", "text": text}


def out(lines: list[str]) -> dict:
    return {"kind": "out", "lines": lines}


def cmd(text: str) -> dict:
    return {"kind": "cmd", "text": text}


# 页面命令原文（渲染进图；执行时由 exec_cmd / with_env 换成隔离环境）
CMD14_SOURCE_STAGE3 = "source toolbox/scripts/export-docker-env.sh\nmake stage3"
CMD14_CURL = (
    "curl -s -N -X POST http://127.0.0.1:8080/api/query "
    "-H 'Content-Type: application/json' -d '{\"query\":\"华北销售额\"}' "
    "| grep '\"type\": \"result\"'"
)
CMD14_RECALL_RED = "(cd system/backend && REBUILD_INTEGRATION=1 .venv/bin/python -m pytest -q tests/recall)"
CMD14_RECALL_OFFLINE = "system/backend/.venv/bin/python -m pytest system/backend/tests/recall -q"
CMD15_BASELINE = "make baseline"
CMD15_SAVE = "toolbox/scripts/lab save p15-before"
CMD15_RESET = "toolbox/scripts/lab reset p15-before --yes"
CMD16_GUARD = "system/backend/.venv/bin/python -m pytest system/backend/tests/generate/test_guard.py -q"
CMD16_MATRIX = "(cd system/backend && .venv/bin/python -m app.scripts.failures --check)"
CMD16_PROBE = "PYTHONPATH=system/backend system/backend/.venv/bin/python system/eval/probe_correction.py | tail -1"
CMD16_DIST = (
    "grep -o '\"expect_code\": \"[A-Z_]*\"' system/eval/correction.jsonl "
    "| awk -F'\"' '{print $4}' | sort | uniq -c | sort -rn"
)
CMD17_SAVE = "toolbox/scripts/lab save p17-before"
CMD17_RESET = "toolbox/scripts/lab reset p17-before --yes"
CMD17_PYTEST = "system/backend/.venv/bin/python -m pytest system/backend/tests/agent/test_correct.py -q"
CMD17_MATRIX = "(cd system/backend && .venv/bin/python -m app.scripts.failures --check)"
CMD17_SCENARIOS = (
    "(cd system/backend && .venv/bin/python -m app.scripts.failures --scenarios | grep corrected)"
)
CMD17_COUNTS = (
    "grep -o '\"retryable\": [a-z]*' system/eval/correction.jsonl | sort | uniq -c\n"
    "grep -o '\"expect\": \"[a-z]*\"' system/eval/correction.jsonl | sort | uniq -c"
)
CMD17_ABL_PYTEST = CMD17_PYTEST
CMD17_ABL_MATRIX = (
    "(cd system/backend && PYTHONUNBUFFERED=1 .venv/bin/python -m app.scripts.failures --check) "
    "2>&1 | tail -5"
)
CMD17_ABL_PROBE = CMD16_PROBE


# ---------------------------------------------------------------- 捕获流程


def patch_contract_gmv(work: Path) -> None:
    path = work / "contracts" / "schema.contract.yaml"
    text = path.read_text(encoding="utf-8")
    anchor = "  - name: GMV\n"
    if text.count(anchor) != 1:
        raise RuntimeError("副本契约里找不到唯一的 `- name: GMV`")
    start = text.index(anchor)
    old = '    formula: "SUM(fact_order.order_amount)"'
    idx = text.find(old, start)
    if idx == -1 or idx > text.find("  - name:", start + 1):
        raise RuntimeError("GMV 块里没找到要改的 formula 行")
    new = '    formula: "SUM(fact_order.order_amount) / COUNT(DISTINCT fact_order.order_id)"'
    path.write_text(text[:idx] + new + text[idx + len(old):], encoding="utf-8")
    say("    改副本契约：GMV 的 formula 末尾加 / COUNT(DISTINCT fact_order.order_id)")


def patch_correct_off(work: Path) -> None:
    path = work / "backend" / "app" / "agent" / "correct.py"
    text = path.read_text(encoding="utf-8")
    anchor = "    contract = table or load_error_table()\n    policy = contract.correction\n"
    if text.count(anchor) != 1:
        raise RuntimeError("副本 correct.py 里找不到唯一的 policy = contract.correction")
    snippet = (
        "    # 拆一刀：关掉校正闭环——任何错误都不再产出候选 SQL\n"
        "    return CorrectionProposal(\n"
        '        attempted=False, ok=False, error=error, note="拆一刀：校正已关闭"\n'
        "    )\n"
    )
    path.write_text(text.replace(anchor, anchor + snippet), encoding="utf-8")
    say("    改副本 correct.py：propose_correction 入口直接返回「校正已关闭」")


TRANSIENT_MARKERS = (
    "连接 Qdrant 失败", "连接 Elasticsearch 失败", "连接 MySQL 失败",
    "timed out", "Timeout", "ReadTimeout", "ConnectionError",
    "Temporary failure in name resolution", "No route to host",
)


def capture_with_retry(records: dict, key: str, display_cmd: str, work: Path,
                       timeout: float, validate, attempts: int = 3,
                       allowed: tuple[int, ...] = (0,),
                       with_env: bool = False) -> list[str]:
    """本机 CPU/IO 被别的任务压满时，host→容器的连接会偶发超时；

    这类「不是判据红」的失败重跑即可（2026-11-19 本机 load 55+ 时实测过一次
    Qdrant 连接超时 4.5 分钟，同一命令单独重跑就过）。判据真的不成立时 validate
    会抛 RuntimeError，也会重试——重试 3 次仍不过才上报。
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            lines = captures_run(records, key, display_cmd, work, timeout,
                                 allowed=allowed, with_env=with_env)
            validate(lines)
            return lines
        except RuntimeError as exc:
            last_exc = exc
            text = str(exc)
            transient = any(marker in text for marker in TRANSIENT_MARKERS)
            if attempt == attempts:
                break
            say(f"      ⚠️  第 {attempt} 次不通过（{'疑似瞬时超时' if transient else '判据未命中'}），"
                f"5 秒后重试")
            time.sleep(5)
    raise RuntimeError(f"重试 {attempts} 次仍失败：{display_cmd}\n{last_exc}")


def capture_all(work: Path, records: dict, extra: list[str]) -> None:
    # ================================================== 第 14 页
    section("第 14 页 · 审检索（page-14.md）")
    run_quiet(records, "14_save", "toolbox/scripts/lab save p14-before", work, timeout=180)
    captures_run(records, "14_recall_offline", CMD14_RECALL_OFFLINE, work,
                 timeout=120)

    def check_stage3(lines: list[str]) -> None:
        for needle in ("S2 VERIFY PASS", "41 passed", "813 passed, 30 skipped", "S3 PASS"):
            if not find_lines(lines, needle):
                raise RuntimeError(f"make stage3 输出里没有 {needle!r}")

    capture_with_retry(records, "14_stage3", CMD14_SOURCE_STAGE3, work,
                       timeout=1200, validate=check_stage3, with_env=True)

    # 拆一刀：停 ES → 查数照常 → 黄金集整片红
    run_quiet(records, "14_stop_es", "docker compose stop elasticsearch",
              work, timeout=180, allowed=(0,))

    def check_query(lines: list[str]) -> None:
        if '[[41099.5]]' not in "".join(lines):
            raise RuntimeError("停 ES 后 /api/query 没有回 41099.5")

    capture_with_retry(records, "14_query", CMD14_CURL, work, timeout=120,
                       validate=check_query, with_env=True)

    def check_recall_red(lines: list[str]) -> None:
        if not find_lines(lines, "18 passed, 23 errors"):
            raise RuntimeError("停 ES 后黄金集没有 18 passed, 23 errors")
        if not any("'es': False" in line for line in lines):
            raise RuntimeError("停 ES 后黄金集的错误行里没有 'es': False（不是停 ES 的红）")
        if any("'es': True" in line for line in lines):
            raise RuntimeError("停 ES 后黄金集错误行里 'es': True（连到别的 ES 了）")

    capture_with_retry(records, "14_recall_red", CMD14_RECALL_RED, work,
                       timeout=300, validate=check_recall_red, allowed=(1,),
                       with_env=True)
    red = records["14_recall_red"]["lines"]

    # 还原：只把 ES 拉回来，等 healthy
    run_quiet(records, "14_start_es", "docker compose start elasticsearch",
              work, timeout=180)
    wait_healthy((f"{PROJECT}-elasticsearch-1",), timeout=180, say_every=30)
    extra.append("第 14 页：停 ES 后 /api/query 仍回 41099.5、黄金集 18 passed, 23 errors；"
                 "ES 已拉回 healthy")

    # ================================================== 第 15 页
    section("第 15 页 · 审生成（page-15.md，离线）")
    run_quiet(records, "15_save", CMD15_SAVE, work, timeout=180)
    captures_run(records, "15_baseline_green", CMD15_BASELINE, work, timeout=180)
    if not find_lines(records["15_baseline_green"]["lines"], "基线：10/10 通过（拒答 2）"):
        raise RuntimeError("基线绿的时候不是 10/10")
    patch_contract_gmv(work)
    captures_run(records, "15_baseline_red", CMD15_BASELINE, work, timeout=180,
                 allowed=(2,))
    red15 = records["15_baseline_red"]["lines"]
    if not find_lines(red15, "基线：8/10 通过（拒答 2）"):
        raise RuntimeError("改坏 GMV 后基线不是 8/10")
    if not find_lines(red15, "SQL_UNKNOWN_COLUMN"):
        raise RuntimeError("改坏 GMV 后 FAIL 行里没有 SQL_UNKNOWN_COLUMN")
    run_quiet(records, "15_reset", CMD15_RESET, work, timeout=180)
    captures_run(records, "15_baseline_green2", CMD15_BASELINE, work, timeout=180)
    if not find_lines(records["15_baseline_green2"]["lines"], "基线：10/10 通过（拒答 2）"):
        raise RuntimeError("reset 后基线没有回到 10/10")

    # ================================================== 第 16 页
    section("第 16 页 · 审校验（page-16.md，离线）")
    captures_run(records, "16_guard", CMD16_GUARD, work, timeout=180)
    if not find_lines(records["16_guard"]["lines"], "26 passed"):
        raise RuntimeError("test_guard.py 不是 26 passed")
    captures_run(records, "16_matrix", CMD16_MATRIX, work, timeout=180)
    matrix = records["16_matrix"]["lines"]
    if not find_lines(matrix, "S6 PASS"):
        raise RuntimeError("失败矩阵没有 S6 PASS")
    captures_run(records, "16_probe", CMD16_PROBE, work, timeout=120)
    if not find_lines(records["16_probe"]["lines"], '{"total": 20, "mismatch": 0}'):
        raise RuntimeError("probe_correction 不是 total 20 / mismatch 0")
    captures_run(records, "16_dist", CMD16_DIST, work, timeout=120)

    # ================================================== 第 17 页
    section("第 17 页 · 审纠错（page-17.md，离线）")
    run_quiet(records, "17_save", CMD17_SAVE, work, timeout=180)
    captures_run(records, "17_pytest", CMD17_PYTEST, work, timeout=180)
    if not find_lines(records["17_pytest"]["lines"], "14 passed"):
        raise RuntimeError("test_correct.py 不是 14 passed")
    captures_run(records, "17_matrix", CMD17_MATRIX, work, timeout=180)
    if not find_lines(records["17_matrix"]["lines"], "S6 PASS"):
        raise RuntimeError("第 17 页失败矩阵没有 S6 PASS")
    captures_run(records, "17_scenarios", CMD17_SCENARIOS, work, timeout=180)
    captures_run(records, "17_counts", CMD17_COUNTS, work, timeout=120)
    counts = records["17_counts"]["lines"]
    for needle in ("11 \"retryable\": true", "9 \"retryable\": false",
                   "11 \"expect\": \"corrected\"", "9 \"expect\": \"rejected\""):
        if not find_lines(counts, needle):
            raise RuntimeError(f"第 17 页统计里没有 {needle!r}")

    # 拆一刀：关掉纠错入口 → 三条判据的三种反应
    patch_correct_off(work)
    captures_run(records, "17_abl_pytest", CMD17_ABL_PYTEST, work, timeout=180,
                 allowed=(1,))
    if not find_lines(records["17_abl_pytest"]["lines"], "5 failed, 9 passed"):
        raise RuntimeError("拆掉纠错后 pytest 不是 5 failed, 9 passed")
    captures_run(records, "17_abl_matrix", CMD17_ABL_MATRIX, work, timeout=180)
    abl = records["17_abl_matrix"]["lines"]
    for needle in ("实际 SQL_SYNTAX", "FAIL: 1 项不符合预期",
                   "corrected: 应当成功，实际是 SQL_SYNTAX"):
        if not find_lines(abl, needle):
            raise RuntimeError(f"拆掉纠错后失败矩阵里没有 {needle!r}")
    captures_run(records, "17_abl_probe", CMD17_ABL_PROBE, work, timeout=120)
    if not find_lines(records["17_abl_probe"]["lines"], '{"total": 20, "mismatch": 0}'):
        raise RuntimeError("拆掉纠错后 probe 不是 mismatch 0（页面说语料判据抓不到）")

    # 还原并回绿
    run_quiet(records, "17_reset", CMD17_RESET, work, timeout=180)
    captures_run(records, "17_green_pytest", f"{CMD17_PYTEST} | tail -1", work,
                 timeout=180)
    captures_run(records, "17_green_matrix", f"{CMD17_MATRIX} | tail -1", work,
                 timeout=180)
    if "14 passed" not in records["17_green_pytest"]["lines"][-1]:
        raise RuntimeError("reset 后第 17 页 pytest 没有回 14 passed")
    if "S6 PASS" not in records["17_green_matrix"]["lines"][-1]:
        raise RuntimeError("reset 后第 17 页失败矩阵没有回 S6 PASS")
    extra.append("第 17 页：拆一刀后 pytest 5 failed / 矩阵 FAIL: 1 项 / 语料 mismatch 0；"
                 "reset 后回 14 passed + S6 PASS")


# ---------------------------------------------------------------- 渲染数据（节选真实输出）


def shot_stage3(records: dict) -> dict:
    lines = records["14_stage3"]["lines"]
    counts = [line for line in lines
              if line.startswith(("counts:", "  Meta", "  ES", "  Qdrant"))]
    return {
        "file": "page-14-stage3.png",
        "panes": [{
            "title": "终端 · 第 3 步：source 环境变量后 make stage3"
                     "（S2 三方对账 → 20 题黄金集 → 全量回归；节选）",
            "items": [
                cmd(CMD14_SOURCE_STAGE3),
                out([find_line(lines, "== S3 · S2 三存储对账 ==")] + counts
                    + [find_line(lines, "S2 VERIFY PASS")]),
                out([find_line(lines, "== S3 · 20 题黄金集（真实 ES/Qdrant/Meta） =="),
                     find_line(lines, "41 passed")]),
                out([find_line(lines, "== S3 · CLI 输出 YAML（stdout）与检索统计（stderr） =="),
                     find_line(lines, "recall stats:")]),
                note("…（YAML 输出 40 行、各段测试进度点省略）"),
                out([find_line(lines, "== S3 · 全部后端测试（S0 + S1 + S2 + S3） =="),
                     find_line(lines, "813 passed"),
                     find_line(lines, "S3 PASS")]),
            ],
        }],
    }


def shot_stop_es(records: dict) -> dict:
    red = records["14_recall_red"]["lines"]
    return {
        "file": "page-14-stop-es.png",
        "panes": [
            {
                "title": "终端 · 停掉 Elasticsearch 之后：POST /api/query 照常回 41099.5"
                         "（主链路走契约离线裁剪，不连检索）",
                "items": [
                    cmd(CMD14_CURL),
                    out([find_line(records["14_query"]["lines"], '"type": "result"')]),
                ],
            },
            {
                "title": "同一终端 · 20 题黄金集整片变红：18 passed, 23 errors"
                         "（检索存储没了，判据不悄悄退回离线）",
                "items": [
                    cmd(CMD14_RECALL_RED),
                    out([find_line(red, "Failed: REBUILD_INTEGRATION=1")]),
                    note("…（20 条同样的 Failed，逐条省略）"),
                    out([find_line(red, "18 passed, 23 errors")]),
                ],
            },
        ],
    }


def shot_baseline(records: dict) -> dict:
    green = records["15_baseline_green"]["lines"]
    red = records["15_baseline_red"]["lines"]
    return {
        "file": "page-15-baseline.png",
        "panes": [
            {
                "title": "终端 · 第 3 步：make baseline 绿——基线：10/10 通过（拒答 2）"
                         "（表格节选两行）",
                "items": [
                    cmd(CMD15_BASELINE),
                    out([find_line(green, "| 问题 |"),
                         find_line(green, "| 华北销售额 |"),
                         find_line(green, "| 平均客单价 |")]),
                    note("…（其余 8 行同表，6 行 PASS + 2 行 REFUSAL，省略）"),
                    out([find_line(green, "基线：10/10")]),
                ],
            },
            {
                "title": "拆一刀 · 把契约里 GMV 的 formula 改坏后：make baseline 红——"
                         "基线：8/10 通过（拒答 2）",
                "items": [
                    cmd(CMD15_BASELINE),
                    out([find_line(red, "| 问题 |"),
                         find_line(red, "| 华北销售额 |"),
                         find_line(red, "| 品牌销售额 Top 3 |")]),
                    note("…（其余 8 行省略；b02 平均客单价仍 PASS——判据按指标精确命中）"),
                    out([find_line(red, "基线：8/10"),
                         find_line(red, "失败明细：")] +
                        [line for line in red
                         if re.match(r"^  - b0[14]:", line)] +
                        [find_line(red, "make: ***")]),
                ],
            },
        ],
    }


def shot_guard(records: dict) -> dict:
    matrix = records["16_matrix"]["lines"]
    dist = [line for line in records["16_dist"]["lines"] if line.strip()]
    return {
        "file": "page-16-guard.png",
        "panes": [
            {
                "title": "终端 · 第 2 步：pytest test_guard.py——静态校验 26 条全过",
                "items": [
                    cmd(CMD16_GUARD),
                    out([last_nonempty(records["16_guard"]["lines"])]),
                ],
            },
            {
                "title": "第 3 步：失败矩阵（9 个场景）+ 16 码表——S6 PASS",
                "items": [
                    cmd(CMD16_MATRIX),
                    out([find_line(matrix, "sql_unknown_column")]),
                    note("…（另外 8 个场景同格式：码 / 类别 / 失败步骤与 scenarios.yaml 一致）"),
                    out([find_line(matrix, "错误码表："),
                         find_line(matrix, "S6 PASS")]),
                ],
            },
            {
                "title": "第 4 步：20 条错单的期望码对账 + 码分布——mismatch 0",
                "items": [
                    cmd(CMD16_PROBE),
                    out([find_line(records["16_probe"]["lines"], '"total"')]),
                    cmd(CMD16_DIST),
                    out(dist[:6]),
                    note("…（其余 4 个码各 1 条：SQL_MULTIPLE_STATEMENTS / "
                         "SQL_MISSING_ORDER_BY / SQL_MISSING_LIMIT / SQL_EMPTY）"),
                ],
            },
        ],
    }


def shot_correct(records: dict) -> dict:
    matrix = records["17_matrix"]["lines"]
    counts = [line for line in records["17_counts"]["lines"] if line.strip()]
    return {
        "file": "page-17-correct.png",
        "panes": [
            {
                "title": "终端 · 第 2 步：pytest test_correct.py——14 条全过",
                "items": [
                    cmd(CMD17_PYTEST),
                    out([last_nonempty(records["17_pytest"]["lines"])]),
                ],
            },
            {
                "title": "第 3 步：失败矩阵——corrected 的期望和实际都是 result，S6 PASS",
                "items": [
                    cmd(CMD17_MATRIX),
                    out([find_line(matrix, "corrected")]),
                    note("…（另外 8 个场景同格式，省略）"),
                    out([find_line(matrix, "错误码表："),
                         find_line(matrix, "S6 PASS")]),
                ],
            },
            {
                "title": "第 4 步：corrected 的期望行 + 20 条语料的可重试 / 标记统计",
                "items": [
                    cmd(CMD17_SCENARIOS),
                    out([last_nonempty(records["17_scenarios"]["lines"])]),
                    cmd(CMD17_COUNTS),
                    out(counts),
                ],
            },
        ],
    }


def shot_ablation(records: dict) -> dict:
    pytest_lines = records["17_abl_pytest"]["lines"]
    matrix = records["17_abl_matrix"]["lines"]
    return {
        "file": "page-17-ablation.png",
        "panes": [
            {
                "title": "拆一刀 · 关掉纠错入口后：pytest 5 failed, 9 passed"
                         "（5 条都在断言校正入口会产出候选）",
                "items": [
                    cmd(CMD17_ABL_PYTEST),
                    note("…（失败明细按节选省略）"),
                    out([line for line in pytest_lines
                         if line.startswith("5 failed, 9 passed")]),
                ],
            },
            {
                "title": "同一刀 · 失败矩阵 9 个场景只红 corrected 一格，FAIL: 1 项不符合预期",
                "items": [
                    cmd(CMD17_ABL_MATRIX),
                    out(matrix),
                ],
            },
            {
                "title": "同一刀 · 20 条语料照绿：语料判据量的是 guard / policy 发什么码，"
                         "不量校正做没做",
                "items": [
                    cmd(CMD17_ABL_PROBE),
                    out([find_line(records["17_abl_probe"]["lines"], '"total"')]),
                ],
            },
        ],
    }


# ---------------------------------------------------------------- 自检


def find_exact(lines: list[str], needle: str) -> bool:
    return any(norm_line(line) == norm_line(needle) for line in lines)


def run_checks(records: dict, extra: list[str], tmpdir: Path) -> bool:
    section("图文一致性自检（页面「你应该看到」↔ 真跑输出）")
    all_ok = True

    def lines_of(*keys: str) -> list[str]:
        merged: list[str] = []
        for key in keys:
            merged.extend(records[key]["lines"])
        return merged

    def green_15_block() -> list[str]:
        """page-15「你应该看到」第 2 块：`make baseline` 绿的那两行 + 基线，截到 S4 段前。"""
        block: list[str] = []
        for line in find_block(blocks_of(15, "## 你应该看到"), "基线：10/10"):
            if line.startswith("== S4 · 生成层测试"):
                break
            if line.startswith("== S4"):
                continue
            block.append(line)
        return block

    # 每块都是页面原文里的一段样例；`…` 当通配符、`...` 行当分段标记、`#` 行是标注跳过。
    # 第 16/17 页的「你应该看到」一块里混了三条命令的输出，这里按页面顺序拼起来对账。
    # 第 14 页的停 ES 两段在「拆一刀」里（页面「你应该看到」只讲主线）。
    page_blocks = {
        "14_offline": (14, blocks_of(14, "## 你应该看到")[0]),
        "14_stage3": (14, blocks_of(14, "## 你应该看到")[1]),
        "14_query": (14, find_block(blocks_of(14, "## 拆一刀"),
                                    'data: {"type": "result"')),
        "14_red": (14, find_block(blocks_of(14, "## 拆一刀"), "18 passed, 23 errors")),
        "15_green": (15, green_15_block()),
        "15_red": (15, find_block(blocks_of(15, "## 拆一刀"), "基线：8/10")),
        "16_all": (16, blocks_of(16, "## 你应该看到")[0]),
        "17_all": (17, blocks_of(17, "## 你应该看到")[0]),
        "17_abl": (17, find_block(blocks_of(17, "## 拆一刀（L3 级考核）"),
                                  "5 failed, 9 passed")),
    }
    block_checks = [
        ("page-14-stage3.png", "14_stage3", lines_of("14_stage3")),
        ("page-14-stop-es.png", "14_query", lines_of("14_query")),
        ("page-14-stop-es.png", "14_red", lines_of("14_recall_red")),
        ("page-15-baseline.png", "15_green", lines_of("15_baseline_green")),
        ("page-15-baseline.png", "15_red", lines_of("15_baseline_red")),
        ("page-16-guard.png", "16_all",
         lines_of("16_guard", "16_matrix", "16_probe", "16_dist")),
        ("page-17-correct.png", "17_all",
         lines_of("17_pytest", "17_matrix", "17_scenarios", "17_counts")),
        ("page-17-ablation.png", "17_abl",
         lines_of("17_abl_pytest", "17_abl_matrix", "17_abl_probe")),
    ]
    # 14_red 的节选顺序和 pytest 真实输出顺序相反（汇总行在页面上提前），
    # 这一块按「每行都在」对账；其余块仍要求按顺序命中。
    presence_only = {"14_red"}
    for shot_name, key, actual in block_checks:
        page, block = page_blocks[key]
        if key in presence_only:
            ok, detail = check_presence(block, actual)
        else:
            ok, detail = check_expected(block, actual)
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} {shot_name} ← page-{page}.md（{key}）：{detail}")

    # 任务点名的关键行：逐条命中（避免样例块里被 `…` 放宽掉）
    section("关键行逐条核对（任务点名的判据）")
    key_checks = [
        ("page-14-stage3.png", "14_stage3",
         ["S3 PASS", "S2 VERIFY PASS", "41 passed", "813 passed, 30 skipped"]),
        ("page-14-stop-es.png", "14_query", ["41099.5"]),
        ("page-14-stop-es.png", "14_recall_red", ["18 passed, 23 errors"]),
        ("page-15-baseline.png", "15_baseline_green", ["基线：10/10 通过（拒答 2）"]),
        ("page-15-baseline.png", "15_baseline_red", ["基线：8/10 通过（拒答 2）"]),
        ("page-16-guard.png", "16_guard", ["26 passed"]),
        ("page-16-guard.png", "16_matrix", ["S6 PASS"]),
        ("page-16-guard.png", "16_probe", ['{"total": 20, "mismatch": 0}']),
        ("page-17-correct.png", "17_pytest", ["14 passed"]),
        ("page-17-correct.png", "17_matrix", ["S6 PASS"]),
        ("page-17-ablation.png", "17_abl_pytest", ["5 failed, 9 passed"]),
        ("page-17-ablation.png", "17_abl_probe", ['{"total": 20, "mismatch": 0}']),
    ]
    for shot_name, key, keys in key_checks:
        ok, detail = check_key_lines(keys, records[key]["lines"])
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} {shot_name} ← {key}：{detail}")

    # 页面命令逐字核对：图里显示的命令必须真的出现在页面正文里
    section("页面命令逐字核对（图里显示的命令 = 页面原文）")
    command_pairs = [
        (14, CMD14_SOURCE_STAGE3), (14, CMD14_CURL), (14, CMD14_RECALL_RED),
        (14, CMD14_RECALL_OFFLINE),
        (15, CMD15_BASELINE), (15, CMD15_SAVE), (15, CMD15_RESET),
        (16, CMD16_GUARD), (16, CMD16_MATRIX), (16, CMD16_PROBE), (16, CMD16_DIST),
        (17, CMD17_PYTEST), (17, CMD17_MATRIX), (17, CMD17_SCENARIOS),
        (17, CMD17_COUNTS), (17, CMD17_ABL_MATRIX), (17, CMD17_ABL_PROBE),
    ]
    for page, display in command_pairs:
        text = page_text(page)
        ok = all(line.strip() in text for line in display.split("\n"))
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} page-{page}.md 含：{display.splitlines()[0]}"
            + (f"（共 {len(display.splitlines())} 行）" if "\n" in display else ""))

    # 图片嵌入行：脚本不写页面，只核对页面里已经有了
    section("页面图片嵌入行核对（脚本不写页面）")
    for page, lines in EMBED_LINES.items():
        text = page_text(page)
        for line in lines:
            ok = line in text
            all_ok = all_ok and ok
            say(f"  {'✅' if ok else '⚠️ '} page-{page}.md 嵌入行：{line[:52]}…")

    # OCR：图里英文/数字关键字能不能真扫出来
    section("OCR 关键字抽检（对 PNG 反色后 tesseract）")
    shots_dir = IMAGES
    for name, keywords in OCR_KEYWORDS.items():
        png = shots_dir / name
        text = ocr_text(png, tmpdir)
        if not text:
            say(f"  ⚠️  {name}：没有 tesseract/Pillow，跳过 OCR（主对账已用渲染前原文完成）")
            continue
        flat = squash(text)
        miss = [kw for kw in keywords if squash(kw) not in flat]
        ok = not miss
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} {name}：{len(keywords) - len(miss)}/{len(keywords)} 命中"
            + (f"，未命中 {miss}" if miss else ""))

    # 尺寸 + 禁止字符串
    section("PNG 尺寸 / 图内禁止字符串")
    for name in OCR_KEYWORDS:
        png = IMAGES / name
        w, h = identify_size(png)
        ok = w == WINDOW_W_CSS * DEVICE_SCALE and h >= MIN_PNG_H
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} {name}  {w}x{h}（@2x，宽 {WINDOW_W_CSS * DEVICE_SCALE}）")

    shot_texts = {}
    for name in OCR_KEYWORDS:
        path = shots_dir / name
        # 图里出现的就是渲染进去的文本：直接从 HTML 里抽出来核对太绕，改用捕获到的
        # 命令 + 展示行（和渲染时同一份数据）。
        shot_texts[name] = records["__display__"][name]
    passwords = []
    env_text = (REPO / ".env").read_text(encoding="utf-8")
    for line in env_text.splitlines():
        m = re.match(r"^(MYSQL_ROOT_PASSWORD|MYSQL_PASSWORD|REBUILD_DW_RO_PASSWORD)=(.*)$",
                     line.strip())
        if m and m.group(2):
            passwords.append(m.group(2))
    hits = check_forbidden(shot_texts, passwords)
    if hits:
        all_ok = False
        say(f"  ❌ 图内出现禁止字符串：{hits}")
    else:
        say(f"  ✅ 6 张图内容无用户名 / 主机名 / 绝对路径 / 隔离端口 / 口令"
            f"（检查了 {', '.join(sorted(shot_texts))}）")
    for line in extra:
        say(f"  ℹ️  {line}")
    return all_ok


# ---------------------------------------------------------------- 主流程


def save_captures(records: dict) -> None:
    data = {k: v for k, v in records.items() if not k.startswith("__")}
    CAPTURES.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    say(f"  捕获缓存：{CAPTURES}（调试用；正常跑完会删）")


def build_shots(records: dict) -> list[dict]:
    return [
        shot_stage3(records),
        shot_stop_es(records),
        shot_baseline(records),
        shot_guard(records),
        shot_correct(records),
        shot_ablation(records),
    ]


def collect_display_text(shots: list[dict]) -> dict[str, list[str]]:
    out_map = {}
    for shot in shots:
        lines: list[str] = []
        for pane in shot["panes"]:
            lines.append(pane["title"])
            for item in pane["items"]:
                if item["kind"] == "cmd":
                    lines.extend(item["text"].split("\n"))
                elif item["kind"] == "out":
                    lines.extend(item["lines"])
                elif item["kind"] == "note":
                    lines.append(item["text"])
        out_map[shot["file"]] = lines
    return out_map


def render_all(shots: list[dict], records: dict, tmpdir: Path) -> list[Path]:
    section("渲染终端截图（真跑输出 → 深色终端版式）")
    targets = []
    for shot in shots:
        targets.append(render_shot(shot, records, tmpdir))
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="渲染练本 L3 第 14–17 页的真跑截图")
    parser.add_argument("--render-only", metavar="CAPTURES_JSON",
                        help="不跑命令，用上次的捕获缓存只重渲染（调试用）")
    parser.add_argument("--keep", action="store_true",
                        help="跑完保留 /tmp/shots-l3b 和隔离栈（调试用；正常会清）")
    args = parser.parse_args(argv)

    t_start = time.monotonic()
    say("=" * 78)
    say("render_l3_pages.py —— 真跑 L3 第 14/15/16/17 页命令，生成 6 张终端运行截图")
    say(f"仓库：{REPO}")
    say(f"输出：{IMAGES.relative_to(REPO)}/page-1[4-7]-*.png 6 张"
        f"（宽 {WINDOW_W_CSS * DEVICE_SCALE}px，@2x，高 ≥{MIN_PNG_H}px）")
    say("=" * 78)
    IMAGES.mkdir(parents=True, exist_ok=True)

    if args.render_only:
        path = Path(args.render_only)
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = {k: {"cmd": v["cmd"], "lines": v["lines"],
                       "exit": v.get("exit", 0)} for k, v in raw.items()}
        shots = build_shots(records)
        records["__display__"] = collect_display_text(shots)
        with tempfile.TemporaryDirectory(prefix="shots-l3-render-") as tmp:
            render_all(shots, records, Path(tmp))
            ok = run_checks(records, ["--render-only：未跑命令，仅用捕获缓存重渲染"],
                            Path(tmp))
        say("")
        say(f"完成（render-only），用时 {time.monotonic() - t_start:.1f}s。")
        return 0 if ok else 2

    # 正常流程
    # 上一轮残留（本脚本自己的 project）先清掉——否则它会占着隔离端口，preflight 会误判
    if any(name.startswith(f"{PROJECT}-") for name in docker_names()):
        say(f"发现上一轮残留的 {PROJECT}-* 容器，先 down -v 清掉（不影响用户栈）")
        tmp_work = WORK if (WORK / ".env").exists() else REPO
        compose(tmp_work, "down -v --remove-orphans", timeout=300, allowed=(0, 1))
    preflight()
    work: Path | None = None
    stack_started = False
    user_before = docker_snapshot()
    records: dict = {}
    extra: list[str] = []
    try:
        work = prepare_workdir()
        with tempfile.TemporaryDirectory(prefix="shots-l3-render-") as tmp:
            start_isolated_stack(work, records, extra)
            stack_started = True
            capture_all(work, records, extra)
            save_captures(records)
            shots = build_shots(records)
            records["__display__"] = collect_display_text(shots)
            render_all(shots, records, Path(tmp))
            ok = run_checks(records, extra, Path(tmp))
        return 0 if ok else 2
    except KeyboardInterrupt:
        say("\n被 Ctrl+C 中断，开始清理……")
        return 130
    except Exception as exc:  # noqa: BLE001
        say(f"\n❌ 出错：{exc}")
        return 1
    finally:
        if not args.keep:
            section("清理")
            if stack_started or any(n.startswith(f"{PROJECT}-") for n in docker_names()):
                stop_isolated_stack(work, records)
            else:
                say("  隔离栈未启动，无需 down")
            tmp_recall = Path("/tmp/rebuild-s3-recall.yaml")
            if tmp_recall.exists():
                tmp_recall.unlink()
                say("  ✅ 删掉 /tmp/rebuild-s3-recall.yaml")
            if work is not None and work.exists():
                shutil.rmtree(work, ignore_errors=True)
            if WORK.exists():
                say(f"  ⚠️  {WORK} 没删掉，请手动检查")
            else:
                say(f"  ✅ 临时副本已删：{WORK}")
            if CAPTURES.exists() and not args.keep:
                CAPTURES.unlink(missing_ok=True)
                say(f"  ✅ 捕获缓存已删：{CAPTURES}")
            leftovers = [n for n in docker_names() if n.startswith(f"{PROJECT}-")]
            if leftovers:
                say(f"  ⚠️  仍有 {PROJECT}-* 容器：{leftovers}，请手动检查")
            else:
                say(f"  ✅ 无 {PROJECT}-* 容器 / 卷 / 网络残留")
            # 仓库 uv.lock 若被改（uv 镜像配置会静默重写），还原掉
            lock = REPO / "backend" / "uv.lock"
            tracked = subprocess.run(
                ["git", "-C", str(REPO), "status", "--porcelain", "--",
                 "system/backend/uv.lock"],
                capture_output=True, text=True, timeout=60,
            ).stdout.strip()
            if tracked:
                subprocess.run(["git", "-C", str(REPO), "checkout", "--",
                                "system/backend/uv.lock"], timeout=60)
                say("  ✅ system/backend/uv.lock 被改过，已 git checkout -- 还原（仓库副本未动）")
            else:
                say("  ✅ system/backend/uv.lock 未被改动（命令都在 /tmp 副本里跑）")
            user_after = docker_snapshot()
            if user_before == user_after:
                say(f"  ✅ 用户栈未变（{len(user_before)} 个非 {PROJECT}- 容器前后一致）")
            else:
                say("  ⚠️  用户容器前后不一致（下面只影响本脚本的 project，请人工确认）：")
                say(f"      before-only: {sorted(set(user_before) - set(user_after))}")
                say(f"      after-only : {sorted(set(user_after) - set(user_before))}")
            say(f"完成，用时 {time.monotonic() - t_start:.1f}s。")
        else:
            say(f"\n--keep：保留 {WORK} 与隔离栈（project={PROJECT}）。")
            say(f"完成，用时 {time.monotonic() - t_start:.1f}s。")


if __name__ == "__main__":
    sys.exit(main())
