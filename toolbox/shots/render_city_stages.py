#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_city_stages.py —— 「同一片城区：从荒地工地到敢交付的城市」四阶段隐喻图（一张 PNG）。

在仓库根目录一条命令重跑：

    python3 tutorial/shots/render_city_stages.py

读（只读）：
  `tutorial/city/stages-city.json`  四阶段定义（D44 造 / 换 / 审 / 守 + 横切系统 × 接线点，
                                  不用「每级长 5/3/4 件」的旧口径）
  `tutorial/city/data.json`         城市几何单源（四区 / 十件设施 / 11 条道路 / 12 件交付物）；
                                  四格共用这一套坐标，脚本只读、不改
写：
  `tutorial/images/city-4stages.png` 3200×2000（设计画布 1600×1000，4× 超采样后降采样到 2×）

图在说什么（一句话）：
  **同一片城区、同一套坐标：L1 造骨架（壳），L2 换真数据与真部署（通水电网），
  L3 审生成与校验（智慧城市），L4 守安全与可观测（城市安防）；级与级的差别是横切系统，不是又一批件。**

四格不是四座不同的城市，而是**同一片城区、同一视角（俯视规划图）、同一坐标基准**的四个版本：
  - 格 1 荒地工地：空地 + 围挡 + 工棚 + 塔吊 + 毛坯楼壳，规划路网只有灰虚线，12 枚编号徽章全空心灰；
  - 格 2 通水电网：楼体成形、道路铺实、水管/电缆接通带节点，仓库/服务中心/门户就位，
    徽章 ②④⑧⑨ 亮起（部署 / 数据 / 契约 / 执行链）；
  - 格 3 智慧城市：路灯亮、橙色数据流沿路网跑、服务中心楼顶城市大脑上线、窗口与门户挂监控屏，
    徽章 ③⑥⑦⑩ 新亮（累计 8/12）；
  - 格 4 城市安防：门禁/检查站、摄像头+视线锥、城管岗亭、应急中心、监控大屏，整体最满，
    徽章 12/12 全亮（①⑤⑪⑫ 新亮，⑧⑨⑩ 二次接线加橙外环）。
  底部一条「接线点」进度（L2 4/4 · L3 4/4 · L4 5/5），并写明接线点 ≠ 徽章数：
  接线点数横切系统要接的页，徽章只数 12 件设施（0 → 4 → 8 → 12）。

确定性：
  只用本机字体与确定性绘制（随机纹理用固定种子 44），不引外部图片 / CDN / 网络；
  重跑像素一致（PNG 不含时间戳等元数据），可反复核对 sha256。

依赖：Python 3 + Pillow（PIL）、Noto Sans CJK SC（/usr/share/fonts/opentype/noto）。
只写上面那一个 PNG；不回写 JSON、不动 tutorial/city/data.json。

自检（脚本结束前打印）：
  ① 4 阶段齐全、名字 / 副题 / 横切系统 / 接线点数 / 徽章数 / 机制条数与 D44+D45 口径逐项一致；
  ② 12 件设施 / 4 区 / 11 条道路与 data.json 对齐，12 枚徽章每格都在、亮起数 0/4/8/12；
  ③ 四格几何同一坐标基准（同一变换、同一 city 数据哈希）；
  ④ 成图 3200×2000，四格「暖度」严格递增；
  ⑤ 图上文字无外链 / 用户名 / 绝对路径 / 口令；
  ⑥ --twice 时重绘一遍比对 sha256（默认开，可用 --fast 跳过）。
"""

from __future__ import annotations

import hashlib
import json
import os
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
STAGES_PATH = REPO / "manual" / "city" / "stages-city.json"
CITY_PATH = REPO / "manual" / "city" / "data.json"
OUT_PNG = REPO / "manual" / "images" / "city-4stages.png"

# ---------------------------------------------------------------- 画布与版式

W, H = 1600, 1000                               # 设计画布（逻辑单位）
SS = 4                                          # 超采样倍数：6400×4000 画，再降到 3200×2000
OUT_W, OUT_H = W * 2, H * 2                     # 成图尺寸（2× 设计画布）
FINAL_SCALE = OUT_W // W                        # 降采样比例（2）

M = 38                                          # 页面左右边距
PW, GAP = 360, 28                               # 单格宽 / 格间距
PY, PH = 104, 800                               # 四格顶 / 高
PAD = 14                                        # 格内边距
INNER = PW - 2 * PAD                            # 格内可用宽 332
MAP_W = INNER                                   # 地图视口宽（城市画布 1600 × 1000 → 同比例）
MAP_H = MAP_W * H / W                           # 207.5
MAP_FRAME_H = 250                                # 地图框高（含注记条 / 图层条 / 比例尺）
PANEL_X = [M + i * (PW + GAP) for i in range(4)]

# 颜色：黑白灰 + 橙色强调；四阶段冷灰 → 暖橙单调递进
PAPER = "#F4F1E9"
INK = "#2E2A24"
INK2 = "#4E473A"
MUT = "#857C6B"
FAINT = "#B4AB99"
HAIR = "#D8D0BE"
ORANGE = "#C2410C"
ORANGE_L = "#E07020"

PALETTES = [
    dict(accent="#8A8274", accent2="#6F6A5C", bg="#F1F0EA", map_bg="#EEEDE6", zone="#E7E5DB"),
    dict(accent="#A0713D", accent2="#7E5A30", bg="#F3EEE1", map_bg="#F0E9D9", zone="#E9E1CB"),
    dict(accent="#B25C1C", accent2="#8C4715", bg="#F6EDDB", map_bg="#F2E8D0", zone="#EDDFC0"),
    dict(accent="#C2410C", accent2="#93320A", bg="#F8EBD3", map_bg="#F4E6C8", zone="#F0DBB2"),
]

FONT_DIR = Path("/usr/share/fonts/opentype/noto")
FONT_FILES = {
    "Black": "NotoSansCJK-Black.ttc",
    "Bold": "NotoSansCJK-Bold.ttc",
    "Medium": "NotoSansCJK-Medium.ttc",
    "Regular": "NotoSansCJK-Regular.ttc",
    "Light": "NotoSansCJK-Light.ttc",
}
FONT_INDEX_SC = 2                               # Noto Sans CJK TTC 里 SC 的序号

# D44 + D45 的口径（自检逐项比对；改口径先改 stages-city.json 与本表）
EXPECTED = [
    dict(level="L1", name="荒地工地", subtitle="只有围挡和毛坯设施，能站人不能用",
         crosscut="骨架", cp=0, badges=0, new=0, rewire=0, mech=3, pages="P0–P9"),
    dict(level="L2", name="通水电网", subtitle="楼立起来、水电管网接通",
         crosscut="数据与部署的真实性", cp=4, badges=4, new=4, rewire=0, mech=4, pages="P10–P13"),
    dict(level="L3", name="智慧城市", subtitle="城市大脑上线：会看、会算、会自查",
         crosscut="生成与校验的正确性", cp=4, badges=8, new=4, rewire=2, mech=4, pages="P14–P17"),
    dict(level="L4", name="城市安防", subtitle="门禁、城管、监控、应急都到位，敢交付",
         crosscut="安全、可观测、可运维", cp=5, badges=12, new=4, rewire=3, mech=5, pages="P18–P22"),
]

# 每格「城市读数」：图里真画出来的东西（数字与绘制代码一致，可人工复核）
STAGE_STATS = [
    [("1 圈", "施工围挡"), ("3 座", "毛坯楼壳"), ("12", "空心徽章")],
    [("3 座", "楼体成形"), ("2 条", "水电管网"), ("0", "亮着路灯")],
    [("10 盏", "亮着路灯"), ("9 路", "数据流"), ("2 块", "监控屏")],
    [("6 个", "摄像头"), ("3 道", "门禁 / 检查站"), ("5 条", "防线（接线点）")],
]

# 12 件设施件 → 城市里的位置（相对所属设施矩形；P8 是流线，用 flow_path 上的点）
BADGE_REL = {
    1: ("P0", 0.78, 0.60),
    2: ("P1", 0.86, 0.12),
    3: ("P2", 0.10, 0.16),
    4: ("P2", 0.82, 0.72),
    5: ("P3", 0.06, 0.92),
    6: ("P4", 0.50, 0.28),
    7: ("P5", 0.82, 0.28),
    8: ("P6", 0.82, 0.18),
    9: ("P7", 0.82, 0.18),
    10: ("P8", 0.22, 1.05),
    11: ("P9", 0.12, 0.30),
    12: ("P9", 0.55, 0.42),
}

HOST_USER = Path.home().name                       # 本机用户名不进图，只用于自检
FORBIDDEN = ["/home/", "/Users/", "/tmp/", HOST_USER, "password", "passwd",
             "sk-", "http://", "https://", "root@", "127.0.0.1", "localhost"]

DRAWN_TEXTS: list[str] = []                     # 所有画到图上的文字（自检用）
BADGE_LOG: list[tuple[int, int, int, int]] = [] # (panel_idx, 画了几枚, 亮几枚, 新亮几枚)
MAP_GEOM: list[tuple] = []                      # (panel_idx, x, y, w, h, city_hash)
WARM_LOG: list[float] = []


# ---------------------------------------------------------------- 通用小工具

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def get_font(weight: str, px: int) -> ImageFont.FreeTypeFont:
    """按字重与像素字号取字体（SC 面，index=2）。"""
    px = max(8, int(round(px)))
    key = (weight, px)
    font = _FONT_CACHE.get(key)
    if font is None:
        font = ImageFont.truetype(str(FONT_DIR / FONT_FILES[weight]), px, index=FONT_INDEX_SC)
        _FONT_CACHE[key] = font
    return font


def mix(c1: str, c2: str, t: float) -> str:
    """两色线性混合，t=0 取 c1，t=1 取 c2。"""
    a = ImageColorHelpers.rgb(c1)
    b = ImageColorHelpers.rgb(c2)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class ImageColorHelpers:
    @staticmethod
    def rgb(c: str) -> tuple[int, int, int]:
        c = c.lstrip("#")
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _tokens(text: str) -> list[str]:
    """折行单位：CJK 逐字可断，ASCII 单词 / 命令整块不拆（过长才硬断）。"""
    toks: list[str] = []
    buf = ""
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch in "_-./:+=%$@\"'"):
            buf += ch
        else:
            if buf:
                toks.append(buf)
                buf = ""
            toks.append(ch)
    if buf:
        toks.append(buf)
    return toks


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_px: float) -> list[str]:
    """按像素宽度折行：中文按字、英文按词；行首不放标点。"""
    lines: list[str] = []
    cur = ""
    for tok in _tokens(text):
        if tok == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + tok
        if font.getlength(trial) <= max_px:
            cur = trial
            continue
        if tok in "，。、；：！？）》」』】·,.;:!?)":
            cur += tok
            lines.append(cur)
            cur = ""
            continue
        if cur:
            lines.append(cur)
            cur = ""
        # 单个 token 比整行还宽：硬断
        while font.getlength(tok) > max_px:
            cut = len(tok)
            while cut > 1 and font.getlength(tok[:cut]) > max_px:
                cut -= 1
            lines.append(tok[:cut])
            tok = tok[cut:]
        cur = tok
    if cur:
        lines.append(cur)
    return lines


def dashed_polyline(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], color: str,
                    width: int, dash: float, gap: float) -> None:
    """按「实线 dash + 空隙 gap」画折线（像素坐标；on/off 跨段连续）。"""
    on, rem = True, dash
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg <= 0:
            continue
        pos = 0.0
        while pos < seg:
            step = min(rem, seg - pos)
            t0, t1 = pos / seg, (pos + step) / seg
            if on:
                draw.line(
                    [(x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0),
                     (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1)],
                    fill=color, width=width)
            pos += step
            rem -= step
            if rem <= 1e-6:
                on = not on
                rem = dash if on else gap


def arrow_head(draw: ImageDraw.ImageDraw, tip: tuple[float, float], angle_rad: float,
               size: float, color: str) -> None:
    """在 tip 处画一个指向 angle_rad 方向的实心箭头。"""
    back = angle_rad + math.pi
    left = (tip[0] + size * math.cos(back + 0.42), tip[1] + size * math.sin(back + 0.42))
    right = (tip[0] + size * math.cos(back - 0.42), tip[1] + size * math.sin(back - 0.42))
    draw.polygon([tip, left, right], fill=color)


def point_at(pts: list[tuple[float, float]], frac: float) -> tuple[float, float, float]:
    """折线上按比例取点，返回 (x, y, 切线角)。"""
    segs = []
    total = 0.0
    for i in range(len(pts) - 1):
        d = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        segs.append(d)
        total += d
    if total <= 0:
        return pts[0][0], pts[0][1], 0.0
    want = frac * total
    acc = 0.0
    for i, d in enumerate(segs):
        if acc + d >= want or i == len(segs) - 1:
            t = 0.0 if d <= 0 else (want - acc) / d
            x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
            y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t
            ang = math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0])
            return x, y, ang
        acc += d
    return pts[-1][0], pts[-1][1], 0.0


# ---------------------------------------------------------------- 主画布（页面）

class Sheet:
    """逻辑坐标 1600×1000 的页面画布（内部按 SS 超采样）。"""

    def __init__(self) -> None:
        self.img = Image.new("RGB", (W * SS, H * SS), PAPER)
        self.d = ImageDraw.Draw(self.img)

    # -- 坐标 / 宽度
    @staticmethod
    def px(v: float) -> int:
        return int(round(v * SS))

    def pt(self, p: tuple[float, float]) -> tuple[int, int]:
        return (self.px(p[0]), self.px(p[1]))

    def line(self, pts, fill, w=1.0, joint="curve") -> None:
        self.d.line([self.pt(p) for p in pts], fill=fill,
                    width=max(1, self.px(w)), joint=joint)

    def dashed(self, pts, fill, w=1.0, dash=6.0, gap=4.0) -> None:
        dashed_polyline(self.d, [self.pt(p) for p in pts], fill,
                        max(1, self.px(w)), dash * SS, gap * SS)

    def rect(self, x, y, w, h, fill=None, outline=None, width=1.0) -> None:
        self.d.rectangle([self.px(x), self.px(y), self.px(x + w), self.px(y + h)],
                         fill=fill, outline=outline, width=max(1, self.px(width)))

    def rrect(self, x, y, w, h, radius, fill=None, outline=None, width=1.0) -> None:
        self.d.rounded_rectangle(
            [self.px(x), self.px(y), self.px(x + w), self.px(y + h)],
            radius=self.px(radius), fill=fill, outline=outline, width=max(1, self.px(width)))

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=1.0) -> None:
        self.d.ellipse([self.px(cx - rx), self.px(cy - ry), self.px(cx + rx), self.px(cy + ry)],
                       fill=fill, outline=outline, width=max(1, self.px(width)))

    def circle(self, cx, cy, r, fill=None, outline=None, width=1.0) -> None:
        self.ellipse(cx, cy, r, r, fill=fill, outline=outline, width=width)

    def arc(self, cx, cy, r, start, end, fill, width=1.0) -> None:
        self.d.arc([self.px(cx - r), self.px(cy - r), self.px(cx + r), self.px(cy + r)],
                   start=start, end=end, fill=fill, width=max(1, self.px(width)))

    def text(self, xy, s, size, fill, weight="Regular", anchor="la", tracking=0.0) -> None:
        font = get_font(weight, size * SS)
        DRAWN_TEXTS.append(s)
        if tracking:
            x, y = self.pt(xy)
            step = tracking * SS
            for ch in s:
                self.d.text((x, y), ch, font=font, fill=fill, anchor=anchor)
                x += font.getlength(ch) + step
        else:
            self.d.text(self.pt(xy), s, font=font, fill=fill, anchor=anchor)

    def measure(self, s, size, weight="Regular") -> float:
        return get_font(weight, size * SS).getlength(s) / SS

    def lines(self, xy, lines, size, fill, weight="Regular", lh=None) -> float:
        """逐行文字，返回下一行的 y。"""
        lh = lh if lh is not None else size * 1.32
        x, y = xy
        for s in lines:
            self.text((x, y), s, size, fill, weight)
            y += lh
        return y


# ---------------------------------------------------------------- 城市地图层

class CityMap:
    """把 data.json 的同一套城区几何画成一张地图（四格调用同一份数据、同一个变换）。"""

    def __init__(self, city: dict, stage: dict, pal: dict, w_px: int, h_px: int) -> None:
        self.city = city
        self.stage = stage
        self.pal = pal
        self.level = stage["level"]
        self.w, self.h = w_px, h_px
        cv = city["canvas"]
        cw = cv["w"] if isinstance(cv, dict) else cv[0]
        self.k = w_px / cw                          # 像素 / 城市单位
        self.img = Image.new("RGBA", (w_px, h_px), pal["map_bg"] + "FF")
        self.glow = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.g = ImageDraw.Draw(self.glow)
        self.fac = {f["no"]: f for f in city["facilities"]}
        self.zones = city["zones"]
        self.roads = city["roads"]
        self.cit = city["citizen"]
        self.built = self.level != "L1"             # 楼体是否成形
        self.flow = self.level in ("L3", "L4")      # 数据流
        self.sec = self.level == "L4"               # 安防
        self.badges = stage["badges"]
        self.ink = INK
        self.ink2 = INK2
        self.mut = MUT
        self.faint = FAINT
        self.accent = pal["accent"]
        self.orange = ORANGE
        # 颜色派生（随阶段变暖；纸面规划图用浅色分块 + 深墨轮廓）
        self.zone_fill = mix(pal["map_bg"], pal["zone"], 0.55)
        self.zone_line = mix(pal["accent"], pal["map_bg"], 0.55)
        self.street_casing = mix(pal["map_bg"], INK, 0.30)
        self.street_fill = mix(pal["map_bg"], PAPER, 0.62)
        self.street_center = mix(pal["map_bg"], INK, 0.55)
        self.pipe = mix(pal["map_bg"], INK, 0.74)
        self.build_fill = mix(pal["map_bg"], pal["zone"], 0.9)
        self.hatch = mix(self.build_fill, INK, 0.12)

    # -- 坐标换算
    def P(self, p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] * self.k, p[1] * self.k)

    def L(self, pts) -> list[tuple[float, float]]:
        return [self.P(p) for p in pts]

    def line(self, pts, fill, w, joint="curve") -> None:
        self.d.line(self.L(pts), fill=fill, width=max(1, int(round(w * self.k))),
                    joint=joint)

    def dashed(self, pts, fill, w, dash=8.0, gap=6.0) -> None:
        dashed_polyline(self.d, self.L(pts), fill, max(1, int(round(w * self.k))),
                        dash * self.k, gap * self.k)

    def rect(self, x, y, w, h, fill=None, outline=None, width=1.0) -> None:
        self.d.rectangle([x * self.k, y * self.k, (x + w) * self.k, (y + h) * self.k],
                         fill=fill, outline=outline,
                         width=max(1, int(round(width * self.k))))

    def rrect(self, x, y, w, h, radius, fill=None, outline=None, width=1.0) -> None:
        self.d.rounded_rectangle(
            [x * self.k, y * self.k, (x + w) * self.k, (y + h) * self.k],
            radius=radius * self.k, fill=fill, outline=outline,
            width=max(1, int(round(width * self.k))))

    def circle(self, cx, cy, r, fill=None, outline=None, width=1.0) -> None:
        self.d.ellipse([(cx - r) * self.k, (cy - r) * self.k,
                        (cx + r) * self.k, (cy + r) * self.k],
                       fill=fill, outline=outline,
                       width=max(1, int(round(width * self.k))))

    def arc(self, cx, cy, r, start, end, fill, width=1.0) -> None:
        self.d.arc([(cx - r) * self.k, (cy - r) * self.k,
                    (cx + r) * self.k, (cy + r) * self.k],
                   start=start, end=end, fill=fill,
                   width=max(1, int(round(width * self.k))))

    def glow_circle(self, cx, cy, r, color=ORANGE, alpha=64) -> None:
        self.g.ellipse([(cx - r) * self.k, (cy - r) * self.k,
                        (cx + r) * self.k, (cy + r) * self.k],
                       fill=ImageColorHelpers.rgb(color) + (alpha,))

    def text(self, xy, s, size, fill, weight="Regular", anchor="la") -> None:
        font = get_font(weight, max(8, int(round(size * self.k))))
        DRAWN_TEXTS.append(s)
        self.d.text((xy[0] * self.k, xy[1] * self.k), s, font=font, fill=fill, anchor=anchor)

    def measure(self, s, size, weight="Regular") -> float:
        return get_font(weight, max(8, int(round(size * self.k)))).getlength(s) / self.k

    def wrap(self, s, size, max_city_w, weight="Regular") -> list[str]:
        font = get_font(weight, max(8, int(round(size * self.k))))
        return wrap_text(s, font, max_city_w * self.k)

    # -- 设施 / 道路几何
    def R(self, no: str) -> tuple[float, float, float, float]:
        f = self.fac[no]
        p, s = f["position"], f["size"]
        return (p["x"], p["y"], s["w"], s["h"])

    def center(self, ref: str) -> tuple[float, float]:
        if ref == "citizen":
            p, s = self.cit["position"], self.cit["size"]
            return (p["x"] + s["w"] / 2, p["y"] + s["h"] / 2)
        if ref == "P8":
            fp = self.fac["P8"]["flow_path"]
            return ((fp[0][0] + fp[1][0]) / 2, (fp[0][1] + fp[1][1]) / 2)
        x, y, w, h = self.R(ref)
        return (x + w / 2, y + h / 2)

    def ref_rect(self, ref: str) -> tuple[float, float, float, float]:
        if ref == "citizen":
            p, s = self.cit["position"], self.cit["size"]
            return (p["x"], p["y"], s["w"], s["h"])
        if ref == "P8":
            fp = self.fac["P8"]["flow_path"]
            return (min(fp[0][0], fp[1][0]), fp[0][1] - 13,
                    abs(fp[1][0] - fp[0][0]), 26)
        return self.R(ref)

    def edge_toward(self, ref: str, target: tuple[float, float]) -> tuple[float, float]:
        x, y, w, h = self.ref_rect(ref)
        cx, cy = x + w / 2, y + h / 2
        dx, dy = target[0] - cx, target[1] - cy
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return (cx, cy)
        tx = (w / 2) / abs(dx) if abs(dx) > 1e-6 else 1e9
        ty = (h / 2) / abs(dy) if abs(dy) > 1e-6 else 1e9
        t = min(tx, ty)
        return (cx + dx * t, cy + dy * t)

    def road_path(self, road: dict) -> list[tuple[float, float]]:
        via = [tuple(v) for v in road.get("via", [])]
        fr, to = road["from"], road["to"]
        if fr == "P8":
            fp = self.fac["P8"]["flow_path"]
            nxt = via[0] if via else self.center(to)
            start = tuple(fp[0] if math.dist(fp[0], nxt) <= math.dist(fp[1], nxt) else fp[1])
        else:
            start = self.edge_toward(fr, via[0] if via else self.center(to))
        if to == "P8":
            fp = self.fac["P8"]["flow_path"]
            prv = via[-1] if via else self.center(fr)
            end = tuple(fp[0] if math.dist(fp[0], prv) <= math.dist(fp[1], prv) else fp[1])
        else:
            end = self.edge_toward(to, via[-1] if via else self.center(fr))
        return [start] + via + [end]

    # ------------------------------------------------------------ 绘制入口
    def draw(self) -> Image.Image:
        self.draw_grid()
        self.draw_zones()
        self.draw_ground()
        if not self.built:
            self.draw_planned_roads()
            self.draw_shells()
            self.draw_site_life()
            self.draw_belt()
            self.draw_citizen()
        else:
            self.draw_plaza()
            self.draw_roads()
            self.draw_pipes()
            self.draw_furniture()
            self.draw_buildings()
            self.draw_belt()
            self.draw_citizen()
            self.draw_remnant_fence()
            self.draw_streetlights()
            if self.flow:
                self.draw_flow()
            if self.level in ("L3", "L4"):
                self.draw_brain()
                self.draw_monitors()
            if self.sec:
                self.draw_security()
        self.draw_badge_glow()
        self.img = Image.alpha_composite(self.img, self.glow)
        self.d = ImageDraw.Draw(self.img)
        self.draw_labels()
        self.draw_badges()
        return self.img.convert("RGB")

    # ------------------------------------------------------------ 底图
    def draw_grid(self) -> None:
        color = mix(self.pal["map_bg"], INK, 0.05)
        for x in range(0, 1601, 50):
            self.line([(x, 0), (x, 1000)], color, 0.7)
        for y in range(0, 1001, 50):
            self.line([(0, y), (1600, y)], color, 0.7)

    def draw_zones(self) -> None:
        for z in self.zones:
            r = z["rect"]
            self.rect(r["x"], r["y"], r["w"], r["h"], fill=self.zone_fill)
            self.dash_rect(r, self.zone_line, 2.2, 14, 10)
            name = z["name"]
            layer = z.get("layer", "")
            col = mix(self.accent, INK, 0.35)
            self.text((r["x"] + 14, r["y"] + 8), name, 34, col, "Bold")
            self.text((r["x"] + 14 + self.measure(name, 34, "Bold") + 9, r["y"] + 15),
                      layer, 18, self.mut, "Medium")

    def dash_rect(self, r, color, w, dash, gap) -> None:
        if isinstance(r, dict):
            x, y, ww, hh = r["x"], r["y"], r["w"], r["h"]
        else:
            x, y, ww, hh = r
        self.dashed([(x, y), (x + ww, y)], color, w, dash, gap)
        self.dashed([(x + ww, y), (x + ww, y + hh)], color, w, dash, gap)
        self.dashed([(x + ww, y + hh), (x, y + hh)], color, w, dash, gap)
        self.dashed([(x, y + hh), (x, y)], color, w, dash, gap)

    def draw_ground(self) -> None:
        rng = random.Random(44)
        if not self.built:
            for _ in range(320):
                x = rng.uniform(16, 1584)
                y = rng.uniform(16, 984)
                ln = rng.uniform(5, 12)
                ang = rng.uniform(-0.5, 0.5)
                col = mix(self.pal["map_bg"], INK, rng.choice([0.14, 0.20, 0.26]))
                self.line([(x, y), (x + ln * math.cos(ang), y + ln * math.sin(ang))],
                          col, rng.choice([0.9, 1.2, 1.5]))
        else:
            col = mix(self.pal["map_bg"], INK, 0.06)
            for y in range(140, 960, 66):
                self.dashed([(30, y), (1570, y)], col, 0.8, 18, 14)
            for x in range(40, 1580, 88):
                self.dashed([(x, 120), (x, 960)], col, 0.8, 14, 18)

    def draw_planned_roads(self) -> None:
        for road in self.roads:
            self.dashed(self.road_path(road), self.faint, 9, 20, 14)
        self.text((620, 888), "规划路网（未建）", 28, mix(self.pal["map_bg"], INK, 0.45), "Medium")

    def draw_plaza(self) -> None:
        x, y, w, h = 1198, 548, 360, 232
        self.rect(x, y, w, h, fill=mix(self.pal["map_bg"], PAPER, 0.55))
        col = mix(self.pal["map_bg"], INK, 0.08)
        for gx in range(x, x + w + 1, 40):
            self.line([(gx, y), (gx, y + h)], col, 1.0)
        for gy in range(y, y + h + 1, 40):
            self.line([(x, gy), (x + w, gy)], col, 1.0)
        self.dash_rect((x, y, w, h), self.zone_line, 1.6, 10, 8)
        for by in (640, 672):
            self.rect(1224, by, 76, 12, fill=mix(self.pal["map_bg"], self.pal["accent"], 0.16),
                      outline=self.ink2, width=1.4)
        self.text((x + 12, y + h - 26), "站前广场", 22, self.mut, "Medium")

    def draw_roads(self) -> None:
        for road in self.roads:
            if road.get("flow") == "utility":
                continue
            path = self.road_path(road)
            self.line(path, self.street_casing, 34)
            self.line(path, self.street_fill, 26)
            self.dashed(path, self.street_center, 1.4, 14, 12)
        # 斑马线：城门 / 仓库路口 / 服务中心路口
        self.crosswalk(1488, 560, vertical=True)
        self.crosswalk(560, 614, vertical=False)
        self.crosswalk(420, 336, vertical=True)

    def crosswalk(self, cx, cy, vertical: bool) -> None:
        col = mix(self.street_fill, PAPER, 0.85)
        if vertical:                     # 路沿 y 方向：横条
            for i in range(4):
                yy = cy + i * 7
                self.line([(cx - 14, yy), (cx + 14, yy)], col, 3.4)
        else:
            for i in range(4):
                xx = cx + i * 7
                self.line([(xx, cy - 14), (xx, cy + 14)], col, 3.4)

    def draw_pipes(self) -> None:
        util = [r for r in self.roads if r.get("flow") == "utility"]
        for road in util:
            path = self.road_path(road)
            self.line(path, self.pipe, 16)
            self.dashed(path, self.pal["map_bg"], 6, 20, 13)
            for p in (path[0], path[-1], *path[1:-1]):
                self.circle(p[0], p[1], 9.5, fill=self.pal["map_bg"], outline=self.pipe, width=3.2)
            for frac in (0.3, 0.66):
                x, y, ang = point_at(path, frac)
                arrow_head(self.d, self.P((x + 12 * math.cos(ang), y + 12 * math.sin(ang))),
                           ang, 9 * self.k, self.pipe)
        # 管网再补两段：仓库 → 服务中心、服务中心 → 门户
        for path in ([(416, 470), (452, 470)], [(1140, 392), (1180, 392)]):
            self.line(path, self.pipe, 13)
            self.dashed(path, self.pal["map_bg"], 5, 14, 10)
            for p in (path[0], path[-1]):
                self.circle(p[0], p[1], 8, fill=self.pal["map_bg"], outline=self.pipe, width=2.6)
        # 阀门 / 表井
        for (vx, vy) in ((40, 282), (420, 240), (420, 330), (120, 208)):
            self.rect(vx - 5, vy - 5, 10, 10, fill=self.pal["map_bg"], outline=self.pipe, width=2)
        self.text((48, 296), "水管", 20, self.mut, "Medium")
        self.text((428, 296), "电缆", 20, self.mut, "Medium")

    def draw_furniture(self) -> None:
        # 服务区停车位 + 两辆车
        px0, py0 = 540, 786
        for i in range(4):
            self.rect(px0 + i * 44, py0, 40, 58, outline=mix(self.pal["map_bg"], INK, 0.30),
                      width=1.4)
        self.rect(px0 + 5, py0 + 8, 30, 42, fill=mix(self.pal["map_bg"], INK, 0.30),
                  outline=self.ink2, width=1.2)
        self.rect(px0 + 49, py0 + 8, 30, 42, fill=mix(self.pal["map_bg"], INK, 0.52),
                  outline=self.ink2, width=1.2)
        self.text((px0, py0 + 63), "停车位", 18, self.mut, "Medium")
        # 仓储区装卸位 + 一辆货车
        self.rect(250, 786, 150, 64, fill=mix(self.pal["map_bg"], PAPER, 0.4),
                  outline=mix(self.pal["map_bg"], INK, 0.30), width=1.4)
        self.rect(272, 806, 52, 26, fill=mix(self.pal["map_bg"], INK, 0.45),
                  outline=self.ink2, width=1.6)
        self.rect(324, 810, 26, 22, fill=mix(self.pal["map_bg"], INK, 0.22),
                  outline=self.ink2, width=1.6)
        self.circle(286, 834, 6, fill=self.ink)
        self.circle(340, 834, 6, fill=self.ink)
        self.text((250, 858), "装卸位", 18, self.mut, "Medium")

    # ------------------------------------------------------------ 楼体（壳 / 成形）
    def draw_shells(self) -> None:
        for no in ("P1", "P3", "P9"):
            r = self.R(no)
            self.dash_rect(r, mix(self.pal["map_bg"], INK, 0.55), 4.0, 22, 12)
            for (bx, by) in [(r[0] + 12, r[1] + 12), (r[0] + r[2] - 12, r[1] + 12),
                             (r[0] + 12, r[1] + r[3] - 12), (r[0] + r[2] - 12, r[1] + r[3] - 12)]:
                self.rect(bx - 6, by - 6, 12, 12, fill=mix(self.pal["map_bg"], INK, 0.50))
            self.line([(r[0] + 10, r[1] + r[3] / 2), (r[0] + 70, r[1] + r[3] / 2)],
                      mix(self.pal["map_bg"], INK, 0.42), 4)
            self.line([(r[0] + r[2] / 2, r[1] + 10), (r[0] + r[2] / 2, r[1] + 64)],
                      mix(self.pal["map_bg"], INK, 0.42), 4)
            # 模板支撑小刻线
            col = mix(self.pal["map_bg"], INK, 0.30)
            for t in range(int(r[0] + 30), int(r[0] + r[2] - 20), 46):
                self.line([(t, r[1] - 7), (t, r[1] + 7)], col, 1.6)
                self.line([(t, r[1] + r[3] - 7), (t, r[1] + r[3] + 7)], col, 1.6)
        for no in ("P2", "P4", "P5", "P6", "P7"):
            r = self.R(no)
            self.dash_rect(r, mix(self.pal["map_bg"], INK, 0.38), 2.2, 14, 10)
        # 测量桩
        for (sx, sy) in ((432, 160), (1160, 160), (36, 920), (432, 920), (1160, 920)):
            self.circle(sx, sy, 6, fill=None, outline=mix(self.pal["map_bg"], INK, 0.45), width=1.8)
            self.line([(sx - 9, sy), (sx + 9, sy)], mix(self.pal["map_bg"], INK, 0.35), 1.4)
            self.line([(sx, sy - 9), (sx, sy + 9)], mix(self.pal["map_bg"], INK, 0.35), 1.4)
        self.text((66, 380), "仓库（壳）", 26, self.ink2, "Bold")
        self.text((470, 176), "服务中心（壳）", 26, self.ink2, "Bold")
        self.text((1196, 312), "门户（壳）", 24, self.ink2, "Bold")
        self.text((70, 244), "场地（三通一平）", 20, self.mut, "Medium")

    def draw_buildings(self) -> None:
        fill = self.build_fill
        # ---- P0 场地：泵房 / 配电 / 水表电表
        r = self.R("P0")
        self.rect(r[0], r[1], r[2], r[3], fill=fill, outline=mix(self.pal["map_bg"], INK, 0.42), width=2.2)
        self.rect(78, 176, 64, 46, fill=mix(fill, self.pal["accent"], 0.18),
                  outline=self.ink2, width=2)
        self.text((84, 184), "泵房", 20, self.ink2, "Bold")
        self.rect(250, 176, 46, 40, fill=mix(fill, self.pal["accent"], 0.12),
                  outline=self.ink2, width=2)
        self.line([(262, 206), (270, 206), (266, 196), (274, 196), (270, 186), (278, 186)],
                  self.ink, 2.2)
        for mx in (150, 190):
            self.rect(mx, 226, 26, 16, fill=self.pal["map_bg"], outline=self.ink2, width=1.8)
        self.line([(96, 222), (96, 340)], self.pipe, 8)
        self.line([(273, 216), (420, 216)], self.pipe, 8)
        self.text((256, 180), "配电", 16, self.ink2, "Medium")
        self.text((148, 246), "水表 / 电表", 18, self.mut, "Medium")
        # 水塔
        self.circle(172, 186, 14, fill=mix(fill, self.pal["accent"], 0.10),
                    outline=self.ink2, width=2.2)
        self.line([(172, 174), (172, 198)], self.ink2, 1.6)
        self.line([(160, 186), (184, 186)], self.ink2, 1.6)
        self.text((152, 204), "水塔", 16, self.mut, "Medium")
        # 阀门表井
        for (vx, vy) in ((40, 270), (420, 300)):
            self.circle(vx, vy, 6.5, fill=self.pal["map_bg"], outline=self.pipe, width=2.2)
            self.line([(vx - 4, vy), (vx + 4, vy)], self.pipe, 1.8)
            self.line([(vx, vy - 4), (vx, vy + 4)], self.pipe, 1.8)

        # ---- P1 仓库
        x, y, w, h = self.R("P1")
        self.rect(x, y, w, h, fill=fill, outline=self.ink, width=4.5)
        self.rect(x + 9, y + 9, w - 18, h - 18, outline=mix(self.pal["map_bg"], INK, 0.45), width=1.8)
        # 天窗 + 楼梯间
        for sx in (x + 40, x + 120, x + 200):
            self.rect(sx, y + 26, 44, 20, fill=self.pal["map_bg"],
                      outline=mix(self.pal["map_bg"], INK, 0.45), width=1.6)
            self.line([(sx + 22, y + 26), (sx + 22, y + 46)], mix(self.pal["map_bg"], INK, 0.35), 1.2)
        self.rect(x + w - 84, y + 24, 34, 26, fill=mix(fill, self.pal["accent"], 0.10),
                  outline=self.ink2, width=1.8)
        for dy in (y + 100, y + 210, y + 320):     # 卸货口
            self.rect(x + w - 16, dy, 16, 34, fill=mix(fill, self.pal["accent"], 0.25),
                      outline=self.ink2, width=1.8)
        # ---- P2 货架（5 排）
        sx, sy, sw, sh = self.R("P2")
        for i in range(5):
            ry = sy + 16 + i * 46
            self.rect(sx + 18, ry, sw - 36, 24, fill=mix(fill, self.pal["accent"], 0.14),
                      outline=self.ink2, width=2)
            for d in range(1, 5):
                dx = sx + 18 + d * (sw - 36) / 5
                self.line([(dx, ry + 1), (dx, ry + 23)], self.ink2, 1.4)
            rows_filled = 3 if self.level == "L2" else 5
            if i < rows_filled:
                for c in range(5):
                    cxp = sx + 18 + (c + 0.5) * (sw - 36) / 5
                    self.circle(cxp, ry + 12, 3.2,
                                fill=self.ink2 if not self.flow else mix(self.ink2, self.accent, 0.5))
        self.text((sx + 18, sy + sh - 22), "库表 · 5 排货架 / 115 行", 19, self.ink2, "Medium")

        # ---- P3 服务中心
        x, y, w, h = self.R("P3")
        self.rect(x, y, w, h, fill=fill, outline=self.ink, width=4.5)
        self.rect(x + 10, y + 10, w - 20, h - 20, outline=mix(self.pal["map_bg"], INK, 0.45), width=1.8)
        # 屋顶设备
        self.rect(700, 196, 34, 22, fill=self.pal["map_bg"], outline=self.ink2, width=1.6)
        self.rect(760, 200, 26, 18, fill=self.pal["map_bg"], outline=self.ink2, width=1.6)
        self.rect(880, 196, 30, 24, fill=mix(fill, self.pal["accent"], 0.10),
                  outline=self.ink2, width=1.6)
        # 走廊
        self.rect(468, 388, 660, 18, fill=mix(fill, self.pal["accent"], 0.10),
                  outline=mix(self.pal["map_bg"], INK, 0.35), width=1.6)
        self.dashed([(474, 397), (1122, 397)], self.street_center, 1.6, 12, 10)
        # 房间
        self.rect(468, 262, 300, 122, fill=fill, outline=self.ink2, width=2.4)
        self.rect(824, 262, 300, 122, fill=fill, outline=self.ink2, width=2.4)
        self.rect(468, 412, 300, 122, fill=fill, outline=self.ink2, width=2.4)
        self.rect(824, 412, 300, 122, fill=fill, outline=self.ink2, width=2.4)
        # P5 前台：柜台 + 座椅
        self.rect(492, 330, 196, 24, fill=mix(fill, self.pal["accent"], 0.22),
                  outline=self.ink2, width=2)
        for cxp in (530, 590, 650):
            self.circle(cxp, 368, 8, fill=self.pal["map_bg"], outline=self.ink2, width=2)
        # P4 窗口：柜台 + 右墙开窗
        self.rect(864, 330, 170, 22, fill=mix(fill, self.pal["accent"], 0.22),
                  outline=self.ink2, width=2)
        self.rect(1114, 316, 18, 48, fill=self.pal["map_bg"])
        self.line([(1118, 316), (1118, 364)], self.ink2, 2)
        self.line([(1126, 316), (1126, 364)], self.ink2, 2)
        # P6 规则室：桌 + 文件
        self.rect(492, 476, 150, 22, fill=mix(fill, self.pal["accent"], 0.22),
                  outline=self.ink2, width=2)
        for i in range(3):
            self.line([(500, 512 + i * 7), (620, 512 + i * 7)], self.ink2, 1.6)
        # P7 取货通道
        self.line([(844, 470), (1100, 470)], self.ink, 3)
        arrow_head(self.d, self.P((1110, 470)), 0.0, 10 * self.k, self.ink)

        # ---- P9 门户
        x, y, w, h = self.R("P9")
        self.rect(x, y, w, h, fill=fill, outline=self.ink, width=4.5)
        self.rect(x + 9, y + 9, w - 18, 40, fill=mix(fill, self.pal["accent"], 0.12),
                  outline=self.ink2, width=1.8)
        gx = x + w - 152
        gy = y + h - 32
        for pxx in (gx, gx + 116):
            self.rect(pxx, gy, 16, 32, fill=self.ink)
        self.rect(gx, gy - 26, 132, 26, fill=mix(fill, self.pal["accent"], 0.22),
                  outline=self.ink, width=3)
        self.rect(gx + 74, gy + 5, 40, 27, fill=self.pal["map_bg"])   # 门洞


    # ------------------------------------------------------------ 传送带 / 市民 / 工地
    def draw_belt(self) -> None:
        fp = self.fac["P8"]["flow_path"]
        x1, y1 = fp[0]
        x2, y2 = fp[1]
        if not self.built:
            self.dashed([(x1, y1), (x2, y2)], self.faint, 5, 18, 12)
            self.text((1050, 552), "传送带（规划）", 22, self.mut, "Medium")
            return
        self.line([(x1, y1 - 13), (x2, y1 - 13)], self.ink, 3.4)
        self.line([(x1, y1 + 13), (x2, y1 + 13)], self.ink, 3.4)
        for x in range(int(x1), int(x2), 30):
            self.line([(x, y1 - 13), (x, y1 + 13)], self.ink2, 2)
        for frac in (0.22, 0.5, 0.78):
            x, _, ang = point_at([(x1, y1), (x2, y1)], frac)
            arrow_head(self.d, self.P((x + 14, y1)), ang, 9 * self.k, self.ink2)
        if self.flow:
            for frac in (0.18, 0.42, 0.66, 0.9):
                x, _, _ = point_at([(x1, y1), (x2, y1)], frac)
                self.glow_circle(x, y1, 10, ORANGE, 120)
                self.rrect(x - 5, y1 - 4, 10, 8, 1.5, fill=ORANGE_L)
        self.text((1188, 544), "传送带 · SSE", 22, self.ink2, "Bold")

    def draw_citizen(self) -> None:
        p, s = self.cit["position"], self.cit["size"]
        cx = p["x"] + s["w"] / 2
        cy = p["y"] + 40
        col = self.ink2 if self.built else mix(self.pal["map_bg"], INK, 0.5)
        self.circle(cx, cy, 15, fill=None, outline=col, width=2.6)
        self.line([(cx, cy + 16), (cx, cy + 40)], col, 2.4)
        self.line([(cx - 15, cy + 28), (cx + 15, cy + 28)], col, 2.4)
        self.text((cx, p["y"] + s["h"] - 14), "市民 / 用户", 22, self.ink2, "Medium", anchor="ma")
        if not self.built:
            self.text((cx + 26, cy - 30), "？", 40, self.mut, "Bold")
        else:
            self.rrect(cx + 24, cy - 40, 56, 26, 8, fill=self.pal["map_bg"],
                       outline=self.ink2, width=1.8)
            self.text((cx + 52, cy - 27), "问一句", 19, self.ink2, "Medium", anchor="mm")

    def draw_site_life(self) -> None:
        # 施工围挡：整片场地一圈
        self.dashed([(16, 18), (1584, 18), (1584, 982), (16, 982), (16, 18)],
                    mix(self.pal["map_bg"], INK, 0.42), 5.5, 26, 14)
        for i in range(24, 1584, 42):
            self.line([(i, 18), (i, 34)], mix(self.pal["map_bg"], INK, 0.32), 3)
            self.line([(i, 966), (i, 982)], mix(self.pal["map_bg"], INK, 0.32), 3)
        self.text((30, 42), "施工围挡 · 场地平整", 24, mix(self.pal["map_bg"], INK, 0.5), "Bold")
        # 工棚
        self.rect(232, 186, 62, 36, fill=mix(self.pal["map_bg"], INK, 0.10),
                  outline=mix(self.pal["map_bg"], INK, 0.42), width=2)
        for i in range(6):
            self.line([(234 + i * 10, 186), (234 + i * 10, 222)],
                      mix(self.pal["map_bg"], INK, 0.22), 1.4)
        self.text((232, 164), "工棚", 20, self.mut, "Medium")
        # 塔吊：底座 + 大臂 + 平衡臂 + 吊钩
        bx, by = 392, 300
        self.circle(bx, by, 11, fill=None, outline=self.ink2, width=2.6)
        self.line([(bx - 10, by - 10), (bx + 10, by + 10)], self.ink2, 2)
        self.line([(bx + 10, by - 10), (bx - 10, by + 10)], self.ink2, 2)
        self.line([(bx, by), (bx - 150, by - 96)], self.ink2, 3.4)
        self.line([(bx, by), (bx + 54, by + 34)], self.ink2, 3.4)
        self.line([(bx - 150, by - 96), (bx - 150, by - 62)], self.ink2, 2)
        self.circle(bx - 150, by - 56, 6, fill=None, outline=self.ink2, width=2)
        self.text((330, 322), "塔吊", 20, self.mut, "Medium")
        # 材料堆
        for (mx, my, mw) in [(456, 226, 34), (502, 234, 24), (546, 222, 28)]:
            self.rect(mx, my, mw, 16, fill=mix(self.pal["map_bg"], INK, 0.18),
                      outline=mix(self.pal["map_bg"], INK, 0.35), width=1.6)
        self.text((456, 246), "材料堆", 18, self.mut, "Medium")
        # 基坑（点线 + 斜撑）
        self.dash_rect((700, 700, 210, 92), mix(self.pal["map_bg"], INK, 0.35), 2, 12, 9)
        for i in range(7):
            self.line([(700 + i * 34, 792), (734 + i * 34, 700)],
                      mix(self.pal["map_bg"], INK, 0.16), 1.5)
        self.text((706, 680), "基坑（待验）", 18, self.mut, "Medium")
        # 材料场
        self.rect(250, 796, 160, 82, outline=mix(self.pal["map_bg"], INK, 0.32), width=1.8)
        for i in range(3):
            for j in range(2):
                self.rect(262 + i * 44, 808 + j * 34, 30, 24,
                          fill=mix(self.pal["map_bg"], INK, 0.14),
                          outline=mix(self.pal["map_bg"], INK, 0.32), width=1.4)
        self.text((250, 882), "材料场", 18, self.mut, "Medium")
        # 项目部板房
        self.rect(1240, 700, 92, 40, fill=mix(self.pal["map_bg"], INK, 0.08),
                  outline=mix(self.pal["map_bg"], INK, 0.42), width=2)
        self.text((1240, 680), "项目部", 18, self.mut, "Medium")
        # 工地大门
        for gx in (1446, 1522):
            self.rect(gx, 958, 10, 24, fill=mix(self.pal["map_bg"], INK, 0.45))
        self.dashed([(1456, 968), (1522, 968)], mix(self.pal["map_bg"], INK, 0.35), 3, 8, 6)
        self.text((1436, 932), "工地大门", 18, self.mut, "Medium")

    def draw_remnant_fence(self) -> None:
        if self.level != "L2":
            return
        self.dashed([(56, 266), (196, 266)], mix(self.pal["map_bg"], INK, 0.35), 3, 10, 7)
        for px in (56, 196):
            self.line([(px, 258), (px, 276)], self.ink2, 2)
        self.text((200, 258), "围挡收尾", 18, self.mut, "Medium")

    # ------------------------------------------------------------ 智慧城市层
    def draw_streetlights(self) -> None:
        lit = self.level in ("L3", "L4")
        roads = [r for r in self.roads
                 if r.get("key") in ("citizen-to-gate", "gate-to-window",
                                     "pickup-to-warehouse", "belt-to-gate")]
        for ri, road in enumerate(roads):
            path = self.road_path(road)
            for j, frac in enumerate((0.2, 0.5, 0.8)):
                x, y, ang = point_at(path, frac)
                side = 1 if (j + ri) % 2 == 0 else -1
                lx = x + side * 24 * math.cos(ang + math.pi / 2)
                ly = y + side * 24 * math.sin(ang + math.pi / 2)
                if lit:
                    self.glow_circle(lx, ly, 22, ORANGE, 62)
                self.circle(lx, ly, 3.4, fill=self.ink2)
                self.circle(lx, ly, 2.2, fill=ORANGE_L if lit else self.mut)

    def draw_flow(self) -> None:
        req = [r for r in self.roads if r.get("flow") == "request"]
        resp = [r for r in self.roads if r.get("flow") == "response"]
        muted = self.level == "L4"
        col = mix(ORANGE, self.pal["map_bg"], 0.30) if muted else ORANGE
        for group, dash, gap, w in ((req, 22, 12, 4.4), (resp, 6, 9, 4.0)):
            for road in group:
                path = self.road_path(road)
                self.dashed(path, col, w, dash, gap)
                for frac in (0.35, 0.68):
                    x, y, ang = point_at(path, frac)
                    arrow_head(self.d, self.P((x, y)), ang, 11 * self.k, col)
                for frac in (0.18, 0.5, 0.82):
                    x, y, _ = point_at(path, frac)
                    self.glow_circle(x, y, 9, ORANGE, 110 if not muted else 70)
                    self.circle(x, y, 2.6,
                                fill=ORANGE_L if not muted else mix(ORANGE, self.pal["map_bg"], 0.4))
        self.text((600, 720), "数据流（请求 → 结果）", 22, col, "Medium")

    def draw_brain(self) -> None:
        cx, cy = 1010, 218
        self.circle(cx, cy, 40, fill=mix(self.pal["map_bg"], self.pal["accent"], 0.22),
                    outline=self.ink, width=3.2)
        self.circle(cx, cy, 20, fill=None, outline=self.ink2, width=2)
        for r in (52, 64, 76):
            for a0, a1 in ((200, 236), (246, 282), (292, 328)):
                self.arc(cx, cy, r, a0, a1, ORANGE, 2.2)
        self.glow_circle(cx, cy, 56, ORANGE, 44)
        self.line([(cx, cy - 40), (cx, cy - 60)], self.ink, 2.4)
        self.circle(cx, cy - 64, 4, fill=ORANGE)
        self.text((956, cy), "城市大脑 / 指挥中心", 22, self.ink2, "Bold", anchor="rm")

    def draw_monitors(self) -> None:
        # 窗口监控屏（P4）
        self.rect(1044, 270, 50, 28, fill=mix(self.pal["map_bg"], self.ink2, 0.82),
                  outline=self.ink, width=1.8)
        for i in range(3):
            self.line([(1048, 276 + i * 7), (1090, 276 + i * 7)], ORANGE_L, 1.4)
        self.text((1044, 300), "监控屏", 18, self.mut, "Medium")
        # 门户信息屏
        self.rect(1448, 450, 100, 22, fill=mix(self.pal["map_bg"], self.ink2, 0.82),
                  outline=self.ink, width=1.8)
        for i in range(2):
            self.line([(1454, 458 + i * 7), (1542, 458 + i * 7)], ORANGE_L, 1.4)
        self.text((1448, 432), "信息屏", 18, self.mut, "Medium")

    # ------------------------------------------------------------ 安防层
    def draw_security(self) -> None:
        for (x, y, w, h) in (self.R("P1"), self.R("P3"), self.R("P9")):
            for (cx0, cy0, sx, sy) in ((x - 6, y - 6, 1, 1), (x + w + 6, y - 6, -1, 1),
                                       (x - 6, y + h + 6, 1, -1), (x + w + 6, y + h + 6, -1, -1)):
                self.line([(cx0, cy0), (cx0 + sx * 26, cy0)], ORANGE, 4)
                self.line([(cx0, cy0), (cx0, cy0 + sy * 26)], ORANGE, 4)
        # 城门检查站
        self.rect(1398, 538, 44, 30, fill=mix(self.pal["map_bg"], self.pal["accent"], 0.2),
                  outline=self.ink, width=2.4)
        self.line([(1442, 552), (1526, 552)], ORANGE, 5)
        for i in range(4):
            self.line([(1442 + i * 21, 546), (1442 + i * 21, 558)], self.ink, 2)
        self.text((1382, 576), "检查站", 22, self.ink2, "Bold")
        # 仓库门禁
        self.rect(496, 592, 10, 10, fill=ORANGE)
        self.line([(480, 614), (530, 614)], ORANGE, 5)
        for i in range(3):
            self.line([(484 + i * 16, 608), (484 + i * 16, 620)], self.ink, 2)
        self.text((470, 640), "门禁", 22, self.ink2, "Bold")
        # 服务中心门禁
        self.rect(442, 350, 10, 10, fill=ORANGE)
        self.text((424, 366), "门禁", 16, self.ink2, "Bold")
        # 摄像头 + 视线锥
        for (cx, cy, ang) in [(408, 300, 2.6), (1158, 318, 3.0), (1004, 538, 0.4),
                              (960, 850, 1.2), (1490, 300, 1.7), (712, 618, 0.2)]:
            self.circle(cx, cy, 4, fill=self.ink)
            self.line([(cx, cy), (cx + 20 * math.cos(ang), cy + 20 * math.sin(ang))], self.ink, 2.2)
            ex = cx + 20 * math.cos(ang)
            ey = cy + 20 * math.sin(ang)
            self.rect(ex - 4, ey - 4, 8, 8, fill=self.ink)
            self.circle(ex + 3 * math.cos(ang), ey + 3 * math.sin(ang), 2.2, fill=ORANGE)
            cone = mix(ORANGE, self.pal["map_bg"], 0.1)
            self.dashed([(ex, ey), (ex + 46 * math.cos(ang - 0.5), ey + 46 * math.sin(ang - 0.5))],
                        cone, 1.8, 6, 5)
            self.dashed([(ex, ey), (ex + 46 * math.cos(ang + 0.5), ey + 46 * math.sin(ang + 0.5))],
                        cone, 1.8, 6, 5)
            self.dashed([(ex + 46 * math.cos(ang - 0.5), ey + 46 * math.sin(ang - 0.5)),
                         (ex + 46 * math.cos(ang + 0.5), ey + 46 * math.sin(ang + 0.5))],
                        cone, 1.8, 6, 5)
        # 城管岗亭
        self.rect(980, 690, 64, 46, fill=mix(self.pal["map_bg"], self.pal["accent"], 0.18),
                  outline=self.ink, width=2.4)
        self.line([(984, 700), (1040, 700)], ORANGE, 4)
        self.text((980, 742), "城管岗亭", 22, self.ink2, "Bold")
        # 应急中心
        self.rect(56, 790, 150, 76, fill=mix(self.pal["map_bg"], self.pal["accent"], 0.16),
                  outline=self.ink, width=3)
        self.line([(96, 812), (126, 812)], ORANGE, 6)
        self.line([(111, 797), (111, 827)], ORANGE, 6)
        self.text((56, 872), "应急中心", 24, self.ink2, "Bold")
        # 监控大屏（P9）
        self.rect(1200, 404, 116, 50, fill=mix(self.pal["map_bg"], self.ink2, 0.86),
                  outline=self.ink, width=2.2)
        for i in range(2):
            for j in range(2):
                self.rect(1206 + i * 54, 409 + j * 22, 48, 18,
                          fill=mix(self.ink2, ORANGE, 0.55) if (i + j) % 2 == 0
                          else mix(self.ink2, self.pal["map_bg"], 0.2))
        self.text((1200, 458), "监控大屏", 20, self.ink2, "Bold")
        # 巡查车
        self.rect(1540, 600, 34, 16, fill=mix(self.pal["map_bg"], ORANGE, 0.55),
                  outline=self.ink, width=1.8)
        self.circle(1548, 618, 4, fill=self.ink)
        self.circle(1566, 618, 4, fill=self.ink)

    # ------------------------------------------------------------ 徽章
    def badge_points(self) -> dict[int, tuple[float, float]]:
        pts = {}
        for no, (ref, rx, ry) in BADGE_REL.items():
            if ref == "P8":
                fp = self.fac["P8"]["flow_path"]
                x = fp[0][0] + (fp[1][0] - fp[0][0]) * rx
                y = fp[0][1] + ry * 34
                pts[no] = (x, y)
            else:
                x, y, w, h = self.R(ref)
                pts[no] = (x + w * rx, y + h * ry)
        return pts

    def draw_badge_glow(self) -> None:
        new = set(self.badges["new"])
        for no, (x, y) in self.badge_points().items():
            if no in new:
                self.glow_circle(x, y, 64, ORANGE, 52)
                self.glow_circle(x, y, 46, ORANGE, 74)

    def draw_badges(self) -> None:
        lit = set(self.badges["cumulative"])
        new = set(self.badges["new"])
        rew = set(self.badges["rewired"])
        r = 30
        for no, (x, y) in self.badge_points().items():
            if no not in lit:
                for k in range(8):
                    a0 = k * 45 + 5
                    self.d.arc([(x - r) * self.k, (y - r) * self.k,
                                (x + r) * self.k, (y + r) * self.k],
                               start=a0, end=a0 + 33,
                               fill=mix(self.pal["map_bg"], INK, 0.52),
                               width=max(1, int(round(3.2 * self.k))))
                self.text((x, y), str(no), 28, mix(self.pal["map_bg"], INK, 0.55), "Bold", anchor="mm")
                continue
            color = ORANGE if no in new else mix(self.pal["map_bg"], INK, 0.88)
            self.circle(x, y, r, fill=color, outline=mix(color, PAPER, 0.35), width=1.6)
            if no in rew:
                for a0 in (0, 120, 240):
                    self.d.arc([(x - r - 6) * self.k, (y - r - 6) * self.k,
                                (x + r + 6) * self.k, (y + r + 6) * self.k],
                               start=a0, end=a0 + 96, fill=ORANGE,
                               width=max(1, int(round(3.0 * self.k))))
            self.text((x, y), str(no), 28, PAPER, "Bold", anchor="mm")

    # ------------------------------------------------------------ 文字标注
    def draw_labels(self) -> None:
        if not self.built:
            return
        self.text((66, 412), "数据仓库大楼", 26, self.ink2, "Bold")
        self.text((470, 172), "查询服务中心", 28, self.ink2, "Bold")
        self.text((1196, 312), "城市门户 · :8081", 24, self.ink2, "Bold")
        # 房间名（图画上只留最短的）
        self.text((480, 272), "前台", 20, self.ink2, "Bold")
        self.text((836, 272), "窗口", 20, self.ink2, "Bold")
        self.text((480, 422), "规则室 · 契约", 20, self.ink2, "Bold")
        self.text((836, 422), "取货 · pymysql", 19, self.ink2, "Bold")


# ---------------------------------------------------------------- 页面组成

def load_json(path: Path, tries: int = 3, wait_s: float = 10.0) -> dict:
    """读 JSON；文件正被别的 agent 重写时等 10 秒重试，最多 3 次。"""
    last = None
    for i in range(tries):
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:                  # pragma: no cover
            last = exc
            if i + 1 < tries:
                print(f"  … 读 {path.name} 失败（{exc}），{wait_s:.0f}s 后重试", file=sys.stderr)
                import time
                time.sleep(wait_s)
    raise SystemExit(f"读不到 {path}: {last}")


def validate(stages: dict, city: dict) -> list[str]:
    """口径自检：D44+D45 的硬性要求逐项核对。"""
    errs: list[str] = []
    sts = stages.get("stages", [])
    if len(sts) != 4:
        errs.append(f"阶段数应为 4，实际 {len(sts)}")
    for st, exp in zip(sts, EXPECTED):
        if st.get("level") != exp["level"]:
            errs.append(f"level 顺序错：{st.get('level')} != {exp['level']}")
        for k in ("name", "subtitle", "crosscut"):
            if st.get(k) != exp[k]:
                errs.append(f"{exp['level']} {k} 应为 {exp[k]!r}，实际 {st.get(k)!r}")
        if len(st.get("connection_points", [])) != exp["cp"]:
            errs.append(f"{exp['level']} 接线点应为 {exp['cp']}，实际 {len(st.get('connection_points', []))}")
        bad = st.get("badges", {})
        if len(bad.get("cumulative", [])) != exp["badges"]:
            errs.append(f"{exp['level']} 累计亮起徽章应为 {exp['badges']}，实际 {len(bad.get('cumulative', []))}")
        if len(bad.get("new", [])) != exp["new"]:
            errs.append(f"{exp['level']} 本阶段新亮徽章应为 {exp['new']}，实际 {len(bad.get('new', []))}")
        if len(bad.get("rewired", [])) != exp["rewire"]:
            errs.append(f"{exp['level']} 二次接线徽章应为 {exp['rewire']}，实际 {len(bad.get('rewired', []))}")
        if len(st.get("mechanisms", [])) != exp["mech"]:
            errs.append(f"{exp['level']} 机制条数应为 {exp['mech']}，实际 {len(st.get('mechanisms', []))}")
        if st.get("pages", "").replace(" ", "") != exp["pages"]:
            errs.append(f"{exp['level']} 页范围应为 {exp['pages']}，实际 {st.get('pages')}")
    # 城市几何 / 12 件
    if len(city.get("zones", [])) != 4:
        errs.append(f"data.json 区数应为 4，实际 {len(city.get('zones', []))}")
    if len(city.get("facilities", [])) != 10:
        errs.append(f"data.json 设施数应为 10，实际 {len(city.get('facilities', []))}")
    if len(city.get("roads", [])) != 11:
        errs.append(f"data.json 道路数应为 11，实际 {len(city.get('roads', []))}")
    arts = sorted(a for f in city.get("facilities", []) for a in f.get("artifacts", []))
    if arts != list(range(1, 13)):
        errs.append(f"data.json 12 件编号不齐：{arts}")
    if len(BADGE_REL) != 12:
        errs.append("脚本内徽章位置表应为 12 件")
    # 徽章累计唯一 / 新亮 = 累计差
    prev: set[int] = set()
    for st, exp in zip(sts, EXPECTED):
        cur = set(st.get("badges", {}).get("cumulative", []))
        if len(cur) != len(st.get("badges", {}).get("cumulative", [])):
            errs.append(f"{exp['level']} 累计徽章有重复")
        if not cur.issubset(set(range(1, 13))):
            errs.append(f"{exp['level']} 徽章编号越界：{sorted(cur)}")
        if not set(st.get("badges", {}).get("new", [])).issubset(cur):
            errs.append(f"{exp['level']} 新亮徽章应属于累计集合")
        if (cur - prev) != set(st.get("badges", {}).get("new", [])):
            errs.append(f"{exp['level']} 新亮徽章 != 累计新增 {sorted(cur - prev)}")
        prev = cur
    if prev != set(range(1, 13)):
        errs.append(f"L4 累计徽章应覆盖 12 件，实际 {sorted(prev)}")
    return errs


def draw_legend(sheet: Sheet, stages: dict) -> None:
    x0, y0 = 872, 36
    items = [
        ("hollow", "空心灰 = 壳 / 未建"),
        ("solid", "实心墨 = 此前已接线"),
        ("new", "橙 + 光晕 = 本阶段新接线"),
        ("rewire", "橙外环 = 再次接线"),
        ("dashed", "灰虚线 = 规划 / 未建"),
        ("number", "①–⑫ = 12 件设施件"),
    ]
    for i, (kind, label) in enumerate(items):
        col = i // 3
        row = i % 3
        x = x0 + col * 348
        y = y0 + row * 21
        if kind == "hollow":
            for a in range(8):
                sheet.arc(x + 8, y + 7, 7, a * 45, a * 45 + 24, mix(PAPER, INK, 0.5), 1.6)
        elif kind == "solid":
            sheet.ellipse(x + 8, y + 7, 7, 7, fill=mix(PAPER, INK, 0.88))
        elif kind == "new":
            sheet.ellipse(x + 8, y + 7, 10, 10, fill=mix(PAPER, ORANGE, 0.25))
            sheet.ellipse(x + 8, y + 7, 7, 7, fill=ORANGE)
        elif kind == "rewire":
            sheet.ellipse(x + 8, y + 7, 7, 7, fill=mix(PAPER, INK, 0.88))
            sheet.arc(x + 8, y + 7, 10, -30, 210, ORANGE, 1.8)
        elif kind == "dashed":
            sheet.dashed([(x, y + 7), (x + 18, y + 7)], MUT, 1.6, 3, 2.5)
        else:
            sheet.ellipse(x + 8, y + 7, 7, 7, fill=None, outline=INK2, width=1.2)
            sheet.text((x + 8, y + 7), "12", 4.6, INK2, "Bold", anchor="mm")
        sheet.text((x + 22, y + 1), label, 7.0, INK2, "Medium")


def draw_title(sheet: Sheet, stages: dict) -> None:
    sheet.text((M, 34), "D44 + D45  ·  四阶段 = 造 / 换 / 审 / 守  ·  横切系统口径（不再按件数分级）",
               7.0, MUT, "Bold")
    sheet.text((M, 46), stages["title"], 27, INK, "Black")
    sheet.text((M, 86), stages["thesis"], 8.4, INK2, "Regular")
    sheet.text((M, 74), "", 6.0, MUT)          # 占位（保持行距）
    draw_legend(sheet, stages)


def draw_panel(sheet: Sheet, stage: dict, idx: int, city: dict) -> None:
    pal = PALETTES[idx]
    px, py = PANEL_X[idx], PY
    accent = pal["accent"]
    # 格底板 / 顶条 / 角标
    sheet.rrect(px, py, PW, PH, 7, fill=pal["bg"], outline=mix(accent, pal["bg"], 0.55), width=1.2)
    sheet.rrect(px + 1, py + 1, PW - 2, 3.4, 2, fill=accent)
    for (cx, cy, sx, sy) in ((px + 8, py + 8, 1, 1), (px + PW - 8, py + 8, -1, 1),
                             (px + 8, py + PH - 8, 1, -1), (px + PW - 8, py + PH - 8, -1, -1)):
        sheet.line([(cx, cy), (cx + sx * 9, cy)], mix(accent, pal["bg"], 0.35), 1.2)
        sheet.line([(cx, cy), (cx, cy + sy * 9)], mix(accent, pal["bg"], 0.35), 1.2)

    # 头部
    sheet.rrect(px + PAD, py + PAD, 33, 17, 8.5, fill=accent)
    sheet.text((px + PAD + 16.5, py + PAD + 8.5), stage["level"], 7.6, PAPER, "Black", anchor="mm")
    sheet.text((px + PAD + 43, py + 10), stage["name"], 22, INK, "Black")
    sheet.text((px + PW - PAD, py + 9), stage["action"], 38,
               mix(pal["bg"], accent, 0.22), "Black", anchor="ra")
    sheet.text((px + PAD, py + 41), stage["subtitle"], 8.8, INK2, "Medium")
    meta = 8.2
    mlines = wrap_text(stage["metaphor_line"], get_font("Regular", int(meta * SS)), INNER * SS)[:3]
    y = py + 54
    for ln in mlines:
        sheet.text((px + PAD, y), ln, meta, INK2, "Regular")
        y += meta * 1.28
    sheet.dashed([(px + PAD, py + 90), (px + PW - PAD, py + 90)],
                 mix(accent, pal["bg"], 0.55), 0.8, 4, 3)

    # ---- 地图框：上注记条 + 城区图 + 图层条 + 比例尺（四格同一变换）
    fx, fy = px + PAD, py + 95
    fw, fh = INNER, MAP_FRAME_H
    sheet.rrect(fx, fy, fw, fh, 2, fill=mix(pal["bg"], pal["map_bg"], 0.45),
                outline=mix(accent, pal["bg"], 0.55), width=0.9)
    sheet.text((fx + 5, fy + 3.4), "N ↑  俯视规划图 · 同一坐标基准", 5.8, MUT, "Medium")
    sheet.text((fx + fw - 5, fy + 2.2), f"徽章 {stage['badges']['label']}", 7.0, accent,
               "Bold", anchor="ra")
    map_x, map_y = fx, fy + 13
    cm = CityMap(city, stage, pal, int(round(INNER * SS)), int(round(MAP_H * SS)))
    map_img = cm.draw()
    sheet.img.paste(map_img, (sheet.px(map_x), sheet.px(map_y)))
    MAP_GEOM.append((idx, round(map_x, 3), round(map_y, 3), round(INNER, 3),
                     round(MAP_H, 3), city_hash))
    sheet.rect(map_x, map_y, INNER, MAP_H, outline=mix(accent, PAPER, 0.5), width=0.8)
    # 图层条：四格同一套图层，本格累到第 idx+1 层
    ly = fy + 13 + MAP_H + 2
    sheet.text((fx + 5, ly + 0.4), "图层", 5.4, MUT, "Bold")
    lx = fx + 23
    for li, lab in enumerate(("① 骨架", "② 楼体 / 管网", "③ 数据流 / 大脑", "④ 安防")):
        on = li <= idx
        lw = sheet.measure(lab, 5.0, "Medium") + 7
        sheet.rrect(lx, ly, lw, 10.2, 3,
                    fill=mix(pal["bg"], accent, 0.22) if on else None,
                    outline=accent if on else mix(accent, pal["bg"], 0.45), width=0.7)
        sheet.text((lx + lw / 2, ly + 5.1), lab, 5.0, accent if on else MUT,
                   "Medium", anchor="mm")
        lx += lw + 4.5
    # 比例尺（400 城市单位 ≈ 83 逻辑单位）
    bar_y = fy + 13 + MAP_H + 18.5
    bx0 = fx + 6
    bar_len = 400 * (INNER / 1600)
    sheet.line([(bx0, bar_y), (bx0 + bar_len, bar_y)], MUT, 0.9)
    for i, lab in ((0, "0"), (1, "200"), (2, "400 m")):
        tx = bx0 + i * bar_len / 2
        sheet.line([(tx, bar_y - 2.0), (tx, bar_y + 2.0)], MUT, 0.9)
        sheet.text((tx, bar_y + 2.2), lab, 4.8, MUT, "Medium", anchor="ma")
    sheet.text((fx + fw - 5, bar_y - 2.2), "同一变换 · 四格同缩放", 5.0, MUT, "Medium", anchor="ra")

    # 横切系统
    yy = fy + fh + 9
    sheet.text((px + PAD, yy), "横切系统", 6.4, MUT, "Bold")
    sheet.text((px + PAD + 50, yy - 2.5), stage["crosscut"], 10.2, INK, "Black")
    cps = stage["connection_points"]
    if cps:
        sheet.text((px + PW - PAD, yy), f"接线点 {len(cps)}/{len(cps)}", 7.0, accent,
                   "Bold", anchor="ra")
        for i in range(len(cps)):
            sheet.rect(px + PW - PAD - 62 + i * 7, yy + 8, 4.5, 4.5, fill=accent)
    else:
        sheet.text((px + PW - PAD, yy), "接线点 —", 7.0, accent, "Bold", anchor="ra")

    # 接线点 chips
    yy += 15
    x = px + PAD
    if cps:
        for cp in cps:
            cw = sheet.measure(cp, 7.2, "Medium") + 11
            sheet.rrect(x, yy, cw, 14, 7, fill=mix(pal["bg"], accent, 0.10), outline=accent, width=0.8)
            sheet.text((x + cw / 2, yy + 7), cp, 7.2, accent, "Medium", anchor="mm")
            x += cw + 5
    else:
        sheet.rrect(x, yy, 176, 14, 7, fill=mix(pal["bg"], accent, 0.10),
                    outline=mix(accent, pal["bg"], 0.6), width=0.8)
        sheet.text((x + 6, yy + 7), "— 骨架阶段：没有接线点，12 件全空", 6.6, accent, "Medium", anchor="lm")

    # 学生动作 / 交付
    yy += 22
    sheet.text((px + PAD, yy), f"学生动作 · {stage['action']}（{stage['pages']}）", 6.4, MUT, "Bold")
    yy += 10.5
    a_lines = wrap_text(stage["student_action"], get_font("Regular", int(7.2 * SS)), (INNER - 26) * SS)[:2]
    for ln in a_lines:
        sheet.text((px + PAD + 26, yy), ln, 7.2, INK2, "Regular")
        yy += 9.2
    sheet.text((px + PAD, yy - 9.2 * len(a_lines)), "动作", 6.4, accent, "Bold")
    sheet.text((px + PAD, yy), "交付", 6.4, accent, "Bold")
    d_lines = wrap_text(stage["deliverable"], get_font("Regular", int(7.0 * SS)), (INNER - 26) * SS)[:2]
    for ln in d_lines:
        sheet.text((px + PAD + 26, yy), ln, 7.0, INK2, "Regular")
        yy += 9.0

    # 机制
    yy += 7
    sheet.text((px + PAD, yy), f"机制 · {len(stage['mechanisms'])} 条接线（{stage['action']}）", 6.4, MUT, "Bold")
    y = yy + 11
    for m in stage["mechanisms"]:
        sheet.rrect(px + PAD, y - 1, 10, 10, 2, fill=accent)
        sheet.text((px + PAD + 5, y + 4), f"{m['no']:02d}", 4.9, PAPER, "Bold", anchor="mm")
        name = m["name"] + (f" · {m['page']}" if m.get("page") else "")
        sheet.text((px + PAD + 15, y - 2), name, 7.9, INK, "Bold")
        what_lines = wrap_text(m["what"], get_font("Regular", int(6.9 * SS)),
                               (INNER - 15) * SS)[:2]
        ty = y + 9
        for ln in what_lines:
            sheet.text((px + PAD + 15, ty), ln, 6.9, INK2, "Regular")
            ty += 9.1
        y = ty + 3.2
        sheet.dashed([(px + PAD, y - 3), (px + PW - PAD, y - 3)],
                     mix(accent, pal["bg"], 0.75), 0.7, 3, 3)

    # 这一格新增
    y += 2
    sheet.text((px + PAD, y), "这一格新增（在上一格之上叠加）", 6.4, accent, "Bold")
    y += 11
    for cue in stage["visual_cues"]:
        sheet.circle(px + PAD + 2.5, y + 3.2, 1.5, fill=accent)
        lines = wrap_text(cue, get_font("Regular", int(6.8 * SS)), (INNER - 9) * SS)[:2]
        for j, ln in enumerate(lines):
            sheet.text((px + PAD + 8, y + j * 8.6), ln, 6.8, INK2, "Regular")
        y += 8.2 * len(lines) + 2.0

    # 验收判据（真跑输出）
    y += 2
    sheet.text((px + PAD, y), "验收判据（真跑输出）", 6.3, accent, "Bold")
    y += 8.6
    ev_lines = wrap_text(stage.get("evidence", ""), get_font("Regular", int(6.6 * SS)),
                         INNER * SS)[:2]
    for ln in ev_lines:
        sheet.text((px + PAD, y), ln, 6.6, INK2, "Regular")
        y += 8.4
    # 本格增量（放得下才画）
    if y <= py + PH - 106:
        y += 3
        new = stage["badges"]["new"]
        circ = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
        if new:
            delta = "、".join(circ[n - 1] for n in new)
            line = f"本格增量：徽章新亮 {delta}（累计 {stage['badges']['label']}） · 接线点 {len(stage['connection_points'])}/{len(stage['connection_points'])}"
        else:
            line = "本格增量：12 件全是壳（徽章 0/12）· 接线点 0"
        sheet.circle(px + PAD + 2.5, y + 3.4, 1.6, fill=accent)
        sheet.text((px + PAD + 8, y), line, 6.6, INK2, "Medium")
        y += 11

    # 城市读数（四格固定在同一个纵坐标；放不下就不画）
    axis_y = py + PH - 92
    bh = 40
    by = axis_y - 48
    drew_stats = y <= by - 3
    if drew_stats:
        sheet.rrect(px + PAD, by, INNER, bh, 3, fill=mix(pal["bg"], accent, 0.05),
                    outline=mix(accent, pal["bg"], 0.5), width=0.8)
        for i in range(1, 3):
            sheet.line([(px + PAD + INNER * i / 3, by + 5),
                        (px + PAD + INNER * i / 3, by + bh - 5)],
                       mix(accent, pal["bg"], 0.6), 0.7)
        for i, (num, lab) in enumerate(STAGE_STATS[idx]):
            cx = px + PAD + INNER * (i + 0.5) / 3
            sheet.text((cx, by + 4), num, 12.5, accent, "Black", anchor="ma")
            sheet.text((cx, by + bh - 10.5), lab, 5.8, MUT, "Medium", anchor="ma")
        y = by + bh
    if os.environ.get("CITY_STAGES_DEBUG"):
        print(f"  [layout] panel {idx + 1} content_end={y - py:.1f} stats={drew_stats}", file=sys.stderr)

    # D44 动作轴（本格在造 / 换 / 审 / 守里的位置）
    if y <= py + PH - 96:
        ay = py + PH - 88
        sheet.text((px + PAD, ay + 3), "D44 动作轴", 6.0, MUT, "Bold")
        ax = px + PAD + 45
        for i, aa in enumerate(("造", "换", "审", "守")):
            cur = (i == idx)
            sheet.rrect(ax, ay, 15, 12.5, 3, fill=accent if cur else mix(pal["bg"], accent, 0.10),
                        outline=accent, width=0.8)
            sheet.text((ax + 7.5, ay + 6.2), aa, 6.4, PAPER if cur else accent, "Bold", anchor="mm")
            ax += 18

    # 底部：12 个徽章刻度 + 动作 / 主题 / 页
    footer_top = py + PH - 48
    sheet.dashed([(px + PAD, footer_top), (px + PW - PAD, footer_top)],
                 mix(accent, pal["bg"], 0.6), 0.8, 4, 3)
    sheet.text((px + PAD, footer_top + 4), f"徽章 {stage['badges']['label']} · 12 件设施件",
               6.5, MUT, "Bold")
    lit = set(stage["badges"]["cumulative"])
    new = set(stage["badges"]["new"])
    rew = set(stage["badges"]["rewired"])
    for i in range(12):
        no = i + 1
        tw = 21
        x0 = px + PAD + i * (tw + 6.4)
        if no in new:
            fill = ORANGE
        elif no in lit:
            fill = mix(pal["bg"], INK, 0.9) if no not in rew else mix(pal["bg"], accent, 0.55)
        else:
            fill = mix(pal["bg"], FAINT, 0.35)
        sheet.rect(x0, footer_top + 15, tw, 7, fill=fill,
                   outline=None if no in lit else mix(pal["bg"], FAINT, 0.7), width=0.7)
        if no in rew:
            sheet.rect(x0, footer_top + 13.2, tw, 1.2, fill=ORANGE)
    sheet.text((px + PAD, py + PH - 24), stage["action"], 13, accent, "Black")
    sheet.text((px + PAD + 17, py + PH - 21), f"{stage['theme']} · {stage['pages']}", 7.6, INK2, "Medium")
    sheet.text((px + PW - PAD, py + PH - 24), stage["level"], 7.0, MUT, "Bold", anchor="ra")

    BADGE_LOG.append((idx, 12, len(lit), len(new)))


def draw_transitions(sheet: Sheet, stages: dict) -> None:
    for i in range(3):
        gx = PANEL_X[i] + PW + GAP / 2
        nxt = stages["stages"][i + 1]
        pal = PALETTES[i + 1]
        sheet.ellipse(gx, 470, 9, 9, fill=ORANGE)
        sheet.text((gx, 470), nxt["action"], 8.6, PAPER, "Black", anchor="mm")
        for j in range(3):
            y = 500 + j * 13
            sheet.line([(gx - 4, y), (gx + 3, y + 4)], pal["accent"], 1.6)
            sheet.line([(gx - 4, y + 8), (gx + 3, y + 4)], pal["accent"], 1.6)


def draw_bottom(sheet: Sheet, stages: dict) -> None:
    sts = stages["stages"]
    sheet.dashed([(M, 908), (W - M, 908)], HAIR, 0.8, 5, 4)
    sheet.text((M, 916), "接线点进度", 7.6, INK, "Black")
    sheet.text((M + 60, 917), "横切系统要接的页（L2 4 · L3 4 · L4 5），不数件", 6.4, MUT, "Medium")
    note = "接线点 ≠ 徽章数：徽章只数 12 件设施（0 → 4 → 8 → 12）"
    sheet.text((W - M, 917), note, 6.4, MUT, "Medium", anchor="ra")
    # 轨道
    centers = [PANEL_X[i] + PW / 2 for i in range(4)]
    sheet.line([(centers[0], 954), (centers[-1], 954)], HAIR, 1.4)
    for i, st in enumerate(sts):
        cx = centers[i]
        pal = PALETTES[i]
        cp = st["connection_points"]
        count = f"{len(cp)}/{len(cp)}" if cp else "0"
        sheet.ellipse(cx, 954, 8.5, 8.5, fill=pal["accent"], outline=PAPER, width=1.2)
        sheet.text((cx, 954), st["level"], 5.6, PAPER, "Black", anchor="mm")
        head = f"{st['level']} {st['name']} · {count}"
        sheet.text((cx, 930), head, 8.2, INK, "Bold", anchor="ma")
        sub = " · ".join(cp) if cp else "12 件全空 · 只有骨架"
        sheet.text((cx, 966), sub, 6.7, MUT, "Medium", anchor="ma")
        if i < 3:
            mx = (centers[i] + centers[i + 1]) / 2
            sheet.ellipse(mx, 954, 7, 7, fill=PAPER, outline=ORANGE, width=1.4)
            sheet.text((mx, 954), sts[i + 1]["action"], 6.6, ORANGE, "Black", anchor="mm")
            sheet.text((mx, 928), sts[i + 1]["theme"], 6.2, MUT, "Medium", anchor="ma")
    # 页脚
    sheet.text((M, 980), "D44 + D45 · 城市四阶段 · 同一片城区 / 同一坐标基准 · 12 件设施 × 横切系统",
               5.8, MUT, "Medium")
    sheet.text((W - M, 980), "SHEET 01/01 · 重跑 python3 tutorial/shots/render_city_stages.py",
               5.8, MUT, "Medium", anchor="ra")


def compose(stages: dict, city: dict) -> Image.Image:
    sheet = Sheet()
    # 页面边框 + 注册角
    sheet.rect(M - 16, 20, W - 2 * (M - 16), 962, outline=HAIR, width=1.0)
    for (cx, cy, sx, sy) in ((M - 16, 20, 1, 1), (W - M + 16, 20, -1, 1),
                             (M - 16, 982, 1, -1), (W - M + 16, 982, -1, -1)):
        sheet.line([(cx, cy), (cx + sx * 14, cy)], FAINT, 1.2)
        sheet.line([(cx, cy), (cx, cy + sy * 14)], FAINT, 1.2)
    draw_title(sheet, stages)
    for i, st in enumerate(stages["stages"]):
        draw_panel(sheet, st, i, city)
    draw_transitions(sheet, stages)
    draw_bottom(sheet, stages)
    return sheet.img.resize((OUT_W, OUT_H), Image.LANCZOS)


# ---------------------------------------------------------------- 自检

def check_png(img: Image.Image, stages: dict) -> list[str]:
    errs: list[str] = []
    if img.size != (OUT_W, OUT_H):
        errs.append(f"成图尺寸应为 {OUT_W}×{OUT_H}，实际 {img.size}")
    # 四格几何一致
    geoms = {(g[3], g[4], g[5]) for g in MAP_GEOM}   # 视口尺寸 / 城市数据哈希；x,y 随格位置走
    if len(geoms) != 1:
        errs.append(f"四格地图几何基准不一致：{sorted(geoms)}")
    if len(MAP_GEOM) != 4:
        errs.append(f"地图基准记录应为 4 条，实际 {len(MAP_GEOM)}")
    # 每格 12 枚徽章
    if len(BADGE_LOG) != 4:
        errs.append(f"徽章记录应为 4 格，实际 {len(BADGE_LOG)}")
    for idx, total, lit, new in BADGE_LOG:
        exp = EXPECTED[idx]
        if total != 12:
            errs.append(f"第 {idx + 1} 格徽章数应为 12，实际 {total}")
        if lit != exp["badges"]:
            errs.append(f"第 {idx + 1} 格亮起徽章应为 {exp['badges']}，实际 {lit}")
        if new != exp["new"]:
            errs.append(f"第 {idx + 1} 格新亮徽章应为 {exp['new']}，实际 {new}")
    # 暖度单调递增（成图上量测，不用脚本常量）
    warm = []
    for i in range(4):
        x0 = int(PANEL_X[i] * FINAL_SCALE) + 4
        x1 = int((PANEL_X[i] + PW) * FINAL_SCALE) - 4
        y0 = int(PY * FINAL_SCALE) + 4
        y1 = int((PY + PH) * FINAL_SCALE) - 4
        crop = img.crop((x0, y0, x1, y1)).convert("RGB")
        px = list(crop.getdata())
        n = len(px)
        mr = sum(p[0] for p in px) / n
        mb = sum(p[2] for p in px) / n
        warm.append(mr - mb)
    if not (warm[0] < warm[1] < warm[2] < warm[3]):
        errs.append(f"四格暖度未严格递增：{[round(w, 1) for w in warm]}")
    WARM_LOG.extend(warm)
    # 文字禁止项
    for t in DRAWN_TEXTS:
        for bad in FORBIDDEN:
            if bad in t:
                errs.append(f"图上文字含禁止内容 {bad!r}：{t!r}")
    # 关键文字都在
    must = ["同一片城区：从荒地工地到敢交付的城市", "荒地工地", "通水电网", "智慧城市", "城市安防",
            "造", "换", "审", "守", "接线点", "徽章", "同一坐标基准"]
    joined = "\n".join(DRAWN_TEXTS)
    for m in must:
        if m not in joined:
            errs.append(f"图上缺关键文字 {m!r}")
    return errs


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    fast = "--fast" in sys.argv
    stages = load_json(STAGES_PATH)
    city = load_json(CITY_PATH)
    global city_hash
    city_hash = hashlib.sha256(json.dumps(city, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]

    print("① 口径自检（stages-city.json vs D44 + D45）")
    errs = validate(stages, city)
    if errs:
        for e in errs:
            print("  ✗", e)
        return 1
    print(f"  ✓ 4 阶段 {[s['level'] for s in stages['stages']]} · 接线点 "
          f"{[len(s['connection_points']) for s in stages['stages']]} · 徽章 "
          f"{[s['badges']['label'] for s in stages['stages']]}")
    print(f"  ✓ 城市单源：4 区 · 10 设施 · 11 道路 · 12 件（city sha256 {city_hash}）")

    print("② 组版四格（同一片城区 · 同一坐标基准）")
    img = compose(stages, city)
    print(f"  ✓ 画布 {W}×{H} × {SS} 超采样 → 成图 {img.size[0]}×{img.size[1]}")

    print("③ 成图自检")
    errs = check_png(img, stages)
    if errs:
        for e in errs:
            print("  ✗", e)
        return 1
    print(f"  ✓ 四格几何基准一致：视口 {MAP_GEOM[0][3]}×{MAP_GEOM[0][4]} × 同一 city 数据（sha256 {city_hash}）")
    print(f"  ✓ 每格 12 枚徽章：{[b[1] for b in BADGE_LOG]}；亮起 "
          f"{[b[2] for b in BADGE_LOG]}；新亮 {[b[3] for b in BADGE_LOG]}")
    print(f"  ✓ 暖度（mean R−B）逐格递增：{[round(w, 1) for w in WARM_LOG]}")
    print(f"  ✓ 图上文字 {len(DRAWN_TEXTS)} 条：无外链 / 用户名 / 绝对路径 / 口令")

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PNG)
    digest = sha256(OUT_PNG)
    print(f"④ 写出 {OUT_PNG.relative_to(REPO)}  ({OUT_PNG.stat().st_size // 1024} KB, sha256 {digest[:16]}…)")

    if not fast:
        print("⑤ 确定性自检：再画一遍比对 sha256")
        img2 = compose(stages, city)
        tmp = OUT_PNG.with_suffix(".verify.png")
        img2.save(tmp)
        d2 = sha256(tmp)
        tmp.unlink()
        if d2 != digest:
            print(f"  ✗ 两次渲染不一致：{digest} != {d2}")
            return 1
        print(f"  ✓ 两次渲染像素一致（sha256 {d2[:16]}…）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
