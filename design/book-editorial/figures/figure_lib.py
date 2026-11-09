#!/usr/bin/env python3
"""Shared SVG drawing helpers for the DSWS editorial figures.

The geometry is deliberately dumb: every primitive records its bounding box
in a sidecar layout file, so the gates can check text overlap, bounds and
palette without a human looking at the PNG first.
"""
from __future__ import annotations

import html
import json

FONT = "'Noto Sans CJK SC','Noto Sans CJK JP','Droid Sans Fallback',sans-serif"

PALETTE = {
    "paper": "#FFFDF8",
    "ink": "#111111",
    "ink2": "#5B5B5B",
    "line": "#D9D3C7",
    "cobalt": "#1F4E9C",
    "rust": "#B24A2E",
    "forest": "#2F5D46",
    "mustard": "#C58B1B",
    "cobalt_tint": "#E7EDF8",
    "rust_tint": "#F7E8E1",
    "forest_tint": "#E6EFE9",
    "mustard_tint": "#F8EEDA",
    "wash": "#F8F5ED",
    "white": "#FFFFFF",
}

SIZES = {
    "title": 42,
    "section": 30,
    "subtitle": 26,
    "label": 24,
    "note": 22,
    "small": 18,
}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def text_width(text: str, size: float) -> float:
    """Conservative width estimate used only by the overlap gate."""
    width = 0.0
    for ch in str(text):
        code = ord(ch)
        if code > 0x2E80:
            width += size
        elif ch in "→←↑↓":
            width += size
        elif ch in " .,:;!|'`()[]":
            width += size * 0.34
        else:
            width += size * 0.58
    return width


class Figure:
    def __init__(self, width: int = 1600, height: int = 1100):
        self.width = width
        self.height = height
        self.elements: list[str] = []
        self.layout: list[dict] = []
        self.defs: list[str] = []
        # Text is drawn as real SVG <text> so it stays selectable and reviewable.
        # Set render_text=False to emit the same geometry without any glyphs; the
        # layout sidecar still records every string for the SVG overlay.
        self.render_text = True
        self._add_markers()

    def _add_markers(self) -> None:
        for name in ("ink", "cobalt", "rust", "forest", "mustard"):
            color = PALETTE[name]
            self.defs.append(
                f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>'
            )

    @staticmethod
    def _hex(value: str) -> str:
        return PALETTE.get(value, value)

    def rect(self, x, y, w, h, fill="paper", stroke="line", sw=1.5, rx=4, dash=None, eid=None):
        fill_hex = self._hex(fill)
        stroke_hex = self._hex(stroke)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.elements.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill_hex}" stroke="{stroke_hex}" stroke-width="{sw}"{dash_attr}/>'
        )
        self.layout.append(
            {
                "kind": "rect",
                "id": eid or f"rect-{len(self.layout)}",
                "box": [x, y, w, h],
                "fill": fill_hex,
                "stroke": stroke_hex,
            }
        )

    def text(self, x, y, value, size="label", fill="ink", weight="normal", anchor="start", eid=None, spacing=None):
        size_px = SIZES.get(size, size) if isinstance(size, str) else size
        fill_hex = self._hex(fill)
        value = str(value)
        width = text_width(value, size_px)
        if anchor == "middle":
            box_x = x - width / 2
        elif anchor == "end":
            box_x = x - width
        else:
            box_x = x
        box_y = y - size_px * 0.82
        box_h = size_px * 1.05
        spacing_attr = f' letter-spacing="{spacing}"' if spacing else ""
        if self.render_text:
            self.elements.append(
                f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size_px}" '
                f'font-weight="{weight}" fill="{fill_hex}" text-anchor="{anchor}"{spacing_attr}>{esc(value)}</text>'
            )
        self.layout.append(
            {
                "kind": "text",
                "id": eid or f"text-{len(self.layout)}",
                "box": [box_x, box_y, width, box_h],
                "text": value,
                "font_size": size_px,
                "fill": fill_hex,
                "anchor": anchor,
                "x": x,
                "y": y,
                "weight": weight,
            }
        )

    def line(self, x1, y1, x2, y2, stroke="ink", sw=2, dash=None, marker=None, eid=None):
        stroke_hex = self._hex(stroke)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        marker_attr = f' marker-end="url(#arrow-{marker})"' if marker else ""
        self.elements.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke_hex}" '
            f'stroke-width="{sw}"{dash_attr}{marker_attr}/>'
        )
        self.layout.append(
            {
                "kind": "line",
                "id": eid or f"line-{len(self.layout)}",
                "box": [min(x1, x2), min(y1, y2), abs(x2 - x1) or sw, abs(y2 - y1) or sw],
                "stroke": stroke_hex,
            }
        )

    def ellipse(self, cx, cy, rx, ry, fill="paper", stroke="ink", sw=1.5, dash=None, eid=None):
        fill_hex = self._hex(fill)
        stroke_hex = self._hex(stroke)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.elements.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill_hex}" '
            f'stroke="{stroke_hex}" stroke-width="{sw}"{dash_attr}/>'
        )
        self.layout.append(
            {
                "kind": "ellipse",
                "id": eid or f"ellipse-{len(self.layout)}",
                "box": [cx - rx, cy - ry, rx * 2, ry * 2],
                "fill": fill_hex,
                "stroke": stroke_hex,
            }
        )

    def circle(self, cx, cy, r, fill="paper", stroke="ink", sw=1.5, eid=None):
        self.ellipse(cx, cy, r, r, fill=fill, stroke=stroke, sw=sw, eid=eid)

    def path(self, d, fill="none", stroke="ink", sw=2, dash=None, cap="round", join="round", eid=None, box=None):
        fill_hex = self._hex(fill)
        stroke_hex = self._hex(stroke)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.elements.append(
            f'<path d="{d}" fill="{fill_hex}" stroke="{stroke_hex}" stroke-width="{sw}" '
            f'stroke-linecap="{cap}" stroke-linejoin="{join}"{dash_attr}/>'
        )
        self.layout.append(
            {
                "kind": "path",
                "id": eid or f"path-{len(self.layout)}",
                "box": box or [0, 0, 0, 0],
                "fill": fill_hex,
                "stroke": stroke_hex,
            }
        )

    def polygon(self, points, fill="paper", stroke="ink", sw=1.5, eid=None):
        fill_hex = self._hex(fill)
        stroke_hex = self._hex(stroke)
        coords = [tuple(map(float, p.split(","))) for p in points.split()]
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        pts = " ".join(f"{x},{y}" for x, y in coords)
        self.elements.append(
            f'<polygon points="{pts}" fill="{fill_hex}" stroke="{stroke_hex}" stroke-width="{sw}"/>'
        )
        self.layout.append(
            {
                "kind": "polygon",
                "id": eid or f"polygon-{len(self.layout)}",
                "box": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
                "fill": fill_hex,
                "stroke": stroke_hex,
            }
        )

    def svg(self) -> str:
        defs = "\n".join(self.defs)
        body = "\n".join(self.elements)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}">\n'
            f'<defs>\n{defs}\n</defs>\n'
            f'<rect x="0" y="0" width="{self.width}" height="{self.height}" fill="{PALETTE["paper"]}"/>\n'
            f'{body}\n</svg>\n'
        )

    def save(self, svg_path: str, layout_path: str | None = None) -> None:
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(self.svg())
        if layout_path:
            with open(layout_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"width": self.width, "height": self.height, "elements": self.layout},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
