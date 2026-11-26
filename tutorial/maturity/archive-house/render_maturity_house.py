#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_maturity_house.py —— 「同一栋房子的四个阶段」隐喻图（一张 PNG）。

在仓库根目录一条命令重跑：

    python3 tutorial/shots/render_maturity_house.py

读：`tutorial/maturity/data.json`（12 件交付物：no / name / location / skeleton / mature）
    `tutorial/maturity/stages.json`（4 阶段：id / name / subtitle / metaphor_line / artifacts_grown / mechanisms）
写：`tutorial/maturity/house.html`（单文件、零外部请求、离线可开：数据与 SVG 全部内联）
    `tutorial/maturity/house-4stages.png`（1600×800 CSS @2x → 3200×1600，convert -trim 收边）

图在说什么（一句话）：**同一栋房子 —— 毛坯能站人，通水通电才能住，装上智能才好用，有了安防才敢交付。**
所以版式不是四张不同的房子，而是**同一栋、同一户型、同一视角（正面剖视）的房子，从左到右四个阶段**：

- 每阶段都画同一栋：地基 / 墙体 / 阁楼 / 地下室 / 门窗位置一个不动，只增不删；
- 12 件交付物是 12 枚**钉在房子对应部位上的编号圆牌**（① 地基、② 墙体、③ 地下室储物架、
  ④ 水箱、⑤ 锅炉、⑥ 路由器、⑦ 天花板感应器、⑧ 阁楼电控箱、⑨ 市政水表、⑩ 水龙头、
  ⑪ 玻璃窗/室内屏、⑫ 入户管线总成），不是底部列表；
- 未到阶段 = 空心灰牌 + 虚线幽灵轮廓；已到 = 实心深棕牌；**本阶段新增 = 实心橙牌 + 光晕**；
- 阶段 2 亮 5 枚（①②③④⑤）、阶段 3 再亮 3 枚（⑥⑦⑧）、阶段 4 再亮 4 枚（⑨⑩⑪⑫），合计 12/12。
口径按 lead 校正：⑦=契约驱动 + 可选检索（ES/Qdrant）；⑧=确定性生成（可切真 LLM）；
①=6 service（5 长驻 + 1 一次性 init）；⑪ 不写登录认证，只写取消 / 错误卡 / 结果表 / 步骤条。

实现（只用本机工具，不引外部字体 / CDN / 图片）：

1. 读两份 JSON + 结构自检：12 件齐、4 阶段齐、每阶段 artifacts_grown 与 mechanisms 对齐、
   mechanisms 的 mature 与 data.json 逐字一致、「本阶段长出来」并集恰好覆盖 12 件各一次；
2. 生成 house.html：手绘感只用 SVG 路径微抖动 + 双描边（不用滤镜），每阶段一套调色板（冷灰 → 暖橙）；
3. 无头 Chrome `--dump-dom` 跑页面**内置自检**：徽章数 / 编号 / 本阶段新增数 / 外部请求数 /
   徽章是否都在房子卡片里 / 12 条 tooltip 的「骨架 → 成熟」是否齐 / 页面是否溢出；
4. 无头 Chrome `--screenshot`（1600×800 @2x）+ `convert -trim` 收白边、回 3200×1600 画布；
5. 成图自检：PNG 尺寸、四阶段"暖度"是否逐级上升、HTML / PNG 里有没有用户名 / 绝对路径 / 口令。

依赖：`/usr/bin/google-chrome`、ImageMagick `convert`、Noto Sans CJK SC（本机字体）。
只写 house.html / house-4stages.png；stages.json 是 4 阶段定义的唯一事实源（本脚本只读它）；不改十页正文、SPEC、completeness、flow、README。
"""

from __future__ import annotations

import html
import json
import math
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent              # tutorial/shots
REPO = HERE.parents[1]                              # 仓库根目录
MAT = REPO / "manual" / "maturity"
DATA_PATH = MAT / "data.json"
STAGES_PATH = MAT / "stages.json"
OUT_HTML = MAT / "house.html"
OUT_PNG = MAT / "house-4stages.png"

CHROME = "/usr/bin/google-chrome"
CONVERT = shutil.which("convert") or "/usr/bin/convert"

DESIGN_W, DESIGN_H = 1600, 800                      # CSS 设计画布
SCALE = 2
OUT_W, OUT_H = DESIGN_W * SCALE, DESIGN_H * SCALE    # 3200×1600
PAPER = "#F4F1EA"
RERUN = "python3 tutorial/shots/render_maturity_house.py"

# 成图 / HTML / 数据里不许出现的字符串（用户名、绝对路径、口令）。
HOST_USER = Path.home().name
FORBIDDEN = [
    "/home/", "/Users/", "/tmp/", HOST_USER,
    "password", "passwd", "labpass", "MYSQL_ROOT_PASSWORD", "REBUILD_DW_RO_PASSWORD",
    "sk-", "root@", "-uroot",
]
# 目视抽查必须能认出的关键真值（都来自 data.json / 十页）。
REQUIRED_TOKENS = ["41099.5", "115", "127.0.0.1:3307", "12/12", "毛坯", "通水通电", "智能家居", "物业安防"]

# 设计口径：四阶段各长出哪几件（与 stages.json 必须逐项一致；并集=12 件各一次）。
EXPECTED_GROUPS = [
    [],
    [1, 2, 3, 4, 5],
    [6, 7, 8],
    [9, 10, 11, 12],
]

# 12 件 → 房子部位（画在哪儿、圆牌钉在哪儿）。pos=圆牌中心；anchor=部位上的钉点；part=报告用。
# 坐标是 house SVG 的 viewBox 坐标（见 VB_W / VB_H）。
BADGES = {
    1:  dict(part="地基 / 场地",        pos=(40.0, 398.0), anchor=(74.0, 396.0)),
    2:  dict(part="墙体",               pos=(352.0, 224.0), anchor=(330.0, 236.0)),
    3:  dict(part="地下室储物架",       pos=(282.0, 448.0), anchor=(262.0, 440.0)),
    4:  dict(part="水箱",               pos=(216.0, 306.0), anchor=(200.0, 308.0)),
    5:  dict(part="锅炉 / 热水器",      pos=(146.0, 268.0), anchor=(122.0, 288.0)),
    6:  dict(part="路由器 / 对讲",      pos=(352.0, 262.0), anchor=(306.0, 258.0)),
    7:  dict(part="天花板感应器",       pos=(256.0, 228.0), anchor=(238.0, 212.0)),
    8:  dict(part="阁楼电控箱 / 大脑",  pos=(214.0, 168.0), anchor=(192.0, 178.0)),
    9:  dict(part="市政水管 + 只读水表", pos=(30.0, 322.0), anchor=(62.0, 340.0)),
    10: dict(part="水龙头 / 逐滴出水",  pos=(242.0, 322.0), anchor=(234.0, 344.0)),
    11: dict(part="玻璃窗 / 室内屏",    pos=(248.0, 264.0), anchor=(226.0, 266.0)),
    12: dict(part="入户管线总成",       pos=(144.0, 448.0), anchor=(160.0, 420.0)),
}


# ------------------------------------------------------------------ 小工具

def esc(text: object) -> str:
    """HTML 文本转义（中文与引号原样保留）。"""
    return html.escape(str(text), quote=False)


def n(v: float) -> str:
    """紧凑数字：40.0 → 40，0.85 → 0.85。"""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def crc(seed: object) -> int:
    return zlib.crc32(str(seed).encode("utf-8")) & 0xFFFFFFFF


def rnd(seed: object) -> random.Random:
    return random.Random(crc(seed))


def wobble(pts: list[tuple[float, float]], seed: object, amp: float = 0.8, closed: bool = True) -> str:
    """折线 → 手绘感路径：每段中点沿法向随机偏一点，用二次曲线连过去。"""
    r = rnd(seed)
    m = len(pts)
    d = [f"M{n(pts[0][0])} {n(pts[0][1])}"]
    segs = m if closed else m - 1
    for i in range(segs):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % m]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        ox, oy = -dy / length, dx / length
        k = r.uniform(-amp, amp)
        mx, my = (x1 + x2) / 2 + ox * k, (y1 + y2) / 2 + oy * k
        d.append(f"Q{n(mx)} {n(my)} {n(x2)} {n(y2)}")
    if closed:
        d.append("Z")
    return " ".join(d)


def sk(pts: list[tuple[float, float]], seed: object, cls: str = "k",
       amp: float = 0.75, closed: bool = True) -> str:
    """主描边 + 一条低透明度错位描边：不加滤镜的手绘感。"""
    return (
        f'<path class="{cls}" d="{wobble(pts, str(seed) + "A", amp, closed)}"/>'
        f'<path class="{cls} k2" d="{wobble(pts, str(seed) + "B", amp * 1.7 + 0.25, closed)}"/>'
    )


def rect_pts(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def fpoly(pts: list[tuple[float, float]], color: str, seed: object = "f", wob: float = 0.45) -> str:
    return f'<path d="{wobble(pts, seed, wob)}" fill="{color}" stroke="none"/>'


def srect(x: float, y: float, w: float, h: float, seed: object, fill: str | None = None,
          cls: str = "k", amp: float = 0.65) -> str:
    pts = rect_pts(x, y, w, h)
    out = fpoly(pts, fill, str(seed) + "F") if fill else ""
    return out + sk(pts, seed, cls, amp)


def scircle(cx: float, cy: float, r: float, seed: object, fill: str | None = None,
            cls: str = "k") -> str:
    r2 = rnd(str(seed) + "C")
    dx, dy = r2.uniform(-0.6, 0.6), r2.uniform(-0.6, 0.6)
    out = f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}" stroke="none"/>' if fill else ""
    return (f'{out}<circle class="{cls}" cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="none"/>'
            f'<circle class="{cls} k2" cx="{n(cx + dx)}" cy="{n(cy + dy)}" r="{n(r + 0.35)}" fill="none"/>')


def path1(d: str, cls: str = "k") -> str:
    return f'<path class="{cls}" d="{d}"/>'


def text(x: float, y: float, s: str, cls: str = "lbl", anchor: str = "middle") -> str:
    return (f'<text class="{cls}" x="{n(x)}" y="{n(y)}" text-anchor="{anchor}">{esc(s)}</text>')


# ------------------------------------------------------------------ 读数据 + 自检

def fail(msg: str):
    print(f"✗ {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path, label: str) -> dict:
    if not path.exists():
        fail(f"找不到{label} {path.relative_to(REPO)}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.relative_to(REPO)} 不是合法 JSON：{exc}")
    if not isinstance(doc, dict):
        fail(f"{path.relative_to(REPO)} 顶层必须是对象")
    return doc


def plain(text: str) -> str:
    return re.sub(r"`([^`]+)`", r"\1", str(text))


def validate_inputs(data: dict, stages_doc: dict) -> None:
    errs: list[str] = []
    arts = data.get("artifacts") or []
    if len(arts) != 12:
        errs.append(f"data.json 里 {len(arts)} 件，口径是 12 件")
    if [a.get("no") for a in arts] != list(range(1, 13)):
        errs.append("data.json 编号必须是 1–12 连续")
    for a in arts:
        for key in ("id", "name", "kind", "location", "skeleton", "mature", "delta", "tags"):
            if not str(a.get(key, "")).strip():
                errs.append(f"#{a.get('no')} 缺 {key}")

    stages = stages_doc.get("stages") or []
    if len(stages) != 4:
        errs.append(f"stages.json 里 {len(stages)} 个阶段，口径是 4 个")
    if str(stages_doc.get("rerun", "")) != RERUN:
        errs.append(f"stages.json rerun 应为本脚本命令 {RERUN!r}")
    if str(stages_doc.get("thesis", "")).count("同一栋房子") == 0:
        errs.append("stages.json 的 thesis 要写清「同一栋房子」")

    by_no = {a["no"]: a for a in arts}
    seen: list[int] = []
    for i, st in enumerate(stages):
        for key in ("id", "level", "name", "subtitle", "metaphor_line"):
            if not str(st.get(key, "")).strip():
                errs.append(f"阶段 {i + 1} 缺 {key}")
        grown = st.get("artifacts_grown")
        if not isinstance(grown, list):
            errs.append(f"阶段 {i + 1} artifacts_grown 必须是数组")
            grown = []
        if sorted(grown) != EXPECTED_GROUPS[i]:
            errs.append(f"阶段 {i + 1} artifacts_grown={grown}，设计口径应为 {EXPECTED_GROUPS[i]}")
        mechs = st.get("mechanisms") or []
        if [m.get("no") for m in mechs] != grown:
            errs.append(f"阶段 {i + 1} mechanisms 的 no 必须与 artifacts_grown 对齐：{grown}")
        for m in mechs:
            no = m.get("no")
            a = by_no.get(no)
            if a is None:
                errs.append(f"阶段 {i + 1} mechanism 引用了不存在的件 {no}")
                continue
            if m.get("mechanism") != a["mature"]:
                errs.append(f"阶段 {i + 1} #{no} 的 mechanism 不是 data.json 的 mature 原文（不许重写）")
            if m.get("name") != a["name"]:
                errs.append(f"阶段 {i + 1} #{no} 的 name 与 data.json 不一致")
            if not str(m.get("label", "")).strip():
                errs.append(f"阶段 {i + 1} #{no} 缺机制短标签 label")
        seen.extend(grown)

    if sorted(seen) != list(range(1, 13)):
        errs.append(f"四个阶段「本阶段长出」的并集是 {sorted(set(seen))}，必须恰好覆盖 1–12 各一次")
    if len(seen) != 12:
        errs.append(f"四个阶段「本阶段长出」合计 {len(seen)} 件，必须是 12 件")
    counts = stages_doc.get("counts") or {}
    if counts.get("grown") != len(seen):
        errs.append("stages.json counts.grown 与实际不符")
    if not (stages_doc.get("legend") and len(stages_doc["legend"]) >= 3):
        errs.append("stages.json 缺 legend（至少空心 / 实心 / 本阶段新增三条）")

    if errs:
        print("✗ 数据自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)
    print("  ✓ 数据：data.json 12 件 × skeleton/mature；stages.json 4 阶段，"
          "本阶段长出 [0,5,3,4]，合计 12 件、并集 1–12 各一次")
    print("  ✓ 口径：mechanisms 与 artifacts_grown 对齐，mature 摘要与 data.json 逐字一致（不重写文字）")


# ------------------------------------------------------------------ 每阶段一套调色板（冷灰 → 暖橙）

PALETTES = [
    dict(  # L1 毛坯房：冷灰、水泥、泥地，一点钢筋锈
        paper="#ECF0F4", border="#BCC3CE", head="#D6DBE3",
        ink="#48505D", soft="#79828F", hatch="#868E9B",
        wall="#CFD4DC", wall_hi="#E6E9EE", ceiling="#DDE2E8",
        roof="#B2B9C4", roof_line="#7C8591",
        floor="#B7BDC6", slab="#A9B0BA",
        ground="#B4AA9B", ground_line="#8E8475",
        metal="#7F8792", water="#9FB4C8", hot="#B08066", light="#D6DAE0",
        glass="#E9ECF0", bs="#7E848D", bs_ink="#5D636B",
        accent="#C2410C", red="#9E5B4C", rust="#A0674F",
        badge_hollow="#6E7783", badge_old="#6B4A2F", badge_new="#D9530F",
        chip="#5E6672",
    ),
    dict(  # L2 通水通电：暖灰、木地板、深瓦，水蓝 + 炉火橙
        paper="#F6F3EB", border="#D6C9B4", head="#EDE5D6",
        ink="#585149", soft="#9C9284", hatch="#AD9F88",
        wall="#E3D8C7", wall_hi="#DACDBA", ceiling="#D9CCB8",
        roof="#6F5A47", roof_line="#54402D",
        floor="#D9C5A7", slab="#C4B7A4",
        ground="#C6B99E", ground_line="#A2947D",
        metal="#8D8475", water="#4C8FC2", hot="#D97706", light="#E8B66A",
        glass="#D6E3E6", bs="#7E7362", bs_ink="#5B5240",
        accent="#C2410C", red="#A34A3E", rust="#9C6A50",
        badge_hollow="#9A9182", badge_old="#6B4A2F", badge_new="#D9530F",
        chip="#7A6E5C",
    ),
    dict(  # L3 智能家居：奶油墙、木地板、灯光暖黄
        paper="#FBF6E8", border="#DFCBA9", head="#F4EAD5",
        ink="#51483C", soft="#978B76", hatch="#B49C76",
        wall="#F0E2C9", wall_hi="#E9D8BD", ceiling="#E9D8BD",
        roof="#7B5C42", roof_line="#5E422C",
        floor="#C9905C", slab="#CDB591",
        ground="#C9BB9D", ground_line="#A19071",
        metal="#8B806D", water="#3F86BC", hot="#D97706", light="#F5B942",
        glass="#DDE7DA", bs="#7B6C56", bs_ink="#5A4E3B",
        accent="#C2410C", red="#B91C1C", rust="#9C6A50",
        badge_hollow="#9A8E7A", badge_old="#6B4A2F", badge_new="#E2570B",
        chip="#7E6F58",
    ),
    dict(  # L4 物业安防：最深最暖的奶油墙 + 橙 + 安防红
        paper="#FDF3E2", border="#E2C69A", head="#F8E7C6",
        ink="#493D2E", soft="#8A7A5B", hatch="#B39667",
        wall="#F5E6C8", wall_hi="#EEDCBA", ceiling="#EEDCBA",
        roof="#5E432E", roof_line="#432E1D",
        floor="#C98F5B", slab="#D3B991",
        ground="#CBBB97", ground_line="#A18B66",
        metal="#867B69", water="#3B7FB5", hot="#D97706", light="#F7C25E",
        glass="#E9E5CB", bs="#77674F", bs_ink="#564734",
        accent="#C2410C", red="#B91C1C", rust="#9C6A50",
        badge_hollow="#968A71", badge_old="#6B4A2F", badge_new="#E2570B",
        chip="#7A6A4F",
    ),
]

# 每阶段「已长出」的累计件（阶段 i 画到第 i 阶段为止所有已长出的机制）。
CUMULATIVE = []
_acc: list[int] = []
for _g in EXPECTED_GROUPS:
    _acc = _acc + list(_g)
    CUMULATIVE.append(set(_acc))

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"


# ------------------------------------------------------------------ 房子几何（四个阶段共用同一套坐标）

VB_X0, VB_Y0, VB_W, VB_H = 12, 28, 360, 484

# 屋顶：同一根脊、同一对檐口、同一厚度 —— 四张图共用，只换材质。
EAVE_L = (62.0, 204.0)
RIDGE = (204.0, 64.0)
EAVE_R = (346.0, 204.0)
ROOF_T = 16.0
CEIL_Y = 204.0
FLOOR_Y = 390.0
SLAB_B = 404.0
GROUND_B = 500.0

WALL_L0, WALL_L1 = 78.0, 98.0          # 左墙外 / 内
WALL_R0, WALL_R1 = 310.0, 330.0        # 右墙内 / 外
BS_X0, BS_X1 = 98.0, 310.0             # 地下室墙外皮
BS_IN0, BS_IN1 = 112.0, 296.0          # 地下室净空
BS_Y0, BS_B = 404.0, 470.0
BS_FLOOR_B = 484.0


def _offset_line(p, q, t):
    dx, dy = q[0] - p[0], q[1] - p[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    if ny < 0:
        nx, ny = -nx, -ny
    return (p[0] + nx * t, p[1] + ny * t), (q[0] + nx * t, q[1] + ny * t)


def _intersect(a1, a2, b1, b2):
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return (px, py)


def _x_at_y(p, q, y):
    (x1, y1), (x2, y2) = p, q
    if abs(y2 - y1) < 1e-9:
        return x1
    return x1 + (x2 - x1) * (y - y1) / (y2 - y1)


_L_IN = _offset_line(EAVE_L, RIDGE, ROOF_T)
_R_IN = _offset_line(RIDGE, EAVE_R, ROOF_T)
RIDGE_IN = _intersect(_L_IN[0], _L_IN[1], _R_IN[0], _R_IN[1])
LEAF_IN = (_x_at_y(_L_IN[0], _L_IN[1], CEIL_Y), CEIL_Y)
REAF_IN = (_x_at_y(_R_IN[0], _R_IN[1], CEIL_Y), CEIL_Y)
ROOF_BAND = [EAVE_L, RIDGE, EAVE_R, REAF_IN, RIDGE_IN, LEAF_IN]
ATTIC = [LEAF_IN, RIDGE_IN, REAF_IN]

# 门窗（同一位置，只换材质/玻璃）
WIN_X0, WIN_X1 = 176.0, 232.0
WIN_Y0, WIN_Y1 = 226.0, 288.0
DOOR_X0, DOOR_X1 = 274.0, 308.0
DOOR_Y0, DOOR_Y1 = 316.0, 390.0

# 设备（同一位置，未长出来时画虚线幽灵轮廓）
BOILER = (104.0, 288.0, 42.0, 64.0)     # x,y,w,h
TANK = (158.0, 306.0, 44.0, 62.0)
SINK = (206.0, 354.0, 46.0, 36.0)
RACK = (190.0, 412.0, 80.0, 58.0)
MANIFOLD = (118.0, 414.0, 56.0, 12.0)
METER = (46.0, 336.0, 32.0, 28.0)
SENSOR = (238.0, 206.0)
ROUTER = (270.0, 250.0, 32.0, 16.0)
CTRLBOX = (148.0, 168.0, 44.0, 36.0)



# ------------------------------------------------------------------ 每阶段房子插画（同一栋，只增不删）

class HouseArt:
    """画同一栋房子的一个阶段：结构全程不动，只把该长出来的机制从虚线幽灵变成实体。"""

    def __init__(self, idx: int, data: dict, stages_doc: dict):
        self.idx = idx
        self.stage = stages_doc["stages"][idx]
        self.data = data
        self.params = self.stage.get("params") or {}
        self.arts = {a["no"]: a for a in data["artifacts"]}
        self.grown = set(CUMULATIVE[idx])
        self.new = set(EXPECTED_GROUPS[idx])
        self.labels: dict[int, str] = {}
        for st in stages_doc["stages"]:
            for m in st["mechanisms"]:
                self.labels[m["no"]] = m["label"]
        self.defs: list[str] = []
        self.body: list[str] = []

    # -- 状态
    def has(self, no: int) -> bool:
        return no in self.grown

    def fresh(self, no: int) -> bool:
        return no in self.new

    # -- 小工具
    def g(self, *chunks: str) -> None:
        self.body.extend(chunks)

    def d(self, *chunks: str) -> None:
        self.defs.extend(chunks)

    def clip(self, name: str, x: float, y: float, w: float, h: float) -> str:
        cid = f"c{self.idx}_{name}"
        self.d(f'<clipPath id="{cid}"><rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"/></clipPath>')
        return cid

    def hatch(self, cid: str, x: float, y: float, w: float, h: float,
              gap: float = 7.0, seed: object = "h") -> None:
        lines = []
        r = rnd(seed)
        start = -h
        off = start
        while off <= w:
            x1, y1 = x + off, y + h
            x2, y2 = x1 + h, y
            lines.append(f'<path class="hatch" d="M{n(x1)} {n(y1)} L{n(x2)} {n(y2)}" opacity="{n(r.uniform(0.45, 0.8))}"/>')
            off += gap
        self.g(f'<g clip-path="url(#{cid})">{"".join(lines)}</g>')

    def clip_poly(self, name: str, pts: list[tuple[float, float]]) -> str:
        cid = f"p{self.idx}_{name}"
        d = " ".join(f"{'M' if i == 0 else 'L'}{n(x)} {n(y)}" for i, (x, y) in enumerate(pts)) + " Z"
        self.d(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        return cid

    def ghost(self, pts: list[tuple[float, float]], seed: object, cls: str = "ghost") -> str:
        return f'<path class="{cls}" d="{wobble(pts, seed, 0.6, True)}"/>'

    def ghost_rect(self, x: float, y: float, w: float, h: float, seed: object) -> str:
        return self.ghost(rect_pts(x, y, w, h), seed)

    def pipe(self, d: str, color: str, width: float = 3.0, cls: str = "") -> str:
        return (f'<path class="pipe {cls}" d="{d}" stroke="{color}" stroke-width="{n(width)}" '
                f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>')

    # -- 泥土 / 场地 -----------------------------------------------------------------
    def draw_soil(self) -> None:
        outer = "M0 390 H384 V500 H0 Z"
        hole = "M98 404 H310 V484 H98 Z"
        self.g(f'<path d="{outer} {hole}" fill-rule="evenodd" fill="var(--ground)"/>')
        dots = []
        r = rnd(f"soil{self.idx}")
        while len(dots) < 90:
            x, y = r.uniform(2, 382), r.uniform(393, 497)
            if 96 < x < 312 and 401 < y < 487:
                continue
            dots.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r.uniform(0.5, 1.3))}"/>')
        self.g(f'<g class="soil-dots">{"".join(dots)}</g>')
        # 土层线（剖面上的土）
        for i, yy in enumerate((438, 462, 484)):
            self.g(path1(f"M{n(2 + i * 5)} {yy} Q{n(40)} {yy - 2} {n(96)} {yy + 1}", "soil-line"))
            self.g(path1(f"M{n(312)} {yy + 2} Q{n(348)} {yy - 1} {n(382 - i * 6)} {yy}", "soil-line"))
        # 毛坯：泥地 + 水坑 + 碎石；之后：草皮
        if self.idx == 0:
            # 右前方：一堆砂 + 一摞砖（毛坯工地）
            self.g(fpoly([(334, 390), (338, 376), (350, 371), (364, 377), (370, 390)], "var(--ground)", "sandpile", 0.6))
            self.g(sk([(334, 390), (338, 376), (350, 371), (364, 377), (370, 390)], "sandedge", "fine", 0.5, closed=False))
            r3 = rnd("sanddots")
            sand_dots = "".join(f'<circle cx="{n(r3.uniform(339, 367))}" cy="{n(r3.uniform(377, 389))}" r="{n(r3.uniform(.45, 1.0))}"/>' for _ in range(16))
            self.g(f'<g class="sand-dots">{sand_dots}</g>')
            for row in range(2):
                for col in range(3):
                    bx = 346 + col * 9 + row * 4
                    by = 388 - row * 5
                    self.g(f'<rect x="{n(bx)}" y="{n(by - 5)}" width="8" height="5" fill="var(--rust)" opacity=".55" stroke="var(--soft)" stroke-width=".5"/>')
            # 左前方：碎石
            for (sx, sy, sr) in ((12, 386, 2.6), (20, 389, 1.8), (6, 390, 1.6), (26, 387, 2.0)):
                self.g(f'<ellipse cx="{sx}" cy="{sy}" rx="{sr}" ry="{n(sr * 0.62)}" fill="var(--soft)" opacity=".7"/>')
            self.g(f'<ellipse cx="34" cy="392" rx="17" ry="5.2" fill="var(--water)" opacity=".5"/>')
            self.g(path1("M23 392 Q30 389 38 392", "hair"))
            self.g(path1("M29 395 Q35 393 41 395", "hair"))
            self.g(f'<ellipse cx="62" cy="398" rx="4.5" ry="2.4" fill="var(--soft)" opacity=".55"/>')
            self.g(f'<ellipse cx="352" cy="404" rx="5" ry="2.6" fill="var(--soft)" opacity=".5"/>')
        else:
            tufts = [(14, 391), (30, 394), (48, 391), (60, 396), (350, 392), (362, 396), (374, 391)]
            for i, (tx, ty) in enumerate(tufts):
                self.g(path1(f"M{n(tx)} {ty} q-2 -6 0 -9", "grass"))
                self.g(path1(f"M{n(tx)} {ty} q2 -7 4 -9", "grass"))
                self.g(path1(f"M{n(tx)} {ty} q-5 -4 -6 -7", "grass"))
                if self.idx >= 2:
                    self.g(f'<circle cx="{n(tx + 3)}" cy="{n(ty - 10)}" r="1.6" fill="var(--light)" opacity=".9"/>')
        if self.idx >= 1:
            # 房子周围一圈碎石（通水通电后场地收拾过）
            r2 = rnd(f"gravel{self.idx}")
            pebbles = [f'<circle cx="{n(w)}" cy="{n(h)}" r="{n(r2.uniform(0.7, 1.6))}"/>'
                       for w, h in ((8, 402), (66, 420), (74, 448), (336, 426), (352, 452), (372, 410))]
            self.g(f'<g class="pebbles">{"".join(pebbles)}</g>')

    # -- 屋顶 / 阁楼 -----------------------------------------------------------------
    def draw_roof(self) -> None:
        # 烟囱（画在屋顶后面，只露出上半截）
        chim_x0, chim_x1 = 262.0, 288.0
        self.g(f'<rect x="{n(chim_x0)}" y="84" width="{n(chim_x1 - chim_x0)}" height="86" fill="var(--roof)"/>')
        self.g(sk(rect_pts(chim_x0, 84, chim_x1 - chim_x0, 86), "chim", "k", 0.6))
        if self.idx == 0:
            for yy in (100, 118, 136, 154):
                self.g(path1(f"M{n(chim_x0 + 1)} {yy} H{n(chim_x1 - 1)}", "hair"))
        else:
            for yy in (100, 116, 132):
                self.g(path1(f"M{n(chim_x0 + 1)} {yy} H{n(chim_x1 - 1)}", "brick-line"))
        self.g(f'<rect x="{n(chim_x0 - 6)}" y="78" width="{n(chim_x1 - chim_x0 + 12)}" height="8" fill="var(--roof)"/>')
        self.g(sk(rect_pts(chim_x0 - 6, 78, chim_x1 - chim_x0 + 12, 8), "chimcap", "k", 0.5))
        self.g(f'<line class="k" x1="{n(chim_x0 - 5)}" y1="86" x2="{n(chim_x1 + 5)}" y2="86"/>')

        # 烟囱冒烟：锅炉烧起来之后，房子才算“活着”
        if self.idx >= 1:
            for k, (sx, sy, ss) in enumerate(((272, 74, 5.0), (280, 60, 7.0), (270, 45, 9.0))):
                self.g(f'<path class="smoke" d="M{n(sx)} {n(sy)} q{n(-ss)} {n(-ss)} 0 {n(-2 * ss)} '
                       f'q{n(ss)} {n(-ss)} 0 {n(-2 * ss)}" opacity="{n(0.34 - k * 0.07)}"/>')

        # 阁楼净空
        self.g(fpoly(ATTIC, "var(--wall-hi)", "atticfill", 0.3))
        # 阁楼里的两根椽子：同一栋房子的结构
        self.g(path1(f"M{n(RIDGE_IN[0])} {n(RIDGE_IN[1] + 13)} L{n(LEAF_IN[0] + 10)} {n(CEIL_Y - 2)}", "rafter"))
        self.g(path1(f"M{n(RIDGE_IN[0])} {n(RIDGE_IN[1] + 13)} L{n(REAF_IN[0] - 10)} {n(CEIL_Y - 2)}", "rafter"))
        # 阁楼里的电控箱 / 大脑（⑧）
        self.g(self.draw_ctrlbox())
        # 屋面（剖面带）
        self.g(fpoly(ROOF_BAND, "var(--roof)", "rooffill", 0.35))
        if self.idx == 0:
            # 沿坡面垂直切的剖面线（屋面是混凝土板，不是铺瓦）
            for side in (0, 1):
                if side == 0:
                    a_out, b_out, a_in, b_in = EAVE_L, RIDGE, LEAF_IN, RIDGE_IN
                else:
                    a_out, b_out, a_in, b_in = EAVE_R, RIDGE, REAF_IN, RIDGE_IN
                t = 0.02
                while t < 0.99:
                    p_out = (a_out[0] + (b_out[0] - a_out[0]) * t, a_out[1] + (b_out[1] - a_out[1]) * t)
                    p_in = (a_in[0] + (b_in[0] - a_in[0]) * t, a_in[1] + (b_in[1] - a_in[1]) * t)
                    self.g(path1(f"M{n(p_out[0])} {n(p_out[1])} L{n(p_in[0])} {n(p_in[1])}", "hatch"))
                    t += 0.055
            # 毛坯屋顶：露出的模板缝 + 几根钢筋
            self.g(path1("M104 190 L140 168", "hair"))
            self.g(path1("M262 168 L300 186", "hair"))
            self.g(path1("M170 108 l4 -8 M238 108 l-4 -8", "rebar"))
            self.g(path1("M86 202 q2 -10 5 -13", "rebar"))
            self.g(path1("M320 202 q-2 -9 -5 -12", "rebar"))
        else:
            # 瓦：沿两坡的瓦缝 + 一条中缝，屋脊压顶
            for side in (0, 1):
                if side == 0:
                    a_out, b_out, a_in, b_in = EAVE_L, RIDGE, LEAF_IN, RIDGE_IN
                else:
                    a_out, b_out, a_in, b_in = EAVE_R, RIDGE, REAF_IN, RIDGE_IN
                for t in (0.10, 0.21, 0.32, 0.43, 0.54, 0.65, 0.76, 0.87):
                    p_out = (a_out[0] + (b_out[0] - a_out[0]) * t, a_out[1] + (b_out[1] - a_out[1]) * t)
                    p_in = (a_in[0] + (b_in[0] - a_in[0]) * t, a_in[1] + (b_in[1] - a_in[1]) * t)
                    self.g(path1(f"M{n(p_out[0])} {n(p_out[1])} L{n(p_in[0])} {n(p_in[1])}", "tile"))
            self.g(path1(f"M{n(EAVE_L[0])} {n(EAVE_L[1] - 8)} L{n(RIDGE[0])} {n(RIDGE[1] + 8)} L{n(EAVE_R[0])} {n(EAVE_R[1] - 8)}", "tile-mid"))
            # 檐口高光：让屋面有一点厚度
            self.g(path1(f"M{n(EAVE_L[0] + 8)} {n(EAVE_L[1] - 2)} L{n(RIDGE[0])} {n(RIDGE[1] + 7)} L{n(EAVE_R[0] - 8)} {n(EAVE_R[1] - 2)}", "roof-hi"))
            self.g(path1(f"M{n(RIDGE_IN[0])} {n(RIDGE_IN[1])} L{n(RIDGE[0])} {n(RIDGE[1])}", "ridge"))
        # 屋面轮廓双描边
        self.g(sk([EAVE_L, RIDGE, EAVE_R], "roofouter", "k", 0.5, closed=False))
        self.g(sk([LEAF_IN, RIDGE_IN, REAF_IN], "roofinner", "k2line", 0.5, closed=False))
        # 檐口线
        self.g(path1(f"M{n(EAVE_L[0])} {n(EAVE_L[1])} L{n(LEAF_IN[0])} {n(LEAF_IN[1])}", "k"))
        if self.idx == 0:
            self.g(path1(f"M{n(EAVE_L[0] + 3)} {n(EAVE_L[1] - 2)} L{n(RIDGE[0])} {n(RIDGE[1] + 5)} L{n(EAVE_R[0] - 3)} {n(EAVE_R[1] - 2)}", "roof-hi"))
        self.g(path1(f"M{n(EAVE_R[0])} {n(EAVE_R[1])} L{n(REAF_IN[0])} {n(REAF_IN[1])}", "k"))
        # 天花板（阁楼地板）：横梁 + 板缝
        self.g(path1(f"M{n(WALL_L0)} {n(CEIL_Y)} H{n(WALL_R1)}", "k"))
        for x in (118, 152, 186, 220, 254, 288):
            self.g(path1(f"M{x} {n(CEIL_Y)} v-4", "hair"))
        if self.idx == 0:
            self.g(path1("M112 204 l3 -8 l4 2", "rebar"))
            self.g(path1("M164 204 l2 -7 l5 1", "rebar"))
            self.g(path1("M244 204 l3 -8 l4 1", "rebar"))
            self.g(path1("M296 204 l-2 -7", "rebar"))
            self.g(path1("M120 208 L126 214", "rebar"))
            self.g(path1("M286 208 L280 214", "rebar"))

    def draw_ctrlbox(self) -> str:
        no = 8
        x, y, w, h = CTRLBOX
        if not self.has(no):
            return self.ghost_rect(x, y, w, h, "ctrlghost")
        out = [fpoly(rect_pts(x, y, w, h), "var(--metal)", "ctrlfill", 0.35)]
        out.append(sk(rect_pts(x, y, w, h), "ctrlbox", "k", 0.55))
        # 面板：三颗 LED + 一块小芯片
        out.append(f'<rect x="{n(x + 5)}" y="{n(y + 6)}" width="{n(w - 10)}" height="{n(h - 12)}" fill="var(--bs-ink)" opacity=".85"/>')
        for i, cx in enumerate((x + 10, x + 17, x + 24)):
            out.append(f'<circle cx="{n(cx)}" cy="{n(y + 13)}" r="1.8" fill="var(--light)"/>')
        out.append(f'<rect x="{n(x + 28)}" y="{n(y + 9)}" width="10" height="10" fill="none" stroke="var(--water)" stroke-width="1"/>')
        out.append(f'<path class="circuit" d="M{n(x + 33)} {n(y + 14)} l6 0 l0 6 M{n(x + 33)} {n(y + 14)} l-4 -5"/>')
        # 从盒子里爬出来的「神经元」走线
        out.append(self.pipe(f"M{n(x + w)} {n(y + 8)} l14 0 l0 10", "var(--hot)", 1.6, "wisp"))
        out.append(self.pipe(f"M{n(x)} {n(y + 26)} l-12 0 l0 -8", "var(--water)", 1.6, "wisp"))
        return "".join(out)

    # -- 墙体 / 楼板 / 地下室 ---------------------------------------------------------
    def draw_structure(self) -> None:
        # 背墙
        self.g(f'<rect x="{n(WALL_L1)}" y="{n(CEIL_Y)}" width="{n(WALL_R0 - WALL_L1)}" height="{n(FLOOR_Y - CEIL_Y)}" fill="var(--wall)"/>')
        if self.idx == 0:
            # 毛坯：模板缝、对拉螺栓孔、裂缝
            for yy in (250, 296, 342):
                self.g(path1(f"M{n(WALL_L1 + 3)} {yy} H{n(WALL_R0 - 3)}", "formline"))
            for xx in (126, 170, 214, 258, 296):
                self.g(f'<circle cx="{xx}" cy="268" r="1.7" fill="none" stroke="var(--soft)" stroke-width=".9"/>')
                self.g(f'<circle cx="{xx}" cy="332" r="1.7" fill="none" stroke="var(--soft)" stroke-width=".9"/>')
            self.g(path1("M152 250 l7 12 l-5 12 l6 13 l-4 14", "crack"))
            self.g(path1("M262 296 l-8 11 l5 10 l-3 12", "crack"))
            self.g(path1("M108 350 q18 -10 34 -2 q16 8 32 0", "formline"))
            # 未砌完的一小段砌块墙
            for row in range(3):
                for col in range(4):
                    bx = 104 + col * 12 + (row % 2) * 6
                    by = 300 + row * 9
                    self.g(f'<rect x="{n(bx)}" y="{n(by)}" width="11" height="8" fill="none" stroke="var(--soft)" stroke-width=".6" opacity=".75"/>')
            self.g(path1("M104 292 H156", "hair"))
            # 墙上的湿渍（毛坯返潮）
            for (sx, sy, sw, sh, op) in ((122, 232, 24, 38, .13), (252, 252, 28, 32, .10), (198, 336, 38, 24, .08)):
                self.g(f'<ellipse cx="{sx}" cy="{sy}" rx="{sw}" ry="{sh}" fill="var(--soft)" opacity="{op}"/>')
        else:
            # 已抹灰：踢脚线 + 一点墙面纹理
            self.g(f'<rect x="{n(WALL_L1)}" y="382" width="{n(WALL_R0 - WALL_L1)}" height="8" fill="var(--wall-hi)"/>')
            self.g(path1(f"M{n(WALL_L1)} 382 H{n(WALL_R0)}", "hair"))
            self.g(path1("M112 250 q26 -6 52 0 q26 6 52 0 q26 -6 52 0", "formline"))
        if self.idx >= 2:
            # 挂画 / 壁灯的小点缀（智能家居阶段的一点点生活气）
            self.g(f'<rect x="150" y="238" width="10" height="14" fill="var(--water)" opacity=".35" stroke="var(--soft)" stroke-width=".8"/>')
        # 背墙的侧向 / 顶部阴影：剖面里的一点纵深
        self.g(f'<rect x="{n(WALL_L1)}" y="{n(CEIL_Y)}" width="{n(WALL_R0 - WALL_L1)}" height="{n(FLOOR_Y - CEIL_Y)}" '
               f'fill="url(#shadeX{self.idx})"/>')
        self.g(f'<rect x="{n(WALL_L1)}" y="{n(CEIL_Y)}" width="{n(WALL_R0 - WALL_L1)}" height="46" '
               f'fill="url(#shadeY{self.idx})"/>')
        # 墙（剖面带）+ 斜剖线
        for name, x0, x1 in (("wl", WALL_L0, WALL_L1), ("wr", WALL_R0, WALL_R1)):
            self.g(f'<rect x="{n(x0)}" y="{n(CEIL_Y)}" width="{n(x1 - x0)}" height="{n(FLOOR_Y - CEIL_Y)}" fill="var(--floor)"/>')
            cid = self.clip(name, x0, CEIL_Y, x1 - x0, FLOOR_Y - CEIL_Y)
            self.hatch(cid, x0, CEIL_Y, x1 - x0, FLOOR_Y - CEIL_Y, 7.0, name + "h")
            self.g(sk(rect_pts(x0, CEIL_Y, x1 - x0, FLOOR_Y - CEIL_Y), name + "box", "k", 0.5))
        # 楼板（剖面）+ 剖线
        self.g(f'<rect x="{n(WALL_L0)}" y="{n(FLOOR_Y)}" width="{n(WALL_R1 - WALL_L0)}" height="{n(SLAB_B - FLOOR_Y)}" fill="var(--slab)"/>')
        cid = self.clip("slab", WALL_L0, FLOOR_Y, WALL_R1 - WALL_L0, SLAB_B - FLOOR_Y)
        self.hatch(cid, WALL_L0, FLOOR_Y, WALL_R1 - WALL_L0, SLAB_B - FLOOR_Y, 6.0, "slabh")
        self.g(sk(rect_pts(WALL_L0, FLOOR_Y, WALL_R1 - WALL_L0, SLAB_B - FLOOR_Y), "slabbox", "k", 0.5))
        # ① 地基/场地：L1 是毛边泥地；L2 起放线、找平、做散水
        if self.idx >= 1:
            self.g(path1(f"M{n(WALL_L0 - 6)} {n(SLAB_B + 1)} H{n(WALL_R1 + 6)}", "k2line"))
            self.g(path1(f"M{n(WALL_L0 - 8)} {n(FLOOR_Y - 1)} H{n(WALL_L0 - 1)} M{n(WALL_R1 + 1)} {n(FLOOR_Y - 1)} H{n(WALL_R1 + 8)}", "fine"))
            self.g(path1("M62 404 v-14", "fine"))
            self.g('<path d="M62 390 l-3 -6 h6 Z" fill="none" class="fine"/>')
            self.g(path1("M58 396 h8", "hair"))
        else:
            self.g(path1(f"M{n(WALL_L0 - 2)} {n(SLAB_B)} l-4 3 l2 4 M{n(WALL_R1 + 2)} {n(SLAB_B)} l4 3", "crack"))

        # 地面装修层（只在地板顶面那一薄条上换材质）
        if self.idx == 0:
            self.g(f'<rect x="{n(WALL_L1)}" y="384" width="{n(WALL_R0 - WALL_L1)}" height="6" fill="var(--floor)"/>')
            self.g(path1(f"M{n(WALL_L1)} 384 H{n(WALL_R0)}", "hair"))
            r4 = rnd("aggregate")
            agg = "".join(f'<circle cx="{n(r4.uniform(WALL_L1 + 6, WALL_R0 - 6))}" cy="{n(r4.uniform(385, 389))}" '
                          f'r="{n(r4.uniform(.35, .85))}" fill="var(--soft)" opacity=".6"/>' for _ in range(22))
            self.g(f'<g class="aggregate">{agg}</g>')
        else:
            self.g(f'<rect x="{n(WALL_L1)}" y="383" width="{n(WALL_R0 - WALL_L1)}" height="7" fill="var(--floor)"/>')
            for x in range(int(WALL_L1) + 10, int(WALL_R0), 26):
                self.g(path1(f"M{x} 383 v7", "hair"))
            self.g(path1(f"M{n(WALL_L1)} 383 H{n(WALL_R0)}", "hair"))

        # 地下室：背墙 + 两侧剖面墙 + 底板
        self.g(f'<rect x="{n(BS_IN0)}" y="{n(BS_Y0)}" width="{n(BS_IN1 - BS_IN0)}" height="{n(BS_B - BS_Y0)}" fill="var(--bs)"/>')
        for yy in (422, 444, 462):
            self.g(path1(f"M{n(BS_IN0 + 2)} {yy} H{n(BS_IN1 - 2)}", "bs-line"))
        for name, x0, x1 in (("bsl", BS_X0, BS_IN0), ("bsr", BS_IN1, BS_X1)):
            self.g(f'<rect x="{n(x0)}" y="{n(BS_Y0)}" width="{n(x1 - x0)}" height="{n(BS_FLOOR_B - BS_Y0)}" fill="var(--slab)"/>')
            cid = self.clip(name, x0, BS_Y0, x1 - x0, BS_FLOOR_B - BS_Y0)
            self.hatch(cid, x0, BS_Y0, x1 - x0, BS_FLOOR_B - BS_Y0, 6.5, name + "h")
            self.g(sk(rect_pts(x0, BS_Y0, x1 - x0, BS_FLOOR_B - BS_Y0), name + "box", "k", 0.45))
        self.g(f'<rect x="{n(BS_X0)}" y="{n(BS_B)}" width="{n(BS_X1 - BS_X0)}" height="{n(BS_FLOOR_B - BS_B)}" fill="var(--slab)"/>')
        cid = self.clip("bsf", BS_X0, BS_B, BS_X1 - BS_X0, BS_FLOOR_B - BS_B)
        self.hatch(cid, BS_X0, BS_B, BS_X1 - BS_X0, BS_FLOOR_B - BS_B, 6.0, "bsfh")
        self.g(path1(f"M{n(BS_IN0)} {n(BS_B)} H{n(BS_IN1)}", "k"))
        self.g(path1(f"M{n(BS_X0)} {n(BS_B)} H{n(BS_X1)}", "hair"))

    # -- 门窗 -------------------------------------------------------------------------
    def draw_window(self) -> None:
        x0, x1, y0, y1 = WIN_X0, WIN_X1, WIN_Y0, WIN_Y1
        # 窗洞 / 玻璃
        if self.idx == 0:
            self.g(f'<rect x="{n(x0 + 4)}" y="{n(y0 + 4)}" width="{n(x1 - x0 - 8)}" height="{n(y1 - y0 - 8)}" fill="var(--paper)"/>')
            for i in range(4):
                yy = y0 + 10 + i * 12
                self.g(path1(f"M{n(x0 + 8)} {yy} l9 9", "window-void"))
        else:
            self.g(f'<rect x="{n(x0 + 4)}" y="{n(y0 + 4)}" width="{n(x1 - x0 - 8)}" height="{n(y1 - y0 - 8)}" fill="var(--glass)"/>')
            self.g(path1(f"M{n(x0 + 9)} {n(y1 - 8)} l16 -40", "glass-line"))
            self.g(path1(f"M{n(x0 + 17)} {n(y1 - 8)} l16 -40", "glass-line"))
        if self.idx == 3:
            # 页面：玻璃窗变成一块亮着的「室内屏」，屏上是查询结果的小图表
            gx0, gy0 = x0 + 6, y0 + 6
            self.g(f'<rect x="{n(gx0)}" y="{n(gy0)}" width="{n(x1 - x0 - 12)}" height="{n(y1 - y0 - 12)}" fill="var(--light)" opacity=".30"/>')
            for i, bh in enumerate((7, 12, 9, 15)):
                bx = gx0 + 6 + i * 7
                self.g(f'<rect x="{n(bx)}" y="{n(gy0 + 26 - bh)}" width="4" height="{bh}" fill="var(--accent)" opacity=".8"/>')
            self.g(path1(f"M{n(gx0 + 5)} {n(gy0 + 30)} H{n(gx0 + 34)}", "screen-line"))
            for i, xx in enumerate((gx0 + 33, gx0 + 38, gx0 + 43)):
                self.g(f'<circle cx="{xx}" cy="{n(gy0 + 8)}" r="1.4" fill="var(--hot)"/>')
            # 右下角一格监控画面：门口摄像头 / 红色录制点
            tx, ty, tw, th = x0 + 33.0, y0 + 31.0, 21.0, 20.0
            self.g(f'<rect x="{n(tx)}" y="{n(ty)}" width="{n(tw)}" height="{n(th)}" fill="var(--bs-ink)" opacity=".92"/>')
            self.g(f'<rect x="{n(tx + 6)}" y="{n(ty + 5)}" width="8" height="11" fill="none" stroke="var(--light)" stroke-width=".8" opacity=".85"/>')
            self.g(f'<circle cx="{n(tx + 3.6)}" cy="{n(ty + 10)}" r="1.7" fill="var(--light)" opacity=".85"/>')
            self.g(f'<circle cx="{n(tx + tw - 3.6)}" cy="{n(ty + 3.6)}" r="1.3" fill="var(--red)"/>')
            self.g(f'<path class="cctv-line" d="M{n(tx + 2)} {n(ty + 14)} H{n(tx + tw - 2)}"/>')
            self.g(f'<circle class="screen-glow" cx="{n((x0 + x1) / 2)}" cy="{n((y0 + y1) / 2)}" r="26"/>')
        # 窗台
        self.g(f'<rect x="{n(x0 - 4)}" y="{n(y1)}" width="{n(x1 - x0 + 8)}" height="3.4" fill="var(--floor)"/>')
        self.g(path1(f"M{n(x0 - 3)} {n(y1 + 3.4)} H{n(x1 + 3)}", "hair"))
        # 窗框 + 中梃
        fw = 3.4
        self.g(sk(rect_pts(x0, y0, x1 - x0, y1 - y0), "winframe", "k", 0.55))
        self.g(sk(rect_pts(x0 + fw, y0 + fw, x1 - x0 - 2 * fw, y1 - y0 - 2 * fw), "wininner", "fine", 0.4))
        self.g(path1(f"M{n((x0 + x1) / 2)} {n(y0 + fw)} V{n(y1 - fw)}", "fine"))
        self.g(path1(f"M{n(x0 + fw)} {n((y0 + y1) / 2)} H{n(x1 - fw)}", "fine"))
        if self.idx == 0:
            self.g(self.ghost_rect(x0 + 5, y0 + 5, x1 - x0 - 10, y1 - y0 - 10, "winghost"))

    def draw_door(self) -> None:
        x0, x1, y0, y1 = DOOR_X0, DOOR_X1, DOOR_Y0, DOOR_Y1
        if self.idx == 0:
            # 毛坯：门洞还空着
            self.g(f'<rect x="{n(x0 + 3)}" y="{n(y0 + 3)}" width="{n(x1 - x0 - 6)}" height="{n(y1 - y0 - 3)}" fill="var(--soft)" opacity=".30"/>')
            self.g(self.ghost_rect(x0 + 6, y0 + 6, x1 - x0 - 12, y1 - y0 - 12, "doorghost"))
        else:
            self.g(f'<rect x="{n(x0 + 3)}" y="{n(y0 + 3)}" width="{n(x1 - x0 - 6)}" height="{n(y1 - y0 - 3)}" fill="var(--rust)" opacity=".55"/>')
            self.g(path1(f"M{n(x0 + 8)} {n(y0 + 12)} V{n(y1 - 22)} q0 -4 4 -4 h{n(x1 - x0 - 20)} q4 0 4 4 V{n(y1 - 22)}", "doorpanel"))
            self.g(path1(f"M{n(x0 + 8)} {n(y0 + 34)} V{n(y1 - 14)} q0 -4 4 -4 h{n(x1 - x0 - 20)} q4 0 4 4 V{n(y1 - 14)}", "doorpanel"))
            self.g(f'<circle cx="{n(x1 - 9)}" cy="{n((y0 + y1) / 2)}" r="1.9" fill="var(--ink)"/>')
        self.g(sk(rect_pts(x0, y0, x1 - x0, y1 - y0), "doorframe", "k", 0.55))
        if self.idx >= 3:
            # 物业安防阶段：门口摄像头 + 门禁读卡器
            self.draw_camera()
            self.draw_cardreader()

    def draw_camera(self) -> None:
        cx, cy = 291.0, 304.0
        self.g(path1(f"M{n(cx)} {n(cy + 6)} V{n(DOOR_Y0 - 4)}", "k"))
        self.g(f'<rect x="{n(cx - 12)}" y="{n(cy - 10)}" width="24" height="10" rx="4" fill="var(--metal)"/>')
        self.g(sk(rect_pts(cx - 12, cy - 10, 24, 10), "cam", "k", 0.4))
        self.g(f'<circle cx="{n(cx - 8)}" cy="{n(cy - 15)}" r="4.4" fill="var(--bs)"/>')
        self.g(f'<circle cx="{n(cx - 8)}" cy="{n(cy - 15)}" r="2" fill="var(--ink)"/>')
        self.g(f'<circle cx="{n(cx - 7)}" cy="{n(cy - 16)}" r=".9" fill="var(--light)"/>')
        self.g(f'<circle cx="{n(cx + 7)}" cy="{n(cy - 5)}" r="1.5" fill="var(--red)"/>')
        self.g(path1(f"M{n(cx - 8)} {n(cy - 20)} l6 -6 M{n(cx - 4)} {n(cy - 22)} l4 -4", "cam-signal"))

    def draw_cardreader(self) -> None:
        x, y = 260.0, 328.0
        self.g(f'<rect x="{n(x)}" y="{n(y)}" width="11" height="20" rx="1.6" fill="var(--metal)"/>')
        self.g(sk(rect_pts(x, y, 11, 20), "reader", "k", 0.3))
        self.g(f'<rect x="{n(x + 2.5)}" y="{n(y + 3)}" width="6" height="3.6" fill="var(--bs)"/>')
        self.g(f'<circle cx="{n(x + 5.5)}" cy="{n(y + 13)}" r="1.8" fill="var(--light)"/>')
        self.g(path1(f"M{n(x + 14)} {n(y + 7)} q4 -2 0 -5 M{n(x + 16)} {n(y + 9)} q6 -4 0 -9", "card-wave"))

    # -- 管线 / 设备 ------------------------------------------------------------------
    def draw_pipes(self) -> None:
        if self.idx == 0:
            # 预留：天花板上两个灯位（虚线吊线 + 空圈），墙面两截还没接的管口
            for lx in (150.0, 284.0):
                self.g(path1(f"M{n(lx)} {n(CEIL_Y)} v13", "ghost"))
                self.g(f'<circle class="ghost" cx="{n(lx)}" cy="{n(CEIL_Y + 20)}" r="6"/>')
            self.g(self.pipe("M78 300 H61", "var(--soft)", 2.4, "ghostpipe"))
            self.g(f'<circle cx="60" cy="300" r="2.6" fill="none" stroke="var(--soft)" stroke-width="1.1"/>')
            self.g(self.pipe("M78 258 H66", "var(--soft)", 1.8, "ghostpipe"))
        # 墙里走的管线（通水通电阶段起）
        if self.idx >= 1:
            for base in (84.0, 323.5):
                self.g(self.pipe(f"M{n(base)} {n(CEIL_Y + 10)} V{n(FLOOR_Y - 6)}", "var(--water)", 1.8))
                self.g(self.pipe(f"M{n(base + 6.5)} {n(CEIL_Y + 10)} V{n(FLOOR_Y - 6)}", "var(--hot)", 1.8))
                for yy in (248, 330):
                    self.g(f'<circle cx="{n(base + 3.2)}" cy="{yy}" r="2.2" fill="var(--metal)"/>')
            # 沿天花板的一根线管
            self.g(self.pipe(f"M{n(WALL_L1)} {n(CEIL_Y + 7)} H{n(150)}", "var(--hot)", 1.7, "wisp"))
            self.g(self.pipe(f"M{n(258)} {n(CEIL_Y + 7)} H{n(WALL_R0)}", "var(--water)", 1.7, "wisp"))

        # 配电箱（通水通电起）：挂在外墙电表上方，电先过箱子再进屋
        if self.idx >= 1:
            bx, by, bw, bh = 48.0, 292.0, 30.0, 28.0
            self.g(f'<rect x="{n(bx)}" y="{n(by)}" width="{n(bw)}" height="{n(bh)}" rx="2" fill="var(--metal)"/>')
            self.g(sk(rect_pts(bx, by, bw, bh), "breaker", "k", 0.4))
            self.g(f'<rect x="{n(bx + 4)}" y="{n(by + 4)}" width="{n(bw - 8)}" height="{n(bh - 8)}" fill="var(--bs-ink)" opacity=".9"/>')
            for i in range(4):
                self.g(f'<rect x="{n(bx + 6 + i * 5.2)}" y="{n(by + 7)}" width="3" height="6" fill="var(--light)" opacity=".9"/>')
                self.g(f'<rect x="{n(bx + 6 + i * 5.2)}" y="{n(by + 16)}" width="3" height="3" fill="var(--hot)" opacity=".85"/>')
            self.g(self.pipe(f"M{n(bx + bw)} {n(by + 14)} H{n(WALL_L0)}", "var(--hot)", 1.6, "wisp"))

        # 锅炉烟道（⑤）：通水通电起
        if self.has(5):
            self.g(f'<rect x="114" y="{n(CEIL_Y)}" width="10" height="84" fill="var(--metal)"/>')
            self.g(sk(rect_pts(114, CEIL_Y, 10, 84), "flue", "k", 0.4))
            self.g(path1(f"M120 {n(CEIL_Y)} v84", "hair"))
        # 水箱 → 楼板 与 锅炉 → 水龙头 的热水管（②级后半段就有了雏形，⑫ 完整总成到 L4）
        if self.has(4):
            self.g(self.pipe(f"M{n(TANK[0] + 22)} {n(TANK[1] + TANK[3])} V{n(FLOOR_Y)}", "var(--water)", 2.6))
            self.g(self.pipe(f"M{n(TANK[0] + 22)} {n(TANK[1])} V{n(TANK[1] - 16)} H{n(WALL_R0)}", "var(--hot)", 2.2))
        if self.has(5) and self.has(4):
            self.g(self.pipe(f"M{n(BOILER[0] + BOILER[2])} {n(320)} H{n(TANK[0] - 6)}", "var(--hot)", 2.4))
        if self.has(10) and self.has(4):
            self.g(self.pipe(f"M{n(TANK[0] + 34)} {n(346)} H{n(230)} V{n(SINK[1] + 6)}", "var(--hot)", 2.2))

        # ⑨ 市政进水 + 只读水表（L4 才长出来）
        if self.has(9):
            self.g(self.pipe("M2 430 H34 Q44 430 46 424 V364", "var(--water)", 3.4))
            self.g(self.pipe("M62 364 V390 Q62 412 78 418 L98 430", "var(--water)", 3.4))
            x, y, w, h = METER
            self.g(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="2.5" fill="var(--metal)"/>')
            self.g(sk(rect_pts(x, y, w, h), "meterbox", "k", 0.45))
            self.g(f'<circle cx="{n(x + 11)}" cy="{n(y + 12)}" r="7.6" fill="var(--light)"/>')
            self.g(f'<circle cx="{n(x + 11)}" cy="{n(y + 12)}" r="7.6" fill="none" stroke="var(--ink)" stroke-width="1"/>')
            self.g(path1(f"M{n(x + 11)} {n(y + 12)} l4 -3.4", "meterneedle"))
            self.g(path1(f"M{n(x + 21)} {n(y + 6)} h6 M{n(x + 21)} {n(y + 10)} h6 M{n(x + 21)} {n(y + 14)} h6", "meterdial"))
            # 只读：表盘上挂一把小锁
            self.g(f'<rect x="{n(x + 19)}" y="{n(y + 17)}" width="7" height="6" rx="1" fill="var(--red)"/>')
            self.g(path1(f"M{n(x + 21)} {n(y + 17)} v-2.6 q2.2 -2.4 4.4 0 V{n(y + 17)}", "lock"))
        else:
            self.g(self.ghost_rect(*METER, "meterghost"))
            self.g(self.pipe("M2 430 H34 Q44 430 46 424 V364", "var(--soft)", 1.4, "ghostpipe"))
            self.g(self.pipe("M62 364 V390 Q62 412 78 418 L98 430", "var(--soft)", 1.4, "ghostpipe"))

        # ⑫ 入户管线总成（地下室分水器 + 上穿楼板的两根立管；L4 才长出来）
        x, y, w, h = MANIFOLD
        if self.has(12):
            self.g(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="2" fill="var(--metal)"/>')
            self.g(sk(rect_pts(x, y, w, h), "manifold", "k", 0.4))
            for i, vx in enumerate((x + 8, x + 22, x + 36, x + 48)):
                self.g(f'<circle cx="{n(vx)}" cy="{n(y + h / 2)}" r="2.6" fill="var(--hot)"/>')
            self.g(self.pipe(f"M{n(x - 6)} {n(y + 5)} H{n(x)}", "var(--water)", 3.2))
            self.g(self.pipe(f"M{n(x + 12)} {n(y)} V{n(BOILER[1] + BOILER[3])}", "var(--water)", 2.6))
            self.g(self.pipe(f"M{n(x + 40)} {n(y)} V{n(TANK[1] + TANK[3] - 2)}", "var(--hot)", 2.6))
            self.g(self.pipe(f"M{n(x - 6)} {n(y + 5)} Q{n(x - 14)} {n(y + 5)} {n(x - 14)} {n(y + 16)} V{n(BS_B)}", "var(--hot)", 2.0))
        else:
            self.g(self.ghost_rect(x, y, w, h, "manifoldghost"))
            self.g(self.pipe(f"M{n(x + 12)} {n(y)} V{n(BOILER[1] + BOILER[3])}", "var(--soft)", 1.3, "ghostpipe"))
            self.g(self.pipe(f"M{n(x + 40)} {n(y)} V{n(TANK[1] + TANK[3] - 2)}", "var(--soft)", 1.3, "ghostpipe"))

    def draw_boiler(self) -> None:
        no = 5
        x, y, w, h = BOILER
        if not self.has(no):
            self.g(self.ghost_rect(x, y, w, h, "boilerghost*" + str(self.idx)))
            self.g(f'<circle cx="{n(x + w / 2)}" cy="{n(y + h - 20)}" r="6" fill="none" stroke="var(--soft)" stroke-width="1" stroke-dasharray="2 3"/>')
            return
        self.g(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="7" fill="var(--metal)"/>')
        self.g(sk(rect_pts(x, y, w, h), "boiler", "k", 0.5))
        self.g(f'<rect x="{n(x + 6)}" y="{n(y + 6)}" width="{n(w - 12)}" height="{n(h - 26)}" rx="4" fill="var(--bs-ink)" opacity=".9"/>')
        # 炉火小窗
        self.g(f'<circle cx="{n(x + w / 2)}" cy="{n(y + h - 22)}" r="7.5" fill="var(--hot)"/>')
        self.g(f'<circle cx="{n(x + w / 2)}" cy="{n(y + h - 22)}" r="15" class="heat-glow"/>')
        self.g(path1(f"M{n(x + w / 2 - 3)} {n(y + h - 19)} q3 -4 6 0 q-3 3 -6 0", "flame"))
        # 压力表 + 两个接口
        self.g(f'<circle cx="{n(x + 11)}" cy="{n(y + 13)}" r="4.6" fill="var(--light)"/>')
        self.g(f'<circle cx="{n(x + 11)}" cy="{n(y + 13)}" r="4.6" fill="none" stroke="var(--ink)" stroke-width=".8"/>')
        self.g(path1(f"M{n(x + 11)} {n(y + 13)} l2.6 -1.8", "meterneedle"))
        self.g(f'<circle cx="{n(x + w - 9)}" cy="{n(y + 12)}" r="2.2" fill="var(--bs)"/>')
        self.g(f'<path d="M{n(x + 8)} {n(y - 4)} q4 -5 8 0" class="steam"/>')
        self.g(f'<path d="M{n(x + 20)} {n(y - 3)} q4 -5 8 0" class="steam"/>')
        if self.fresh(no) and self.idx > 0:
            self.g(f'<circle class="new-glow" cx="{n(x + w / 2)}" cy="{n(y + h / 2)}" r="20"/>')
            self.g(f'<path class="spark" d="M{n(x + w + 3)} {n(y - 8)} l1.6 4.4 l4.4 1.6 l-4.4 1.6 l-1.6 4.4 l-1.6 -4.4 l-4.4 -1.6 l4.4 -1.6 Z"/>')

    def draw_tank(self) -> None:
        no = 4
        x, y, w, h = TANK
        cx = x + w / 2
        if not self.has(no):
            self.g(self.ghost_rect(x, y, w, h, "tankghost*" + str(self.idx)))
            self.g(f'<ellipse class="ghost" cx="{n(cx)}" cy="{n(y)}" rx="{n(w / 2)}" ry="5"/>')
            return
        # 圆柱水箱：上盖椭圆 + 桶身 + 水位
        body = f'<path d="M{n(x)} {n(y)} V{n(y + h - 4)} A{n(w / 2)} 6 0 0 0 {n(x + w)} {n(y + h - 4)} V{n(y)} Z" fill="var(--water)" opacity=".28"/>'
        self.g(body)
        self.g(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h - 4)}" fill="none"/>')
        self.g(f'<path d="M{n(x)} {n(y + 18)} H{n(x + w)} V{n(y + h - 4)} A{n(w / 2)} 6 0 0 1 {n(x)} {n(y + h - 4)} Z" fill="var(--water)" opacity=".55"/>')
        self.g(f'<path d="M{n(x)} {n(y + 18)} H{n(x + w)}" stroke="var(--water)" stroke-width="1.6"/>')
        self.g(path1(f"M{n(x)} {n(y)} V{n(y + h - 4)} A{n(w / 2)} 6 0 0 0 {n(x + w)} {n(y + h - 4)} V{n(y)}", "k"))
        self.g(f'<ellipse cx="{n(cx)}" cy="{n(y)}" rx="{n(w / 2)}" ry="5.4" fill="var(--floor)"/>')
        self.g(f'<ellipse class="k" cx="{n(cx)}" cy="{n(y)}" rx="{n(w / 2)}" ry="5.4" fill="none"/>')
        self.g(f'<ellipse class="k2" cx="{n(cx + 0.5)}" cy="{n(y - 0.4)}" rx="{n(w / 2 + 0.3)}" ry="5.6" fill="none"/>')
        self.g(f'<rect x="{n(cx - 5)}" y="{n(y - 7)}" width="10" height="5" rx="1.5" fill="var(--metal)"/>')
        self.g(path1(f"M{n(x + 6)} {n(y + 18)} h4 M{n(x + 6)} {n(y + 30)} h4 M{n(x + 6)} {n(y + 42)} h4", "hair"))
        if self.fresh(no):
            self.g(f'<circle class="new-glow" cx="{n(cx)}" cy="{n(y + h / 2)}" r="21"/>')
            self.g(f'<path class="spark" d="M{n(x - 8)} {n(y + 26)} l1.5 4 l4 1.5 l-4 1.5 l-1.5 4 l-1.5 -4 l-4 -1.5 l4 -1.5 Z"/>')

    def draw_rack(self) -> None:
        no = 3
        x, y, w, h = RACK
        if not self.has(no):
            self.g(self.ghost_rect(x, y, w, h, "rackghost*" + str(self.idx)))
            for i in range(1, 3):
                self.g(path1(f"M{n(x)} {n(y + i * h / 3)} H{n(x + w)}", "ghost"))
            return
        self.g(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" fill="none"/>')
        # 立柱 + 三层隔板
        self.g(f'<rect x="{n(x)}" y="{n(y)}" width="5" height="{n(h)}" fill="var(--rust)"/>')
        self.g(f'<rect x="{n(x + w - 5)}" y="{n(y)}" width="5" height="{n(h)}" fill="var(--rust)"/>')
        for i in range(1, 4):
            yy = y + i * h / 4
            self.g(f'<rect x="{n(x)}" y="{n(yy - 2)}" width="{n(w)}" height="3.6" fill="var(--rust)" opacity=".85"/>')
            self.g(path1(f"M{n(x)} {n(yy)} H{n(x + w)}", "rackline"))
        # 5 个卷宗 / 文件盒 = 5 张表
        for i in range(5):
            fx = x + 8 + i * 13.2
            fh = 12 + (i % 3) * 3
            self.g(f'<rect x="{n(fx)}" y="{n(y + (h / 4) - fh - 1)}" width="9" height="{fh}" fill="var(--light)" opacity="{n(0.6 + 0.07 * i)}" stroke="var(--bs-ink)" stroke-width=".8"/>')
            self.g(path1(f"M{n(fx + 1.5)} {n(y + h / 4 - fh + 2)} h6", "hair"))
        for i in range(3):
            bx = x + 12 + i * 20
            self.g(f'<rect x="{n(bx)}" y="{n(y + h / 2 - 10)}" width="15" height="9" fill="var(--bs-ink)" opacity=".7" stroke="var(--soft)" stroke-width=".7"/>')
        if self.fresh(no):
            self.g(f'<circle class="new-glow" cx="{n(x + w / 2)}" cy="{n(y + h / 2)}" r="20"/>')

    def draw_router(self) -> None:
        no = 6
        x, y, w, h = ROUTER
        if not self.has(no):
            self.g(self.ghost_rect(x, y, w, h, "routerghost*" + str(self.idx)))
            self.g(path1(f"M{n(x + 5)} {n(y)} l-3 -10 M{n(x + w - 5)} {n(y)} l3 -10", "ghost"))
            return
        # 搁板
        self.g(f'<rect x="{n(x - 4)}" y="{n(y + h)}" width="{n(w + 8)}" height="3.4" fill="var(--rust)"/>')
        self.g(path1(f"M{n(x)} {n(y + h + 3)} l-4 8 M{n(x + w)} {n(y + h + 3)} l4 8", "hair"))
        # 路由器
        self.g(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="2.4" fill="var(--metal)"/>')
        self.g(sk(rect_pts(x, y, w, h), "router", "k", 0.4))
        self.g(path1(f"M{n(x + 5)} {n(y)} l-3 -11", "antenna"))
        self.g(path1(f"M{n(x + w - 5)} {n(y)} l3 -11", "antenna"))
        for i, col in enumerate(("var(--light)", "var(--hot)", "var(--water)")):
            self.g(f'<circle cx="{n(x + 6 + i * 5)}" cy="{n(y + h - 4)}" r="1.5" fill="{col}"/>')
        self.g(f'<path class="wifi" d="M{n(x + w / 2 - 5)} {n(y - 12)} q5 -6 10 0"/>')
        self.g(f'<path class="wifi" d="M{n(x + w / 2 - 9)} {n(y - 16)} q9 -10 18 0"/>')
        if self.fresh(no):
            self.g(f'<circle class="new-glow" cx="{n(x + w / 2)}" cy="{n(y + h / 2)}" r="19"/>')

    def draw_sensor(self) -> None:
        no = 7
        cx, cy = SENSOR
        if not self.has(no):
            self.g(f'<path class="ghost" d="M{n(cx - 8)} {n(cy)} q8 8 16 0"/>')
            self.g(path1(f"M{n(cx)} {n(cy - 5)} V{n(cy)}", "ghost"))
            return
        self.g(f'<rect x="{n(cx - 3)}" y="{n(cy - 5)}" width="6" height="5" rx="1" fill="var(--metal)"/>')
        self.g(f'<path d="M{n(cx - 8)} {n(cy)} q8 8 16 0 Z" fill="var(--metal)"/>')
        self.g(f'<path class="k" d="M{n(cx - 8)} {n(cy)} q8 8 16 0 Z" fill="none"/>')
        self.g(f'<circle cx="{n(cx)}" cy="{n(cy + 2)}" r="1.8" fill="var(--light)"/>')
        # 「听懂话」的声波
        self.g(f'<path class="wave" d="M{n(cx - 13)} {n(cy + 6)} q-6 8 0 16"/>')
        self.g(f'<path class="wave" d="M{n(cx - 17)} {n(cy + 3)} q-8 11 0 22"/>')
        self.g(f'<path class="wave" d="M{n(cx + 13)} {n(cy + 6)} q6 8 0 16"/>')
        self.g(f'<path class="wave" d="M{n(cx + 17)} {n(cy + 3)} q8 11 0 22"/>')
        if self.fresh(no):
            self.g(f'<circle class="new-glow" cx="{n(cx)}" cy="{n(cy + 8)}" r="19"/>')

    def draw_sink(self) -> None:
        no = 10
        x, y, w, h = SINK
        if not self.has(no):
            self.g(self.ghost_rect(x, y, w, h, "sinkghost*" + str(self.idx)))
            self.g(path1(f"M{n(x + 18)} {n(y)} V{n(y - 16)} q0 -4 4 -4 h8", "ghost"))
            return
        # 台盆柜
        self.g(f'<rect x="{n(x)}" y="{n(y + 4)}" width="{n(w)}" height="{n(h - 4)}" fill="var(--rust)" opacity=".75"/>')
        self.g(sk(rect_pts(x, y + 4, w, h - 4), "vanity", "k", 0.5))
        self.g(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="5" fill="var(--floor)"/>')
        self.g(path1(f"M{n(x)} {n(y)} H{n(x + w)}", "k"))
        self.g(path1(f"M{n(x + w / 2)} {n(y + 7)} V{n(y + h - 3)}", "hair"))
        for dx in (10, w - 10):
            self.g(f'<circle cx="{n(x + dx)}" cy="{n(y + 18)}" r="1.6" fill="var(--bs-ink)"/>')
        # 水龙头：竖管 + 弯头 + 出水口
        fx = x + 22
        self.g(f'<rect x="{n(fx - 2.6)}" y="{n(y - 18)}" width="5.2" height="20" rx="1.6" fill="var(--metal)"/>')
        self.g(sk(rect_pts(fx - 2.6, y - 18, 5.2, 20), "faucetstem", "k", 0.3))
        self.g(f'<path d="M{n(fx)} {n(y - 18)} q0 -6 7 -6 h6 q3 0 3 4 v3" fill="none" stroke="var(--metal)" stroke-width="4.4" stroke-linecap="round"/>')
        self.g(f'<path class="k" d="M{n(fx)} {n(y - 18)} q0 -6 7 -6 h6 q3 0 3 4 v3" fill="none"/>')
        self.g(f'<circle cx="{n(fx + 8)}" cy="{n(y - 19)}" r="2.2" fill="var(--metal)"/>')
        # 逐滴出水
        for i, (dy, dr) in enumerate(((-8, 1.7), (2, 1.5), (12, 1.3))):
            self.g(f'<ellipse class="drop d{i}" cx="{n(fx + 8)}" cy="{n(y - 3 + dy)}" rx="{n(dr)}" ry="{n(dr * 1.35)}" fill="var(--water)"/>')
        if self.fresh(no):
            self.g(f'<circle class="new-glow" cx="{n(fx)}" cy="{n(y - 10)}" r="18"/>')

    # -- 灯光 / 生活气 / 安防 ---------------------------------------------------------
    def draw_life(self) -> None:
        if self.idx >= 2:
            for lx in (150.0, 284.0):
                # 吊灯：线 + 灯罩 + 灯泡 + 光晕
                self.g(path1(f"M{n(lx)} {n(CEIL_Y)} V{n(CEIL_Y + 16)}", "k"))
                self.g(f'<path d="M{n(lx - 9)} {n(CEIL_Y + 24)} L{n(lx - 4)} {n(CEIL_Y + 16)} H{n(lx + 4)} L{n(lx + 9)} {n(CEIL_Y + 24)} Z" fill="var(--light)"/>')
                self.g(f'<path class="k" d="M{n(lx - 9)} {n(CEIL_Y + 24)} L{n(lx - 4)} {n(CEIL_Y + 16)} H{n(lx + 4)} L{n(lx + 9)} {n(CEIL_Y + 24)} Z" fill="none"/>')
                self.g(f'<circle cx="{n(lx)}" cy="{n(CEIL_Y + 27)}" r="3" fill="var(--light)" stroke="var(--hot)" stroke-width=".8"/>')
                self.g(f'<circle class="lamp-glow" cx="{n(lx)}" cy="{n(CEIL_Y + 31)}" r="26" style="fill:url(#lampGlow{self.idx})"/>')
                self.g(f'<ellipse class="lamp-pool" cx="{n(lx)}" cy="381" rx="26" ry="5"/>')
            # 小盆栽
            px, py = 108.0, 390.0
            self.g(f'<path d="M{n(px - 7)} {n(py - 12)} H{n(px + 7)} L{n(px + 5)} {n(py)} H{n(px - 5)} Z" fill="var(--rust)"/>')
            self.g(path1(f"M{n(px)} {n(py - 12)} V{n(py - 22)}", "plant"))
            self.g(path1(f"M{n(px)} {n(py - 18)} q-7 -4 -8 -11", "plant"))
            self.g(path1(f"M{n(px)} {n(py - 20)} q7 -5 7 -13", "plant"))
            self.g(path1(f"M{n(px)} {n(py - 22)} q-2 -8 1 -13", "plant"))
        if self.idx >= 3:
            # 灭火器（物业安防）
            ex, ey = 263.0, 372.0
            self.g(f'<rect x="{n(ex - 6)}" y="{n(ey - 14)}" width="12" height="26" rx="4" fill="var(--red)"/>')
            self.g(sk(rect_pts(ex - 6, ey - 14, 12, 26), "extinguisher", "k", 0.3))
            self.g(f'<rect x="{n(ex - 3)}" y="{n(ey - 18)}" width="6" height="5" rx="1" fill="var(--metal)"/>')
            self.g(path1(f"M{n(ex + 3)} {n(ey - 16)} q6 2 3 8", "hose"))
            self.g(f'<rect x="{n(ex - 8)}" y="{n(ey + 10)}" width="16" height="3" fill="var(--bs-ink)" opacity=".7"/>')
            # 门口摄像头的一束淡淡红色警戒光
            self.g(f'<path class="guard-cone" d="M291 318 L{n(268)} {n(390)} L{n(314)} {n(390)} Z"/>')
            self.g(f'<path class="guard-light" d="M291 318 L{n(268)} {n(390)} M291 318 L{n(314)} {n(390)}"/>')

    # -- 12 枚编号圆牌 ----------------------------------------------------------------
    def draw_badges(self) -> None:
        out = []
        for no, spec in BADGES.items():
            x, y = spec["pos"]
            ax, ay = spec["anchor"]
            state = "new" if self.fresh(no) else ("old" if self.has(no) else "hollow")
            pin = ""
            dot = ""
            if abs(ax - x) > 4 or abs(ay - y) > 4:
                dx, dy = ax - x, ay - y
                dist = math.hypot(dx, dy) or 1.0
                ux, uy = dx / dist, dy / dist
                x1, y1 = x + ux * 15.5, y + uy * 15.5
                pin = f'<line class="pin" x1="{n(x1)}" y1="{n(y1)}" x2="{n(ax)}" y2="{n(ay)}"/>'
                dot = f'<circle class="pin-dot" cx="{n(ax)}" cy="{n(ay)}" r="2"/>'
            aria = f"{CIRCLED[no - 1]} {self.arts[no]['name']} · {spec['part']}（{self.stage['name']}）"
            out.append(
                f'<g class="badge st-{state}" data-no="{no}" data-state="{state}" '
                f'role="button" tabindex="0" aria-label="{esc(aria)}" data-x="{n(x)}" data-y="{n(y)}">'
                f'{pin}{dot}'
                f'<circle class="halo" cx="{n(x)}" cy="{n(y)}" r="16.8"/>'
                f'<circle class="ring" cx="{n(x)}" cy="{n(y)}" r="16.8"/>'
                f'<circle class="disc" cx="{n(x)}" cy="{n(y)}" r="10.8"/>'
                f'<text class="num" x="{n(x)}" y="{n(y + 0.6)}">{CIRCLED[no - 1]}</text>'
                f'</g>'
            )
        self.g("".join(out))

    # -- 总装 -------------------------------------------------------------------------
    def render(self) -> str:
        self.draw_soil()
        self.draw_structure()
        self.draw_roof()          # 屋顶 + 阁楼 + ⑧ 电控箱（要压在背墙/天花板之上）
        self.draw_window()
        self.draw_door()
        self.draw_pipes()         # 墙内管线 / 市政进水 / 分水器
        self.draw_boiler()        # ⑤
        self.draw_tank()          # ④
        self.draw_rack()          # ③
        self.draw_router()        # ⑥
        self.draw_sensor()        # ⑦
        self.draw_sink()          # ⑩
        self.draw_life()          # 灯 / 盆栽 / 摄像头 / 灭火器
        self.draw_badges()        # ①–⑫
        gid = self.idx
        defs = ("<defs>"
                f'<radialGradient id="lampGlow{gid}"><stop offset="0" stop-color="#F7C25E" stop-opacity=".34"/>'
                f'<stop offset="1" stop-color="#F7C25E" stop-opacity="0"/></radialGradient>'
                f'<linearGradient id="shadeX{gid}" x1="0" y1="0" x2="1" y2="0">'
                '<stop offset="0" stop-color="#2A241C" stop-opacity=".14"/>'
                '<stop offset=".14" stop-color="#2A241C" stop-opacity="0"/>'
                '<stop offset=".86" stop-color="#2A241C" stop-opacity="0"/>'
                '<stop offset="1" stop-color="#2A241C" stop-opacity=".14"/></linearGradient>'
                f'<linearGradient id="shadeY{gid}" x1="0" y1="0" x2="0" y2="1">'
                '<stop offset="0" stop-color="#2A241C" stop-opacity=".13"/>'
                '<stop offset="1" stop-color="#2A241C" stop-opacity="0"/></linearGradient>'
                + "".join(self.defs) + "</defs>")
        return (f'<svg class="house" viewBox="{VB_X0} {VB_Y0} {VB_W} {VB_H}" role="img" '
                f'aria-label="{esc(self.stage["name"])}：同一栋房子的第 {self.idx + 1} 个阶段">'
                f"{defs}{''.join(self.body)}</svg>")


# ------------------------------------------------------------------ 组版：CSS + HTML + 轻交互

CSS = r"""
:root{
  --ink-strong:#2A241C; --paper-page:#F4F1EA; --tip-paper:#FFFDF5;
  --font-cjk:"Noto Sans CJK SC","Source Han Sans SC","Droid Sans Fallback","Microsoft YaHei",sans-serif;
  --font-mono:"DejaVu Sans Mono","Noto Sans Mono CJK SC","Noto Sans CJK SC",monospace;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:#fff;}
html{overflow:auto;}
body{width:1600px;height:800px;padding:16px;background:#fff;
  font-family:var(--font-cjk);color:var(--ink-strong);-webkit-font-smoothing:antialiased;}
#poster{position:relative;width:1568px;height:768px;padding:11px 12px 7px;background:var(--paper-page);
  display:flex;flex-direction:column;}
#head{flex:0 0 auto;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;
  align-items:start;border-bottom:2px solid var(--ink-strong);padding:0 2px 7px;}
.kicker{font-size:10px;line-height:1.2;letter-spacing:.9px;color:#7A6A52;font-weight:700;}
h1{margin:3px 0 0;font-size:26px;line-height:1.12;font-weight:900;letter-spacing:.3px;}
.thesis{margin:4px 0 0;font-size:12.4px;line-height:1.4;color:#4A4034;}
.thesis b{color:#C2410C;}
.legend{display:grid;grid-template-columns:auto auto;gap:5px 14px;padding-top:2px;}
.lg{display:flex;align-items:center;gap:6px;font-size:9.6px;line-height:1.2;color:#4A4034;white-space:nowrap;}
.sw{flex:0 0 auto;width:17px;height:17px;border-radius:50%;display:grid;place-items:center;
  font-family:var(--font-cjk);font-size:9.4px;font-weight:700;}
.sw.hollow{background:#fff;border:1.6px solid #7B8491;color:#7B8491;}
.sw.old{background:#6B4A2F;border:1.6px solid #6B4A2F;color:#FFF6E9;}
.sw.new{background:#D9530F;border:1.6px solid #7C2D12;color:#FFF6E9;
  box-shadow:0 0 0 3px rgba(217,83,15,.17);}
.sw.pin{background:#FFF6E6;border:1.4px dashed #6B4A2F;color:#6B4A2F;font-size:8.4px;}
.legend-note{grid-column:1/3;font-size:9px;color:#7A6A52;}
#stages{flex:1 1 auto;display:flex;align-items:stretch;gap:4px;margin-top:7px;min-height:0;}
.stage{flex:1 1 0;min-width:0;position:relative;display:flex;flex-direction:column;
  background:var(--paper);border:1.4px solid var(--border);border-radius:10px;
  padding:5px 6px 3px;transition:border-color .15s,box-shadow .15s;}
.stage.focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(226,87,11,.16);}
.sh{display:grid;grid-template-columns:auto minmax(0,1fr) auto;grid-template-rows:auto auto;
  column-gap:7px;row-gap:1px;align-items:center;padding:1px 3px 6px;cursor:pointer;
  border-bottom:1.6px solid var(--border);user-select:none;outline:none;}
.stage.focus .sh{border-bottom-color:var(--accent);}
.sh:hover .nm,.sh:focus-visible .nm{color:var(--accent);}
.idx{grid-row:1;grid-column:1;font:900 12.5px/1 var(--font-mono);color:var(--accent);letter-spacing:.4px;}
.nm{grid-row:1;grid-column:2;margin:0;font-size:18.5px;line-height:1.1;font-weight:900;letter-spacing:.6px;transition:color .15s;}
.lv{grid-row:1;grid-column:3;font:700 9px/1 var(--font-mono);border:1.2px solid currentColor;
  border-radius:99px;padding:3px 5px;color:var(--chip);}
.sub{grid-row:2;grid-column:1/3;margin:0;font-size:9.4px;line-height:1.25;color:var(--chip);}
.cnt{grid-row:2;grid-column:3;font:700 10px/1 var(--font-mono);color:var(--accent);text-align:right;}
.art{flex:1 1 auto;display:flex;align-items:center;justify-content:center;min-height:0;padding:2px 0;margin:0 -3px;}
.house{width:100%;height:auto;display:block;overflow:visible;}
.grown{margin:0;padding:4px 2px 1px;border-top:1px dashed var(--border);
  font-size:9.5px;line-height:1.25;text-align:center;color:var(--chip);}
.grown b{color:var(--accent);font-weight:900;letter-spacing:.8px;}
.grown b.none{color:var(--chip);letter-spacing:.2px;font-weight:700;}
.arrow{flex:0 0 13px;display:flex;align-items:center;justify-content:center;
  font-size:20px;font-weight:900;color:#B08A5A;}
#foot{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:6px 2px 0;border-top:1.4px solid rgba(42,36,28,.16);margin-top:6px;
  font-size:9px;line-height:1.3;color:#7A6A52;}
#foot b{color:#4A4034;}
#tip{position:absolute;z-index:60;width:374px;padding:9px 11px 9px;background:var(--tip-paper);
  border:1.6px solid var(--ink-strong);border-radius:8px;box-shadow:0 12px 26px rgba(42,30,16,.20);
  display:none;pointer-events:none;}
#tip.on{display:block;}
#tip.pinned{pointer-events:auto;box-shadow:0 14px 30px rgba(42,30,16,.28);}
.tip-h{display:flex;align-items:center;gap:7px;margin-bottom:5px;padding-bottom:5px;
  border-bottom:1px dashed #CBB894;}
.tip-no{font-size:15px;font-weight:900;color:#C2410C;}
.tip-name{font-size:12px;font-weight:900;color:#2A241C;}
.tip-part{margin-left:auto;font-size:8.6px;padding:2px 6px;border-radius:99px;background:#F1E3C9;color:#6B4A2F;white-space:nowrap;}
.tip-row{display:flex;gap:7px;font-size:9.6px;line-height:1.5;margin:3px 0;}
.tip-row b{flex:0 0 26px;font-weight:900;color:#6B4A2F;letter-spacing:.5px;}
.tip-row.mature b{color:#C2410C;}
.tip-row span{flex:1;color:#3C342A;}
.tip-tag{margin-top:5px;font-size:8.8px;line-height:1.4;color:#6B4A2F;background:#F6ECD8;
  border-left:2.5px solid #C2410C;padding:2px 6px;border-radius:0 3px 3px 0;}
.tip-row code{font-family:var(--font-mono);font-size:8.8px;background:#F0E7D4;
  padding:0 2px;border-radius:2px;color:#5A4630;}
/* ---- SVG 手绘感线条（不加滤镜：靠双描边 + 轻微抖动） ---- */
.house .k{fill:none;stroke:var(--ink);stroke-width:2.15;stroke-linecap:round;stroke-linejoin:round;}
.house .k2{fill:none;stroke:var(--ink);stroke-width:1.05;opacity:.30;stroke-linecap:round;stroke-linejoin:round;}
.house .k2line{fill:none;stroke:var(--ink);stroke-width:1.05;opacity:.5;stroke-linecap:round;stroke-linejoin:round;}
.house .fine{fill:none;stroke:var(--ink);stroke-width:1.15;opacity:.78;stroke-linecap:round;stroke-linejoin:round;}
.house .hair{fill:none;stroke:var(--soft);stroke-width:.9;opacity:.72;stroke-linecap:round;}
.house .hatch{fill:none;stroke:var(--hatch);stroke-width:.8;opacity:.62;}
.house .ghost{fill:none;stroke:var(--soft);stroke-width:1.3;stroke-dasharray:3 3.6;
  opacity:.85;stroke-linecap:round;stroke-linejoin:round;}
.house .soil-line{fill:none;stroke:var(--ground-line);stroke-width:.9;opacity:.5;}
.house .soil-dots circle{fill:var(--ground-line);opacity:.32;}
.house .pebbles circle{fill:var(--soft);opacity:.5;}
.house .sand-dots circle{fill:var(--ground-line);opacity:.45;}
.house .rafter{fill:none;stroke:var(--soft);stroke-width:1.5;opacity:.6;stroke-linecap:round;}
.house .roof-hi{fill:none;stroke:#FFF6E4;stroke-width:1.2;opacity:.22;stroke-linecap:round;}
.house .grass{fill:none;stroke:#77804E;stroke-width:1.15;opacity:.72;stroke-linecap:round;}
.house .formline{fill:none;stroke:var(--soft);stroke-width:.85;opacity:.5;}
.house .crack{fill:none;stroke:var(--soft);stroke-width:.9;opacity:.8;}
.house .rebar{fill:none;stroke:var(--rust);stroke-width:1.5;opacity:.9;stroke-linecap:round;}
.house .brick-line{fill:none;stroke:var(--roof-line);stroke-width:.8;opacity:.55;}
.house .tile{fill:none;stroke:var(--roof-line);stroke-width:.85;opacity:.62;}
.house .tile-mid{fill:none;stroke:var(--roof-line);stroke-width:1;opacity:.55;}
.house .ridge{fill:none;stroke:var(--roof-line);stroke-width:2.6;opacity:.85;stroke-linecap:round;}
.house .bs-line{fill:none;stroke:var(--bs-ink);stroke-width:.9;opacity:.55;}
.house .window-void{fill:none;stroke:var(--soft);stroke-width:.9;opacity:.7;stroke-dasharray:2 3;}
.house .glass-line{fill:none;stroke:#FFFFFF;stroke-width:2.6;opacity:.55;stroke-linecap:round;}
.house .screen-line{fill:none;stroke:var(--bs-ink);stroke-width:.8;opacity:.6;}
.house .screen-glow{fill:var(--light);opacity:.12;}
.house .doorpanel{fill:none;stroke:var(--bs-ink);stroke-width:1;opacity:.7;}
.house .pipe{filter:none;}
.house .ghostpipe{stroke-dasharray:2 3;opacity:.45;}
.house .wisp{opacity:.85;}
.house .circuit{fill:none;stroke:var(--water);stroke-width:.9;opacity:.9;}
.house .heat-glow{fill:var(--hot);opacity:.10;}
.house .new-glow{fill:var(--hot);opacity:.065;}
.house .steam{fill:none;stroke:var(--soft);stroke-width:1;opacity:.5;stroke-linecap:round;}
.house .flame{fill:none;stroke:#FFF3D8;stroke-width:1;opacity:.9;}
.house .rackline{fill:none;stroke:#4A3824;stroke-width:.7;opacity:.55;}
.house .antenna{fill:none;stroke:var(--ink);stroke-width:1.4;stroke-linecap:round;}
.house .wifi{fill:none;stroke:var(--light);stroke-width:1.5;opacity:.95;stroke-linecap:round;}
.house .wave{fill:none;stroke:var(--hot);stroke-width:1.25;opacity:.75;stroke-linecap:round;}
.house .lamp-glow{fill:none;}
.house .lamp-pool{fill:var(--light);opacity:.10;}
.house .plant{fill:none;stroke:#6D7C46;stroke-width:1.35;opacity:.9;stroke-linecap:round;}
.house .guard-light{fill:none;stroke:var(--red);stroke-width:.7;opacity:.12;stroke-dasharray:2 4;}
.house .guard-cone{fill:var(--red);opacity:.04;}
.house .cctv-line{fill:none;stroke:#FFF6E4;stroke-width:.7;opacity:.35;}
.house .smoke{fill:none;stroke:var(--soft);stroke-width:1.6;opacity:.35;stroke-linecap:round;}
.house .cam{fill:none;stroke:var(--ink);stroke-width:1;opacity:.85;}
.house .cam-signal{fill:none;stroke:var(--red);stroke-width:.8;opacity:.75;stroke-linecap:round;}
.house .card-wave{fill:none;stroke:var(--light);stroke-width:1;opacity:.9;stroke-linecap:round;}
.house .lock{fill:none;stroke:#FFF0E2;stroke-width:1;opacity:.95;}
.house .meterneedle{fill:none;stroke:var(--ink);stroke-width:1;}
.house .meterdial{fill:none;stroke:var(--ink);stroke-width:.7;opacity:.7;}
.house .hose{fill:none;stroke:var(--bs-ink);stroke-width:1;opacity:.8;}
.house .drop{opacity:.75;}
.house .spark{fill:var(--accent);opacity:.85;}
.pin{stroke:var(--ink);stroke-width:.9;opacity:.5;stroke-dasharray:2 2.5;}
.pin-dot{fill:var(--ink);opacity:.55;}
/* ---- 12 枚编号圆牌 ---- */
.badge{cursor:pointer;outline:none;}
.badge .halo{fill:#FFFFFF;opacity:.5;transition:opacity .15s;}
.badge .disc{transition:transform .12s ease;transform-box:fill-box;transform-origin:center;}
.badge .ring{fill:none;stroke:var(--accent);stroke-width:1.3;stroke-dasharray:2.4 3.2;opacity:0;transition:opacity .15s;}
.badge .num{font-family:var(--font-cjk);font-size:11.2px;font-weight:700;text-anchor:middle;
  dominant-baseline:central;pointer-events:none;transition:fill .15s;}
.badge.st-hollow .disc{fill:var(--paper);stroke:var(--badge-hollow);stroke-width:1.7;}
.badge.st-hollow .num{fill:var(--badge-hollow);}
.badge.st-old .disc{fill:var(--badge-old);stroke:var(--badge-old);stroke-width:1.7;}
.badge.st-old .num{fill:#FFF6E9;}
.badge.st-new .disc{fill:var(--badge-new);stroke:#7C2D12;stroke-width:1.8;}
.badge.st-new .num{fill:#FFF6E9;}
.badge.st-new .halo{fill:var(--badge-new);opacity:.16;}
.badge.st-new .ring{opacity:.95;}
.badge:hover .disc,.badge:focus-visible .disc{transform:scale(1.16);}
.badge:hover .ring,.badge:focus-visible .ring{opacity:1;stroke-dasharray:none;stroke-width:1.9;}
.badge:focus-visible .halo{opacity:.85;}
.stage.focus .badge.st-hollow{opacity:.26;}
.stage.focus .badge.st-old{opacity:.56;}
.stage.focus .badge.st-new .ring{opacity:1;stroke-dasharray:none;stroke-width:2.1;}
.stage.focus .badge.st-new .halo{opacity:.3;}
.stage.focus .badge.st-new .disc{stroke-width:2.4;}
"""


def palette_css() -> str:
    rules = []
    for i, pal in enumerate(PALETTES):
        body = ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in pal.items())
        rules.append(f'.stage[data-s="{i + 1}"]{{{body}}}')
    return "\n".join(rules)


JS = r"""
(function(){
  "use strict";
  var CIRCLED = "__CIRCLED__";
  var ARTS = JSON.parse(document.getElementById("artifacts-json").textContent);
  var poster = document.getElementById("poster");
  var tip = document.getElementById("tip");
  var pinnedNo = 0;

  function esc(s){
    return String(s).replace(/[&<>"]/g, function(c){
      return ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[c];
    });
  }
  function fmt(s){
    return esc(s).replace(/`([^`]+)`/g, "<code>$1</code>");
  }
  function tipHTML(no){
    var a = ARTS[no - 1];
    return '<div class="tip-h"><span class="tip-no">' + CIRCLED.charAt(no - 1) + '</span>' +
      '<span class="tip-name">' + esc(a.name) + '</span>' +
      '<span class="tip-part">' + esc(a.part) + '</span></div>' +
      '<div class="tip-row"><b>骨架</b><span>' + fmt(a.skeleton) + '</span></div>' +
      '<div class="tip-row mature"><b>成熟</b><span>' + fmt(a.mature) + '</span></div>' +
      '<div class="tip-tag">机制：' + esc(a.label) + '</div>';
  }
  function hideTip(){
    if (pinnedNo) return;
    tip.classList.remove("on");
  }
  function place(no, el){
    tip.innerHTML = tipHTML(no);
    tip.classList.add("on");
    var r = el.getBoundingClientRect(), p = poster.getBoundingClientRect();
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var left = r.right - p.left + 9;
    if (left + tw > p.width - 6) left = r.left - p.left - tw - 9;
    if (left < 6) left = Math.max(6, Math.min(r.left - p.left, p.width - tw - 6));
    var top = r.top - p.top - 8;
    if (top + th > p.height - 6) top = p.height - th - 6;
    if (top < 6) top = 6;
    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
  }
  function hideAll(){
    pinnedNo = 0;
    tip.classList.remove("on", "pinned");
  }

  Array.prototype.forEach.call(document.querySelectorAll(".badge"), function(b){
    b.addEventListener("mouseenter", function(){ if (!pinnedNo) place(+b.dataset.no, b); });
    b.addEventListener("mouseleave", hideTip);
    b.addEventListener("focus", function(){ if (!pinnedNo) place(+b.dataset.no, b); });
    b.addEventListener("blur", hideTip);
    b.addEventListener("click", function(ev){
      ev.stopPropagation();
      var no = +b.dataset.no;
      if (pinnedNo === no) { hideAll(); return; }
      pinnedNo = no;
      tip.classList.add("pinned");
      place(no, b);
    });
    b.addEventListener("keydown", function(ev){
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); b.click(); }
    });
  });

  var stages = Array.prototype.slice.call(document.querySelectorAll(".stage"));
  stages.forEach(function(stage){
    var head = stage.querySelector(".sh");
    function toggle(){
      var on = !stage.classList.contains("focus");
      stages.forEach(function(s){
        s.classList.remove("focus");
        s.querySelector(".sh").setAttribute("aria-pressed", "false");
      });
      if (on) {
        stage.classList.add("focus");
        head.setAttribute("aria-pressed", "true");
        hideAll();
      }
    }
    head.addEventListener("click", toggle);
    head.addEventListener("keydown", function(ev){
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(); }
    });
  });
  poster.addEventListener("click", function(){ hideAll(); });

  /* 交互演示锚点：#tip=4 钉住某件的 tooltip；#focus=3 高亮某阶段本阶段新增（截图/人工验收用） */
  (function(){
    var h = location.hash || "";
    var fm = /^#focus=(\d)$/.exec(h);
    if (fm) {
      var st = stages[+fm[1] - 1];
      if (st) {
        stages.forEach(function(x){ x.classList.remove("focus"); x.querySelector(".sh").setAttribute("aria-pressed", "false"); });
        st.classList.add("focus");
        st.querySelector(".sh").setAttribute("aria-pressed", "true");
      }
    }
    var tm = /^#tip=(\d+)$/.exec(h);
    if (tm) {
      var badge = document.querySelector('.stage[data-s="1"] .badge[data-no="' + tm[1] + '"]');
      if (badge) { pinnedNo = +tm[1]; tip.classList.add("pinned"); place(+tm[1], badge); }
    }
  })();

  /* ---------- 页面内置自检：写成 JSON 塞进 #selftest，--dump-dom 读回 ---------- */
  function selftest(){
    var out = {};
    var secs = stages;
    out.stages = secs.length;
    out.stageNames = secs.map(function(s){ return s.querySelector(".nm").textContent.trim(); });
    out.viewBoxes = Array.prototype.map.call(document.querySelectorAll("svg.house"), function(sv){ return sv.getAttribute("viewBox"); });
    out.houseSvgs = document.querySelectorAll("svg.house").length;
    out.badgesPerStage = secs.map(function(s){ return s.querySelectorAll(".badge").length; });
    out.numbersPerStage = secs.map(function(s){
      return Array.prototype.map.call(s.querySelectorAll(".badge"), function(b){ return +b.dataset.no; })
        .sort(function(a, b){ return a - b; });
    });
    out.newPerStage = secs.map(function(s){ return s.querySelectorAll(".badge.st-new").length; });
    out.cumPerStage = secs.map(function(s){ return s.querySelectorAll(".badge:not(.st-hollow)").length; });
    out.bottomLines = secs.map(function(s){ return s.querySelector(".grown").textContent.trim(); });
    out.grownSum = out.newPerStage.reduce(function(a, b){ return a + b; }, 0);
    var union = {};
    Array.prototype.forEach.call(document.querySelectorAll(".badge.st-new"), function(b){ union[+b.dataset.no] = 1; });
    out.grownUnion = Object.keys(union).map(Number).sort(function(a, b){ return a - b; });
    out.externalResources = performance.getEntriesByType("resource").map(function(e){ return e.name; });
    out.srcAttrs = Array.prototype.slice.call(document.querySelectorAll("[src],[href]"))
      .map(function(el){ return el.getAttribute("src") || el.getAttribute("href"); })
      .filter(function(v){ return v && v.indexOf("data:") !== 0 && v.charAt(0) !== "#"; });
    out.artifacts = ARTS.length;
    out.artifactTextOk = ARTS.every(function(a){
      return a && a.name && a.location && a.skeleton && a.mature && a.part && a.label &&
        a.skeleton.length > 20 && a.mature.length > 20;
    });
    /* tooltip 真的能拼出「骨架 → 成熟 → 标签」 */
    var probe = document.createElement("div");
    probe.style.cssText = "position:absolute;left:-9999px;top:0;width:380px";
    poster.appendChild(probe);
    out.tooltipOk = true;
    out.tooltipSkels = {};
    for (var i = 1; i <= ARTS.length; i++) {
      probe.innerHTML = tipHTML(i);
      var rows = probe.querySelectorAll(".tip-row span");
      var tag = probe.querySelector(".tip-tag");
      out.tooltipSkels[i] = rows.length === 2 ? rows[0].textContent.length : 0;
      if (rows.length !== 2 || !rows[0].textContent.trim() || !rows[1].textContent.trim() || !tag) {
        out.tooltipOk = false;
      }
    }
    probe.parentNode.removeChild(probe);
    /* 徽章都在自己那张卡片里（说明「钉在房子上」，不是掉到底部列表） */
    out.badgesInsideCards = secs.every(function(s){
      var cr = s.getBoundingClientRect();
      return Array.prototype.every.call(s.querySelectorAll(".badge"), function(b){
        var r = b.getBoundingClientRect();
        return r.left >= cr.left - 1 && r.right <= cr.right + 1 &&
               r.top >= cr.top - 1 && r.bottom <= cr.bottom + 1;
      });
    });
    /* 每个圆牌的钉点 / 圆牌都在 SVG viewBox 内 */
    out.badgeSvgBounds = secs.every(function(s){
      var sv = s.querySelector("svg.house");
      if (!sv) return false;
      var vb = (sv.getAttribute("viewBox") || "").split(/\s+/).map(Number);
      return Array.prototype.every.call(s.querySelectorAll(".badge"), function(b){
        var x = +b.dataset.x, y = +b.dataset.y;
        return x > vb[0] + 4 && x < vb[0] + vb[2] - 4 && y > vb[1] + 4 && y < vb[1] + vb[3] - 4;
      });
    });
    var de = document.documentElement;
    out.overflow = { docW: de.scrollWidth, docH: de.scrollHeight, bodyW: document.body.scrollWidth, bodyH: document.body.scrollHeight };
    out.font = getComputedStyle(document.body).fontFamily;
    out.legendItems = document.querySelectorAll(".legend .lg").length;
    var blob = JSON.stringify(out);
    var node = document.getElementById("selftest");
    if (node) node.textContent = blob;
    var node2 = document.getElementById("selftest-data");
    if (node2) node2.textContent = blob;
    return out;
  }
  try { window.__houseSelftest = selftest(); } catch (e) { /* 页面开给人看时静默 */ }
})();
"""


def build_html(data: dict, stages_doc: dict) -> str:
    arts = {a["no"]: a for a in data["artifacts"]}
    labels: dict[int, str] = {}
    for st in stages_doc["stages"]:
        for m in st["mechanisms"]:
            labels[m["no"]] = m["label"]

    emb = []
    for no in range(1, 13):
        a = arts[no]
        emb.append(dict(no=no, name=a["name"], kind=a["kind"], location=a["location"],
                        skeleton=a["skeleton"], mature=a["mature"],
                        part=BADGES[no]["part"], label=labels[no]))
    payload = json.dumps(emb, ensure_ascii=False).replace("</", "<\\/")

    cards = []
    for i, st in enumerate(stages_doc["stages"]):
        art = HouseArt(i, data, stages_doc).render()
        grown = st["artifacts_grown"]
        if grown:
            line = (f'本阶段长出来：<b>{"".join(CIRCLED[no - 1] for no in grown)}</b>'
                    f'（累计 {len(CUMULATIVE[i])}/12）')
        else:
            line = '本阶段长出来：<b class="none">无</b>（12 件全是空心壳，累计 0/12）'
        cards.append(
            f'<article class="stage" data-s="{i + 1}" data-stage="{esc(st["id"])}">'
            f'<div class="sh" role="button" tabindex="0" aria-pressed="false" '
            f'title="点一下：只亮本阶段长出来的徽章">'
            f'<span class="idx">{i + 1:02d}</span>'
            f'<h2 class="nm">{esc(st["name"])}</h2>'
            f'<span class="lv">{esc(st["level"])}</span>'
            f'<p class="sub">{esc(st["subtitle"])}</p>'
            f'<span class="cnt">{len(CUMULATIVE[i])}/12</span>'
            f"</div>"
            f'<div class="art">{art}</div>'
            f'<p class="grown">{line}</p>'
            f"</article>"
        )
        if i < 3:
            cards.append('<div class="arrow" aria-hidden="true">→</div>')

    legend = (
        '<div class="legend">'
        '<span class="lg"><i class="sw hollow">④</i>空心 = 壳 / 占位</span>'
        '<span class="lg"><i class="sw old">④</i>实心 = 真机制</span>'
        '<span class="lg"><i class="sw new">④</i>橙 + 光晕 = 本阶段新增</span>'
        '<span class="lg"><i class="sw pin">⑫</i>①–⑫ = 钉在部位上的 12 件</span>'
        '<span class="legend-note">编号与 <code>data.json</code> 的 12 件一一对应；未长出来的部位画成虚线幽灵</span>'
        "</div>"
    )

    title = esc(stages_doc["title"])
    thesis = esc(stages_doc["thesis"])
    thesis_html = thesis.replace("毛坯能站人", "<b>毛坯能站人</b>").replace(
        "通水通电才能住", "<b>通水通电才能住</b>").replace(
        "装上智能才好用", "<b>装上智能才好用</b>").replace("有了安防才敢交付", "<b>有了安防才敢交付</b>")

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1600">
<title>{title} · 四阶段成熟度</title>
<style>
{CSS}
{palette_css()}
</style>
</head>
<body>
<main id="poster">
  <header id="head">
    <div class="head-l">
      <div class="kicker">{esc(stages_doc["kicker"])}</div>
      <h1>{title}</h1>
      <p class="thesis">{thesis_html}</p>
    </div>
    {legend}
  </header>
  <section id="stages">
    {"".join(cards)}
  </section>
  <footer id="foot">
    <span><b>同一栋房子，四个阶段</b>：结构只增不删；每阶段亮起来的编号，就是这一级真的长出来的那几件。</span>
    <span>重跑：<b>{RERUN}</b>　·　本机 Chrome 无头截图 + <code>convert -trim</code>　·　零外部请求 / 本地字体</span>
  </footer>
  <div id="tip" role="tooltip" aria-hidden="true"></div>
  <pre id="selftest" hidden></pre>
</main>
<script type="application/json" id="artifacts-json">{payload}</script>
<script type="application/json" id="selftest-data"></script>
<script>
{JS.replace("__CIRCLED__", CIRCLED)}
</script>
</body>
</html>
"""
    return html_doc


# ------------------------------------------------------------------ 静态自检（HTML / 数据 / 口径）

CIRCLED_SET = set(CIRCLED)


def circled_numbers(text: str) -> list[int]:
    order = {ch: i + 1 for i, ch in enumerate(CIRCLED)}
    return [order[ch] for ch in text if ch in order]


def check_text_forbidden(text: str, where: str) -> None:
    for bad in FORBIDDEN:
        if bad and bad in text:
            fail(f"{where} 里出现禁用字符串 {bad!r}（不许出现用户名 / 绝对路径 / 口令）")


def check_html(page: str, data: dict, stages_doc: dict) -> None:
    errs: list[str] = []
    # 1) 零外部请求：不许出现 http(s)、外部 link/img/字体
    for pat, label in ((r"https?://(?!127\.0\.0\.1|localhost)", "外链 URL"), (r"<link\b", "<link>"),
                       (r"@import", "@import"), (r"<img\b", "<img>"),
                       (r"url\(\s*['\"]?https?:", "CSS 外部 url()"),
                       (r"<script[^>]+\bsrc=", "<script src=>"),
                       (r"<iframe\b", "<iframe>"), (r"@font-face", "@font-face")):
        if re.search(pat, page, re.I):
            errs.append(f"house.html 里出现{label}（必须零外部请求、离线可开）")
    # 2) 四个阶段 + 每阶段 12 枚徽章、编号 1–12
    stage_blocks = re.findall(r'<article class="stage" data-s="(\d)"', page)
    if stage_blocks != ["1", "2", "3", "4"]:
        errs.append(f"阶段卡片应依次为 1–4，实际 {stage_blocks}")
    badges = re.findall(r'class="badge st-(hollow|old|new)" data-no="(\d+)"', page)
    if len(badges) != 48:
        errs.append(f"徽章应 48 枚（4 阶段 × 12），实际 {len(badges)}")
    for i in range(4):
        chunk = badges[i * 12:(i + 1) * 12]
        nos = sorted(int(b[1]) for b in chunk)
        if nos != list(range(1, 13)):
            errs.append(f"阶段 {i + 1} 的徽章编号不是 1–12：{nos}")
        states = [b[0] for b in chunk]
        want_new = len(EXPECTED_GROUPS[i])
        if states.count("new") != want_new:
            errs.append(f"阶段 {i + 1} 本阶段新增徽章 {states.count('new')} 枚，应为 {want_new}")
        if states.count("hollow") != 12 - len(CUMULATIVE[i]):
            errs.append(f"阶段 {i + 1} 空心徽章数不对")
    # 3) 「本阶段长出来」合计 = 12，并集 = 1–12 各一次
    lines = re.findall(r'<p class="grown">(.*?)</p>', page, re.S)
    if len(lines) != 4:
        errs.append(f"「本阶段长出来」应有 4 行，实际 {len(lines)}")
    per = []
    for i, line in enumerate(lines):
        txt = re.sub(r"<[^>]+>", "", line)
        got = circled_numbers(txt)
        want = EXPECTED_GROUPS[i]
        if got != want:
            errs.append(f"阶段 {i + 1} 的「本阶段长出来」编号 {got} ≠ 设计口径 {want}")
        per.extend(got)
    if sorted(per) != list(range(1, 13)):
        errs.append(f"四行「本阶段长出来」合计 {len(per)} 个编号：{sorted(set(per))}，必须恰好覆盖 12 件各一次")
    # 4) 12 件的 skeleton / mature 逐字来自 data.json（内嵌 JSON 反解析后逐字比对）
    m = re.search(r'<script type="application/json" id="artifacts-json">(.*?)</script>', page, re.S)
    if not m:
        errs.append("找不到内嵌的 artifacts-json（徽章 tooltip 数据）")
    else:
        try:
            embedded = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            embedded = []
            errs.append(f"内嵌 artifacts-json 不是合法 JSON：{exc}")
        if len(embedded) != 12:
            errs.append(f"内嵌 artifacts-json 有 {len(embedded)} 件，应为 12")
        by_no = {a["no"]: a for a in data["artifacts"]}
        labels = {m["no"]: m["label"] for st in stages_doc["stages"] for m in st["mechanisms"]}
        for item in embedded:
            a = by_no.get(item.get("no"))
            if a is None:
                errs.append(f"内嵌数据引用不存在的件 {item.get('no')}")
                continue
            for key in ("name", "location", "skeleton", "mature"):
                if item.get(key) != a[key]:
                    errs.append(f"#{a['no']} 的 {key} 与 data.json 不一致（不许重写文字）")
            if item.get("part") != BADGES[a["no"]]["part"]:
                errs.append(f"#{a['no']} 的房子部位标注与画图坐标不一致")
            if item.get("label") != labels.get(a["no"]):
                errs.append(f"#{a['no']} 的机制短标签与 stages.json 不一致")
    # 5) 标题 / 主旨 / 四阶段名 / 关键真值
    for token in ("同一栋房子", "毛坯能站人", "通水通电才能住", "装上智能才好用", "有了安防才敢交付"):
        if token not in page:
            errs.append(f"house.html 缺主旨句成分 {token!r}")
    for st in stages_doc["stages"]:
        if st["name"] not in page:
            errs.append(f"house.html 缺阶段名 {st['name']!r}")
    for token in REQUIRED_TOKENS:
        if token not in page:
            errs.append(f"house.html 缺关键真值 {token!r}")
    # 6) 无用户名 / 绝对路径 / 口令
    check_text_forbidden(page, "house.html")

    if errs:
        print("✗ house.html 静态自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)
    print("  ✓ 静态自检：4 阶段 × 12 徽章（编号 1–12 齐）、本阶段长出来合计 12 件、"
          "内嵌 12 件文字与 data.json 逐字一致、无外链资源（页面里 127.0.0.1 只是 data.json 的"
          "本机端点文字，不是资源请求）、无用户名/绝对路径/口令")


# ------------------------------------------------------------------ 无头 Chrome：内置自检 + 截图

CHROME_BASE = [
    CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
    "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check",
    "--disable-extensions", "--mute-audio", "--font-render-hinting=none",
]


def run_chrome(args: list[str], timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(CHROME_BASE + args, capture_output=True, text=True, timeout=timeout)


def dump_dom(page: Path, work: Path) -> str:
    prof = work / "chrome-profile-dom"
    proc = run_chrome([f"--user-data-dir={prof}", "--virtual-time-budget=2500",
                       "--dump-dom", page.as_uri()])
    if proc.returncode != 0:
        fail(f"Chrome --dump-dom 失败（{proc.returncode}）：{proc.stderr[-800:]}")
    return proc.stdout


def parse_selftest(dom: str) -> dict:
    m = re.search(r'<script[^>]*id="selftest-data"[^>]*>(.*?)</script>', dom, re.S)
    if not m:
        m = re.search(r'<pre[^>]*id="selftest"[^>]*>(.*?)</pre>', dom, re.S)
    if not m:
        fail("页面内置自检没写回（--dump-dom 里没有 #selftest-data）")
    raw = html.unescape(m.group(1)).strip()
    start, end = raw.find("{"), raw.rfind("}")
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        fail(f"页面内置自检 JSON 解析失败：{exc}")


def check_metrics(metrics: dict, data: dict, stages_doc: dict) -> None:
    errs: list[str] = []
    want_names = [st["name"] for st in stages_doc["stages"]]
    if metrics.get("stages") != 4:
        errs.append(f"页面里 {metrics.get('stages')} 个阶段，应为 4")
    if metrics.get("stageNames") != want_names:
        errs.append(f"阶段名 {metrics.get('stageNames')} ≠ {want_names}")
    if metrics.get("houseSvgs") != 4:
        errs.append(f"房子 SVG {metrics.get('houseSvgs')} 张，应为 4")
    vb = metrics.get("viewBoxes") or []
    if len(set(vb)) != 1:
        errs.append(f"四栋房子的 viewBox 不一致（必须是同一栋、同一视角）：{vb}")
    if metrics.get("badgesPerStage") != [12, 12, 12, 12]:
        errs.append(f"每阶段徽章数 {metrics.get('badgesPerStage')}，应都是 12")
    want_nums = [list(range(1, 13))] * 4
    if metrics.get("numbersPerStage") != want_nums:
        errs.append("某阶段的徽章编号不是 1–12")
    if metrics.get("newPerStage") != [0, 5, 3, 4]:
        errs.append(f"本阶段新增徽章数 {metrics.get('newPerStage')}，应为 [0,5,3,4]")
    if metrics.get("cumPerStage") != [0, 5, 8, 12]:
        errs.append(f"累计亮起徽章数 {metrics.get('cumPerStage')}，应为 [0,5,8,12]")
    if metrics.get("grownSum") != 12:
        errs.append(f"「本阶段长出来」合计 {metrics.get('grownSum')} 件，应为 12")
    if metrics.get("grownUnion") != list(range(1, 13)):
        errs.append(f"「本阶段长出来」并集不是 1–12：{metrics.get('grownUnion')}")
    lines = metrics.get("bottomLines") or []
    if len(lines) != 4:
        errs.append(f"页面里「本阶段长出来」{len(lines)} 行，应为 4")
    per = [circled_numbers(x) for x in lines]
    if per != EXPECTED_GROUPS:
        errs.append(f"页面四行「本阶段长出来」{per} ≠ {EXPECTED_GROUPS}")
    if metrics.get("externalResources"):
        errs.append(f"页面发起了外部请求：{metrics['externalResources']}")
    if metrics.get("srcAttrs"):
        errs.append(f"页面有 src/href 资源引用：{metrics['srcAttrs']}")
    if metrics.get("artifacts") != 12:
        errs.append(f"内嵌 artifact 数据 {metrics.get('artifacts')} 件，应为 12")
    if not metrics.get("artifactTextOk"):
        errs.append("内嵌 12 件的 name/location/skeleton/mature/part/label 有缺")
    if not metrics.get("tooltipOk"):
        errs.append("12 条徽章 tooltip 的「骨架 → 成熟」没有全部拼出来")
    if not metrics.get("badgesInsideCards"):
        errs.append("有徽章跑到卡片外面（必须钉在自己那栋房子上）")
    if not metrics.get("badgeSvgBounds"):
        errs.append("有徽章 / 钉点超出 SVG viewBox")
    ov = metrics.get("overflow") or {}
    if (ov.get("docW", 0) > DESIGN_W or ov.get("docH", 0) > DESIGN_H
            or ov.get("bodyW", 0) > DESIGN_W or ov.get("bodyH", 0) > DESIGN_H):
        errs.append(f"页面溢出 {DESIGN_W}×{DESIGN_H}：{ov}")
    if "Noto Sans CJK SC" not in str(metrics.get("font", "")):
        errs.append(f"页面字体不是系统 Noto Sans CJK：{metrics.get('font')}")
    if metrics.get("legendItems", 0) < 3:
        errs.append("图例条目不足 3 条")
    if errs:
        print("✗ 页面内置自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)
    print("  ✓ 页面内置自检：4 阶段 / 同 viewBox / 48 徽章（每阶段 12、编号齐） / "
          "新增 [0,5,3,4] 累计 [0,5,8,12] / 「本阶段长出来」合计 12 / 外部请求 0 / 12 条 tooltip 齐")


def screenshot(page: Path, raw_png: Path, work: Path) -> None:
    prof = work / "chrome-profile-shot"
    args = [f"--user-data-dir={prof}", f"--window-size={DESIGN_W},{DESIGN_H}",
            f"--force-device-scale-factor={SCALE}", f"--screenshot={raw_png}",
            "--virtual-time-budget=2500", page.as_uri()]
    proc = run_chrome(args)
    if proc.returncode != 0 or not raw_png.exists():
        fail(f"Chrome --screenshot 失败（{proc.returncode}）：{proc.stderr[-800:]}")
    size = png_size(raw_png)
    if size != (OUT_W, OUT_H):
        fail(f"截图尺寸 {size} ≠ {OUT_W}×{OUT_H}（检查 --window-size / --force-device-scale-factor）")


def png_size(png: Path) -> tuple[int, int]:
    head = png.read_bytes()[:33]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{png} 不是 PNG")
    return struct.unpack(">II", head[16:24])


def trim_and_pad(raw: Path, out: Path, work: Path) -> tuple[tuple[int, int], tuple[int, int]]:
    """convert -trim 收掉白边，再用纸色 -extent 回 3200×1600 画布（中间图只写临时目录）。"""
    raw_size = png_size(raw)
    trimmed = work / "trimmed.png"
    proc = subprocess.run([CONVERT, str(raw), "-trim", "+repage", str(trimmed)],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not trimmed.exists():
        fail(f"convert -trim 失败：{proc.stderr[-500:]}")
    trimmed_size = png_size(trimmed)
    if not (OUT_W * 0.85 <= trimmed_size[0] <= OUT_W and OUT_H * 0.85 <= trimmed_size[1] <= OUT_H):
        fail(f"-trim 后尺寸 {trimmed_size} 不合理（白边没收对？）")
    proc = subprocess.run([CONVERT, str(trimmed), "-background", PAPER, "-gravity", "center",
                           "-extent", f"{OUT_W}x{OUT_H}", str(out)],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        fail(f"convert -extent 回画布失败：{proc.stderr[-500:]}")
    return raw_size, trimmed_size


def pixel_grid(png: Path, w: int = 800, h: int = 400) -> bytes:
    proc = subprocess.run([CONVERT, str(png), "-resize", f"{w}x{h}!", "-depth", "8", "rgb:-"],
                          capture_output=True)
    if proc.returncode != 0 or len(proc.stdout) != w * h * 3:
        fail(f"读取 PNG 像素失败：{proc.stderr[-500:]}")
    return proc.stdout


def check_png(png: Path, raw_size: tuple[int, int], trimmed_size: tuple[int, int]) -> None:
    size = png_size(png)
    if size != (OUT_W, OUT_H):
        fail(f"成图尺寸 {size} ≠ {OUT_W}×{OUT_H}")
    if png.stat().st_size < 200_000:
        fail(f"成图只有 {png.stat().st_size} 字节，像是空图")
    # 边角是纸色（trim + extent 的收边色）
    proc = subprocess.run([CONVERT, str(png), "-format", "%[pixel:p{4,4}]", "info:"],
                          capture_output=True, text=True)
    corner = proc.stdout.strip()
    if "244,241,234" not in corner.replace(" ", ""):
        print(f"  ! 边角像素是 {corner}（预期纸色 srgb(244,241,234)，可能只是取色偏差）")
    # 四阶段「暖度」逐级上升：同一栋房子从左到右越来越暖
    w, h = 800, 400
    raw = pixel_grid(png, w, h)
    bands = [(16, 194), (212, 391), (409, 587), (605, 784)]
    warm: list[float] = []
    for x0, x1 in bands:
        hit = total = 0
        for y in range(0, h):
            base = y * w * 3
            for x in range(x0, x1):
                i = base + x * 3
                r, g, b = raw[i], raw[i + 1], raw[i + 2]
                total += 1
                if r > 140 and r - b > 40 and g > 55 and g < 215:
                    hit += 1
        warm.append(hit / total * 100.0)
    print("  · 四阶段暖色占比（%）：" + "  ".join(f"{v:.2f}" for v in warm))
    if not (warm[0] < warm[1] < warm[2] < warm[3]):
        fail(f"四个阶段没有从左到右逐步变暖：{warm}")
    if warm[0] > 4.0:
        fail(f"毛坯房阶段暖色占比 {warm[0]:.2f}% 太高（L1 应该是冷灰）")
    # 无用户名 / 绝对路径 / 口令（PNG 文本块也查）
    blob = png.read_bytes().decode("latin-1", "ignore")
    check_text_forbidden(blob, "house-4stages.png")
    print(f"  ✓ 成图：{size[0]}×{size[1]}，{png.stat().st_size // 1024} KB；"
          f"截图 {raw_size[0]}×{raw_size[1]} → -trim {trimmed_size[0]}×{trimmed_size[1]} → 回画布；"
          f"四阶段暖度单调上升 {warm[0]:.2f} < {warm[1]:.2f} < {warm[2]:.2f} < {warm[3]:.2f}")


# ------------------------------------------------------------------ 主流程

def main() -> int:
    if not Path(CHROME).exists():
        fail(f"找不到 Chrome：{CHROME}")
    if not Path(CONVERT).exists():
        fail(f"找不到 ImageMagick convert：{CONVERT}")
    print("① 读数据 + 口径自检")
    data = load_json(DATA_PATH, "data.json")
    stages_doc = load_json(STAGES_PATH, "stages.json")
    validate_inputs(data, stages_doc)

    print("② 组版 house.html（手绘感 SVG × 4 阶段 + 12 枚徽章 + 轻交互）")
    page = build_html(data, stages_doc)
    check_html(page, data, stages_doc)
    OUT_HTML.write_text(page, encoding="utf-8")
    print(f"  ✓ 写入 tutorial/maturity/house.html（{OUT_HTML.stat().st_size // 1024} KB，零外部请求）")

    with tempfile.TemporaryDirectory(prefix="house-") as td:
        work = Path(td)
        print("③ 页面内置自检（Chrome --dump-dom）")
        metrics = parse_selftest(dump_dom(OUT_HTML, work))
        check_metrics(metrics, data, stages_doc)
        print("④ 截图（Chrome --headless --screenshot @2x）")
        raw = work / "raw.png"
        screenshot(OUT_HTML, raw, work)
        print("⑤ convert -trim 收边 + 回画布 + 成图自检")
        raw_size, trimmed_size = trim_and_pad(raw, OUT_PNG, work)
        check_png(OUT_PNG, raw_size, trimmed_size)

    print("\n✓ 交付：")
    print(f"  tutorial/maturity/stages.json          （4 阶段定义）")
    print(f"  tutorial/maturity/house.html           （{OUT_HTML.stat().st_size // 1024} KB，离线可开）")
    print(f"  tutorial/maturity/house-4stages.png    （{OUT_W}×{OUT_H}，{OUT_PNG.stat().st_size // 1024} KB）")
    print(f"  重跑：{RERUN}")
    print("\n12 枚编号圆牌在房子上的位置：")
    for no in range(1, 13):
        spec = BADGES[no]
        a = {x["no"]: x for x in data["artifacts"]}[no]
        print(f"  {CIRCLED[no - 1]} {a['name']:<28s} → {spec['part']:<16s} "
              f"（钉点 {n(spec['anchor'][0])},{n(spec['anchor'][1])}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

