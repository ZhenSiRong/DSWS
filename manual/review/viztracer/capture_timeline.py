#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""附录图 gui-viztracer.png 的截图流水线（headless Chrome + DevTools 协议）。

前置：先跑 `manual/shots/trace_viztracer.py`，本目录已有 `timeline.html`。

跑法（仓库根目录，系统 python3 带 websocket-client 即可）：
    python3 manual/review/viztracer/capture_timeline.py

产物：
    manual/review/viztracer/gui-overview.png   整窗 1600×1000（未裁，证据）
    manual/review/viztracer/gui-selected.png   点选 guard_check 后的详情面板（证据）
    manual/images/gui-viztracer.png            裁到函数条带的成图（宽 1600）

为什么不用 `google-chrome --screenshot`：无头下那套命令等到 load 就拍，
而 timeline.html 的 trace 是 load 之后由 JS 异步导入的，直接拍只会得到
“Importing...”对话框（实测）。这里用同一种 headless Chrome 的 DevTools 协议，
等 10s 导入完成再截图；截图前把悬浮的鼠标模式面板藏掉（它压住条带）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PORT = 9333
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TIMELINE = HERE / "timeline.html"
OVERVIEW = HERE / "gui-overview.png"
SELECTED = HERE / "gui-selected.png"
FIGURE = REPO / "manual" / "images" / "gui-viztracer.png"

#: 成图的裁剪框（device px，来自整窗 1600×1000 截图）与目标宽度。
CROP_BOX = (497, 90, 1515, 440)


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.load(resp)


def _wait_chrome(timeout: float = 20.0) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        try:
            targets = _get(f"http://127.0.0.1:{PORT}/json/list")
            for target in targets:
                if target.get("type") == "page":
                    return target
        except Exception:
            pass
        time.sleep(0.3)
    raise SystemExit("headless Chrome 没起来（检查 google-chrome 是否可执行）")


class CDP:
    def __init__(self, ws_url: str) -> None:
        import websocket  # 系统 python3 的 websocket-client；不在仓库依赖里

        self.ws = websocket.create_connection(ws_url, timeout=120)
        self.mid = 0

    def send(self, method: str, **params):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def eval(self, expr: str):
        result = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def shot(self, path: Path) -> None:
        import base64

        png = self.send("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        path.write_bytes(base64.b64decode(png["data"]))
        print(f"  {path.relative_to(REPO)}  ({path.stat().st_size // 1024} KB)")


def main() -> int:
    if not TIMELINE.exists():
        raise SystemExit(f"缺少 {TIMELINE.relative_to(REPO)}：先跑 manual/shots/trace_viztracer.py")

    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if chrome is None:
        raise SystemExit("找不到 google-chrome / chromium")
    profile = tempfile.mkdtemp(prefix="viztracer-shot-")
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        cdp = CDP(_wait_chrome()["webSocketDebuggerUrl"])
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        # 800×500 CSS + 2x 设备像素 = 整窗 1600×1000；函数名在成图里约 36 px 高。
        cdp.send("Emulation.setDeviceMetricsOverride", width=800, height=500,
                 deviceScaleFactor=2, mobile=False)
        cdp.send("Page.navigate", url=TIMELINE.as_uri())
        time.sleep(10)  # 等 trace 导入 + 时间线渲染
        if not cdp.eval("!!document.getElementById('trace-viewer')"):
            raise SystemExit("timeline.html 没有渲染出 viewer")
        # 悬浮的鼠标模式面板会压住条带；只影响截图，不影响 trace 数据。
        cdp.eval("(function(){const els=document.getElementsByTagName('tr-ui-b-mouse-mode-selector');"
                 "for (let i=0;i<els.length;i++) els[i].style.display='none'; return els.length;})()")
        time.sleep(1)
        cdp.shot(OVERVIEW)
        # 点选 guard_check：底部出现 Title / Start / Wall Duration / Self Time。
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            cdp.send("Input.dispatchMouseEvent", type=kind, x=560, y=100,
                     button="left", clickCount=1)
        time.sleep(2)
        cdp.shot(SELECTED)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)

    from PIL import Image  # 系统 python3 自带 Pillow；只用来裁图

    image = Image.open(OVERVIEW)
    cropped = image.crop(CROP_BOX)
    height = round(cropped.height * 1600 / cropped.width)
    cropped.resize((1600, height), Image.LANCZOS).save(FIGURE, optimize=True)
    print(f"  {FIGURE.relative_to(REPO)}  ({FIGURE.stat().st_size // 1024} KB, 1600×{height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
