#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_map.py —— 《全书地图》城市版：十座设施 ↔ 我们这十页（一张 3200×2000 横版讲义）。

在仓库根目录一条命令重跑：

    python3 tutorial/shots/render_map.py

读：
    `tutorial/city/data.json`       单源数据：10 件设施（P0–P9）+ 23 页标题 + 12 件交付物 + 四区 + 道路
    `tutorial/city/stages-city.json` 城市四阶段单源（阶段名 / 一句话 / 横切系统 / 页段，必须存在）
    `tutorial/page-00.md … 09.md`   只抽 H1（页标题与页码自动同步，不手写）
    `tutorial/OVERVIEW.md`          四阶段城市口径与诚实三行（图与 Markdown 同源，逐字同步）
写：
    `tutorial/images/map-city-vs-pages.png`（1600×1000 CSS @2x → 3200×2000，横向讲义）

图在说什么（一句话）：**左边是城市里的一座设施（场地 / 楼 / 楼内房间 / 流线）与它回答的问题，
右边是我们这一页真正造出来的东西，中间同号虚线把「比喻」和「交付物」钉在一起**；
底部是同一片城区的四阶段成熟度，最后是「比方不贴」的诚实三行。

版式：左「设施：城市名 + 问题 → 方案 + 简单 SVG 图标」／中「虚线 + 同号 0–9」／
右「第 N 页 + 从 page-0X.md 抽出的 H1 标题 + 造什么 + 交付物徽章」。黑白灰 + 橙色强调，
零外部 CDN / 字体 / 图片；中文用系统 Noto Sans CJK SC。

内置自检（任一不过就退出码 1，不写成品）：
  1. 数据：city/data.json 的 4 区 / 10 设施 P0–P9 / 23 页标题（10+4+4+5）/ 12 件交付物各一次 /
     道路非空；页标题只从 `page-00.md … 09.md` 各抽 H1，必须是「第 N 页 · 标题」，N 与文件名一致；
  2. OVERVIEW.md：≤100 行、首行固定城市版 H1、指向本图与 city/city-map.html、10 行对照表与
     city/data.json 逐字同步（设施名 / 问题 / 方案 / 造什么 / 交付物徽章）、四阶段 4 行与
     city/stages-city.json 逐字同步（阶段名 / 一句话 / 横切系统）、诚实 3 行、
     不手写「第 N 页 · 标题」整串；
  3. 成品 HTML：无外链 / 无 src·href 资源、字体是系统 Noto Sans CJK、不溢出画布、
     10 个图标 / 10 个同号圆 / 12 个交付物徽章 / 4 段成熟度（名称·一句话·横切系统同上）/ 3 行诚实都齐；
  4. 成品 PNG：尺寸 3200×2000、非空、有橙色强调、左右两栏都有墨、无用户名/绝对路径/口令。

依赖：本机 python3、google-chrome、Noto Sans CJK SC、Pillow（像素统计）。
只写 `tutorial/images/map-city-vs-pages.png`；page-0X.md、city/ 与 OVERVIEW 正文之外的东西都不改。
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

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
PAGES_DIR = REPO / "manual"
CITY_DIR = PAGES_DIR / "city"
DATA_PATH = CITY_DIR / "data.json"              # 城市版单源（只读）
STAGES_CITY_PATH = CITY_DIR / "stages-city.json"  # 必须：城市四阶段单源（只读）
OVERVIEW_PATH = PAGES_DIR / "OVERVIEW.md"
PAGE00_PATH = PAGES_DIR / "page-00.md"
README_PATH = PAGES_DIR / "README.md"
OUT_PNG = PAGES_DIR / "images" / "map-city-vs-pages.png"

CHROME = "/usr/bin/google-chrome"
RERUN = "python3 tutorial/shots/render_map.py"

DESIGN_W, DESIGN_H = 1600, 1000                 # CSS 设计画布（横版讲义）
SCALE = 2
OUT_W, OUT_H = DESIGN_W * SCALE, DESIGN_H * SCALE  # 3200×2000

PAGE_IDS = [f"page-{i:02d}" for i in range(10)]
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"

# 全书地图的城市版 H1（OVERVIEW.md 第一行；图内大标题逐字用它）。
H1_WANT = "全书地图 · 一片空地，十座设施，一段一段接通管网"

# 城市版四阶段（D44：造 / 换 / 审 / 守；10 + 4 + 4 + 5 = 23 页）：
# 阶段名 / 动作 / 页段 / 一句话（subtitle）/ 横切系统（crosscut）全部来自
# city/stages-city.json，本脚本只固定级号顺序，不写死四阶段内容；
# 页数与页段再与 city/data.json 的 levels 交叉校验。
STAGE_LEVELS = ["L1", "L2", "L3", "L4"]
STAGE_PAGE_COUNTS = [10, 4, 4, 5]

# 每件设施在图上配哪个简单 SVG 图标（顺序 = P0…P9；图标名只用于自检与报告）。
ICON_IDS = [
    "场地平整",   # P0 市政配套 · 场地平整
    "仓库大楼",   # P1 数据仓库大楼
    "货架分区",   # P2 仓库分区与入库通道
    "服务中心",   # P3 查询服务中心
    "服务窗口",   # P4 对外服务窗口
    "接待柜台",   # P5 前台接待台
    "规则室",     # P6 办事指南与规则室
    "取货通道",   # P7 取货通道
    "传送带",     # P8 传送带
    "城市门户",   # P9 城市门户 + 道路网
]

# 不许出现在成品里（用户名 / 绝对路径 / 口令）；外链另行用正则查。
HOST_USER = Path.home().name
FORBIDDEN = [
    "/home/", "/Users/", "/tmp/", "/opt/", "/var/", "/root/", "file://", "C:\\",
    HOST_USER, "password", "passwd", "MYSQL_ROOT_PASSWORD", "REBUILD_DW_RO_PASSWORD",
    "sk-", "root@", "-uroot", "labpass",
]
# 目视抽查必须能认出的关键真值。
REQUIRED_TOKENS = ["41099.5", "115", "12 条 progress", "荒地工地", "通水电网", "智慧城市",
                   "城市安防", "P0", "P9", "①", "⑫", "第 0 页", "第 9 页"]


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


# ------------------------------------------------------------------ city/data.json 自检

def validate_city_data(data: dict) -> dict:
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    for key in ("schema", "decision", "title", "one_liner", "canvas", "levels", "zones",
                "facilities", "roads", "titles"):
        need(str(data.get(key, "")).strip() != "" or isinstance(data.get(key), (list, dict)),
             f"city/data.json 缺 {key}")
    if errs:
        print("✗ city/data.json 结构不完整：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    need(data.get("decision") == "D45", "city/data.json 的 decision 应为 D45")
    need(data.get("canvas") == {"w": 1600, "h": 1000},
         f"city/data.json 的 canvas 应为 1600×1000，实为 {data.get('canvas')}")
    need(bool(str(data.get("one_liner", "")).strip()), "city/data.json 缺 one_liner（全书一句话主旨）")

    # 四区
    zones = data["zones"]
    need(isinstance(zones, list) and len(zones) == 4, f"应为 4 个区（四层），实为 {len(zones)}")
    for z in zones:
        need(all(str(z.get(k, "")).strip() for k in ("id", "name", "layer", "level", "maps_to")),
             f"区 {z.get('id')} 缺 id / name / layer / level / maps_to")

    # 四阶段页码口径（city/data.json 的 levels 与 D44 的 10+4+4+5 = 23 对齐）
    levels = data["levels"]
    need([lv.get("level") for lv in levels] == ["L1 造", "L2 换", "L3 审", "L4 守"],
         f"levels 应为 L1 造 / L2 换 / L3 审 / L4 守，实为 {[lv.get('level') for lv in levels]}")
    need([lv.get("count") for lv in levels] == STAGE_PAGE_COUNTS,
         f"levels 页数应为 {STAGE_PAGE_COUNTS}，实为 {[lv.get('count') for lv in levels]}")
    need(sum(int(lv.get("count", 0)) for lv in levels) == 23, "levels 页数合计应为 23")
    for lv in levels:
        need(bool(str(lv.get("theme", "")).strip()) and bool(str(lv.get("desc", "")).strip()),
             f"{lv.get('level')} 缺 theme / desc")

    # 十件设施 P0–P9 + 十二件交付物各一次
    facs = data["facilities"]
    need(isinstance(facs, list) and len(facs) == 10, f"应为 10 件设施 P0–P9，实为 {len(facs)}")
    need([f.get("no") for f in facs] == [f"P{i}" for i in range(10)],
         "设施编号应为 P0–P9 顺序")
    artifacts: dict[int, str] = {}
    for i, f in enumerate(facs):
        no = str(f.get("no", ""))
        for k in ("no", "name", "kind", "soft", "problem", "solution", "page", "page_id", "artifacts"):
            need(k in f and str(f.get(k, "")).strip() != "", f"{no or f'第 {i} 件'} 缺 {k}")
        need(f.get("page_id") == f"page-{i:02d}", f"{no} 的 page_id 应为 page-{i:02d}")
        need(f.get("page") == f"第 {i} 页", f"{no} 的 page 应为「第 {i} 页」")
        arts = f.get("artifacts")
        need(isinstance(arts, list) and 1 <= len(arts) <= 2, f"{no} 的 artifacts 应为 1–2 件")
        for a in arts if isinstance(arts, list) else []:
            need(isinstance(a, int) and 1 <= a <= 12, f"{no} 的交付物编号 {a} 不在 1–12")
            if isinstance(a, int) and 1 <= a <= 12:
                need(a not in artifacts,
                     f"交付物 {CIRCLED[a - 1]} 重复出现在 {artifacts.get(a)} 与 {no}")
                artifacts[a] = no
        for k in ("name", "soft", "problem", "solution"):
            need("|" not in str(f.get(k, "")), f"{no} 的 {k} 含竖线 |，会撑坏 Markdown 表格")
    need(sorted(artifacts) == list(range(1, 13)),
         f"12 件交付物应各出现一次，实为 {sorted(artifacts)}")

    # 23 页标题：P0–P22，10+4+4+5，P0–P9 与设施的问题 / 方案 / 判据逐字一致
    titles = data["titles"]
    need(isinstance(titles, list) and len(titles) == 23, f"应为 23 页标题，实为 {len(titles)}")
    need([t.get("page") for t in titles] == [f"P{i}" for i in range(23)],
         "23 页标题的 page 应为 P0–P22 顺序")
    for i, t in enumerate(titles):
        for k in ("page", "page_id", "level", "problem", "solution", "criterion"):
            need(k in t and str(t.get(k, "")).strip() != "", f"标题 P{i} 缺 {k}")
        need(t.get("page_id") == f"page-{i:02d}", f"标题 P{i} 的 page_id 应为 page-{i:02d}")
        for k in ("problem", "solution", "criterion"):
            need("|" not in str(t.get(k, "")), f"标题 P{i} 的 {k} 含竖线 |")
    want_levels = (["L1 造"] * 10) + (["L2 换"] * 4) + (["L3 审"] * 4) + (["L4 守"] * 5)
    need([t.get("level") for t in titles] == want_levels,
         "23 页标题的级应为 10×L1 造 / 4×L2 换 / 4×L3 审 / 5×L4 守")
    for i in range(10):
        f, t = facs[i], titles[i]
        need(t.get("problem") == f.get("problem"),
             f"标题 P{i} 的问题与设施 {f.get('no')} 不一致（同一份 city/data.json 内应逐字相同）")
        need(t.get("solution") == f.get("solution"),
             f"标题 P{i} 的方案与设施 {f.get('no')} 不一致（同一份 city/data.json 内应逐字相同）")
        need(t.get("criterion") == f.get("criterion"),
             f"标题 P{i} 的判据与设施 {f.get('no')} 不一致（同一份 city/data.json 内应逐字相同）")

    # 道路 / 管网
    roads = data["roads"]
    need(isinstance(roads, list) and len(roads) >= 10,
         f"道路 / 管网应至少 10 条，实为 {len(roads) if isinstance(roads, list) else roads}")

    if errs:
        print("✗ city/data.json 自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    print("  ✓ city/data.json：4 区 / 10 设施 P0–P9 / 12 件交付物各一次 / "
          f"{len(roads)} 条道路 / 23 页标题（10+4+4+5）")
    return dict(facs=facs, titles=titles, artifacts=artifacts)


# ------------------------------------------------------------------ OVERVIEW.md 解析 + 同步自检

TAB_RE = re.compile(r"^\|(?P<body>.+)\|\s*$")
FAC_ROW_RE = re.compile(r"^\|\s*(page-\d{2})\s*\|")
STAGE_ROW_RE = re.compile(r"^\|\s*(L[1-4])\s*\|")
HONEST_ROW_RE = re.compile(r"^\|\s*(0[1-3])\s*\|")


def table_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


# ------------------------------------------------------------------ 四阶段：读 city/stages-city.json（只读单源）

STAGE_KEYS = ("level", "name", "action", "subtitle", "crosscut", "pages")


def load_stages_city(data: dict) -> list[dict]:
    """读 city/stages-city.json：四阶段 = 阶段名 + 一句话（subtitle）+ 横切系统（crosscut）+ 页段。

    四阶段内容不在本脚本里写死；这里只固定 L1–L4 的顺序，并把级号 / 动作 / 页段 / 页数
    与 city/data.json 的 levels 交叉校验。返回 OVERVIEW 与图共用的规范化口径。
    """
    doc = load_json(STAGES_CITY_PATH, "city/stages-city.json（城市四阶段单源）")
    if doc.get("schema") != "manual-city-stages/1":
        fail(f"city/stages-city.json 的 schema 应为 manual-city-stages/1，实为 {doc.get('schema')!r}")
    raw = doc.get("stages")
    if not isinstance(raw, list) or len(raw) != 4:
        fail(f"city/stages-city.json 的 stages 应为 4 个阶段，实为 "
             f"{len(raw) if isinstance(raw, list) else raw!r}")
    levels = data["levels"]
    stages: list[dict] = []
    for i, st in enumerate(raw):
        if not isinstance(st, dict):
            fail(f"city/stages-city.json 第 {i + 1} 个阶段不是对象：{st!r}")
        for key in STAGE_KEYS:
            if not str(st.get(key, "")).strip():
                fail(f"city/stages-city.json 第 {i + 1} 个阶段缺 {key}")
        code = str(st["level"]).strip()
        if code != STAGE_LEVELS[i]:
            fail(f"city/stages-city.json 第 {i + 1} 个阶段 level 应为 {STAGE_LEVELS[i]}，实为 {code!r}")
        action = str(st["action"]).strip()
        lv = levels[i]
        if str(lv.get("level", "")).strip() != f"{code} {action}":
            fail(f"city/data.json 的 levels[{i}] 应为「{code} {action}」，"
                 f"实为 {lv.get('level')!r}")
        pages = str(st["pages"]).strip()
        if pages != str(lv.get("pages", "")).strip():
            fail(f"city/stages-city.json 的 {code} 页段 {pages!r} 与 city/data.json 的 "
                 f"levels[{i}] {lv.get('pages')!r} 不一致")
        if int(lv.get("count", 0)) != STAGE_PAGE_COUNTS[i]:
            fail(f"city/data.json 的 levels[{i}] 页数应为 {STAGE_PAGE_COUNTS[i]}，"
                 f"实为 {lv.get('count')!r}")
        stages.append(dict(level=code, name=str(st["name"]).strip(), action=action,
                           pages=pages, count=int(lv["count"]),
                           city=str(st["subtitle"]).strip(),
                           soft=str(st["crosscut"]).strip()))
    print(f"  ✓ city/stages-city.json：4 阶段 L1–L4（{', '.join(s['name'] for s in stages)}）；"
          "级别 / 动作 / 页段 / 页数与 city/data.json 交叉校验通过（四阶段内容不再写死）")
    return stages


def parse_overview(data: dict, titles: dict[str, dict], stages: list[dict]) -> dict:
    """读 OVERVIEW.md：H1 / 10 行对照 / 四阶段 / 诚实三行，并逐字对齐 city/data.json 与四阶段单源。"""
    if not OVERVIEW_PATH.exists():
        fail("找不到 tutorial/OVERVIEW.md（本图的 Markdown 源页）")
    overview = OVERVIEW_PATH.read_text(encoding="utf-8")
    lines = overview.splitlines()
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    need(len(lines) <= 100, f"OVERVIEW.md 有 {len(lines)} 行，超过 100 行上限")
    need(bool(lines) and lines[0].strip() == f"# {H1_WANT}",
         f"OVERVIEW.md 第一行必须是「# {H1_WANT}」")
    need("![全书地图" in overview and "images/map-city-vs-pages.png" in overview,
         "OVERVIEW.md 开头要有一行指向 images/map-city-vs-pages.png 的图")
    need("city/city-map.html" in overview,
         "OVERVIEW.md 要指向城市版 L1 全景 city/city-map.html")
    need("生成脚本" in overview and "page-0X.md" in overview,
         "OVERVIEW.md 要约一句：页标题与页码由生成脚本从 page-0X.md 提取并同步")
    need(str(data["one_liner"]) in overview,
         f"OVERVIEW.md 要逐字包含 city/data.json 的 one_liner：{data['one_liner']!r}")

    # 10 行对照表
    fac_rows = [ln for ln in lines if FAC_ROW_RE.match(ln)]
    need(len(fac_rows) == 10, f"OVERVIEW.md 对照表有 {len(fac_rows)} 行 page-，应为 10 行")
    parsed_rows: list[dict] = []
    for i, ln in enumerate(fac_rows):
        cells = table_cells(ln)
        f = data["facilities"][i] if i < len(data["facilities"]) else {}
        fno, fname = str(f.get("no", "")), str(f.get("name", ""))
        want_badges = "".join(CIRCLED[a - 1] for a in (f.get("artifacts") or []))
        want = [f"page-{i:02d}", f"{fno} {fname}", str(f.get("problem", "")),
                str(f.get("solution", "")), str(f.get("soft", "")), want_badges]
        if len(cells) != 6:
            errs.append(f"对照表第 {i} 行有 {len(cells)} 列，应为 6 列：{ln[:80]}")
            continue
        for col, (got, expect) in enumerate(zip(cells, want)):
            if got != expect:
                errs.append(f"对照表第 {i} 行第 {col + 1} 列与 city/data.json 不同步："
                            f"OVERVIEW={got!r}，data={expect!r}")
        parsed_rows.append(dict(page_id=f"page-{i:02d}", no=fno, name=fname,
                                problem=cells[2], solution=cells[3],
                                soft=cells[4], badges=cells[5],
                                artifacts=list(f.get("artifacts") or [])))
    need([r["page_id"] for r in parsed_rows] == PAGE_IDS,
         "对照表的 page-00…page-09 顺序不对")
    need(len(fac_rows) == 10, "对照表不足 10 行")

    # 四阶段成熟度表：阶段名 / 一句话 / 横切系统与 city/stages-city.json 逐字同步，
    # 页段与 city/data.json 的 levels 逐字同步
    stage_rows = [ln for ln in lines if STAGE_ROW_RE.match(ln)]
    need(len(stage_rows) == 4, f"OVERVIEW.md 四阶段表有 {len(stage_rows)} 行 L1–L4，应为 4 行")
    parsed_stages: list[dict] = []
    for i, ln in enumerate(stage_rows):
        cells = table_cells(ln)
        if len(cells) != 6:
            errs.append(f"四阶段表第 {i + 1} 行有 {len(cells)} 列，应为 6 列：{ln[:80]}")
            continue
        level, name, city_live, soft, action, pages = cells
        s = stages[i]
        want_pages = f"{s['pages']}（{s['count']} 页）"
        if level != s["level"]:
            errs.append(f"四阶段第 {i + 1} 行级应为 {s['level']}，实为 {level!r}")
        if name != s["name"]:
            errs.append(f"四阶段第 {i + 1} 行城市阶段名与 city/stages-city.json 的 name 不同步："
                        f"OVERVIEW={name!r}，data={s['name']!r}")
        if city_live != s["city"]:
            errs.append(f"四阶段第 {i + 1} 行「城市里长什么样」与 city/stages-city.json 的 "
                        f"subtitle 不同步：OVERVIEW={city_live!r}，data={s['city']!r}")
        if soft != s["soft"]:
            errs.append(f"四阶段第 {i + 1} 行「软件里对应（横切系统）」与 city/stages-city.json 的 "
                        f"crosscut 不同步：OVERVIEW={soft!r}，data={s['soft']!r}")
        if action != s["action"]:
            errs.append(f"四阶段第 {i + 1} 行学生动作应为 {s['action']}，实为 {action!r}")
        if pages != want_pages:
            errs.append(f"四阶段第 {i + 1} 行页段应为 {want_pages!r}，实为 {pages!r}"
                        "（页段 / 页数由 city/data.json 的 levels 提供）")
        parsed_stages.append(dict(level=level, name=name, city=city_live, soft=soft,
                                  action=action, pages=pages))
    need(len(parsed_stages) == 4, "四阶段表不足 4 行")

    # 诚实三行表
    honest_rows = [ln for ln in lines if HONEST_ROW_RE.match(ln)]
    need(len(honest_rows) == 3, f"OVERVIEW.md 诚实三行有 {len(honest_rows)} 行，应为 3 行")
    parsed_honest: list[dict] = []
    for i, ln in enumerate(honest_rows):
        cells = table_cells(ln)
        if len(cells) != 3:
            errs.append(f"诚实第 {i + 1} 行有 {len(cells)} 列，应为 3 列：{ln[:80]}")
            continue
        no, lead, detail = cells
        if no != f"{i + 1:02d}":
            errs.append(f"诚实第 {i + 1} 行编号应为 {i + 1:02d}，实为 {no!r}")
        if not lead or not detail:
            errs.append(f"诚实第 {i + 1} 行的「城市里不成立」与「软件里能」都不能为空")
        parsed_honest.append(dict(no=no, lead=lead, detail=detail))
    need(len(parsed_honest) == 3, "诚实表不足 3 行")

    # 四阶段已接入 city/stages-city.json，OVERVIEW 不许再留「待生成后同步」的占位口径。
    if "生成后同步" in overview:
        errs.append("OVERVIEW.md 还标注「待 city/stages-city.json 生成后同步」——"
                    "四阶段现在必须写正式口径（阶段名 / 一句话 / 横切系统）")

    # 页标题不得手写：整串「第 N 页 · 标题」不许出现在 OVERVIEW 里。
    for pid, t in titles.items():
        if t["h1"] in overview:
            errs.append(f"OVERVIEW.md 里手写了页标题整串「{t['h1']}」——"
                        f"页标题只许由脚本从 {pid}.md 提取")
            break

    # 诚实三行只能借城市骨架，不能把房子版文案抄回来。
    for h in parsed_honest:
        if "房子" in h["lead"] or "盖房子" in h["detail"]:
            errs.append(f"诚实行还留着房子版文案：{h['lead']!r}")

    if errs:
        print("✗ OVERVIEW.md 自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"  ✓ OVERVIEW.md：{len(lines)} 行（≤100）、首行城市版 H1、指向本图 + city/city-map.html、"
          "10 行与 city/data.json 逐字同步、四阶段 4 行与 city/stages-city.json 逐字同步"
          "（阶段名 / 一句话 / 横切系统）、诚实 3 行、未手写页标题整串")
    return dict(h1=H1_WANT, rows=parsed_rows, stages=parsed_stages, honest=parsed_honest)


# ------------------------------------------------------------------ 简单 SVG 图标（viewBox 0 0 40 40，全部线条 + 橙色强调）

def icon_site() -> str:
    """P0 市政配套 · 场地平整：地平线 + 场地折线 + 标桩 + 橙色开工旗。"""
    return (
        '<path d="M3.5 32.5 H36.5"/>'
        '<path d="M8 32.5 V20 H20"/>'
        '<path class="acc" d="M11 32.5 v-4 M17 32.5 v-6 M23 32.5 v-3"/>'
        '<path d="M28 32.5 V9.5"/>'
        '<path class="accf" d="M28 10.5 l8 3 -8 3 Z"/>'
    )


def icon_warehouse() -> str:
    """P1 数据仓库大楼：仓库屋顶 + 楼身 + 货窗 + 门。"""
    return (
        '<path d="M11 32.5 V12 h18 v20.5"/>'
        '<path class="acc" d="M8 12 L20 4.5 L32 12"/>'
        '<path d="M14.5 16.5 h4 v3 h-4 Z M21.5 16.5 h4 v3 h-4 Z"/>'
        '<path d="M14.5 23 h4 v3 h-4 Z M21.5 23 h4 v3 h-4 Z"/>'
        '<path d="M17.5 32.5 v-4.5 h5 v4.5"/>'
        '<path d="M4 32.5 h32"/>'
    )


def icon_shelves() -> str:
    """P2 仓库分区与入库通道：货架三层 + 分区货箱。"""
    return (
        '<path d="M8 9.5 h24 v23 h-24 Z"/>'
        '<path d="M8 18 h24 M8 26.5 h24"/>'
        '<path d="M12 12 h5 v5 h-5 Z M21 12 h5 v5 h-5 Z"/>'
        '<path class="acc" d="M12 20.5 h5 v5 h-5 Z"/>'
        '<path d="M21 20.5 h5 v5 h-5 Z M12 29 h5 v3 h-5 Z M21 29 h5 v3 h-5 Z"/>'
        '<path d="M4 32.5 h4"/>'
    )


def icon_service() -> str:
    """P3 查询服务中心：带屋顶的服务楼 + 门柱 + 橙色服务徽。"""
    return (
        '<path d="M5 32.5 h30"/>'
        '<path d="M9.5 32.5 V16 h21 v16.5"/>'
        '<path class="acc" d="M7 16 L20 8 L33 16"/>'
        '<path d="M14 21 v11.5 M20 21 v11.5 M26 21 v11.5"/>'
        '<circle class="accf" cx="20" cy="12.8" r="1.5"/>'
    )


def icon_window() -> str:
    """P4 对外服务窗口：窗口 + 柜台 + 柜台后的办事员 + 橙色告示牌。"""
    return (
        '<path d="M9 8.5 h22 v16 h-22 Z"/>'
        '<path d="M9 24.5 h22"/>'
        '<circle cx="16.5" cy="15.5" r="2.3"/>'
        '<path d="M12.5 21 q4 -3.4 8 0"/>'
        '<path class="acc" d="M23.5 12 h5 v3.5 h-5 Z"/>'
        '<path d="M5 32.5 h30"/>'
    )


def icon_desk() -> str:
    """P5 前台接待台：柜台 + 台腿 + 橙色对话气泡。"""
    return (
        '<path d="M9 24.5 h22 v5.5 h-22 Z"/>'
        '<path d="M12.5 30 v2.5 M27.5 30 v2.5"/>'
        '<path class="acc" d="M14 9 h12 v7 h-7 l-3 2.8 V16 h-2 Z"/>'
        '<path class="acc" d="M18 12.5 h4"/>'
        '<path d="M5 32.5 h30"/>'
    )


def icon_rules() -> str:
    """P6 办事指南与规则室：办事指南板 + 三条规则 + 橙色判据章。"""
    return (
        '<path d="M12 8 h16 v24 h-16 Z"/>'
        '<path d="M17 6 h6 v4.5 h-6 Z"/>'
        '<path d="M15.5 14.5 h9 M15.5 18 h9 M15.5 21.5 h5.5"/>'
        '<circle class="acc" cx="25" cy="27.5" r="2.8"/>'
    )


def icon_corridor() -> str:
    """P7 取货通道：两侧墙 + 地面导向 + 取货车 + 车轮。"""
    return (
        '<path d="M6 8 v24.5 M34 8 v24.5"/>'
        '<path class="acc" d="M11 30.5 h3.5 M18.5 30.5 h3.5 M26 30.5 h3.5"/>'
        '<path d="M13 16 h9 v8.5 h-9 Z"/>'
        '<path d="M22 18.5 h3.5"/>'
        '<circle cx="15.5" cy="26.3" r="1.7"/>'
        '<circle cx="19.8" cy="26.3" r="1.7"/>'
    )


def icon_belt() -> str:
    """P8 传送带：上下带面 + 两端滚筒 + 货箱 + 橙色输送方向。"""
    return (
        '<path d="M7 23 h26 M7 28.5 h26"/>'
        '<circle cx="7.5" cy="25.8" r="2.6"/>'
        '<circle cx="32.5" cy="25.8" r="2.6"/>'
        '<path d="M11 15 h6 v8 h-6 Z M20 15 h6 v8 h-6 Z"/>'
        '<path class="acc" d="M27.5 9.5 h4.5 M29.8 7.2 L32 9.5 l-2.2 2.3"/>'
    )


def icon_gate() -> str:
    """P9 城市门户 + 道路网：两座门塔 + 拱门 + 橙色道路中线。"""
    return (
        '<path d="M7 32.5 V13 h6 v19.5"/>'
        '<path d="M27 32.5 V13 h6 v19.5"/>'
        '<path d="M13 20.5 q7 -8.5 14 0"/>'
        '<path class="acc" d="M7 9.5 h6 M27 9.5 h6"/>'
        '<path class="acc" d="M20 25 v2.5 M20 30.5 v2"/>'
        '<path d="M3.5 32.5 h33"/>'
    )


ICON_FUNCS = [
    icon_site, icon_warehouse, icon_shelves, icon_service, icon_window,
    icon_desk, icon_rules, icon_corridor, icon_belt, icon_gate,
]

# 四阶段色条：黑白灰逐级变深，橙只做 Lx 强调。
STAGE_FILL = ["#F1ECE1", "#E2D9C8", "#C2B8A4", "#6F6759"]
STAGE_DARK = [False, False, False, True]


# ------------------------------------------------------------------ 组版 HTML

def build_svg(idx: int) -> str:
    return (f'<svg viewBox="0 0 40 40" role="img" aria-hidden="true" '
            f'data-icon="{esc(ICON_IDS[idx])}">{ICON_FUNCS[idx]()}</svg>')


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --paper: #F6F3EC; --panel: #FFFDF8;
  --ink: #26231E; --ink2: #4E4940; --gray: #7A7368; --light: #A9A197;
  --hair: #E3DDD0; --hair2: #D6CFC0;
  --orange: #D9530F; --orange-deep: #B8430A; --orange-soft: #FBE8DC;
}
html, body { background: var(--paper); }
body {
  width: 1600px; height: 1000px; overflow: hidden;
  font-family: "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC", sans-serif;
  color: var(--ink); -webkit-font-smoothing: antialiased;
}
.page { width: 1600px; height: 1000px; padding: 24px 40px 14px;
        display: flex; flex-direction: column; }

/* ---------- 页眉 ---------- */
header { display: flex; justify-content: space-between; align-items: flex-end; gap: 26px; }
.kicker { display: flex; align-items: center; gap: 8px; color: var(--orange);
          font-size: 13px; font-weight: 700; letter-spacing: 2.2px; }
.kicker .dot { width: 9px; height: 9px; background: var(--orange); display: inline-block; }
h1 { font-size: 27px; line-height: 1.18; font-weight: 800; letter-spacing: 0.4px;
     margin-top: 6px; }
.sub { display: flex; align-items: center; gap: 9px; margin-top: 6px;
       font-size: 15px; color: var(--ink2); }
.sub .bar { width: 4px; height: 17px; background: var(--orange); display: inline-block; }
.legend { width: 430px; padding-bottom: 2px; text-align: right; }
.leg-line { display: flex; align-items: center; justify-content: flex-end; gap: 8px;
            font-size: 12px; color: var(--ink2); }
.leg-line .dash { width: 80px; border-top: 1.6px dashed var(--hair2); display: inline-block; }
.leg-line .sample-num { width: 22px; height: 22px; border-radius: 50%; background: var(--orange);
                        color: #FFF9F2; font-size: 11.5px; font-weight: 800;
                        display: inline-flex; align-items: center; justify-content: center; }
.leg-note { margin-top: 6px; font-size: 11px; color: var(--gray); line-height: 1.4; }
.header-rule { margin-top: 10px; height: 3px;
               background: linear-gradient(90deg, var(--orange) 0 96px, var(--ink) 96px 100%); }

/* ---------- 两栏表头 ---------- */
.colheads { display: grid; grid-template-columns: 700px 88px 1fr; align-items: baseline;
            margin-top: 8px; padding: 0 14px; }
.ch { font-size: 13px; color: var(--ink2); display: flex; align-items: baseline; gap: 8px; }
.ch b { font-size: 14px; font-weight: 800; color: var(--ink); }
.ch span { font-size: 11px; color: var(--gray); }
.ch.mid { justify-content: center; font-size: 10.5px; color: var(--light); letter-spacing: 1px; }
.ch.right { justify-content: flex-start; }

/* ---------- 10 行对照 ---------- */
.map { margin-top: 5px; background: var(--panel); border: 1px solid var(--hair2);
       border-radius: 9px; overflow: hidden; }
.row { display: grid; grid-template-columns: 700px 88px 1fr; align-items: center;
       min-height: 55px; padding: 0 14px; }
.row:nth-child(even) { background: #FAF7EF; }
.row + .row { border-top: 1px solid var(--hair); }
.site { display: flex; align-items: center; gap: 12px; min-width: 0; }
.iconbox { flex: none; width: 46px; height: 46px; border-radius: 9px;
           background: #F5F0E5; border: 1px solid #EAE3D4;
           display: flex; align-items: center; justify-content: center; }
.iconbox svg { width: 35px; height: 35px; display: block; }
.iconbox svg path, .iconbox svg circle { fill: none; stroke: var(--ink2);
    stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.iconbox svg .acc { stroke: var(--orange); }
.iconbox svg .accf { fill: var(--orange); stroke: none; }
.stext { min-width: 0; flex: 1; }
.fline { display: flex; align-items: center; gap: 7px; min-width: 0; }
.fno { flex: none; background: var(--orange-soft); color: var(--orange-deep);
       font-size: 10.5px; font-weight: 800; letter-spacing: 0.4px;
       padding: 1.5px 5px; border-radius: 3px; }
.fname { font-size: 15.5px; font-weight: 800; letter-spacing: 0.2px; line-height: 1.25;
         white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kind { flex: none; margin-left: auto; font-size: 9.5px; color: var(--gray);
        border: 1px solid var(--hair2); border-radius: 3px; padding: 0.5px 5px; }
.qline { display: flex; align-items: baseline; gap: 6px; margin-top: 2.5px; font-size: 12.2px;
         line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.prob { color: var(--ink2); flex: none; }
.qarrow { color: var(--orange); font-weight: 800; flex: none; }
.sol { color: var(--gray); min-width: 0; overflow: hidden; text-overflow: ellipsis; }

.conn { position: relative; align-self: stretch; display: flex; align-items: center;
        justify-content: center; }
.conn::before { content: ""; position: absolute; left: 2px; right: 2px; top: 50%;
                border-top: 1.6px dashed #C6BCAA; }
.conn::after { content: "▸"; position: absolute; right: 0; top: 50%;
               transform: translateY(-58%); font-size: 9px; color: #B3A794; }
.num { position: relative; z-index: 1; width: 26px; height: 26px; border-radius: 50%;
       background: var(--orange); color: #FFF9F2; font-size: 12.5px; font-weight: 800;
       display: flex; align-items: center; justify-content: center;
       box-shadow: 0 0 0 3px var(--panel); }

.pagecell { display: flex; align-items: center; gap: 12px; min-width: 0; }
.pagechip { flex: none; min-width: 70px; text-align: center; background: var(--ink);
            color: #F8F4EA; font-size: 11.5px; font-weight: 700; letter-spacing: 0.6px;
            padding: 4px 7px; border-radius: 4px; }
.ptext { min-width: 0; flex: 1; }
.ptitle { font-size: 15.5px; font-weight: 800; line-height: 1.25; letter-spacing: 0.2px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.build { font-size: 12.2px; color: var(--gray); line-height: 1.3; margin-top: 2.5px;
         white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badges { flex: none; display: flex; gap: 3px; }
.badge { width: 19px; height: 19px; border-radius: 50%; background: var(--orange-soft);
         border: 1px solid #F2C4A5; color: var(--orange-deep); font-size: 11.5px;
         font-weight: 800; display: flex; align-items: center; justify-content: center; }

/* ---------- 四阶段成熟度条 ---------- */
.stages { margin-top: 10px; }
.sechead { display: flex; align-items: baseline; justify-content: space-between; }
.sectitle { font-size: 14.5px; font-weight: 800; }
.sectitle .orange { color: var(--orange); }
.secnote { font-size: 10.5px; color: var(--gray); }
.stagebar { margin-top: 6px; display: grid; grid-template-columns: repeat(4, 1fr);
            border: 1px solid var(--hair2); border-radius: 8px; overflow: hidden;
            height: 90px; }
.stage { padding: 8px 13px 7px; display: flex; flex-direction: column; gap: 3px;
         border-left: 1px solid rgba(84, 74, 58, 0.14); overflow: hidden; }
.stage:first-child { border-left: 0; }
.st-top { display: flex; align-items: baseline; gap: 6px; }
.lv { font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; color: var(--orange-deep); }
.nm { font-size: 15px; font-weight: 800; }
.act { font-size: 9.5px; font-weight: 800; color: #FFF9F2; background: var(--orange);
       padding: 0.5px 5px; border-radius: 3px; }
.pages { margin-left: auto; font-size: 10px; color: var(--gray); }
.city { font-size: 10.9px; line-height: 1.3; color: var(--ink2); }
.sw { font-size: 10.3px; line-height: 1.3; color: var(--gray); }
.dark .nm { color: #F8F4EA; }
.dark .lv { color: #FFB183; }
.dark .pages { color: #DED6C7; }
.dark .city { color: #F0E9DC; }
.dark .sw { color: #DED6C7; }

/* ---------- 诚实三行 ---------- */
.honest { margin-top: 10px; }
.honest-lines { margin-top: 6px; border-top: 1px solid var(--hair); }
.honest-line { display: flex; align-items: baseline; gap: 10px; padding: 4px 2px;
               border-bottom: 1px solid var(--hair); line-height: 1.4; }
.hno { flex: none; width: 22px; font-size: 10px; font-weight: 800; color: var(--orange);
       letter-spacing: 0.5px; }
.hlead { flex: none; font-size: 13px; font-weight: 800; }
.hdetail { font-size: 12.3px; color: var(--gray); white-space: nowrap;
           overflow: hidden; text-overflow: ellipsis; }

/* ---------- 页脚 ---------- */
footer { margin-top: auto; border-top: 1px solid var(--hair2); padding-top: 6px;
         display: flex; justify-content: space-between; align-items: baseline;
         font-size: 10px; color: var(--light); letter-spacing: 0.3px; }
footer b { color: var(--gray); font-weight: 700; }
"""

SELFTEST_JS = """
window.addEventListener('load', function () {
  var q = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };
  var txt = function (e) { return e.textContent.trim(); };
  var metrics = {
    rows: q('.row').length,
    numbers: q('.conn .num').map(txt),
    chips: q('.pagechip').map(txt),
    titles: q('.ptitle').map(txt),
    fnos: q('.fno').map(txt),
    fnames: q('.fname').map(txt),
    kinds: q('.kind').map(txt),
    problems: q('.prob').map(txt),
    solutions: q('.sol').map(txt),
    builds: q('.build').map(txt),
    badges: q('.badge').map(txt),
    icons: q('.iconbox svg').length,
    iconIds: q('.iconbox svg').map(function (e) { return e.getAttribute('data-icon'); }),
    stages: q('.stage').length,
    stageLevels: q('.stage .lv').map(txt),
    stageNames: q('.stage .nm').map(txt),
    stageActions: q('.stage .act').map(txt),
    stagePages: q('.stage .pages').map(txt),
    stageCities: q('.stage .city').map(txt),
    stageSofts: q('.stage .sw').map(txt),
    stageClipped: q('.stage').filter(function (e) {
      return e.scrollHeight > e.clientHeight + 1;
    }).length,
    honest: q('.honest-line').length,
    honestLeads: q('.honest-line .hlead').map(txt),
    honestDetails: q('.honest-line .hdetail').map(txt),
    oneLiner: q('.sub').map(function (e) { return e.textContent.trim(); })[0] || '',
    resources: performance.getEntriesByType('resource').length,
    srcAttrs: document.querySelectorAll('[src],[href]').length,
    font: getComputedStyle(document.body).fontFamily,
    docW: document.documentElement.scrollWidth,
    docH: document.documentElement.scrollHeight,
    bodyW: document.body.scrollWidth,
    bodyH: document.body.scrollHeight,
    contentBottom: (function () {
      var f = document.querySelector('footer');
      return f ? Math.round(f.getBoundingClientRect().bottom) : -1;
    })(),
    h1: q('h1').map(txt)[0] || '',
    stageBarHeight: Math.round(document.querySelector('.stagebar').getBoundingClientRect().height),
    mapRowsHeight: Math.round(document.querySelector('.map').getBoundingClientRect().height),
    mapClient: document.querySelector('.map').clientHeight,
    mapScroll: document.querySelector('.map').scrollHeight,
    rowsClipped: (function () {
      var m = document.querySelector('.map');
      var cs = getComputedStyle(m);
      var contentBottom = m.getBoundingClientRect().bottom - parseFloat(cs.borderBottomWidth);
      return q('.row').filter(function (r) {
        return r.getBoundingClientRect().bottom > contentBottom + 0.5;
      }).length;
    })(),
    pageClient: document.querySelector('.page').clientHeight,
    pageScroll: document.querySelector('.page').scrollHeight,
    truncated: q('.fname, .qline, .ptitle, .build, .hdetail').filter(function (e) {
      return e.scrollWidth > e.clientWidth + 1;
    }).map(function (e) { return e.className + ':' + e.textContent.trim().slice(0, 14); })
  };
  document.getElementById('selftest-data').textContent = JSON.stringify(metrics);
});
"""


def build_html(data: dict, titles: dict[str, dict], overview: dict) -> str:
    rows_html: list[str] = []
    for idx, row in enumerate(overview["rows"]):
        t = titles[row["page_id"]]
        badges = "".join(
            f'<span class="badge" data-art="{a}">{CIRCLED[a - 1]}</span>'
            for a in row["artifacts"]
        )
        fac = data["facilities"][idx]
        rows_html.append(
            f'<div class="row" data-fac="{esc(row["no"])}" data-page="{esc(row["page_id"])}">'
            '<div class="site">'
            f'<span class="iconbox">{build_svg(idx)}</span>'
            '<div class="stext">'
            '<div class="fline">'
            f'<span class="fno">{esc(row["no"])}</span>'
            f'<span class="fname">{esc(row["name"])}</span>'
            f'<span class="kind">{esc(fac["kind"])}</span>'
            '</div>'
            '<div class="qline">'
            f'<span class="prob">{esc(row["problem"])}</span>'
            '<span class="qarrow">→</span>'
            f'<span class="sol">{esc(row["solution"])}</span>'
            '</div></div></div>'
            f'<div class="conn"><span class="num">{t["no"]}</span></div>'
            '<div class="pagecell">'
            f'<span class="pagechip">第 {t["no"]} 页</span>'
            '<div class="ptext">'
            f'<div class="ptitle">{esc(t["tail"])}</div>'
            f'<div class="build">{esc(row["soft"])}</div>'
            '</div>'
            f'<div class="badges">{badges}</div>'
            '</div></div>'
        )

    stages_html = []
    for i, s in enumerate(overview["stages"]):
        stages_html.append(
            '<div class="stage' + (" dark" if STAGE_DARK[i] else "") + '" '
            f'style="background:{STAGE_FILL[i]}">'
            '<div class="st-top">'
            f'<span class="lv">{esc(s["level"])}</span>'
            f'<span class="nm">{esc(s["name"])}</span>'
            f'<span class="act">{esc(s["action"])}</span>'
            f'<span class="pages">{esc(s["pages"])}</span>'
            '</div>'
            f'<div class="city">{esc(s["city"])}</div>'
            f'<div class="sw">{esc(s["soft"])}</div>'
            '</div>'
        )

    honest_html = "".join(
        '<div class="honest-line">'
        f'<span class="hno">{esc(h["no"])}</span>'
        f'<span class="hlead">{esc(h["lead"])}</span>'
        f'<span class="hdetail">{esc(h["detail"])}</span>'
        '</div>'
        for h in overview["honest"]
    )

    stages_note = "口径同 city/stages-city.json（D44 造 / 换 / 审 / 守）"
    one_liner = str(data["one_liner"])

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>全书地图 · 城市十设施 ↔ 我们这十页</title>
<style>{CSS}</style></head>
<body><div class="page">
  <header>
    <div class="hleft">
      <div class="kicker"><span class="dot"></span>D45 · 城市隐喻 · 一页图看懂十页</div>
      <h1>{esc(overview["h1"])}</h1>
      <div class="sub"><span class="bar"></span>{esc(one_liner)}</div>
    </div>
    <div class="legend">
      <div class="leg-line"><span class="dash"></span><span class="sample-num">N</span>
        <span>同号虚线：左边 P0–P9 设施，右边第 0–9 页</span></div>
      <div class="leg-note">左列是比喻层（为什么是这个顺序）<br>右列是交付层（做完应该看到什么）</div>
    </div>
  </header>
  <div class="header-rule"></div>
  <div class="colheads">
    <div class="ch"><b>设施</b><span>城市里的场地 / 楼 / 楼内房间 / 流线 · 问题 → 方案</span></div>
    <div class="ch mid">同号 0–9</div>
    <div class="ch right"><b>我们的页面</b><span>页标题运行期取自正文 H1 · 造什么 · 交付物</span></div>
  </div>
  <div class="map">
    {''.join(rows_html)}
  </div>
  <section class="stages">
    <div class="sechead">
      <div class="sectitle">四阶段成熟度 · <span class="orange">同一片城区，一段一段接通管网</span></div>
      <div class="secnote">{esc(stages_note)}</div>
    </div>
    <div class="stagebar">{''.join(stages_html)}</div>
  </section>
  <section class="honest">
    <div class="sechead"><div class="sectitle">诚实三行 · <span class="orange">比方不贴的地方，照实说</span></div>
      <div class="secnote">比喻只借骨架，不借结论</div></div>
    <div class="honest-lines">{honest_html}</div>
  </section>
  <footer>
    <div>数据源 <b>tutorial/city/data.json</b> · 页标题由脚本从 <b>tutorial/page-0X.md</b> 提取 ·
      城市全景 <b>tutorial/city/city-map.html</b></div>
    <div>重跑：<b>{esc(RERUN)}</b> · 零外链 / 系统 Noto Sans CJK</div>
  </footer>
</div>
<script>{SELFTEST_JS}</script>
<script id="selftest-data" type="application/json">{{}}</script>
</body></html>
"""
    return doc


# ------------------------------------------------------------------ 成品 HTML / PNG 与页面自检

def scan_forbidden(text: str, where: str) -> None:
    for bad in FORBIDDEN:
        if bad and bad in text:
            fail(f"{where} 里出现禁用字符串 {bad!r}（不许出现用户名 / 绝对路径 / 口令）")
    if re.search(r"https?://", text):
        fail(f"{where} 里出现外链（不许有 http:// 或 https://）")
    for pat in (r"\bsrc\s*=", r"\bhref\s*=", r"@import", r"url\s*\("):
        if re.search(pat, text, re.I):
            fail(f"{where} 里出现外部资源引用 {pat!r}（必须零外链）")


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


def check_metrics(metrics: dict, data: dict, titles: dict[str, dict], overview: dict) -> None:
    errs: list[str] = []
    want_titles = [titles[pid]["tail"] for pid in PAGE_IDS]
    want_chips = [f"第 {i} 页" for i in range(10)]
    want_badges = [CIRCLED[a - 1] for f in data["facilities"] for a in f["artifacts"]]
    if metrics.get("rows") != 10:
        errs.append(f"页面里 {metrics.get('rows')} 行，应为 10")
    if metrics.get("numbers") != [str(i) for i in range(10)]:
        errs.append(f"同号圆 {metrics.get('numbers')}，应为 0–9")
    if metrics.get("chips") != want_chips:
        errs.append(f"页码徽标 {metrics.get('chips')}，应为 {want_chips}")
    if metrics.get("titles") != want_titles:
        errs.append("页面里的页标题与 page-0X.md 的 H1 不一致（标题必须自动提取）：\n"
                    f"      页面 {metrics.get('titles')}\n      正文 {want_titles}")
    if metrics.get("fnos") != [f["no"] for f in data["facilities"]]:
        errs.append(f"页面设施编号 {metrics.get('fnos')} 与 city/data.json 不一致")
    if metrics.get("fnames") != [f["name"] for f in data["facilities"]]:
        errs.append("页面设施名与 city/data.json 不一致")
    if metrics.get("kinds") != [f["kind"] for f in data["facilities"]]:
        errs.append("页面设施类型与 city/data.json 不一致")
    if metrics.get("problems") != [f["problem"] for f in data["facilities"]]:
        errs.append("页面设施「问题」与 city/data.json 不一致")
    if metrics.get("solutions") != [f["solution"] for f in data["facilities"]]:
        errs.append("页面设施「方案」与 city/data.json 不一致")
    if metrics.get("builds") != [f["soft"] for f in data["facilities"]]:
        errs.append("页面「这一页在软件里造什么」与 city/data.json 不一致")
    if metrics.get("badges") != want_badges:
        errs.append(f"页面交付物徽章 {metrics.get('badges')}，应为 {want_badges}（12 件各一次）")
    if metrics.get("icons") != 10:
        errs.append(f"页面里 {metrics.get('icons')} 个图标，应为 10（每件设施一个）")
    if metrics.get("iconIds") != ICON_IDS:
        errs.append(f"页面图标顺序 {metrics.get('iconIds')} 与设计口径不一致")
    if metrics.get("stages") != 4:
        errs.append(f"页面里 {metrics.get('stages')} 段成熟度条，应为 4")
    if metrics.get("stageLevels") != ["L1", "L2", "L3", "L4"]:
        errs.append(f"页面四阶段 level {metrics.get('stageLevels')}，应为 L1–L4")
    if metrics.get("stageNames") != [s["name"] for s in overview["stages"]]:
        errs.append("页面四阶段名称与 OVERVIEW.md 不一致")
    if metrics.get("stageActions") != [s["action"] for s in overview["stages"]]:
        errs.append("页面四阶段学生动作与 OVERVIEW.md 不一致")
    if metrics.get("stagePages") != [s["pages"] for s in overview["stages"]]:
        errs.append("页面四阶段页段与 OVERVIEW.md 不一致")
    if metrics.get("stageCities") != [s["city"] for s in overview["stages"]]:
        errs.append("页面四阶段「城市里长什么样」与 OVERVIEW.md / city/stages-city.json 不一致")
    if metrics.get("stageSofts") != [s["soft"] for s in overview["stages"]]:
        errs.append("页面四阶段「横切系统」与 OVERVIEW.md / city/stages-city.json 不一致")
    if metrics.get("honest") != 3:
        errs.append(f"页面里 {metrics.get('honest')} 行诚实，应为 3")
    if metrics.get("honestLeads") != [h["lead"] for h in overview["honest"]]:
        errs.append("页面诚实三行与 OVERVIEW.md 不一致")
    if metrics.get("oneLiner") != data["one_liner"]:
        errs.append("页面一句话主旨与 city/data.json 的 one_liner 不一致")
    if metrics.get("h1") != f"{overview['h1']}":
        errs.append(f"H1 与 OVERVIEW.md 首行不一致：{metrics.get('h1')!r}")
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
    if int(metrics.get("stageBarHeight", 0)) != 90:
        errs.append(f"四阶段色条高度 {metrics.get('stageBarHeight')}px，应为 90px")
    if metrics.get("stageClipped"):
        errs.append(f"有 {metrics.get('stageClipped')} 段成熟度文字被裁切（读者会看不全）")
    if not (540 <= int(metrics.get("mapRowsHeight", 0)) <= 600):
        errs.append(f"10 行对照区高度 {metrics.get('mapRowsHeight')}px 不在 540–600px")
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
          "10 个图标 / 12 个交付物徽章 / 4 段成熟度 / 3 行诚实 / 外部请求 0 / "
          "系统 Noto Sans CJK / 不溢出、无裁切")


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
        fail(f"map-city-vs-pages.png 带文本元数据块 {chunks}（不许夹带用户名/路径/口令）")
    text = blob.decode("latin-1", "ignore")
    for bad in FORBIDDEN:
        if len(bad) >= 6 and bad in text:
            fail(f"map-city-vs-pages.png 里出现禁用字符串 {bad!r}")
    if "http://" in text or "https://" in text:
        fail("map-city-vs-pages.png 里出现外链")


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
    w, h = img.size                      # noqa: F841（尺寸已校验，这里只取像素）
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
    left_ink = sum(1 for i, (r, g, b) in enumerate(px) if i % 800 < 340 and lum(r, g, b) < 130)
    right_ink = sum(1 for i, (r, g, b) in enumerate(px) if i % 800 > 420 and lum(r, g, b) < 130)
    colors = len(set(px))
    stats = dict(orange=orange / total * 100, ink=ink / total * 100,
                 light=light / total * 100, colors=colors,
                 left_ink=left_ink / (340 * 500) * 100,
                 right_ink=right_ink / (380 * 500) * 100)
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
    if "OVERVIEW.md" in readme and "images/map-city-vs-pages.png" in readme:
        ok.append("README.md 目录区已接 OVERVIEW.md + 城市版全书地图")
    else:
        warn.append("README.md 目录区还没接 OVERVIEW.md / images/map-city-vs-pages.png")
    if "map-house-vs-pages.png" in readme or "map/data.json" in readme:
        warn.append("README.md 还残留旧工地版引用（map-house-vs-pages.png / map/data.json）")
    explorer = HERE / "build_explorer.py"
    if explorer.exists() and "map/data.json" in explorer.read_text(encoding="utf-8"):
        warn.append("shots/build_explorer.py 仍读 tutorial/map/data.json（交互版换城市视图是另一条任务）")
    if (PAGES_DIR / "map" / "archive-house").is_dir():
        ok.append("旧工地版已归档 tutorial/map/archive-house/")
    for line in ok:
        print(f"  ✓ 接入：{line}")
    for line in warn:
        print(f"  ! 接入：{line}")


# ------------------------------------------------------------------ 主流程

def main() -> int:
    if not Path(CHROME).exists():
        fail(f"找不到 Chrome：{CHROME}")
    print("① 读城市版数据 + 四阶段单源 + 页标题 + OVERVIEW 口径自检")
    data = load_json(DATA_PATH, "city/data.json")
    info = validate_city_data(data)
    stages = load_stages_city(data)                # 四阶段内容只从 stages-city.json 读，脚本不写死
    titles = extract_page_titles()                 # page-0X.md 的 H1 是页标题唯一来源
    overview = parse_overview(data, titles, stages)

    print("② 组版单页 HTML（10 行设施 ↔ 十页 + 10 个 SVG 图标 + 四阶段条 + 诚实三行）")
    page = build_html(data, titles, overview)
    scan_forbidden(page, "成品 HTML")
    scan_forbidden(OVERVIEW_PATH.read_text(encoding="utf-8"), "OVERVIEW.md")
    print("  ✓ 素材：零外链、无 src/href 资源引用、无用户名 / 绝对路径 / 口令")
    if "Noto Sans CJK SC" not in page:
        fail("CSS 没有指定系统中文字体 Noto Sans CJK SC")
    for token in REQUIRED_TOKENS:
        if token not in page:
            fail(f"成品 HTML 里缺少关键真值 {token!r}（图会讲不清）")
    with tempfile.TemporaryDirectory(prefix="map-city-render-") as tmp:
        work = Path(tmp)
        html_path = work / "map-city.html"
        html_path.write_text(page, encoding="utf-8")
        metrics = parse_selftest(dump_dom(html_path, work))
        check_metrics(metrics, data, titles, overview)
        print("③ 无头 Chrome 截图 1600×1000 @2x")
        raw = work / "map-city.raw.png"
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
    print(f"  数据源：tutorial/city/data.json（D45，{len(info['facs'])} 设施 / "
          f"{len(info['titles'])} 页标题 / 12 件交付物）")
    print(f"  四阶段：tutorial/city/stages-city.json（{' / '.join(s['name'] for s in stages)}，"
          "阶段名 / 一句话 / 横切系统与 OVERVIEW.md 同源）")
    print(f"  重跑：{RERUN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
