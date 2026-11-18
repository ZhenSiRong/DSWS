#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_map.py —— 《全书地图》：工地比喻 ↔ 我们这十页（一张 3200×2000 横版讲义）。

在仓库根目录一条命令重跑：

    python3 manual/shots/render_map.py

读：
    `manual/map/data.json`      单源数据：10 行对照 + 四阶段 + 诚实三行
    `manual/page-00.md … 09.md` 只抽 H1（页标题与页码自动同步，不手写）
    `manual/maturity/stages.json`（只读）四阶段口径：名称、L1–L4、累计长出件数
写：
    `manual/images/map-house-vs-pages.png`（1600×1000 CSS @2x → 3200×2000，横向讲义）

图在说什么（一句话）：**左边是工地上的一个动作，右边是我们这一页真正造出来的东西，
中间同号虚线把「比喻」和「交付物」钉在一起**；底部是同一栋房子的四阶段成熟度，
最后是「比方不贴」的诚实三行。

版式：左「工地：动作名 + 比喻句 + 简单 SVG 图标」／中「虚线 + 同号 0–9」／
右「第 N 页 + 从 page-0X.md 抽出的 H1 标题 + 这一页造什么」。黑白灰 + 橙色强调，
零外部 CDN / 字体 / 图片；中文用系统 Noto Sans CJK SC。

内置自检（任一不过就退出码 1，不写成品）：
  1. 数据：10 行、页码 page-00…page-09 各一次、字段齐全、四阶段 L1–L4、诚实 3 行；
  2. 页标题：从 `page-00.md … 09.md` 各抽 H1，必须是「第 N 页 · 标题」，N 与 data 的 page
     对得上；页面里渲染的标题必须逐字等于 md 的 H1（不手写、不漂移）；
  3. OVERVIEW.md：≤90 行、指向本图、10 行表格与 data 同步、不设页标题列、不写「第 N 页 · 标题」整串；
  4. 成品 HTML：无外链 / 无 src·href 资源、字体是系统 Noto Sans CJK、不溢出画布、
     10 个图标 / 10 个同号圆 / 4 段成熟度条 / 3 行诚实都齐；
  5. 成品 PNG：尺寸 3200×2000、非空、有橙色强调、左右两栏都有墨、无用户名/绝对路径/口令。

依赖：本机 python3、google-chrome、Noto Sans CJK SC、ImageMagick `convert`（仅取像素统计）。
只写 `manual/images/map-house-vs-pages.png`；page-0X.md 与本脚本都不改正文。
"""

from __future__ import annotations

import html
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
PAGES_DIR = REPO / "manual"
DATA_PATH = PAGES_DIR / "map" / "data.json"
STAGES_PATH = PAGES_DIR / "maturity" / "stages.json"
OVERVIEW_PATH = PAGES_DIR / "OVERVIEW.md"
PAGE00_PATH = PAGES_DIR / "page-00.md"
README_PATH = PAGES_DIR / "README.md"
OUT_PNG = PAGES_DIR / "images" / "map-house-vs-pages.png"

CHROME = "/usr/bin/google-chrome"
RERUN = "python3 manual/shots/render_map.py"

DESIGN_W, DESIGN_H = 1600, 1000                 # CSS 设计画布（横版讲义）
SCALE = 2
OUT_W, OUT_H = DESIGN_W * SCALE, DESIGN_H * SCALE  # 3200×2000

PAPER = "#F6F3EC"
PAGE_IDS = [f"page-{i:02d}" for i in range(10)]

# 每页在图上配哪个简单 SVG 图标（顺序 = page-00…page-09；图标名只用于自检与报告）。
ICON_IDS = [
    "三通一平",   # page-00：水电/管线接口 + 场地
    "地基",       # page-01：基础垫层 + 钢筋
    "隔墙",       # page-02：砖墙 + 材料箱
    "锅炉",       # page-03：常驻锅炉
    "对讲",       # page-04：门口对讲机
    "感应器",     # page-05：天花板感应器（耳朵）
    "电控箱",     # page-06：电控箱 + 接线
    "水表",       # page-07：市政水管 + 只读水表
    "水龙头",     # page-08：龙头 + 逐滴
    "窗和钥匙",   # page-09：窗户 + 交钥匙
]

# 不许出现在成品里（用户名 / 绝对路径 / 口令）；外链另行用正则查。
HOST_USER = Path.home().name
FORBIDDEN = [
    "/home/", "/Users/", "/tmp/", "/opt/", "/var/", "/root/", "file://", "C:\\",
    HOST_USER, "password", "passwd", "MYSQL_ROOT_PASSWORD", "REBUILD_DW_RO_PASSWORD",
    "sk-", "root@", "-uroot", "labpass",
]
# 目视抽查必须能认出的关键真值。
REQUIRED_TOKENS = ["41099.5", "115", "12 progress", "毛坯", "通水通电", "智能家居", "物业安防"]


def fail(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    raise SystemExit(1)


def esc(text: object) -> str:
    return html.escape(str(text), quote=False)


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


# ------------------------------------------------------------------ 页标题：只从 page-0X.md 抽

H1_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.M)
H1_NUMBER_RE = re.compile(r"^第\s*(?P<no>\d+)\s*页\s*·\s*(?P<tail>\S.*)$")


def extract_page_titles() -> dict[str, dict]:
    """返回 {page-00: {h1, no, tail}}；页标题唯一来源是正文 H1。"""
    titles: dict[str, dict] = {}
    for idx, pid in enumerate(PAGE_IDS):
        path = PAGES_DIR / f"{pid}.md"
        if not path.exists():
            fail(f"找不到正文页 {path.relative_to(REPO)}（页标题必须从正文 H1 提取）")
        text = path.read_text(encoding="utf-8")
        m = H1_RE.search(text)
        if not m:
            fail(f"{path.relative_to(REPO)} 里找不到 H1（形如「# 第 {idx} 页 · 标题」）")
        h1 = m.group("title").strip()
        num = H1_NUMBER_RE.match(h1)
        if not num:
            fail(f"{path.relative_to(REPO)} 的 H1 不是「第 N 页 · 标题」格式：{h1!r}")
        if int(num.group("no")) != idx:
            fail(f"{path.relative_to(REPO)} 的 H1 页码是第 {num.group('no')} 页，"
                 f"与文件名 {pid} 不一致")
        titles[pid] = dict(h1=h1, no=int(num.group("no")), tail=num.group("tail").strip())
    return titles


# ------------------------------------------------------------------ 数据 + 口径自检

def validate_data(data: dict, titles: dict, stages_doc: dict) -> dict:
    errs: list[str] = []
    for key in ("title", "kicker", "one_liner", "image", "rerun", "note"):
        if not str(data.get(key, "")).strip():
            errs.append(f"data.json 缺 {key}")
    if data.get("rerun") != RERUN:
        errs.append(f"data.json rerun 应为本脚本命令 {RERUN!r}")
    if data.get("image") != "images/map-house-vs-pages.png":
        errs.append("data.json image 必须是 images/map-house-vs-pages.png")

    rows = data.get("rows") or []
    if len(rows) != 10:
        errs.append(f"data.json 里 {len(rows)} 行，口径是 10 行（page-00…page-09 每页一行）")
    if [r.get("page") for r in rows] != PAGE_IDS:
        errs.append(f"data.json 的 page 顺序 {[r.get('page') for r in rows]} 必须是 {PAGE_IDS}")
    for i, r in enumerate(rows):
        for key in ("page", "site_action", "metaphor", "build"):
            if not str(r.get(key, "")).strip():
                errs.append(f"第 {i} 行缺 {key}")
        if "|" in "".join(str(r.get(k, "")) for k in ("site_action", "metaphor", "build")):
            errs.append(f"第 {i} 行内容含竖线 |，会撑坏 Markdown 表格")
        for key in ("site_action", "metaphor", "build"):
            if any(b and b in str(r.get(key, "")) for b in FORBIDDEN):
                errs.append(f"{r.get('page')} 的 {key} 含禁用字符串（用户名/绝对路径/口令）")

    stages = data.get("stages") or []
    if len(stages) != 4:
        errs.append(f"data.json 里 {len(stages)} 个阶段，口径是 4 个")
    if [s.get("level") for s in stages] != ["L1", "L2", "L3", "L4"]:
        errs.append("四阶段 level 必须是 L1–L4 连续")
    for i, s in enumerate(stages):
        for key in ("level", "name", "live", "software"):
            if not str(s.get(key, "")).strip():
                errs.append(f"阶段 {i + 1} 缺 {key}")
        if "软件里对应" not in str(s.get("software", "")):
            errs.append(f"阶段 {i + 1} 的 software 要写明「软件里对应 Lx」")

    # 四阶段口径与 maturity/stages.json 对齐（只读它，不改它）。
    mat_stages = stages_doc.get("stages") or []
    cum: list[int] = []
    grown_total = 0
    if len(mat_stages) != 4:
        errs.append(f"maturity/stages.json 里 {len(mat_stages)} 个阶段，口径是 4 个")
    else:
        for i, (s, ms) in enumerate(zip(stages, mat_stages)):
            grown_total += len(ms.get("artifacts_grown") or [])
            cum.append(grown_total)
            if ms.get("level") != s["level"]:
                errs.append(f"阶段 {i + 1} level={s['level']} 与 stages.json 的 {ms.get('level')} 不一致")
            if not (s["name"] in str(ms.get("name", "")) or str(ms.get("name", "")) in s["name"]):
                errs.append(f"阶段 {i + 1} 名称 {s['name']!r} 与 stages.json 的 "
                            f"{ms.get('name')!r} 不同口径")
        if grown_total != 12:
            errs.append(f"stages.json 四阶段长出件数合计 {grown_total}，口径是 12")
    if not OVERVIEW_PATH.exists():
        errs.append("找不到 manual/OVERVIEW.md（本图的 Markdown 源页）")

    honest = data.get("honest") or []
    if len(honest) != 3:
        errs.append(f"data.json 里诚实 {len(honest)} 行，口径是 3 行")
    for i, h in enumerate(honest):
        for key in ("lead", "detail"):
            if not str(h.get(key, "")).strip():
                errs.append(f"诚实第 {i + 1} 行缺 {key}")

    # 页标题与 data 的 page 对照：数量 / 顺序已在上面对过，这里逐页确认 H1 抽到了。
    for idx, pid in enumerate(PAGE_IDS):
        t = titles.get(pid) or {}
        if int(t.get("no", -1)) != idx:
            errs.append(f"{pid} 的 H1 页码 {t.get('no')} 与 data 的 page 不一致")

    if errs:
        print("✗ 数据 / 页标题 / 口径自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    print("  ✓ 数据：10 行（page-00…page-09 各一次）、四阶段 L1–L4、诚实 3 行")
    print("  ✓ 页标题：从 page-00.md…page-09.md 各抽 H1，页码与 data 的 page 逐页对齐")
    print(f"  ✓ 四阶段口径：与 maturity/stages.json 一致，累计长出 {cum}/12 件")
    return dict(cum=cum, grown_total=grown_total)


# ------------------------------------------------------------------ OVERVIEW.md 同步自检

def validate_overview(data: dict, titles: dict) -> None:
    errs: list[str] = []
    overview = OVERVIEW_PATH.read_text(encoding="utf-8") if OVERVIEW_PATH.exists() else ""
    lines = overview.splitlines()
    if not overview:
        fail("manual/OVERVIEW.md 不存在或为空")
    if len(lines) > 90:
        errs.append(f"OVERVIEW.md 有 {len(lines)} 行，超过 90 行上限")
    if not lines or lines[0].strip() != "# 全书地图":
        errs.append("OVERVIEW.md 第一行必须是「# 全书地图」")
    if "![全书地图" not in overview or "images/map-house-vs-pages.png" not in overview:
        errs.append("OVERVIEW.md 开头要有一行指向 images/map-house-vs-pages.png 的图")
    if "生成脚本" not in overview or "page-0X.md" not in overview:
        errs.append("OVERVIEW.md 要约一句：页标题与页码由生成脚本从 page-0X.md 提取并同步")
    table_rows = [ln for ln in lines if ln.startswith("| page-")]
    if len(table_rows) != 10:
        errs.append(f"OVERVIEW.md 对照表有 {len(table_rows)} 行 page-，应为 10 行")
    for i, r in enumerate(data["rows"]):
        for key in ("site_action", "metaphor", "build"):
            if str(r[key]) not in overview:
                errs.append(f"OVERVIEW.md 与 data.json 不同步：第 {i} 行 {key} 缺 {r[key]!r}")
    for s in data["stages"]:
        if s["name"] not in overview or s["level"] not in overview:
            errs.append(f"OVERVIEW.md 缺阶段 {s['level']} {s['name']}")
    for h in data["honest"]:
        if h["lead"] not in overview:
            errs.append(f"OVERVIEW.md 缺诚实行「{h['lead']}」")
    # 页标题不得手写：对照表只许有「页 | 工地动作 | 比喻句 | 这一页造什么」四列，
    # 且不许出现「第 N 页 · 标题」整串；页标题只由渲染脚本从 page-0X.md 抽。
    if "| 页 | 工地动作 | 比喻句 | 这一页造什么 |" not in overview:
        errs.append("OVERVIEW.md 对照表表头必须是「| 页 | 工地动作 | 比喻句 | 这一页造什么 |」")
    for pid, t in titles.items():
        if t["h1"] in overview:
            errs.append(f"OVERVIEW.md 里手写了页标题整串「{t['h1']}」——"
                        f"页标题只许由脚本从 {pid}.md 提取")
            break
    if errs:
        print("✗ OVERVIEW.md 自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)
    print("  ✓ OVERVIEW.md：≤90 行、首行「# 全书地图」、指向本图、10 行与 data 同步、"
          "四列表头、未手写「第 N 页 · 标题」整串")


# ------------------------------------------------------------------ 简单 SVG 图标（viewBox 0 0 40 40）

def icon_wire() -> str:
    """page-00 三通一平：水滴 + 电 + 插头/管线，脚下一块干净场地。"""
    return (
        '<path class="accf" d="M11 8.5 C11 8.5 6.6 15 6.6 18.1 A4.3 4.3 0 0 0 15 18.1 '
        'C15 15 11 8.5 11 8.5 Z"/>'
        '<path class="accf" d="M21.6 5.5 L16.4 17 h4.1 L18.5 24.5 24.2 12.6 h-4.1 Z"/>'
        '<path d="M27.5 8 v6.4 a3.8 3.8 0 0 0 3.8 3.8 H36"/>'
        '<path d="M24 8 h3.5"/>'
        '<path d="M4 32.5 H36"/>'
        '<path class="acc" d="M7 32.5 h4 M17 32.5 h3 M29 32.5 h4"/>'
    )


def icon_foundation() -> str:
    """page-01 打地基：地坪线 + 地下垫层 + 钢筋 + 橙色基础底线。"""
    return (
        '<path d="M4 19.5 H36"/>'
        '<path d="M8.5 24 h23 v8.5 h-23 Z"/>'
        '<path d="M8.5 28.2 h23"/>'
        '<path d="M13 24 v-9.5 M18.5 24 v-12 M24 24 v-11 M29.5 24 v-8.5"/>'
        '<path class="acc" d="M8.5 32.5 h23"/>'
    )


def icon_wall() -> str:
    """page-02 隔墙 + 材料进场：砖墙 + 材料箱。"""
    return (
        '<path d="M5.5 13.5 h16.5 v18 h-16.5 Z"/>'
        '<path d="M5.5 19.5 h16.5 M5.5 25.5 h16.5"/>'
        '<path d="M11.75 13.5 v6 M16.5 19.5 v6 M11.75 25.5 v6"/>'
        '<path class="acc" d="M26.5 18.5 h9 v13 h-9 Z"/>'
        '<path class="acc" d="M26.5 18.5 L35.5 31.5 M35.5 18.5 L26.5 31.5"/>'
    )


def icon_boiler() -> str:
    """page-03 装锅炉（常驻）：锅炉本体 + 烟囱 + 橙色火苗。"""
    return (
        '<path d="M12.5 8.5 h6 v-4 h-6 Z"/>'
        '<path d="M9.5 8.5 h14 v22 a3 3 0 0 1 -3 3 h-8 a3 3 0 0 1 -3 -3 Z"/>'
        '<path d="M23.5 14.5 h5.5 a3 3 0 0 1 3 3 v9"/>'
        '<path d="M9.5 27.5 h14"/>'
        '<path class="accf" d="M16.5 29.5 c-2 0 -3.1 -1.4 -3.1 -2.9 0 -1.6 1.3 -2.3 2 -3.8 '
        '0.4 0.9 0.8 1.4 1.5 1.8 0.3 -1 0.9 -1.7 1.4 -2.4 0.3 1.5 1.7 2.4 1.7 4.1 0 1.7 -1.4 3.2 -3.5 3.2 Z"/>'
        '<circle cx="13.2" cy="14.5" r="1.8"/>'
    )


def icon_intercom() -> str:
    """page-04 装门铃/对讲：门口面板 + 喇叭 + 橙色按钮 + 铃声。"""
    return (
        '<path d="M12.5 6.5 h15 a2.5 2.5 0 0 1 2.5 2.5 v22 a2.5 2.5 0 0 1 -2.5 2.5 h-15 '
        'a2.5 2.5 0 0 1 -2.5 -2.5 v-22 a2.5 2.5 0 0 1 2.5 -2.5 Z"/>'
        '<circle cx="20" cy="11.5" r="2"/>'
        '<path d="M16.5 17 h7 M16.5 20.5 h7 M16.5 24 h4.5"/>'
        '<circle class="accf" cx="20" cy="28" r="2.4"/>'
        '<path class="acc" d="M31.5 12.5 a7 7 0 0 1 0 9"/>'
    )


def icon_sensor() -> str:
    """page-05 装感应器（耳朵）：天花板感应器 + 橙色声波。"""
    return (
        '<path d="M7 7 h26"/>'
        '<path d="M16 7 v2.5 a4 4 0 0 0 8 0 V7"/>'
        '<path d="M12.5 13.5 a7.5 7.5 0 0 1 15 0"/>'
        '<circle class="accf" cx="20" cy="16.2" r="1.5"/>'
        '<path class="acc" d="M30 13.5 a5.5 5.5 0 0 1 0 8"/>'
        '<path class="acc" d="M33 10.5 a10 10 0 0 1 0 14"/>'
        '<path d="M14 21.5 h12"/>'
    )


def icon_breaker() -> str:
    """page-06 照图纸接线：电控箱 + 空开 + 橙色的线。"""
    return (
        '<path d="M8 6.5 h24 v25 h-24 Z"/>'
        '<path d="M8 12.5 h24"/>'
        '<path d="M12.5 17 h3 v7 h-3 Z M18 17 h3 v7 h-3 Z M23.5 17 h3 v7 h-3 Z"/>'
        '<path class="acc" d="M13.9 20.5 L20 25.5 L21.5 33.5"/>'
        '<path d="M32 24 h4.5 v10"/>'
        '<path d="M8 10.5 h3"/>'
    )


def icon_meter() -> str:
    """page-07 接市政水管 + 装水表：进水管 + 只读表盘 + 橙色指针。"""
    return (
        '<path d="M3 20.5 h8 M29 20.5 h8"/>'
        '<circle cx="20" cy="20.5" r="9.5"/>'
        '<circle cx="20" cy="20.5" r="6.4" stroke-dasharray="1.2 2.1"/>'
        '<path class="acc" d="M20 20.5 L25.5 15"/>'
        '<path d="M20 9.5 v1.8 M20 29.7 v1.8 M10.5 20.5 h1.8 M27.7 20.5 h1.8"/>'
        '<path class="acc" d="M3 20.5 h3"/>'
    )


def icon_faucet() -> str:
    """page-08 装水龙头，一滴一滴：龙头 + 橙色水滴。"""
    return (
        '<path d="M9 32.5 v-14 a6 6 0 0 1 6 -6 h6"/>'
        '<path d="M21 12.5 v7"/>'
        '<path d="M15.5 8 h4 v4 h-4 Z"/>'
        '<path d="M9 32.5 h6"/>'
        '<path class="accf" d="M21 23 c0 0 -2.4 3.2 -2.4 5 a2.4 2.4 0 0 0 4.8 0 '
        'c0 -1.8 -2.4 -5 -2.4 -5 Z"/>'
        '<circle class="accf" cx="21" cy="32.5" r="1.3"/>'
    )


def icon_window_key() -> str:
    """page-09 装窗户 + 交钥匙：窗 + 橙色钥匙。"""
    return (
        '<path d="M5 8.5 h19 v20.5 h-19 Z"/>'
        '<path d="M14.5 8.5 v20.5 M5 18.75 h19"/>'
        '<path d="M4 32 h21"/>'
        '<path class="acc" d="M33 12.6 a3.4 3.4 0 1 1 -0.01 0 Z"/>'
        '<path class="acc" d="M33 16 v14 M33 24.5 h4 M33 28 h3"/>'
    )


ICON_FUNCS = {
    0: icon_wire, 1: icon_foundation, 2: icon_wall, 3: icon_boiler, 4: icon_intercom,
    5: icon_sensor, 6: icon_breaker, 7: icon_meter, 8: icon_faucet, 9: icon_window_key,
}

# 四阶段色条：黑白灰逐级变深，橙只做 Lx 强调。
STAGE_FILL = ["#F1ECE1", "#E2D9C8", "#C2B8A4", "#6F6759"]
STAGE_DARK = [False, False, False, True]


# ------------------------------------------------------------------ 组版 HTML

def build_svg(idx: int) -> str:
    return (f'<svg viewBox="0 0 40 40" role="img" aria-hidden="true" '
            f'data-icon="{esc(ICON_IDS[idx])}">{ICON_FUNCS[idx]()}</svg>')


def build_html(data: dict, titles: dict, cum: list[int]) -> str:
    rows_html: list[str] = []
    for idx, r in enumerate(data["rows"]):
        t = titles[r["page"]]
        rows_html.append(
            '<div class="row">'
            '<div class="site">'
            f'<span class="iconbox">{build_svg(idx)}</span>'
            '<div class="stext">'
            f'<div class="action">{esc(r["site_action"])}</div>'
            f'<div class="metaphor">{esc(r["metaphor"])}</div>'
            '</div></div>'
            f'<div class="conn"><span class="num">{t["no"]}</span></div>'
            '<div class="pagecell">'
            f'<span class="pagechip">第 {t["no"]} 页</span>'
            '<div class="ptext">'
            f'<div class="ptitle">{esc(t["tail"])}</div>'
            f'<div class="build">{esc(r["build"])}</div>'
            '</div></div>'
            '</div>'
        )
    stages_html = "".join(
        f'<div class="stage{" dark" if STAGE_DARK[i] else ""}" '
        f'style="background:{STAGE_FILL[i]}">'
        f'<div class="st-top"><span class="lv">{esc(s["level"])}</span>'
        f'<span class="nm">{esc(s["name"])}</span>'
        f'<span class="live">{esc(s["live"])}</span>'
        f'<span class="cnt">{cum[i]}/12 件</span></div>'
        f'<div class="sw">{esc(s["software"])}</div>'
        '</div>'
        for i, s in enumerate(data["stages"])
    )
    honest_html = "".join(
        f'<div class="honest-line"><span class="hno">{i + 1:02d}</span>'
        f'<span class="hlead">{esc(h["lead"])}</span>'
        f'<span class="hdetail">{esc(h["detail"])}</span></div>'
        for i, h in enumerate(data["honest"])
    )
    title = data["title"]
    assert title.startswith("全书地图 · ")
    # 大标题逐字用 data.json 的完整标题（含「全书地图 ·」前缀），kicker 只做导读。
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>全书地图 · 工地十动作 ↔ 我们这十页</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --paper: {PAPER}; --panel: #FFFDF8;
  --ink: #26231E; --ink2: #4E4940; --gray: #7A7368; --light: #A9A197;
  --hair: #E3DDD0; --hair2: #D6CFC0;
  --orange: #D9530F; --orange-deep: #B8430A; --orange-soft: #FBE8DC;
}}
html, body {{ background: var(--paper); }}
body {{
  width: {DESIGN_W}px; height: {DESIGN_H}px; overflow: hidden;
  font-family: "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC", sans-serif;
  color: var(--ink); -webkit-font-smoothing: antialiased;
}}
.page {{ width: {DESIGN_W}px; height: {DESIGN_H}px; padding: 30px 42px 16px;
         display: flex; flex-direction: column; }}

/* ---------- 页眉 ---------- */
header {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 26px; }}
.kicker {{ display: flex; align-items: center; gap: 8px; color: var(--orange);
          font-size: 13px; font-weight: 700; letter-spacing: 2.4px; }}
.kicker .dot {{ width: 9px; height: 9px; background: var(--orange); display: inline-block; }}
h1 {{ font-size: 27.5px; line-height: 1.18; font-weight: 800; letter-spacing: 0.4px;
      margin-top: 7px; }}
.sub {{ display: flex; align-items: center; gap: 9px; margin-top: 7px;
        font-size: 15.5px; color: var(--ink2); }}
.sub .bar {{ width: 4px; height: 17px; background: var(--orange); display: inline-block; }}
.legend {{ width: 420px; padding-bottom: 2px; text-align: right; }}
.leg-line {{ display: flex; align-items: center; justify-content: flex-end; gap: 8px;
             font-size: 12px; color: var(--ink2); }}
.leg-line .dash {{ width: 84px; border-top: 1.6px dashed var(--hair2); display: inline-block; }}
.leg-line .sample-num {{ width: 22px; height: 22px; border-radius: 50%; background: var(--orange);
                         color: #FFF9F2; font-size: 11.5px; font-weight: 800;
                         display: inline-flex; align-items: center; justify-content: center; }}
.leg-note {{ margin-top: 6px; font-size: 11px; color: var(--gray); line-height: 1.4; }}
.header-rule {{ margin-top: 12px; height: 3px;
                background: linear-gradient(90deg, var(--orange) 0 96px, var(--ink) 96px 100%); }}

/* ---------- 两栏表头 ---------- */
.colheads {{ display: grid; grid-template-columns: 620px 92px 1fr; align-items: baseline;
             margin-top: 9px; padding: 0 12px; }}
.ch {{ font-size: 13px; color: var(--ink2); display: flex; align-items: baseline; gap: 8px; }}
.ch b {{ font-size: 14px; font-weight: 800; color: var(--ink); }}
.ch span {{ font-size: 11px; color: var(--gray); }}
.ch.mid {{ justify-content: center; font-size: 10.5px; color: var(--light); letter-spacing: 1px; }}
.ch.right {{ justify-content: flex-start; }}

/* ---------- 10 行对照 ---------- */
.map {{ margin-top: 5px; background: var(--panel); border: 1px solid var(--hair2);
        border-radius: 9px; overflow: hidden; }}
.row {{ display: grid; grid-template-columns: 620px 92px 1fr; align-items: center;
        min-height: 56px; padding: 0 12px; }}
.row:nth-child(even) {{ background: #FAF7EF; }}
.row + .row {{ border-top: 1px solid var(--hair); }}
.site {{ display: flex; align-items: center; gap: 13px; }}
.iconbox {{ flex: none; width: 45px; height: 45px; border-radius: 9px;
            background: #F5F0E5; border: 1px solid #EAE3D4;
            display: flex; align-items: center; justify-content: center; }}
.iconbox svg {{ width: 34px; height: 34px; display: block; }}
.iconbox svg path, .iconbox svg rect, .iconbox svg circle {{ fill: none; stroke: var(--ink2);
    stroke-width: 1.65; stroke-linecap: round; stroke-linejoin: round; }}
.iconbox svg .acc {{ stroke: var(--orange); }}
.iconbox svg .accf {{ fill: var(--orange); stroke: none; }}
.stext {{ min-width: 0; }}
.action {{ font-size: 16px; font-weight: 800; letter-spacing: 0.3px; line-height: 1.25; }}
.metaphor {{ font-size: 13px; color: var(--gray); line-height: 1.35; margin-top: 2px;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

.conn {{ position: relative; align-self: stretch; display: flex; align-items: center;
         justify-content: center; }}
.conn::before {{ content: ""; position: absolute; left: 2px; right: 2px; top: 50%;
                 border-top: 1.6px dashed #C6BCAA; }}
.conn::after {{ content: "▸"; position: absolute; right: 0; top: 50%;
                transform: translateY(-58%); font-size: 9px; color: #B3A794; }}
.num {{ position: relative; z-index: 1; width: 27px; height: 27px; border-radius: 50%;
        background: var(--orange); color: #FFF9F2; font-size: 13px; font-weight: 800;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 0 0 3px var(--panel); }}

.pagecell {{ display: flex; align-items: center; gap: 13px; }}
.pagechip {{ flex: none; min-width: 70px; text-align: center; background: var(--ink);
             color: #F8F4EA; font-size: 11.5px; font-weight: 700; letter-spacing: 0.6px;
             padding: 4px 7px; border-radius: 4px; }}
.ptext {{ min-width: 0; }}
.ptitle {{ font-size: 16px; font-weight: 800; line-height: 1.25; letter-spacing: 0.2px;
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.build {{ font-size: 13px; color: var(--gray); line-height: 1.35; margin-top: 2px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

/* ---------- 四阶段成熟度条 ---------- */
.stages {{ margin-top: 12px; }}
.sechead {{ display: flex; align-items: baseline; justify-content: space-between; }}
.sectitle {{ font-size: 14.5px; font-weight: 800; }}
.sectitle .orange {{ color: var(--orange); }}
.secnote {{ font-size: 10.5px; color: var(--gray); }}
.stagebar {{ margin-top: 6px; display: grid; grid-template-columns: repeat(4, 1fr);
             border: 1px solid var(--hair2); border-radius: 8px; overflow: hidden;
             height: 67px; }}
.stage {{ padding: 8px 13px 7px; display: flex; flex-direction: column;
          justify-content: space-between; border-left: 1px solid rgba(84, 74, 58, 0.14); }}
.stage:first-child {{ border-left: 0; }}
.st-top {{ display: flex; align-items: baseline; gap: 7px; }}
.lv {{ font-size: 11px; font-weight: 800; letter-spacing: 0.8px; color: var(--orange-deep); }}
.nm {{ font-size: 15.5px; font-weight: 800; }}
.live {{ font-size: 11px; color: var(--gray); }}
.cnt {{ margin-left: auto; font-size: 10.5px; color: var(--gray); }}
.sw {{ font-size: 10.9px; line-height: 1.3; color: var(--ink2); }}
.dark .nm {{ color: #F8F4EA; }}
.dark .lv {{ color: #FFB183; }}
.dark .live, .dark .cnt {{ color: #DED6C7; }}
.dark .sw {{ color: #F0E9DC; }}

/* ---------- 诚实三行 ---------- */
.honest {{ margin-top: 12px; }}
.honest-lines {{ margin-top: 6px; border-top: 1px solid var(--hair); }}
.honest-line {{ display: flex; align-items: baseline; gap: 10px; padding: 4px 2px;
                border-bottom: 1px solid var(--hair); line-height: 1.4; }}
.hno {{ flex: none; width: 22px; font-size: 10px; font-weight: 800; color: var(--orange);
        letter-spacing: 0.5px; }}
.hlead {{ flex: none; font-size: 13px; font-weight: 800; }}
.hdetail {{ font-size: 12.3px; color: var(--gray); }}

/* ---------- 页脚 ---------- */
footer {{ margin-top: auto; border-top: 1px solid var(--hair2); padding-top: 6px;
          display: flex; justify-content: space-between; align-items: baseline;
          font-size: 10px; color: var(--light); letter-spacing: 0.3px; }}
footer b {{ color: var(--gray); font-weight: 700; }}
</style></head>
<body><div class="page">
  <header>
    <div class="hleft">
      <div class="kicker"><span class="dot"></span>导读 · 一页图看懂十页</div>
      <h1>{esc(title)}</h1>
      <div class="sub"><span class="bar"></span>{esc(data["one_liner"])}</div>
    </div>
    <div class="legend">
      <div class="leg-line"><span class="dash"></span><span class="sample-num">N</span>
        <span>同号虚线：左边工地动作，右边这一页</span></div>
      <div class="leg-note">左列是比喻层（为什么按这个顺序）<br>右列是交付层（盖完应该看到什么）</div>
    </div>
  </header>
  <div class="header-rule"></div>
  <div class="colheads">
    <div class="ch"><b>工地</b><span>我们做了什么动作 · 比喻句</span></div>
    <div class="ch mid">同号 0–9</div>
    <div class="ch right"><b>我们的页面</b><span>这一页真正造出什么 · 页标题自动来自正文</span></div>
  </div>
  <div class="map">
    {''.join(rows_html)}
  </div>
  <section class="stages">
    <div class="sechead">
      <div class="sectitle">四阶段成熟度 · <span class="orange">同一栋房子，一阶段比一阶段能住</span></div>
      <div class="secnote">口径同 manual/maturity/stages.json 与 house-4stages.png</div>
    </div>
    <div class="stagebar">{stages_html}</div>
  </section>
  <section class="honest">
    <div class="sechead"><div class="sectitle">诚实三行 · <span class="orange">比方不贴的地方，照实说</span></div>
      <div class="secnote">比喻只借骨架，不借结论</div></div>
    <div class="honest-lines">{honest_html}</div>
  </section>
  <footer>
    <div>数据源 <b>manual/map/data.json</b> · 页标题由脚本从 <b>manual/page-0X.md</b> 提取 ·
      四阶段只读 <b>manual/maturity/stages.json</b></div>
    <div>重跑：<b>{esc(RERUN)}</b> · 零外链 / 系统 Noto Sans CJK</div>
  </footer>
</div>
<script>
window.addEventListener('load', function () {{
  var q = function (s) {{ return Array.prototype.slice.call(document.querySelectorAll(s)); }};
  var metrics = {{
    rows: q('.row').length,
    numbers: q('.conn .num').map(function (e) {{ return e.textContent.trim(); }}),
    chips: q('.pagechip').map(function (e) {{ return e.textContent.trim(); }}),
    titles: q('.ptitle').map(function (e) {{ return e.textContent.trim(); }}),
    actions: q('.action').map(function (e) {{ return e.textContent.trim(); }}),
    builds: q('.build').map(function (e) {{ return e.textContent.trim(); }}),
    icons: q('.iconbox svg').length,
    iconIds: q('.iconbox svg').map(function (e) {{ return e.getAttribute('data-icon'); }}),
    stages: q('.stage').length,
    stageNames: q('.stage .nm').map(function (e) {{ return e.textContent.trim(); }}),
    stageLevels: q('.stage .lv').map(function (e) {{ return e.textContent.trim(); }}),
    stageCounts: q('.stage .cnt').map(function (e) {{ return e.textContent.trim(); }}),
    honest: q('.honest-line').length,
    resources: performance.getEntriesByType('resource').length,
    srcAttrs: document.querySelectorAll('[src],[href]').length,
    font: getComputedStyle(document.body).fontFamily,
    docW: document.documentElement.scrollWidth,
    docH: document.documentElement.scrollHeight,
    bodyW: document.body.scrollWidth,
    bodyH: document.body.scrollHeight,
    contentBottom: (function () {{
      var f = document.querySelector('footer');
      return f ? Math.round(f.getBoundingClientRect().bottom) : -1;
    }})(),
    h1: q('h1').map(function (e) {{ return e.textContent.trim(); }})[0] || '',
    stageBarHeight: Math.round(document.querySelector('.stagebar').getBoundingClientRect().height),
    mapRowsHeight: Math.round(document.querySelector('.map').getBoundingClientRect().height),
    mapClient: document.querySelector('.map').clientHeight,
    mapScroll: document.querySelector('.map').scrollHeight,
    rowsClipped: (function () {{
      var m = document.querySelector('.map');
      var cs = getComputedStyle(m);
      var contentBottom = m.getBoundingClientRect().bottom - parseFloat(cs.borderBottomWidth);
      return q('.row').filter(function (r) {{
        return r.getBoundingClientRect().bottom > contentBottom + 0.5;
      }}).length;
    }})(),
    pageClient: document.querySelector('.page').clientHeight,
    pageScroll: document.querySelector('.page').scrollHeight,
    truncated: q('.metaphor, .build, .ptitle').filter(function (e) {{
      return e.scrollWidth > e.clientWidth + 1;
    }}).map(function (e) {{ return e.className + ':' + e.textContent.trim().slice(0, 14); }})
  }};
  document.getElementById('selftest-data').textContent = JSON.stringify(metrics);
}});
</script>
<script id="selftest-data" type="application/json">{{}}</script>
</body></html>
"""


def scan_forbidden(text: str, where: str) -> None:
    for bad in FORBIDDEN:
        if bad and bad in text:
            fail(f"{where} 里出现禁用字符串 {bad!r}（不许出现用户名 / 绝对路径 / 口令）")
    if re.search(r"https?://", text):
        fail(f"{where} 里出现外链（不许有 http:// 或 https://）")
    for pat in (r"\bsrc\s*=", r"\bhref\s*=", r"@import", r"url\s*\("):
        if re.search(pat, text, re.I):
            fail(f"{where} 里出现外部资源引用 {pat!r}（必须零外链）")


# ------------------------------------------------------------------ Chrome

CHROME_BASE = [
    CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
    "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check",
    "--disable-extensions", "--mute-audio", "--font-render-hinting=none",
]


def run_chrome(args: list[str], timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(CHROME_BASE + args, capture_output=True, text=True, timeout=timeout)


def dump_dom(page: Path, work: Path) -> str:
    proc = run_chrome([f"--user-data-dir={work / 'chrome-dom'}", "--virtual-time-budget=2500",
                       "--dump-dom", page.as_uri()])
    if proc.returncode != 0:
        fail(f"Chrome --dump-dom 失败（{proc.returncode}）：{proc.stderr[-800:]}")
    return proc.stdout


def parse_selftest(dom: str) -> dict:
    m = re.search(r'<script[^>]*id="selftest-data"[^>]*>(.*?)</script>', dom, re.S)
    if not m:
        fail("页面内置自检没写回（--dump-dom 里没有 #selftest-data）")
    raw = html.unescape(m.group(1)).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        fail(f"页面内置自检内容不是 JSON：{raw[:200]!r}")
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        fail(f"页面内置自检 JSON 解析失败：{exc}")


def check_metrics(metrics: dict, data: dict, titles: dict, cum: list[int]) -> None:
    errs: list[str] = []
    want_titles = [titles[pid]["tail"] for pid in PAGE_IDS]
    want_chips = [f"第 {i} 页" for i in range(10)]
    if metrics.get("rows") != 10:
        errs.append(f"页面里 {metrics.get('rows')} 行，应为 10")
    if metrics.get("numbers") != [str(i) for i in range(10)]:
        errs.append(f"同号圆 {metrics.get('numbers')}，应为 0–9")
    if metrics.get("chips") != want_chips:
        errs.append(f"页码徽标 {metrics.get('chips')}，应为 {want_chips}")
    if metrics.get("titles") != want_titles:
        errs.append("页面里的页标题与 page-0X.md 的 H1 不一致（标题必须自动提取）：\n"
                    f"      页面 {metrics.get('titles')}\n      正文 {want_titles}")
    if metrics.get("actions") != [r["site_action"] for r in data["rows"]]:
        errs.append("页面里的工地动作与 data.json 不一致")
    if metrics.get("builds") != [r["build"] for r in data["rows"]]:
        errs.append("页面里的「这一页造什么」与 data.json 不一致")
    if metrics.get("icons") != 10:
        errs.append(f"页面里 {metrics.get('icons')} 个图标，应为 10（每页一个）")
    if metrics.get("iconIds") != ICON_IDS:
        errs.append(f"页面图标顺序 {metrics.get('iconIds')} 与设计口径不一致")
    if metrics.get("stages") != 4:
        errs.append(f"页面里 {metrics.get('stages')} 段成熟度条，应为 4")
    if metrics.get("stageNames") != [s["name"] for s in data["stages"]]:
        errs.append("页面四阶段名称与 data.json 不一致")
    if metrics.get("stageLevels") != ["L1", "L2", "L3", "L4"]:
        errs.append(f"页面四阶段 level {metrics.get('stageLevels')}，应为 L1–L4")
    want_cnt = [f"{c}/12 件" for c in cum]
    if metrics.get("stageCounts") != want_cnt:
        errs.append(f"页面四阶段累计件数 {metrics.get('stageCounts')}，应为 {want_cnt}")
    if metrics.get("honest") != 3:
        errs.append(f"页面里 {metrics.get('honest')} 行诚实，应为 3")
    if metrics.get("resources"):
        errs.append(f"页面发起了 {metrics['resources']} 个外部资源请求（必须 0）")
    if metrics.get("srcAttrs"):
        errs.append(f"页面有 src/href 资源引用 {metrics['srcAttrs']} 个（必须 0）")
    if "Noto Sans CJK SC" not in str(metrics.get("font", "")):
        errs.append(f"页面字体不是系统 Noto Sans CJK：{metrics.get('font')}")
    for key, limit in (("docW", DESIGN_W), ("bodyW", DESIGN_W), ("docH", DESIGN_H), ("bodyH", DESIGN_H)):
        if int(metrics.get(key, 0)) > limit:
            errs.append(f"页面 {key}={metrics.get(key)} 超出画布上限 {limit}（会裁切）")
    bottom = int(metrics.get("contentBottom", 0))
    if not (DESIGN_H - 40 <= bottom <= DESIGN_H - 8):
        errs.append(f"页脚底边 {bottom}px 不在 {DESIGN_H - 40}–{DESIGN_H - 8}px（版面没撑满或溢出）")
    if metrics.get("h1") != data["title"]:
        errs.append(f"H1 与 data.json 的完整标题不一致：{metrics.get('h1')!r}")
    if not (60 <= int(metrics.get("stageBarHeight", 0)) <= 90):
        errs.append(f"四阶段色条高度 {metrics.get('stageBarHeight')}px 不在 60–90px")
    if not (540 <= int(metrics.get("mapRowsHeight", 0)) <= 610):
        errs.append(f"10 行对照区高度 {metrics.get('mapRowsHeight')}px 不在 540–610px")
    if metrics.get("truncated"):
        errs.append(f"有文字被省略号截断（读者会看不全）：{metrics['truncated']}")
    if int(metrics.get("mapScroll", 0)) > int(metrics.get("mapClient", 0)) + 1:
        errs.append(f"10 行对照区被压缩裁切：map scroll {metrics.get('mapScroll')} > "
                    f"client {metrics.get('mapClient')}")
    if metrics.get("rowsClipped"):
        errs.append(f"有 {metrics.get('rowsClipped')} 行被 map 底边裁掉")
    if int(metrics.get("pageScroll", 0)) > int(metrics.get("pageClient", 0)) + 1:
        errs.append(f"整页内容超出 1000px 画布：page scroll {metrics.get('pageScroll')} > "
                    f"client {metrics.get('pageClient')}")
    if errs:
        print("✗ 页面内置自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)
    print("  ✓ 页面内置自检：10 行 / 同号 0–9 / 10 个标题逐字等于 page-0X.md 的 H1 / "
          "10 个图标 / 4 段成熟度条 / 3 行诚实 / 外部请求 0 / 系统 Noto Sans CJK / 不溢出、无裁切")


def screenshot(page: Path, raw_png: Path, work: Path) -> None:
    proc = run_chrome([f"--user-data-dir={work / 'chrome-shot'}",
                       f"--window-size={DESIGN_W},{DESIGN_H}",
                       f"--force-device-scale-factor={SCALE}",
                       f"--screenshot={raw_png}", "--virtual-time-budget=2500",
                       page.as_uri()])
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


# ------------------------------------------------------------------ 成图自检（像素）

PNG_TEXT_CHUNKS = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}


def scan_png_metadata(png: Path) -> None:
    """PNG 只查文本块 + 够长的禁用串；压缩像素数据是随机字节，短串会误报。"""
    blob = png.read_bytes()
    p, chunks = 8, []
    while p + 8 <= len(blob):
        ln = struct.unpack(">I", blob[p:p + 4])[0]
        typ = blob[p + 4:p + 8]
        if typ in PNG_TEXT_CHUNKS:
            chunks.append(typ.decode("latin-1"))
        p += 12 + ln
    if chunks:
        fail(f"map-house-vs-pages.png 带文本元数据块 {chunks}（不许夹带用户名/路径/口令）")
    text = blob.decode("latin-1", "ignore")
    for bad in FORBIDDEN:
        if len(bad) >= 6 and bad in text:
            fail(f"map-house-vs-pages.png 里出现禁用字符串 {bad!r}")
    if "http://" in text or "https://" in text:
        fail("map-house-vs-pages.png 里出现外链")


def check_png(png: Path) -> None:
    size = png_size(png)
    if size != (OUT_W, OUT_H):
        fail(f"成图尺寸 {size} ≠ {OUT_W}×{OUT_H}")
    if png.stat().st_size < 150_000:
        fail(f"成图只有 {png.stat().st_size} 字节，像是空图")
    scan_png_metadata(png)

    try:
        from PIL import Image
    except ImportError:
        fail("需要 Pillow 读像素做自检（python3 -c 'import PIL' 失败）")
    img = Image.open(png).convert("RGB")
    w, h = img.size
    small = img.resize((800, 500))
    px = list(small.getdata())

    def is_orange(r: int, g: int, b: int) -> bool:
        return r > 150 and 55 <= g <= 135 and b < 90

    def lum(r: int, g: int, b: int) -> float:
        return 0.299 * r + 0.587 * g + 0.114 * b

    total = len(px)
    orange = sum(1 for r, g, b in px if is_orange(r, g, b))
    ink = sum(1 for r, g, b in px if lum(r, g, b) < 110)
    light = sum(1 for r, g, b in px if lum(r, g, b) > 225)
    left_ink = sum(1 for i, (r, g, b) in enumerate(px) if i % 800 < 360 and lum(r, g, b) < 130)
    right_ink = sum(1 for i, (r, g, b) in enumerate(px) if i % 800 > 440 and lum(r, g, b) < 130)
    colors = len(set(px))
    stats = dict(orange=orange / total * 100, ink=ink / total * 100,
                 light=light / total * 100, colors=colors,
                 left_ink=left_ink / (360 * 500) * 100,
                 right_ink=right_ink / (360 * 500) * 100)
    if not (0.4 <= stats["orange"] <= 6.0):
        fail(f"橙色强调占比 {stats['orange']:.2f}% 不在 0.4%–6%")
    if not (2.0 <= stats["ink"] <= 30.0):
        fail(f"墨色占比 {stats['ink']:.2f}% 不在 2%–30%")
    if not (40.0 <= stats["light"] <= 95.0):
        fail(f"纸色占比 {stats['light']:.2f}% 不在 40%–95%")
    if stats["colors"] < 200:
        fail(f"成图只有 {stats['colors']} 种颜色，像没渲染出来")
    if stats["left_ink"] < 1.0 or stats["right_ink"] < 1.0:
        fail(f"左/右栏有一侧是空的（左 {stats['left_ink']:.2f}% / 右 {stats['right_ink']:.2f}%）")
    print(f"  ✓ 成图：{size[0]}×{size[1]}，{png.stat().st_size // 1024} KB；"
          f"橙色 {stats['orange']:.2f}% / 墨 {stats['ink']:.2f}% / 纸 {stats['light']:.2f}%；"
          f"左栏墨 {stats['left_ink']:.2f}% · 右栏墨 {stats['right_ink']:.2f}%；"
          f"无文本元数据 / 无用户名 / 绝对路径 / 口令")


# ------------------------------------------------------------------ 接入检查（软：只提醒，不拦渲染）

def check_hooks() -> None:
    ok: list[str] = []
    warn: list[str] = []
    p00 = PAGE00_PATH.read_text(encoding="utf-8") if PAGE00_PATH.exists() else ""
    hook = "> 全书在盖什么：先看 [全书地图](OVERVIEW.md)（一页图，10 分钟看懂整本）。"
    if hook in p00:
        ok.append("page-00.md 标题下已接「全书地图」入口")
    else:
        warn.append("page-00.md 缺约定的一行入口（> 全书在盖什么：先看 [全书地图](OVERVIEW.md)…）")
    readme = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    if "OVERVIEW.md" in readme and "images/map-house-vs-pages.png" in readme:
        ok.append("README.md 目录区已接 OVERVIEW.md + 本图")
    else:
        warn.append("README.md 目录区还没接 OVERVIEW.md / map-house-vs-pages.png")
    for line in ok:
        print(f"  ✓ 接入：{line}")
    for line in warn:
        print(f"  ! 接入：{line}")


# ------------------------------------------------------------------ 主流程

def main() -> int:
    if not Path(CHROME).exists():
        fail(f"找不到 Chrome：{CHROME}")
    print("① 读数据 + 页标题 + 口径自检")
    data = load_json(DATA_PATH, "data.json")
    stages_doc = load_json(STAGES_PATH, "stages.json")
    titles = extract_page_titles()
    info = validate_data(data, titles, stages_doc)
    validate_overview(data, titles)

    print("② 组版单页 HTML（10 行对照 + 10 个 SVG 图标 + 四阶段色条 + 诚实三行）")
    page = build_html(data, titles, info["cum"])
    scan_forbidden(page, "成品 HTML")
    print("  ✓ HTML 素材：零外链、无 src/href 资源引用、无用户名 / 绝对路径 / 口令")
    if "Noto Sans CJK SC" not in page:
        fail("CSS 没有指定系统中文字体 Noto Sans CJK SC")
    for token in REQUIRED_TOKENS:
        if token not in page:
            fail(f"成品 HTML 里缺少关键真值 {token!r}（图会讲不清）")
    with tempfile.TemporaryDirectory(prefix="map-render-") as tmp:
        work = Path(tmp)
        html_path = work / "map.html"
        html_path.write_text(page, encoding="utf-8")
        metrics = parse_selftest(dump_dom(html_path, work))
        check_metrics(metrics, data, titles, info["cum"])
        print("③ 无头 Chrome 截图 1600×1000 @2x")
        raw = work / "map.raw.png"
        screenshot(html_path, raw, work)
        png_bytes = raw.read_bytes()

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    OUT_PNG.write_bytes(png_bytes)
    print("④ 成图自检")
    check_png(OUT_PNG)
    print("⑤ 接入检查")
    check_hooks()
    print(f"\n✓ 完成：{OUT_PNG.relative_to(REPO)}  {OUT_W}×{OUT_H}  "
          f"{OUT_PNG.stat().st_size // 1024} KB")
    print(f"  重跑：{RERUN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
