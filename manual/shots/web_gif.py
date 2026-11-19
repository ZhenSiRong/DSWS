#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""web_gif.py —— 真跑第 9 页（MySQL 3307 + uvicorn 8000 + nginx 8081），
用本机 Chrome 录一条**真浏览器操作**的 GIF：敲问题 → 点「问一句」→ SSE 进度逐条刷新 → 41099.5。

在仓库根目录一条命令重跑：

    python3 manual/shots/web_gif.py

输出（只新增这一个文件，不动已有 PNG）：

    manual/images/page-09-demo.gif   约 6.5 秒循环，含最终结果停留 2.5 秒以上

它做四件事（复用 web_shots.py 的真三层环境，不改原脚本）：

1. 在 /tmp 建临时工作区：软链 `backend/`（复用仓库 venv），拷入 `fixtures/dw.sql`
   和 `.env.example`，写 `lab/app.py`（复用 term_render.py 的 APP_PAGE_08，即第 3–8 页
   产物的最终形态）、第 9 页逐字的 `lab/default.conf` / `lab/index.html`。
2. 起三层环境（容器名带 shots- 前缀，与用户自己的 lab-* 栈隔离）：
   `shots-web-mysql`（127.0.0.1:3307）→ uvicorn `--host 0.0.0.0 --port 8000` →
   `shots-web-nginx`（127.0.0.1:8081）。
3. Playwright（frontend/node_modules/playwright-core）驱动 /usr/bin/google-chrome：
   打开 8081 → `#q` 清空 → 逐字敲「华北销售额」（delay≈60ms）→ 点「问一句」→
   每约 120ms 截一帧，直到 `#out` 文本是 `41099.5` 后再多截约 1.6 秒（约 15 帧）。
4. 所有帧统一裁掉页面上下空白（与 page-09-browser-ok.png 同一套裁剪逻辑：宽度 1100px、
   内容上下各留 32px、1px 灰边），按 120ms 采样成 12.5fps 帧序列，再用
   `convert -delay 8 -loop 0 -layers Optimize` 合成 GIF；首帧停留约 1 秒、
   末帧（41099.5）停留 2.5 秒以上，整条循环约 6.5 秒。
   跑完自动 `docker rm -f` 两个容器、停 uvicorn、删临时工作区，不留端口占用。

自检（脚本里真做，失败即退出码 1）：
  - 页面 DOM 文本必须有 41099.5，且无用户名 / 主机名 / 绝对路径 / 端口；
  - 首 / 中 / 末三帧 `compare -metric AE` 证明画面确实在变；
  - 末帧 tesseract OCR 必须读出 `41099.5`；
  - GIF 尺寸 / 帧数 / 字节数打印出来，目标 ≤ 2.5MB。

依赖（本机已装，不新装）：docker、google-chrome、ImageMagick、node、tesseract；
仓库的 `backend/.venv` 与 `frontend/node_modules/playwright-core`。
端口只用 3307 / 8000 / 8081，不碰用户的 dsws-lab-ui-* 栈（18081 等）。
"""

from __future__ import annotations

import getpass
import importlib.util
import json
import os
import re
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

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"
PLAYWRIGHT_CORE = REPO / "frontend" / "node_modules" / "playwright-core"
CHROME = "/usr/bin/google-chrome"

WINDOW_W = 1100          # 与 page-09-browser-ok.png 同一窗宽 / 成品宽度
VIEWPORT_H = 720         # 截图视口高；成品只保留有内容的上下范围
CROP_PAD = 32            # 裁掉空白后上下各留的像素（与 web_shots.py 一致）
BORDER_PX = 1            # 1px 灰边，与现有 PNG 一致

MYSQL_PORT = 3307
API_PORT = 8000
WEB_PORT = 8081
MYSQL_CONTAINER = "shots-web-mysql"
NGINX_CONTAINER = "shots-web-nginx"
MYSQL_IMAGE_FALLBACK = "docker.m.daocloud.io/library/mysql:8.0"
NGINX_IMAGE_FALLBACK = "docker.m.daocloud.io/library/nginx:1.27-alpine"

GIF = IMAGES / "page-09-demo.gif"
GIF_MAX_BYTES = 2_500_000
SAMPLE_MS = 120          # 每 120ms 采一帧
GIF_DELAY = 8            # 8/100 秒 = 12.5fps，与「12fps 左右」一致
STEPS = ["extract_keywords", "recall_column", "recall_value", "recall_metric",
         "merge_retrieved_info", "filter_table", "filter_metric", "add_extra_context",
         "generate_sql", "validate_sql", "correct_sql", "run_sql"]

GIF_TARGET_SECONDS = 6.5
FINAL_HOLD_MIN_SECONDS = 2.5
PRE_ROLL_FRAMES = 12     # 开头先停约 0.96 秒，让人看清页面

# ---------------------------------------------------------------- 第 3–8 页的 lab/app.py


def load_app_py() -> str:
    """复用 term_render.py 里「按页序组装」出的 APP_PAGE_08，避免两处 app.py 漂移。"""
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
    app_py = getattr(module, "APP_PAGE_08", None)
    if not isinstance(app_py, str) or not app_py.strip():
        raise RuntimeError(f"{path} 里没有 APP_PAGE_08")
    if "text/event-stream" not in app_py or "/api/stream" not in app_py:
        raise RuntimeError("term_render.py 的 APP_PAGE_08 不是第 8 页最终形态（缺 /api/stream）")
    return app_py


# ---------------------------------------------------------------- 第 9 页逐字代码
# 与 manual/page-09.md「动手」第 2 步的两段代码逐字一致。

DEFAULT_CONF = """\
server {
    listen 80;
    location / { root /usr/share/nginx/html; }
    location /api/ {
        proxy_pass http://host.docker.internal:8000;
        proxy_buffering off;
    }
}
"""

INDEX_HTML = """\
<!doctype html>
<meta charset="utf-8">
<form onsubmit="ask(q.value); return false">
  <input id="q" name="q" value="华北销售额" size="30"> <button>问一句</button>
</form>
<pre id="out"></pre>
<script>
function ask(question) {
  out.textContent = '';
  const es = new EventSource('/api/stream?q=' + encodeURIComponent(question));
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    out.textContent = msg.type === 'result' ? msg.data.rows[0].sales : msg.step;
    if (msg.type === 'result') es.close();
  };
}
</script>
"""

# ---------------------------------------------------------------- 浏览器录制脚本
# 由本脚本写进临时工作区再 `node` 执行（NODE_PATH 指向 frontend/node_modules）。
# 录制流程（与页面「动手」一模一样）：打开 8081 → 清空输入框 → 逐字敲问题 →
# 点「问一句」→ 等 #out 变 41099.5 → 再多录 1.6 秒。
# 截图由一个后台 async 循环每 ~120ms 做一次，与键盘/点击并发，所以敲字过程本身
# 就在帧里；每帧记录真实时间戳，Python 端再按 120ms 采样成 GIF 帧，避免截图抖动。

BROWSER_CAPTURE_JS = r"""'use strict';
// web_gif.py 临时生成：用系统 Chrome 真操作第 9 页，逐帧录屏素材（PNG + 时间戳）。
// 用法：node capture_page.cjs <frame-dir> <meta.json>
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const FRAME_DIR = process.argv[2];
const META_PATH = process.argv[3];
const URL = 'http://127.0.0.1:8081';
const QUESTION = '华北销售额';
const SAMPLE_MS = 120;

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

(async () => {
  fs.mkdirSync(FRAME_DIR, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-gpu',
      '--hide-scrollbars',
      '--force-device-scale-factor=1',
      '--lang=zh-CN',
      '--disable-dev-shm-usage',
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1100, height: 720 },
    deviceScaleFactor: 1,
    locale: 'zh-CN',
  });
  const page = await context.newPage();
  const meta = { url: URL, question: QUESTION, events: [], frames: [] };

  await page.goto(URL, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(500);          // 等页面稳定、字体就绪

  const t0 = Date.now();
  const now = () => Date.now() - t0;
  const captureStartAt = now();

  // 后台录制循环：每 ~120ms 截一帧，记录真实时间戳。
  let capturing = true;
  const frames = [];
  const captureLoop = (async () => {
    while (capturing) {
      const t = now();
      const file = `raw-${String(frames.length).padStart(4, '0')}.png`;
      try {
        await page.screenshot({ path: path.join(FRAME_DIR, file) });
      } catch (err) {
        meta.captureError = String((err && err.message) || err);
      }
      frames.push({ t, file });
      const spent = now() - t;
      await sleep(Math.max(0, SAMPLE_MS - spent));
    }
  })();

  // 只加一个 MutationObserver 记录 #out 文本变化（不改 DOM），给 Python 端留证据。
  await page.evaluate(() => {
    window.__outHistory = [];
    const out = document.querySelector('#out');
    new MutationObserver(() => {
      const text = (out.textContent || '').trim();
      const hist = window.__outHistory;
      if (!hist.length || hist[hist.length - 1].text !== text) {
        hist.push({ t: Date.now(), text });
      }
    }).observe(out, { childList: true, characterData: true, subtree: true });
  });

  // —— 真操作：与 page-09.md 的页面一致 ——
  meta.defaultQuestion = await page.inputValue('#q');
  meta.buttonText = (await page.locator('button').innerText()).trim();
  await page.waitForTimeout(120);

  await page.fill('#q', '');
  meta.clearedAt = now();
  await page.waitForTimeout(150);

  const typeStart = now();
  await page.keyboard.type(QUESTION, { delay: 60 });
  meta.typeStartAt = typeStart;
  meta.typeEndAt = now();
  meta.typeMs = meta.typeEndAt - typeStart;
  await page.waitForTimeout(150);

  meta.clickAt = now();
  await page.locator('button').click({ timeout: 10000 });

  await page.waitForFunction(() => {
    const out = document.querySelector('#out');
    return out !== null && out.textContent.trim() === '41099.5';
  }, null, { timeout: 30000 });
  meta.resultAt = now();
  meta.outTextAtResult = (await page.locator('#out').innerText()).trim();

  await page.waitForTimeout(1600);         // 结果停留：再多录约 15 帧
  meta.captureEndAt = now();
  meta.outText = (await page.locator('#out').innerText()).trim();
  meta.questionAfterClick = await page.inputValue('#q');
  meta.bodyText = await page.evaluate(() => document.body.innerText);
  meta.outTextHistory = await page.evaluate(() => window.__outHistory || []);
  capturing = false;
  await captureLoop;

  meta.captureStartAt = captureStartAt;
  meta.frames = frames;
  fs.writeFileSync(META_PATH, JSON.stringify(meta, null, 2));
  await browser.close();
})().catch((err) => {
  console.error('BROWSER_CAPTURE_FAILED ' + ((err && err.stack) || err));
  process.exit(1);
});
"""

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


def run_cmd(args: list[str], timeout: float = 120.0, cwd: Path | None = None,
            env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True,
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


def nginx_image() -> str:
    return image_from_env("NGINX_IMAGE", NGINX_IMAGE_FALLBACK)


# ---------------------------------------------------------------- uvicorn 后台进程


class UvicornServer:
    """第 9 页第 1 步：uvicorn --host 0.0.0.0 --port 8000（在临时工作区里跑）。"""

    def __init__(self, work: Path):
        self.work = work
        self.proc: subprocess.Popen | None = None
        self.lines: list[str] = []
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    @property
    def command(self) -> str:
        return f"backend/.venv/bin/python -m uvicorn lab.app:app --host 0.0.0.0 --port {API_PORT}"

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
    missing = [tool for tool in ("docker", "google-chrome", "convert", "identify", "node")
               if shutil.which(tool) is None]
    if missing:
        sys.exit(f"缺少依赖：{', '.join(missing)}（本脚本不装新依赖）")
    if not (PLAYWRIGHT_CORE / "package.json").is_file():
        sys.exit(f"找不到 {PLAYWRIGHT_CORE}（需要 frontend/node_modules/playwright-core）")
    for path in (REPO / "backend" / ".venv" / "bin" / "python", REPO / "fixtures" / "dw.sql"):
        if not path.exists():
            sys.exit(f"缺少仓库产物：{path}")
    for port in (MYSQL_PORT, API_PORT, WEB_PORT):
        if port_open(port):
            sys.exit(
                f"端口 {port} 已被占用；本脚本不杀别人的进程。"
                f"先停掉占用它的服务再重跑。"
            )
    for name in (MYSQL_CONTAINER, NGINX_CONTAINER):
        if name in docker_names():
            say(f"发现上一轮残留的容器 {name}，先删除（脚本自己会清理，正常不应出现）")
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)
    IMAGES.mkdir(parents=True, exist_ok=True)


def prepare_workdir() -> Path:
    work = Path(tempfile.mkdtemp(prefix="manual-web-gif-"))
    os.symlink(REPO / "backend", work / "backend", target_is_directory=True)
    (work / "fixtures").mkdir()
    shutil.copy2(REPO / "fixtures" / "dw.sql", work / "fixtures" / "dw.sql")
    shutil.copy2(REPO / ".env.example", work / ".env.example")
    (work / "lab").mkdir()
    (work / "lab" / "app.py").write_text(load_app_py(), encoding="utf-8")
    (work / "lab" / "default.conf").write_text(DEFAULT_CONF, encoding="utf-8")
    (work / "lab" / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (work / "capture_page.cjs").write_text(BROWSER_CAPTURE_JS, encoding="utf-8")
    (work / "frames").mkdir()
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
        wait_until("MySQL 灌完 fixtures/dw.sql（fact_order = 115）", data_ready,
                   timeout=300, interval=1.0)
    except RuntimeError:
        logs = subprocess.run(
            ["docker", "logs", "--tail", "40", MYSQL_CONTAINER],
            capture_output=True, text=True, timeout=60,
        )
        raise RuntimeError("MySQL 没等到数据：\n" + (logs.stdout + logs.stderr)[-3000:])


def start_nginx(work: Path) -> None:
    run_cmd([
        "docker", "run", "-d", "--name", NGINX_CONTAINER,
        "-p", f"127.0.0.1:{WEB_PORT}:80",
        "--add-host", "host.docker.internal:host-gateway",
        "-v", f"{work}/lab/default.conf:/etc/nginx/conf.d/default.conf:ro",
        "-v", f"{work}/lab/index.html:/usr/share/nginx/html/index.html:ro",
        nginx_image(),
    ], timeout=180)

    def page_ready() -> bool:
        got = http_get(f"http://127.0.0.1:{WEB_PORT}/")
        return bool(got and got[0] == 200 and "问一句" in got[1])

    try:
        wait_until("nginx 8081 首页就绪", page_ready, timeout=60, interval=0.2)
    except RuntimeError:
        logs = subprocess.run(
            ["docker", "logs", "--tail", "40", NGINX_CONTAINER],
            capture_output=True, text=True, timeout=60,
        )
        raise RuntimeError("nginx 没起来：\n" + (logs.stdout + logs.stderr)[-3000:])


# ---------------------------------------------------------------- 浏览器录制


def run_browser_capture(work: Path, timeout: float = 180.0) -> dict:
    meta_path = work / "capture-meta.json"
    env = os.environ.copy()
    env["NODE_PATH"] = str(PLAYWRIGHT_CORE.parent)   # frontend/node_modules
    env["LANGUAGE"] = "zh_CN.UTF-8"
    env["LANG"] = "zh_CN.UTF-8"
    cmd = ["node", str(work / "capture_page.cjs"), str(work / "frames"), str(meta_path)]
    proc = subprocess.run(
        cmd, cwd=work, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "浏览器录制脚本失败：\n" + (proc.stderr or proc.stdout)[-4000:]
        )
    if not meta_path.is_file():
        raise RuntimeError("浏览器录制没有写出 meta.json")
    return json.loads(meta_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 帧处理 / GIF


def frame_bbox(path: Path) -> tuple[int, int, int, int]:
    """返回 (w, h, x, y) 内容边界；-format %@ 基于四角底色求 trim bbox。"""
    out = run_cmd(["convert", str(path), "-format", "%@", "info:"], timeout=60).stdout.strip()
    match = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", out)
    if not match:
        raise RuntimeError(f"找不到 {path.name} 的内容边界（截图是空白页？）：{out!r}")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def union_crop_box(raw_frames: list[Path]) -> tuple[int, int, int]:
    """所有帧取并集，算出统一的上下裁剪范围 (y0, y1, content_top)，避免 GIF 抖动。"""
    tops: list[int] = []
    bottoms: list[int] = []
    for path in raw_frames:
        w, h, _x, y = frame_bbox(path)
        if w <= 0 or h <= 0:
            raise RuntimeError(f"{path.name} 内容区域为空")
        tops.append(y)
        bottoms.append(y + h)
    top = max(0, min(tops) - CROP_PAD)
    bottom = min(VIEWPORT_H, max(bottoms) + CROP_PAD)
    if bottom <= top:
        raise RuntimeError("裁剪范围为空")
    return top, bottom, min(tops)


def crop_frame(raw: Path, target: Path, y0: int, y1: int) -> None:
    """统一裁上下白，宽度保持 1100px（先左右各削 1px 再加 1px 灰边，与现有 PNG 一致）。"""
    run_cmd([
        "convert", str(raw),
        "-crop", f"{WINDOW_W}x{y1 - y0}+0+{y0}", "+repage",
        "-shave", "1x0",
        "-bordercolor", "#c9d1d9", "-border", str(BORDER_PX),
        str(target),
    ], timeout=120)


def build_timeline(meta: dict) -> dict:
    """把录制帧按 120ms 采样成 GIF 帧计划（含开头 / 结尾停留）。

    返回 {"frames": [png 路径...], "duration_s": ..., "final_hold_s": ...}
    """
    raw = sorted(meta["frames"], key=lambda f: f["t"])
    if len(raw) < 10:
        raise RuntimeError(f"只录到 {len(raw)} 帧，太少")
    times = [f["t"] for f in raw]
    capture_start = raw[0]["t"]
    capture_end = raw[-1]["t"]

    # 120ms 采样：每个 tick 取「截至该时刻的最后一帧」。
    tick = capture_start
    picks: list[dict] = []
    i = 0
    while tick <= capture_end:
        while i + 1 < len(times) and times[i + 1] <= tick:
            i += 1
        picks.append(raw[i])
        tick += SAMPLE_MS
    if picks[-1] is not raw[-1]:
        picks.append(raw[-1])          # 保证最后录到的那帧（含 41099.5）一定进 GIF

    # 开头停留：第一帧重复 PRE_ROLL_FRAMES 次（约 0.96s）
    plan = [picks[0]] * PRE_ROLL_FRAMES + picks

    # 结尾停留：末帧重复到「总时长 ≈ 6.5s 且末帧停留 ≥ 2.5s」
    delay_s = GIF_DELAY / 100.0
    target_frames = round(GIF_TARGET_SECONDS / delay_s)
    min_hold = int(round(FINAL_HOLD_MIN_SECONDS / delay_s))
    repeats = max(min_hold, target_frames - len(plan))
    plan += [picks[-1]] * repeats
    return {
        "frames": plan,
        "duration_s": round(len(plan) * delay_s, 2),
        "final_hold_s": round(repeats * delay_s, 2),
        "sampled": len(picks),
        "capture_s": round((capture_end - capture_start) / 1000.0, 2),
    }


def write_gif(cropped: list[Path], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["convert", "-delay", str(GIF_DELAY), "-loop", "0"]
    cmd += [str(p) for p in cropped]
    cmd += ["-layers", "Optimize", str(out)]
    run_cmd(cmd, timeout=600)


def gif_info(path: Path) -> tuple[int, int, int, int]:
    """返回 (宽, 高, 帧数, 字节数)。"""
    out = run_cmd(["identify", "-format", "%w %h %n\n", str(path)], timeout=120).stdout
    first = out.splitlines()[0].split()
    w, h, n = (int(x) for x in first)
    return w, h, n, path.stat().st_size


def extract_gif_frames(gif: Path, out_dir: Path, count: int = 3) -> list[Path]:
    """抽首 / 中 / 末 count 帧（-coalesce 还原成整帧）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(["convert", str(gif), "-coalesce", str(out_dir / "frame-%03d.png")], timeout=300)
    all_frames = sorted(out_dir.glob("frame-*.png"))
    if not all_frames:
        raise RuntimeError("抽帧失败")
    if count == 3:
        idx = [0, len(all_frames) // 3, len(all_frames) - 1]
        return [all_frames[i] for i in idx]
    return all_frames


def frame_ae(a: Path, b: Path) -> int:
    """`compare -metric AE`：两帧不同像素数。"""
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
    """白底浏览器图 OCR：原图 + 3 倍放大各跑一次，多个 PSM 取并集，结果更稳。"""
    if shutil.which("tesseract") is None:
        return ""
    texts: list[str] = []
    variants: list[tuple[Path, str]] = [(png, "6"), (png, "11")]

    def _tess(source: Path, psm: str) -> str:
        proc = subprocess.run(
            ["tesseract", str(source), "stdout", "-l", "eng", "--psm", psm],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
        )
        return proc.stdout or ""

    for source, psm in variants:
        texts.append(_tess(source, psm))
    big = png.with_name(png.stem + ".3x.png")
    try:
        run_cmd(["convert", str(png), "-resize", "300%", str(big)], timeout=120)
        texts.append(_tess(big, "6"))
    except Exception:
        pass
    finally:
        big.unlink(missing_ok=True)
    return "\n".join(texts)


def check_no_secrets(label: str, text: str, extra_forbidden: list[str]) -> None:
    forbidden = ["/home/", "/tmp/", "/root/", "/Users/", getpass.getuser(),
                 socket.gethostname()] + extra_forbidden
    hits = [needle for needle in forbidden if needle and needle in text]
    if hits:
        raise RuntimeError(f"{label} 里出现禁止字符串 {hits}：\n{text[:1000]}")
    say(f"    ✅ 敏感串检查（{label}）：0 命中（用户名 / 主机名 / 绝对路径 / 端口）")


# ---------------------------------------------------------------- 主流程


def cleanup(work: Path | None, server: UvicornServer | None) -> None:
    if server is not None:
        try:
            server.stop()
        except Exception:
            pass
    for name in (NGINX_CONTAINER, MYSQL_CONTAINER):
        try:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)
        except Exception:
            pass
    if work is not None:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    started = time.monotonic()
    say("=" * 78)
    say("web_gif.py —— 真跑第 9 页，用本机 Chrome 录一条浏览器操作 GIF")
    say(f"仓库：{REPO}")
    say(f"输出：{GIF.relative_to(REPO)}")
    say("=" * 78)

    before_ids = docker_id_set()
    preflight()

    work: Path | None = None
    server: UvicornServer | None = None
    try:
        work = prepare_workdir()
        say(f"临时工作区：{work}（页面命令里的相对路径在这里，图里不出现绝对路径）")
        say("    lab/app.py = term_render.py 的 APP_PAGE_08；default.conf / index.html = 第 9 页逐字")

        say("")
        say("── 环境 1/3：MySQL 容器 shots-web-mysql（127.0.0.1:3307）──")
        start_mysql(work)
        say("    ✅ fact_order = 115（fixtures/dw.sql 已灌入）")

        say("")
        say("── 环境 2/3：uvicorn 8000（第 9 页命令：--host 0.0.0.0）──")
        server = UvicornServer(work)
        server.start()
        say(f"    $ {server.command}")
        for line in server.startup_log():
            say(f"      {line}")
        say("    ✅ /health 就绪")

        say("")
        say("── 环境 3/3：nginx 容器 shots-web-nginx（8081）──")
        start_nginx(work)
        say("    ✅ http://127.0.0.1:8081 返回第 9 页的 index.html")

        say("")
        say("── 录制：打开页面 → 清空输入框 → 逐字敲「华北销售额」→ 点「问一句」→ 等 41099.5 ──")
        meta = run_browser_capture(work)
        frames_meta = meta.get("frames", [])
        say(f"    DB 文本：{meta.get('bodyText', '').strip()[:120]!r}")
        say(f"    输入框默认值={meta.get('defaultQuestion')!r}  按钮={meta.get('buttonText')!r}")
        say(f"    敲字用时 {meta.get('typeMs')}ms；点击后 {meta.get('resultAt')}ms 出现结果")
        say(f"    录到 {len(frames_meta)} 帧，覆盖 {frames_meta[-1]['t'] - frames_meta[0]['t']}ms")

        if meta.get("defaultQuestion") != "华北销售额":
            raise RuntimeError(f"输入框默认值不是「华北销售额」：{meta.get('defaultQuestion')!r}")
        if meta.get("buttonText") != "问一句":
            raise RuntimeError(f"按钮文字不是「问一句」：{meta.get('buttonText')!r}")
        if meta.get("questionAfterClick") != "华北销售额":
            raise RuntimeError(f"输入框里的问题不是「华北销售额」：{meta.get('questionAfterClick')!r}")
        if meta.get("outText") != "41099.5":
            raise RuntimeError(f"结果区不是 41099.5：{meta.get('outText')!r}")
        if "41099.5" not in meta.get("bodyText", ""):
            raise RuntimeError("页面文本里没有 41099.5")
        if meta.get("typeMs") is None or not (300 <= float(meta["typeMs"]) <= 3000):
            raise RuntimeError(f"敲字用时异常（应 ~420-1500ms）：{meta.get('typeMs')}")
        if (meta.get("resultAt", 0) - meta.get("clickAt", 0)) < 800:
            raise RuntimeError("点「问一句」后不到 0.8 秒就出结果，不像 SSE 逐条刷新")
        if len(frames_meta) < 20:
            raise RuntimeError(f"只录到 {len(frames_meta)} 帧，太少")
        check_no_secrets("页面 DOM 文本", meta.get("bodyText", ""),
                         ["127.0.0.1", "8081", "8000", "uvicorn", "nginx"])

        # 页面 #out 的变化历史（MutationObserver 记录）：证明真页面逐条刷过步骤名
        steps_seen = [h.get("text", "") for h in meta.get("outTextHistory", [])]
        say(f"    页面 #out 变化历史（{len(steps_seen)} 次）：{steps_seen[:4]} … {steps_seen[-2:]}")
        step_names = {h for h in steps_seen if h in STEPS}
        if len(step_names) < 10:
            raise RuntimeError(f"页面只刷过 {len(step_names)} 个步骤名，不像逐条刷新：{steps_seen}")
        if not steps_seen or steps_seen[-1] != "41099.5":
            raise RuntimeError(f"#out 最后一次变化不是 41099.5：{steps_seen[-3:]}")
        say(f"    ✅ 页面 #out 逐条刷过 {len(step_names)} 个步骤名，最后停在 41099.5")

        stream_hits = [line for line in server.logs() if "/api/stream" in line]
        if not stream_hits:
            raise RuntimeError("uvicorn 访问日志里没有 /api/stream，浏览器点「问一句」没走通")
        say(f"    ✅ uvicorn 访问日志确认浏览器请求：{stream_hits[-1].strip()}")
        if not any("200 OK" in line for line in stream_hits):
            raise RuntimeError("浏览器请求 /api/stream 不是 200")

        # ---- 统一裁剪 + 采样 + 合成 GIF
        say("")
        say("── 合成 GIF：统一裁剪（1100px 宽）→ 120ms 采样 → convert -delay 8 -loop 0 -layers Optimize ──")
        raw_paths = [work / "frames" / f["file"] for f in frames_meta]
        missing = [p.name for p in raw_paths if not p.is_file()]
        if missing:
            raise RuntimeError(f"缺帧：{missing[:5]}")
        y0, y1, _top = union_crop_box(raw_paths[: min(len(raw_paths), 80)])
        say(f"    统一裁剪：y0={y0} y1={y1}（高 {y1 - y0}px，加边框后 1100x{y1 - y0}）")

        # 先按目录顺序裁全部原始帧
        crop_dir = work / "cropped"
        crop_dir.mkdir()
        cropped: list[Path] = []
        for raw in raw_paths:
            target = crop_dir / raw.name
            crop_frame(raw, target, y0, y1)
            cropped.append(target)
        w, h = image_size(cropped[0])
        if w != WINDOW_W:
            raise RuntimeError(f"裁剪后宽 {w}px ≠ {WINDOW_W}px")

        # 采样计划：把「录到的帧」映射成「GIF 帧序列」
        plan = build_timeline(meta)
        index_of = {f["file"]: i for i, f in enumerate(frames_meta)}
        plan_paths = [cropped[index_of[f["file"]]] for f in plan["frames"]]
        gif_dir = work / "gif-frames"
        gif_dir.mkdir()
        final_paths: list[Path] = []
        for i, src in enumerate(plan_paths):
            dst = gif_dir / f"gif-{i:04d}.png"
            shutil.copyfile(src, dst)
            final_paths.append(dst)
        say(f"    GIF 帧：{len(final_paths)} 帧 × {GIF_DELAY}/100s = {plan['duration_s']}s"
            f"（录制 {plan['capture_s']}s，采样 {plan['sampled']} 帧，末帧停留 {plan['final_hold_s']}s）")

        write_gif(final_paths, GIF)
        gw, gh, gn, gbytes = gif_info(GIF)
        say(f"    🖼  {GIF.relative_to(REPO)}  {gw}x{gh}  帧数 {gn}  {gbytes / 1024:.0f} KB")
        if gbytes > GIF_MAX_BYTES:
            raise RuntimeError(f"GIF {gbytes} 字节 > 上限 {GIF_MAX_BYTES}")
        if (gw, gh) != (WINDOW_W, h):
            raise RuntimeError(f"GIF 尺寸 {gw}x{gh} ≠ 帧尺寸 {WINDOW_W}x{h}")

        # ---- 自检：帧真的有变化 + 末帧 OCR
        say("")
        say("── 自检：首/中/末帧对比 + 末帧 OCR ──")
        sample_dir = work / "gif-check"
        first, mid, last = extract_gif_frames(GIF, sample_dir, count=3)
        ae_first_mid = frame_ae(first, mid)
        ae_mid_last = frame_ae(mid, last)
        ae_first_last = frame_ae(first, last)
        say(f"    compare -metric AE：首↔中 {ae_first_mid}  中↔末 {ae_mid_last}  首↔末 {ae_first_last}（0 = 相同）")
        if ae_first_last <= 0:
            raise RuntimeError("GIF 首↔末帧相同，没有动画效果")
        if ae_first_mid <= 0 and ae_mid_last <= 0:
            raise RuntimeError("GIF 只有两种画面，看不出逐条刷新")
        # 全片逐帧 sha256：唯一画面数 ≥ 4 才叫「有过程」
        import hashlib
        hashes = {hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in extract_gif_frames(GIF, work / "gif-hashes", count=0)}
        say(f"    全片唯一帧画面数：{len(hashes)} / {gn}（≥4 说明画面在变化）")
        if len(hashes) < 4:
            raise RuntimeError(f"GIF 唯一画面只有 {len(hashes)} 种，看不出过程")
        ocr_last = ocr_text(last)
        ocr_flat = "".join(ocr_last.split())
        if "41099.5" not in ocr_flat:
            raise RuntimeError(f"末帧 OCR 没读出 41099.5：{ocr_last[:500]!r}")
        say("    ✅ 末帧 OCR 读出 41099.5")
        check_no_secrets("末帧 OCR 文本", ocr_last,
                         ["127.0.0.1", "8081", "8000"])

        # ---- 收尾证据：用户栈容器 ID 集合不变
        after_ids = docker_id_set()
        own = {MYSQL_CONTAINER, NGINX_CONTAINER}
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
        say(f"用时 {time.monotonic() - started:.1f}s；重跑：python3 manual/shots/web_gif.py")
        return 0
    except KeyboardInterrupt:
        say("\n被 Ctrl+C 中断，开始清理……")
        return 130
    except Exception as exc:  # noqa: BLE001
        say(f"\n❌ 出错：{exc}")
        return 1
    finally:
        say("清理：删两个容器 / 停 uvicorn / 删临时工作区 ...")
        cleanup(work, server)


if __name__ == "__main__":
    sys.exit(main())
