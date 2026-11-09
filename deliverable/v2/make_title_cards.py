#!/usr/bin/env python3
"""生成验收版片头/片尾卡片（纸感，与正片一致）。

用法：
    python3 deliverable/v2/make_title_cards.py
产物：
    deliverable/v2/intro-card.png
    deliverable/v2/outro-card.png
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
W, H = 1920, 1080
BG = (248, 239, 231)
INK = (26, 26, 26)
GRAY = (91, 91, 91)
GREEN = (47, 93, 70)
MUSTARD = (240, 180, 41)
BLACK = (17, 17, 17)

REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=2)  # index 2 = SC


def badge(draw: ImageDraw.ImageDraw, text: str) -> None:
    f = font(BOLD, 34)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    tw, th = right - left, bottom - top
    x2, y1 = 1880, 8
    x1, y2 = x2 - tw - 44, y1 + th + 28
    draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill=BLACK)
    draw.text(((x1 + x2) / 2, (y1 + y2) / 2), text, font=f, fill=(255, 255, 255), anchor="mm")


def bottom(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.rectangle((0, 988, W, H), fill=BLACK)
    draw.rectangle((0, 984, W, 988), fill=MUSTARD)
    draw.text((W / 2, 1036), text, font=font(REG, 34), fill=(255, 255, 255), anchor="mm")


def opening() -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    badge(d, "PRD 总览 · 电商问数")
    bottom(d, "自然语言问数 · LangGraph 12 节点 · SQL 自校验与自纠错")
    d.text((W / 2, 340), "DSWS · 电商问数", font=font(REG, 26), fill=GREEN, anchor="mm")
    d.text((W / 2, 425), "电商问数智能体", font=font(BOLD, 86), fill=INK, anchor="mm")
    d.text((W / 2, 525), "自然语言问数 · LangGraph 12 节点 · SQL 自校验与自纠错",
           font=font(REG, 34), fill=GRAY, anchor="mm")
    d.text((W / 2, 600), "项目：DSWS 电商问数 ｜ 2026-11", font=font(REG, 30), fill=INK, anchor="mm")
    d.text((W / 2, 655), "演示环境：http://8.155.135.97:5051", font=font(REG, 30), fill=GREEN, anchor="mm")
    return im


def closing() -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    badge(d, "DSWS · 验收完成")
    bottom(d, "演示结束 · 感谢观看 · 欢迎验收指导")
    d.text((W / 2, 345), "DSWS · 电商问数", font=font(REG, 26), fill=GREEN, anchor="mm")
    d.text((W / 2, 435), "演示结束", font=font(BOLD, 86), fill=INK, anchor="mm")
    d.text((W / 2, 535), "感谢观看 · 欢迎验收指导", font=font(REG, 36), fill=GRAY, anchor="mm")
    d.text((W / 2, 610), "12 节点 · 校正闭环 · 安全拒绝", font=font(REG, 30), fill=INK, anchor="mm")
    d.text((W / 2, 665), "演示环境：http://8.155.135.97:5051", font=font(REG, 30), fill=GREEN, anchor="mm")
    return im


def main() -> int:
    opening().save(HERE / "intro-card.png")
    closing().save(HERE / "outro-card.png")
    print(HERE / "intro-card.png")
    print(HERE / "outro-card.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
