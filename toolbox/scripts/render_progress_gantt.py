#!/usr/bin/env python3
"""render_progress_gantt.py —— 进度看板甘特图渲染（离线、可重复）

从 materials/humen-desicions/14-progress-gantt.md 的 ```mermaid 代码块渲染 PNG：
mermaid@11 本地副本（materials/design/assets/mermaid.min.js）+ google-chrome 无头 + ImageMagick trim。

用法：
    python3 toolbox/scripts/render_progress_gantt.py            # 渲染并覆盖 materials/humen-desicions/progress-gantt.png
    python3 toolbox/scripts/render_progress_gantt.py --width 1800
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "humen-desicions" / "14-progress-gantt.md"
OUT = REPO / "humen-desicions" / "progress-gantt.png"
MERMAID_LOCAL = REPO / "design" / "assets" / "mermaid.min.js"
FONT_STACK = "Noto Sans CJK SC,Source Han Sans SC,Microsoft YaHei,sans-serif"
CFG = {
    "startOnLoad": False,
    "theme": "base",
    "fontFamily": FONT_STACK,
    "themeVariables": {"fontSize": "15px", "fontFamily": FONT_STACK},
    "gantt": {
        "useWidth": 1600,
        "useMaxWidth": False,
        "topPadding": 55,
        "leftPadding": 130,
        "fontSize": 15,
        "barHeight": 26,
        "barGap": 6,
        "sectionBkgColor": "#fafafa",
        "altSectionBkgColor": "#ffffff",
        "gridLineStartPadding": 20,
    },
}


def extract_mmd() -> str:
    text = DOC.read_text(encoding="utf-8")
    m = re.search(r"```mermaid\n(.*?)```", text, re.S)
    if not m:
        raise SystemExit(f"{DOC.name} 里没找到 ```mermaid 代码块")
    return m.group(1).strip()


def build_html(mmd: str, mermaid_js: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>gantt</title>
<style>
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
body {{ display: inline-block; }}
.fig {{ padding: 16px 20px; font-family: {FONT_STACK}; }}
#holder svg {{ display: block; }}
</style></head><body>
<div class="fig"><div id="holder"><pre class="mermaid">
{mmd}
</pre></div></div>
<script>{mermaid_js}</script>
<script>
  mermaid.initialize({json.dumps(CFG, ensure_ascii=False)});
  mermaid.run({{ querySelector: '.mermaid' }}).then(() => {{
    const r = document.querySelector('.fig').getBoundingClientRect();
    document.title = 'DIM ' + Math.ceil(r.width) + ' ' + Math.ceil(r.height);
  }}).catch((e) => {{ document.title = 'ERR ' + (e && e.message ? e.message : e); }});
</script>
</body></html>
"""


def chrome(args: list[str]) -> subprocess.CompletedProcess:
    cmd = ["google-chrome", "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars"]
    return subprocess.run(cmd + args, capture_output=True, text=True, timeout=240)


def measure(html: Path, work: Path) -> tuple[int, int]:
    proc = chrome([
        "--window-size=4200,3000",
        "--virtual-time-budget=20000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", html.as_uri(),
    ])
    m = re.search(r"<title>DIM (\d+) (\d+)</title>", proc.stdout)
    if not m:
        err = re.search(r"<title>ERR ([^<]*)</title>", proc.stdout)
        raise SystemExit(f"mermaid 渲染失败：{err.group(1) if err else (proc.stderr or proc.stdout)[-2000:]}")
    return int(m.group(1)), int(m.group(2))


def screenshot(html: Path, png: Path, size: tuple[int, int], work: Path) -> None:
    png.unlink(missing_ok=True)
    proc = chrome([
        f"--window-size={size[0] + 4},{size[1] + 4}",
        "--force-device-scale-factor=2",
        "--virtual-time-budget=20000",
        f"--user-data-dir={work / 'chrome-shot'}",
        f"--screenshot={png}", html.as_uri(),
    ])
    if not png.exists() or png.stat().st_size == 0:
        raise SystemExit(f"chrome 截图失败：{(proc.stderr or proc.stdout)[-2000:]}")


def convert(args: list[str]) -> None:
    proc = subprocess.run(["convert"] + args, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise SystemExit("ImageMagick 失败：" + (proc.stderr or proc.stdout)[-2000:])


def render_to_png(mmd: str, out: Path, width: int = 1800, mermaid_js: str | None = None) -> tuple[int, int]:
    """可复用渲染核心：mermaid 源 → PNG（不写 meta，由调用方决定哈希源）。

    返回最终 PNG 的 (宽, 高)。task.py render 复用此函数，meta 改用 ledger 的 sha。
    """
    if mermaid_js is None:
        if not MERMAID_LOCAL.exists():
            raise SystemExit(f"缺本地 mermaid：{MERMAID_LOCAL}")
        mermaid_js = MERMAID_LOCAL.read_text(encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="gantt-"))
    try:
        html = work / "gantt.html"
        html.write_text(build_html(mmd, mermaid_js), encoding="utf-8")
        w, h = measure(html, work)
        print(f"自然尺寸 {w}x{h}")
        raw = work / "raw.png"
        screenshot(html, raw, (w, h), work)
        trimmed = work / "trim.png"
        convert([str(raw), "-trim", "+repage", str(trimmed)])
        margin = 16
        convert([str(trimmed), "-resize", f"{width - 2 * margin}x",
                 "-bordercolor", "#ffffff", "-border", str(margin), str(out)])
        proc = subprocess.run(["identify", "-format", "%w %h", str(out)],
                              capture_output=True, text=True, check=True)
        fw, fh = (int(x) for x in proc.stdout.split())
        print(f"输出 {out}：{fw}x{fh}，{out.stat().st_size} 字节")
        return fw, fh
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1800, help="最终 PNG 宽度（默认 1800）")
    args = ap.parse_args()

    mmd = extract_mmd()
    render_to_png(mmd, OUT, args.width)
    # 源哈希侧车：check_progress 比对现源 sha，不依赖 mtime（commit/clone 不保留）
    sha = hashlib.sha256(mmd.encode("utf-8")).hexdigest()
    OUT.with_suffix(".png.meta").write_text(sha + "\n", encoding="utf-8")
    print(f"源哈希 {sha[:12]}… → {OUT.with_suffix('.png.meta').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())