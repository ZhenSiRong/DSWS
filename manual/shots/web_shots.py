#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""web_shots.py —— 真跑第 9 页（MySQL 3307 + uvicorn 8000 + nginx 8081），
用本机 Chrome 截两张**真浏览器**图。

在仓库根目录一条命令重跑：

    python3 manual/shots/web_shots.py

输出：

    manual/images/page-09-browser-ok.png   http://127.0.0.1:8081 点过「问一句」、结果区 41099.5
    manual/images/page-09-no-nginx.png     删掉 nginx 容器后再打开 8081，Chrome 的 ERR_CONNECTION_REFUSED

它做四件事：

1. 在 /tmp 建一个**临时工作区**：软链 `backend/`（复用仓库现成的 venv），拷入
   `fixtures/dw.sql` 和 `.env.example`，写 `lab/app.py`（第 3–8 页产物的最终形态；
   直接复用 `term_render.py` 里组装好的 `APP_PAGE_08`，避免两处 app.py 漂移），
   再逐字写入第 9 页的 `lab/default.conf` 和 `lab/index.html`。
   页面命令里全是相对路径，在临时工作区里逐字执行，所以图里不会出现
   `/home/...` 这类绝对路径。
2. 起三层环境，端口/容器名与第 9 页一致：`shots-web-mysql`（`-p 127.0.0.1:3307:3306`，
   挂 `fixtures/dw.sql`）→ uvicorn `--host 0.0.0.0 --port 8000` →
   `shots-web-nginx`（`-p 127.0.0.1:8081:80`，`--add-host host.docker.internal:host-gateway`，
   挂 default.conf 和 index.html；镜像名与第 9 页一样从 `.env.example` 的 `NGINX_IMAGE` 读）。
3. 浏览器自动化：本机没有 Playwright 自带浏览器，用 `frontend/node_modules/playwright-core`
   驱动 `/usr/bin/google-chrome`（`executablePath`）。视口 1100×720、
   `deviceScaleFactor=1`（1:1 像素）：
   成功图 = 打开 8081 → 核对输入框默认值「华北销售额」→ 点「问一句」→
   等 `#out` 变成 `41099.5` → 截图；
   失败图 = `docker rm -f shots-web-nginx` → 重新打开 8081（连接被拒）→
   截 Chrome 错误页（页面文本里必须有 `ERR_CONNECTION_REFUSED`）。
4. 每张图只裁掉页面**上下**空白（宽度保持 1100px，加 1px 灰边方便在文档里看出边界），
   并核对页面文本里没有用户名 / 主机名 / 绝对路径；装了 tesseract 时再 OCR 一遍，
   确认像素里真有 `41099.5` / `ERR_CONNECTION_REFUSED`。
   跑完自动 `docker rm -f` 两个容器、停 uvicorn、删临时工作区，不留端口占用。

端口只用 3307 / 8000 / 8081；8100 / 13306 / 18081 是别的栈在用，本脚本不碰。

依赖（本机已装，不新装）：docker、google-chrome、ImageMagick、node、
仓库的 `backend/.venv` 与 `frontend/node_modules/playwright-core`。
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

WINDOW_W = 1100          # SPEC：窗宽固定（浏览器视口宽）
VIEWPORT_H = 720         # 截图时的视口高；成品只保留有内容的上下范围
CROP_PAD = 32            # 裁掉空白后上下各留的像素
BORDER_PX = 1            # 1px 灰边：白底截图在文档里能看出边界（不缩放内容）

MYSQL_PORT = 3307        # 与第 1 页 -p 127.0.0.1:3307:3306 一致
API_PORT = 8000          # 与第 3 页/第 9 页 uvicorn --port 8000 一致
WEB_PORT = 8081          # 与第 9 页 -p 127.0.0.1:8081:80 一致

MYSQL_CONTAINER = "shots-web-mysql"
NGINX_CONTAINER = "shots-web-nginx"
MYSQL_IMAGE_FALLBACK = "docker.m.daocloud.io/library/mysql:8.0"
NGINX_IMAGE_FALLBACK = "docker.m.daocloud.io/library/nginx:1.27-alpine"

BROWSER_JSON_OK = "browser-ok.json"
BROWSER_JSON_ERR = "browser-err.json"

# ---------------------------------------------------------------- 第 3–8 页的 lab/app.py
# 不在本文件里再抄一遍：直接复用 term_render.py 中「按页序组装」出的最终形态
# （第 8 页结束时的完整文件），保证第 8 页和第 9 页跑的是同一份服务端代码。


def load_app_py() -> str:
    path = HERE / "term_render.py"
    spec = importlib.util.spec_from_file_location("manual_term_render", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    # 导入只是借它的 APP_PAGE_08，不在 manual/shots/ 下留 __pycache__。
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

# ---------------------------------------------------------------- 浏览器脚本
# 由本脚本写进临时工作区再 `node` 执行（playwright-core 在 frontend/node_modules，
# 通过 NODE_PATH 找到；本机没有 Playwright 自带浏览器，用系统 Chrome）。
# 两个阶段都用同一个 1100×720、deviceScaleFactor=1 的视口：
#   ok  —— 打开 8081，核对默认问题，点「问一句」，等 #out == 41099.5，截图；
#   err —— 打开 8081（此时 nginx 已删），捕获 net::ERR_CONNECTION_REFUSED，
#          等浏览器把错误页画出来后截图。
# Chrome 的界面语言用环境变量 LANGUAGE/LANG=zh_CN.UTF-8 切成中文，
# 错误页会写「无法访问此网站」「127.0.0.1 拒绝了我们的连接请求」，并带 ERR_CONNECTION_REFUSED。

BROWSER_JS = r"""'use strict';
// web_shots.py 临时生成：用系统 Chrome 打开第 9 页的 nginx 入口，截两张真浏览器图。
// 用法：node browser_shot.cjs <phase: ok|err> <out.json> <out.png>
const fs = require('fs');
const { chromium } = require('playwright-core');

const PHASE = process.argv[2];
const OUT_JSON = process.argv[3];
const OUT_PNG = process.argv[4];
const URL = 'http://127.0.0.1:8081';

(async () => {
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
  const result = { phase: PHASE, url: URL };

  if (PHASE === 'ok') {
    await page.goto(URL, { waitUntil: 'load', timeout: 30000 });
    result.defaultQuestion = await page.inputValue('#q');
    result.buttonText = (await page.locator('button').innerText()).trim();
    await page.locator('button').click({ timeout: 10000 });
    await page.waitForFunction(() => {
      const out = document.querySelector('#out');
      return out !== null && out.textContent.trim() === '41099.5';
    }, null, { timeout: 30000 });
    await page.waitForTimeout(400);
    result.outText = (await page.locator('#out').innerText()).trim();
    result.questionAfterClick = await page.inputValue('#q');
    result.bodyText = await page.evaluate(() => document.body.innerText);
    await page.screenshot({ path: OUT_PNG });
  } else {
    let navError = '';
    try {
      await page.goto(URL, { waitUntil: 'load', timeout: 30000 });
    } catch (err) {
      navError = String((err && err.message) || err).split('\n')[0];
    }
    await page.waitForTimeout(1500); // 等浏览器把错误页画完
    result.navError = navError;
    result.pageUrl = page.url();
    result.bodyText = await page.evaluate(() => (document.body ? document.body.innerText : ''));
    await page.screenshot({ path: OUT_PNG });
  }

  fs.writeFileSync(OUT_JSON, JSON.stringify(result, null, 2));
  await browser.close();
})().catch((err) => {
  console.error('BROWSER_SCRIPT_FAILED ' + ((err && err.stack) || err));
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


def http_get(url: str, timeout: float = 2.0) -> tuple[int, str] | None:
    try:
        with _OPENER.open(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception:
        return None


def http_post_json(url: str, payload: dict, timeout: float = 10.0) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with _OPENER.open(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


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
        """启动日志截到 "Uvicorn running on" 那一行为止。"""
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
    work = Path(tempfile.mkdtemp(prefix="manual-web-shots-"))
    os.symlink(REPO / "backend", work / "backend", target_is_directory=True)
    (work / "fixtures").mkdir()
    shutil.copy2(REPO / "fixtures" / "dw.sql", work / "fixtures" / "dw.sql")
    shutil.copy2(REPO / ".env.example", work / ".env.example")
    (work / "lab").mkdir()
    (work / "lab" / "app.py").write_text(load_app_py(), encoding="utf-8")
    (work / "lab" / "default.conf").write_text(DEFAULT_CONF, encoding="utf-8")
    (work / "lab" / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (work / "browser_shot.cjs").write_text(BROWSER_JS, encoding="utf-8")
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


def remove_nginx() -> None:
    subprocess.run(["docker", "rm", "-f", NGINX_CONTAINER],
                   capture_output=True, timeout=120)
    wait_port_closed(WEB_PORT)


# ---------------------------------------------------------------- 浏览器截图


def run_browser(work: Path, phase: str, json_name: str, png: Path,
                timeout: float = 180.0) -> dict:
    json_path = work / json_name
    env = os.environ.copy()
    env["NODE_PATH"] = str(PLAYWRIGHT_CORE.parent)   # frontend/node_modules
    env["LANGUAGE"] = "zh_CN.UTF-8"                  # Chrome 界面/错误页用中文
    env["LANG"] = "zh_CN.UTF-8"
    cmd = ["node", str(work / "browser_shot.cjs"), phase, str(json_path), str(png)]
    proc = subprocess.run(
        cmd, cwd=work, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"浏览器脚本失败（{phase}）：\n" + (proc.stderr or proc.stdout)[-4000:]
        )
    if not png.is_file() or png.stat().st_size == 0:
        raise RuntimeError(f"浏览器没有写出截图：{png}")
    return json.loads(json_path.read_text(encoding="utf-8"))


def check_text_no_secrets(label: str, text: str) -> None:
    """硬约束：页面文本里不得出现用户名 / 主机名 / 绝对路径。"""
    forbidden = ["/home/", "/tmp/", "/root/", getpass.getuser(), socket.gethostname()]
    hits = [needle for needle in forbidden if needle and needle in text]
    if hits:
        raise RuntimeError(f"{label} 的页面文本里出现禁止字符串 {hits}：\n{text}")
    say(f"    ✅ 内容检查（{label}）：无用户名 / 主机名 / 绝对路径")


def crop_vertical(raw: Path, target: Path) -> tuple[int, int]:
    """只裁掉页面上下空白，宽度保持 1100px；再加 1px 灰边（内容不缩放，仍 1:1）。"""
    raw_w, raw_h = image_size(raw)
    if raw_w != WINDOW_W:
        raise RuntimeError(f"{raw.name} 宽度是 {raw_w}px，不是约定的 {WINDOW_W}px")
    bbox = run_cmd(["convert", str(raw), "-format", "%@", "info:"], timeout=60).stdout.strip()
    match = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", bbox)
    if not match:
        raise RuntimeError(f"找不到 {raw.name} 的内容边界（截图是空白页？）：{bbox!r}")
    content_w, content_h, _x, top = (int(g) for g in match.groups())
    if content_w <= 0 or content_h <= 0:
        raise RuntimeError(f"{raw.name} 内容区域为空")
    y0 = max(0, top - CROP_PAD)
    y1 = min(raw_h, top + content_h + CROP_PAD)

    tmp = target.with_name(target.stem + ".crop.png")
    # 先裁出 1100×H+2 再左右各削 1px，最后加 1px 边框 → 成品正好 1100px 宽。
    run_cmd([
        "convert", str(raw),
        "-crop", f"{WINDOW_W}x{y1 - y0}+0+{y0}", "+repage",
        "-shave", "1x0",
        "-bordercolor", "#c9d1d9", "-border", str(BORDER_PX),
        str(tmp),
    ], timeout=120)
    tmp.replace(target)
    return image_size(target)


def ocr_verify(png: Path, needles: list[str]) -> bool:
    """有 tesseract 就 OCR 一遍成品图，确认像素里确实有这几段字（没有就跳过）。"""
    if shutil.which("tesseract") is None:
        say("    ⚠️  未装 tesseract，跳过 OCR 复核（页面 DOM 文本已核对过）")
        return True
    proc = subprocess.run(
        ["tesseract", str(png), "stdout", "-l", "eng"],
        capture_output=True, text=True, timeout=120,
    )
    text = "".join(proc.stdout.split())   # OCR 会插空格，去掉再比
    missing = [needle for needle in needles if needle not in text]
    if missing:
        say(f"    ⚠️  OCR 没底确认 {missing}（OCR 有噪声；页面 DOM 文本已核对过，请人工看图）")
        return False
    say(f"    ✅ OCR 复核：图中确有 {' / '.join(needles)}")
    return True


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
    say("web_shots.py —— 真跑第 9 页，用本机 Chrome 截两张浏览器图")
    say(f"仓库：{REPO}")
    say(f"输出：{IMAGES.relative_to(REPO)}/page-09-browser-ok.png、page-09-no-nginx.png")
    say("=" * 78)

    preflight()

    work: Path | None = None
    server: UvicornServer | None = None
    try:
        work = prepare_workdir()
        say(f"临时工作区：{work}（命令里的相对路径都在这里，图里不出现绝对路径）")
        say("    lab/app.py = term_render.py 的 APP_PAGE_08（第 3–8 页产物的最终形态）")
        say("    lab/default.conf、lab/index.html = manual/page-09.md 里逐字的那两份")

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

        # ---- 图 1：浏览器成功
        say("")
        say("── 截图 1/2：浏览器打开 8081，点「问一句」，等 41099.5 ──")
        raw_ok = work / "browser-ok.raw.png"
        local_ok = work / "browser-ok.local.png"
        result_ok = run_browser(work, "ok", BROWSER_JSON_OK, raw_ok)
        say(f"    输入框默认值：{result_ok.get('defaultQuestion')!r}"
            f"  按钮：{result_ok.get('buttonText')!r}")
        say(f"    点击后结果区 #out：{result_ok.get('outText')!r}")
        if result_ok.get("defaultQuestion") != "华北销售额":
            raise RuntimeError("输入框默认值不是「华北销售额」")
        if result_ok.get("buttonText") != "问一句":
            raise RuntimeError("按钮文字不是「问一句」")
        if result_ok.get("outText") != "41099.5":
            raise RuntimeError(f"结果区不是 41099.5：{result_ok.get('outText')!r}")
        if result_ok.get("questionAfterClick") != "华北销售额":
            raise RuntimeError("点击后输入框里的问题变了")
        body_ok = result_ok.get("bodyText", "")
        if "41099.5" not in body_ok:
            raise RuntimeError("页面文本里没有 41099.5")
        check_text_no_secrets("成功页", body_ok)
        stream_hits = [line for line in server.logs() if "/api/stream" in line]
        if not stream_hits:
            raise RuntimeError("uvicorn 访问日志里没有 /api/stream，浏览器点「问一句」没走通")
        say(f"    ✅ uvicorn 访问日志确认浏览器请求：{stream_hits[-1].strip()}")
        target_ok = IMAGES / "page-09-browser-ok.png"
        size_ok = crop_vertical(raw_ok, target_ok)
        say(f"    🖼  {target_ok.relative_to(REPO)}  {size_ok[0]}x{size_ok[1]}")
        ocr_verify(target_ok, ["41099.5"])

        # ---- 图 2：删掉 nginx 后
        say("")
        say("── 截图 2/2：docker rm -f shots-web-nginx，再打开 8081 ──")
        remove_nginx()
        say("    ✅ nginx 容器已删除，8081 已无监听")
        raw_err = work / "browser-err.raw.png"
        result_err = run_browser(work, "err", BROWSER_JSON_ERR, raw_err)
        err_nav = result_err.get("navError", "")
        err_body = result_err.get("bodyText", "")
        say(f"    浏览器导航错误：{err_nav}")
        say(f"    错误页文本（前 5 行）：")
        for line in [ln for ln in err_body.splitlines() if ln.strip()][:5]:
            say(f"      {line}")
        if "ERR_CONNECTION_REFUSED" not in err_nav:
            raise RuntimeError(f"导航错误不是 ERR_CONNECTION_REFUSED：{err_nav!r}")
        if "ERR_CONNECTION_REFUSED" not in err_body:
            raise RuntimeError(f"错误页文本里没有 ERR_CONNECTION_REFUSED：{err_body!r}")
        check_text_no_secrets("错误页", err_body)
        target_err = IMAGES / "page-09-no-nginx.png"
        size_err = crop_vertical(raw_err, target_err)
        say(f"    🖼  {target_err.relative_to(REPO)}  {size_err[0]}x{size_err[1]}")
        ocr_verify(target_err, ["ERR_CONNECTION_REFUSED"])

        # ---- 主干还在：nginx 删了，uvicorn 仍答得出 41099.5
        say("")
        say("── 主干复核：nginx 已删，直连 8000 仍拿得到 41099.5 ──")
        status, body = http_post_json(
            f"http://127.0.0.1:{API_PORT}/api/query", {"question": "华北销售额"})
        data = json.loads(body)
        sales = data["rows"][0]["sales"]
        say(f"    HTTP {status}，rows[0].sales = {sales}")
        if status != 200 or sales != 41099.5:
            raise RuntimeError(f"直连 8000 没拿到 41099.5：HTTP {status} {body[:300]}")

        say("")
        say("=" * 78)
        say("完成，两张图（identify）：")
        for path in (target_ok, target_err):
            ident = run_cmd(["identify", "-format", "%f  %wx%h", str(path)], timeout=60).stdout
            say(f"  {ident.strip()}")
        say("")
        say(f"用时 {time.monotonic() - started:.1f}s；重跑：python3 manual/shots/web_shots.py")
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
