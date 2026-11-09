#!/usr/bin/env python3
"""给设计图注入“读图带”：这张图回答什么 + 读图 1→2→3。

用法：
    python3 design/scripts/add_reading_band.py            # 全部 32 张
    python3 design/scripts/add_reading_band.py --only 12  # 只做某几张

幂等：已有 data-reading-band 的 SVG 会跳过。
注意：必须在 render_all.py 之后运行，否则重新渲染会覆盖读图带。
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "diagrams" / "reading-paths.json"
BAND = 56
BG = "#F8F5ED"
INK = "#1A1A1A"
MUTED = "#5B5B5B"
ACCENT = "#B24A2E"


def clean_md(text: str) -> str:
    return text.replace("`", "").replace("**", "").strip()


def fit(text: str, width: float, size: float) -> str:
    max_chars = max(12, int((width - 32) / (size * 0.92)))
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def inject(svg_path: Path, entry: dict) -> bool:
    text = svg_path.read_text(encoding="utf-8")
    if "data-reading-band" in text:
        return False

    m = re.search(r"<svg\b[^>]*>", text)
    if not m:
        return False
    opening = m.group(0)
    vb = re.search(r'viewBox="([\d.\s-]+)"', opening)
    if vb:
        parts = [float(x) for x in vb.group(1).split()]
        w, h = parts[2], parts[3]
    else:
        wm = re.search(r'width="([\d.]+)"', opening)
        hm = re.search(r'height="([\d.]+)"', opening)
        if not (wm and hm):
            return False
        w, h = float(wm.group(1)), float(hm.group(1))

    new_h = h + BAND
    new_open = opening
    new_open = re.sub(r'height="[\d.]+"', f'height="{new_h:g}"', new_open)
    new_open = re.sub(r'viewBox="[^"]+"', f'viewBox="0 0 {w:g} {new_h:g}"', new_open)
    new_open = new_open.replace("<svg", '<svg data-reading-band="1"', 1)

    q = fit(clean_md(entry.get("question") or entry.get("one_liner") or ""), w, 15)
    path = " → ".join(f"{i + 1} {p}" for i, p in enumerate(entry.get("path", [])))
    path = fit(path, w, 13)

    band = (
        f'<rect x="0" y="0" width="{w:g}" height="{BAND}" fill="{BG}"/>'
        f'<rect x="0" y="{BAND - 2}" width="{w:g}" height="2" fill="{ACCENT}"/>'
        f'<text x="16" y="23" font-family="Noto Sans CJK SC, sans-serif" font-size="15" '
        f'fill="{INK}">这张图回答：{html.escape(q)}</text>'
        f'<text x="16" y="44" font-family="Noto Sans CJK SC, sans-serif" font-size="13" '
        f'fill="{MUTED}">读图：{html.escape(path)}</text>'
        f'<g transform="translate(0,{BAND})">'
    )

    body = text[: m.start()] + new_open + band + text[m.end():]
    body = body.replace("</svg>", "</g></svg>")
    svg_path.write_text(body, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="逗号分隔的图号，例如 12,16,22")
    args = ap.parse_args()

    entries = json.loads(DATA.read_text(encoding="utf-8"))
    wanted = set(args.only.split(",")) if args.only else None
    changed = 0
    for e in entries:
        if wanted and e["id"] not in wanted:
            continue
        if inject(ROOT / e["svg"], e):
            changed += 1
            print("band:", e["id"], e["svg"])
    print(f"done: {changed} svg(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
