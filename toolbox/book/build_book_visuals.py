#!/usr/bin/env python3
"""把页面首图（page-visuals）转成「章」版本，供手册 HTML/PDF 使用。

只替换生成源 HTML 里的「第 N 页 → 第 N 章」，再离屏渲染 1600×1000 WebP；
不改 page-visuals 正典、不改网页阅读版。输出到 toolbox/book/.visuals/（gitignore）。
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "toolbox" / "page-visuals"
OUT = Path(__file__).resolve().parent / ".visuals"

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for page in range(24):
        src = SRC / f"page-{page:02d}" / "index.html"
        if not src.is_file():
            print(f"skip page-{page:02d}: no source"); continue
        html = src.read_text(encoding="utf-8")
        html = re.sub(r"第\s*(\d+)\s*页", r"第 \1 章", html)
        tmp = src.with_name(".book.html")
        tmp.write_text(html, encoding="utf-8")
        png = OUT / f"page-{page:02d}-visual.png"
        subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--window-size=1600,1000",
                        f"--screenshot={png}", tmp.resolve().as_uri()],
                       check=True, capture_output=True, timeout=120)
        tmp.unlink(missing_ok=True)
        webp = OUT / f"page-{page:02d}-visual.webp"
        subprocess.run(["convert", str(png), "-quality", "82", str(webp)], check=True, capture_output=True)
        n += 1
    print(f"book visuals: {n} page(s) → {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
