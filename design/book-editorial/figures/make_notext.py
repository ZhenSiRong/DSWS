#!/usr/bin/env python3
"""Render a text-free twin of a comic figure.

Purpose: Seedream image-to-image gets a structural reference (people, table,
speech bubbles, panel frames) with no glyphs, so it can restyle the scene
without inventing fake Chinese. The SVG overlay keeps the real text.

Usage:
    python3 make_notext.py content/fig-3-0-three-silent-failures.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from figure_lib import Figure
from gen_figure import draw

HERE = Path(__file__).resolve().parent


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: make_notext.py <content.json>", file=sys.stderr)
        return 2
    content_path = Path(sys.argv[1])
    data = json.loads(content_path.read_text(encoding="utf-8"))
    base = HERE / f"{data['id']}-notext"

    fig = Figure(1600, 900)
    fig.render_text = False
    draw(fig, data)
    fig.save(str(base) + ".svg")

    print(str(base) + ".svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
