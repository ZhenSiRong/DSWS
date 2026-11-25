#!/usr/bin/env python3
"""把已有的 page-NN/index.html 渲染成 out/poster.png + images/page-NN-visual.webp（不重建 index.html）。

用法： python3 manual/designs/render_existing.py 00 [01 ...]
适用：在 editor.html 里改完、下载 HTML 覆盖 index.html 之后使用。
"""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DESIGNS = ROOT/"manual"/"designs"

def render(page: str) -> None:
    proj = DESIGNS/f"page-{page}"
    index = proj/"index.html"
    if not index.is_file(): raise SystemExit(f"缺少 {index}")
    out = proj/"out"; out.mkdir(exist_ok=True)
    png = out/"poster.png"
    subprocess.run(["google-chrome","--headless=new","--disable-gpu","--hide-scrollbars",
                    "--force-device-scale-factor=1","--window-size=1600,1000",
                    f"--screenshot={png}", index.resolve().as_uri()], check=True,
                   capture_output=True, timeout=120)
    webp = ROOT/"manual"/"images"/f"page-{page}-visual.webp"
    subprocess.run(["convert",str(png),"-quality","82",str(webp)], check=True, capture_output=True)
    print(f"page-{page}: {png} → {webp} ({webp.stat().st_size}B)")

for arg in sys.argv[1:] or []:
    render(arg.zfill(2))
if not sys.argv[1:]:
    raise SystemExit("给页号，如 00")
