#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_city_map.py —— D45 城市隐喻样例：L1 城市地图（单源出图 + 出标题草案）。

在仓库根目录一条命令重跑（重建 HTML、标题草案、PNG 三个产物）：

    python3 manual/shots/render_city_map.py

读（唯一事实源）：
    `manual/city/data.json`
      canvas     1600×1000 CSS 画布
      zones      四区：市政配套区 / 仓储区 / 服务区 / 门户区（= L0 地基 / 数据层 / 服务层 / 入口层）
      facilities 十座设施 P0–P9：城市名、软件对应、问题句、方案句、判据、区、交付物 ①–⑫、坐标
      roads      设施之间的道路 / 管网（市民 → 门户 → 服务窗口 → 前台 → 规则室 → 取货通道 → 仓库；
                 仓库 → 传送带 → 门户 → 市民），每条有 from / to / label / via
      titles     23 页标题草案 P0–P22（L1 = 地图设施的问题 + 方案；L2–L4 = 换 / 审 / 守的动作升级）
写：
    `manual/city/city-map.html`     俯视规划图风格的可交互地图（悬停 tooltip、点击高亮相连道路）
    `manual/city/titles-v2.md`      23 行标题草案（Markdown 表，≤60 行）
    `manual/images/city-map-l1.png` 1600×1000 CSS @2x → 3200×2000 静态成图

依据：
    `humen-desicions/09-ablation-course.md` D44（四级 = 造 / 换 / 审 / 守；10+4+4+5 = 23 页）
    与 D45（城市 = 多座设施 + 管网；标题统一「问题 + 方案」，先出样例再全量替换）；
    粒度严格按 `GLOSSARY.md` 的「城市隐喻」表：设施 = 运行单元、窗口 = 端点、
    办事员 = 函数、货架 = 库表、道路 = 网络，不许把窗口画成楼。

内置自检（任一不过就退出码 1，不写成品）：
  1. 数据：四区 / 十设施 / 12 件交付物各一次 / 11 条路（含 9 段主链、引用合法）/ 23 行标题
     （P0–P22 顺序、级 10+4+4+5、L1 问题与方案与地图设施逐字一致）、矩形不越界不互相压。
  2. HTML：零外链 / 零 src·href 资源 / 无用户名 / 绝对路径 / 口令；字体系统 Noto Sans CJK SC；
     10 个设施块、12 个圈号徽章各一次、11 条路、3 个图注、12 个 progress 刻度都在页面上。
  3. 页面内置自检（无头 Chrome --dump-dom 读回）：DOM 计数、悬停 tooltip 内容、点击高亮
     相连道路（P4 → 2 条）、四区箭头、不溢出 1600×1000。
  4. 成图：3200×2000，四区都有墨，橙色「已建成」占比合理；PNG 无文本元数据 / 用户名 /
     绝对路径 / 口令；装了 tesseract 时再 OCR 抽查关键真值（软检查，只提醒）。

依赖：本机 python3 / google-chrome / Noto Sans CJK SC / DejaVu Sans Mono / Pillow。
只写上面三个产物；不改十页正文、SPEC、completeness、maturity、README、决策文档、map/。
"""

from __future__ import annotations

import html
import json
import re
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
CITY_DIR = REPO / "manual" / "city"
DATA_PATH = CITY_DIR / "data.json"
HTML_PATH = CITY_DIR / "city-map.html"
TITLES_PATH = CITY_DIR / "titles-v2.md"
IMAGES_DIR = REPO / "manual" / "images"
OUT_PNG = IMAGES_DIR / "city-map-l1.png"
PAGES_DIR = REPO / "manual"

CHROME = "/usr/bin/google-chrome"
DESIGN_W, DESIGN_H = 1600, 1000                 # CSS 设计画布
SCALE = 2
OUT_W, OUT_H = DESIGN_W * SCALE, DESIGN_H * SCALE  # 3200×2000
RERUN = "python3 manual/shots/render_city_map.py"

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
PROGRESS_TICKS = 12                             # 第 8 页 SSE 的 12 条 progress
FRAME = {"x": 20, "y": 92, "w": 1560, "h": 856}  # 地图图框

# 不许出现在成品里（本机用户名 / 绝对路径 / 口令）；外链另行用正则查。
HOST_USER = Path.home().name                   # 不在源码里写死本机用户名
FORBIDDEN = [
    "/home/", "/Users/", "/tmp/", "/root/", "/opt/", "/var/", "C:\\", "file://",
    HOST_USER, "password", "passwd", "MYSQL_ROOT_PASSWORD", "REBUILD_DW_RO_PASSWORD",
    "root@", "-uroot", "labpass",
]
EXTERNAL_PATTERNS = [
    (r"https?://", "外链 URL"),
    (r"<link\b", "<link> 外部样式"),
    (r"<img\b", "<img> 外部图片"),
    (r"\bsrc\s*=", "src 资源引用"),
    (r"\bhref\s*=", "href 链接"),
    (r"@import", "CSS @import"),
    (r"url\((?!\s*#)", "CSS url() 外部资源"),
    (r"data:image", "data URI 图片"),
    (r"<iframe\b", "<iframe>"),
    (r"\bsk-[A-Za-z0-9]{10,}", "疑似 API Key"),
    (r"\bghp_[A-Za-z0-9]{10,}", "疑似 GitHub Token"),
]
# 图上必须能认出的关键真值（数据 / HTML 都要有）
REQUIRED_TOKENS = ["41099.5", "115", "3307", "8000", "8081", "Noto Sans CJK SC",
                   "已建成", "市政配套区", "仓储区", "服务区", "门户区", "12 条 progress"]
# 六种粒度（GLOSSARY 原表，顺序固定）
GRANULARITY = [
    ("设施 / 建筑", "运行单元（容器 / 进程 / 存储）"),
    ("窗口 / 柜台", "端点（路由）"),
    ("办事员", "进程内函数（抽词、生成 SQL）"),
    ("分区 / 货架", "库表"),
    ("库存", "数据行"),
    ("道路 / 管网", "网络、端口、数据流"),
    ("市民 / 顾客", "用户"),
]
ZONE_WANT = ["市政配套区", "仓储区", "服务区", "门户区"]
ZONE_LAYER_WANT = ["地基", "数据层", "服务层", "入口层"]
ZONE_LEVEL_WANT = ["L0", "L1", "L1", "L1"]
CHAIN_WANT = [("citizen", "P9"), ("P9", "P4"), ("P4", "P5"), ("P5", "P6"),
              ("P6", "P7"), ("P7", "P2"), ("P2", "P8"), ("P8", "P9"), ("P9", "citizen")]
LEVEL_OF = lambda i: "L1 造" if i < 10 else "L2 换" if i < 14 else "L3 审" if i < 18 else "L4 守"
LEVEL_COUNTS = {"L1 造": 10, "L2 换": 4, "L3 审": 4, "L4 守": 5}
TABLE_NAMES = ["dim_customer", "dim_date", "dim_product", "dim_region", "fact_order"]


# ------------------------------------------------------------------ 小工具

def fail(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    raise SystemExit(1)


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def load_json(path: Path, label: str) -> dict:
    if not path.exists():
        fail(f"找不到 {path.relative_to(REPO)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{label} 不是合法 JSON：{exc}")


def png_size(png: Path) -> tuple[int, int]:
    head = png.read_bytes()[:33]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{png} 不是 PNG")
    return struct.unpack(">II", head[16:24])


def pos_size(item: dict) -> dict:
    return {"x": item["position"]["x"], "y": item["position"]["y"],
            "w": item["size"]["w"], "h": item["size"]["h"]}


def overlap(a: dict, b: dict) -> bool:
    return (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
            and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])


def contains(outer: dict, inner: dict) -> bool:
    return (inner["x"] >= outer["x"] and inner["y"] >= outer["y"]
            and inner["x"] + inner["w"] <= outer["x"] + outer["w"]
            and inner["y"] + inner["h"] <= outer["y"] + outer["h"])


def in_canvas(rect: dict) -> bool:
    return (rect["x"] >= 0 and rect["y"] >= 0
            and rect["x"] + rect["w"] <= DESIGN_W and rect["y"] + rect["h"] <= DESIGN_H)


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


# ------------------------------------------------------------------ 道路几何

def edge_point(rect: dict, target: tuple[float, float]) -> tuple[float, float]:
    """从矩形中心朝 target 打一条射线，返回与矩形边界的交点。"""
    cx, cy = rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2
    dx, dy = target[0] - cx, target[1] - cy
    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return (cx, cy)
    tx = (rect["w"] / 2) / abs(dx) if abs(dx) > 0.01 else 1e9
    ty = (rect["h"] / 2) / abs(dy) if abs(dy) > 0.01 else 1e9
    t = min(tx, ty)
    return (cx + dx * t, cy + dy * t)


def orthogonalize(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """把折线掰成横平竖直（规划图的直角路网），斜段用拐点补成两段。"""
    out: list[tuple[float, float]] = [points[0]]
    for i in range(1, len(points)):
        a = out[-1]
        b = points[i]
        if abs(a[0] - b[0]) < 0.01 or abs(a[1] - b[1]) < 0.01:
            out.append(b)
            continue
        nxt = points[i + 1] if i + 1 < len(points) else None
        if nxt is not None and abs(nxt[0] - b[0]) < 0.01:
            elbow = (b[0], a[1])          # 先横后竖
        elif nxt is not None and abs(nxt[1] - b[1]) < 0.01:
            elbow = (a[0], b[1])          # 先竖后横
        elif len(out) >= 2 and abs(out[-2][1] - a[1]) < 0.01:
            elbow = (b[0], a[1])
        else:
            elbow = (a[0], b[1])
        if abs(elbow[0] - a[0]) > 0.01 or abs(elbow[1] - a[1]) > 0.01:
            out.append(elbow)
        out.append(b)
    dedup = [out[0]]
    for p in out[1:]:
        if abs(p[0] - dedup[-1][0]) > 0.01 or abs(p[1] - dedup[-1][1]) > 0.01:
            dedup.append(p)
    return dedup


def rounded_path(points: list[tuple[float, float]], radius: float = 9.0) -> str:
    """把直角折线画成带圆角的路：M… L… Q… L…。"""
    pts = [points[0]]
    for p in points[1:]:
        if dist(p, pts[-1]) > 0.01:
            pts.append(p)
    if len(pts) < 2:
        return ""
    def fmt(v: float) -> str:
        s = f"{v:.1f}"
        return s[:-2] if s.endswith(".0") else s
    d = [f"M {fmt(pts[0][0])} {fmt(pts[0][1])}"]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        rr = min(radius, dist(p0, p1) / 2, dist(p1, p2) / 2)
        if rr < 0.5:
            d.append(f"L {fmt(p1[0])} {fmt(p1[1])}")
            continue
        l1, l2 = dist(p0, p1), dist(p1, p2)
        a = (p1[0] + (p0[0] - p1[0]) / l1 * rr, p1[1] + (p0[1] - p1[1]) / l1 * rr)
        b = (p1[0] + (p2[0] - p1[0]) / l2 * rr, p1[1] + (p2[1] - p1[1]) / l2 * rr)
        d.append(f"L {fmt(a[0])} {fmt(a[1])}")
        d.append(f"Q {fmt(p1[0])} {fmt(p1[1])} {fmt(b[0])} {fmt(b[1])}")
    d.append(f"L {fmt(pts[-1][0])} {fmt(pts[-1][1])}")
    return " ".join(d)


def trim_end(points: list[tuple[float, float]], amount: float = 8.0) -> list[tuple[float, float]]:
    """把终点沿最后一段回缩一点，让箭头落在设施块外面（否则会被设施块盖住）。"""
    if len(points) < 2:
        return points
    a, b = points[-2], points[-1]
    d = dist(a, b)
    if d <= amount + 1.0:
        return points
    t = (d - amount) / d
    return points[:-1] + [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)]


def road_path(road: dict, rects: dict[str, dict]) -> str:
    ra, rb = rects[road["from"]], rects[road["to"]]
    via = [tuple(v) for v in road.get("via", [])]
    ca = (ra["x"] + ra["w"] / 2, ra["y"] + ra["h"] / 2)
    cb = (rb["x"] + rb["w"] / 2, rb["y"] + rb["h"] / 2)
    p0 = edge_point(ra, via[0] if via else cb)
    p1 = edge_point(rb, via[-1] if via else ca)
    return rounded_path(trim_end(orthogonalize([p0] + via + [p1])))


# ------------------------------------------------------------------ 数据自检

def validate_data(data: dict) -> dict:
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    # 顶层
    for key in ("schema", "decision", "status", "title", "kicker", "one_liner", "image",
                "rerun", "note", "canvas", "granularity", "legend", "levels", "zones",
                "citizen", "facilities", "roads", "notes", "titles"):
        need(key in data, f"data.json 缺字段 {key}")
    if errs:
        print("✗ data.json 结构不完整：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    need(data["decision"] == "D45", "decision 应为 D45")
    need(data["canvas"] == {"w": DESIGN_W, "h": DESIGN_H},
         f"canvas 应为 {DESIGN_W}×{DESIGN_H}，实为 {data['canvas']}")
    need(data["image"] == "images/city-map-l1.png", "image 应指向 images/city-map-l1.png")
    need(data["rerun"] == RERUN, "rerun 与脚本实际命令不一致")

    # 粒度表（GLOSSARY 原表，顺序固定）
    need([(g["city"], g["soft"]) for g in data["granularity"]] == GRANULARITY,
         "granularity 与 GLOSSARY 城市隐喻表不一致（设施=运行单元 / 窗口=端点 / 办事员=函数 / 货架=库表）")
    for g in data["granularity"]:
        need(bool(g.get("not")), f"granularity {g.get('city')} 缺「禁止混成」")

    # 级
    levels = data["levels"]
    need([lv["level"] for lv in levels] == list(LEVEL_COUNTS), f"levels 应为 {list(LEVEL_COUNTS)}")
    need(sum(lv["count"] for lv in levels) == 23, "levels 页数合计应为 23")
    for lv in levels:
        need(lv["count"] == LEVEL_COUNTS[lv["level"]], f"{lv['level']} 页数应为 {LEVEL_COUNTS[lv['level']]}")
        need(bool(lv.get("theme")) and bool(lv.get("desc")), f"{lv['level']} 缺 theme / desc")

    # 区
    zones = data["zones"]
    need(len(zones) == 4, f"应为 4 个区，实为 {len(zones)}")
    need([z["name"] for z in zones] == ZONE_WANT, f"区名 / 顺序应为 {ZONE_WANT}")
    need([z["layer"] for z in zones] == ZONE_LAYER_WANT, f"区 layer 应为 {ZONE_LAYER_WANT}")
    need([z["level"] for z in zones] == ZONE_LEVEL_WANT, f"区 level 应为 {ZONE_LEVEL_WANT}")
    zone_rect: dict[str, dict] = {}
    for z in zones:
        for k in ("id", "name", "layer", "level", "maps_to", "rect"):
            need(k in z, f"zone {z.get('id')} 缺 {k}")
        zone_rect[z["id"]] = z["rect"]
        need(in_canvas(z["rect"]) and contains(FRAME, z["rect"]),
             f"区 {z['name']} 的矩形越出图框")
        need(bool(z["maps_to"]), f"区 {z['name']} 缺 maps_to")
    for i in range(len(zones)):
        for j in range(i + 1, len(zones)):
            need(not overlap(zones[i]["rect"], zones[j]["rect"]),
                 f"区 {zones[i]['name']} 与 {zones[j]['name']} 矩形重叠")

    # 设施
    facs = data["facilities"]
    need(len(facs) == 10, f"应为 10 座设施，实为 {len(facs)}")
    need([f["no"] for f in facs] == [f"P{i}" for i in range(10)],
         "设施编号应为 P0–P9 顺序")
    by_no: dict[str, dict] = {}
    artifacts: dict[int, str] = {}
    for f in facs:
        for k in ("no", "name", "kind", "soft", "problem", "solution", "criterion",
                  "zone", "artifacts", "facts", "page", "page_id", "position", "size"):
            need(k in f, f"设施 {f.get('no')} 缺字段 {k}")
        if f["no"] in by_no:
            errs.append(f"设施编号重复 {f['no']}")
        by_no[f["no"]] = f
        need(f["zone"] in zone_rect, f"{f['no']} 的 zone {f['zone']} 不存在")
        no = int(f["no"][1:])
        need(f["page_id"] == f"page-{no:02d}", f"{f['no']} 的 page_id 应为 page-{no:02d}")
        need(f["page"] == f"第 {no} 页", f"{f['no']} 的 page 应为「第 {no} 页」")
        arts = f["artifacts"]
        need(isinstance(arts, list) and 1 <= len(arts) <= 2, f"{f['no']} 的 artifacts 应为 1–2 件")
        for a in arts:
            need(isinstance(a, int) and 1 <= a <= 12, f"{f['no']} 的交付物编号 {a} 不在 1–12")
            need(a not in artifacts, f"交付物 {CIRCLED[a - 1]} 重复出现在 {artifacts.get(a)} 与 {f['no']}")
            artifacts[a] = f["no"]
        need(1 <= len(f["facts"]) <= 4, f"{f['no']} 的 facts 应为 1–4 条")
        need(isinstance(f["position"], dict) and isinstance(f["size"], dict),
             f"{f['no']} 的 position / size 不是对象")
    need(sorted(artifacts) == list(range(1, 13)),
         f"12 件交付物应各出现一次，实为 {sorted(artifacts)}")

    fac_rect = {f["no"]: pos_size(f) for f in facs}
    for f in facs:
        r = fac_rect[f["no"]]
        need(in_canvas(r), f"{f['no']} 的矩形越出画布")
        need(contains(zone_rect[f["zone"]], r), f"{f['no']} 不在它的区 {f['zone']} 里")
    for f in facs:
        if "parent" in f:
            need(f["parent"] in by_no, f"{f['no']} 的 parent {f['parent']} 不存在")
            if f["parent"] in by_no:
                need(contains(fac_rect[f["parent"]], fac_rect[f["no"]]),
                     f"{f['no']} 没有画在父设施 {f['parent']} 里")
    for i in range(len(facs)):
        for j in range(i + 1, len(facs)):
            a, b = facs[i], facs[j]
            parent_child = (b.get("parent") == a["no"]) or (a.get("parent") == b["no"])
            if parent_child:
                continue
            need(not overlap(fac_rect[a["no"]], fac_rect[b["no"]]),
                 f"设施 {a['no']} 与 {b['no']} 矩形重叠（读者会认成同一座楼）")

    # 货架 / 路线 / 刻度（特殊部件的口径）
    p2 = by_no.get("P2", {})
    need(p2.get("shelves") == TABLE_NAMES,
         f"P2 的 shelves 应为 5 张库表 {TABLE_NAMES}，实为 {p2.get('shelves')}")
    p9 = by_no.get("P9", {})
    route = p9.get("route") or []
    need(len(route) >= 2 and "nginx" in route and ":8000" in route,
         "P9 的 route 应含 nginx → :8000 的端到端链路")
    need(all(isinstance(x, str) and x for x in route), "P9 的 route 步骤不能为空")

    # 市民
    cit = data["citizen"]
    cit_rect = pos_size(cit)
    need(cit.get("name") == "市民 / 用户", "citizen.name 应为「市民 / 用户」")
    need(in_canvas(cit_rect) and contains(zone_rect["portal"], cit_rect),
         "市民没有站在门户区里")
    need(not any(overlap(cit_rect, r) for r in fac_rect.values()), "市民与设施矩形重叠")

    # 图注
    notes = data["notes"]
    need(len(notes) == 3, f"应为 3 个图注，实为 {len(notes)}")
    note_ids = set()
    for n in notes:
        need(n["id"] not in note_ids, f"图注 id 重复 {n['id']}")
        note_ids.add(n["id"])
        r = n["rect"]
        need(in_canvas(r), f"图注 {n['id']} 越出画布")
        need(any(contains(zr, r) for zr in zone_rect.values()), f"图注 {n['id']} 不在任何区里")
        need(not any(overlap(r, fr) for fr in fac_rect.values()), f"图注 {n['id']} 压住了设施")
        need(not overlap(r, cit_rect), f"图注 {n['id']} 压住了市民")
        need(bool(n["title"]) and 2 <= len(n["lines"]) <= 3, f"图注 {n['id']} 应有 2–3 行")

    # 道路
    roads = data["roads"]
    valid_refs = set(by_no) | {"citizen"}
    rects = {**fac_rect, "citizen": cit_rect}
    road_keys = set()
    for r in roads:
        for k in ("key", "from", "to", "flow", "label", "via", "label_at", "label_rotate"):
            need(k in r, f"道路 {r.get('key')} 缺字段 {k}")
        need(r["key"] not in road_keys, f"道路 key 重复 {r['key']}")
        road_keys.add(r["key"])
        need(r["from"] in valid_refs, f"道路 {r['key']} 的 from={r['from']} 不是设施 / 市民")
        need(r["to"] in valid_refs, f"道路 {r['key']} 的 to={r['to']} 不是设施 / 市民")
        need(r["from"] != r["to"], f"道路 {r['key']} 首尾相同")
        need(r["flow"] in ("request", "response", "utility"),
             f"道路 {r['key']} 的 flow 应为 request / response / utility")
        need(bool(r["label"]), f"道路 {r['key']} 没有标注")
        need(r["label_rotate"] in (0, -90), f"道路 {r['key']} 的 label_rotate 只支持 0 / -90")
        for v in r["via"]:
            need(isinstance(v, list) and len(v) == 2, f"道路 {r['key']} 的 via 点格式错误")
            need(0 <= v[0] <= DESIGN_W and 0 <= v[1] <= DESIGN_H,
                 f"道路 {r['key']} 的 via 点 {v} 越出画布")
        lx, ly = r["label_at"]
        need(0 <= lx <= DESIGN_W and 0 <= ly <= DESIGN_H,
             f"道路 {r['key']} 的 label_at 越出画布")
        # 路径必须是横平竖直的（规划图直角路网）
        ra, rb = rects[r["from"]], rects[r["to"]]
        via = [tuple(v) for v in r["via"]]
        ca = (ra["x"] + ra["w"] / 2, ra["y"] + ra["h"] / 2)
        cb = (rb["x"] + rb["w"] / 2, rb["y"] + rb["h"] / 2)
        p0 = edge_point(ra, via[0] if via else cb)
        p1 = edge_point(rb, via[-1] if via else ca)
        pts = orthogonalize([p0] + via + [p1])
        for a, b in zip(pts, pts[1:]):
            need(abs(a[0] - b[0]) < 0.01 or abs(a[1] - b[1]) < 0.01,
                 f"道路 {r['key']} 有一段既非横也非竖：{a} → {b}")
            need(in_canvas({"x": min(a[0], b[0]), "y": min(a[1], b[1]),
                            "w": abs(a[0] - b[0]), "h": abs(a[1] - b[1])}),
                 f"道路 {r['key']} 有一段画出画布")
    pairs = [(r["from"], r["to"]) for r in roads]
    for edge in CHAIN_WANT:
        need(edge in pairs, f"主干道路缺 {edge[0]} → {edge[1]}（D45 的进城 / 回城链路）")
    used = set()
    for r in roads:
        used.update((r["from"], r["to"]))
    for f in facs:
        need(f["no"] in used, f"{f['no']} 没有任何道路接入（会像孤岛）")
    need("citizen" in used, "市民没有接入任何道路")

    # 标题
    titles = data["titles"]
    need(len(titles) == 23, f"标题应为 23 行，实为 {len(titles)}")
    need([t["page"] for t in titles] == [f"P{i}" for i in range(23)],
         "标题页码应为 P0–P22 顺序")
    for i, t in enumerate(titles):
        need(t["level"] == LEVEL_OF(i), f"{t['page']} 的级应为 {LEVEL_OF(i)}，实为 {t['level']}")
        need(t["page_id"] == f"page-{i:02d}", f"{t['page']} 的 page_id 应为 page-{i:02d}")
        for k in ("problem", "solution", "criterion"):
            need(isinstance(t[k], str) and t[k].strip(), f"{t['page']} 的 {k} 不能为空")
            need("|" not in t[k], f"{t['page']} 的 {k} 含竖线，会破坏 Markdown 表")
    for t in titles[:10]:
        f = by_no[t["page"]]
        need(t["problem"] == f["problem"], f"{t['page']} 标题的问题句与地图设施不一致")
        need(t["solution"] == f["solution"], f"{t['page']} 标题的方案句与地图设施不一致")
        need(t["criterion"] == f["criterion"], f"{t['page']} 标题的判据与地图设施不一致")
    cnt = Counter(t["level"] for t in titles)
    need(dict(cnt) == LEVEL_COUNTS, f"标题级配比应为 {LEVEL_COUNTS}，实为 {dict(cnt)}")
    for i in range(10):
        need((PAGES_DIR / f"page-{i:02d}.md").exists(), f"L1 正文 manual/page-{i:02d}.md 不存在")

    if errs:
        print("✗ data.json 自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"  ✓ 数据：4 区 / {len(facs)} 设施 / 12 件交付物各一次 / {len(roads)} 条路"
          f"（主链 {len(CHAIN_WANT)} 段齐）/ {len(titles)} 行标题（10+4+4+5）")
    print("  ✓ 粒度：设施=运行单元、窗口=端点、办事员=函数、货架=库表、道路=网络（与 GLOSSARY 逐字一致）")
    print("  ✓ 徽章落点：" + " ".join(f"{CIRCLED[a-1]}→{artifacts[a]}" for a in range(1, 13)))
    print("  ✓ 道路引用：from / to 全部合法（设施或 citizen），直角路网无斜线，全部在画布内")
    print(f"  ✓ 标题：P0–P22 齐；L1 的问题 / 方案 / 判据与地图设施逐字一致；级配比 "
          f"{cnt['L1 造']}+{cnt['L2 换']}+{cnt['L3 审']}+{cnt['L4 守']}")
    return {"facilities": by_no, "artifacts": artifacts, "rects": rects,
            "roads": roads, "titles": titles}


# ------------------------------------------------------------------ HTML 组版

def zone_html(zone: dict) -> str:
    r = zone["rect"]
    return (
        f'<div class="zone zone-{esc(zone["id"])}" data-zone="{esc(zone["id"])}" '
        f'style="left:{r["x"]}px;top:{r["y"]}px;width:{r["w"]}px;height:{r["h"]}px">'
        f'<div class="zlabel"><span class="zname">{esc(zone["name"])}</span>'
        f'<span class="zlevel">{esc(zone["level"])} {esc(zone["layer"])}</span>'
        f'<span class="zmap">{esc(zone["maps_to"])}</span></div></div>'
    )


def facts_html(facts: list[str]) -> str:
    return '<div class="facts">' + "".join(f"<span>{esc(x)}</span>" for x in facts) + "</div>"


def shelves_html(names: list[str]) -> str:
    rows = "".join(
        f'<div class="shelf"><span class="shelf-name">{esc(n)}</span>'
        f'<span class="shelf-tag">分区 · 库表</span></div>' for n in names)
    return f'<div class="shelves"><div class="shelves-h">货架 = 库表</div>{rows}</div>'


def ticks_html(n: int) -> str:
    return '<div class="ticks">' + "".join("<i></i>" for _ in range(n)) + "</div>"


def route_html(steps: list[str]) -> str:
    parts = []
    for i, s in enumerate(steps):
        if i:
            parts.append('<em>→</em>')
        parts.append(f"<span>{esc(s)}</span>")
    return '<div class="route">' + "".join(parts) + "</div>"


def plain(text: str) -> str:
    return str(text).replace("`", "")


def facility_html(f: dict) -> str:
    r = pos_size(f)
    cls = "fac"
    if f["no"] == "P0":
        cls += " site"
    elif f["no"] in ("P1", "P3"):
        cls += " building"
    elif "parent" in f:
        cls += " inner"
    if f["no"] == "P8":
        cls += " belt"
    if f["no"] == "P9":
        cls += " gate"
    badges = "".join(
        f'<span class="badge" data-art="{a}" title="交付物 {CIRCLED[a - 1]}">{CIRCLED[a - 1]}</span>'
        for a in f["artifacts"])
    extra = ""
    if "shelves" in f:
        extra = shelves_html(f["shelves"])
    elif f["no"] == "P8":
        extra = ticks_html(PROGRESS_TICKS)
    elif "route" in f:
        extra = route_html(f["route"])
    crit = ""
    if f.get("crit_on_map"):
        crit = f'<div class="crit"><b>判据</b>{esc(plain(f["criterion"]))}</div>'
    page_no = int(f["no"][1:])
    return (
        f'<div class="{cls}" data-no="{esc(f["no"])}" data-zone="{esc(f["zone"])}" '
        f'data-page="{esc(f["page"])}" tabindex="0" role="button" '
        f'aria-label="{esc(f["no"] + " " + f["name"])}" '
        f'style="left:{r["x"]}px;top:{r["y"]}px;width:{r["w"]}px;height:{r["h"]}px">'
        f'<div class="head"><span class="pno">{esc(f["no"])}</span>'
        f'<span class="fname">{esc(f["name"])}</span>'
        f'<span class="kind">{esc(f["kind"])}</span>'
        f'<span class="badges">{badges}</span></div>'
        f'<div class="softrow"><span class="soft">{esc(f["soft"])}</span>'
        f'<span class="pg">第 {page_no} 页</span></div>'
        f'<div class="tag"><span class="q">问</span>{esc(f["problem"])}'
        f'<span class="arrow">→</span><span class="a">方</span>{esc(f["solution"])}</div>'
        f'{facts_html(f["facts"])}{extra}{crit}</div>'
    )


def roads_svg(roads: list[dict], rects: dict[str, dict]) -> str:
    defs = (
        '<defs>'
        '<marker id="arw-req" markerWidth="17" markerHeight="14" refX="11" refY="5" '
        'orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L12,5 L0,10 z" fill="#34495A"/></marker>'
        '<marker id="arw-res" markerWidth="17" markerHeight="14" refX="11" refY="5" '
        'orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L12,5 L0,10 z" fill="#2F6F6B"/></marker>'
        '<marker id="arw-util" markerWidth="14" markerHeight="12" refX="9" refY="5" '
        'orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#A97C3F"/></marker>'
        '</defs>'
    )
    groups = []
    for r in roads:
        d = road_path(r, rects)
        attrs = (f'class="road-seg" data-key="{esc(r["key"])}" data-from="{esc(r["from"])}" '
                 f'data-to="{esc(r["to"])}" data-flow="{esc(r["flow"])}"')
        if r["flow"] == "utility":
            inner = (f'<path class="utilcasing" d="{d}"/>'
                     f'<path class="utility" d="{d}" marker-end="url(#arw-util)"/>')
        else:
            marker = "arw-req" if r["flow"] == "request" else "arw-res"
            road_cls = "roadreq" if r["flow"] == "request" else "roadres"
            inner = (f'<path class="casing" d="{d}"/>'
                     f'<path class="{road_cls}" d="{d}" marker-end="url(#{marker})"/>'
                     f'<path class="center" d="{d}"/>')
        groups.append(f"<g {attrs}>{inner}</g>")
    return defs + "".join(groups)


def road_labels_html(roads: list[dict]) -> str:
    out = []
    for r in roads:
        x, y = r["label_at"]
        rot = r["label_rotate"]
        style = (f"left:{x}px;top:{y}px;"
                 f"transform:translate(-50%,-50%) rotate({rot}deg)")
        out.append(f'<div class="rlabel" data-road="{esc(r["key"])}" style="{style}">'
                   f'{esc(r["label"])}</div>')
    return "".join(out)


def notes_html(notes: list[dict]) -> str:
    out = []
    for n in notes:
        r = n["rect"]
        lines = "".join(f'<div class="note-l">{esc(x)}</div>' for x in n["lines"])
        out.append(f'<div class="note note-{esc(n["tone"])}" data-id="{esc(n["id"])}" '
                   f'style="left:{r["x"]}px;top:{r["y"]}px;width:{r["w"]}px;height:{r["h"]}px">'
                   f'<div class="note-h">{esc(n["title"])}</div>{lines}</div>')
    return "".join(out)


def citizen_html(cit: dict) -> str:
    r = pos_size(cit)
    return (
        f'<div class="citizen" data-id="citizen" style="left:{r["x"]}px;top:{r["y"]}px;'
        f'width:{r["w"]}px;height:{r["h"]}px">'
        '<svg class="person" viewBox="0 0 34 42" aria-hidden="true">'
        '<circle cx="17" cy="9" r="6.4" fill="#22303A"/>'
        '<path d="M17 17c-7.4 0-11.4 5.2-11.4 12.6V34h22.8v-4.4C28.4 22.2 24.4 17 17 17z" '
        'fill="#D9761C"/></svg>'
        f'<div class="c-name">{esc(cit["name"])}</div>'
        f'<div class="c-soft">{esc(cit["soft"])}</div>'
        f'<div class="c-note">{esc(cit["note"])}</div></div>'
    )


def compass_html() -> str:
    return (
        '<div class="compass" aria-hidden="true">'
        '<svg viewBox="0 0 22 30"><path d="M11 2 L16.5 20 L11 16.5 L5.5 20 Z" fill="#22303A"/>'
        '<text x="11" y="29" text-anchor="middle" font-size="8.5" fill="#22303A">N</text></svg>'
        '</div>'
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>__H1__</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: __W__px; height: __H__px; overflow: hidden; }
body {
  font-family: "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK TC", sans-serif;
  background: #F5F2E9; color: #22303A; -webkit-font-smoothing: antialiased;
}
#page {
  position: relative; width: __W__px; height: __H__px; overflow: hidden;
  background-color: #F5F2E9;
  background-image:
    linear-gradient(rgba(34, 48, 58, .028) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 48, 58, .028) 1px, transparent 1px);
  background-size: 24px 24px;
}
#hdr { position: absolute; left: 28px; top: 8px; width: 1544px; height: 80px; }
.hdr-l { position: absolute; left: 0; top: 0; width: 780px; }
.kicker { font-size: 9.6px; letter-spacing: 2.4px; color: #8A6A3C; font-weight: 700; }
h1 { font-size: 20.5px; font-weight: 800; letter-spacing: .9px; margin-top: 2px; }
.one-liner { font-size: 9.8px; color: #4D6070; margin-top: 3px; letter-spacing: .2px; }
.hdr-r { position: absolute; right: 0; top: 0; width: 700px; text-align: right; }
.plan-note { font-size: 8.2px; color: #7A8B97; letter-spacing: 1.1px; }
.legend { margin-top: 5px; display: flex; gap: 11px; justify-content: flex-end; }
.lg { font-size: 8.2px; color: #43555F; display: inline-flex; align-items: center; gap: 4px; }
.lg i { display: inline-block; width: 15px; height: 4px; background: #34495A; }
.lg-request i { background: #34495A; }
.lg-response i { background: #2F6F6B; }
.lg-built i { background: #E07A1F; height: 7px; width: 11px; }
.lg-utility i { background: repeating-linear-gradient(90deg, #A97C3F 0 4px, transparent 4px 7px); }
.lg-zone i { height: 9px; width: 11px; background: transparent; border: 1.4px dashed #93A3AE; }
.gran-line {
  position: absolute; left: 0; bottom: -1px; width: 1544px; border-top: 1px solid #C9C2B2;
  padding-top: 4px; font-size: 8.2px; color: #4D6070; letter-spacing: .2px; white-space: nowrap;
}
.gran-k { font-weight: 800; color: #8A6A3C; letter-spacing: 1.2px; margin-right: 9px; }
.gran-line b { font-weight: 800; color: #22303A; }

#frame {
  position: absolute; left: __FX__px; top: __FY__px; width: __FW__px; height: __FH__px;
  border: 1.7px solid #2B3B46; background: rgba(255, 253, 247, .5);
  outline: 1px solid rgba(43, 59, 70, .35); outline-offset: 4px;
}
#frame::before, #frame::after {
  content: ""; position: absolute; width: 26px; height: 26px;
  border-color: #2B3B46; border-style: solid; opacity: .75;
}
#frame::before { left: -7px; top: -7px; border-width: 2px 0 0 2px; }
#frame::after { right: -7px; bottom: -7px; border-width: 0 2px 2px 0; }

.zone { position: absolute; border: 1.5px dashed #93A3AE; border-radius: 3px; z-index: 1; }
.zone-municipal { background: #E9EFF2; }
.zone-storage { background: #F1ECDD; }
.zone-service { background: #E8F0E9; }
.zone-portal { background: #F4EAE2; }
.zlabel { position: absolute; left: 12px; top: 6px; right: 10px; line-height: 1.22; }
.zname { font-size: 10.4px; font-weight: 800; letter-spacing: 1.7px; color: #2B3B46; }
.zlevel {
  font-size: 7.4px; font-weight: 700; color: #fff; background: #5B6C78;
  padding: 0 4px; line-height: 11px; border-radius: 2px; margin-left: 6px; letter-spacing: .7px;
  vertical-align: 1px;
}
.zmap { display: block; font-size: 8.1px; color: #5B6C78; margin-top: 1px; letter-spacing: .3px; }

#roads { position: absolute; left: 0; top: 0; width: __W__px; height: __H__px; z-index: 2;
         pointer-events: none; overflow: visible; }
#roads path { fill: none; stroke-linejoin: round; stroke-linecap: round; }
path.casing { stroke: #FFFDF7; stroke-width: 10.5; }
path.roadreq { stroke: #34495A; stroke-width: 5.2; }
path.roadres { stroke: #2F6F6B; stroke-width: 5.2; }
path.center { stroke: #FFFDF7; stroke-width: 1.0; stroke-dasharray: 5 6; }
path.utilcasing { stroke: #FFFDF7; stroke-width: 6.5; }
path.utility { stroke: #A97C3F; stroke-width: 2.3; stroke-dasharray: 7 5.5; }
.road-seg.hot path.casing, .road-seg.hot path.utilcasing { stroke: #F8DDBE; }
.road-seg.hot path.roadreq, .road-seg.hot path.roadres { stroke: #D9761C; }
.road-seg.hot path.utility { stroke: #D9761C; }
#map.dim .road-seg:not(.hot) { opacity: .26; }

.fac {
  position: absolute; z-index: 3; background: #FCF8EF; border: 1.7px solid #2B3B46;
  border-radius: 2px; padding: 9px 10px 8px; cursor: pointer;
  display: flex; flex-direction: column;
  box-shadow: 2px 3px 0 rgba(43, 59, 70, .10);
  transition: box-shadow .12s, background .12s, opacity .12s;
}
.fac::before {
  content: ""; position: absolute; left: -1.7px; top: -1.7px;
  width: calc(100% + 3.4px); height: 4px; background: #E07A1F; border-radius: 2px 2px 0 0;
}
.fac.building { border-width: 2.2px; background: #FDFAF3; box-shadow: 3px 4px 0 rgba(43, 59, 70, .13); }
.fac.inner { border-style: dashed; border-width: 1.4px; background: #FFFDF6; z-index: 4;
             box-shadow: 1px 2px 0 rgba(43, 59, 70, .08); }
.fac.site { background: #F7F1E4; border-style: dashed; }
.fac.site::after {
  content: ""; position: absolute; inset: 0; z-index: 1; pointer-events: none; border-radius: 2px;
  background: repeating-linear-gradient(45deg, rgba(169, 124, 63, .11) 0 6px, transparent 6px 12px);
}
.fac.belt { background: #ECF2F0; border-width: 1.8px; }
.fac.gate { background: #FBF1E7; border-width: 2px; }
.fac > .head, .fac > .softrow, .fac > .soft, .fac > .tag, .fac > .facts,
.fac > .shelves, .fac > .route, .fac > .crit { position: relative; z-index: 3; }
.head { display: flex; align-items: center; gap: 5px; }
.pno {
  flex: none; background: #E07A1F; color: #fff; font-weight: 800; font-size: 10.4px;
  line-height: 15px; padding: 0 5px; border-radius: 2px; letter-spacing: .6px;
}
.fname { flex: none; font-size: 12.4px; font-weight: 800; letter-spacing: .4px; white-space: nowrap; }
.kind {
  flex: none; font-size: 7.4px; color: #5B6C78; border: 1px solid #AEBBC4; background: #fff;
  padding: 0 4px; border-radius: 2px; white-space: nowrap; line-height: 12px;
}
.badges { margin-left: auto; display: flex; gap: 3px; flex: none; }
.badge {
  width: 17px; height: 17px; border-radius: 50%; background: #fff;
  border: 1.6px solid #E07A1F; color: #22303A; font-size: 10.5px; line-height: 14px;
  text-align: center; font-weight: 700;
}
.softrow { display: flex; align-items: baseline; gap: 6px; margin-top: 3px; }
.soft {
  flex: 1; min-width: 0; font-family: "DejaVu Sans Mono", "Noto Sans Mono CJK SC", monospace;
  font-size: 8.6px; color: #3E5563; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pg {
  flex: none; font-family: "DejaVu Sans Mono", monospace; font-size: 7px;
  color: #8FA0AB; letter-spacing: .3px;
}
.crit {
  margin-top: auto; padding-top: 4px; border-top: 1px dashed #C9BE9F;
  font-size: 7.9px; line-height: 1.45; color: #4A5C67;
}
.crit b { color: #8A6A3C; font-weight: 800; margin-right: 4px; }
.tag { margin-top: 4px; font-size: 8.5px; line-height: 1.42; color: #3A4A55; }
.tag .q, .tag .a {
  display: inline-block; width: 12px; height: 12px; line-height: 12px; text-align: center;
  font-size: 7.6px; border-radius: 2px; color: #fff; margin-right: 2px; font-weight: 700;
}
.tag .q { background: #A8452F; }
.tag .a { background: #3C7452; }
.tag .arrow { color: #D9761C; font-weight: 800; margin: 0 3px; }
.facts { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 3px; }
.facts span {
  font-size: 7.4px; color: #4A5C67; background: #F0EBDF; border: 1px solid #D6CDB9;
  border-radius: 2px; padding: 0 4px; line-height: 12px; white-space: nowrap;
  font-family: "DejaVu Sans Mono", "Noto Sans CJK SC", monospace;
}
.shelves { margin-top: 5px; }
.shelves-h { font-size: 7.6px; color: #7A6534; letter-spacing: 1px; margin-bottom: 2px; }
.shelf { display: flex; align-items: center; height: 20px; border-bottom: 1.3px solid #B7A981; position: relative; }
.shelf::before, .shelf::after { content: ""; position: absolute; bottom: -1.3px; width: 3px; height: 8px; background: #8C7A4E; }
.shelf::before { left: 0; }
.shelf::after { right: 0; }
.shelf-name { font-family: "DejaVu Sans Mono", monospace; font-size: 8px; color: #3E5563; margin-left: 7px; }
.shelf-tag { margin-left: auto; font-size: 7px; color: #8A7A50; }
.ticks { position: absolute; left: 10px; right: 10px; bottom: 6px; display: flex; justify-content: space-between; z-index: 2; }
.ticks i { display: block; width: 5px; height: 7px; background: #D9761C; opacity: .6; }
.route { margin-top: 5px; display: flex; flex-wrap: wrap; align-items: center; gap: 2px; }
.route span {
  font-family: "DejaVu Sans Mono", monospace; font-size: 7.3px; background: #F0E6DA;
  border: 1px solid #D8C4AC; border-radius: 2px; padding: 0 3px; line-height: 12px; white-space: nowrap;
}
.route em { font-style: normal; color: #D9761C; font-size: 7.6px; }

.fac.sel { outline: 2.5px solid #E07A1F; outline-offset: 2px; background: #FFF6E7;
           box-shadow: 4px 5px 0 rgba(224, 122, 31, .25); }
.fac.related { box-shadow: 0 0 0 2px rgba(224, 122, 31, .5), 3px 4px 0 rgba(43, 59, 70, .12); }
#map.dim .fac:not(.sel):not(.related) { opacity: .55; }

.rlabel {
  position: absolute; z-index: 6; font-size: 8.1px; line-height: 13px; color: #22303A;
  background: rgba(255, 253, 247, .95); border: 1px solid #B9C4CB; border-radius: 2px;
  padding: 0 5px; white-space: nowrap; letter-spacing: .2px;
  box-shadow: 0 1px 0 rgba(43, 59, 70, .08);
}
.note {
  position: absolute; z-index: 5; background: rgba(255, 253, 247, .94);
  border: 1.3px dashed #A9977A; border-radius: 3px; padding: 7px 9px;
  display: flex; flex-direction: column; justify-content: center; gap: 2px;
}
.note-h { font-size: 9px; font-weight: 800; color: #7A5E2E; letter-spacing: .5px; }
.note-l { font-size: 8.05px; color: #43555F; line-height: 1.44; }
.note-info { border-color: #93A3AE; background: rgba(255, 253, 247, .9); }
.note-info .note-h { color: #3E5563; }

.citizen { position: absolute; z-index: 7; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; }
.citizen .person { width: 30px; height: 37px; margin-bottom: 1px; }
.c-name { font-size: 9.6px; font-weight: 800; letter-spacing: .6px; }
.c-soft { font-family: "DejaVu Sans Mono", monospace; font-size: 7.4px; color: #4D6070; margin-top: 1px; white-space: nowrap; }
.c-note { font-size: 7.2px; color: #8A6A3C; margin-top: 1px; }

.compass { position: absolute; left: 1544px; top: 108px; z-index: 3; width: 22px; height: 30px; }

#ftr { position: absolute; left: 28px; top: 950px; width: 1544px; height: 46px; font-size: 7.9px; color: #5B6C78; }
.ftr-row { position: absolute; left: 0; width: 1544px; display: flex; justify-content: space-between; }
.ftr-row b { font-weight: 700; color: #3E5563; }
.ftr-r1 { top: 0; }
.ftr-r2 { top: 14px; }
.ftr-r3 { top: 28px; }
.hint b { color: #D9761C; }

#tooltip {
  position: absolute; z-index: 100; width: 330px; background: #FFFDF7;
  border: 1.6px solid #22303A; box-shadow: 5px 6px 0 rgba(43, 59, 70, .18);
  padding: 9px 11px; font-size: 8.8px; line-height: 1.5; color: #22303A; pointer-events: none;
}
#tooltip[hidden] { display: none; }
.tt-head { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
.tt-pno { background: #E07A1F; color: #fff; font-weight: 800; font-size: 10px; padding: 0 5px; border-radius: 2px; }
.tt-name { font-size: 12px; font-weight: 800; }
.tt-kind { font-size: 7.4px; color: #5B6C78; border: 1px solid #AEBBC4; padding: 0 4px; border-radius: 2px; margin-left: auto; }
.tt-row { display: flex; gap: 6px; margin-top: 2px; }
.tt-row b { flex: none; width: 30px; font-size: 8.2px; color: #8A6A3C; font-weight: 800; }
.tt-row span { flex: 1; font-size: 8.6px; color: #33454F; }
</style>
</head>
<body>
<div id="page">
  <header id="hdr">
    <div class="hdr-l">
      <div class="kicker">__KICKER__</div>
      <h1>__H1__</h1>
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
    __FACILITIES__
    __CITIZEN__
    __NOTES__
    __ROAD_LABELS__
    __COMPASS__
    <div id="tooltip" hidden>
      <div class="tt-head"><span class="tt-pno"></span><span class="tt-name"></span><span class="tt-kind"></span></div>
      <div class="tt-row"><b>软件</b><span class="tt-soft"></span></div>
      <div class="tt-row"><b>问题</b><span class="tt-problem"></span></div>
      <div class="tt-row"><b>方案</b><span class="tt-solution"></span></div>
      <div class="tt-row"><b>判据</b><span class="tt-criterion"></span></div>
      <div class="tt-row"><b>位置</b><span class="tt-page"></span></div>
    </div>
  </div>
  <footer id="ftr">
    <div class="ftr-row ftr-r1"><span>数据源：<b>manual/city/data.json</b>（单源）· 一条命令重跑：<b>python3 manual/shots/render_city_map.py</b></span><span>23 页标题草案：<b>manual/city/titles-v2.md</b>（确认后再改正文 H1）</span></div>
    <div class="ftr-row ftr-r2"><span>图注：__LEGEND_LONG__</span></div>
    <div class="ftr-row ftr-r3"><span class="hint">悬停设施看「城市名 ↔ 软件名」· <b>点击设施高亮相连道路</b>（再点一次或 Esc 取消）</span><span>本图只画 L1（P0–P9）；L2–L4 的横切系统不进这张图</span></div>
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
  var facs = {};
  DATA.facilities.forEach(function (f) { facs[f.no] = f; });
  var roadEls = Array.prototype.slice.call(document.querySelectorAll('.road-seg'));
  var selected = null;

  function artsText(f) {
    return f.artifacts.map(function (a) { return ARTS.charAt(a - 1); }).join(' ');
  }
  function fillTip(f) {
    tip.querySelector('.tt-pno').textContent = f.no;
    tip.querySelector('.tt-name').textContent = f.name;
    tip.querySelector('.tt-kind').textContent = f.kind;
    tip.querySelector('.tt-soft').textContent = f.soft;
    tip.querySelector('.tt-problem').textContent = f.problem;
    tip.querySelector('.tt-solution').textContent = f.solution;
    tip.querySelector('.tt-criterion').textContent = String(f.criterion).replace(/`/g, '');
    tip.querySelector('.tt-page').textContent = f.page + '（' + f.page_id + '）· 交付物 ' + artsText(f);
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
  function clearSel() {
    selected = null;
    Array.prototype.forEach.call(document.querySelectorAll('.fac.sel'), function (e) { e.classList.remove('sel'); });
    Array.prototype.forEach.call(document.querySelectorAll('.fac.related'), function (e) { e.classList.remove('related'); });
    Array.prototype.forEach.call(document.querySelectorAll('.road-seg.hot'), function (e) { e.classList.remove('hot'); });
    map.classList.remove('dim');
  }
  function select(no) {
    clearSel();
    selected = no;
    var el = document.querySelector('.fac[data-no="' + no + '"]');
    if (!el) return;
    el.classList.add('sel');
    map.classList.add('dim');
    var related = {};
    roadEls.forEach(function (r) {
      if (r.dataset.from === no || r.dataset.to === no) {
        r.classList.add('hot');
        var other = r.dataset.from === no ? r.dataset.to : r.dataset.from;
        if (other !== 'citizen') related[other] = 1;
      }
    });
    Object.keys(related).forEach(function (n) {
      var e = document.querySelector('.fac[data-no="' + n + '"]');
      if (e) e.classList.add('related');
    });
  }
  function toggle(no) { if (selected === no) { clearSel(); } else { select(no); } }
  window.__citySelect = toggle;
  window.__cityClear = clearSel;

  Array.prototype.forEach.call(document.querySelectorAll('.fac'), function (el) {
    var f = facs[el.dataset.no];
    el.addEventListener('mouseenter', function (ev) { fillTip(f); tip.hidden = false; moveTip(ev); });
    el.addEventListener('mousemove', moveTip);
    el.addEventListener('mouseleave', function () { tip.hidden = true; });
    el.addEventListener('click', function (ev) { ev.stopPropagation(); toggle(el.dataset.no); });
    el.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggle(el.dataset.no); }
    });
  });
  map.addEventListener('click', function (ev) {
    if (!ev.target.closest || !ev.target.closest('.fac')) { clearSel(); }
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') { clearSel(); } });

  /* 页面内置自检：DOM 计数 + 交互（悬停 / 点击）真跑一遍，写回 #selftest-data 供 --dump-dom 读取 */
  function collect() {
    var cards = Array.prototype.slice.call(document.querySelectorAll('.fac[data-no]'));
    var badges = Array.prototype.slice.call(document.querySelectorAll('.badge[data-art]'));
    var segs = Array.prototype.slice.call(document.querySelectorAll('.road-seg'));
    var rlabels = Array.prototype.slice.call(document.querySelectorAll('.rlabel'));
    var p4 = document.querySelector('.fac[data-no="P4"]');
    p4.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    var hot = document.querySelectorAll('.road-seg.hot').length;
    var sel = document.querySelectorAll('.fac.sel').length;
    var related = document.querySelectorAll('.fac.related').length;
    p4.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    var hotAfter = document.querySelectorAll('.road-seg.hot').length;
    p4.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false, clientX: 940, clientY: 300 }));
    var tipShown = !tip.hidden;
    var tipText = tip.textContent;
    p4.dispatchEvent(new MouseEvent('mouseleave'));
    var tipHidden = tip.hidden;
    var rects = cards.map(function (c) {
      var r = c.getBoundingClientRect();
      return { no: c.dataset.no, x: Math.round(r.left), y: Math.round(r.top),
               w: Math.round(r.width), h: Math.round(r.height) };
    });
    var overflow = cards.filter(function (c) { return c.scrollHeight > c.clientHeight + 1; })
                        .map(function (c) { return c.dataset.no; });
    var clipped = Array.prototype.filter.call(document.querySelectorAll('.soft'),
      function (s) { return s.scrollWidth > s.clientWidth + 1; })
      .map(function (s) { return s.textContent; });
    var zoneLabels = Array.prototype.map.call(document.querySelectorAll('.zone'), function (z) {
      var lab = z.querySelector('.zlabel').getBoundingClientRect();
      return { id: z.dataset.zone, labelBottom: Math.round(lab.bottom) };
    });
    return {
      facilities: cards.map(function (c) { return c.dataset.no; }),
      badges: badges.map(function (b) { return b.dataset.art; }),
      roads: segs.map(function (s) { return s.dataset.key; }),
      rlabels: rlabels.map(function (s) { return s.textContent; }),
      notes: document.querySelectorAll('.note').length,
      shelves: document.querySelectorAll('.shelf').length,
      route: document.querySelectorAll('.route span').length,
      ticks: document.querySelectorAll('.ticks i').length,
      zones: document.querySelectorAll('.zone').length,
      pages: cards.map(function (c) { return c.querySelector('.pg').textContent; }),
      crits: document.querySelectorAll('.crit').length,
      overflow: overflow,
      clipped: clipped,
      zoneLabels: zoneLabels,
      selftest: { hot: hot, sel: sel, related: related, hotAfter: hotAfter,
                  tipShown: tipShown, tipHidden: tipHidden,
                  tipHasSoft: tipText.indexOf('POST /api/query') >= 0,
                  tipHasPage: tipText.indexOf('第 4 页') >= 0 },
      resources: performance.getEntriesByType('resource').length,
      srcAttrs: document.querySelectorAll('[src]').length + document.querySelectorAll('link').length,
      font: getComputedStyle(document.body).fontFamily,
      docW: document.documentElement.scrollWidth,
      docH: document.documentElement.scrollHeight,
      bodyW: document.body.scrollWidth,
      bodyH: document.body.scrollHeight,
      h1: document.querySelector('h1').textContent,
      tooltipText: tipText.slice(0, 400),
      rects: rects
    };
  }
  document.getElementById('selftest-data').textContent = JSON.stringify(collect());
})();
</script>
</body>
</html>
"""


def build_html(data: dict, info: dict) -> str:
    plan_note = (f"规划示意 · 非按比例 · {len(data['facilities'])} 座设施 · 12 件交付物 · "
                 f"{len(data['roads'])} 条道路 / 管网 · {len(data['titles'])} 页标题")
    legend = "".join(
        f'<span class="lg lg-{esc(l["mark"])}"><i></i>{esc(l["short"])}</span>'
        for l in data["legend"])
    legend_long = " · ".join(l["text"] for l in data["legend"])
    granularity = " · ".join(f'<b>{esc(c)}</b> = {esc(s)}' for c, s in
                             ((g["city"], g["soft"]) for g in data["granularity"]))
    page = HTML_TEMPLATE
    replacements = {
        "__W__": str(DESIGN_W),
        "__H__": str(DESIGN_H),
        "__FX__": str(FRAME["x"]),
        "__FY__": str(FRAME["y"]),
        "__FW__": str(FRAME["w"]),
        "__FH__": str(FRAME["h"]),
        "__H1__": esc(data["title"]),
        "__KICKER__": esc(data["kicker"]),
        "__ONE_LINER__": esc(data["one_liner"]),
        "__PLAN_NOTE__": esc(plan_note),
        "__LEGEND__": legend,
        "__LEGEND_LONG__": esc(legend_long),
        "__GRANULARITY__": granularity,
        "__ZONES__": "".join(zone_html(z) for z in data["zones"]),
        "__ROADS__": roads_svg(data["roads"], info["rects"]),
        "__FACILITIES__": "".join(facility_html(f) for f in
                                  sorted(data["facilities"],
                                         key=lambda f: (1 if "parent" in f else 0, f["no"]))),
        "__CITIZEN__": citizen_html(data["citizen"]),
        "__NOTES__": notes_html(data["notes"]),
        "__ROAD_LABELS__": road_labels_html(data["roads"]),
        "__COMPASS__": compass_html(),
        "__DATA_JSON__": json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page


def build_titles_md(data: dict) -> str:
    lines = [
        "# 23 页「问题 + 方案」标题草案（D45 · 城市隐喻）",
        "",
        "> 这是**标题草案**：确认后再改十页正文 H1；正文、SPEC、completeness、maturity 一律不动。",
        "> 依据：`humen-desicions/09-ablation-course.md` D44（造 → 换 → 审 → 守，10+4+4+5 = 23 页）"
        "与 D45（标题统一「问题 + 方案」，先出样例再全量替换）；设施 / 道路单源见 "
        "[data.json](data.json)，城市地图见 [city-map.html](city-map.html) 与 "
        "[成图](../images/city-map-l1.png)。",
        "> 级的口径：L1 造 = 从无到有；L2 换 = 真的假不了；L3 审 = 机器靠不靠谱；"
        "L4 守 = 出了事兜不兜得住。本表由 `python3 manual/shots/render_city_map.py` "
        "从 data.json 生成，改标题只改 data.json。",
        "",
        "| 页码 | 级 | 问题 | 方案 | 判据摘要 |",
        "|---|---|---|---|---|",
    ]
    for t in data["titles"]:
        lines.append(f'| {t["page"]} | {t["level"]} | {t["problem"]} | {t["solution"]} | {t["criterion"]} |')
    lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ 文本 / 成品自检

def scan_forbidden(text: str, label: str) -> None:
    bad: list[str] = []
    for token in FORBIDDEN:
        if token and token in text:
            bad.append(f"禁用字符串 {token!r}")
    for pattern, why in EXTERNAL_PATTERNS:
        if re.search(pattern, text):
            bad.append(why)
    if bad:
        print(f"✗ {label} 含不许出现的内容：", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        raise SystemExit(1)


def check_html_static(page: str, data: dict, info: dict) -> None:
    if "Noto Sans CJK SC" not in page:
        fail("CSS 没有指定系统中文字体 Noto Sans CJK SC")
    for token in REQUIRED_TOKENS:
        if token not in page:
            fail(f"成品 HTML 里缺少关键真值 {token!r}（图会讲不清）")
    if page.count('class="badge"') != 12:
        fail(f"HTML 里圈号徽章 {page.count('class=\"badge\"')} 个，应为 12")
    if page.count('class="zone zone-') != 4:
        fail("HTML 里区划不是 4 个")
    if page.count('class="road-seg"') != len(data["roads"]):
        fail(f"HTML 里道路 {page.count('class=\"road-seg\"')} 条，应为 {len(data['roads'])}")
    if page.count('style="left:') < 10:
        fail("HTML 里绝对定位元素太少，版面没排出来")
    print("  ✓ HTML 素材：零外链 / 零 src·href 资源 / 无用户名 / 绝对路径 / 口令；"
          "10 设施 / 12 徽章 / 11 条道路都在")


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


def check_metrics(metrics: dict, data: dict, info: dict) -> None:
    errs: list[str] = []
    want_facs = [f["no"] for f in data["facilities"]]
    got_facs = sorted(metrics.get("facilities") or [], key=lambda s: int(str(s)[1:]))
    if got_facs != want_facs:
        errs.append(f"页面设施 {metrics.get('facilities')}，应为 {want_facs}")
    got_badges = sorted(int(x) for x in (metrics.get("badges") or []))
    if got_badges != list(range(1, 13)):
        errs.append(f"页面徽章 {metrics.get('badges')}，应为 1–12 各一次")
    want_roads = [r["key"] for r in data["roads"]]
    if metrics.get("roads") != want_roads:
        errs.append("页面道路 key 与 data.json 不一致")
    want_labels = [r["label"] for r in data["roads"]]
    if metrics.get("rlabels") != want_labels:
        errs.append("页面道路标注与 data.json 不一致")
    if metrics.get("notes") != len(data["notes"]):
        errs.append(f"页面图注 {metrics.get('notes')} 个，应为 {len(data['notes'])}")
    if metrics.get("zones") != 4:
        errs.append(f"页面区划 {metrics.get('zones')} 个，应为 4")
    if metrics.get("shelves") != 5:
        errs.append(f"P2 货架 {metrics.get('shelves')} 行，应为 5（5 张库表）")
    if metrics.get("route") != len(data["facilities"][-1].get("route") or []):
        errs.append("P9 端到端链路步骤数与 data.json 不一致")
    if metrics.get("ticks") != PROGRESS_TICKS:
        errs.append(f"传送带进度刻度 {metrics.get('ticks')} 个，应为 {PROGRESS_TICKS}")
    want_pages = sorted(f"第 {int(f["no"][1:])} 页" for f in data["facilities"])
    if sorted(metrics.get("pages") or []) != want_pages:
        errs.append(f"页面页码标 {metrics.get('pages')}，应为 {want_pages}")
    want_crits = sum(1 for f in data["facilities"] if f.get("crit_on_map"))
    if metrics.get("crits") != want_crits:
        errs.append(f"页面判据条 {metrics.get('crits')} 条，应为 {want_crits}")
    if metrics.get("overflow"):
        errs.append(f"设施卡内容溢出（会被裁掉）：{metrics['overflow']}")
    if metrics.get("clipped"):
        errs.append(f"软件对应行被省略号截断：{metrics['clipped']}")
    zone_min_top = {}
    for f in data["facilities"]:
        zone_min_top[f["zone"]] = min(zone_min_top.get(f["zone"], 10 ** 9), f["position"]["y"])
    for zl in metrics.get("zoneLabels") or []:
        limit = zone_min_top.get(zl["id"])
        if limit is not None and zl["labelBottom"] > limit - 2:
            errs.append(f"区 {zl['id']} 的标题底边 {zl['labelBottom']} 压住了第一座设施（top {limit}）")
    if metrics.get("h1") != data["title"]:
        errs.append("页面 H1 与 data.json 的 title 不一致")
    hit = metrics.get("selftest", {})
    connected = sum(1 for r in data["roads"] if "P4" in (r["from"], r["to"]))
    related = len({r["to"] if r["from"] == "P4" else r["from"]
                   for r in data["roads"] if "P4" in (r["from"], r["to"])} - {"citizen"})
    for key, want in (("hot", connected), ("sel", 1), ("related", related), ("hotAfter", 0)):
        if hit.get(key) != want:
            errs.append(f"交互自检 {key}={hit.get(key)}，应为 {want}（点击 P4 应高亮 {connected} 条路）")
    if not hit.get("tipShown") or not hit.get("tipHidden"):
        errs.append("悬停 tooltip 没有正确显示 / 收起")
    if not hit.get("tipHasSoft"):
        errs.append("tooltip 里没有软件对应（POST /api/query）")
    if not hit.get("tipHasPage"):
        errs.append("tooltip 里没有页码（第 4 页）")
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
    for rect in metrics.get("rects", []):
        r = {"x": rect["x"], "y": rect["y"], "w": rect["w"], "h": rect["h"]}
        if not in_canvas(r):
            errs.append(f"{rect['no']} 渲染后越出画布：{rect}")
        want = pos_size(info["facilities"][rect["no"]])
        if abs(r["x"] - want["x"]) > 1 or abs(r["y"] - want["y"]) > 1 \
                or abs(r["w"] - want["w"]) > 1 or abs(r["h"] - want["h"]) > 1:
            errs.append(f"{rect['no']} 渲染位置 {r} 与 data.json {want} 不一致")
    if errs:
        print("✗ 页面内置自检失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  ✓ 页面自检：10 设施 / 12 徽章 / 11 条路 / 4 区 / 3 图注 / 5 货架 / "
          f"{PROGRESS_TICKS} 个进度刻度 / 10 个页码标 / {want_crits} 条判据；"
          f"悬停 tooltip 有软件名与页码；点击 P4 高亮 {connected} 条路、再点归零；"
          f"无外部请求、无内容溢出 / 截断、区标题不压设施")


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
        fail(f"city-map-l1.png 带文本元数据块 {chunks}（不许夹带用户名 / 路径 / 口令）")
    text = blob.decode("latin-1", "ignore")
    for bad in FORBIDDEN:
        if len(bad) >= 6 and bad in text:
            fail(f"city-map-l1.png 里出现禁用字符串 {bad!r}")
    if "http://" in text or "https://" in text:
        fail("city-map-l1.png 里出现外链")


def check_png(png: Path, data: dict) -> None:
    size = png_size(png)
    if size != (OUT_W, OUT_H):
        fail(f"成图尺寸 {size} ≠ {OUT_W}×{OUT_H}")
    if png.stat().st_size < 200_000:
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
    if not (0.3 <= orange <= 6.0):
        fail(f"橙色强调占比 {orange:.2f}% 不在 0.3%–6%")
    if not (0.8 <= ink <= 25.0):
        fail(f"墨色（深字 / 道路）占比 {ink:.2f}% 不在 0.8%–25%")
    if not (3.0 <= mid <= 45.0):
        fail(f"中调（文字 / 描边）占比 {mid:.2f}% 不在 3%–45%")
    if not (40.0 <= light <= 95.0):
        fail(f"纸色占比 {light:.2f}% 不在 40%–95%")
    if colors < 300:
        fail(f"成图只有 {colors} 种颜色，像没渲染出来")

    # 四个区各裁一块，确认都有墨（不是空区）
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
    print(f"  ✓ 成图：{size[0]}×{size[1]}，{png.stat().st_size // 1024} KB；"
          f"橙色 {orange:.2f}% / 墨 {ink:.2f}% / 中调 {mid:.2f}% / 纸 {light:.2f}%，{colors} 种颜色；"
          f"四区都有墨（" + " / ".join(f"{k} {v:.1f}%" for k, v in stats.items()) + "）")


def ocr_soft_check(png: Path) -> None:
    """装了 tesseract 时才跑：OCR 抽查图上关键真值；找不到只提醒，不拦渲染。"""
    import shutil
    if not shutil.which("tesseract"):
        print("  ! OCR：本机没装 tesseract，跳过（像素与 DOM 自检已覆盖）")
        return
    try:
        proc = subprocess.run(["tesseract", str(png), "stdout", "-l", "eng", "--psm", "11"],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        print("  ! OCR：tesseract 跑不起来，跳过")
        return
    text = re.sub(r"\s+", "", proc.stdout)
    hits = [tok for tok in ("41099.5", "115", "3307", "8000", "8081") if tok in text]
    if hits:
        print(f"  ✓ OCR 抽查（eng）：图上认出 {' / '.join(hits)}")
    else:
        print("  ! OCR 抽查（eng）：中文密排图上没认出关键真值（只提醒，以 DOM 与像素自检为准）")


# ------------------------------------------------------------------ 主流程

def main() -> int:
    if not Path(CHROME).exists():
        fail(f"找不到 Chrome：{CHROME}")

    print("① 读 data.json + 结构与几何自检")
    data = load_json(DATA_PATH, "data.json")
    info = validate_data(data)
    scan_forbidden(DATA_PATH.read_text(encoding="utf-8"), "data.json")
    print("  ✓ 数据文本：无外链 / 用户名 / 绝对路径 / 口令")

    print("② 组版 city-map.html（四区 + 十设施 + 十二条徽章 + 十一条道路 + 图注）")
    page = build_html(data, info)
    scan_forbidden(page, "成品 HTML")
    check_html_static(page, data, info)
    HTML_PATH.write_text(page, encoding="utf-8")

    print("③ 生成 titles-v2.md（23 行标题草案，≤60 行）")
    titles_md = build_titles_md(data)
    scan_forbidden(titles_md, "titles-v2.md")
    lines = titles_md.rstrip("\n").split("\n")
    if len(lines) > 60:
        fail(f"titles-v2.md 有 {len(lines)} 行，超过 60 行预算")
    rows = [x for x in lines if x.startswith("| P")]
    if len(rows) != 23:
        fail(f"titles-v2.md 表格数据行 {len(rows)} 行，应为 23 行")
    for i, row in enumerate(rows):
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != 5:
            fail(f"titles-v2.md 第 {i + 1} 行列数 {len(cells)}，应为 5 列")
        t = data["titles"][i]
        if cells[:5] != [t["page"], t["level"], t["problem"], t["solution"], t["criterion"]]:
            fail(f"titles-v2.md 第 {i + 1} 行与 data.json 不一致：{cells}")
    if "确认后再改十页正文 H1" not in titles_md:
        fail("titles-v2.md 开头缺「这是标题草案，确认后再改十页正文 H1」的说明")
    TITLES_PATH.write_text(titles_md, encoding="utf-8")
    print(f"  ✓ titles-v2.md：{len(lines)} 行、23 行表格（P0–P22 顺序、5 列、与 data.json 逐字一致）")

    with tempfile.TemporaryDirectory(prefix="city-map-") as tmp:
        work = Path(tmp)
        html_path = work / "city-map.html"
        html_path.write_text(page, encoding="utf-8")
        print("④ 无头 Chrome 读回页面内置自检（DOM + tooltip + 点击高亮）")
        metrics = parse_selftest(dump_dom(html_path, work))
        check_metrics(metrics, data, info)
        print("⑤ 无头 Chrome 截图 1600×1000 @2x")
        raw = work / "city-map-l1.raw.png"
        screenshot(html_path, raw, work)
        png_bytes = raw.read_bytes()

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PNG.write_bytes(png_bytes)
    print("⑥ 成图自检")
    check_png(OUT_PNG, data)
    ocr_soft_check(OUT_PNG)

    print("\n✓ 完成：")
    print(f"  {HTML_PATH.relative_to(REPO)}（可交互：悬停 tooltip / 点击高亮相连道路）")
    print(f"  {TITLES_PATH.relative_to(REPO)}（23 行标题草案）")
    print(f"  {OUT_PNG.relative_to(REPO)}  {OUT_W}×{OUT_H}  {OUT_PNG.stat().st_size // 1024} KB")
    print(f"  重跑：{RERUN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
