#!/usr/bin/env python3
"""Deterministic gates for a DSWS editorial figure.

Usage:
    python3 check_figure.py content/fig-3-0-three-silent-failures.json

Reads the content JSON plus the sidecar .layout.json / .text-manifest.json,
checks the PNG, and writes <figure>.checks.json.
"""
from __future__ import annotations

import collections
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PALETTE = {
    "#FFFDF8",  # paper
    "#111111",  # ink
    "#5B5B5B",  # ink2
    "#D9D3C7",  # line
    "#1F4E9C",  # cobalt
    "#B24A2E",  # rust
    "#2F5D46",  # forest
    "#C58B1B",  # mustard
    "#E7EDF8",  # cobalt tint
    "#F7E8E1",  # rust tint
    "#E6EFE9",  # forest tint
    "#F8EEDA",  # mustard tint
    "#F8F5ED",  # wash
    "#FFFFFF",  # white
}
FONT_SIZES = {42, 30, 26, 24, 22, 18}
EXPECTED = (1600, 900)


def png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", head[16:24])


def box_area(b) -> float:
    return max(0.0, b[2]) * max(0.0, b[3])


def overlap_area(a, b) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[0] + a[2], b[0] + b[2])
    y2 = min(a[1] + a[3], b[1] + b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def contains(a, b) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and a[0] + a[2] >= b[0] + b[2] and a[1] + a[3] >= b[1] + b[3]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_figure.py <content.json>", file=sys.stderr)
        return 2
    content_path = Path(sys.argv[1])
    data = json.loads(content_path.read_text(encoding="utf-8"))
    base = HERE / data["id"]
    png, svg = Path(str(base) + ".png"), Path(str(base) + ".svg")
    layout_path = Path(str(base) + ".layout.json")
    manifest_path = Path(str(base) + ".text-manifest.json")

    checks = []

    def add(gate: str, ok: bool, evidence: str) -> None:
        checks.append({"gate": gate, "pass": bool(ok), "evidence": evidence})

    # 1. Size
    w, h = png_size(png)
    add("size", (w, h) == EXPECTED, f"PNG {w}x{h}, expected {EXPECTED[0]}x{EXPECTED[1]}")
    svg_text = svg.read_text(encoding="utf-8")
    m = re.search(r'<svg[^>]*width="(\d+)"[^>]*height="(\d+)"', svg_text)
    add(
        "svg_size",
        bool(m) and (int(m.group(1)), int(m.group(2))) == EXPECTED,
        m.group(0) if m else "no width/height",
    )

    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    elements = layout["elements"]
    texts = [e for e in elements if e["kind"] == "text"]
    rects = [e for e in elements if e["kind"] == "rect"]

    # 2. Spelling / manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_counter = collections.Counter(s["text"] for s in manifest["strings"])
    layout_counter = collections.Counter(e["text"] for e in texts)
    expected_counter = collections.Counter(data.get("figure_text", []))
    add(
        "spelling_manifest",
        layout_counter == manifest_counter,
        f"{len(texts)} text elements, {len(manifest_counter)} unique strings in manifest",
    )
    missing = expected_counter - layout_counter
    extra = layout_counter - expected_counter
    add(
        "spelling_expected",
        not missing and not extra,
        f"missing={dict(missing)} extra={dict(extra)}",
    )

    # 2b. Hybrid rendering: the raster carries art only; the SVG must still
    # carry every string as real text, so spelling stays machine-checkable.
    hybrid = data.get("render") == "hybrid"
    if hybrid:
        import html as _html

        svg_strings = [
            _html.unescape(s)
            for s in re.findall(r"<text\b[^>]*>(.*?)</text>", svg_text, re.S)
        ]
        add(
            "hybrid_text_layer",
            collections.Counter(svg_strings) == layout_counter,
            f"{len(svg_strings)} <text> nodes in overlay, {sum(layout_counter.values())} layout strings",
        )
        add(
            "hybrid_raster_ref",
            "<image" in svg_text and (HERE / str(data.get("render_source", ""))).is_file(),
            f"render_source={data.get('render_source')}",
        )

    # 3. Typography
    sizes = sorted({e["font_size"] for e in texts})
    add("typography_sizes", set(sizes) <= FONT_SIZES, f"sizes={sizes}, allowed={sorted(FONT_SIZES)}")
    add("typography_title", 42 in sizes, "title 42px present")
    add("typography_section", 30 in sizes, "section 30px present")
    add("typography_label", 24 in sizes, "label 24px present")
    add("typography_note", 22 in sizes, "note 22px present")
    add("typography_small", 18 in sizes, "small 18px present")

    # 4. Color: vector figures must use the editorial palette everywhere.
    # Hybrid figures split this into a real text-colour check plus an explicit
    # deferral for the AI raster, which cannot be palette-gated deterministically.
    used = set()
    for e in elements:
        for key in ("fill", "stroke"):
            if key in e and e[key] and e[key] != "none":
                used.add(e[key].upper())
    if hybrid:
        text_used = {e["fill"].upper() for e in texts if e.get("fill")}
        bad = sorted(text_used - PALETTE)
        add("color_palette_text", not bad, f"text fills={sorted(text_used)} bad={bad}")
        add(
            "color_raster",
            True,
            "deferred: AI-rendered raster palette is checked in vision review, not by hex gate",
        )
    else:
        bad = sorted(used - PALETTE)
        add("color_palette", not bad, f"used={sorted(used)} bad={bad}")
        add("color_cobalt", "#1F4E9C" in used, "cobalt #1F4E9C present")
        add("color_rust", "#B24A2E" in used, "rust #B24A2E present")
        add("color_forest", "#2F5D46" in used, "forest #2F5D46 present")
        add("color_tint", "#E7EDF8" in used, "cobalt tint #E7EDF8 present")

    # 5. Layout: text-vs-text overlap
    collisions = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            ov = overlap_area(a["box"], b["box"])
            if ov > 0.20 * min(box_area(a["box"]), box_area(b["box"])):
                collisions.append((a["id"], b["id"], round(ov, 1)))
    add("layout_text_overlap", not collisions, f"collisions={collisions[:10]}")

    # 6. Layout: rect-vs-rect overlap (containment allowed).
    # Comic scenes intentionally layer bodies, tables, receipts and windows;
    # the text-overlap gate is the meaningful one there.
    if data.get("kind") == "comic":
        add("layout_rect_overlap", True, "comic: intentional scene overlaps; text overlap gate covers labels")
    else:
        rect_collisions = []
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                if overlap_area(a["box"], b["box"]) <= 0:
                    continue
                if contains(a["box"], b["box"]) or contains(b["box"], a["box"]):
                    continue
                rect_collisions.append((a["id"], b["id"]))
        add("layout_rect_overlap", not rect_collisions, f"collisions={rect_collisions[:10]}")

    # 7. Bounds
    out_of_bounds = []
    for e in texts:
        x, y, bw, bh = e["box"]
        if x < 0 or y < 0 or x + bw > EXPECTED[0] or y + bh > EXPECTED[1]:
            out_of_bounds.append(e["id"])
    add("layout_bounds", not out_of_bounds, f"out_of_bounds={out_of_bounds[:10]}")

    # 8. Non-blank PNG
    try:
        colors = subprocess.check_output(
            ["identify", "-format", "%k", str(png)], text=True, stderr=subprocess.DEVNULL
        ).strip()
        add("png_nonblank", int(colors) > 10, f"unique_colors={colors}")
    except Exception as exc:  # pragma: no cover
        add("png_nonblank", False, f"identify failed: {exc}")

    # 9. File sizes
    png_mb = png.stat().st_size / 1024 / 1024
    svg_kb = svg.stat().st_size / 1024
    add("file_size_png", png_mb < 3.0, f"PNG {png_mb:.2f} MB < 3 MB")
    add("file_size_svg", svg_kb < 1024, f"SVG {svg_kb:.1f} KB < 1 MB")

    # 10. Uniqueness: exactly one PNG with this basename under figures/
    matches = list(HERE.rglob(png.name))
    add("uniqueness", len(matches) == 1, f"found {len(matches)} PNG(s) named {png.name}")

    result = {
        "figure": data["id"],
        "png": str(png),
        "svg": str(svg),
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks),
        "manual_gates": {
            "teaching_5s": "pending human/reviewer confirmation",
            "no_figure_needed": "pending human/reviewer confirmation",
        },
    }
    out = Path(str(base) + ".checks.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in checks:
        print(("PASS" if c["pass"] else "FAIL"), c["gate"], "-", c["evidence"])
    print("ALL PASS" if result["all_pass"] else "GATES FAILED")
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
