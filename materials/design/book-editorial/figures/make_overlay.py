#!/usr/bin/env python3
"""Composite an AI scene raster with the exact SVG text layer.

The raster carries only art; every Chinese string stays real text in the SVG,
so the spelling manifest, font sizes and reading order remain checkable.

Usage:
    python3 make_overlay.py \
        --layout fig-3-0-three-silent-failures.layout.json \
        --image  ai-pilot/fig-3-0-ai-draft.png \
        --out    fig-3-0-hybrid
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from figure_lib import FONT, esc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--halo", type=float, default=0.0)
    args = ap.parse_args()

    layout_path = Path(args.layout).resolve()
    image_path = Path(args.image).resolve()
    out_path = Path(args.out).resolve()
    if out_path.suffix != ".svg":
        out_path = out_path.with_suffix(".svg")

    data = json.loads(layout_path.read_text(encoding="utf-8"))
    width, height = data["width"], data["height"]
    texts = [e for e in data["elements"] if e["kind"] == "text"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<image x="0" y="0" width="{width}" height="{height}" '
        f'href="{image_path.as_uri()}" xlink:href="{image_path.as_uri()}"/>',
    ]
    for t in texts:
        # No stroke halo here: WeasyPrint (the PDF engine) ignores
        # paint-order="stroke" and paints the outline over the glyph, which
        # washes the label out. Plain fill renders identically everywhere.
        parts.append(
            f'<text x="{t["x"]}" y="{t["y"]}" font-family="{FONT}" '
            f'font-size="{t["font_size"]}" font-weight="{t.get("weight", "normal")}" '
            f'fill="{t["fill"]}" text-anchor="{t["anchor"]}">{esc(t["text"])}</text>'
        )
    parts.append("</svg>")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
