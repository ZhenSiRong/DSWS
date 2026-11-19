#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_city_map_23.py —— D44/D45「同城改造层叠加」全景图（答辩 / 概览用）。

在仓库根目录一条命令重出图（只写一张 PNG，旧图旧数据一律不动）：

    python3 manual/shots/render_city_map_23.py

读（唯一事实源）：
    `manual/city/data-23.json`
      canvas        1600×1000 CSS（@2x = 3200×2000，与旧图 city-map-l1.png 同尺寸）
      facilities    L1 十件设施（逐字等于 data.json：位置 / 尺寸 / 道路 / 图注内容全部复用）
      retrofits     13 件改造层设施（P10–P22，每件一条 level + page + from，以及 link_path
                    改造接入线；L2 蓝 / L3 橙 / L4 红）
      zones/citizen/roads/notes/granularity/levels/legend  L1 原样 + 新增「改造层」图例
      registry      门户区「改造层登记处」面板（13 条改造关系 + 整图图注）
    只读比对 `manual/city/data.json`：L1 十件设施 / 四区 / 11 条道路必须逐字不变，否则报错。

写：
    `manual/images/city-map-23.png`  1600×1000 CSS @2x → 3200×2000

复用：优先 import `render_city_map.py`（旧图渲染脚本，不改它）——
  * 小工具 / 几何：esc、load_json、png_size、pos_size、flow_bbox、overlap、contains、
    edge_point、orthogonalize、rounded_path、trim_end
  * L1 组版：zone_html、facilities_html、citizen_html、notes_html、road_labels_html、compass_html
  * 成品与自检设施：scan_forbidden、HTML_TEMPLATE 里的 CSS、CHROME_BASE / dump_dom /
    parse_selftest / screenshot（画布同为 1600×1000 @2x）
新增：改造层卡片 / 接入线 SVG / 屋顶图标 / 登记处面板 / 23 件页面内置自检 / 成图自检。

内置自检（任一不过就退出码 1，不写成品）：
  1. 数据：L1 与 data.json 逐字一致；13 件改造层设施 P10–P22 各一次、level 配比 4/4/5、
     from 合法且名字对得上、矩形不越界不互相压、接入线横平竖直且终点落在被改造设施边上。
  2. HTML：零外链 / 零 src·href 资源 / 无用户名 / 绝对路径 / 口令；23 个 `P编号 + 名称`
     一个不少；L1 十件名称原样；改造层三色与图例都在。
  3. 页面内置自检（无头 Chrome --dump-dom 读回）：23 张卡片的实际位置与 data 完全一致、
     无溢出 / 截断、悬停 tooltip 对 L1 写「属于 P3…」、对改造层写「← P6…」。
  4. 成图：3200×2000；PNG 无文本元数据 / 用户名 / 绝对路径 / 口令；23 个卡片区域都有墨、
     三档改造层颜色都真的画出来；装了 tesseract 再 OCR 抽查 23 个 P 编号（软检查）。
"""

from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent                 # manual/shots
REPO = HERE.parents[1]
CITY_DIR = REPO / "manual" / "city"
DATA_PATH = CITY_DIR / "data-23.json"
DATA_L1_PATH = CITY_DIR / "data.json"                  # 只读：证明 L1 原样
IMAGES_DIR = REPO / "manual" / "images"
OUT_PNG = IMAGES_DIR / "city-map-23.png"
RERUN = "python3 manual/shots/render_city_map_23.py"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import render_city_map as city                          # noqa: E402  旧图渲染脚本（只读复用）

DESIGN_W, DESIGN_H = 1600, 1000
SCALE = 2
OUT_W, OUT_H = DESIGN_W * SCALE, DESIGN_H * SCALE       # 3200×2000，与旧图同尺寸
FRAME = dict(city.FRAME)                                # 旧图图框，L1 坐标一套到底
CAPTION = "全市 3 座楼（P1/P3/P9）+ 1 块场地（P0）；P2、P4–P8 是楼内房间/通道/流线，不是独立建筑。"

LEVEL_COLORS = {"L2 换": "#2E6CA4", "L3 审": "#C98116", "L4 守": "#B03A2E"}
LEVEL_PAGES = {"L2 换": ["P10", "P11", "P12", "P13"],
               "L3 审": ["P14", "P15", "P16", "P17"],
               "L4 守": ["P18", "P19", "P20", "P21", "P22"]}
RETRO_NOS = [f"P{i}" for i in range(10, 23)]
L1_NOS = [f"P{i}" for i in range(10)]
ALL_NOS = L1_NOS + RETRO_NOS
REQUIRED_TOP = ("schema", "decision", "status", "purpose", "title", "kicker", "one_liner",
                "image", "rerun", "note", "sources", "canvas", "scale", "granularity",
                "legend", "levels", "zones", "citizen", "facilities", "roads", "notes",
                "caption", "retrofit_legend", "retrofits", "icons", "registry")
FORBIDDEN_TOKENS = ["/home/", "/Users/", "/tmp/", "/root/", "/opt/", "http://", "https://"]

# 13 条改造接入线的颜色按级取
LEVEL_BY_NO = {no: lv for lv, nos in LEVEL_PAGES.items() for no in nos}


# ------------------------------------------------------------------ 小工具（复用旧脚本）

def fail(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    raise SystemExit(1)


esc = city.esc
load_json = city.load_json
png_size = city.png_size
pos_size = city.pos_size
overlap = city.overlap
contains = city.contains
in_canvas = city.in_canvas


def rect_of(item: dict) -> dict:
    return {"x": item["position"]["x"], "y": item["position"]["y"],
            "w": item["size"]["w"], "h": item["size"]["h"]}


def dist_to_rect(pt: tuple[float, float], r: dict) -> float:
    dx = max(r["x"] - pt[0], 0, pt[0] - (r["x"] + r["w"]))
    dy = max(r["y"] - pt[1], 0, pt[1] - (r["y"] + r["h"]))
    return (dx * dx + dy * dy) ** 0.5


def is_orthogonal(points: list[tuple[float, float]]) -> bool:
    return all(abs(a[0] - b[0]) < 0.01 or abs(a[1] - b[1]) < 0.01
               for a, b in zip(points, points[1:]))


# ------------------------------------------------------------------ 数据自检

def validate_data(data: dict, old: dict) -> dict:
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    for key in REQUIRED_TOP:
        need(key in data, f"data-23.json 缺字段 {key}")
    if errs:
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        fail("data-23.json 结构不完整")

    need(data["schema"] == "manual-city-23/1", "schema 应为 manual-city-23/1")
    need(data["decision"] == "D44 + D45", "decision 应为 D44 + D45")
    need(data["canvas"] == {"w": DESIGN_W, "h": DESIGN_H},
         f"canvas 应为 {DESIGN_W}×{DESIGN_H}，实为 {data['canvas']}")
    need(data["scale"] == SCALE, "scale 应为 2")
    need(data["image"] == "images/city-map-23.png", "image 应指向 images/city-map-23.png")
    need(data["rerun"] == RERUN, "rerun 与脚本命令不一致")

    # —— L1 必须逐字原样（旧数据只读比对）——
    need(old.get("schema") == "manual-city/1", "data.json 不是 manual-city/1")
    need(data["facilities"] == old["facilities"],
         "L1 十件设施与 data.json 不逐字一致（位置 / 尺寸 / 名称 / 判据都不许改）")
    need(data["roads"] == old["roads"], "L1 11 条道路与 data.json 不逐字一致")
    need(data["zones"] == old["zones"], "四区与 data.json 不逐字一致")
    need(data["citizen"] == old["citizen"], "市民与 data.json 不逐字一致")
    need(data["granularity"] == old["granularity"], "粒度表与 data.json 不逐字一致")
    need(data["levels"] == old["levels"], "四阶段级配与 data.json 不逐字一致")
    need(data["legend"][:5] == old["legend"], "旧图 5 条图例必须原样保留")
    need(data["caption"] == CAPTION, "整图图注与约定不一致")
    old_notes = {n["id"]: n for n in old["notes"]}
    note_ids = [n["id"] for n in data["notes"]]
    need(note_ids == ["inventory", "portal-route"],
         f"图注应为 inventory / portal-route（结构图注已移入登记处），实为 {note_ids}")
    for n in data["notes"]:
        need(n == old_notes[n["id"]], f"图注 {n['id']} 与 data.json 不一致（L1 原样）")
    need(old_notes["structure"]["lines"][0] == CAPTION, "结构图注内容与 caption 不同源")

    # —— 图例 / 改造层图例 ——
    need(len(data["legend"]) == 6 and data["legend"][-1]["mark"] == "retrofit",
         "legend 应为旧 5 条 + 1 条 retrofit")
    need("L2 蓝" in data["legend"][-1]["short"] and "L3 橙" in data["legend"][-1]["short"]
         and "L4 红" in data["legend"][-1]["short"], "改造层图例要写清 L2 蓝 / L3 橙 / L4 红")
    rl = data["retrofit_legend"]
    need([it["level"] for it in rl["items"]] == ["L2 换", "L3 审", "L4 守"],
         "retrofit_legend 三级顺序应为 L2 / L3 / L4")
    need([it["pages"] for it in rl["items"]] == ["P10–P13", "P14–P17", "P18–P22"],
         "retrofit_legend 页段应为 P10–P13 / P14–P17 / P18–P22")

    # —— L1 编号 / 三类计数（与旧图一致）——
    facs = data["facilities"]
    by_no = {f["no"]: f for f in facs}
    need([f["no"] for f in facs] == L1_NOS, "L1 设施编号应为 P0–P9")
    need(len({f["no"] for f in facs}) == 10, "L1 设施编号重复")
    l1_rects = {f["no"]: pos_size(f) for f in facs}
    for f in facs:
        need(in_canvas(l1_rects[f["no"]]), f"{f['no']} 越出画布")
    for a, b in ((facs[i], facs[j]) for i in range(len(facs)) for j in range(i + 1, len(facs))):
        if b.get("parent") == a["no"] or a.get("parent") == b["no"]:
            continue
        need(not overlap(l1_rects[a["no"]], l1_rects[b["no"]]),
             f"L1 {a['no']} 与 {b['no']} 矩形重叠")
    citizen_rect = pos_size(data["citizen"])
    need(in_canvas(citizen_rect), "市民越出画布")
    for n in data["notes"]:
        need(in_canvas(n["rect"]), f"图注 {n['id']} 越出画布")
        need(not any(overlap(n["rect"], r) for r in l1_rects.values()),
             f"图注 {n['id']} 压住 L1 设施")

    # —— 13 件改造层设施 ——
    retros = data["retrofits"]
    need(len(retros) == 13, f"应为 13 件改造层设施，实为 {len(retros)}")
    need([r["no"] for r in retros] == RETRO_NOS, "改造层编号应为 P10–P22 顺序")
    need({r["no"] for r in retros} == set(RETRO_NOS), "改造层编号重复 / 缺失")
    labels: list[str] = []
    retro_rects: dict[str, dict] = {}
    markers: list[tuple[float, float]] = []
    for r in retros:
        no = r["no"]
        n = int(no[1:])
        need(r["page"] == no, f"{no} 的 page 应为 {no}")
        need(r["page_id"] == f"page-{n:02d}", f"{no} 的 page_id 应含 page-{n:02d}")
        need(r["level"] in LEVEL_COLORS, f"{no} 的 level {r['level']} 不在 L2/L3/L4")
        need(no in LEVEL_PAGES[r["level"]], f"{no} 不属于 {r['level']}（配比 4/4/5）")
        need(LEVEL_BY_NO[no] == r["level"], f"{no} 的级与页段不一致")
        for k in ("name", "kind", "theme", "layer", "soft", "goal", "short", "foot",
                  "criterion", "from", "from_name", "relation", "target_note", "link_note"):
            need(isinstance(r.get(k), str) and r[k].strip(), f"{no} 缺字段 {k}")
        need(r["from"] in by_no, f"{no} 的 from={r['from']} 不是 L1 设施")
        need(r["from_name"] == by_no[r["from"]]["name"],
             f"{no} 的 from_name={r['from_name']} 与 {r['from']} 的名称不一致")
        for a in r.get("also", []):
            need(a in by_no, f"{no} 的 also={a} 不是 L1 设施")
        if r["from"] in ("P6", "P7"):
            need(not (r["from"] in ("P6", "P7") and by_no[r["from"]].get("parent") != "P3"),
                 f"{no} 的 from 楼内归属异常")
        rect = rect_of(r)
        retro_rects[no] = rect
        labels.append(f'{no} {r["name"]}')
        need(in_canvas(rect) and contains(FRAME, rect), f"{no} 的矩形越出图框 / 画布")
        min_h = 22 if r.get("picto") else 30
        need(rect["w"] >= 150 and rect["h"] >= min_h, f"{no} 的卡片太小（字会放不下）")
        # 与 L1 设施：只允许「贴在目标楼体里」的两件（P11/P12 贴在 P3 里，目标是楼内房间）
        hit = [f for f, fr in l1_rects.items() if overlap(rect, fr)]
        if hit:
            allowed = {r["from"]}
            parent = by_no[r["from"]].get("parent")
            if parent:
                allowed.add(parent)
            need(set(hit) <= allowed,
                 f"{no} 压住了 L1 设施 {hit}（只允许贴在自己要改造的设施 / 它的父楼里）")
            for h in hit:
                need(contains(l1_rects[h], rect), f"{no} 贴在 {h} 里但没被 {h} 完全包含")
        need(not overlap(rect, citizen_rect), f"{no} 压住市民")
        for note in data["notes"]:
            need(not overlap(rect, note["rect"]), f"{no} 压住图注 {note['id']}")
        # 接入线：横平竖直、从卡片边缘出发、终点落在被改造设施边上
        path = [tuple(p) for p in r["link_path"]]
        need(len(path) >= 2, f"{no} 的 link_path 至少 2 个点")
        need(is_orthogonal(path), f"{no} 的接入线不是横平竖直：{path}")
        need(in_canvas({"x": min(p[0] for p in path), "y": min(p[1] for p in path),
                        "w": max(p[0] for p in path) - min(p[0] for p in path),
                        "h": max(p[1] for p in path) - min(p[1] for p in path)}),
             f"{no} 的接入线画出画布")
        sx, sy = path[0]
        need(rect["x"] - 1 <= sx <= rect["x"] + rect["w"] + 1
             and rect["y"] - 1 <= sy <= rect["y"] + rect["h"] + 1,
             f"{no} 的接入线起点 {path[0]} 不在卡片边缘")
        tx, ty = tuple(r["target_at"])
        need(path[-1] == (tx, ty), f"{no} 的接入线终点应为 target_at={r['target_at']}")
        gap = dist_to_rect((tx, ty), l1_rects[r["from"]])
        need(gap <= 40, f"{no} 的接入线终点离 {r['from']} 太远（{gap:.0f}px）")
        markers.append((tx, ty))
    for i in range(len(retros)):
        for j in range(i + 1, len(retros)):
            need(not overlap(retro_rects[retros[i]["no"]], retro_rects[retros[j]["no"]]),
                 f"改造层 {retros[i]['no']} 与 {retros[j]['no']} 卡片重叠")
    need(len(markers) == 13, "13 件改造层设施应各有 1 个落点")

    # —— 屋顶 / 仓门图标 ——
    icons = data["icons"]
    need(len(icons) == 5, f"屋顶 / 仓门图标应为 5 个，实为 {len(icons)}")
    icon_at: list[dict] = []
    for ic in icons:
        need(ic["kind"] in ("tower", "camera", "gate"), f"图标 {ic['id']} 的 kind 不合法")
        need(ic["of"] in RETRO_NOS, f"图标 {ic['id']} 的 of={ic['of']} 不是改造层设施")
        need(ic["color"] == LEVEL_COLORS[LEVEL_BY_NO[ic["of"]]],
             f"图标 {ic['id']} 的颜色应与其改造层设施同色")
        rc = dict(ic["at"])
        need(in_canvas(rc), f"图标 {ic['id']} 越出画布")
        icon_at.append(rc)
    for i in range(len(icon_at)):
        for j in range(i + 1, len(icon_at)):
            need(not overlap(icon_at[i], icon_at[j]), f"图标 {icons[i]['id']} 与 {icons[j]['id']} 重叠")

    # —— 登记处面板 ——
    reg = data["registry"]
    rr = reg["rect"]
    need(in_canvas(rr) and contains(FRAME, rr), "登记处面板越出图框")
    need(contains(data["zones"][3]["rect"], rr), "登记处面板应放在门户区里")
    need(not any(overlap(rr, r) for r in l1_rects.values()), "登记处面板压住 L1 设施")
    need(not overlap(rr, citizen_rect), "登记处面板压住市民")
    for note in data["notes"]:
        need(not overlap(rr, note["rect"]), f"登记处面板压住图注 {note['id']}")
    for rect in retro_rects.values():
        need(not overlap(rr, rect), "登记处面板压住改造层卡片")
    need(reg["caption"] == CAPTION, "登记处里的整图图注与约定不一致")
    need(reg["counts"].endswith("23 页（P0–P22）"), "登记处计数要写 23 页")
    need(len(retros) + len(facs) == 23, "L1 10 + 改造层 13 应为 23 件")

    # —— 23 页对齐：L1 P0–P9 + 改造层 P10–P22 ——
    pages = sorted([f["page_id"] for f in facs] + [r["page_id"] for r in retros])
    need(pages == [f"page-{i:02d}" for i in range(23)],
         f"23 页应各出现一次，实为 {pages}")
    need(len(labels) == 13, "改造层标签应有 13 个")

    if errs:
        print("✗ data-23.json 自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"  ✓ L1 原样：10 件设施 / 4 区 / {len(data['roads'])} 条道路 / 市民 / 5 条旧图例 "
          f"与 data.json 逐字一致（旧数据只读比对）")
    print(f"  ✓ 改造层：13 件 P10–P22（L2 4 + L3 4 + L4 5），件件有 from（← 被改造的 L1 设施）"
          f"与横平竖直的接入线；终点全部落在目标 40px 内")
    print(f"  ✓ 版面：改造层卡片互不重叠；P11/P12 贴在父楼 P3 里；登记处面板在门户区，"
          f"不压任何设施 / 图注 / 市民")
    print(f"  ✓ 23 页：P0–P9（L1）+ P10–P22（改造层）各一次，共 {len(facs) + len(retros)} 件")
    return {"l1_rects": l1_rects, "retro_rects": retro_rects, "citizen_rect": citizen_rect,
            "markers": markers, "by_no": by_no}


# ------------------------------------------------------------------ HTML 组版

def legend_html(data: dict) -> str:
    return "".join(
        f'<span class="lg lg-{esc(l["mark"])}" title="{esc(l["text"])}"><i></i>{esc(l["short"])}</span>'
        for l in data["legend"])


def granularity_html(data: dict) -> str:
    return " · ".join(f'<b>{esc(g["city"])}</b> = {esc(g["soft"])}' for g in data["granularity"])


def picto_svg(r: dict) -> str:
    if r.get("picto") != "tower":
        return ""
    return ('<svg class="rpicto" viewBox="0 0 12 14" aria-hidden="true">'
            '<path d="M6 1.5 V13 M2 13 H10 M3.4 5.4 H8.6 M4.2 9.4 H7.8" '
            'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>'
            '<circle cx="6" cy="1.8" r="1.3" fill="currentColor"/></svg>')


def flow_html_23(f: dict) -> str:
    """流线 P8：保留原条带 / 名称 / 交付物徽章，把旧图上的口语「问 → 方」换成正式标注。"""
    r = city.pos_size(f)
    badges = "".join(
        f'<span class="badge" data-art="{a}" title="交付物 {city.CIRCLED[a - 1]}">'
        f'{city.CIRCLED[a - 1]}</span>' for a in f["artifacts"])
    return (
        f'<div class="flow" data-no="{esc(f["no"])}" data-kind="{esc(f["kind"])}" '
        f'data-zone="{esc(f["zone"])}" data-page="{esc(f["page"])}" tabindex="0" role="button" '
        f'aria-label="{esc(f["no"] + " " + f["name"])}" '
        f'style="left:{r["x"]}px;top:{r["y"]}px;width:{r["w"]}px;height:{r["h"]}px">'
        f'{badges}<span class="flow-name">{esc(f["no"] + " " + f["name"])}</span>'
        f'<span class="flow-formal">12 条 progress → 1 条 result</span>'
        f'<span class="flow-chev">›››</span></div>')


def facilities_html_23(data: dict) -> str:
    """L1 十件原样（复用旧脚本的楼 / 场地 / 房间组件），只把 P8 条带换成正式标注。"""
    by_no = {f["no"]: f for f in data["facilities"]}
    out = []
    for no in ["P0", "P1", "P3", "P9", "P2", "P4", "P5", "P6", "P7", "P8"]:
        f = by_no[no]
        if f["kind"] in city.BUILDING_KINDS:
            out.append(city.building_html(f))
        elif f["kind"] == "场地":
            out.append(city.site_html(f))
        elif f["kind"] == "流道":
            out.append(flow_html_23(f))
        else:
            out.append(city.room_html(f))
    return "".join(out)


def retro_card_html(r: dict) -> str:
    rect = rect_of(r)
    lv = r["level_key"]
    foot = f'<div class="rfoot">{esc(r["foot"])}</div>' if rect["h"] >= 64 else ""
    return (
        f'<div class="retro {lv.lower()}" data-no="{esc(r["no"])}" data-level="{esc(r["level"])}" '
        f'aria-label="{esc(r["no"] + " " + r["name"])}" tabindex="0" role="button" '
        f'style="left:{rect["x"]}px;top:{rect["y"]}px;width:{rect["w"]}px;height:{rect["h"]}px">'
        f'<div class="rhead"><span class="rpno">{esc(r["no"])}</span>'
        f'{picto_svg(r)}<span class="rname">{esc(r["name"])}</span>'
        f'<span class="rtag">{esc(r["level"])}</span></div>'
        f'<div class="rtarget">{esc(r["relation"])}</div>{foot}</div>')


def retro_cards_html(data: dict) -> str:
    return "".join(retro_card_html(r) for r in data["retrofits"])


def retro_links_svg(data: dict) -> str:
    defs = ['<defs>']
    for lv, color in LEVEL_COLORS.items():
        mid = lv.split()[0].lower()          # l2 / l3 / l4
        defs.append(
            f'<marker id="arw-{mid}" markerWidth="12" markerHeight="10" refX="7.5" refY="4" '
            f'orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{color}"/></marker>')
    defs.append("</defs>")
    groups: list[str] = []
    for r in data["retrofits"]:
        lv = LEVEL_BY_NO[r["no"]]
        mid = lv.split()[0].lower()
        pts = [tuple(p) for p in r["link_path"]]
        d = city.rounded_path(pts, radius=7.0)
        wide = " wide" if r["no"] in ("P10", "P20") else ""
        groups.append(
            f'<g class="rgroup {mid}" data-link="{esc(r["no"])}" data-from="{esc(r["from"])}">'
            f'<path class="rcase" d="{d}"/>'
            f'<path class="rlink {mid}{wide}" d="{d}" marker-end="url(#arw-{mid})"/></g>')
    return "".join(defs) + "".join(groups)


def retro_markers_svg(data: dict) -> str:
    out: list[str] = []
    for r in data["retrofits"]:
        lv = LEVEL_BY_NO[r["no"]]
        mid = lv.split()[0].lower()
        x, y = r["target_at"]
        out.append(
            f'<g class="rpin {mid}" data-pin="{esc(r["no"])}">'
            f'<rect x="{x - 4.6:.1f}" y="{y - 4.6:.1f}" width="9.2" height="9.2" rx="1.2" '
            f'transform="rotate(45 {x:.1f} {y:.1f})" fill="#FFFDF7" stroke="{LEVEL_COLORS[lv]}" '
            f'stroke-width="1.6"/></g>')
    return "".join(out)


def icon_svg(kind: str, color: str) -> str:
    if kind == "tower":
        return (f'<svg viewBox="0 0 30 27" width="100%" height="100%">'
                f'<path d="M15 4 L7.5 24 M15 4 L22.5 24 M6 24 H24" '
                f'stroke="{color}" stroke-width="2" stroke-linecap="round" fill="none"/>'
                f'<path d="M11.2 14.5 H18.8 M12.8 9.5 H17.2" '
                f'stroke="{color}" stroke-width="1.5" stroke-linecap="round" fill="none"/>'
                f'<circle cx="15" cy="3.6" r="2.2" fill="{color}"/>'
                f'<path d="M8.5 6.5 Q15 0.5 21.5 6.5" stroke="{color}" '
                f'stroke-width="1.3" fill="none" opacity=".85"/></svg>')
    if kind == "camera":
        return (f'<svg viewBox="0 0 22 20" width="100%" height="100%">'
                f'<rect x="1.5" y="5" width="13" height="9" rx="2" fill="{color}"/>'
                f'<path d="M14.5 8 L20 4.5 V15.5 L14.5 12 Z" fill="{color}"/>'
                f'<circle cx="6.5" cy="9.5" r="2" fill="#FFFDF7"/></svg>')
    return (f'<svg viewBox="0 0 24 12" width="100%" height="100%">'
            f'<rect x="1" y="1" width="22" height="10" rx="1.5" fill="{color}" opacity=".2"/>'
            f'<path d="M2 10 L7 2 M8 10 L13 2 M14 10 L19 2" stroke="{color}" '
            f'stroke-width="2.4"/></svg>')


def roof_icons_html(data: dict) -> str:
    out: list[str] = []
    for ic in data["icons"]:
        r = ic["at"]
        out.append(
            f'<div class="roof-icon icon-{esc(ic["kind"])}" data-icon="{esc(ic["id"])}" '
            f'data-of="{esc(ic["of"])}" title="{esc(ic["note"])}" '
            f'style="left:{r["x"]}px;top:{r["y"]}px;width:{r["w"]}px;height:{r["h"]}px">'
            f'{icon_svg(ic["kind"], ic["color"])}</div>')
    return "".join(out)


def registry_html(data: dict) -> str:
    reg = data["registry"]
    rr = reg["rect"]
    rows = "".join(
        f'<div class="rg-row {r["level_key"].lower()}">'
        f'<span class="rg-dot"></span>'
        f'<span class="rg-fac">{esc(r["no"])} {esc(r["name"])}</span>'
        f'<span class="rg-arrow">←</span>'
        f'<span class="rg-from">{esc(r["from"])} {esc(r["from_name"])}</span></div>'
        for r in data["retrofits"])
    legend = "".join(
        f'<div class="rg-lg"><span class="rg-swatch" style="background:{it["color"]}"></span>'
        f'<b>{esc(it["level"])}</b><span class="rg-pages">{esc(it["pages"])}</span>'
        f'<span class="rg-desc">{esc(it["desc"])}</span></div>'
        for it in data["retrofit_legend"]["items"])
    lines = "".join(f'<div class="rg-line">{esc(x)}</div>' for x in reg["lines"])
    return (
        f'<div class="registry" id="registry" style="left:{rr["x"]}px;top:{rr["y"]}px;'
        f'width:{rr["w"]}px;height:{rr["h"]}px">'
        f'<div class="rg-top"><span class="rg-title">{esc(reg["title"])}</span>'
        f'<span class="rg-badge">叠加层</span></div>'
        f'<div class="rg-sub">{esc(reg["subtitle"])}</div>'
        f'<div class="rg-legend">{legend}</div>'
        f'{lines}'
        f'<div class="rg-h">改造关系：改的是哪件 L1 设施</div>'
        f'<div class="rg-rows">{rows}</div>'
        f'<div class="rg-cap">{esc(reg["caption"])}</div>'
        f'<div class="rg-count">{esc(reg["counts"])}</div></div>')


CSS_EXTRA = r"""
/* ================= 改造层（D44 横切系统叠加） ================= */
.hdr-r { width: 752px; }
.legend { gap: 8px; }
.lg { font-size: 7.9px; }
.lg-retrofit i { width: 16px; height: 7px;
  background: linear-gradient(90deg, #2E6CA4 0 5px, #C98116 5px 10px, #B03A2E 10px 15px); }

/* 改造接入线：画在道路上面、设施下面，箭头落在目标设施边上 */
#retro-lines { position: absolute; left: 0; top: 0; width: __W__px; height: __H__px;
  z-index: 4; pointer-events: none; overflow: visible; }
#retro-lines path { fill: none; stroke-linejoin: round; stroke-linecap: round; }
#retro-lines path.rcase { stroke: #FFFDF7; stroke-width: 4.4; opacity: .92; }
#retro-lines path.rlink { stroke-width: 1.8; stroke-dasharray: 6 4; }
#retro-lines path.rlink.wide { stroke-width: 3.0; stroke-dasharray: 9 5; }
#retro-lines path.l2 { stroke: #2E6CA4; }
#retro-lines path.l3 { stroke: #C98116; }
#retro-lines path.l4 { stroke: #B03A2E; }
#retro-markers { position: absolute; left: 0; top: 0; width: __W__px; height: __H__px;
  z-index: 6; pointer-events: none; overflow: visible; }

/* 改造层设施卡片：P编号 + 名称 + 级色 + ← 被改造的 L1 设施 */
.retro { position: absolute; z-index: 6; display: flex; flex-direction: column; gap: 2px;
  padding: 4px 6px 4px 7px; border: 1.2px solid var(--lv); border-left: 4.5px solid var(--lv);
  border-radius: 2px; background: var(--lvbg); cursor: pointer;
  box-shadow: 1.5px 2px 0 rgba(43, 59, 70, .12);
  transition: box-shadow .12s, background .12s; }
.retro:hover { box-shadow: 2.5px 3px 0 rgba(43, 59, 70, .22); background: #FFFDF7; }
.retro.l2 { --lv: #2E6CA4; --lvbg: #ECF3FA; }
.retro.l3 { --lv: #C98116; --lvbg: #FBF1DE; }
.retro.l4 { --lv: #B03A2E; --lvbg: #F8EAE7; }
.rhead { display: flex; align-items: center; gap: 4px; }
.rpno { flex: none; background: var(--lv); color: #fff; font-weight: 800; font-size: 8.4px;
  line-height: 13px; padding: 0 3px; border-radius: 2px; letter-spacing: .3px; }
.rname { flex: none; font-size: 10.2px; font-weight: 800; letter-spacing: .2px; white-space: nowrap; }
.rpicto { flex: none; width: 11px; height: 13px; color: var(--lv); }
.flow-formal { flex: none; font-size: 7.2px; color: #2F4E4A; background: rgba(255, 253, 247, .88);
  border: 1px solid #9FB8B2; border-radius: 2px; padding: 0 4px; line-height: 12px; white-space: nowrap; }
.rtag { margin-left: auto; flex: none; font-size: 6.4px; font-weight: 700; color: #fff;
  background: var(--lv); padding: 0 3px; line-height: 9px; border-radius: 2px; letter-spacing: .5px; }
.rtarget { font-size: 7.7px; color: #3A4A55; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rfoot { font-family: "DejaVu Sans Mono", "Noto Sans CJK SC", monospace; font-size: 6.6px;
  color: #4D6070; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* 屋顶 / 仓门图标：改造层长在旧城的屋顶与门口 */
.roof-icon { position: absolute; z-index: 5; pointer-events: none;
  filter: drop-shadow(0 1px 0 rgba(34, 48, 58, .28)); }
.icon-tower { padding: 0; }
.icon-gate { padding: 1px 0; }

/* 门户区「改造层登记处」：13 条改造关系 + 图例 + 整图图注 */
.registry { position: absolute; z-index: 5; display: flex; flex-direction: column; gap: 2px;
  background: rgba(255, 253, 247, .96); border: 1.3px solid #7E919D;
  border-top: 4px solid #22303A; padding: 7px 9px 7px; border-radius: 2px;
  box-shadow: 2px 3px 0 rgba(43, 59, 70, .14); }
.rg-top { display: flex; align-items: baseline; gap: 6px; }
.rg-title { font-size: 11.2px; font-weight: 800; letter-spacing: .5px; }
.rg-badge { margin-left: auto; font-size: 6.6px; font-weight: 700; color: #fff;
  background: #22303A; padding: 0 4px; line-height: 10px; border-radius: 2px; letter-spacing: .6px; }
.rg-sub { font-size: 7.2px; color: #5B6C78; line-height: 1.2; }
.rg-legend { display: flex; flex-direction: column; gap: 2px; padding: 3px 0 3px;
  border-top: 1px dashed #C9C2B2; border-bottom: 1px dashed #C9C2B2; }
.rg-lg { display: flex; align-items: center; gap: 4px; font-size: 6.9px; color: #3A4A55; }
.rg-lg b { flex: none; font-size: 7.2px; }
.rg-swatch { flex: none; width: 9px; height: 6px; border-radius: 1px; }
.rg-pages { flex: none; font-family: "DejaVu Sans Mono", monospace; color: #5B6C78; }
.rg-desc { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rg-line { font-size: 6.7px; color: #6B5A33; line-height: 1.4; }
.rg-h { margin-top: 2px; font-size: 7.4px; font-weight: 800; color: #3E5563; letter-spacing: .3px; }
.rg-rows { display: flex; flex-direction: column; gap: 1px; }
.rg-row { display: flex; align-items: center; gap: 3px; font-size: 6.9px; line-height: 10px;
  border-bottom: 1px dotted #E2DACA; padding-bottom: .5px; }
.rg-dot { flex: none; width: 5px; height: 5px; border-radius: 50%; background: #999; }
.rg-row.l2 .rg-dot { background: #2E6CA4; }
.rg-row.l3 .rg-dot { background: #C98116; }
.rg-row.l4 .rg-dot { background: #B03A2E; }
.rg-fac { flex: none; font-weight: 700; color: #22303A; }
.rg-arrow { flex: none; color: #A97C3F; font-weight: 800; }
.rg-from { flex: 1; min-width: 0; color: #4D6070; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.rg-cap { margin-top: 2px; font-size: 6.5px; color: #5B6C78; line-height: 1.38; }
.rg-count { margin-top: 1px; font-size: 7.2px; font-weight: 800; color: #22303A; letter-spacing: .2px; }
"""

HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
__CSS__
</style>
</head>
<body>
<div id="page">
  <header id="hdr">
    <div class="hdr-l">
      <div class="kicker">__KICKER__</div>
      <h1>__TITLE__</h1>
      <div class="one-liner">__ONE_LINER__</div>
    </div>
    <div class="hdr-r">
      <div class="plan-note">__PLAN_NOTE__</div>
      <div class="legend">__LEGEND__</div>
    </div>
    <div class="gran-line"><span class="gran-k">粒度（GLOSSARY · D45）</span>__GRANULARITY__</div>
  </header>
  <div id="map">
    <div id="frame"></div>
    <div class="zones">__ZONES__</div>
    <svg id="roads" viewBox="0 0 __W__ __H__" aria-hidden="true">__ROADS__</svg>
    <svg id="retro-lines" viewBox="0 0 __W__ __H__" aria-hidden="true">__RETRO_LINKS__</svg>
    __FACILITIES__
    __CITIZEN__
    __NOTES__
    __ROAD_LABELS__
    <svg id="retro-markers" viewBox="0 0 __W__ __H__" aria-hidden="true">__RETRO_MARKERS__</svg>
    __ROOF_ICONS__
    __RETRO_CARDS__
    __REGISTRY__
    __COMPASS__
    <div id="tooltip" hidden>
      <div class="tt-head"><span class="tt-pno"></span><span class="tt-name"></span><span class="tt-kind"></span></div>
      <div class="tt-row"><b class="tt-k1">软件</b><span class="tt-v1"></span></div>
      <div class="tt-row"><b class="tt-k2">问题</b><span class="tt-v2"></span></div>
      <div class="tt-row"><b class="tt-k3">方案</b><span class="tt-v3"></span></div>
      <div class="tt-row"><b>判据</b><span class="tt-v4"></span></div>
      <div class="tt-row"><b class="tt-k5">归属</b><span class="tt-v5"></span></div>
      <div class="tt-row"><b>位置</b><span class="tt-v6"></span></div>
    </div>
  </div>
  <footer id="ftr">
    <div class="ftr-row ftr-r1"><span>数据源：<b>manual/city/data-23.json</b>（单源）· 一条命令重跑：<b>python3 manual/shots/render_city_map_23.py</b></span><span>旧图：<b>manual/images/city-map-l1.png</b>（L1-only，本图不改它）</span></div>
    <div class="ftr-row ftr-r2"><span>图注：同一片城区、同一套坐标 —— L1 十件设施原样保留，叠加 L2 换 4 / L3 审 4 / L4 守 5，共 23 件 = 23 页（P0–P22）。</span><span>改造关系表在门户区「改造层登记处」</span></div>
    <div class="ftr-row ftr-r3"><span class="hint">虚线 = 改造接入线：从改造层设施指向被改造的 L1 设施（如 <b>P11 契约校准站 ← P6 办事指南与规则室</b>）· 悬停看详情</span><span>答辩 / 概览用：不进程页面、不替代 page-00…page-22 验收</span></div>
  </footer>
</div>
<script type="application/json" id="city-data">__DATA_JSON__</script>
<script id="selftest-data" type="application/json">{}</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById('city-data').textContent);
  var ARTS = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫';
  var map = document.getElementById('map');
  var tip = document.getElementById('tooltip');
  var byNo = {};
  DATA.facilities.forEach(function (f) { byNo[f.no] = f; });
  DATA.retrofits.forEach(function (r) { byNo[r.no] = r; });

  function isRetro(f) { return !!f.level_key; }
  function artsText(f) {
    return (f.artifacts || []).map(function (a) { return ARTS.charAt(a - 1); }).join(' ');
  }
  function fillTip(f) {
    tip.querySelector('.tt-pno').textContent = f.no;
    tip.querySelector('.tt-name').textContent = f.name;
    tip.querySelector('.tt-kind').textContent = isRetro(f) ? f.level : f.kind;
    tip.querySelector('.tt-k1').textContent = isRetro(f) ? '改造' : '软件';
    tip.querySelector('.tt-v1').textContent = f.soft;
    tip.querySelector('.tt-k2').textContent = isRetro(f) ? '目标' : '问题';
    tip.querySelector('.tt-v2').textContent = isRetro(f) ? f.relation : f.problem;
    tip.querySelector('.tt-k3').textContent = isRetro(f) ? '做法' : '方案';
    tip.querySelector('.tt-v3').textContent = isRetro(f) ? f.goal : f.solution;
    tip.querySelector('.tt-v4').textContent = String(f.criterion).replace(/`/g, '');
    tip.querySelector('.tt-k5').textContent = isRetro(f) ? '接入' : '归属';
    if (isRetro(f)) {
      tip.querySelector('.tt-v5').textContent = f.link_note + '（落点：' + f.target_note + '）';
    } else if (f.parent) {
      var p = byNo[f.parent];
      var kindTxt = f.kind === '流道' ? '楼内流线，属于 ' : '楼内房间，属于 ';
      tip.querySelector('.tt-v5').textContent = kindTxt + p.no + ' ' + p.name + '（不是独立建筑）';
    } else if (f.kind === '场地') {
      tip.querySelector('.tt-v5').textContent = '场地（不是楼）';
    } else {
      tip.querySelector('.tt-v5').textContent = '独立建筑（运行单元）';
    }
    tip.querySelector('.tt-v6').textContent = isRetro(f)
      ? f.page + '（' + f.page_id + '）· 改造层设施'
      : f.page + '（' + f.page_id + '）· 交付物 ' + artsText(f);
  }
  function moveTip(ev) {
    if (tip.hidden) return;
    var w = 330, h = tip.offsetHeight || 190, pad = 10;
    var x = ev.clientX + 18, y = ev.clientY + 16;
    if (x + w > __W__ - pad) x = ev.clientX - w - 18;
    if (y + h > __H__ - pad) y = ev.clientY - h - 16;
    tip.style.left = Math.max(pad, x) + 'px';
    tip.style.top = Math.max(pad, y) + 'px';
  }
  Array.prototype.forEach.call(
    document.querySelectorAll('.fac[data-no], .flow[data-no], .retro[data-no]'), function (el) {
    var f = byNo[el.dataset.no];
    if (!f) return;
    el.addEventListener('mouseenter', function (ev) { fillTip(f); tip.hidden = false; moveTip(ev); });
    el.addEventListener('mousemove', moveTip);
    el.addEventListener('mouseleave', function () { tip.hidden = true; });
  });

  /* 页面内置自检：DOM 计数 + 23 件位置 + 悬停 tooltip + 溢出，写回 #selftest-data */
  function collect() {
    var cards = Array.prototype.slice.call(
      document.querySelectorAll('.fac[data-no], .flow[data-no], .retro[data-no]'));
    var rects = cards.map(function (c) {
      var r = c.getBoundingClientRect();
      return { no: c.dataset.no, x: Math.round(r.left), y: Math.round(r.top),
               w: Math.round(r.width), h: Math.round(r.height) };
    });
    var labels = cards.map(function (c) { return c.getAttribute('aria-label') || ''; });
    function overflowOf(sel) {
      return Array.prototype.filter.call(document.querySelectorAll(sel), function (c) {
        return c.scrollHeight > c.clientHeight + 1;
      }).map(function (c) { return c.dataset.no || c.id || c.className; });
    }
    var clipped = Array.prototype.filter.call(
      document.querySelectorAll('.soft, .rname, .rtarget, .rfoot, .rg-fac, .rg-from, .rg-desc'),
      function (s) { return s.scrollWidth > s.clientWidth + 1; })
      .map(function (s) { return s.textContent; });
    function textRect(el) {
      var range = document.createRange();
      range.selectNodeContents(el);
      var rs = Array.prototype.filter.call(range.getClientRects(), function (r) {
        return r.width > 0 && r.height > 0;
      });
      if (!rs.length) { return null; }
      var x0 = Math.min.apply(null, rs.map(function (r) { return r.left; }));
      var y0 = Math.min.apply(null, rs.map(function (r) { return r.top; }));
      var x1 = Math.max.apply(null, rs.map(function (r) { return r.right; }));
      var y1 = Math.max.apply(null, rs.map(function (r) { return r.bottom; }));
      return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
    }
    var zlabels = Array.prototype.map.call(document.querySelectorAll('.zone'), function (z) {
      var lab = textRect(z.querySelector('.zlabel'));
      return lab ? { id: z.dataset.zone, x: lab.x, y: lab.y, w: lab.w, h: lab.h } : null;
    }).filter(Boolean);
    var levelColors = {};
    ['l2', 'l3', 'l4'].forEach(function (lv) {
      var el = document.querySelector('.retro.' + lv);
      levelColors[lv] = el ? getComputedStyle(el).borderLeftColor : '';
    });
    var labelRects = {}, headRects = {};
    cards.forEach(function (c) {
      var el = c.querySelector('.pno') || c.querySelector('.rpno') || c.querySelector('.flow-name');
      if (el) {
        var lr = el.getBoundingClientRect();
        labelRects[c.dataset.no] = { x: lr.left, y: lr.top, w: lr.width, h: lr.height };
      }
      var hd = c.querySelector('.bhead') || c.querySelector('.shead') ||
               c.querySelector('.rhead') || c.querySelector('.flow-name');
      if (hd) {
        var hr = hd.getBoundingClientRect();
        headRects[c.dataset.no] = { x: hr.left, y: hr.top, w: hr.width, h: hr.height };
      }
    });
    var p6 = document.querySelector('[data-no="P6"]');
    p6.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false, clientX: 600, clientY: 470 }));
    var tip6 = tip.textContent;
    p6.dispatchEvent(new MouseEvent('mouseleave'));
    var p11 = document.querySelector('[data-no="P11"]');
    p11.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false, clientX: 600, clientY: 560 }));
    var tip11Shown = !tip.hidden;
    var tip11 = tip.textContent;
    p11.dispatchEvent(new MouseEvent('mouseleave'));
    var reg = document.querySelector('.registry');
    return {
      facilities: cards.map(function (c) { return c.dataset.no; }),
      labels: labels,
      rects: rects,
      labelRects: labelRects,
      headRects: headRects,
      l1: document.querySelectorAll('.fac[data-no]').length,
      flow: document.querySelectorAll('.flow[data-no]').length,
      retro: document.querySelectorAll('.retro[data-no]').length,
      retroLevels: Array.prototype.map.call(document.querySelectorAll('.retro'), function (e) {
        return e.dataset.level;
      }),
      zones: document.querySelectorAll('.zone').length,
      roads: Array.prototype.map.call(document.querySelectorAll('.road-seg'), function (s) { return s.dataset.key; }),
      rlabels: Array.prototype.map.call(document.querySelectorAll('.rlabel'), function (s) { return s.textContent; }),
      notes: document.querySelectorAll('.note').length,
      registry: document.querySelectorAll('.registry').length,
      registryText: reg ? reg.textContent : '',
      links: document.querySelectorAll('#retro-lines .rgroup').length,
      markers: document.querySelectorAll('#retro-markers .rpin').length,
      icons: document.querySelectorAll('.roof-icon').length,
      legend: document.querySelectorAll('#hdr .legend .lg').length,
      tags: Array.prototype.map.call(document.querySelectorAll('.rtag'), function (e) { return e.textContent; }),
      levelColors: levelColors,
      overflow: overflowOf('.fac, .flow, .retro, .registry'),
      clipped: clipped,
      zoneLabels: zlabels,
      tip6: tip6,
      tip11: tip11,
      tip11Shown: tip11Shown,
      tipHidden: tip.hidden,
      resources: performance.getEntriesByType('resource').length,
      srcAttrs: document.querySelectorAll('[src]').length + document.querySelectorAll('link').length,
      font: getComputedStyle(document.body).fontFamily,
      docW: document.documentElement.scrollWidth,
      docH: document.documentElement.scrollHeight,
      bodyW: document.body.scrollWidth,
      bodyH: document.body.scrollHeight,
      h1: document.querySelector('h1').textContent,
      legendText: document.getElementById('hdr').textContent
    };
  }
  document.getElementById('selftest-data').textContent = JSON.stringify(collect());
})();
</script>
</body>
</html>
"""


def build_html(data: dict, info: dict) -> str:
    plan_note = (f"答辩 / 概览用 · 非按比例 · 不变坐标 · L1 10 + 改造层 13 = 23 件 · "
                 f"{OUT_W}×{OUT_H} @2x")
    css = city.HTML_TEMPLATE.split("<style>", 1)[1].split("</style>", 1)[0]
    css = css.replace("__W__", str(DESIGN_W)).replace("__H__", str(DESIGN_H))
    css += CSS_EXTRA.replace("__W__", str(DESIGN_W)).replace("__H__", str(DESIGN_H))
    page = HTML_TEMPLATE
    replacements = {
        "__CSS__": css,
        "__W__": str(DESIGN_W),
        "__H__": str(DESIGN_H),
        "__FX__": str(FRAME["x"]),
        "__FY__": str(FRAME["y"]),
        "__FW__": str(FRAME["w"]),
        "__FH__": str(FRAME["h"]),
        "__TITLE__": esc(data["title"]),
        "__KICKER__": esc(data["kicker"]),
        "__ONE_LINER__": esc(data["one_liner"]),
        "__PLAN_NOTE__": esc(plan_note),
        "__LEGEND__": legend_html(data),
        "__GRANULARITY__": granularity_html(data),
        "__ZONES__": "".join(city.zone_html(z) for z in data["zones"]),
        "__ROADS__": city.roads_svg(data["roads"], info["rects"]),
        "__RETRO_LINKS__": retro_links_svg(data),
        "__FACILITIES__": facilities_html_23(data),
        "__CITIZEN__": city.citizen_html(data["citizen"]),
        "__NOTES__": city.notes_html(data["notes"]),
        "__ROAD_LABELS__": city.road_labels_html(data["roads"]),
        "__RETRO_MARKERS__": retro_markers_svg(data),
        "__ROOF_ICONS__": roof_icons_html(data),
        "__RETRO_CARDS__": retro_cards_html(data),
        "__REGISTRY__": registry_html(data),
        "__COMPASS__": city.compass_html(),
        "__DATA_JSON__": json.dumps(data, ensure_ascii=False,
                                    separators=(",", ":")).replace("</", "<\\/"),
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    if "__" in page.replace("__DATA_JSON__", ""):
        leftovers = sorted(set(re.findall(r"__[A-Z_]+__", page)))
        if leftovers:
            fail(f"HTML 还有没替换的占位符：{leftovers}")
    return page


# ------------------------------------------------------------------ 文本自检

def check_html_static(page: str, data: dict, info: dict) -> None:
    if "Noto Sans CJK SC" not in page:
        fail("CSS 没有指定系统中文字体 Noto Sans CJK SC")
    if city.CAPTION_TEXT not in page or CAPTION not in page:
        fail("HTML 里没有整图图注（全市 3 座楼 + 1 块场地…不是独立建筑）")
    for f in data["facilities"]:
        need = f'aria-label="{esc(f["no"] + " " + f["name"])}"'
        if need not in page:
            fail(f"HTML 里缺少 L1 设施标签 {f['no']} {f['name']}")
    for r in data["retrofits"]:
        need = f'aria-label="{esc(r["no"] + " " + r["name"])}"'
        if need not in page:
            fail(f"HTML 里缺少改造层设施标签 {r['no']} {r['name']}")
    for token in ("L2 蓝", "L3 橙", "L4 红", "#2E6CA4", "#C98116", "#B03A2E"):
        if token not in page:
            fail(f"HTML 缺少改造层视觉分层标记 {token!r}")
    checks = [
        ('class="badge"', 12, "圈号徽章"),
        ('class="zone zone-', 4, "区划"),
        ('class="road-seg"', len(data["roads"]), "L1 道路"),
        ('class="fac bldg', 3, "L1 楼"),
        ('class="fac room', 5, "L1 楼内房间"),
        ('class="fac sitecard"', 1, "L1 场地"),
        ('class="flow"', 1, "L1 流线"),
        ('class="note note-', 2, "图注"),
        ('class="retro ', 13, "改造层卡片"),
        ('class="rlink ', 13, "改造接入线"),
        ('class="rpin ', 13, "接入线落点"),
        ('class="roof-icon ', 5, "屋顶 / 仓门图标"),
        ('class="registry"', 1, "改造层登记处"),
        ('class="rg-row ', 13, "改造关系行"),
    ]
    for needle, want, label in checks:
        got = page.count(needle)
        if got != want:
            fail(f"HTML 里{label} {got} 个，应为 {want}")
    for token in ("P10 真实供水管线", "P11 契约校准站", "P12 执行器车间",
                  "P13 部署调度塔", "P14 抽检站", "P15 生成审计室", "P16 校验门禁",
                  "P17 纠错法庭", "P18 门禁闸机", "P19 策略哨所", "P20 应急通道",
                  "P21 监控塔", "P22 回归演练场"):
        if token not in page:
            fail(f"HTML 里 23 件清单缺 {token}")
    if page.count('style="left:') < 10:
        fail("HTML 里绝对定位元素太少，版面没排出来")
    print("  ✓ HTML 素材：零外链 / 零 src·href 资源 / 无用户名 / 绝对路径 / 口令；"
          "L1 10 件 + 改造层 13 件（P0–P22）一个不少、名称原样；三色分层与登记处都在")


# ------------------------------------------------------------------ 页面内置自检

def check_metrics(metrics: dict, data: dict, info: dict) -> None:
    errs: list[str] = []
    l1 = data["facilities"]
    retros = data["retrofits"]
    want_labels = sorted([f'{f["no"]} {f["name"]}' for f in l1] +
                         [f'{r["no"]} {r["name"]}' for r in retros],
                         key=lambda s: int(s[1:s.index(" ")]))
    got_labels = sorted(metrics.get("labels") or [],
                        key=lambda s: int(s[1:s.index(" ")]) if s and s[1:].split(" ")[0].isdigit() else -1)
    if got_labels != want_labels:
        errs.append(f"页面 23 件标签不对：{got_labels}")
    if sorted(metrics.get("facilities") or [], key=lambda s: int(s[1:])) != \
            [f"P{i}" for i in range(23)]:
        errs.append(f"页面设施编号不对：{metrics.get('facilities')}")
    if metrics.get("l1") != 9 or metrics.get("flow") != 1 or metrics.get("retro") != 13:
        errs.append(f"页面卡片数 L1(不含流线)={metrics.get('l1')}/流线={metrics.get('flow')}"
                    f"/改造层={metrics.get('retro')}，应为 9/1/13")
    if metrics.get("zones") != 4:
        errs.append(f"页面区划 {metrics.get('zones')} 个，应为 4")
    want_roads = [r["key"] for r in data["roads"]]
    if metrics.get("roads") != want_roads:
        errs.append("页面 L1 道路 key 与 data-23.json 不一致")
    if metrics.get("rlabels") != [r["label"] for r in data["roads"]]:
        errs.append("页面 L1 道路标注与 data-23.json 不一致")
    if metrics.get("notes") != 2:
        errs.append(f"页面图注 {metrics.get('notes')} 个，应为 2（结构图注移入登记处）")
    if metrics.get("registry") != 1:
        errs.append("页面没有改造层登记处面板")
    if metrics.get("links") != 13 or metrics.get("markers") != 13:
        errs.append(f"页面接入线 {metrics.get('links')} 条 / 落点 {metrics.get('markers')} 个，应各 13")
    if metrics.get("icons") != len(data["icons"]):
        errs.append(f"页面屋顶图标 {metrics.get('icons')} 个，应为 {len(data['icons'])}")
    if metrics.get("legend") != 6:
        errs.append(f"页面图例 {metrics.get('legend')} 条，应为 6（旧 5 + 改造层 1）")
    if "改造层" not in str(metrics.get("legendText", "")):
        errs.append("页头图例没有「改造层」")
    tags = metrics.get("tags") or []
    if tags.count("L2 换") != 4 or tags.count("L3 审") != 4 or tags.count("L4 守") != 5:
        errs.append(f"页面改造层级标签配比不对：{tags}")
    reg_text = str(metrics.get("registryText", ""))
    if "不是独立建筑" not in reg_text or "改造层登记处" not in reg_text:
        errs.append("登记处面板缺整图图注 / 标题")
    want_colors = {"l2": "rgb(46, 108, 164)", "l3": "rgb(201, 129, 22)", "l4": "rgb(176, 58, 46)"}
    for k, v in want_colors.items():
        if metrics.get("levelColors", {}).get(k) != v:
            errs.append(f"改造层 {k} 的边框色 {metrics.get('levelColors', {}).get(k)}，应为 {v}")
    if metrics.get("overflow"):
        errs.append(f"卡片内容溢出（会被裁掉）：{metrics['overflow']}")
    if metrics.get("clipped"):
        errs.append(f"文字被省略号截断：{metrics['clipped']}")
    # 23 张卡片实际渲染位置 = data 坐标
    want_rects = {}
    for f in l1:
        want_rects[f["no"]] = pos_size(f)
    for r in retros:
        want_rects[r["no"]] = rect_of(r)
    for rect in metrics.get("rects", []):
        want = want_rects.get(rect["no"])
        if want is None:
            errs.append(f"页面多出未登记卡片 {rect['no']}")
            continue
        if any(abs(rect[k] - want[k]) > 1 for k in ("x", "y", "w", "h")):
            errs.append(f"{rect['no']} 渲染位置 {rect} 与 data {want} 不一致")
    # 区标题不能压住第一张卡片
    for zl in metrics.get("zoneLabels") or []:
        zr = {"x": zl["x"], "y": zl["y"], "w": zl["w"], "h": zl["h"]}
        for rect in metrics.get("rects", []):
            if overlap(zr, {"x": rect["x"], "y": rect["y"], "w": rect["w"], "h": rect["h"]}):
                errs.append(f"区 {zl['id']} 的标题压住了 {rect['no']}")
    hit6 = str(metrics.get("tip6", ""))
    hit11 = str(metrics.get("tip11", ""))
    if "属于 P3 查询服务中心" not in hit6 or "第 6 页" not in hit6:
        errs.append(f"悬停 P6 的 tooltip 不对：{hit6[:120]}")
    if not metrics.get("tip11Shown") or "P6 办事指南与规则室" not in hit11 or "校准站" not in hit11:
        errs.append(f"悬停 P11 的 tooltip 不对：{hit11[:120]}")
    if not metrics.get("tipHidden"):
        errs.append("悬停移开后 tooltip 没有收起")
    if metrics.get("resources"):
        errs.append(f"页面发起了 {metrics['resources']} 个外部资源请求（必须 0）")
    if metrics.get("srcAttrs"):
        errs.append(f"页面有 src / link 资源 {metrics['srcAttrs']} 个（必须 0）")
    if "Noto Sans CJK SC" not in str(metrics.get("font", "")):
        errs.append(f"页面字体不是系统 Noto Sans CJK：{metrics.get('font')}")
    for key, limit in (("docW", DESIGN_W), ("bodyW", DESIGN_W),
                       ("docH", DESIGN_H), ("bodyH", DESIGN_H)):
        if int(metrics.get(key, 0)) > limit:
            errs.append(f"页面 {key}={metrics.get(key)} 超出画布 {limit}（会裁切）")
    if metrics.get("h1") != data["title"]:
        errs.append("页面 H1 与 data-23.json 的 title 不一致")
    if errs:
        print("✗ 页面内置自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  ✓ 页面自检：L1 10 件 + 改造层 13 件 = 23 张卡片（P0–P22），"
          f"渲染坐标与 data 逐张一致（±1px）")
    print(f"    接入线 13 条 + 落点 13 个 + 屋顶图标 {len(data['icons'])} 个 + 登记处 13 行；"
          f"悬停 P6 显示「属于 P3 查询服务中心」、P11 显示「← P6 办事指南与规则室」；")
    print(f"    无外部请求、无溢出 / 截断、区标题不压卡片、改造层三色与图例就位")


# ------------------------------------------------------------------ 成图自检

PNG_TEXT_CHUNKS = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}


def scan_png_metadata(png: Path) -> None:
    blob = png.read_bytes()
    p, chunks = 8, []
    while p + 8 <= len(blob):
        ln = struct.unpack(">I", blob[p:p + 4])[0]
        typ = blob[p + 4:p + 8]
        if typ in PNG_TEXT_CHUNKS:
            chunks.append(typ.decode("latin-1"))
        p += 12 + ln
    if chunks:
        fail(f"city-map-23.png 带文本元数据块 {chunks}（不许夹带用户名 / 路径 / 口令）")
    text = blob.decode("latin-1", "ignore")
    for bad in city.FORBIDDEN:
        if len(bad) >= 6 and bad in text:
            fail(f"city-map-23.png 里出现禁用字符串 {bad!r}")
    if "http://" in text or "https://" in text:
        fail("city-map-23.png 里出现外链")


def _hex_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def check_png(png: Path, data: dict, info: dict) -> None:
    size = png_size(png)
    if size != (OUT_W, OUT_H):
        fail(f"成图尺寸 {size} ≠ {OUT_W}×{OUT_H}（应与旧图 city-map-l1.png 同尺寸 3200×2000）")
    if png.stat().st_size < 250_000:
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
        return r > 150 and 55 <= g <= 140 and b < 100

    def lum(r: int, g: int, b: int) -> float:
        return 0.299 * r + 0.587 * g + 0.114 * b

    total = len(px)
    orange = sum(1 for r, g, b in px if is_orange(r, g, b)) / total * 100
    ink = sum(1 for r, g, b in px if lum(r, g, b) < 110) / total * 100
    mid = sum(1 for r, g, b in px if lum(r, g, b) < 175) / total * 100
    light = sum(1 for r, g, b in px if lum(r, g, b) > 225) / total * 100
    colors = len(set(px))
    if not (0.3 <= orange <= 7.0):
        fail(f"橙色强调占比 {orange:.2f}% 不在 0.3%–7%")
    if not (0.8 <= ink <= 25.0):
        fail(f"墨色（深字 / 道路）占比 {ink:.2f}% 不在 0.8%–25%")
    if not (3.0 <= mid <= 45.0):
        fail(f"中调（文字 / 描边）占比 {mid:.2f}% 不在 3%–45%")
    if not (40.0 <= light <= 95.0):
        fail(f"纸色占比 {light:.2f}% 不在 40%–95%")
    if colors < 300:
        fail(f"成图只有 {colors} 种颜色，像没渲染出来")

    # 四个区各裁一块，确认都有墨
    stats = {}
    for z in data["zones"]:
        r = z["rect"]
        box = (r["x"] * SCALE + 10, r["y"] * SCALE + 30,
               (r["x"] + r["w"]) * SCALE - 10, (r["y"] + r["h"]) * SCALE - 10)
        crop = img.crop(box).resize((220, 160))
        vals = list(crop.getdata())
        dark = sum(1 for rr, gg, bb in vals if lum(rr, gg, bb) < 200) / len(vals) * 100
        stats[z["name"]] = dark
        if dark < 3.5:
            fail(f"成图里「{z['name']}」几乎是空的（有内容像素 {dark:.2f}%），版面没排上")

    # 13 件改造层卡片：逐块确认有墨 + 有本级颜色
    retro_stats = []
    for r in data["retrofits"]:
        rect = rect_of(r)
        box = (rect["x"] * SCALE + 2, rect["y"] * SCALE + 2,
               (rect["x"] + rect["w"]) * SCALE - 2, (rect["y"] + rect["h"]) * SCALE - 2)
        crop = img.crop(box)
        vals = list(crop.getdata())
        dark = sum(1 for rr, gg, bb in vals if lum(rr, gg, bb) < 200) / len(vals) * 100
        cr, cg, cb = _hex_rgb(LEVEL_COLORS[r["level"]])
        near = sum(1 for rr, gg, bb in vals
                   if (rr - cr) ** 2 + (gg - cg) ** 2 + (bb - cb) ** 2 < 55 ** 2) / len(vals) * 100
        retro_stats.append((r["no"], dark, near))
        if dark < 3.0:
            fail(f"成图里改造层 {r['no']} 卡片几乎是空的（内容像素 {dark:.2f}%）")
        if near < 0.8:
            fail(f"成图里改造层 {r['no']} 没有画出 {r['level']} 的颜色（{near:.2f}%）")

    # 23 张卡片逐块确认有墨（L1 十件 + 改造层十三件）
    all_rects = {f["no"]: pos_size(f) for f in data["facilities"]}
    all_rects.update({r["no"]: rect_of(r) for r in data["retrofits"]})
    empty_cards = []
    for no, rc in all_rects.items():
        box = (rc["x"] * SCALE + 2, rc["y"] * SCALE + 2,
               (rc["x"] + rc["w"]) * SCALE - 2, (rc["y"] + rc["h"]) * SCALE - 2)
        vals = list(img.crop(box).getdata())
        dark = sum(1 for rr, gg, bb in vals if lum(rr, gg, bb) < 200) / len(vals) * 100
        if dark < 2.0:
            empty_cards.append((no, round(dark, 2)))
    if empty_cards:
        fail(f"成图里这些卡片没画出来：{empty_cards}")

    # 登记处面板有墨
    reg = data["registry"]["rect"]
    vals = list(img.crop((reg["x"] * SCALE + 4, reg["y"] * SCALE + 4,
                          (reg["x"] + reg["w"]) * SCALE - 4,
                          (reg["y"] + reg["h"]) * SCALE - 4)).getdata())
    reg_dark = sum(1 for rr, gg, bb in vals if lum(rr, gg, bb) < 200) / len(vals) * 100
    if reg_dark < 4.0:
        fail(f"成图里改造层登记处几乎是空的（{reg_dark:.2f}%）")

    # 三档改造层颜色在整图上都要有量
    color_hits = {}
    for lv, hexv in LEVEL_COLORS.items():
        cr, cg, cb = _hex_rgb(hexv)
        n = sum(1 for rr, gg, bb in px if (rr - cr) ** 2 + (gg - cg) ** 2 + (bb - cb) ** 2 < 50 ** 2)
        color_hits[lv] = n
        if n < 60:
            fail(f"整图上 {lv} 的颜色太少（{n} 个采样点），视觉分层没画出来")
    print(f"  ✓ 成图：{size[0]}×{size[1]}（与旧图同尺寸），{png.stat().st_size // 1024} KB；"
          f"橙色 {orange:.2f}% / 墨 {ink:.2f}% / 中调 {mid:.2f}% / 纸 {light:.2f}%，{colors} 种颜色")
    print(f"    四区都有墨（" + " / ".join(f"{k} {v:.1f}%" for k, v in stats.items()) + "）；"
          f"23 张卡片逐块有墨；改造层卡片色块就位（L2 {color_hits['L2 换']} / "
          f"L3 {color_hits['L3 审']} / L4 {color_hits['L4 守']} 采样点）")
    print(f"    13 件改造层卡片内容像素：" +
          " ".join(f"{no} {dark:.1f}%/{near:.1f}%" for no, dark, near in retro_stats))


def ocr_soft_check(png: Path, metrics: dict) -> None:
    """装了 tesseract 时才跑：按 DOM 给的 P 编号小盒子裁图 OCR，核对 23 个 P 编号。
    白字徽章做白字掩膜（多组 psm / 阈值取并集），传送带上的深色小字做深字掩膜兜底；
    中文名称靠 DOM / HTML 关键字自检，OCR 只做软检查，不拦渲染。"""
    import shutil
    if not shutil.which("tesseract"):
        print("  ! OCR：本机没装 tesseract，跳过（DOM 与 HTML 关键字自检已覆盖）")
        return
    try:
        from PIL import Image
    except ImportError:
        print("  ! OCR：没有 Pillow，跳过")
        return
    img = Image.open(png).convert("RGB")
    label_rects = metrics.get("labelRects") or {}
    if len(label_rects) != 23:
        print(f"  ! OCR：DOM 只给出 {len(label_rects)} 个 P 编号盒子，跳过")
        return

    def crop_of(rc: dict, pad: int):
        return img.crop((max(0, int(rc["x"] * SCALE) - pad),
                         max(0, int(rc["y"] * SCALE) - pad),
                         int((rc["x"] + rc["w"]) * SCALE) + pad,
                         int((rc["y"] + rc["h"]) * SCALE) + pad))

    def masked(crop, white: bool, thr: int):
        w, h = crop.size
        px = crop.load()
        g = Image.new("L", (w, h))
        gp = g.load()
        for y in range(h):
            for x in range(w):
                r, gg, b = px[x, y]
                if white:
                    gp[x, y] = 0 if (r > thr and gg > thr and b > thr) else 255
                else:
                    lum = 0.299 * r + 0.587 * gg + 0.114 * b
                    gp[x, y] = 0 if lum < thr else 255
        return g.resize((w * 6, h * 6), Image.LANCZOS)

    def read(g, psm: int) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            g.save(tmp.name)
            proc = subprocess.run(
                ["tesseract", tmp.name, "stdout", "-l", "eng", "--psm", str(psm),
                 "-c", "tessedit_char_whitelist=P0123456789"],
                capture_output=True, text=True, timeout=60)
            return re.sub(r"\s+", "", proc.stdout)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    hits, misses = [], []
    try:
        for no in ALL_NOS:
            rc = label_rects[no]
            text = ""
            for psm in (7, 8):                       # 白字徽章：多组阈值取并集
                for white in (190, 170, 210):
                    text = read(masked(crop_of(rc, 0), True, white), psm)
                    if no in text:
                        break
                if no in text:
                    break
            if no not in text:                       # 深色小字（传送带上的 P8）：深字掩膜兜底
                for psm in (8, 13):
                    text = read(masked(crop_of(rc, 2), False, 90), psm)
                    if no in text:
                        break
            (hits if no in text else misses).append(no)
    except (OSError, subprocess.TimeoutExpired):
        print("  ! OCR：tesseract 跑不起来，跳过")
        return
    if not misses:
        print(f"  ✓ OCR 抽查（eng + 掩膜）：DOM 定位的 23 个 P 编号盒子全部认出（{len(hits)}/23）")
    else:
        print(f"  ! OCR 抽查（eng + 掩膜）：23 个 P 编号认出 {len(hits)} 个，没认出 {misses}"
              f"（P 编号 23/23 由 DOM / HTML 关键字自检硬校验）")


# ------------------------------------------------------------------ 主流程

def main() -> int:
    if not Path(city.CHROME).exists():
        fail(f"找不到 Chrome：{city.CHROME}")
    print("① 读 data-23.json + 结构 / 几何 / 「L1 原样」自检")
    data = load_json(DATA_PATH, "data-23.json")
    old = load_json(DATA_L1_PATH, "data.json（旧数据只读）")
    info = validate_data(data, old)
    scan_data_text = DATA_PATH.read_text(encoding="utf-8")
    for tok in FORBIDDEN_TOKENS:
        if tok in scan_data_text:
            fail(f"data-23.json 里出现禁用字符串 {tok!r}")
    city.scan_forbidden(scan_data_text, "data-23.json")
    print("  ✓ 数据文本：无外链 / 用户名 / 绝对路径 / 口令")

    print("② 组版 HTML：四区 + L1 十件（原样）+ 改造层 13 件 + 13 条接入线 + 登记处")
    info["rects"] = {**info["l1_rects"], "citizen": info["citizen_rect"]}
    page = build_html(data, info)
    city.scan_forbidden(page, "成品 HTML")
    check_html_static(page, data, info)
    if "--html-out" in sys.argv:
        out_html = Path(sys.argv[sys.argv.index("--html-out") + 1])
        out_html.write_text(page, encoding="utf-8")
        print(f"  ! 调试：HTML 另存 {out_html}")

    with tempfile.TemporaryDirectory(prefix="city-map-23-") as tmp:
        work = Path(tmp)
        html_path = work / "city-map-23.html"
        html_path.write_text(page, encoding="utf-8")
        print("③ 无头 Chrome 读回页面内置自检（23 张卡片位置 + 悬停 tooltip + 溢出）")
        metrics = city.parse_selftest(city.dump_dom(html_path, work))
        check_metrics(metrics, data, info)
        print("④ 无头 Chrome 截图 1600×1000 @2x → 3200×2000")
        raw = work / "city-map-23.raw.png"
        city.screenshot(html_path, raw, work)
        png_bytes = raw.read_bytes()

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PNG.write_bytes(png_bytes)
    print("⑤ 成图自检")
    check_png(OUT_PNG, data, info)
    ocr_soft_check(OUT_PNG, metrics)

    print("\n✓ 完成：")
    print(f"  {OUT_PNG.relative_to(REPO)}  {OUT_W}×{OUT_H}  {OUT_PNG.stat().st_size // 1024} KB")
    print("  23 件设施：L1 P0–P9（原样）+ L2 换 P10–P13 / L3 审 P14–P17 / L4 守 P18–P22")
    print(f"  重跑：{RERUN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
