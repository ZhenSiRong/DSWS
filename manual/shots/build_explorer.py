#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_explorer.py —— 由单源 data.json 生成《建成证明》可交互原型 explorer.html。

在仓库根目录一条命令重跑：

    python3 manual/shots/build_explorer.py

它做五件事（依据 D38 / D39 / D40 / D41，D41 = 状态粒度下沉到「能力格」）：

1. **读单源**：`manual/completeness/data.json`（12 个节点 = 四层「责任 × 证据」矩阵的
   12 行；10 个槽位 A0–A9；13 项能力列；13 条链路边；D38 三条完备性判据；
   D41 能力格真源 = 每节点每能力的 `cell_state`）。
2. **反向核对**（防止两版漂移）：
   - 解析 `manual/completeness/poster.md` 的四张矩阵，逐行核对「节点名 / 能力列名 /
     `cell_state` 的 ■ 与 — / 证据文本」，要求与 data.json 一字一致；
   - 解析 `manual/flow.mmd`，核对槽位 A0–A9 的活动名与工期；
   - 核对槽位↔节点归属（每个槽位有且只有一个所属节点；节点拥有的槽位合计 10 个）、
     答案态自检（10/10 槽位、12/12 行、13/13 列、13/13 边、13■ + 31— 能力格）。
3. **内联**：把 data.json 原样内联进 HTML 模板的 `<script type="application/json">`，
   产物是**单文件、零依赖、离线可双击打开**的 explorer.html（不引 CDN / 外部字体 / 图片）。
4. **自检产物**：HTML 里必须出现 `Noto Sans CJK SC`；不许出现 URL / `<link` / `src=` /
   `@import` / `url(` / `fetch(` 等外部资源痕迹；不许出现用户名或绝对路径；
   必须含 D41 构件（能力格 `data-cell=`、卡片顶部只读派生徽章 `data-derived-card=`），
   且不得再出现卡片顶部节点控件（`data-tri=`）。
5. **DOM 链路自检**（D41）：把产物复制一份、注入一段验收脚本，用本机 `google-chrome
   --headless --dump-dom` 真跑一遍「空白态点一格 → 节点派生 ◧ → 结构图徽章派生 →
   行/列/边计数重算 → 其余格也点 ■ 才变节点 ■ → 再点另一张卡演示槽位同源 →
   重置 → 切回答案态恢复全 ■」，并做负向对照（— 格不可编辑、卡片徽章只读、
   结构图点块不改状态、边要两端节点都 ■、答案态点格无效）。断言结果写进 `<title>`，
   本脚本读回。找不到 Chrome 时跳过该步并打印警告（静态断言仍然生效）。

依赖：python3；DOM 自检需要本机 `google-chrome`（或 `chromium`），截图见
manual/review/explorer-shots/（由本机 playwright-core + 系统 Chrome 生成）。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
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
            "completeness_rules", "status_legend", "answer_selfcheck", "meta",
            "edit_model"]
    for key in need:
        if key not in data:
            fail("data.json 缺字段 %r" % key)

    # 编辑模型（D41）：唯一真源是「节点 × 能力」矩阵格，节点/槽位/结构图全部派生
    edit_model = data["edit_model"]
    if not isinstance(edit_model, dict):
        fail("edit_model 必须是对象")
    if edit_model.get("source") != "cell" or edit_model.get("unit") != "cell":
        fail("edit_model.source / unit 必须是 cell（D41：能力格为唯一真源）")
    if edit_model.get("direction") != "cell→node→slot→diagram":
        fail("edit_model.direction 应为 cell→node→slot→diagram")
    if edit_model.get("cycle") != list(STATUS):
        fail("edit_model.cycle 必须等于 status_order：%s" % (list(STATUS),))
    if edit_model.get("blank_initial") != "unbuilt":
        fail("edit_model.blank_initial 必须是 unbuilt（空白态全 ▢）")
    if edit_model.get("answer_initial") != "built" or edit_model.get("na") != "na":
        fail("edit_model.answer_initial 必须是 built、na 必须是 na（答案态：提供格 ■、不提供格 —）")
    if edit_model.get("answer_readonly") is not True:
        fail("edit_model.answer_readonly 必须是 true（答案态只读）")
    for key in ("cell_state_values", "node_derivation", "card_header",
                "slot_derivation", "diagram", "persistence"):
        if not edit_model.get(key):
            fail("edit_model 缺 D41 字段 %r" % key)
    if set(edit_model["cell_state_values"]) != {"built", "unverified", "unbuilt", "na"}:
        fail("edit_model.cell_state_values 必须覆盖 built/unverified/unbuilt/na 四值")
    if "全部 ■" not in edit_model["node_derivation"]:
        fail("edit_model.node_derivation 必须写清「全部 ■ ⇒ 节点 ■」派生规则")

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
            if not any(node["capabilities"].values()):
                fail("节点 %s 至少要提供一项能力（否则节点状态无法派生）" % nid)

            # D41：每节点每能力都有初始态 cell_state；答案态 提供→built、不提供→na
            cell_state = node.get("cell_state")
            if not isinstance(cell_state, dict):
                fail("节点 %s 缺 cell_state（D41：每节点每能力要有初始态）" % nid)
            if set(cell_state) != set(cols):
                fail("节点 %s 的 cell_state 键必须正好是该层列名 %s" % (nid, cols))
            for col in cols:
                want = "built" if node["capabilities"][col] else "na"
                if cell_state[col] != want:
                    fail("节点 %s 的 cell_state[%r] 应为 %r（答案态：提供→built / 不提供→na），实际 %r"
                         % (nid, col, want, cell_state[col]))

            pages = node.get("pages") or [node["page"]]
            if node["page"] not in pages:
                fail("节点 %s 的 page 必须在 pages 里" % nid)
            for page in pages:
                if not re.fullmatch(r"page-0[0-9]\.md", page):
                    fail("节点 %s 的 pages 里有非法页名 %r" % (nid, page))
                if not (MANUAL / page).exists():
                    fail("节点 %s 的 %s 不存在" % (nid, page))

            node_slots = node.get("slots") or []
            mapped_slots = node.get("mapped_slots") or []
            if node_slots:
                if len(node_slots) == 1:
                    if node["slot"] != node_slots[0]:
                        fail("节点 %s 单槽位时 slot 必须等于该槽位" % nid)
                elif node["slot"] is not None:
                    fail("节点 %s 多槽位时 slot 应为 null（槽位见 slots）" % nid)
                if mapped_slots:
                    fail("节点 %s 拥有槽位，不能再写 mapped_slots" % nid)
                if node.get("slot_ref") or node.get("map_note"):
                    fail("节点 %s 有独立槽位，不该再写 slot_ref / map_note" % nid)
                for sid in node_slots:
                    if sid not in SLOT_IDS:
                        fail("节点 %s 引用了非法槽位 %r" % (nid, sid))
                    if data_slot_owner(data, sid) != nid:
                        fail("槽位 %s 的 node 不是 %s" % (sid, nid))
                want = sum(index_slots(data)[sid]["duration_min"] for sid in node_slots)
                if node.get("duration_min") != want:
                    fail("节点 %s 的 duration_min 应为槽位工期之和 %d" % (nid, want))
            else:
                # D40：无独立槽位的行也有自己的节点状态（在卡片上编辑）；
                # mapped_slots / slot_ref / map_note 只是结构图位置映射提示。
                if not mapped_slots:
                    fail("节点 %s 无独立槽位，必须用 mapped_slots 标出结构图映射" % nid)
                for sid in mapped_slots:
                    if sid not in SLOT_IDS:
                        fail("节点 %s 的 mapped_slots 含非法槽位 %r" % (nid, sid))
                if node.get("duration_min") is not None:
                    fail("节点 %s 无槽位，duration_min 必须为 null" % nid)
                if not node.get("slot_ref") or not node.get("map_note"):
                    fail("节点 %s 无独立槽位，必须写 slot_ref 与 map_note" % nid)

    if count != 12:
        fail("节点总数应为 12 行（四层 2/3/5/2），实际 %d" % count)

    # 槽位归属完整性（D40 派生链 node → slot）：10 个槽位各归属且仅归属一个节点
    owned: dict = {}
    slotless = 0
    for node in nodes.values():
        if not node.get("slots"):
            slotless += 1
            continue
        for sid in node["slots"]:
            if sid in owned:
                fail("槽位 %s 被节点 %s 与 %s 重复拥有" % (sid, owned[sid], node["id"]))
            owned[sid] = node["id"]
    if sorted(owned) != SLOT_IDS:
        fail("12 个节点拥有的槽位应正好覆盖 A0–A9，实际 %s" % sorted(owned))
    if slotless != 3:
        fail("应恰有 3 行无独立槽位（L1 两行 + MySQL），实际 %d" % slotless)
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
    cells_total = sum(len(data["capability_columns"][layer["id"]]) * len(layer["nodes"])
                      for layer in layers)
    provided = sum(1 for node in nodes.values() for cid, given in node["capabilities"].items() if given)
    answer_cells = {"built": 0, "na": 0}
    for node in nodes.values():
        for state in node["cell_state"].values():
            if state not in answer_cells:
                fail("cell_state 只允许 built / na，节点 %s 出现 %r" % (node["id"], state))
            answer_cells[state] += 1
    selfcheck = data["answer_selfcheck"]
    meta = data["meta"]
    if rows != 12 or cols != 13 or cells_total != 44 or provided != 13:
        fail("答案态自检应为 12 行 / 13 列 / 44 格 / 13 个提供格，实际 %d/%d/%d/%d"
             % (rows, cols, cells_total, provided))
    if answer_cells["built"] != 13 or answer_cells["na"] != 31:
        fail("答案态能力格应为 13 个 ■ + 31 个 —，实际 %d + %d"
             % (answer_cells["built"], answer_cells["na"]))
    if selfcheck.get("rows") != "12/12" or selfcheck.get("columns") != "13/13":
        fail("answer_selfcheck 的 rows/columns 口径不对")
    if selfcheck.get("cells") != "13/44" or selfcheck.get("total_cells") != 44:
        fail("answer_selfcheck 的能力格口径应为 13/44")
    if meta.get("cell_count") != 44 or meta.get("provided_cell_count") != 13 \
            or meta.get("na_cell_count") != 31:
        fail("meta 的能力格统计应为 44 / 13 / 31")
    # 答案态节点状态必须能由能力格派生为 ■（全 ■ 派生）
    for node in nodes.values():
        for col in data["capability_columns"][node["layer"]]:
            if node["capabilities"][col]:
                if node["cell_state"][col] != "built":
                    fail("答案态节点 %s 的提供格 %r 不是 built" % (node["id"], col))
    if len(slots_by_id) != 10 or len(data["edges"]) != meta["edge_count"]:
        fail("槽位/边数量与 meta 不符")
    all_evidence = [n["evidence"] for n in nodes.values()]
    for needle in EVIDENCE_MUST:
        if not any(needle in ev for ev in all_evidence):
            fail("证据里缺少点名判据 %r" % needle)

    ok("data.json 结构：12 节点 / 10 槽位 / 13 能力列 / 44 能力格 / 13 条边 / 3 条判据")
    ok("D41 编辑模型：能力格为唯一真源 · 节点/槽位/结构图全部派生 · 卡片顶部只读徽章")
    ok("答案态自检：A0–A9 10/10 · 行 12/12 · 列 13/13 · 能力格 13■ + 31—")


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
                want = "built" if mark == "■" else "na"
                if node["cell_state"][col] != want:
                    fail("poster.md %s「%s」%s 的 ■/— 与 data.json 的 cell_state 不一致"
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
.mode-row{display:flex;align-items:center;gap:9px;}
.modes{display:flex;border:2px solid var(--ink);border-radius:6px;overflow:hidden;}
.mode-btn{border:0;border-right:1.5px solid var(--ink);background:#fff;color:var(--ink);
          font:inherit;font-size:13.5px;font-weight:800;padding:6px 15px;cursor:pointer;
          letter-spacing:.5px;}
.mode-btn:last-child{border-right:0;}
.mode-btn:hover{background:#eeeeee;}
.mode-btn.is-on{background:var(--ink);color:#fff;}
.reset-btn{border:2px solid var(--ink);border-radius:6px;background:#fff;color:var(--ink);
           font:inherit;font-size:12.5px;font-weight:800;padding:6px 12px;cursor:pointer;
           letter-spacing:.5px;}
.reset-btn:hover:not(:disabled){background:var(--ink);color:#fff;}
.reset-btn:disabled{opacity:.35;cursor:default;}
.mode-hint{font-size:11.5px;color:var(--mute);max-width:430px;text-align:right;line-height:1.45;}

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
.lh-ro{font-size:10.5px;color:#444;border:1px solid #999;border-radius:3px;
       padding:0 5px;background:#fff;white-space:nowrap;}
.lh-edit{font-size:10.5px;color:#333;border:1px dashed #999;border-radius:3px;
         padding:1px 6px;background:#fff;white-space:nowrap;}
.lh-edit[hidden]{display:none;}
.legend{display:flex;align-items:center;gap:11px;margin-left:auto;flex-wrap:wrap;
        font-size:11px;color:var(--ink2);}
.legend .lg{display:inline-flex;align-items:center;gap:4px;}
.legend .box{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;font-size:15px;
             line-height:1;cursor:default;}
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
.chip{font-size:10.5px;line-height:16px;padding:0 5px;background:#ededed;
      border:1px solid #888;border-radius:3px;color:#222;white-space:nowrap;}
.chip.ref{background:#fff;border-style:dashed;color:#666;}
.blk-status{margin-left:auto;font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;
            font-size:19px;line-height:1;color:var(--ink);cursor:inherit;}
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
.card-status{display:flex;align-items:center;gap:7px;font-size:12px;flex-wrap:wrap;
             border-top:1px solid #dddddd;border-bottom:1px solid #dddddd;padding:5px 0;}
.card-status .derived-badge{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;
                  font-size:22px;line-height:1;border:1.4px solid var(--ink);border-radius:5px;
                  background:#fff;color:var(--ink);padding:1px 6px;cursor:default;}
.card-status .tri-name{font-weight:800;font-size:12px;}
.card-status .ro-tag{font-size:9.5px;color:#444;border:1px solid #999;border-radius:3px;
                     padding:0 4px;background:#fff;white-space:nowrap;}
.card-status .derive{font-size:10px;color:#333;border:1px dashed #aaa;border-radius:3px;
                     padding:0 4px;white-space:nowrap;
                     font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;}
.card-status .cs-note{color:#666;font-size:10.5px;margin-left:auto;text-align:right;}
.card-slots{display:flex;flex-direction:column;gap:3px;font-size:11px;}
.slotrow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.slotrow .box{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;font-size:14px;
              line-height:1;color:var(--ink);}
.slotrow .dim{color:#666;}
.card-cap{font-size:10px;color:#666;letter-spacing:.2px;margin-bottom:3px;}
.card-mtx table.mini{width:100%;border-collapse:collapse;table-layout:fixed;}
.mini th,.mini td{border:1px solid #333;padding:2px 3px;font-size:9.5px;
                  text-align:center;line-height:1.15;}
.mini thead th{background:#e9e9e9;font-weight:800;overflow-wrap:anywhere;}
.mini td.cellwrap{padding:0;}
.cell{display:block;width:100%;border:0;background:#fff;color:var(--ink);
      font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;font-size:15px;
      line-height:1;height:24px;padding:0;cursor:pointer;}
.cell:hover:not(:disabled){background:#e6e6e6;}
.cell:focus-visible{outline:2px solid var(--ink);outline-offset:-2px;background:#fff;}
.cell.is-locked{cursor:default;background:#fbfbfb;color:#333;}
.mini td.dash{color:#888;font-size:11.5px;padding:0 2px;}
.card-ev .ev{margin:0;font-size:10.4px;line-height:1.5;background:#f7f7f7;
             border-left:3px solid var(--ink);padding:5px 7px;overflow-wrap:anywhere;}
.card-pg{font-size:10.5px;color:#444;display:flex;gap:6px;align-items:center;
         flex-wrap:wrap;border-top:1px dashed #cccccc;padding-top:6px;}
a.pg{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--ink);font-size:10px;}
a.pg:hover{background:var(--ink);color:#fff;}

/* ---------- 提示条 ---------- */
.toast{position:fixed;left:50%;top:14px;transform:translateX(-50%) translateY(-8px);
       background:var(--ink);color:#fff;font-size:12.5px;font-weight:700;letter-spacing:.3px;
       padding:8px 16px;border-radius:6px;box-shadow:0 4px 14px rgba(0,0,0,.25);
       opacity:0;pointer-events:none;transition:opacity .16s ease,transform .16s ease;z-index:50;}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0);}
.toast[hidden]{display:none;}

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
      <div class="mode-row">
        <div class="modes" role="group" aria-label="模式切换">
          <button type="button" class="mode-btn" data-mode="answer" aria-pressed="true">答案态</button>
          <button type="button" class="mode-btn" data-mode="blank" aria-pressed="false">空白态</button>
        </div>
        <button type="button" class="reset-btn" id="reset" disabled
                title="答案态无需重置；先切到空白态">重置</button>
      </div>
      <div class="mode-hint" id="mode-hint"></div>
    </div>
  </header>

  <section class="statusbar" aria-label="完备性状态条">
    <div class="stat" id="stat-rows" title=""></div>
    <div class="stat" id="stat-cols" title=""></div>
    <div class="stat" id="stat-edges" title=""></div>
    <div class="stat muted" title="十个槽位里 ■ 的个数（槽位状态由所属节点派生，节点状态再由本行能力格派生）"><span class="k">槽位 ■</span><b id="slot-count">—</b></div>
    <div class="stamp" id="stamp" hidden>建成证明 ✓</div>
  </section>

  <main class="split">
    <section class="left">
      <div class="left-head">
        <span class="lh-title">① 全局结构图</span>
        <span class="lh-note">L1 / L2 / L3 + L0 地基条 · 块等大（面积不编码任何维度）</span>
        <span class="lh-ro">结构图只读 · 徽章由能力格 → 节点派生</span>
        <span class="lh-edit" id="edit-note" hidden>编辑态 · 点卡片能力格循环 ▢→◧→■ · 进度存在本机浏览器</span>
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
      <div class="diag-cap">悬停块看工期 / 能力数；点块在右侧开卡，再点同一块关闭该卡；结构图只读，徽章由本行能力格 → 节点派生；状态编辑入口是右侧卡片里的能力格（仅空白态）。</div>
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
<div class="toast" id="toast" role="status" aria-live="polite" hidden></div>

<script id="completeness-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  'use strict';

  var DATA = JSON.parse(document.getElementById('completeness-data').textContent);
  var NODE_BY_ID = {};
  var LAYER_BY_ID = {};
  var SLOT_BY_ID = {};
  var LEGEND = {};
  var NODES = [];
  DATA.layers.forEach(function (layer) {
    LAYER_BY_ID[layer.id] = layer;
    layer.nodes.forEach(function (node) {
      NODE_BY_ID[node.id] = node;
      NODES.push(node);
    });
  });
  DATA.slots.forEach(function (slot) { SLOT_BY_ID[slot.id] = slot; });
  DATA.status_legend.forEach(function (item) { LEGEND[item.key] = item; });
  var STATUS_SET = {};
  DATA.status_order.forEach(function (key) { STATUS_SET[key] = true; });

  var GLYPH = { unbuilt: '▢', unverified: '◧', built: '■' };
  var NA = 'na';
  var NA_GLYPH = '—';
  var ORDER = (DATA.edit_model && DATA.edit_model.cycle)
    ? DATA.edit_model.cycle.slice() : DATA.status_order.slice();
  var CYCLE = {};
  ORDER.forEach(function (key, index) {
    CYCLE[key] = ORDER[(index + 1) % ORDER.length];
  });
  var BLANK_INITIAL = (DATA.edit_model && DATA.edit_model.blank_initial) || 'unbuilt';

  // 编辑态进度存本机浏览器；不可用（隐私模式 / 某些 file:// 策略）时降级为不持久化。
  var STORAGE_KEY = 'completeness-explorer/cells-v1';
  var STORAGE_OK = (function () {
    try {
      window.localStorage.setItem('__explorer_probe__', '1');
      window.localStorage.removeItem('__explorer_probe__');
      return true;
    } catch (err) { return false; }
  })();

  // 唯一可变状态（D41）：mode（答案态 / 空白态）、cells（格级真源）、open（打开的卡片）
  var state = { mode: 'answer', cells: {}, open: [] };

  function esc(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/[&<>"]/g, function (ch) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch];
      });
  }

  function layerCols(node) { return DATA.capability_columns[node.layer]; }

  function isProvided(node, col) { return node.capabilities[col] === true; }

  function editableCols(node) {
    return layerCols(node).filter(function (col) { return node.capabilities[col] === true; });
  }

  function blankCellsMap() {
    var map = {};
    NODES.forEach(function (node) {
      var cells = {};
      editableCols(node).forEach(function (col) { cells[col] = BLANK_INITIAL; });
      map[node.id] = cells;
    });
    return map;
  }

  function resetCellMap() { state.cells = blankCellsMap(); }

  function readSaved() {
    if (!STORAGE_OK) { return null; }
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) { return null; }
      var obj = JSON.parse(raw);
      if (!obj || obj.v !== 2 || obj.mode !== 'blank' || !obj.cells) { return null; }
      var cells = blankCellsMap();
      NODES.forEach(function (node) {
        var saved = obj.cells[node.id];
        if (!saved || typeof saved !== 'object') { return; }
        editableCols(node).forEach(function (col) {
          var value = saved[col];
          if (STATUS_SET[value]) { cells[node.id][col] = value; }
        });
      });
      return cells;
    } catch (err) { return null; }
  }

  function saveSaved() {
    if (!STORAGE_OK) { return; }
    try {
      if (state.mode !== 'blank') {
        window.localStorage.removeItem(STORAGE_KEY);
        return;
      }
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        v: 2, mode: 'blank', cells: state.cells, ts: Date.now()
      }));
    } catch (err) { /* 存不了就只在本页内存里编辑 */ }
  }

  function discardSaved() {
    if (!STORAGE_OK) { return; }
    try { window.localStorage.removeItem(STORAGE_KEY); } catch (err) {}
  }

  // ---------- 派生链（D41）：能力格 → 节点 → 槽位 → 结构图 ----------
  function cellStatus(node, col) {
    if (!node || !isProvided(node, col)) { return NA; }
    if (state.mode === 'answer') { return node.cell_state[col]; }
    var nodeCells = state.cells[node.id];
    var value = nodeCells ? nodeCells[col] : null;
    return STATUS_SET[value] ? value : BLANK_INITIAL;
  }

  function cellCounts(node) {
    var counts = { editable: 0, built: 0, unverified: 0, unbuilt: 0, na: 0 };
    layerCols(node).forEach(function (col) {
      var status = cellStatus(node, col);
      if (status === NA) { counts.na += 1; return; }
      counts.editable += 1;
      counts[status] += 1;
    });
    return counts;
  }

  // 节点状态 = 本行可编辑格派生：全 ▢ ⇒ ▢；全 ■ ⇒ ■；其余 ⇒ ◧（— 格不参与）
  function nodeStatus(node) {
    var counts = cellCounts(node);
    if (!counts.editable) { return BLANK_INITIAL; }
    if (counts.unbuilt === counts.editable) { return 'unbuilt'; }
    if (counts.built === counts.editable) { return 'built'; }
    return 'unverified';
  }

  function deriveLine(node) {
    var counts = cellCounts(node);
    return '由本卡 ' + counts.editable + ' 项能力派生：' +
      counts.built + '■ ' + counts.unverified + '◧ ' + counts.unbuilt + '▢';
  }

  function slotStatus(slotId) {
    var slot = SLOT_BY_ID[slotId];
    if (!slot) { return BLANK_INITIAL; }
    return nodeStatus(NODE_BY_ID[slot.node]);
  }

  function capCount(node) { return editableCols(node).length; }

  function compute() {
    var perLayer = DATA.layers.map(function (layer) {
      var cols = DATA.capability_columns[layer.id];
      var colDone = {};
      cols.forEach(function (col) { colDone[col] = false; });
      var rowsPass = 0;
      layer.nodes.forEach(function (node) {
        if (nodeStatus(node) === 'built') { rowsPass += 1; }
        cols.forEach(function (col) {
          if (cellStatus(node, col) === 'built') { colDone[col] = true; }
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
    perLayer.forEach(function (part) {
      rowsPass += part.rowsPass; rowsTotal += part.rowsTotal;
      colsPass += part.colsPass; colsTotal += part.colsTotal;
    });
    var edges = DATA.edges.map(function (edge) {
      var pass = nodeStatus(NODE_BY_ID[edge.from]) === 'built' &&
                 nodeStatus(NODE_BY_ID[edge.to]) === 'built';
      return { edge: edge, pass: pass };
    });
    var edgesPass = edges.filter(function (item) { return item.pass; }).length;
    var slotsPass = DATA.slots.filter(function (slot) {
      return slotStatus(slot.id) === 'built';
    }).length;
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
    var rowDetail = result.perLayer.map(function (part) {
      return part.id + ' ' + part.rowsPass + '/' + part.rowsTotal;
    }).join(' · ');
    setStat('stat-rows', '行覆盖', result.rowsPass, result.rowsTotal,
      result.rowsPass === result.rowsTotal,
      'D38 ① 每层矩阵每行 ≥ 1 个 ■（节点不是空壳）：' + rowDetail +
      '（节点状态由本行能力格派生：全部可编辑格 ■ 才算节点 ■）');

    var colDetail = result.perLayer.map(function (part) {
      return part.id + ' ' + part.colsPass + '/' + part.colsTotal;
    }).join(' · ');
    setStat('stat-cols', '列覆盖', result.colsPass, result.colsTotal,
      result.colsPass === result.colsTotal,
      'D38 ② 每层矩阵每列 ≥ 1 个 ■（能力没有漏，按能力格计）：' + colDetail);

    var failed = result.edges.filter(function (item) { return !item.pass; })
      .map(function (item) { return item.edge.span + ' ' + item.edge.label; });
    setStat('stat-edges', '跨层边通', result.edgesPass, result.edgesTotal,
      result.edgesPass === result.edgesTotal,
      failed.length ? ('未通的边（两端节点都 ■ 才算通）：' + failed.join(' / '))
        : 'D38 ③ 跨层边都通，端到端证据 41099.5');

    document.getElementById('slot-count').textContent =
      result.slotsPass + '/' + result.slotsTotal;

    var stamp = document.getElementById('stamp');
    stamp.hidden = !result.all;
    stamp.title = result.all
      ? '行 / 列 / 边三条判据全绿 ⇒ 四层全通过，系统能力完备'
      : '三条判据还没全绿';

    var chain = document.getElementById('chain');
    if (chain) { chain.classList.toggle('pass', result.all); }

    return result;
  }

  function slotChipsHTML(node) {
    if (node.slots && node.slots.length) {
      return node.slots.map(function (slotId) {
        var slot = SLOT_BY_ID[slotId];
        var derived = slotStatus(slotId);
        var tip = '槽位 ' + slotId + ' ' + slot.name + ' · 派生状态 ' +
          GLYPH[derived] + ' ' + LEGEND[derived].name +
          '（由所属节点「' + node.name + '」派生；节点状态再由本行能力格派生，结构图只读）';
        return '<span class="chip slot" data-slot="' + esc(slotId) + '" data-status="' + esc(derived) +
          '" title="' + esc(tip) + '">' + esc(slotId) + '</span>';
      }).join('');
    }
    var refs = node.mapped_slots || [];
    var label = node.slot_ref || (refs.length ? refs.join('·') : '—');
    var refTip = '映射槽位 ' + label + '（仅示意位置；状态由本卡能力格派生）';
    return '<span class="chip ref" data-mapped="' + esc(refs.join(' ')) +
      '" title="' + esc(refTip) + '">' + esc(label) + '</span>';
  }

  function blockHTML(node) {
    var layer = LAYER_BY_ID[node.layer];
    var cols = layerCols(node);
    var st = nodeStatus(node);
    var open = state.open.indexOf(node.id) >= 0;
    var badgeTip = '结构图只读 · 节点「' + node.name + '」状态 ' + GLYPH[st] + ' ' +
      LEGEND[st].name + '（由本行能力格 → 节点派生，点块只开卡）';
    var tip = node.name + ' · ' + layer.code + ' ' + layer.name +
      ' · 状态 ' + GLYPH[st] + ' ' + LEGEND[st].name +
      (node.duration_min === null || node.duration_min === undefined
        ? '' : ' · 工期 ' + node.duration_min + ' 分钟') +
      ' · 能力 ' + capCount(node) + '/' + cols.length + ' 项';
    return '<div class="block' + (open ? ' is-open' : '') + '" data-node="' + esc(node.id) + '"' +
      ' role="button" tabindex="0" aria-pressed="' + (open ? 'true' : 'false') + '"' +
      ' title="' + esc(tip) + '">' +
      '<div class="slotline">' + slotChipsHTML(node) +
      '<span class="blk-status" data-derived-node="' + esc(node.id) + '" data-status="' + esc(st) +
      '" title="' + esc(badgeTip) + '">' + GLYPH[st] + '</span>' +
      '</div>' +
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

  function cellHTML(node, col, editable) {
    if (!isProvided(node, col)) {
      return '<td class="dash" data-na="' + esc(col) + '" title="该节点不提供「' +
        esc(col) + '」：— 格不可编辑，也不参与节点派生">' + NA_GLYPH + '</td>';
    }
    var cell = cellStatus(node, col);
    var next = CYCLE[cell];
    var tip = editable
      ? ('当前：' + GLYPH[cell] + ' ' + LEGEND[cell].name + ' · 点一下切下一态 → ' +
         GLYPH[next] + ' ' + LEGEND[next].name + '（循环 ▢ → ◧ → ■ → ▢）')
      : ('答案态只读：' + GLYPH[cell] + ' ' + LEGEND[cell].name +
         ' · 切到「空白态」后点格可编辑');
    var locked = editable ? '' : ' is-locked';
    var disabled = editable ? '' : ' disabled aria-disabled="true"';
    return '<td class="cellwrap"><button type="button" class="cell' + locked + '"' +
      ' data-cell="' + esc(node.id) + '" data-col="' + esc(col) + '"' +
      ' data-status="' + esc(cell) + '"' + disabled +
      ' title="' + esc(tip) + '"' +
      ' aria-label="' + esc('能力格「' + col + '」：' + LEGEND[cell].name +
        (editable ? '，点一下切下一态' : '，答案态只读')) + '">' +
      GLYPH[cell] + '</button></td>';
  }

  function cardHTML(node) {
    var layer = LAYER_BY_ID[node.layer];
    var cols = layerCols(node);
    var st = nodeStatus(node);
    var counts = cellCounts(node);
    var editable = state.mode === 'blank';
    var derived = deriveLine(node);
    var thead = cols.map(function (col) {
      var cls = isProvided(node, col) ? '' : ' class="th-na"';
      return '<th' + cls + '>' + esc(col) + '</th>';
    }).join('');
    var cells = cols.map(function (col) { return cellHTML(node, col, editable); }).join('');

    var slotRows = '';
    if (node.slots && node.slots.length) {
      slotRows = node.slots.map(function (slotId) {
        var slot = SLOT_BY_ID[slotId];
        var ss = slotStatus(slotId);
        return '<div class="slotrow" data-slot="' + esc(slotId) + '" data-status="' + esc(ss) + '"' +
          ' title="槽位 ' + esc(slotId) + ' 状态由所属节点「' + esc(node.name) + '」派生；' +
          '节点状态由本行能力格派生">' +
          '<span class="mono">' + esc(slotId) + '</span>' +
          '<span>' + esc(slot.name) + '</span>' +
          '<span class="box" data-status="' + esc(ss) + '">' + GLYPH[ss] + '</span>' +
          '<span class="dim">' + esc(slot.duration_min) + ' 分钟</span></div>';
      }).join('');
    } else {
      var mapText = node.map_note ||
        (node.mapped_slots && node.mapped_slots.length ? '映射 ' + node.mapped_slots.join('·') : '无独立槽位');
      slotRows = '<div class="slotrow"><span class="mono">—</span>' +
        '<span class="dim">无独立槽位 · ' + esc(mapText) + '</span></div>';
    }

    var pages = (node.pages || [node.page]).map(function (page) {
      return '<a class="pg" href="../' + esc(page) + '">' + esc(page) + '</a>';
    }).join(' ');

    var stNote = (node.slots && node.slots.length)
      ? ('槽位 ' + node.slots.join(' · '))
      : ('映射 ' + (node.slot_ref || '') + ' · 能力格决定节点状态');

    var badgeTitle = derived + '（只读派生徽章：在下方能力格上点，节点状态自动重算）';
    var capNote = editable
      ? '本行能力格（点格循环 ▢ → ◧ → ■ → ▢ · — 不提供、不可点）'
      : '本行能力格（答案态只读 · ■ 提供且判据通过 · — 不提供）';

    return '<article class="card" data-card="' + esc(node.id) + '">' +
      '<header class="card-h">' +
      '<span class="card-layer">' + esc(layer.code) + ' · ' + esc(layer.name) + '</span>' +
      '<span class="card-tag">' + esc(layer.tag) + '</span>' +
      '<button type="button" class="card-x" data-close="' + esc(node.id) + '"' +
      ' aria-label="关闭 ' + esc(node.name) + ' 的卡片">×</button>' +
      '</header>' +
      '<h2 class="card-name">' + esc(node.name) + '</h2>' +
      '<div class="card-status">' +
      '<span class="derived-badge" data-derived-card="' + esc(node.id) + '"' +
      ' data-status="' + esc(st) + '" title="' + esc(badgeTitle) + '"' +
      ' aria-label="' + esc(node.name + ' 的派生状态：' + LEGEND[st].name +
        '；' + derived) + '">' + GLYPH[st] + '</span>' +
      '<span class="tri-name">' + esc(LEGEND[st].name) + '</span>' +
      '<span class="ro-tag">只读派生</span>' +
      '<span class="derive" title="' + esc(derived) + '">派生 ' +
      counts.built + '■ ' + counts.unverified + '◧ ' + counts.unbuilt + '▢</span>' +
      '<span class="cs-note">' + esc(stNote) + '</span>' +
      '</div>' +
      '<div class="card-slots">' + slotRows + '</div>' +
      '<div class="card-mtx"><div class="card-cap">' + esc(capNote) + '</div>' +
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
        '可同时开多张；空白态下点卡片里的能力格按 ▢ → ◧ → ■ → ▢ 循环，' +
        '节点状态由本卡能力格派生，结构图与顶部判定实时重算。</div>';
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

  function cycleCell(nodeId, col) {
    if (state.mode !== 'blank') { return false; }
    var node = NODE_BY_ID[nodeId];
    if (!node || !isProvided(node, col)) { return false; }
    var current = cellStatus(node, col);
    state.cells[nodeId][col] = CYCLE[current] || BLANK_INITIAL;
    saveSaved();
    renderAll();
    var btn = document.querySelector('.card[data-card="' + nodeId + '"] .cell[data-col="' + col + '"]');
    if (btn && !btn.disabled) { btn.focus(); }
    return true;
  }

  function resetEdits() {
    if (state.mode !== 'blank') { return; }
    resetCellMap();
    saveSaved();
    renderAll();
    showToast('已重置：所有能力格恢复 ▢（节点随之 ▢），本机手改进度已清空。');
  }

  function showToast(msg) {
    var el = document.getElementById('toast');
    if (!el) { return; }
    el.textContent = msg;
    el.hidden = false;
    el.classList.add('show');
    if (showToast.timer) { clearTimeout(showToast.timer); }
    showToast.timer = setTimeout(function () {
      el.classList.remove('show');
      el.hidden = true;
    }, 3400);
  }

  function applyModeUI() {
    var mode = state.mode;
    Array.prototype.forEach.call(document.querySelectorAll('.mode-btn'), function (btn) {
      var on = btn.getAttribute('data-mode') === mode;
      btn.classList.toggle('is-on', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    var hint = document.getElementById('mode-hint');
    if (mode === 'answer') {
      hint.textContent = '答案态（参考答案）：13 个能力格全 ■ → 12 个节点全 ■、只读；' +
        '点左侧块开卡对照证据，卡片顶部徽章是派生结果。';
    } else {
      hint.textContent = '空白态（编辑态）：点卡片里的能力格，按 ▢ → ◧ → ■ → ▢ 循环；' +
        '卡片顶部徽章只读、由本卡能力格派生；结构图徽章与顶部三条判据实时派生。' +
        (STORAGE_OK ? '进度存在本机浏览器（localStorage），可点「重置」清空。'
                    : '本机浏览器不允许存进度，刷新会丢；点「重置」可清空。');
    }
    var reset = document.getElementById('reset');
    reset.disabled = mode !== 'blank';
    reset.title = mode === 'blank'
      ? '把所有能力格恢复 ▢（清空本机手改进度）'
      : '答案态无需重置；先切到空白态';
    var note = document.getElementById('edit-note');
    if (note) {
      note.hidden = mode !== 'blank';
      note.textContent = '编辑态 · 点卡片能力格循环 ▢→◧→■ · ' +
        (STORAGE_OK ? '进度存在本机浏览器' : '本机不存进度');
    }
  }

  function switchMode(mode) {
    if (mode !== 'answer' && mode !== 'blank') { return; }
    if (mode === state.mode) { return; }
    var hadEdits = false;
    NODES.forEach(function (node) {
      editableCols(node).forEach(function (col) {
        if (state.cells[node.id] && state.cells[node.id][col] !== BLANK_INITIAL) { hadEdits = true; }
      });
    });
    state.mode = mode;
    resetCellMap();
    if (mode === 'blank') { saveSaved(); } else { discardSaved(); }
    applyModeUI();
    renderAll();
    if (mode === 'answer') {
      showToast(hadEdits
        ? '已切回答案态：手动改的能力格已丢弃，恢复全 ■。'
        : '已切回答案态：13 个能力格全 ■、只读预览。');
    }
  }

  // ---------- 事件 ----------
  var diagram = document.getElementById('diagram');
  diagram.addEventListener('click', function (ev) {
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

  var cardsHost = document.getElementById('cards');
  cardsHost.addEventListener('click', function (ev) {
    var target = ev.target;
    var cell = target.closest ? target.closest('[data-cell]') : null;
    if (cell) { cycleCell(cell.getAttribute('data-cell'), cell.getAttribute('data-col')); return; }
    var close = target.closest ? target.closest('[data-close]') : null;
    if (close) { toggleCard(close.getAttribute('data-close')); }
  });

  document.getElementById('close-all').addEventListener('click', function () {
    state.open = [];
    renderAll();
  });
  document.getElementById('reset').addEventListener('click', resetEdits);
  Array.prototype.forEach.call(document.querySelectorAll('.mode-btn'), function (btn) {
    btn.addEventListener('click', function () { switchMode(btn.getAttribute('data-mode')); });
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
    storageKey: STORAGE_KEY,
    storageOk: STORAGE_OK,
    blankInitial: BLANK_INITIAL,
    editableCols: function (idOrNode) {
      var node = (typeof idOrNode === 'string') ? NODE_BY_ID[idOrNode] : idOrNode;
      return node ? editableCols(node) : [];
    },
    statusOfCell: function (nodeId, col) {
      var node = NODE_BY_ID[nodeId];
      return node ? cellStatus(node, col) : NA;
    },
    countsOfNode: function (nodeId) {
      var node = NODE_BY_ID[nodeId];
      return node ? cellCounts(node) : null;
    },
    deriveLine: function (nodeId) {
      var node = NODE_BY_ID[nodeId];
      return node ? deriveLine(node) : '';
    },
    statusOfSlot: slotStatus,
    statusOfNode: function (idOrNode) {
      var node = (typeof idOrNode === 'string') ? NODE_BY_ID[idOrNode] : idOrNode;
      return node ? nodeStatus(node) : BLANK_INITIAL;
    },
    compute: compute,
    openCard: function (id) {
      if (state.open.indexOf(id) < 0) { state.open.push(id); renderAll(); }
    },
    closeAll: function () { state.open = []; renderAll(); },
    setMode: switchMode,
    cycleCell: cycleCell,
    resetEdits: resetEdits,
    toggleCard: toggleCard,
    render: renderAll,
    savedRaw: function () {
      try { return window.localStorage.getItem(STORAGE_KEY); } catch (err) { return null; }
    }
  };

  // ---------- 启动：有空白态进度就恢复，否则答案态 ----------
  var savedCells = readSaved();
  if (savedCells) {
    state.mode = 'blank';
    state.cells = savedCells;
  } else {
    state.mode = 'answer';
    resetCellMap();
  }
  applyModeUI();
  renderAll();
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
    # D41 链路构件：能力格编辑 / 卡片顶部只读派生徽章 / 结构图只读派生 / 重置 / 本机进度
    for needle in ("data-cell=", "data-derived-card=", "data-derived-node=",
                   "点一下切下一态", "由本卡", "cycleCell", 'id="reset"',
                   "localStorage", "本机浏览器"):
        if needle not in text:
            fail("产物缺少 D41 链路构件 %r" % needle)
    if "data-tri=" in text:
        fail("产物里仍有卡片顶部节点控件 data-tri（D41 要求移除，改为只读派生徽章）")
    if re.search(r"<button[^>]*data-derived-card=", text):
        fail("卡片顶部派生徽章仍是按钮（D41 要求只读）")
    if 'class="cell' not in text or "cellwrap" not in text:
        fail("产物缺少能力格按钮（D41：每节点每提供能力一格可点）")
    if re.search(r"<button[^>]*data-slot=", text):
        fail("结构图槽位仍被渲染成可点按钮（要求结构图只读、状态由能力格 → 节点派生）")
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


# ------------------------------------------------------------------ DOM 链路自检（D40）

# 把产物复制一份、注入这段验收脚本，用 headless Chrome 真跑一遍交互链路：
# 卡片点状态徽章 → 左侧结构图徽章派生 → 顶部判定重算 → 重置 → 切回答案态恢复全 ■。
# 断言结果写进 document.title，build 从 `--dump-dom` 的输出里读回。
DOM_CHECK_JS = r"""
<script id="explorer-dom-selfcheck">
(function () {
  'use strict';
  var fails = [];
  var info = {};
  function check(cond, msg) { if (!cond) { fails.push(msg); } }
  function q(sel) { return document.querySelector(sel); }
  function qa(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  function text(sel) { var el = q(sel); return el ? el.textContent.trim() : '<missing ' + sel + '>'; }
  function api() { return window.__EXPLORER__; }

  function blockState(nodeId) {
    var block = q('#diagram .block[data-node="' + nodeId + '"]');
    if (!block) { return null; }
    var badge = block.querySelector('.blk-status');
    return {
      status: badge ? badge.getAttribute('data-status') : null,
      glyph: badge ? badge.textContent.trim() : '',
      chips: Array.prototype.map.call(block.querySelectorAll('.chip[data-slot]'), function (chip) {
        return chip.getAttribute('data-slot') + '=' + chip.getAttribute('data-status');
      })
    };
  }
  function cardBadge(nodeId) {
    var card = q('.card[data-card="' + nodeId + '"]');
    if (!card) { return null; }
    var badge = card.querySelector('[data-derived-card]');
    var derive = card.querySelector('.derive');
    var ro = card.querySelector('.ro-tag');
    return {
      tag: badge ? badge.tagName : null,
      status: badge ? badge.getAttribute('data-status') : null,
      glyph: badge ? badge.textContent.trim() : '',
      title: badge ? (badge.getAttribute('title') || '') : '',
      deriveText: derive ? derive.textContent.trim() : '',
      roText: ro ? ro.textContent.trim() : '',
      slots: Array.prototype.map.call(card.querySelectorAll('.slotrow[data-slot]'), function (row) {
        var box = row.querySelector('.box');
        return row.getAttribute('data-slot') + '=' + row.getAttribute('data-status') + ':' + (box ? box.textContent.trim() : '');
      }),
      cells: Array.prototype.map.call(card.querySelectorAll('.cell[data-cell]'), function (btn) {
        return btn.getAttribute('data-col') + '=' + btn.getAttribute('data-status') + ':' + btn.textContent.trim();
      })
    };
  }
  function cellState(nodeId, col) {
    var btn = q('.card[data-card="' + nodeId + '"] .cell[data-col="' + col + '"]');
    if (!btn) { return null; }
    return {
      status: btn.getAttribute('data-status'),
      glyph: btn.textContent.trim(),
      disabled: btn.disabled,
      title: btn.getAttribute('title') || ''
    };
  }
  function stats() {
    return {
      rows: text('#stat-rows b'), cols: text('#stat-cols b'),
      edges: text('#stat-edges b'), slots: text('#slot-count'),
      stamp: !q('#stamp').hidden,
      blockCount: qa('#diagram .block').length,
      diagramButtons: qa('#diagram button').length,
      diagramTri: qa('#diagram [data-tri]').length,
      cardTri: qa('.card [data-tri]').length,
      cards: qa('.card').length,
      badges: qa('.card [data-derived-card]').length,
      cellButtons: qa('.card .cell[data-cell]').length,
      dashCells: qa('.card td.dash').length
    };
  }
  function counts(label) {
    var s = stats();
    return label + '：行 ' + s.rows + ' · 列 ' + s.cols + ' · 边 ' + s.edges + ' · 槽位 ' + s.slots;
  }
  function expectCounts(label, rows, cols, edges, slots) {
    var s = stats();
    check(s.rows === rows && s.cols === cols && s.edges === edges && s.slots === slots,
      label + ' 应为 行 ' + rows + ' · 列 ' + cols + ' · 边 ' + edges + ' · 槽位 ' + slots +
      '，实际 ' + [s.rows, s.cols, s.edges, s.slots].join(' · '));
  }
  function clickBlock(nodeId) {
    var block = q('#diagram .block[data-node="' + nodeId + '"]');
    if (!block) { fails.push('找不到结构块 ' + nodeId); return; }
    block.click();
  }
  function clickCell(nodeId, col) {
    var btn = q('.card[data-card="' + nodeId + '"] .cell[data-col="' + col + '"]');
    if (!btn) { fails.push('找不到能力格 ' + nodeId + ' · ' + col); return; }
    btn.click();
  }
  function cellsSnapshot() { return JSON.stringify(api().state.cells); }
  function allBlockGlyphs(expected, label) {
    qa('#diagram .blk-status').forEach(function (badge) {
      check(badge.getAttribute('data-status') === expected && badge.textContent.trim() === api().glyph[expected],
        label + '：结构图徽章应统一 ' + api().glyph[expected] + '，实际 ' +
        badge.getAttribute('data-derived-node') + '=' + badge.textContent.trim());
    });
  }
  function run() {
    var ref = api();
    check(!!ref, '缺少 __EXPLORER__ 验收句柄');
    if (!ref) { return; }

    // ===== 1) 答案态：13 个能力格全 ■、只读、派生徽章只读、计数全绿 =====
    check(ref.state.mode === 'answer', '初始应为答案态');
    var s = stats();
    check(s.blockCount === 12, '结构图应有 12 个块，实际 ' + s.blockCount);
    check(s.diagramButtons === 0, '结构图里不应有可点按钮（只读），实际 ' + s.diagramButtons);
    check(s.diagramTri === 0 && s.cardTri === 0, 'D41 要求移除卡片顶部节点控件，[data-tri] 应为 0');
    expectCounts('答案态计数', '12/12', '13/13', '13/13', '10/10');
    check(s.stamp === true, '答案态应显示建成证明印章');
    allBlockGlyphs('built', '答案态');

    qa('#diagram .block').map(function (block) {
      return block.getAttribute('data-node');
    }).forEach(clickBlock);
    s = stats();
    check(s.cards === 12, '点 12 个块应开 12 张卡，实际 ' + s.cards);
    check(s.badges === 12, '每张卡应有一个只读派生徽章，实际 ' + s.badges);
    check(s.cellButtons === 13, '答案态应有 13 个能力格按钮（可编辑格），实际 ' + s.cellButtons);
    check(s.dashCells === 31, '— 格应有 31 个，实际 ' + s.dashCells);
    qa('.card [data-derived-card]').forEach(function (badge) {
      check(badge.tagName !== 'BUTTON', '卡片顶部派生徽章不应是按钮（只读），实际 ' + badge.tagName);
      check(badge.getAttribute('data-status') === 'built' && badge.textContent.trim() === '■',
        '答案态卡片派生徽章应 ■：' + badge.getAttribute('data-derived-card'));
    });
    var l1 = cardBadge('l1-interact');
    check(l1 && l1.status === 'built' && l1.glyph === '■', '答案态 l1-interact 派生徽章应 ■');
    check(l1 && l1.title.indexOf('由本卡 2 项能力派生：2■ 0◧ 0▢') === 0,
      '派生徽章 tooltip 应写「由本卡 2 项能力派生：2■ 0◧ 0▢」，实际 ' + (l1 ? l1.title : ''));
    check(l1 && l1.roText === '只读派生', '卡片应标注「只读派生」，实际 ' + (l1 ? l1.roText : ''));
    check(l1 && l1.cells.join(' ') === '接收提问=built:■ 返回答案=built:■',
      '答案态 l1-interact 能力格组合不对：' + (l1 ? l1.cells.join(' / ') : ''));
    qa('.card .cell[data-cell]').forEach(function (btn) {
      check(btn.disabled === true, '答案态能力格应只读（disabled）：' + btn.getAttribute('data-col'));
      check(btn.getAttribute('data-status') === 'built' && btn.textContent.trim() === '■',
        '答案态能力格应 ■：' + btn.getAttribute('data-col'));
      check((btn.getAttribute('title') || '').indexOf('答案态只读') >= 0,
        '答案态能力格 tooltip 应写明只读：' + (btn.getAttribute('title') || ''));
    });

    // 负向对照：答案态点格 / 点徽章都不改真源
    var before = cellsSnapshot();
    clickCell('l1-interact', '接收提问');
    check(cellsSnapshot() === before, '负向对照：答案态点能力格不应改变格状态');
    check(ref.statusOfCell('l1-interact', '接收提问') === 'built', '答案态点格后仍是 ■');

    // ===== 2) 空白态：全 ▢、可编辑 =====
    q('.mode-btn[data-mode="blank"]').click();
    s = stats();
    check(ref.state.mode === 'blank', '应切到空白态');
    expectCounts('空白态初始计数', '0/12', '0/13', '0/13', '0/10');
    check(s.stamp === false, '空白态印章应隐藏');
    allBlockGlyphs('unbuilt', '空白态');
    check(q('#reset').disabled === false, '空白态「重置」应可用');
    check(q('#edit-note') && !q('#edit-note').hidden, '空白态应显示编辑态说明');
    check(q('#edit-note') && q('#edit-note').textContent.indexOf('本机浏览器') >= 0,
      '编辑态说明应注明「进度存在本机浏览器」');
    check(q('#mode-hint').textContent.indexOf('能力格') >= 0, '空白态提示应说明点能力格编辑');
    l1 = cardBadge('l1-interact');
    check(l1 && l1.status === 'unbuilt' && l1.glyph === '▢', '空白态 l1-interact 派生徽章应 ▢');
    check(l1 && l1.title.indexOf('由本卡 2 项能力派生：0■ 0◧ 2▢') === 0,
      '空白态派生 tooltip 应为「由本卡 2 项能力派生：0■ 0◧ 2▢」，实际 ' + (l1 ? l1.title : ''));
    check(l1 && l1.cells.join(' ') === '接收提问=unbuilt:▢ 返回答案=unbuilt:▢',
      '空白态 l1-interact 能力格应全 ▢：' + (l1 ? l1.cells.join(' / ') : ''));
    var enabled = qa('.card .cell[data-cell]').filter(function (btn) { return !btn.disabled; });
    check(enabled.length === 13, '空白态 13 个可编辑格都可点，实际 ' + enabled.length);
    var tip = cellState('l1-interact', '接收提问').title;
    check(tip.indexOf('点一下切下一态') >= 0, '空白态能力格 tooltip 应写「点一下切下一态」，实际 ' + tip);
    check(tip.indexOf('▢') >= 0 && tip.indexOf('◧') >= 0, '空白态能力格 tooltip 应写当前态与下一态：' + tip);
    if (ref.storageOk) {
      var savedBlank = ref.savedRaw();
      check(typeof savedBlank === 'string' && savedBlank.indexOf('"mode":"blank"') >= 0,
        '切到空白态应写入 localStorage 进度');
    }

    // ===== 3) 负向对照：— 格 / 卡片徽章 / 结构图都改不了状态 =====
    var dash = q('.card[data-card="l1-interact"] td.dash');
    check(!!dash, '应能找到 — 不提供格（不可编辑）');
    var beforeNeg = cellsSnapshot();
    if (dash) { dash.click(); }
    check(cellsSnapshot() === beforeNeg, '负向对照：点 — 格不应改变任何格状态');
    check(ref.statusOfCell('l1-interact', '访问数据') === 'na', '— 格状态应恒为 na');
    check(ref.cycleCell('l1-interact', '访问数据') === false, '负向对照：直接调用也不能编辑 — 格');
    check(ref.cycleCell('l1-interact', '不存在的列') === false, '负向对照：未知能力列应被拒绝');
    var badgeEl = q('.card[data-card="l1-interact"] [data-derived-card]');
    check(badgeEl && badgeEl.tagName === 'SPAN', '卡片顶部派生徽章应为 span（只读）');
    if (badgeEl) { badgeEl.click(); }
    check(cellsSnapshot() === beforeNeg, '负向对照：点卡片顶部派生徽章不应改变格状态');
    check(ref.statusOfNode('l1-interact') === 'unbuilt', '负向对照后 l1-interact 仍是 ▢');
    expectCounts('负向对照后计数', '0/12', '0/13', '0/13', '0/10');

    // 结构图只读：点块只开卡，不改格状态
    ref.closeAll();
    clickBlock('l1-interact');
    check(qa('.card').length === 1, '点结构块应开 1 张卡');
    var beforeBlock = cellsSnapshot();
    clickBlock('A4');
    check(cellsSnapshot() === beforeBlock, '负向对照：点结构图块不应改变格状态');
    ref.closeAll();

    // ===== 4) 主链路：改一格 → 节点 ◧ → 结构图徽章派生 → 计数变化 → 其余格 ■ 才变节点 ■ =====
    clickBlock('l1-interact');
    clickCell('l1-interact', '接收提问');          // ▢ → ◧
    var c1 = cellState('l1-interact', '接收提问');
    var c2 = cellState('l1-interact', '返回答案');
    check(c1 && c1.status === 'unverified' && c1.glyph === '◧', '第 1 格点一下应 ◧');
    check(c2 && c2.status === 'unbuilt' && c2.glyph === '▢', '第 2 格应仍 ▢');
    check(ref.statusOfNode('l1-interact') === 'unverified', '一格 ◧ 时节点应派生 ◧');
    var blk = blockState('l1-interact');
    check(blk && blk.status === 'unverified' && blk.glyph === '◧', '结构图徽章应派生 ◧');
    l1 = cardBadge('l1-interact');
    check(l1 && l1.title.indexOf('由本卡 2 项能力派生：0■ 1◧ 1▢') === 0,
      '派生 tooltip 应为 0■ 1◧ 1▢，实际 ' + (l1 ? l1.title : ''));
    expectCounts('一格 ◧ 时', '0/12', '0/13', '0/13', '0/10');

    clickCell('l1-interact', '接收提问');          // ◧ → ■
    check(cellState('l1-interact', '接收提问').status === 'built', '第 1 格再点应 ■');
    check(ref.statusOfNode('l1-interact') === 'unverified', '只有一格 ■、另一格 ▢ 时节点仍 ◧');
    blk = blockState('l1-interact');
    check(blk && blk.status === 'unverified', '结构图徽章仍 ◧（节点未全 ■）');
    expectCounts('一格 ■ 一格 ▢ 时', '0/12', '1/13', '0/13', '0/10');
    l1 = cardBadge('l1-interact');
    check(l1 && l1.title.indexOf('由本卡 2 项能力派生：1■ 0◧ 1▢') === 0,
      '派生 tooltip 应为 1■ 0◧ 1▢，实际 ' + (l1 ? l1.title : ''));

    clickCell('l1-interact', '返回答案');          // ▢ → ◧
    check(ref.statusOfNode('l1-interact') === 'unverified', '两格 ■◧ 混合时节点仍 ◧');
    expectCounts('两格 ■◧ 时', '0/12', '1/13', '0/13', '0/10');

    clickCell('l1-interact', '返回答案');          // ◧ → ■ → 节点 ■
    check(cellState('l1-interact', '返回答案').status === 'built', '第 2 格再点应 ■');
    check(ref.statusOfNode('l1-interact') === 'built', '两格全 ■ 时节点应 ■');
    blk = blockState('l1-interact');
    check(blk && blk.status === 'built' && blk.glyph === '■', '结构图徽章应派生 ■');
    l1 = cardBadge('l1-interact');
    check(l1 && l1.title.indexOf('由本卡 2 项能力派生：2■ 0◧ 0▢') === 0,
      '派生 tooltip 应为 2■ 0◧ 0▢，实际 ' + (l1 ? l1.title : ''));
    expectCounts('两格都 ■ 后', '1/12', '2/13', '0/13', '0/10');
    check(ref.statusOfSlot('A0') === 'unbuilt', 'l1-interact 无独立槽位，槽位计数不受它影响');
    if (ref.storageOk) {
      var savedEdit = ref.savedRaw();
      check(typeof savedEdit === 'string' && savedEdit.indexOf('l1-interact') >= 0 &&
        savedEdit.indexOf('"built"') >= 0, '空白态编辑应写入 localStorage');
    }

    // ===== 5) 槽位同源（A1·A2）与边计数 =====
    clickBlock('data');
    clickCell('data', '可查询数据');               // ▢ → ◧
    check(ref.statusOfNode('data') === 'unverified', 'data 一格 ◧ 时节点应 ◧');
    check(ref.statusOfSlot('A1') === 'unverified' && ref.statusOfSlot('A2') === 'unverified',
      'data 节点 ◧ 时槽位 A1·A2 应同步 ◧');
    expectCounts('data ◧ 时', '1/12', '2/13', '0/13', '0/10');

    clickCell('data', '可查询数据');               // ◧ → ■
    check(ref.statusOfNode('data') === 'built', 'data 唯一能力格 ■ 后节点应 ■');
    check(ref.statusOfSlot('A1') === 'built' && ref.statusOfSlot('A2') === 'built',
      'data 节点 ■ 时槽位 A1·A2 应同源同步 ■');
    var dataBadge = cardBadge('data');
    check(dataBadge && dataBadge.slots.indexOf('A1=built:■') >= 0 &&
      dataBadge.slots.indexOf('A2=built:■') >= 0,
      'data 卡片槽位行应 A1·A2 都 ■：' + (dataBadge ? dataBadge.slots.join(' / ') : ''));
    blk = blockState('data');
    check(blk && blk.status === 'built', '结构图 data 块应 ■');
    check(blk && blk.chips.indexOf('A1=built') >= 0 && blk.chips.indexOf('A2=built') >= 0,
      '结构图 data 块槽位 chip 应同步 A1·A2 ■');
    expectCounts('data ■ 后', '2/12', '3/13', '0/13', '2/10');
    check(ref.compute().edges.filter(function (e) { return e.edge.id === 'e13'; })[0].pass === false,
      'data→mysql 边在 mysql 未 ■ 时不应通（负向对照）');

    clickBlock('mysql');
    clickCell('mysql', '数据存储与查询');          // ▢ → ◧
    check(ref.statusOfNode('mysql') === 'unverified', 'mysql 一格 ◧ 时节点应 ◧');
    expectCounts('mysql ◧ 时', '2/12', '3/13', '0/13', '2/10');
    check(ref.compute().edges.filter(function (e) { return e.edge.id === 'e13'; })[0].pass === false,
      '边要两端节点都 ■：mysql ◧ 时 data→mysql 仍不通');

    clickCell('mysql', '数据存储与查询');          // ◧ → ■
    check(ref.statusOfNode('mysql') === 'built', 'mysql 唯一能力格 ■ 后节点应 ■');
    expectCounts('mysql ■ 后', '3/12', '4/13', '1/13', '2/10');
    var passes = ref.compute().edges.filter(function (e) { return e.pass; })
      .map(function (e) { return e.edge.id; });
    check(passes.indexOf('e13') >= 0, '两端节点都 ■ 后 data→mysql 边应通，实际通的边 ' + passes.join(','));
    check(passes.indexOf('e03') < 0, '负向对照：backend 未 ■，backend→mysql 边不应通');
    var mysqlBlk = blockState('mysql');
    check(mysqlBlk && mysqlBlk.status === 'built', '结构图 mysql 块应由节点派生 ■');

    // ===== 6) 重置：全部回 ▢ =====
    q('#reset').click();
    expectCounts('重置后计数', '0/12', '0/13', '0/13', '0/10');
    allBlockGlyphs('unbuilt', '重置后');
    check(ref.statusOfCell('data', '可查询数据') === 'unbuilt', '重置后 data 能力格应 ▢');
    check(ref.statusOfCell('l1-interact', '接收提问') === 'unbuilt', '重置后 l1-interact 能力格应 ▢');
    check(ref.state.cells.data['可查询数据'] === 'unbuilt', '重置后格级真源应全 unbuilt');

    // ===== 7) 再编辑 → 切回答案态：恢复全 ■、丢弃手改 =====
    clickCell('data', '可查询数据');
    check(ref.statusOfNode('data') === 'unverified', '重置后应能再次编辑');
    q('.mode-btn[data-mode="answer"]').click();
    expectCounts('切回答案态计数', '12/12', '13/13', '13/13', '10/10');
    allBlockGlyphs('built', '切回答案态');
    check(ref.state.mode === 'answer', '应切回答案态');
    check(sStatsDisabled() === 0, '答案态应没有可点的能力格');
    check(q('#toast') && !q('#toast').hidden && q('#toast').textContent.indexOf('丢弃') >= 0,
      '切回答案态应提示「丢弃手改」');
    if (ref.storageOk) {
      check(ref.savedRaw() === null, '切回答案态应清掉 localStorage 进度');
    }
    var l1Answer = cardBadge('l1-interact');
    check(l1Answer && l1Answer.title.indexOf('由本卡 2 项能力派生：2■ 0◧ 0▢') === 0,
      '切回答案态 l1-interact 派生 tooltip 应 2■ 0◧ 0▢');

    info = {
      rows: text('#stat-rows b'), cols: text('#stat-cols b'),
      edges: text('#stat-edges b'), slots: text('#slot-count'),
      blocks: stats().blockCount, cards: stats().cards,
      cells: qa('.card .cell[data-cell]').length
    };
  }
  function sStatsDisabled() {
    return qa('.card .cell[data-cell]').filter(function (btn) { return !btn.disabled; }).length;
  }
  function finish() {
    var pass = fails.length === 0;
    var marker = 'DOM_SELF' + 'CHECK_';
    document.title = marker + (pass ? 'PASS' : 'FAIL') +
      (pass ? '' : ' ' + fails.slice(0, 8).join(' || '));
    var pre = document.createElement('pre');
    pre.id = 'explorer-dom-selfcheck';
    pre.textContent = (pass ? 'PASS' : 'FAIL') + '\n' + fails.join('\n') + '\n' + JSON.stringify(info);
    document.body.appendChild(pre);
  }
  function start() {
    try { run(); } catch (err) { fails.push('异常：' + (err && err.message ? err.message : err)); }
    finish();
  }
  if (document.readyState === 'complete') { start(); }
  else { window.addEventListener('load', start); }
})();
</script>
"""


def find_chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return ""


def check_dom(html: str) -> None:
    """在 headless Chrome 里真跑一遍「卡片编辑 → 结构图派生 → 判定重算」链路。"""
    chrome = find_chrome()
    if not chrome:
        print("  ⚠ 未找到 google-chrome / chromium，跳过 DOM 链路自检（静态断言仍然生效）")
        return
    with tempfile.TemporaryDirectory(prefix="explorer-domcheck-") as tmp:
        work = Path(tmp)
        page = work / "explorer-selfcheck.html"
        page.write_text(html.replace("</body>", DOM_CHECK_JS + "\n</body>"), encoding="utf-8")
        cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
               "--disable-dev-shm-usage", "--virtual-time-budget=5000",
               "--user-data-dir=%s" % (work / "profile"), "--dump-dom", page.as_uri()]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                              encoding="utf-8", errors="replace")
        dom = proc.stdout or ""
        if ("DOM_SELFCHECK_PASS" in dom
                and '<pre id="explorer-dom-selfcheck">PASS' in dom):
            ok("DOM 链路自检：点一格 → 节点 ◧ → 结构图徽章派生 → 行列边重算 → 其余格 ■ 才变节点 ■ → 重置/答案态 全通过（含负向对照）")
            return
        match = re.search(r"<title>(DOM_SELFCHECK_FAIL[^<]*)</title>", dom)
        detail = match.group(1) if match else ((proc.stderr or dom or "")[-2000:])
        fail("DOM 链路自检未通过：%s" % detail)


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
    ok("D41 产物构件：能力格可点 · 卡片顶部只读派生徽章 · 结构图只读派生 · 重置按钮 · 本机进度说明")
    ok("内联 JSON 与 data.json 逐字节等价（%d 字节数据）" % len(payload.encode("utf-8")))
    print("  输出：%s  %d 字节（%.1f KB）  sha256 %s"
          % (OUT_PATH.relative_to(REPO), size, size / 1024.0, digest[:16]))
    check_dom(html)
    print("完成：一个文件即可离线双击打开，无需任何网络请求。")


def main() -> None:
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
