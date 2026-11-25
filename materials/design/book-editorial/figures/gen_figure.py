#!/usr/bin/env python3
"""Generate the §3 comic: three silent failures told as a restaurant story.

Usage:
    python3 gen_figure.py content/fig-3-0-three-silent-failures.json

The geometry is fixed here. The content file supplies the dialogue, captions,
and the per-panel accent/tint tokens, so an executor never has to invent
coordinates. The comic is deliberately vector line art: exact Chinese text,
a limited editorial palette, and no raster generation step.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from figure_lib import Figure

HERE = Path(__file__).resolve().parent


# ---------- shared comic primitives ----------


def speech(fig, pid, x, y, w, h, lines, accent, tail_x, tail_y, size="note"):
    fig.rect(x, y, w, h, fill="white", stroke=accent, sw=1.5, rx=12, eid=f"{pid}-speech-box")
    fig.polygon(
        f"{x + w * 0.30},{y + h - 1} {x + w * 0.46},{y + h - 1} {tail_x},{tail_y}",
        fill="white",
        stroke=accent,
        sw=1.5,
        eid=f"{pid}-speech-tail",
    )
    line_h = 26
    for i, line in enumerate(lines):
        fig.text(
            x + w / 2,
            y + h / 2 + 7 + (i - (len(lines) - 1) / 2) * line_h,
            line,
            size=size,
            fill="ink",
            anchor="middle",
            eid=f"{pid}-speech-{i}",
        )


def thought(fig, pid, x, y, w, h, lines, accent, tail_x, tail_y, size="note"):
    fig.rect(x, y, w, h, fill="white", stroke=accent, sw=1.5, rx=18, dash="4 4", eid=f"{pid}-thought-box")
    fig.circle(tail_x, tail_y - 14, 5, fill="white", stroke=accent, sw=1.2, eid=f"{pid}-thought-dot-1")
    fig.circle(tail_x, tail_y - 3, 3, fill="white", stroke=accent, sw=1.2, eid=f"{pid}-thought-dot-2")
    line_h = 24
    for i, line in enumerate(lines):
        fig.text(
            x + w / 2,
            y + h / 2 + 7 + (i - (len(lines) - 1) / 2) * line_h,
            line,
            size=size,
            fill="ink",
            anchor="middle",
            eid=f"{pid}-thought-{i}",
        )


def customer(fig, pid, cx, cy, expression="confused"):
    # Hair behind the head.
    fig.path(
        f"M {cx - 30} {cy - 2} Q {cx - 32} {cy - 40} {cx} {cy - 40} "
        f"Q {cx + 32} {cy - 40} {cx + 30} {cy - 2} "
        f"Q {cx + 18} {cy - 16} {cx} {cy - 16} "
        f"Q {cx - 18} {cy - 16} {cx - 30} {cy - 2} Z",
        fill="ink",
        stroke="ink",
        sw=1,
        eid=f"{pid}-customer-hair",
    )
    fig.circle(cx, cy, 30, fill="paper", stroke="ink", sw=2.2, eid=f"{pid}-customer-head")
    fig.circle(cx - 10, cy - 2, 2.6, fill="ink", stroke="ink", sw=0, eid=f"{pid}-customer-eye-l")
    fig.circle(cx + 10, cy - 2, 2.6, fill="ink", stroke="ink", sw=0, eid=f"{pid}-customer-eye-r")
    fig.path(f"M {cx - 17} {cy - 13} L {cx - 6} {cy - 10}", stroke="ink", sw=2, eid=f"{pid}-customer-brow-l")
    fig.path(f"M {cx + 6} {cy - 10} L {cx + 17} {cy - 13}", stroke="ink", sw=2, eid=f"{pid}-customer-brow-r")
    if expression == "confused":
        mouth = f"M {cx - 7} {cy + 12} Q {cx} {cy + 18} {cx + 7} {cy + 12}"
    elif expression == "worried":
        mouth = f"M {cx - 7} {cy + 16} Q {cx} {cy + 10} {cx + 7} {cy + 16}"
    else:
        mouth = f"M {cx - 8} {cy + 14} Q {cx} {cy + 20} {cx + 8} {cy + 14}"
    fig.path(mouth, stroke="ink", sw=2, eid=f"{pid}-customer-mouth")
    fig.rect(cx - 32, cy + 30, 64, 74, fill="cobalt_tint", stroke="cobalt", sw=2, rx=10, eid=f"{pid}-customer-body")
    fig.path(f"M {cx - 30} {cy + 48} L {cx - 58} {cy + 86}", stroke="cobalt", sw=6, eid=f"{pid}-customer-arm-l")
    fig.path(f"M {cx + 30} {cy + 48} L {cx + 58} {cy + 86}", stroke="cobalt", sw=6, eid=f"{pid}-customer-arm-r")


def waiter(fig, pid, cx, cy, pose="point"):
    fig.path(
        f"M {cx - 24} {cy - 4} Q {cx - 26} {cy - 34} {cx} {cy - 34} "
        f"Q {cx + 26} {cy - 34} {cx + 24} {cy - 4} "
        f"Q {cx + 12} {cy - 18} {cx} {cy - 18} "
        f"Q {cx - 12} {cy - 18} {cx - 24} {cy - 4} Z",
        fill="ink",
        stroke="ink",
        sw=1,
        eid=f"{pid}-waiter-hair",
    )
    fig.circle(cx, cy, 24, fill="paper", stroke="ink", sw=2, eid=f"{pid}-waiter-head")
    fig.circle(cx - 8, cy - 1, 2.2, fill="ink", stroke="ink", sw=0, eid=f"{pid}-waiter-eye-l")
    fig.circle(cx + 8, cy - 1, 2.2, fill="ink", stroke="ink", sw=0, eid=f"{pid}-waiter-eye-r")
    fig.path(f"M {cx - 6} {cy + 10} Q {cx} {cy + 14} {cx + 6} {cy + 10}", stroke="ink", sw=1.8, eid=f"{pid}-waiter-mouth")
    fig.rect(cx - 25, cy + 24, 50, 92, fill="white", stroke="ink", sw=2, rx=8, eid=f"{pid}-waiter-body")
    fig.rect(cx - 20, cy + 52, 40, 58, fill="ink", stroke="ink", sw=1, rx=4, eid=f"{pid}-waiter-apron")
    fig.polygon(
        f"{cx - 10},{cy + 28} {cx},{cy + 34} {cx - 10},{cy + 40}",
        fill="rust",
        stroke="rust",
        sw=1,
        eid=f"{pid}-waiter-bow-l",
    )
    fig.polygon(
        f"{cx + 10},{cy + 28} {cx},{cy + 34} {cx + 10},{cy + 40}",
        fill="rust",
        stroke="rust",
        sw=1,
        eid=f"{pid}-waiter-bow-r",
    )
    if pose == "point":
        fig.path(f"M {cx - 20} {cy + 44} L {cx - 58} {cy + 78}", stroke="ink", sw=5, eid=f"{pid}-waiter-arm-l")
        fig.path(f"M {cx + 20} {cy + 44} L {cx + 48} {cy + 70}", stroke="ink", sw=5, eid=f"{pid}-waiter-arm-r")
    elif pose == "shrug":
        fig.path(f"M {cx - 20} {cy + 44} L {cx - 52} {cy + 28}", stroke="ink", sw=5, eid=f"{pid}-waiter-arm-l")
        fig.path(f"M {cx + 20} {cy + 44} L {cx + 52} {cy + 28}", stroke="ink", sw=5, eid=f"{pid}-waiter-arm-r")
    else:  # carry
        fig.path(f"M {cx - 20} {cy + 44} L {cx - 46} {cy + 64}", stroke="ink", sw=5, eid=f"{pid}-waiter-arm-l")
        fig.path(f"M {cx + 20} {cy + 44} L {cx + 46} {cy + 64}", stroke="ink", sw=5, eid=f"{pid}-waiter-arm-r")


def chef(fig, pid, cx, cy):
    fig.rect(cx - 22, cy - 44, 44, 16, fill="white", stroke="ink", sw=1.5, rx=3, eid=f"{pid}-chef-hat-band")
    fig.ellipse(cx, cy - 46, 22, 10, fill="white", stroke="ink", sw=1.5, eid=f"{pid}-chef-hat-top")
    fig.circle(cx, cy, 20, fill="paper", stroke="ink", sw=2, eid=f"{pid}-chef-head")
    fig.circle(cx - 7, cy - 2, 2, fill="ink", stroke="ink", sw=0, eid=f"{pid}-chef-eye-l")
    fig.circle(cx + 7, cy - 2, 2, fill="ink", stroke="ink", sw=0, eid=f"{pid}-chef-eye-r")
    fig.path(
        f"M {cx - 10} {cy + 8} Q {cx - 5} {cy + 4} {cx} {cy + 8} Q {cx + 5} {cy + 4} {cx + 10} {cy + 8}",
        stroke="ink",
        sw=3,
        eid=f"{pid}-chef-mustache",
    )
    fig.rect(cx - 24, cy + 18, 48, 42, fill="white", stroke="ink", sw=2, rx=6, eid=f"{pid}-chef-body")
    fig.rect(cx - 18, cy + 32, 36, 28, fill="forest", stroke="forest", sw=1, rx=3, eid=f"{pid}-chef-apron")


def table(fig, pid, x, y, w):
    fig.rect(x, y, w, 10, fill="line", stroke="ink", sw=2, rx=2, eid=f"{pid}-table-top")
    fig.path(f"M {x + 30} {y + 10} L {x + 22} {y + 50}", stroke="ink", sw=4, eid=f"{pid}-table-leg-l")
    fig.path(f"M {x + w - 30} {y + 10} L {x + w - 22} {y + 50}", stroke="ink", sw=4, eid=f"{pid}-table-leg-r")


def plate(fig, pid, cx, cy, empty=False):
    fig.ellipse(cx, cy, 62, 12, fill="white", stroke="ink", sw=2, eid=f"{pid}-plate")
    fig.ellipse(cx, cy, 46, 7, fill="none", stroke="line", sw=1.2, dash="3 4" if empty else None, eid=f"{pid}-plate-inner")


def header(fig, pid, x, y, w, panel):
    fig.rect(x, y, w, 76, fill=panel["tint"], stroke="none", sw=0, rx=6, eid=f"{pid}-header-bg")
    fig.text(x + 18, y + 28, panel["act"], size="label", fill=panel["accent"], weight="bold", eid=f"{pid}-act")
    fig.text(x + 18, y + 54, panel["root"], size="small", fill="ink2", eid=f"{pid}-root")
    fig.line(x, y + 76, x + w, y + 76, stroke=panel["accent"], sw=1.5, eid=f"{pid}-header-rule")


def captions(fig, pid, x, y, w, panel):
    fig.line(x + 18, y + 410, x + w - 18, y + 410, stroke="line", sw=1, eid=f"{pid}-caption-rule")
    fig.text(x + 18, y + 440, panel["caption_seen"], size="note", fill="ink", weight="bold", eid=f"{pid}-caption-seen")
    fig.text(x + 18, y + 470, panel["caption_actual"], size="small", fill="ink2", eid=f"{pid}-caption-actual")
    fig.text(x + 18, y + 500, panel["fix"], size="small", fill=panel["accent"], weight="bold", eid=f"{pid}-caption-fix")


# ---------- three panels ----------


def panel_one(fig, x, y, w, h, p):
    fig.rect(x, y, w, h, fill="paper", stroke="line", sw=1.5, rx=6, eid="p1-bg")
    header(fig, "p1", x, y, w, p)
    fig.line(x + 18, y + 400, x + w - 18, y + 400, stroke="line", sw=1.5, eid="p1-floor")

    customer(fig, "p1", x + 95, y + 270, "confused")
    waiter(fig, "p1", x + 380, y + 240, "point")
    table(fig, "p1", x + 40, y + 350, w - 80)
    plate(fig, "p1", x + 250, y + 345)

    fig.rect(x + 210, y + 315, 80, 32, fill="paper", stroke="ink", sw=1.5, rx=2, eid="p1-note")
    fig.text(x + 250, y + 337, p["note"], size="small", fill="ink", anchor="middle", eid="p1-note-text")

    fig.rect(x + 320, y + 300, 80, 50, fill="mustard_tint", stroke="mustard", sw=1.5, rx=3, eid="p1-receipt")
    fig.text(x + 360, y + 322, p["receipt"], size="small", fill="ink", anchor="middle", eid="p1-receipt-text")
    fig.path(f"M {x + 352} {y + 342} L {x + 358} {y + 348} L {x + 370} {y + 334}", stroke="forest", sw=3, eid="p1-check")

    thought(fig, "p1", x + 18, y + 150, 150, 60, p["thought"], "cobalt", x + 95, y + 240)
    speech(fig, "p1", x + 300, y + 140, 140, 56, p["speech"], "cobalt", x + 380, y + 216)
    captions(fig, "p1", x, y, w, p)


def panel_two(fig, x, y, w, h, p):
    fig.rect(x, y, w, h, fill="paper", stroke="line", sw=1.5, rx=6, eid="p2-bg")
    header(fig, "p2", x, y, w, p)
    fig.line(x + 18, y + 400, x + w - 18, y + 400, stroke="line", sw=1.5, eid="p2-floor")

    customer(fig, "p2", x + 95, y + 270, "worried")
    waiter(fig, "p2", x + 380, y + 240, "shrug")
    table(fig, "p2", x + 40, y + 350, w - 80)
    plate(fig, "p2", x + 250, y + 345, empty=True)
    fig.circle(x + 235, y + 342, 2.5, fill="mustard", stroke="mustard", sw=0, eid="p2-crumb-1")
    fig.circle(x + 265, y + 343, 2, fill="mustard", stroke="mustard", sw=0, eid="p2-crumb-2")

    thought(fig, "p2", x + 18, y + 140, 170, 80, p["thought"], "rust", x + 95, y + 240)
    speech(fig, "p2", x + 320, y + 140, 120, 56, p["speech"], "rust", x + 380, y + 216)
    captions(fig, "p2", x, y, w, p)


def panel_three(fig, x, y, w, h, p):
    fig.rect(x, y, w, h, fill="paper", stroke="line", sw=1.5, rx=6, eid="p3-bg")
    header(fig, "p3", x, y, w, p)
    fig.line(x + 18, y + 400, x + w - 18, y + 400, stroke="line", sw=1.5, eid="p3-floor")

    # Kitchen pass in the background.
    fig.rect(x + 290, y + 90, 150, 120, fill="wash", stroke="line", sw=1.5, rx=4, eid="p3-window")
    fig.text(x + 365, y + 112, p["kitchen"], size="small", fill="ink2", anchor="middle", eid="p3-kitchen-text")
    chef(fig, "p3", x + 365, y + 178)
    fig.rect(x + 290, y + 200, 150, 10, fill="wash", stroke="none", sw=0, eid="p3-mask")
    fig.rect(x + 290, y + 210, 150, 10, fill="line", stroke="ink", sw=1.5, eid="p3-counter")
    fig.ellipse(x + 365, y + 240, 38, 9, fill="white", stroke="ink", sw=1.5, eid="p3-pass-plate")
    fig.ellipse(x + 365, y + 236, 24, 7, fill="ink", stroke="ink", sw=1, eid="p3-burnt-dish")
    fig.path(f"M {x + 350} {y + 230} C {x + 338} {y + 212}, {x + 360} {y + 200}, {x + 348} {y + 184}", stroke="ink2", sw=2.5, eid="p3-smoke-1")
    fig.path(f"M {x + 370} {y + 230} C {x + 382} {y + 210}, {x + 362} {y + 198}, {x + 374} {y + 180}", stroke="ink2", sw=2.5, eid="p3-smoke-2")

    customer(fig, "p3", x + 95, y + 270, "cough")
    waiter(fig, "p3", x + 380, y + 300, "carry")
    table(fig, "p3", x + 40, y + 350, w - 80)

    plate(fig, "p3", x + 250, y + 345)
    fig.ellipse(x + 250, y + 338, 34, 10, fill="ink", stroke="ink", sw=1, eid="p3-table-burnt")
    fig.rect(x + 205, y + 312, 90, 58, fill="none", stroke="rust", sw=3, rx=3, eid="p3-alert-frame")
    fig.circle(x + 298, y + 310, 15, fill="rust", stroke="paper", sw=2, eid="p3-alert-badge")
    fig.path(f"M {x + 298} {y + 302} L {x + 298} {y + 314}", stroke="white", sw=4, eid="p3-alert-stem")
    fig.circle(x + 298, y + 320, 2.6, fill="white", stroke="white", sw=0, eid="p3-alert-dot")

    # Cough marks.
    fig.path(f"M {x + 118} {y + 278} L {x + 130} {y + 274}", stroke="ink2", sw=1.5, eid="p3-cough-1")
    fig.path(f"M {x + 120} {y + 288} L {x + 134} {y + 286}", stroke="ink2", sw=1.5, eid="p3-cough-2")
    fig.path(f"M {x + 118} {y + 298} L {x + 130} {y + 302}", stroke="ink2", sw=1.5, eid="p3-cough-3")

    thought(fig, "p3", x + 18, y + 140, 130, 56, p["thought"], "forest", x + 95, y + 240)
    speech(fig, "p3", x + 270, y + 210, 190, 60, p["speech"], "forest", x + 380, y + 276)
    captions(fig, "p3", x, y, w, p)


def draw(fig: Figure, data: dict) -> None:
    fig.text(80, 64, data["title"], size="title", fill="ink", weight="bold", eid="title")
    fig.text(80, 100, data["subtitle"], size="subtitle", fill="ink2", eid="subtitle")
    fig.line(80, 126, 1520, 126, stroke="line", sw=1.5, eid="header-rule")

    fig.rect(1370, 38, 150, 36, fill="mustard_tint", stroke="mustard", sw=1.5, rx=18, eid="analogy-tag")
    fig.text(1445, 62, data["tag"], size="small", fill="mustard", anchor="middle", eid="tag-text")

    xs = [80, 570, 1060]
    for x, panel in zip(xs, data["panels"]):
        {"p1": panel_one, "p2": panel_two, "p3": panel_three}[panel["id"]](fig, x, 160, 460, 540, panel)

    fig.line(80, 718, 1520, 718, stroke="line", sw=1.5, eid="footer-rule")
    fig.text(80, 758, data["takeaway"], size="section", fill="ink", weight="bold", eid="takeaway")
    fig.text(80, 796, data["countermeasure"], size="subtitle", fill="ink2", eid="countermeasure")
    fig.text(80, 846, data["source_line"], size="small", fill="ink2", eid="source-line")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: gen_figure.py <content.json>", file=sys.stderr)
        return 2
    content_path = Path(sys.argv[1])
    data = json.loads(content_path.read_text(encoding="utf-8"))
    base = HERE / data["id"]

    fig = Figure(1600, 900)
    draw(fig, data)
    fig.save(str(base) + ".svg", str(base) + ".layout.json")

    manifest = {
        "figure": data["id"],
        "strings": [
            {"text": e["text"], "font_size": e["font_size"], "id": e["id"]}
            for e in fig.layout
            if e["kind"] == "text"
        ],
    }
    (Path(str(base) + ".text-manifest.json")).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(str(base) + ".svg")
    print(str(base) + ".layout.json")
    print(str(base) + ".text-manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
