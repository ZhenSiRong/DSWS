#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_explorer.py —— 由单源 data.json 生成《建成证明》可交互原型 explorer.html。

在仓库根目录一条命令重跑：

    python3 manual/shots/build_explorer.py

它做四件事：

1. **读单源**：`manual/completeness/data.json`（12 个节点 = 四层「责任 × 证据」矩阵的
   12 行；10 个槽位 A0–A9；13 项能力列；13 条链路边；D38 三条完备性判据）。
2. **反向核对**（防止两版漂移）：
   - 解析 `manual/completeness/poster.md` 的四张矩阵，逐行核对「节点名 / 能力列名 /
     ■ 与 — / 证据文本」，要求与 data.json 一字一致；
   - 解析 `manual/flow.mmd`，核对槽位 A0–A9 的活动名与工期；
   - 核对槽位↔节点归属、答案态自检（10/10 槽位、12/12 行、13/13 列、13/13 边）。
3. **内联**：把 data.json 原样内联进 HTML 模板的 `<script type="application/json">`，
   产物是**单文件、零依赖、离线可双击打开**的 explorer.html（不引 CDN / 外部字体 / 图片）。
4. **自检产物**：HTML 里必须出现 `Noto Sans CJK SC`；不许出现 URL / `<link` / `src=` /
   `@import` / `url(` / `fetch(` 等外部资源痕迹；不许出现用户名或绝对路径。

依赖：只要 python3。不需要 Chrome（截图与交互验证见 manual/review/explorer-shots/）。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
MANUAL = REPO / "manual"
DATA_PATH = MANUAL / "completeness" / "data.json"
POSTER_MD = MANUAL / "completeness" / "poster.md"
FLOW_MMD = MANUAL / "flow.mmd"
OUT_PATH = MANUAL / "completeness" / "explorer.html"

SLOT_IDS = ["A%d" % i for i in range(10)]
STATUS = ("unbuilt", "unverified", "built")
LAYER_IDS = ["L1", "L2", "L3", "L0"]

# 产物里不许出现的字符串（用户名 / 绝对路径 / 外部资源）
FORBIDDEN = ["/home/", "/Users/", "/tmp/", "zhensirong", "root@", ".dsh"]
EXTERNAL = ["http://", "https://", "//cdn", "<link", "@import", "url(", "src=",
            "fetch(", "XMLHttpRequest", "<iframe"]

# 证据必须与现有海报逐条一致，任务点名要核对的四串
EVIDENCE_MUST = [
    "COUNT(*)=115",
    "rows[0].sales=41099.5",
    "progress=12",
    "SELECT VERSION()=8.0.46",
]

DATA_TOKEN = "__DATA_JSON__"


def fail(msg: str) -> None:
    raise SystemExit("build_explorer.py: " + msg)


def ok(msg: str) -> None:
    print("  ✓ " + msg)


# ------------------------------------------------------------------ data.json

def load_data() -> dict:
    if not DATA_PATH.exists():
        fail("缺 %s" % DATA_PATH.relative_to(REPO))
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("data.json 不是合法 JSON：%s" % exc)
    return data


def index_nodes(data: dict) -> dict:
    return {n["id"]: n for layer in data["layers"] for n in layer["nodes"]}


def index_slots(data: dict) -> dict:
    return {s["id"]: s for s in data["slots"]}


def validate_data(data: dict) -> None:
    need = ["schema", "title", "layers", "capability_columns", "slots", "edges",
            "completeness_rules", "status_legend", "answer_selfcheck", "meta"]
    for key in need:
        if key not in data:
            fail("data.json 缺字段 %r" % key)

    # 层：四层、顺序固定
    layers = data["layers"]
    if [layer["id"] for layer in layers] != LAYER_IDS:
        fail("layers 必须是 %s，实际 %s" % (LAYER_IDS, [x["id"] for x in layers]))
    if set(data["capability_columns"]) != set(LAYER_IDS):
        fail("capability_columns 必须按四层分组")

    # 槽位：正好 A0–A9，各字段合法
    slots = data["slots"]
    if [s["id"] for s in slots] != SLOT_IDS:
        fail("slots 必须正好是 A0–A9 且按序，实际 %s" % [s["id"] for s in slots])
    nodes = index_nodes(data)
    for slot in slots:
        if slot["status"] not in STATUS:
            fail("槽位 %s 状态非法：%r" % (slot["id"], slot["status"]))
        if not isinstance(slot["duration_min"], int) or slot["duration_min"] <= 0:
            fail("槽位 %s 工期必须是正整数" % slot["id"])
        if slot["node"] not in nodes:
            fail("槽位 %s 指向不存在的节点 %r" % (slot["id"], slot["node"]))
        if not slot.get("judge"):
            fail("槽位 %s 缺完成判据文本" % slot["id"])
        page = slot["page"]
        if not re.fullmatch(r"page-0[0-9]\.md", page):
            fail("槽位 %s 的 page 不是 page-0N.md：%r" % (slot["id"], page))
        if not (MANUAL / page).exists():
            fail("槽位 %s 的 %s 不存在" % (slot["id"], page))

    # 节点：12 个矩阵行；能力键 = 该层列 id；证据/页/工期/槽位归属
    count = 0
    for layer in layers:
        cols = data["capability_columns"][layer["id"]]
        if not isinstance(cols, list) or not cols or not all(isinstance(c, str) and c for c in cols):
            fail("%s 能力列必须是列名（非空字符串）数组" % layer["id"])
        if len(set(cols)) != len(cols):
            fail("%s 能力列名重复" % layer["id"])
        for node in layer["nodes"]:
            count += 1
            nid = node["id"]
            if node["layer"] != layer["id"]:
                fail("节点 %s 的 layer 与所在层不一致" % nid)
            if node["status"] not in STATUS:
                fail("节点 %s 状态非法" % nid)
            if not node.get("evidence"):
                fail("节点 %s 缺证据文本" % nid)
            if set(node["capabilities"]) != set(cols):
                fail("节点 %s 的能力键必须正好是该层列名 %s" % (nid, cols))
            if any(not isinstance(v, bool) for v in node["capabilities"].values()):
                fail("节点 %s 的 capabilities 值必须是布尔" % nid)

            pages = node.get("pages") or [node["page"]]
            if node["page"] not in pages:
                fail("节点 %s 的 page 必须在 pages 里" % nid)
            for page in pages:
                if not re.fullmatch(r"page-0[0-9]\.md", page):
                    fail("节点 %s 的 pages 里有非法页名 %r" % (nid, page))
                if not (MANUAL / page).exists():
                    fail("节点 %s 的 %s 不存在" % (nid, page))

            node_slots = node.get("slots") or []
            derived = node.get("derived_from_slots") or []
            if node_slots:
                if len(node_slots) == 1:
                    if node["slot"] != node_slots[0]:
                        fail("节点 %s 单槽位时 slot 必须等于该槽位" % nid)
                elif node["slot"] is not None:
                    fail("节点 %s 多槽位时 slot 应为 null（槽位见 slots）" % nid)
                if derived:
                    fail("节点 %s 不能既有 slots 又有 derived_from_slots" % nid)
                if node.get("slot_ref") or node.get("derive_note"):
                    fail("节点 %s 有独立槽位，不该再写 slot_ref / derive_note" % nid)
                for sid in node_slots:
                    if sid not in SLOT_IDS:
                        fail("节点 %s 引用了非法槽位 %r" % (nid, sid))
                    if data_slot_owner(data, sid) != nid:
                        fail("槽位 %s 的 node 不是 %s" % (sid, nid))
                want = sum(index_slots(data)[sid]["duration_min"] for sid in node_slots)
                if node.get("duration_min") != want:
                    fail("节点 %s 的 duration_min 应为槽位工期之和 %d" % (nid, want))
            else:
                if not derived:
                    fail("节点 %s 既无槽位也无派生来源" % nid)
                for sid in derived:
                    if sid not in SLOT_IDS:
                        fail("节点 %s 的 derived_from_slots 含非法槽位 %r" % (nid, sid))
                if node.get("duration_min") is not None:
                    fail("节点 %s 无槽位，duration_min 必须为 null" % nid)
                if not node.get("slot_ref") or not node.get("derive_note"):
                    fail("节点 %s 无独立槽位，必须写 slot_ref 与 derive_note" % nid)

    if count != 12:
        fail("节点总数应为 12 行（四层 2/3/5/2），实际 %d" % count)
    if len(data["meta"].get("row_plan", {})) != 4:
        fail("meta.row_plan 缺层")

    # 边：端点存在；答案态全通
    for edge in data["edges"]:
        for end in ("from", "to"):
            if edge[end] not in nodes:
                fail("边 %s 的端点 %r 不存在" % (edge["id"], edge[end]))
        if not edge.get("label"):
            fail("边 %s 缺 label" % edge["id"])

    # 判据：三条
    if len(data["completeness_rules"]) != 3:
        fail("completeness_rules 必须是 D38 的三条判据")
    if len(data["status_legend"]) != 3:
        fail("status_legend 必须是三态")
    if [x["key"] for x in data["status_legend"]] != list(STATUS):
        fail("status_legend 顺序应为 %s" % (STATUS,))

    # 答案态：全部 built；自检数字对得上
    slots_by_id = index_slots(data)
    for slot in data["slots"]:
        if slot["status"] != "built":
            fail("答案态槽位 %s 必须是 built" % slot["id"])
    for node in nodes.values():
        if node["status"] != "built":
            fail("答案态节点 %s 必须是 built" % node["id"])

    rows = sum(len(layer["nodes"]) for layer in layers)
    cols = sum(len(data["capability_columns"][layer["id"]]) for layer in layers)
    covered = sum(1 for node in nodes.values() for cid, provided in node["capabilities"].items() if provided)
    selfcheck = data["answer_selfcheck"]
    if rows != 12 or cols != 13 or covered != 13:
        fail("答案态自检应为 12 行 / 13 列 / 13 个 ■，实际 %d/%d/%d" % (rows, cols, covered))
    if selfcheck.get("rows") != "12/12" or selfcheck.get("columns") != "13/13":
        fail("answer_selfcheck 的 rows/columns 口径不对")
    if len(slots_by_id) != 10 or len(data["edges"]) != data["meta"]["edge_count"]:
        fail("槽位/边数量与 meta 不符")
    all_evidence = [n["evidence"] for n in nodes.values()]
    for needle in EVIDENCE_MUST:
        if not any(needle in ev for ev in all_evidence):
            fail("证据里缺少点名判据 %r" % needle)

    ok("data.json 结构：12 节点 / 10 槽位 / 13 能力列 / 13 条边 / 3 条判据")
    ok("答案态自检：A0–A9 10/10 · 行 12/12 · 列 13/13 · ■ 13 个")


def data_slot_owner(data: dict, slot_id: str) -> str:
    for slot in data["slots"]:
        if slot["id"] == slot_id:
            return slot["node"]
    fail("未知槽位 %r" % slot_id)
    return ""


# ------------------------------------------------------------------ poster.md 反向核对

def _is_separator(cells: list) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-+:?", c.replace(" ", "")) for c in cells if c)


def parse_poster_sections(path: Path) -> dict:
    sections: dict = {}
    current = None
    in_table = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        heading = re.match(r"^###\s+(L[0-3])\s*·", line)
        if heading:
            current = heading.group(1)
            sections[current] = {"header": None, "rows": []}
            in_table = False
            continue
        if re.match(r"^#{1,6}\s", line):      # 任何其他标题：当前矩阵小节结束
            current = None
            in_table = False
            continue
        if current is None:
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if _is_separator(cells):
                continue
            if sections[current]["header"] is None:
                sections[current]["header"] = cells
            else:
                sections[current]["rows"].append(cells)
            in_table = True
        elif in_table and line == "":
            in_table = False
        # 其余段落文本忽略
    return sections


def check_poster(data: dict) -> None:
    if not POSTER_MD.exists():
        fail("缺 %s（海报源稿，反向核对用）" % POSTER_MD.relative_to(REPO))
    sections = parse_poster_sections(POSTER_MD)
    if set(sections) != set(LAYER_IDS):
        fail("poster.md 里没找到四张矩阵（L1/L2/L3/L0）")
    for layer in data["layers"]:
        code = layer["id"]
        sec = sections[code]
        if not sec["header"]:
            fail("poster.md 的 %s 矩阵缺表头" % code)
        want_cols = data["capability_columns"][code]
        got_cols = sec["header"][1:-1]
        if got_cols != want_cols:
            fail("poster.md %s 能力列与 data.json 不一致：%s ≠ %s" % (code, got_cols, want_cols))
        if len(sec["rows"]) != len(layer["nodes"]):
            fail("poster.md %s 行数 %d ≠ data.json 节点数 %d"
                 % (code, len(sec["rows"]), len(layer["nodes"])))
        for cells, node in zip(sec["rows"], layer["nodes"]):
            label = cells[0]
            marks = cells[1:-1]
            evidence = cells[-1].replace("`", "").strip()
            if label != node["name"]:
                fail("poster.md %s 行名 %r ≠ data.json %r" % (code, label, node["name"]))
            if evidence != node["evidence"]:
                fail("poster.md %s「%s」证据不一致：\n  poster: %r\n  data  : %r"
                     % (code, label, evidence, node["evidence"]))
            if len(marks) != len(want_cols):
                fail("poster.md %s「%s」列数不对" % (code, label))
            for col, mark in zip(want_cols, marks):
                if mark not in ("■", "—"):
                    fail("poster.md %s「%s」矩阵格 %r 不是 ■/—" % (code, label, mark))
                provided = node["capabilities"][col]
                if provided != (mark == "■"):
                    fail("poster.md %s「%s」%s 的 ■/— 与 data.json 不一致"
                         % (code, label, col))
    ok("poster.md 反向核对：4 张矩阵 · 12 行 · 13 列 · 证据逐条一字一致")


# ------------------------------------------------------------------ flow.mmd 反向核对

def check_flow(data: dict) -> None:
    if not FLOW_MMD.exists():
        fail("缺 %s（活动编号/名称口径）" % FLOW_MMD.relative_to(REPO))
    text = FLOW_MMD.read_text(encoding="utf-8")
    found = {}
    pattern = re.compile(r'A(\d+)\["<b>A\d+ (.+?)</b><br/>工期 (\d+)<br/>')
    for m in pattern.finditer(text):
        found["A" + m.group(1)] = (m.group(2).strip(), int(m.group(3)))
    if list(found) != SLOT_IDS:
        fail("flow.mmd 里没解析出 A0–A9 十个活动：%s" % list(found))
    for slot in data["slots"]:
        name, duration = found[slot["id"]]
        if name != slot["name"]:
            fail("flow.mmd %s 活动名 %r ≠ data.json %r" % (slot["id"], name, slot["name"]))
        if duration != slot["duration_min"]:
            fail("flow.mmd %s 工期 %d ≠ data.json %d"
                 % (slot["id"], duration, slot["duration_min"]))
    ok("flow.mmd 反向核对：A0–A9 活动名与工期逐条一致（工期合计 %d 分钟）"
       % sum(s["duration_min"] for s in data["slots"]))


# ------------------------------------------------------------------ HTML 模板

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>建成证明 · 可交互原型</title>
<style>
:root{
  --ink:#111111; --ink2:#333333; --mute:#666666; --hair:#c9c9c9;
  --soft:#f4f4f4; --paper:#ffffff; --wire:#b9b9b9;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:var(--paper);color:var(--ink);}
body{
  font-family:"Noto Sans CJK SC","Source Han Sans SC","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.mono,.ev,.chip,.card-layer,.card-tag,.stat b,.panel-h .ph-n,.chain,a.pg,.card-pg{
  font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;
}
.app{display:flex;flex-direction:column;height:100vh;min-height:660px;overflow:hidden;}

/* ---------- 顶部 ---------- */
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;
     padding:13px 22px 9px;border-bottom:2.5px solid var(--ink);flex:0 0 auto;}
.kicker{font-size:12px;letter-spacing:.6px;color:var(--mute);}
h1{margin:2px 0 0;font-size:27px;font-weight:900;letter-spacing:.5px;line-height:1.1;}
h1 .mid{font-weight:400;color:var(--mute);}
.sub{margin-top:3px;font-size:12.5px;color:var(--ink2);}
.controls{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex:0 0 auto;}
.modes{display:flex;border:2px solid var(--ink);border-radius:6px;overflow:hidden;}
.mode-btn{border:0;border-right:1.5px solid var(--ink);background:#fff;color:var(--ink);
          font:inherit;font-size:13.5px;font-weight:800;padding:6px 15px;cursor:pointer;
          letter-spacing:.5px;}
.mode-btn:last-child{border-right:0;}
.mode-btn:hover{background:#eeeeee;}
.mode-btn.is-on{background:var(--ink);color:#fff;}
.mode-hint{font-size:11.5px;color:var(--mute);max-width:360px;text-align:right;line-height:1.45;}

/* ---------- 状态条 ---------- */
.statusbar{display:flex;align-items:center;gap:9px;padding:7px 22px;
           border-bottom:1.5px solid var(--ink);background:var(--soft);
           flex:0 0 auto;flex-wrap:wrap;}
.stat{display:flex;align-items:baseline;gap:7px;border:1.6px solid var(--ink);
      border-radius:5px;padding:3px 10px;background:#fff;font-size:12.5px;white-space:nowrap;}
.stat .k{font-weight:800;}
.stat b{font-size:16px;letter-spacing:.5px;}
.stat .ok{font-size:12px;font-weight:800;color:#666;}
.stat.pass{background:var(--ink);color:#fff;}
.stat.pass .ok{color:#fff;}
.stat.fail{border-style:dashed;color:#444;}
.stat.fail .ok{color:#888;}
.stat.muted{border-style:dashed;background:#fff;color:#555;font-size:11.5px;}
.stat.muted b{font-size:13px;}
.stamp{margin-left:auto;border:3px double var(--ink);padding:2px 14px;font-size:17px;
       font-weight:900;letter-spacing:2px;transform:rotate(-3deg);background:#fff;
       font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;}
.stamp[hidden]{display:none;}

/* ---------- 中分 ---------- */
.split{display:flex;flex:1 1 auto;min-height:0;}
.left{flex:0 0 58%;min-width:0;padding:12px 16px 12px 22px;overflow:auto;
      display:flex;flex-direction:column;gap:9px;}
.right{flex:1 1 42%;min-width:0;display:flex;flex-direction:column;
       border-left:2px solid var(--ink);background:#fafafa;
       box-shadow:-10px 0 18px rgba(0,0,0,.07);position:relative;z-index:2;}

/* ---------- 左：结构图 ---------- */
.left-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;flex:0 0 auto;}
.lh-title{font-size:14px;font-weight:900;letter-spacing:.4px;}
.lh-note{font-size:11px;color:var(--mute);}
.legend{display:flex;align-items:center;gap:11px;margin-left:auto;flex-wrap:wrap;
        font-size:11px;color:var(--ink2);}
.legend .lg{display:inline-flex;align-items:center;gap:4px;}
.legend .box{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;font-size:15px;line-height:1;}
.legend .dim{color:#888;}
.diagram{border:2px solid var(--ink);border-radius:8px;padding:8px 12px;background:#fff;
          flex:1 1 auto;display:flex;flex-direction:column;min-height:0;}
.lane{display:flex;align-items:stretch;gap:10px;padding:7px 0;flex:1 1 0;min-height:96px;}
.lane + .lane{border-top:1px dashed var(--wire);}
.lane-base{border-top:3.5px solid var(--ink);margin-top:2px;padding-top:10px;
           background:repeating-linear-gradient(135deg,#fff,#fff 8px,#f5f5f5 8px,#f5f5f5 16px);
           border-radius:0 0 5px 5px;}
.gutter{flex:0 0 92px;display:flex;flex-direction:column;justify-content:center;
        border-right:2.5px solid var(--ink);padding-right:9px;line-height:1.18;}
.gutter b{font-size:18px;font-weight:900;}
.gutter span{font-size:12.5px;}
.gutter small{font-size:10px;color:#777;}
.row{flex:1 1 auto;display:grid;gap:9px;align-items:stretch;min-width:0;}
.block{position:relative;display:flex;flex-direction:column;justify-content:center;gap:3px;
       padding:8px 10px;border:1.7px solid var(--ink);border-radius:6px;background:#fff;
       cursor:pointer;transition:background .12s ease,box-shadow .12s ease;overflow:hidden;}
.block:hover{background:#f4f4f4;}
.block:focus-visible{outline:3px double var(--ink);outline-offset:2px;}
.block.is-open{background:#ececec;box-shadow:inset 0 0 0 3px var(--ink);}
.slotline{display:flex;gap:6px;flex-wrap:wrap;align-items:center;min-height:25px;}
.slotpair{display:inline-flex;align-items:center;gap:4px;}
.chip{font-size:10.5px;line-height:16px;padding:0 5px;background:#ededed;
      border:1px solid #888;border-radius:3px;color:#222;white-space:nowrap;}
.chip.ref{background:#fff;border-style:dashed;color:#666;}
.box{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;font-size:18px;line-height:1;
     border:0;background:none;padding:0;cursor:pointer;color:var(--ink);}
.box.ro{cursor:default;color:#333;}
.box.live{border:1.2px solid #b5b5b5;border-radius:4px;background:#fff;padding:0 4px;}
.box.live:hover{background:var(--ink);color:#fff;border-color:var(--ink);}
.bname{font-size:14.5px;font-weight:800;line-height:1.14;letter-spacing:.2px;}
.bnote{font-size:10.7px;color:#555;line-height:1.24;}
.diag-foot{border:1.6px solid var(--ink);border-radius:6px;padding:7px 12px;
           display:flex;align-items:center;gap:10px;flex-wrap:wrap;
           font-size:11.5px;background:#fff;flex:0 0 auto;}
.diag-foot .df-t{font-weight:900;font-size:12px;}
.chain{display:flex;align-items:center;gap:5px;flex-wrap:wrap;font-size:11px;color:#555;}
.chain.pass{color:var(--ink);font-weight:700;}
.chain .arw{color:#999;font-weight:400;}
.chain .res{font-weight:900;}
.diag-cap{font-size:10.5px;color:#777;line-height:1.5;flex:0 0 auto;}

/* ---------- 右：浮层侧栏 ---------- */
.panel-h{display:flex;align-items:center;gap:9px;padding:8px 14px;
         border-bottom:1.5px solid var(--ink);background:#fff;flex:0 0 auto;}
.ph-t{font-size:13px;font-weight:900;letter-spacing:.3px;}
.panel-h .ph-n{font-size:11px;color:#666;}
#close-all{margin-left:auto;border:1.6px solid var(--ink);background:#fff;font:inherit;
           font-size:12px;font-weight:800;padding:4px 11px;border-radius:4px;cursor:pointer;}
#close-all:hover:not(:disabled){background:var(--ink);color:#fff;}
#close-all:disabled{opacity:.35;cursor:default;}
.cards{flex:1 1 auto;overflow:auto;padding:12px 14px 20px;
       display:grid;grid-template-columns:repeat(auto-fit,minmax(246px,1fr));
       gap:12px;align-content:start;align-items:stretch;}
.cards.is-empty{display:flex;flex-direction:column;}
.empty{grid-column:1/-1;flex:1 1 auto;min-height:300px;display:flex;align-items:center;
       justify-content:center;padding:28px;color:#888;font-size:13px;
       text-align:center;line-height:1.8;border:1.6px dashed var(--wire);border-radius:8px;background:#fff;}

.card{border:1.7px solid var(--ink);border-radius:7px;background:#fff;
      padding:9px 11px 10px;display:flex;flex-direction:column;gap:7px;min-width:0;
      box-shadow:0 1px 0 #dddddd;}
.card-h{display:flex;align-items:center;gap:6px;}
.card-layer{font-size:10.5px;background:var(--ink);color:#fff;padding:1px 7px;border-radius:3px;}
.card-tag{font-size:9.5px;color:#666;border:1px solid #aaa;border-radius:3px;padding:0 5px;}
.card-x{margin-left:auto;border:0;background:none;font-size:19px;line-height:1;
        cursor:pointer;color:#444;padding:0 2px;}
.card-x:hover{color:#000;}
.card-name{margin:0;font-size:16.5px;font-weight:900;line-height:1.18;}
.card-status{display:flex;align-items:center;gap:7px;font-size:12px;
             border-top:1px solid #dddddd;border-bottom:1px solid #dddddd;padding:5px 0;}
.card-status .box.big{font-size:21px;line-height:1;}
.card-status .cs-note{color:#666;font-size:10.5px;margin-left:auto;text-align:right;}
.card-slots{display:flex;flex-direction:column;gap:3px;font-size:11px;}
.slotrow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.slotrow .box{font-size:14px;cursor:default;}
.slotrow .dim{color:#666;}
.card-cap{font-size:10px;color:#666;letter-spacing:.2px;margin-bottom:3px;}
.card-mtx table.mini{width:100%;border-collapse:collapse;table-layout:fixed;}
.mini th,.mini td{border:1px solid #333;padding:2px 3px;font-size:9.5px;
                  text-align:center;line-height:1.15;}
.mini thead th{background:#e9e9e9;font-weight:800;overflow-wrap:anywhere;}
.mini td.mark{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;
              font-size:15px;font-weight:700;height:24px;}
.mini td.dash{color:#888;font-size:11.5px;}
.card-ev .ev{margin:0;font-size:10.4px;line-height:1.5;background:#f7f7f7;
             border-left:3px solid var(--ink);padding:5px 7px;overflow-wrap:anywhere;}
.card-pg{font-size:10.5px;color:#444;display:flex;gap:6px;align-items:center;
         flex-wrap:wrap;border-top:1px dashed #cccccc;padding-top:6px;}
a.pg{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--ink);font-size:10px;}
a.pg:hover{background:var(--ink);color:#fff;}

@media (max-width:1180px){
  .left{flex-basis:60%;}
  .legend{display:none;}
}
</style>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="brand">
      <div class="kicker" id="kicker"></div>
      <h1><span id="title"></span> <span class="mid">·</span> <span id="subtitle"></span></h1>
      <div class="sub" id="lead"></div>
    </div>
    <div class="controls">
      <div class="modes" role="group" aria-label="模式切换">
        <button type="button" class="mode-btn" data-mode="answer" aria-pressed="true">答案态</button>
        <button type="button" class="mode-btn" data-mode="blank" aria-pressed="false">空白态</button>
      </div>
      <div class="mode-hint" id="mode-hint"></div>
    </div>
  </header>

  <section class="statusbar" aria-label="完备性状态条">
    <div class="stat" id="stat-rows" title=""></div>
    <div class="stat" id="stat-cols" title=""></div>
    <div class="stat" id="stat-edges" title=""></div>
    <div class="stat muted" title="十个槽位里已涂成 ■ 的个数"><span class="k">槽位 ■</span><b id="slot-count">—</b></div>
    <div class="stamp" id="stamp" hidden>建成证明 ✓</div>
  </section>

  <main class="split">
    <section class="left">
      <div class="left-head">
        <span class="lh-title">① 全局结构图</span>
        <span class="lh-note">L1 / L2 / L3 + L0 地基条 · 块等大（面积不编码任何维度）</span>
        <span class="legend">
          <span class="lg"><span class="box">▢</span>未建</span>
          <span class="lg"><span class="box">◧</span>已建未验</span>
          <span class="lg"><span class="box">■</span>已建且判据通过</span>
          <span class="lg dim">矩阵 ■ 提供 · — 不提供</span>
        </span>
      </div>
      <div class="diagram" id="diagram"></div>
      <div class="diag-foot">
        <span class="df-t">端到端证据</span>
        <span class="chain" id="chain"></span>
      </div>
      <div class="diag-cap">悬停块看工期 / 能力数；点块在右侧开卡，再点同一块关闭该卡；空白态点方框循环涂 ▢ → ◧ → ■，顶部状态条实时重算。</div>
    </section>

    <aside class="right" aria-label="浮层侧栏">
      <div class="panel-h">
        <span class="ph-t">② 浮层侧栏 · 矩阵卡</span>
        <span class="ph-n" id="card-count">0 张</span>
        <button type="button" id="close-all" disabled>全部关闭</button>
      </div>
      <div class="cards" id="cards"></div>
    </aside>
  </main>
</div>

<script id="completeness-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  'use strict';

  var DATA = JSON.parse(document.getElementById('completeness-data').textContent);
  var NODE_BY_ID = {};
  var LAYER_BY_ID = {};
  var SLOT_BY_ID = {};
  var LEGEND = {};
  DATA.layers.forEach(function (layer) {
    LAYER_BY_ID[layer.id] = layer;
    layer.nodes.forEach(function (node) { NODE_BY_ID[node.id] = node; });
  });
  DATA.slots.forEach(function (slot) { SLOT_BY_ID[slot.id] = slot; });
  DATA.status_legend.forEach(function (item) { LEGEND[item.key] = item; });

  var GLYPH = { unbuilt: '▢', unverified: '◧', built: '■' };
  var RANK = { unbuilt: 0, unverified: 1, built: 2 };
  var ORDER = ['unbuilt', 'unverified', 'built'];
  var CYCLE = { unbuilt: 'unverified', unverified: 'built', built: 'unbuilt' };
  var state = { mode: 'answer', blank: {}, open: [] };
  DATA.slots.forEach(function (slot) { state.blank[slot.id] = 'unbuilt'; });

  function esc(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/[&<>"]/g, function (ch) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch];
      });
  }

  function slotStatus(id) {
    return state.mode === 'answer' ? SLOT_BY_ID[id].status : state.blank[id];
  }

  function nodeSlotIds(node) {
    if (node.slots && node.slots.length) { return node.slots; }
    if (node.derived_from_slots && node.derived_from_slots.length) { return node.derived_from_slots; }
    return [];
  }

  function nodeStatus(node) {
    var ids = nodeSlotIds(node);
    if (!ids.length) { return node.status; }
    var rank = 2;
    ids.forEach(function (id) { rank = Math.min(rank, RANK[slotStatus(id)]); });
    return ORDER[rank];
  }

  function capCount(node) {
    var cols = DATA.capability_columns[node.layer];
    return cols.filter(function (col) { return node.capabilities[col] === true; }).length;
  }

  function compute() {
    var perLayer = DATA.layers.map(function (layer) {
      var cols = DATA.capability_columns[layer.id];
      var colDone = {};
      cols.forEach(function (col) { colDone[col] = false; });
      var rowsPass = 0;
      layer.nodes.forEach(function (node) {
        var st = nodeStatus(node);
        if (st === 'built') { rowsPass += 1; }
        cols.forEach(function (col) {
          if (node.capabilities[col] === true && st === 'built') { colDone[col] = true; }
        });
      });
      var colsPass = cols.filter(function (col) { return colDone[col]; }).length;
      return {
        id: layer.id,
        rowsPass: rowsPass,
        rowsTotal: layer.nodes.length,
        colsPass: colsPass,
        colsTotal: cols.length,
        colDone: colDone
      };
    });
    var rowsPass = 0, rowsTotal = 0, colsPass = 0, colsTotal = 0;
    perLayer.forEach(function (p) {
      rowsPass += p.rowsPass; rowsTotal += p.rowsTotal;
      colsPass += p.colsPass; colsTotal += p.colsTotal;
    });
    var edges = DATA.edges.map(function (edge) {
      var pass = nodeStatus(NODE_BY_ID[edge.from]) === 'built' &&
                 nodeStatus(NODE_BY_ID[edge.to]) === 'built';
      return { edge: edge, pass: pass };
    });
    var edgesPass = edges.filter(function (item) { return item.pass; }).length;
    var slotsPass = DATA.slots.filter(function (slot) { return slotStatus(slot.id) === 'built'; }).length;
    var all = rowsPass === rowsTotal && colsPass === colsTotal && edgesPass === edges.length;
    return {
      perLayer: perLayer,
      rowsPass: rowsPass, rowsTotal: rowsTotal,
      colsPass: colsPass, colsTotal: colsTotal,
      edges: edges, edgesPass: edgesPass, edgesTotal: edges.length,
      slotsPass: slotsPass, slotsTotal: DATA.slots.length,
      all: all
    };
  }

  function setStat(id, label, value, total, pass, detail) {
    var el = document.getElementById(id);
    el.classList.toggle('pass', pass);
    el.classList.toggle('fail', !pass);
    el.title = detail;
    el.innerHTML = '<span class="k">' + esc(label) + '</span><b>' + value + '/' + total + '</b>' +
      '<span class="ok">' + (pass ? '✓' : '✗') + '</span>';
  }

  function renderStatus() {
    var result = compute();
    var rowDetail = result.perLayer.map(function (p) {
      return p.id + ' ' + p.rowsPass + '/' + p.rowsTotal;
    }).join(' · ');
    setStat('stat-rows', '行覆盖', result.rowsPass, result.rowsTotal,
      result.rowsPass === result.rowsTotal,
      'D38 ① 每层矩阵每行 ≥ 1 个 ■（节点不是空壳）：' + rowDetail);

    var colDetail = result.perLayer.map(function (p) {
      return p.id + ' ' + p.colsPass + '/' + p.colsTotal;
    }).join(' · ');
    setStat('stat-cols', '列覆盖', result.colsPass, result.colsTotal,
      result.colsPass === result.colsTotal,
      'D38 ② 每层矩阵每列 ≥ 1 个 ■（能力没有漏）：' + colDetail);

    var failed = result.edges.filter(function (item) { return !item.pass; })
      .map(function (item) { return item.edge.span + ' ' + item.edge.label; });
    setStat('stat-edges', '跨层边通', result.edgesPass, result.edgesTotal,
      result.edgesPass === result.edgesTotal,
      failed.length ? ('未通的边：' + failed.join(' / ')) : 'D38 ③ 跨层边都通，端到端证据 41099.5');

    document.getElementById('slot-count').textContent = result.slotsPass + '/' + result.slotsTotal;

    var stamp = document.getElementById('stamp');
    stamp.hidden = !result.all;
    stamp.title = result.all
      ? '行 / 列 / 边三条判据全绿 ⇒ 四层全通过，系统能力完备'
      : '三条判据还没全绿';

    var chain = document.getElementById('chain');
    if (chain) { chain.classList.toggle('pass', result.all); }
    return result;
  }

  function blockHTML(node) {
    var layer = LAYER_BY_ID[node.layer];
    var cols = DATA.capability_columns[node.layer];
    var st = nodeStatus(node);
    var slotText = node.slots.length ? node.slots.join('·') :
      (node.slot_ref ? node.slot_ref + '（映射）' : '—');
    var chips = '';
    if (node.slots.length) {
      chips = node.slots.map(function (id) {
        var ss = slotStatus(id);
        var live = state.mode === 'blank';
        var tip = id + ' ' + SLOT_BY_ID[id].name + ' · ' + LEGEND[ss].name +
          (live ? '（点击循环 ▢ → ◧ → ■）' : '（答案态只读）');
        return '<span class="slotpair"><span class="chip">' + esc(id) + '</span>' +
          '<button type="button" class="box ' + (live ? 'live' : 'ro') + '" data-slot="' + esc(id) + '"' +
          ' title="' + esc(tip) + '" aria-label="' + esc(id + ' 状态 ' + LEGEND[ss].name) + '">' +
          GLYPH[ss] + '</button></span>';
      }).join('');
    } else {
      var dtip = '无独立槽位 · ' + (node.derive_note || ('派生自 ' + nodeSlotIds(node).join('·')));
      chips = '<span class="slotpair">' +
        (node.slot_ref ? '<span class="chip ref">' + esc(node.slot_ref) + '</span>' : '') +
        '<span class="box ro" title="' + esc(dtip) + '" aria-label="派生状态">' + GLYPH[st] + '</span></span>';
    }
    var tip2 = node.name + ' · ' + layer.code + ' ' + layer.name + ' · 槽位 ' + slotText +
      ' · 三态 ' + LEGEND[st].name +
      (node.duration_min === null || node.duration_min === undefined ? '' : ' · 工期 ' + node.duration_min + ' 分钟') +
      ' · 能力 ' + capCount(node) + '/' + cols.length + ' 项';
    var open = state.open.indexOf(node.id) >= 0;
    return '<div class="block' + (open ? ' is-open' : '') + '" data-node="' + esc(node.id) + '"' +
      ' role="button" tabindex="0" aria-pressed="' + (open ? 'true' : 'false') + '"' +
      ' title="' + esc(tip2) + '">' +
      '<div class="slotline">' + chips + '</div>' +
      '<div class="bname">' + esc(node.block_name || node.name) + '</div>' +
      '<div class="bnote">' + esc(node.note || '') + '</div>' +
      '</div>';
  }

  function renderDiagram() {
    var host = document.getElementById('diagram');
    host.innerHTML = DATA.layers.map(function (layer) {
      var blocks = layer.nodes.map(blockHTML).join('');
      var base = layer.kind === 'foundation' ? ' lane-base' : '';
      return '<div class="lane' + base + '" data-layer="' + esc(layer.id) + '">' +
        '<div class="gutter"><b>' + esc(layer.code) + '</b><span>' + esc(layer.name) +
        '</span><small>' + esc(layer.tag) + '</small></div>' +
        '<div class="row" style="grid-template-columns:repeat(' + layer.nodes.length +
        ',minmax(0,1fr))">' + blocks + '</div>' +
        '</div>';
    }).join('');
  }

  function renderChain() {
    var host = document.getElementById('chain');
    var parts = DATA.end_to_end.chain.map(function (item) {
      return '<span class="ci">' + esc(item) + '</span>';
    });
    parts.push('<span class="res">' + esc(DATA.end_to_end.evidence) + '</span>');
    host.innerHTML = parts.join('<span class="arw">→</span>');
  }

  function cardHTML(node) {
    var layer = LAYER_BY_ID[node.layer];
    var cols = DATA.capability_columns[node.layer];
    var st = nodeStatus(node);
    var derivedOnly = !node.slots.length;
    var thead = cols.map(function (col) {
      return '<th>' + esc(col) + '</th>';
    }).join('');
    var cells = cols.map(function (col) {
      if (node.capabilities[col] !== true) { return '<td class="dash">—</td>'; }
      return '<td class="mark">' + GLYPH[st] + '</td>';
    }).join('');

    var slotRows = '';
    if (node.slots.length) {
      slotRows = node.slots.map(function (id) {
        var slot = SLOT_BY_ID[id];
        var ss = slotStatus(id);
        return '<div class="slotrow"><span class="mono">' + esc(id) + '</span>' +
          '<span>' + esc(slot.name) + '</span>' +
          '<span class="box">' + GLYPH[ss] + '</span>' +
          '<span class="dim">' + esc(slot.duration_min) + ' 分钟</span></div>';
      }).join('');
    } else {
      slotRows = '<div class="slotrow"><span class="mono">—</span>' +
        '<span class="dim">无独立槽位' +
        (node.slot_ref ? ' · 映射 ' + esc(node.slot_ref) : '') +
        (node.derive_note ? ' · ' + esc(node.derive_note) : '') + '</span></div>';
    }

    var pages = (node.pages || [node.page]).map(function (page) {
      return '<a class="pg" href="../' + esc(page) + '">' + esc(page) + '</a>';
    }).join(' ');

    var stNote = derivedOnly
      ? (node.derive_note || ('派生自 ' + nodeSlotIds(node).join(' · ')))
      : '槽位 ' + node.slots.join(' · ');

    return '<article class="card" data-card="' + esc(node.id) + '">' +
      '<header class="card-h">' +
      '<span class="card-layer">' + esc(layer.code) + ' · ' + esc(layer.name) + '</span>' +
      '<span class="card-tag">' + esc(layer.tag) + '</span>' +
      '<button type="button" class="card-x" data-close="' + esc(node.id) + '"' +
      ' aria-label="关闭 ' + esc(node.name) + ' 的卡片">×</button>' +
      '</header>' +
      '<h2 class="card-name">' + esc(node.name) + '</h2>' +
      '<div class="card-status"><span class="box big">' + GLYPH[st] + '</span>' +
      '<span>' + esc(LEGEND[st].name) + '</span>' +
      '<span class="cs-note">' + esc(stNote) + '</span></div>' +
      '<div class="card-slots">' + slotRows + '</div>' +
      '<div class="card-mtx"><div class="card-cap">该行能力（列 = 该层能力）　■ 提供且通过 · — 不提供</div>' +
      '<table class="mini"><thead><tr>' + thead + '</tr></thead>' +
      '<tbody><tr>' + cells + '</tr></tbody></table></div>' +
      '<div class="card-ev"><div class="card-cap">证据（实跑判据）</div>' +
      '<p class="ev" data-evidence="' + esc(node.id) + '">' + esc(node.evidence) + '</p></div>' +
      '<div class="card-pg">对应页 ' + pages + '</div>' +
      '</article>';
  }

  function renderCards() {
    var host = document.getElementById('cards');
    host.classList.toggle('is-empty', state.open.length === 0);
    if (!state.open.length) {
      host.innerHTML = '<div class="empty">点左侧任意块 → 在这里开一张「责任 × 证据」卡<br>' +
        '可同时开多张，卡片自动排布；每张卡右上角 × 单独关闭，顶部「全部关闭」一次清空。</div>';
    } else {
      host.innerHTML = state.open.map(function (id) {
        return cardHTML(NODE_BY_ID[id]);
      }).join('');
    }
    document.getElementById('card-count').textContent = state.open.length + ' 张';
    document.getElementById('close-all').disabled = state.open.length === 0;
  }

  function renderAll() {
    renderDiagram();
    renderCards();
    renderChain();
    return renderStatus();
  }

  function toggleCard(id) {
    if (!NODE_BY_ID[id]) { return; }
    var at = state.open.indexOf(id);
    if (at >= 0) { state.open.splice(at, 1); } else { state.open.push(id); }
    renderAll();
  }

  function cycleSlot(id) {
    if (state.mode !== 'blank' || !SLOT_BY_ID[id]) { return; }
    state.blank[id] = CYCLE[state.blank[id]];
    renderAll();
  }

  function setMode(mode) {
    if (mode !== 'answer' && mode !== 'blank') { return; }
    state.mode = mode;
    Array.prototype.forEach.call(document.querySelectorAll('.mode-btn'), function (btn) {
      var on = btn.getAttribute('data-mode') === mode;
      btn.classList.toggle('is-on', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    document.getElementById('mode-hint').textContent = mode === 'answer'
      ? '答案态（参考答案）：A0–A9 全 ■，方框只读；点块开卡。'
      : '空白态：点方框按 ▢ → ◧ → ■ 循环自己涂，顶部三条判据实时重算。';
    renderAll();
  }

  // ---------- 事件 ----------
  var diagram = document.getElementById('diagram');
  diagram.addEventListener('click', function (ev) {
    var box = ev.target.closest ? ev.target.closest('[data-slot]') : null;
    if (box) {
      if (state.mode === 'blank') {
        ev.preventDefault();
        cycleSlot(box.getAttribute('data-slot'));
        return;
      }
      // 答案态：方框只读，交给块去开/关卡
    }
    var block = ev.target.closest ? ev.target.closest('.block') : null;
    if (block) { toggleCard(block.getAttribute('data-node')); }
  });
  diagram.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Enter' && ev.key !== ' ') { return; }
    var block = ev.target.closest ? ev.target.closest('.block') : null;
    if (!block) { return; }
    ev.preventDefault();
    toggleCard(block.getAttribute('data-node'));
  });
  document.getElementById('cards').addEventListener('click', function (ev) {
    var close = ev.target.closest ? ev.target.closest('[data-close]') : null;
    if (close) { toggleCard(close.getAttribute('data-close')); }
  });
  document.getElementById('close-all').addEventListener('click', function () {
    state.open = [];
    renderAll();
  });
  Array.prototype.forEach.call(document.querySelectorAll('.mode-btn'), function (btn) {
    btn.addEventListener('click', function () { setMode(btn.getAttribute('data-mode')); });
  });

  // ---------- 静态文案 ----------
  document.getElementById('kicker').textContent = DATA.kicker;
  document.getElementById('title').textContent = DATA.title;
  document.getElementById('subtitle').textContent = DATA.subtitle;
  document.getElementById('lead').textContent = DATA.lead;
  document.title = DATA.title + ' · ' + DATA.subtitle;

  // ---------- 调试 / 验收用只读句柄（离线，无副作用） ----------
  window.__EXPLORER__ = {
    data: DATA,
    state: state,
    glyph: GLYPH,
    legend: LEGEND,
    statusOfSlot: slotStatus,
    statusOfNode: nodeStatus,
    nodeSlotIds: nodeSlotIds,
    compute: compute,
    openCard: function (id) {
      if (state.open.indexOf(id) < 0) { state.open.push(id); renderAll(); }
    },
    closeAll: function () { state.open = []; renderAll(); },
    setMode: setMode,
    cycleSlot: cycleSlot,
    toggleCard: toggleCard,
    render: renderAll
  };

  setMode('answer');
})();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------ 产物自检

def check_html(text: str) -> None:
    if DATA_TOKEN in text:
        fail("HTML 里还残留占位符 %s，JSON 没内联进去" % DATA_TOKEN)
    if "Noto Sans CJK SC" not in text:
        fail("CSS 没有指定中文字体 Noto Sans CJK SC")
    if "DejaVu Sans Mono" not in text:
        fail("证据行没有指定等宽字体 DejaVu Sans Mono")
    for bad in FORBIDDEN:
        if bad in text:
            fail("产物里出现禁用字符串 %r（不许用户名 / 绝对路径）" % bad)
    for bad in EXTERNAL:
        if bad in text:
            fail("产物里出现外部资源痕迹 %r（必须离线可用）" % bad)
    if text.count("<script") != 2:
        fail("应只有两段内联 script（数据 + 逻辑），实际 %d" % text.count("<script"))
    if "<style" not in text or "<style" in text.split("<body>")[-1]:
        fail("CSS 应内联在 head 里")
    # 数据能被重新解析，且与源文件一致
    marker = '<script id="completeness-data" type="application/json">'
    start = text.index(marker) + len(marker)
    end = text.index("</script>", start)
    try:
        embedded = json.loads(text[start:end].replace("<\\/", "</"))
    except json.JSONDecodeError as exc:
        fail("内联 JSON 解析失败：%s" % exc)
    return embedded


def build() -> None:
    print("「建成证明」交互原型：data.json → explorer.html（单文件 / 零依赖 / 离线）")
    data = load_data()
    validate_data(data)
    check_poster(data)
    check_flow(data)

    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    html = TEMPLATE.replace(DATA_TOKEN, payload)
    embedded = check_html(html)
    if embedded != data:
        fail("内联进 HTML 的 JSON 与 data.json 不一致")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")

    size = OUT_PATH.stat().st_size
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if size < 20000:
        fail("产物只有 %d 字节，像是模板没渲染" % size)
    ok("产物自检：无外链 / 无外字体 / 无图片 / 无用户名与绝对路径")
    ok("内联 JSON 与 data.json 逐字节等价（%d 字节数据）" % len(payload.encode("utf-8")))
    print("  输出：%s  %d 字节（%.1f KB）  sha256 %s"
          % (OUT_PATH.relative_to(REPO), size, size / 1024.0, digest[:16]))
    print("完成：一个文件即可离线双击打开，无需任何网络请求。")


def main() -> None:
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
