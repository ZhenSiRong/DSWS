#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_explorer.py —— 由 v2 单源 data.json 生成《建成证明》可交互原型 explorer.html。

在仓库根目录一条命令重跑：

    python3 manual/shots/build_explorer.py            # 生成 explorer.html + 静态 / DOM 自检
    python3 manual/shots/build_explorer.py --shots    # 另出 3 张验证截图（v2-01/02/03）

依据 `humen-desicions/09-ablation-course.md` 的 **D39 / D40 / D41 / D42 / D43**：
D39 中分视图（左材料总览、右可多开卡片）；D40 编辑入口只在卡片上、总览只读派生；
D41 状态粒度下沉到「一格一状态」；D42 行=交付物、格=检验点（1–3 个、命令+期望输出）；
D43 交互页改吃 v2 单源、行状态由检验点派生、保留一条只做位置导航的 AON 流水条。

它做五件事：

1. **读单源**：只读 `manual/completeness/v2/data.json`（12 件交付物 × 24 个检验点；
   每件 `id/name/kind/location/pages/checkpoints[{criterion,command,expected_output,
   evidence_source}]/depends_on`），不再依赖 v1 的 `completeness/data.json` / `poster.md`。
2. **数据一致性自检**：schema / 12 件 / 每件 1–3 个检验点 / 合计 24 / id 唯一 /
   依赖存在且无环 / 页签文件存在 / 每个检验点的 `evidence_source` 页与行号可解析且在
   对应页行数内 / 答案态算术（12/12 行、24/24 检验点、端到端链 ✓）。
3. **flow.mmd 交叉核对**：解析 A0–A9 活动名与 FS 紧前关系；核对 12 件交付物 → A0–A9
   的位置映射全覆盖且按编号单调；逐条核对 `depends_on` 的交付物在 AON 图里是祖先活动；
   导航只取位置，**不参与勾选**。
4. **内联**：data.json 原样内联进单文件 HTML（`<script type="application/json">`），
   AON 导航条由生成器按 flow.mmd 静态渲染；产物零外部请求、可离线双击打开。
5. **自检产物 + DOM 链路真跑**（无头 Chrome）：
   - 静态：无外链 / 无外字体 / 无图片 / 无 `fetch` / 无用户名与绝对路径；数据内 URL
     只允许 `127.0.0.1` 命令文本；只读徽章不是按钮；内联 JSON 与 data.json 等价。
   - DOM：答案态 12/12 · 24/24 · 端到端 ✓ → 点一格 ▢→◧ 后行变 ◧、计数不变 →
     同件其余格 ■ 后行 ■、计数变化 → 端到端链 2/2 ✓ 但 12 行不全不出印章 →
     重置回 ▢ → 切回答案态恢复全 ■、丢弃手改；并做负向对照（点行徽章 / 卡顶徽章 /
     答案态点格 / 未知 id / AON 导航只高亮不改状态）。

依赖：python3；DOM 自检与截图需要本机 `google-chrome`（或 `chromium`）。截图用
`--force-device-scale-factor=2`：v2-01 / v2-03 为 1600×1050 视口（→ 3200×2100），
v2-02 加高到 1600×1320（→ 3200×2640）以便 3 张卡都完整入镜。
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
MANUAL = REPO / "manual"
DATA_PATH = MANUAL / "completeness" / "v2" / "data.json"
FLOW_MMD = MANUAL / "flow.mmd"
OUT_PATH = MANUAL / "completeness" / "explorer.html"
SHOT_DIR = MANUAL / "review" / "explorer-shots"

SHOT_W, SHOT_H = 1600, 1050                     # 默认截图视口（CSS px）；--shots 各张可单独指定高
SHOT_SCALE = 2                                  # → 3200×2100 PNG（v2-02 更高以容纳 3 张卡）

STATUS = ("unbuilt", "unverified", "built")
GLYPH = {"unbuilt": "▢", "unverified": "◧", "built": "■"}

# flow.mmd 的 A0–A9 活动 → 12 件交付物的「流水线位置」（D43：只做位置导航，不参与勾选）。
# 说明：v2 data.json 没有 AON 字段，所以位置映射放在生成器里，并用 flow.mmd 的
# 紧前关系 + 每件 depends_on 反查校验（见 check_flow）。
ACTIVITY_OF_ARTIFACT = {
    "env": "A0",
    "mysql-container": "A1",
    "dw-tables": "A2",
    "dw-data": "A2",
    "service": "A3",
    "api-query": "A4",
    "keywords-fn": "A5",
    "sql-fn": "A6",
    "exec-chain": "A7",
    "stream-endpoint": "A8",
    "nginx-page": "A9",
    "e2e-chain": "A9",
}
MAIN_LINE = ["A0", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
BRANCH_LINE = ["A0", "A1", "A2", "A7"]          # 数据支线（A2 → A7 汇入主干）
EXPECTED_FLOW_EDGES = [
    ("A0", "A1"), ("A0", "A3"), ("A1", "A2"), ("A2", "A7"),
    ("A3", "A4"), ("A4", "A5"), ("A5", "A6"), ("A6", "A7"),
    ("A7", "A8"), ("A8", "A9"),
]
EXPECTED_ACTIVITIES = ["A%d" % i for i in range(10)]
E2E_ID = "e2e-chain"                            # 第 12 件「端到端链路」：端到端链判据
STORAGE_KEY = "completeness-v2/checks-v1"       # 本机手改进度（D43：键换 v2）

DATA_TOKEN = "__DATA_JSON__"
AON_TOKEN = "__AON_NAV__"

# 产物里不许出现的字符串（本机用户名 / 绝对路径 / 旧实现痕迹）
FORBIDDEN = ["/home/", "/Users/", "/tmp/", Path.home().name, "root@", ".dsh"]
# 静态壳里不许出现的外部资源痕迹（内联数据里的命令 URL 单独按 host 校验）
EXTERNAL_SHELL = ["http://", "https://", "//cdn", "<link", "@import", "url(",
                  "src=", "fetch(", "XMLHttpRequest", "<iframe", "<img",
                  "onclick=", "<input"]
URL_RE = re.compile(r"https?://([^/\"'\s]+)")
EVIDENCE_REF = re.compile(r"page-(\d{2})\.md:(\d+)(?:[-,–](\d+))?")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
AON_NODE_RE = re.compile(r'A(\d+)\["<b>([^<]+)</b>')
AON_EDGE_RE = re.compile(r"A(\d+)\s*-->\|FS\|\s*A(\d+)")

# （文件名, 说明, 视口宽, 视口高, 截图前的状态注入 JS）
SHOTS = [
    ("v2-01-initial.png", "答案态整屏（全 ■ + 印章）", 1600, 1050, ""),
    ("v2-02-cards.png", "答案态同时开 3 张卡（#03 / #05 / #07）", 1600, 1320,
     "E.openCard('dw-tables'); E.openCard('keywords-fn'); E.openCard('service');"),
    ("v2-03-partial.png", "空白态：env 只涂 1 个检验点 → 行 ◧", 1600, 1050,
     "E.setMode('blank'); E.openCard('env'); E.cycleCheck('env', 1); E.cycleCheck('env', 1);"),
]


def fail(msg: str) -> None:
    raise SystemExit("build_explorer.py: " + msg)


def ok(msg: str) -> None:
    print("  ✓ " + msg)


def pad2(number: int) -> str:
    return "%02d" % number


def plain(text: object) -> str:
    """去掉数据里的反引号（用于 tooltip / aria-label 等纯文本位置）。"""
    return re.sub(r"`([^`]*)`", r"\1", str(text))


def esc(text: object) -> str:
    return html_mod.escape(str(text), quote=True)


def png_size(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()[:33]
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        fail("%s 不是 PNG" % path)
    return struct.unpack(">II", raw[16:24])


# ------------------------------------------------------------------ 读数据 / 结构校验

def load_data() -> dict:
    if not DATA_PATH.exists():
        fail("缺 %s（v2 单源数据，D42/D43）" % DATA_PATH.relative_to(REPO))
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("data.json 不是合法 JSON：%s" % exc)
    if not isinstance(data, dict):
        fail("data.json 顶层必须是对象")
    return data


def page_file(page_id: str) -> Path:
    return MANUAL / ("%s.md" % page_id)


def validate_data(data: dict) -> None:
    """v2 数据一致性自检；任一失败就退出（FAIL 只许修数据，不许改生成器绕过）。"""
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    need(data.get("schema") == "completeness-v2/1",
         "schema 应为 completeness-v2/1，实际 %r" % data.get("schema"))
    need(data.get("decision") == "D42", "decision 应为 D42（v2 单源）")
    for key in ("title", "subtitle", "kicker", "order_hint"):
        need(bool(str(data.get(key, "")).strip()), "缺字段 %s" % key)
    legend = data.get("legend") or []
    need([item.get("mark") for item in legend] == ["▢", "◧", "■"],
         "legend 应为 ▢ / ◧ / ■ 三态，实际 %r" % [item.get("mark") for item in legend])
    for item in legend:
        need(bool(str(item.get("name", "")).strip()) and bool(str(item.get("desc", "")).strip()),
             "legend %r 缺 name / desc" % item.get("mark"))
    field_map = data.get("field_map") or {}
    for key in ("location", "command", "expected_output", "evidence_source"):
        need(bool(str(field_map.get(key, "")).strip()), "field_map 缺 %s 的说明" % key)

    arts = data.get("artifacts")
    if not isinstance(arts, list):
        fail("data.json 的 artifacts 必须是数组")
    total_cp = sum(len(art.get("checkpoints") or []) for art in arts)
    counts = data.get("counts") or {}
    need(len(arts) == 12, "交付物应为 12 件，实际 %d 件" % len(arts))
    need(total_cp == 24, "检验点应为 24 个，实际 %d 个" % total_cp)
    need(counts.get("artifacts") == len(arts),
         "counts.artifacts=%r 与实际 %d 不符" % (counts.get("artifacts"), len(arts)))
    need(counts.get("checkpoints") == total_cp,
         "counts.checkpoints=%r 与实际 %d 不符" % (counts.get("checkpoints"), total_cp))

    ids = [art.get("id") for art in arts]
    need(len(set(ids)) == len(ids), "交付物 id 有重复：%r" % ids)
    id_set = set(ids)
    page_lines: dict[str, int] = {}
    for idx, art in enumerate(arts):
        no = art.get("no")
        tag = "#%s" % no
        need(no == idx + 1, "%s 的编号应为 %d（按文档顺序 1–12）" % (tag, idx + 1))
        art_id = art.get("id")
        need(isinstance(art_id, str) and bool(SLUG_RE.match(art_id)),
             "%s 的 id %r 不是小写 slug" % (tag, art_id))
        for key in ("name", "kind", "location"):
            need(bool(str(art.get(key, "")).strip()), "%s 缺 %s" % (tag, key))
        pages = art.get("pages") or []
        need(isinstance(pages, list) and bool(pages), "%s 缺 pages（页签）" % tag)
        for page_id in pages:
            match = re.match(r"^(page-\d{2})$", str(page_id))
            need(bool(match), "%s 的 page %r 应形如 page-00" % (tag, page_id))
            if match:
                path = page_file(page_id)
                need(path.exists(), "%s 的页签文件 %s.md 不存在" % (tag, page_id))
                if path.exists() and page_id not in page_lines:
                    page_lines[page_id] = len(path.read_text(encoding="utf-8").splitlines())
        deps = art.get("depends_on") or []
        need(isinstance(deps, list), "%s 的 depends_on 必须是数组" % tag)
        for dep in deps:
            need(dep in id_set, "%s 的 depends_on 指向不存在的 id %r" % (tag, dep))
            need(dep != art_id, "%s 依赖自己" % tag)
            dep_art = next((x for x in arts if x.get("id") == dep), None)
            if dep_art is not None:
                need(dep_art.get("no", 0) < (no or 0),
                     "%s 的前置 %r 编号应更小（顺序依赖只能向后）" % (tag, dep))
        cps = art.get("checkpoints") or []
        need(isinstance(cps, list) and 1 <= len(cps) <= 3,
             "%s 应有 1–3 个检验点，实际 %d 个" % (tag, len(cps)))
        for i, cp in enumerate(cps, 1):
            ctag = "%s 第 %d 个检验点" % (tag, i)
            for key in ("criterion", "command", "expected_output", "evidence_source"):
                need(bool(str(cp.get(key, "")).strip()), "%s 缺 %s" % (ctag, key))
            raw_ref = str(cp.get("evidence_source", ""))
            match = EVIDENCE_REF.search(raw_ref)
            need(bool(match), "%s 的 evidence_source 里没有 page-XX.md:行号（%r）" % (ctag, raw_ref))
            if not match:
                continue
            ref_page = "page-%s" % match.group(1)
            ref_lo = int(match.group(2))
            ref_hi = int(match.group(3) or match.group(2))
            need(ref_page in pages, "%s 的溯源页 %s 不在 pages 里" % (ctag, ref_page))
            if ref_page in page_lines:
                need(1 <= ref_lo <= ref_hi <= page_lines[ref_page],
                     "%s 的溯源行号 %d-%d 超出 %s 的 %d 行"
                     % (ctag, ref_lo, ref_hi, ref_page, page_lines[ref_page]))

    criteria = data.get("completeness_criteria") or []
    need(len(criteria) == 3, "完备性判据应为 3 条，实际 %d 条" % len(criteria))
    for item in criteria:
        need(item.get("mark") == "■" and bool(str(item.get("text", "")).strip()), "完备性判据缺 mark/text")

    # 答案态算术（数据层；DOM 段再真跑一遍）
    e2e = next((art for art in arts if art.get("id") == E2E_ID), None)
    need(e2e is not None, "缺第 12 件端到端链路 id=%r" % E2E_ID)
    need(e2e is not None and e2e.get("no") == len(arts),
         "端到端链路应是最后一件（no=%d）" % len(arts))
    need(e2e is not None and len(e2e.get("checkpoints") or []) >= 1, "端到端链路至少要 1 个检验点")
    if errs:
        print("✗ v2 数据一致性校验失败（%d 条）：" % len(errs))
        for err in errs:
            print("  - " + err)
        raise SystemExit(1)

    e2e_cp = len(e2e["checkpoints"]) if e2e else 0
    dep_count = sum(len(art.get("depends_on") or []) for art in arts)
    ok("数据结构：%d 件交付物 · %d 个检验点（每件 1–3 个）· %d 条顺序依赖无环 · 页签文件全部存在"
       % (len(arts), total_cp, dep_count))
    ok("答案态算术：行 ■ %d/%d · 检验点 ■ %d/%d · 端到端链 %d/%d ✓（数据层；DOM 再真跑）"
       % (len(arts), len(arts), total_cp, total_cp, e2e_cp, e2e_cp))


# ------------------------------------------------------------------ flow.mmd 交叉核对

def load_flow() -> dict:
    if not FLOW_MMD.exists():
        fail("缺 %s（AON 活动名 / 紧前关系，D43 导航条来源）" % FLOW_MMD.relative_to(REPO))
    text = FLOW_MMD.read_text(encoding="utf-8")
    names: dict[str, str] = {}
    for match in AON_NODE_RE.finditer(text):
        label = match.group(2).strip()
        parsed = re.match(r"^(A\d+)\s+(.+)$", label)
        if not parsed:
            fail("flow.mmd 活动标签解析失败：%r" % label)
        names[parsed.group(1)] = parsed.group(2).strip()
    edges = [("A%s" % a, "A%s" % b) for a, b in AON_EDGE_RE.findall(text)]
    return {"names": names, "edges": edges}


def check_flow(data: dict, flow: dict) -> None:
    names, edges = flow["names"], flow["edges"]
    ids = sorted(names, key=lambda item: int(item[1:]))
    if ids != EXPECTED_ACTIVITIES:
        fail("flow.mmd 活动应为 A0–A9，实际 %r" % ids)
    if set(edges) != set(EXPECTED_FLOW_EDGES):
        missing = sorted(set(EXPECTED_FLOW_EDGES) - set(edges))
        extra = sorted(set(edges) - set(EXPECTED_FLOW_EDGES))
        fail("flow.mmd 的 FS 紧前关系与预期不符：缺 %r / 多 %r" % (missing, extra))

    art_ids = {art.get("id") for art in data["artifacts"]}
    if set(ACTIVITY_OF_ARTIFACT) != art_ids:
        fail("交付物 → AON 位置映射与 data.json 不一致：缺 %r / 多 %r"
             % (sorted(art_ids - set(ACTIVITY_OF_ARTIFACT)),
                sorted(set(ACTIVITY_OF_ARTIFACT) - art_ids)))
    order = {act: idx for idx, act in enumerate(EXPECTED_ACTIVITIES)}
    by_act: dict[str, list[str]] = {}
    last = -1
    for art in sorted(data["artifacts"], key=lambda item: item["no"]):
        act = ACTIVITY_OF_ARTIFACT[art["id"]]
        by_act.setdefault(act, []).append(art["id"])
        if order[act] < last:
            fail("#%d 的 AON 位置必须随编号单调递增（%s 出现在更晚的活动后）" % (art["no"], act))
        last = order[act]
    for act in EXPECTED_ACTIVITIES:
        if not by_act.get(act):
            fail("AON 活动 %s 没有对应交付物" % act)

    # 导航条的画法必须真在 flow.mmd 的边上：主干 A0→A3→…→A9，支线 A0→A1→A2→A7
    edge_set = set(edges)
    for left, right in zip(MAIN_LINE, MAIN_LINE[1:]):
        if (left, right) not in edge_set:
            fail("AON 主干 %s→%s 不在 flow.mmd 里" % (left, right))
    for left, right in zip(BRANCH_LINE, BRANCH_LINE[1:]):
        if (left, right) not in edge_set:
            fail("AON 数据支线 %s→%s 不在 flow.mmd 里" % (left, right))
    for act in ("A1", "A2"):
        if act not in by_act:
            fail("AON 支线活动 %s 没有对应交付物" % act)

    # depends_on 与 AON 交叉核对：前置交付物所在活动必须是本活动在 flow.mmd 里的祖先
    succ: dict[str, set[str]] = {act: set() for act in EXPECTED_ACTIVITIES}
    for left, right in edges:
        succ[left].add(right)
    reach: dict[str, set[str]] = {}

    def ancestors(start: str) -> set[str]:
        if start in reach:
            return reach[start]
        seen: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in succ[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        reach[start] = seen
        return seen

    for art in data["artifacts"]:
        act = ACTIVITY_OF_ARTIFACT[art["id"]]
        for dep in art.get("depends_on") or []:
            dep_act = ACTIVITY_OF_ARTIFACT[dep]
            if dep_act != act and act not in ancestors(dep_act):
                fail("#%d 的前置 %r（%s）在 flow.mmd 里不是 %s 的祖先活动"
                     % (art["no"], dep, dep_act, act))

    ok("flow.mmd 交叉核对：活动名 10 个 · FS 紧前关系 %d 条 · 12 件交付物的 A0–A9 位置映射全覆盖"
       "（depends_on 均为 AON 祖先；导航只定位、不勾选）" % len(edges))


# ------------------------------------------------------------------ AON 导航条渲染

def aon_nav_html(data: dict, flow: dict) -> str:
    by_act: dict[str, list[dict]] = {}
    for art in data["artifacts"]:
        by_act.setdefault(ACTIVITY_OF_ARTIFACT[art["id"]], []).append(art)
    names = flow["names"]

    def node(act: str) -> str:
        arts = by_act[act]
        where = " · ".join("#%02d %s" % (art["no"], plain(art["name"])) for art in arts)
        tip = ("%s %s · 位置：%s · 只高亮左侧对应零件行，不参与勾选"
               % (act, names[act], where))
        return ('<button type="button" class="aon-node" data-activity="%s" data-arts="%s"'
                ' title="%s"><span class="an">%s</span>%s</button>'
                % (esc(act), esc(" ".join(art["id"] for art in arts)), esc(tip),
                   esc(act), esc(names[act])))

    arrow = '<span class="aon-arw">→</span>'
    main = arrow.join(node(act) for act in MAIN_LINE)
    branch = ('<span class="aon-arw">└</span>' + node("A1") + arrow + node("A2")
              + '<span class="aon-join">↘ 汇入 A7（真执行 SQL）；数据支线有浮动</span>')
    return ('<div class="aon-line main" id="aon-main">' + main + '</div>'
            '<div class="aon-line branch" id="aon-branch">' + branch + '</div>')


# ------------------------------------------------------------------ HTML 模板

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>建成证明 v2 · 可交互原型</title>
<style>
:root{
  --ink:#111111; --ink2:#333333; --mute:#666666; --hair:#c9c9c9;
  --soft:#f4f4f4; --paper:#ffffff; --wire:#b9b9b9;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:var(--paper);color:var(--ink);}
body{font-family:"Noto Sans CJK SC","Source Han Sans SC","Microsoft YaHei",sans-serif;
     -webkit-font-smoothing:antialiased;}
.mono,.code,.ev,.stat b,.card-no,.name-id,.c-no,.box,.row-badge,.derived-badge,
.aon-node .an,.derive,.cp-cmd,.cp-exp,.cp-src,.pg,.card-tag,.lh-ro,.lh-edit,.aon-title,
.ph-n,.ct-count,.cp-no,.lbl,.aon-note,.aon-join,.aon-arw,.mid,.stamp{
  font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;
}
.app{display:flex;flex-direction:column;height:100vh;min-height:720px;overflow:hidden;}

/* ---------- 顶部 ---------- */
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;
     padding:12px 22px 9px;border-bottom:2.5px solid var(--ink);flex:0 0 auto;}
.kicker{font-size:11.5px;letter-spacing:.6px;color:var(--mute);}
h1{margin:2px 0 0;font-size:26px;font-weight:900;letter-spacing:.4px;line-height:1.12;}
.sub{margin-top:4px;font-size:12.5px;color:var(--ink2);}
.controls{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex:0 0 auto;max-width:590px;}
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
.mode-hint{font-size:11.5px;color:var(--mute);text-align:right;line-height:1.45;}

/* ---------- 状态条 ---------- */
.statusbar{display:flex;align-items:center;gap:9px;padding:6px 22px;
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
.stamp{margin-left:auto;border:3px double var(--ink);padding:2px 14px;font-size:17px;
       font-weight:900;letter-spacing:2px;transform:rotate(-3deg);background:#fff;}
.stamp[hidden]{display:none;}

/* ---------- AON 流水导航（只定位，不勾选） ---------- */
.aon{display:flex;flex-direction:column;gap:3px;padding:6px 22px 7px;
     border-bottom:1.5px solid var(--ink);background:#fff;flex:0 0 auto;}
.aon-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;}
.aon-title{font-size:12px;font-weight:900;letter-spacing:.3px;}
.aon-note{font-size:10.3px;color:var(--mute);}
.aon-body{display:flex;flex-direction:column;gap:3px;}
.aon-line{display:flex;align-items:center;gap:4px;flex-wrap:wrap;font-size:11px;}
.aon-line.branch{padding-left:18px;border-left:2px solid var(--hair);margin-left:7px;
                 padding-top:2px;padding-bottom:1px;}
.aon-node{border:1.4px solid var(--ink);border-radius:5px;background:#fff;color:var(--ink);
          font:inherit;font-size:10.5px;font-weight:700;padding:2px 7px;cursor:pointer;
          white-space:nowrap;letter-spacing:.2px;}
.aon-node .an{font-weight:800;margin-right:3px;}
.aon-node:hover{background:#e8e8e8;}
.aon-node.is-on{background:var(--ink);color:#fff;}
.aon-arw{color:#999;font-size:11px;}
.aon-join{font-size:10px;color:#666;border-left:1px solid #bbb;padding-left:6px;margin-left:2px;}

/* ---------- 中分 ---------- */
.split{display:flex;flex:1 1 auto;min-height:0;}
.left{flex:0 0 46%;min-width:0;padding:10px 14px 10px 20px;display:flex;
      flex-direction:column;gap:8px;overflow:hidden;}
.right{flex:1 1 54%;min-width:0;display:flex;flex-direction:column;
       border-left:2px solid var(--ink);background:#fafafa;
       box-shadow:-10px 0 18px rgba(0,0,0,.06);position:relative;z-index:2;}

/* ---------- 左：物料清单 ---------- */
.left-head{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;flex:0 0 auto;}
.lh-title{font-size:14px;font-weight:900;letter-spacing:.3px;}
.lh-title b{font-size:16px;}
.lh-ro{font-size:10.5px;color:#444;border:1px solid #999;border-radius:3px;
       padding:0 5px;background:#fff;white-space:nowrap;}
.lh-edit{font-size:10.5px;color:#333;border:1px dashed #999;border-radius:3px;
         padding:1px 6px;background:#fff;white-space:nowrap;}
.lh-edit[hidden]{display:none;}
.legend{display:flex;align-items:center;gap:10px;margin-left:auto;flex-wrap:wrap;
        font-size:10.8px;color:var(--ink2);}
.legend .lg{display:inline-flex;align-items:center;gap:4px;}
.legend .glyph{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;font-size:14px;line-height:1;}
.table-wrap{flex:1 1 auto;min-height:0;overflow:auto;border:2px solid var(--ink);
            border-radius:8px;background:#fff;}
table.material{width:100%;border-collapse:collapse;table-layout:fixed;font-size:11.2px;}
table.material col.c-st{width:30px;}
table.material col.c-no{width:34px;}
table.material col.c-name{width:21%;}
table.material col.c-kind{width:14%;}
table.material col.c-pg{width:52px;}
table.material thead th{position:sticky;top:0;background:#ececec;border-bottom:1.6px solid var(--ink);
                        font-size:10.4px;font-weight:800;padding:4px 5px;text-align:left;z-index:1;}
table.material tbody tr.mrow{cursor:pointer;vertical-align:top;border-bottom:1px solid #d6d6d6;}
table.material tbody tr.mrow:last-child{border-bottom:0;}
table.material td{padding:6px 5px;vertical-align:top;line-height:1.34;}
table.material tbody tr.mrow:hover{background:#f2f2f2;}
table.material tbody tr.mrow.is-open{background:#e0e0e0;box-shadow:inset 4px 0 0 var(--ink);}
table.material tbody tr.mrow.is-navhl{background:#e9e9e9;outline:2px dashed #555;outline-offset:-2px;}
table.material tbody tr.mrow.is-open.is-navhl{background:#d8d8d8;}
td.c-st{text-align:center;padding-top:4px;}
.row-badge{display:inline-block;font-size:17px;line-height:1;cursor:default;}
td.c-no{font-size:10px;color:#555;padding-top:7px;}
td.c-name{font-weight:800;font-size:12.2px;}
td.c-name .name-id{display:block;font-weight:400;font-size:9px;color:#777;margin-top:2px;}
td.c-kind{font-size:10.7px;color:#222;}
td.c-loc{font-size:10.5px;color:#222;overflow-wrap:anywhere;}
td.c-loc code,td.c-name code,td.c-kind code{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;
             font-size:9.3px;background:#f2f2f2;padding:0 2px;border-radius:2px;}
td.c-pg{font-size:10px;white-space:nowrap;padding-top:7px;}
a.pg{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--ink);}
a.pg:hover{background:var(--ink);color:#fff;}
.criteria{border:1.6px solid var(--ink);border-radius:7px;padding:6px 10px;background:#fff;
          display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:10.8px;
          flex:0 0 auto;}
.criteria .cr-title{font-weight:900;font-size:11px;border-right:1.5px solid var(--ink);
                    padding-right:10px;white-space:nowrap;}
.criteria .cr-item{display:inline-flex;gap:5px;align-items:baseline;white-space:nowrap;}
.criteria .cr-mark{font-family:"DejaVu Sans","Noto Sans CJK SC",sans-serif;font-size:13px;line-height:1;}
.criteria .cr-note{color:#666;font-size:10px;margin-left:auto;white-space:nowrap;}
.left-foot{font-size:10.5px;color:#555;line-height:1.45;flex:0 0 auto;}

/* ---------- 右：检验卡 ---------- */
.panel-h{display:flex;align-items:center;gap:9px;padding:8px 14px;
         border-bottom:1.5px solid var(--ink);background:#fff;flex:0 0 auto;}
.ph-t{font-size:12.5px;font-weight:900;letter-spacing:.2px;}
.ph-n{font-size:11px;color:#666;}
#close-all{margin-left:auto;border:1.6px solid var(--ink);background:#fff;font:inherit;
           font-size:12px;font-weight:800;padding:4px 11px;border-radius:4px;cursor:pointer;}
#close-all:hover:not(:disabled){background:var(--ink);color:#fff;}
#close-all:disabled{opacity:.35;cursor:default;}
.cards{flex:1 1 auto;overflow:auto;padding:12px 14px 20px;
       display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
       gap:12px;align-content:start;align-items:start;}
.cards.is-empty{display:flex;flex-direction:column;}
.empty{grid-column:1/-1;flex:1 1 auto;min-height:280px;display:flex;align-items:center;
       justify-content:center;padding:28px;color:#888;font-size:13px;text-align:center;
       line-height:1.9;border:1.6px dashed var(--wire);border-radius:8px;background:#fff;}
.card{border:1.7px solid var(--ink);border-radius:7px;background:#fff;
      padding:9px 11px 9px;display:flex;flex-direction:column;gap:6px;min-width:0;
      box-shadow:0 1px 0 #dddddd;}
.card-h{display:flex;align-items:center;gap:6px;}
.card-no{font-size:10px;background:var(--ink);color:#fff;padding:1px 7px;border-radius:3px;}
.card-tag{font-size:9.5px;color:#666;border:1px solid #aaa;border-radius:3px;padding:0 5px;
          white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:250px;}
.card-x{margin-left:auto;border:0;background:none;font-size:19px;line-height:1;
        cursor:pointer;color:#444;padding:0 2px;}
.card-x:hover{color:#000;}
.card-name{margin:0;font-size:15.5px;font-weight:900;line-height:1.2;}
.card-name code{font-size:13px;}
.card-loc{font-size:10.3px;color:#333;line-height:1.4;overflow-wrap:anywhere;}
.card-loc code{font-size:9.5px;background:#f2f2f2;padding:0 2px;border-radius:2px;
               font-family:"DejaVu Sans Mono",monospace;}
.card-status{display:flex;align-items:center;gap:7px;font-size:11.5px;flex-wrap:wrap;
             border-top:1px solid #dddddd;border-bottom:1px solid #dddddd;padding:5px 0;}
.derived-badge{font-size:21px;line-height:1;border:1.4px solid var(--ink);border-radius:5px;
               background:#fff;color:var(--ink);padding:1px 6px;cursor:default;}
.state-name{font-weight:800;font-size:11.5px;}
.ro-tag{font-size:9.5px;color:#444;border:1px solid #999;border-radius:3px;padding:0 4px;
        background:#fff;white-space:nowrap;}
.derive{font-size:10px;color:#333;border:1px dashed #aaa;border-radius:3px;padding:0 4px;
        white-space:nowrap;}
.card-meta{display:flex;gap:9px;flex-wrap:wrap;font-size:10px;color:#555;
           border-top:1px dashed #cccccc;padding-top:5px;}
.card-meta .cm{display:inline-flex;gap:3px;align-items:baseline;}
.card-meta b{font-size:11px;}
.cps{display:flex;flex-direction:column;gap:8px;}
.cp{border:1.3px solid #333;border-radius:6px;padding:6px 8px 7px;background:#fff;
    display:flex;flex-direction:column;gap:4px;}
.cp-h{display:flex;align-items:flex-start;gap:7px;}
.box{flex:0 0 auto;width:29px;height:27px;border:1.6px solid var(--ink);border-radius:4px;
     background:#fff;color:var(--ink);font-size:18px;line-height:1;cursor:pointer;padding:0;}
.box:hover:not(:disabled){background:#e6e6e6;}
.box:focus-visible{outline:2px solid var(--ink);outline-offset:1px;}
.box.is-locked{cursor:default;background:#f7f7f7;color:#222;}
.cp-crit{font-size:11px;line-height:1.4;overflow-wrap:anywhere;flex:1 1 auto;}
.cp-crit .cp-no{font-size:9px;color:#666;margin-right:4px;font-weight:400;}
.cp-crit code{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:9.6px;
              background:#f2f2f2;padding:0 2px;border-radius:2px;}
.cp-src{font-size:8.6px;color:#777;white-space:nowrap;padding-top:3px;}
.cp-kv{display:flex;flex-direction:column;gap:2px;}
.cp-kv .lbl{font-size:8.6px;font-weight:800;letter-spacing:.9px;color:#555;}
.cp-cmd,.cp-exp{margin:0;font-size:9.4px;line-height:1.45;white-space:pre-wrap;
                overflow-wrap:anywhere;border-radius:0 3px 3px 0;padding:4px 6px;color:#111;}
.cp-cmd{background:#f7f7f7;border-left:3px solid var(--ink);}
.cp-exp{background:#fcfcfc;border-left:3px solid #999;}
.card-foot{font-size:9.7px;color:#555;border-top:1px dashed #cccccc;padding-top:5px;
           line-height:1.4;overflow-wrap:anywhere;}
.card-foot code{font-family:"DejaVu Sans Mono",monospace;font-size:9.2px;background:#f2f2f2;padding:0 2px;}

/* ---------- 提示条 ---------- */
.toast{position:fixed;left:50%;top:14px;transform:translateX(-50%) translateY(-8px);
       background:var(--ink);color:#fff;font-size:12.5px;font-weight:700;letter-spacing:.3px;
       padding:8px 16px;border-radius:6px;box-shadow:0 4px 14px rgba(0,0,0,.25);
       opacity:0;pointer-events:none;transition:opacity .16s ease,transform .16s ease;z-index:50;}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0);}
.toast[hidden]{display:none;}

@media (max-width:1280px){
  .left{flex-basis:48%;}
  .cards{grid-template-columns:repeat(auto-fill,minmax(300px,1fr));}
  .legend{display:none;}
}
</style>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="brand">
      <div class="kicker" id="kicker"></div>
      <h1><span id="title"></span> <span class="mid">·</span> 可交互</h1>
      <div class="sub" id="subtitle"></div>
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

  <section class="statusbar" aria-label="建成证明状态条">
    <div class="stat" id="stat-rows" title=""></div>
    <div class="stat" id="stat-checks" title=""></div>
    <div class="stat" id="stat-e2e" title=""></div>
    <div class="stamp" id="stamp" hidden title="">建成证明 ✓</div>
  </section>

  <nav class="aon" id="aon" aria-label="AON 流水导航（只定位，不勾选）">
    <div class="aon-head">
      <span class="aon-title">AON 流水 · 位置导航</span>
      <span class="aon-note">A0–A9 活动名 / 顺序取自 manual/flow.mmd · 点它只高亮左侧零件行，<b>不参与勾选</b></span>
    </div>
    <div class="aon-body">__AON_NAV__</div>
  </nav>

  <main class="split">
    <section class="left">
      <div class="left-head">
        <span class="lh-title">① 物料清单 · <b id="art-count">12</b> 件</span>
        <span class="lh-ro">行徽章只读 · 由本件检验点派生</span>
        <span class="lh-edit" id="edit-note" hidden>编辑态 · 点卡片三态方框循环 ▢→◧→■ · 进度存本机浏览器</span>
        <span class="legend">
          <span class="lg"><span class="glyph">▢</span>未建</span>
          <span class="lg"><span class="glyph">◧</span>已建未验</span>
          <span class="lg"><span class="glyph">■</span>已建且判据通过</span>
        </span>
      </div>
      <div class="table-wrap" id="material-scroll">
        <table class="material" id="material-table">
          <colgroup>
            <col class="c-st"><col class="c-no"><col class="c-name">
            <col class="c-kind"><col class="c-loc"><col class="c-pg">
          </colgroup>
          <thead>
            <tr>
              <th class="c-st" title="行首派生徽章（只读）：本件全部检验点 ■ ⇒ ■；部分 ⇒ ◧；全 ▢ ⇒ ▢">态</th>
              <th class="c-no">编号</th>
              <th class="c-name">零件名</th>
              <th class="c-kind">类型</th>
              <th class="c-loc">位置</th>
              <th class="c-pg">页签</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      <div class="criteria" id="criteria"></div>
      <div class="left-foot">点一行开卡、再点关闭，可同时开多张卡。行徽章：本件检验点全 ■ ⇒ ■，部分 ■/◧ ⇒ ◧，全 ▢ ⇒ ▢；卡片里的三态方框是唯一编辑入口（仅空白态）。</div>
    </section>

    <aside class="right" aria-label="检验卡区">
      <div class="panel-h">
        <span class="ph-t">② 检验卡 · 每张卡 = 该件交付物的 1–3 个检验点</span>
        <span class="ph-n" id="card-count">0 张</span>
        <button type="button" id="close-all" disabled>全部关闭</button>
      </div>
      <div class="cards is-empty" id="cards"></div>
    </aside>
  </main>
</div>
<div class="toast" id="toast" role="status" aria-live="polite" hidden></div>

<script id="completeness-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  'use strict';

  var DATA = JSON.parse(document.getElementById('completeness-data').textContent);
  var ARTS = DATA.artifacts.slice();
  var ART_BY_ID = {};
  var ART_INDEX = {};
  ARTS.forEach(function (art, index) {
    ART_BY_ID[art.id] = art;
    ART_INDEX[art.id] = index;
  });

  var GLYPH = { unbuilt: '▢', unverified: '◧', built: '■' };
  var NAME = { unbuilt: '未建', unverified: '已建未验', built: '已建且判据通过' };
  var DESC = { unbuilt: '还没动手，或没跑通', unverified: '做完了但没对判据',
               built: '输出与页面「你应该看到」逐字对上' };
  (DATA.legend || []).forEach(function (item) {
    if (item.mark === '▢') { NAME.unbuilt = item.name; DESC.unbuilt = item.desc; }
    if (item.mark === '◧') { NAME.unverified = item.name; DESC.unverified = item.desc; }
    if (item.mark === '■') { NAME.built = item.name; DESC.built = item.desc; }
  });
  var CYCLE = { unbuilt: 'unverified', unverified: 'built', built: 'unbuilt' };
  var E2E_ART = null;
  ARTS.forEach(function (art) { if (art.id === 'e2e-chain') { E2E_ART = art; } });
  if (!E2E_ART) { E2E_ART = ARTS[ARTS.length - 1]; }
  var TOTAL_CHECKS = ARTS.reduce(function (sum, art) { return sum + art.checkpoints.length; }, 0);

  // AON 导航的活动 → 交付物 id（由生成器从 flow.mmd 映射后写进 data-arts）
  var ACTIVITY_ARTS = {};
  Array.prototype.forEach.call(document.querySelectorAll('#aon [data-activity]'), function (node) {
    var ids = (node.getAttribute('data-arts') || '').split(/\s+/);
    ACTIVITY_ARTS[node.getAttribute('data-activity')] = ids.filter(function (id) { return id; });
  });

  // ---------- 本机进度（D43：键换 completeness-v2/checks-v1） ----------
  var STORAGE_KEY = 'completeness-v2/checks-v1';
  var STORAGE_OK = (function () {
    try {
      window.localStorage.setItem('__explorer_v2_probe__', '1');
      window.localStorage.removeItem('__explorer_v2_probe__');
      return true;
    } catch (err) { return false; }
  })();

  // 唯一可变状态：mode（答案态 / 空白态）、checks（检验点级真源）、open（打开的卡片）、navhl
  var state = { mode: 'answer', checks: {}, open: [], navhl: null };

  function esc(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/[&<>"]/g, function (ch) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch];
      });
  }

  // 把 `反引号` 渲染成等宽 code；其余部分转义
  function rich(text) {
    var source = String(text === null || text === undefined ? '' : text);
    var out = '';
    var pos = 0;
    var re = /`([^`]*)`/g;
    var match;
    while ((match = re.exec(source)) !== null) {
      out += esc(source.slice(pos, match.index)) + '<code>' + esc(match[1]) + '</code>';
      pos = re.lastIndex;
    }
    return out + esc(source.slice(pos));
  }

  function pad2(number) { return (number < 10 ? '0' : '') + number; }

  function pageLabel(pageId) {
    var number = parseInt(String(pageId).replace(/^page-/, ''), 10);
    return '第' + (isNaN(number) ? '?' : number) + '页';
  }

  function pageLink(pageId) {
    return '<a class="pg" href="../' + esc(pageId) + '.md" title="打开 ' + esc(pageId) +
      '.md">' + esc(pageLabel(pageId)) + '</a>';
  }

  // ---------- 派生规则（D43）：检验点 → 行 / 卡顶徽章 ----------
  function blankChecks() {
    var map = {};
    ARTS.forEach(function (art) {
      map[art.id] = art.checkpoints.map(function () { return 'unbuilt'; });
    });
    return map;
  }

  function coerceStatus(value) {
    return (value === 'unbuilt' || value === 'unverified' || value === 'built') ? value : 'unbuilt';
  }

  function checkStatus(art, index) {
    if (state.mode === 'answer') { return 'built'; }
    var row = state.checks[art.id];
    return row && index >= 0 && index < row.length ? coerceStatus(row[index]) : 'unbuilt';
  }

  function countsOf(art) {
    var counts = { total: art.checkpoints.length, built: 0, unverified: 0, unbuilt: 0 };
    art.checkpoints.forEach(function (_, index) {
      counts[checkStatus(art, index)] += 1;
    });
    return counts;
  }

  function artifactStatus(art) {
    var counts = countsOf(art);
    if (!counts.total) { return 'unbuilt'; }
    if (counts.built === counts.total) { return 'built'; }
    if (counts.unbuilt === counts.total) { return 'unbuilt'; }
    return 'unverified';
  }

  function deriveLine(art) {
    var counts = countsOf(art);
    return '由本件 ' + counts.total + ' 个检验点派生：' + counts.built + '■ ' +
      counts.unverified + '◧ ' + counts.unbuilt + '▢';
  }

  function compute() {
    var rowsPass = 0;
    var checksPass = 0;
    var checksTotal = 0;
    ARTS.forEach(function (art) {
      var counts = countsOf(art);
      checksTotal += counts.total;
      checksPass += counts.built;
      if (artifactStatus(art) === 'built') { rowsPass += 1; }
    });
    var e2eTotal = E2E_ART ? E2E_ART.checkpoints.length : 0;
    var e2ePass = !!E2E_ART && artifactStatus(E2E_ART) === 'built';
    return {
      rowsPass: rowsPass, rowsTotal: ARTS.length,
      checksPass: checksPass, checksTotal: checksTotal,
      e2ePass: e2ePass, e2eTotal: e2eTotal, e2eId: E2E_ART ? E2E_ART.id : null,
      all: rowsPass === ARTS.length && checksPass === checksTotal && e2ePass
    };
  }

  // ---------- 本机进度读写 ----------
  function savedRaw() {
    if (!STORAGE_OK) { return null; }
    try { return window.localStorage.getItem(STORAGE_KEY); } catch (err) { return null; }
  }

  function readSaved() {
    var raw = savedRaw();
    if (!raw) { return null; }
    try {
      var obj = JSON.parse(raw);
      if (!obj || obj.v !== 1 || obj.mode !== 'blank' || !obj.checks || typeof obj.checks !== 'object') {
        return null;
      }
      var map = blankChecks();
      ARTS.forEach(function (art) {
        var saved = obj.checks[art.id];
        if (!Array.isArray(saved)) { return; }
        art.checkpoints.forEach(function (_, index) {
          if (index < saved.length && typeof saved[index] === 'string') {
            map[art.id][index] = coerceStatus(saved[index]);
          }
        });
      });
      return map;
    } catch (err) { return null; }
  }

  function persist() {
    if (!STORAGE_OK) { return; }
    try {
      if (state.mode !== 'blank') {
        window.localStorage.removeItem(STORAGE_KEY);
        return;
      }
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        v: 1, mode: 'blank', checks: state.checks, ts: Date.now()
      }));
    } catch (err) { /* 存不了就只在本页内存里编辑 */ }
  }

  function clearSaved() {
    if (!STORAGE_OK) { return; }
    try { window.localStorage.removeItem(STORAGE_KEY); } catch (err) {}
  }

  // ---------- 渲染：左物料清单 ----------
  function rowHTML(art) {
    var status = artifactStatus(art);
    var open = state.open.indexOf(art.id) >= 0;
    var nav = state.navhl && ACTIVITY_ARTS[state.navhl] &&
      ACTIVITY_ARTS[state.navhl].indexOf(art.id) >= 0;
    var tip = deriveLine(art) + '（只读；点行开卡 / 关这张卡）';
    return '<tr class="mrow' + (open ? ' is-open' : '') + (nav ? ' is-navhl' : '') + '"' +
      ' data-art="' + esc(art.id) + '" tabindex="0" role="button" aria-pressed="' +
      (open ? 'true' : 'false') + '" title="' + esc(plainTitle(art)) + '">' +
      '<td class="c-st"><span class="row-badge" data-derived-row="' + esc(art.id) +
      '" data-status="' + esc(status) + '" title="' + esc(tip) + '">' + GLYPH[status] +
      '</span></td>' +
      '<td class="c-no">' + esc(pad2(art.no)) + '</td>' +
      '<td class="c-name"><span class="name-t">' + rich(art.name) + '</span>' +
      '<span class="name-id">' + esc(art.id) + '</span></td>' +
      '<td class="c-kind">' + rich(art.kind) + '</td>' +
      '<td class="c-loc">' + rich(art.location) + '</td>' +
      '<td class="c-pg">' + art.pages.map(pageLink).join('') + '</td>' +
      '</tr>';
  }

  function plainTitle(art) {
    return art.id + ' · ' + art.name.replace(/`/g, '') + ' · ' + art.kind.replace(/`/g, '');
  }

  function renderRows() {
    var host = document.getElementById('rows');
    var scroller = document.getElementById('material-scroll');
    var scrollTop = scroller ? scroller.scrollTop : 0;
    host.innerHTML = ARTS.map(rowHTML).join('');
    if (scroller) { scroller.scrollTop = scrollTop; }
  }

  // ---------- 渲染：右检验卡 ----------
  function checkpointHTML(art, checkpoint, index, editable) {
    var number = index + 1;
    var status = checkStatus(art, index);
    var next = CYCLE[status];
    var tip = editable
      ? ('当前：' + GLYPH[status] + ' ' + NAME[status] + ' · 点一下切下一态 → ' +
         GLYPH[next] + ' ' + NAME[next] + '（循环 ▢ → ◧ → ■ → ▢）')
      : ('答案态只读：' + GLYPH[status] + ' ' + NAME[status] +
         ' · 切到「空白态」后点方框可编辑');
    var locked = editable ? '' : ' is-locked';
    var disabled = editable ? '' : ' disabled aria-disabled="true"';
    var refMatch = String(checkpoint.evidence_source || '')
      .match(/page-\d{2}\.md:\d+(?:[-,–]\d+)?/);
    var refText = refMatch ? refMatch[0] : '溯源';
    return '<div class="cp" data-cp="' + esc(art.id) + ':' + number + '">' +
      '<div class="cp-h">' +
      '<button type="button" class="box' + locked + '" data-check="' + esc(art.id) +
      '" data-cp="' + number + '" data-status="' + esc(status) + '"' + disabled +
      ' title="' + esc(tip) + '" aria-label="' +
      esc('检验点 [' + number + ']：' + NAME[status] + (editable ? '，点一下切下一态' : '，答案态只读')) +
      '">' + GLYPH[status] + '</button>' +
      '<div class="cp-crit"><span class="cp-no">[' + number + ']</span>' +
      rich(checkpoint.criterion) + '</div>' +
      '<span class="cp-src" title="' + esc(checkpoint.evidence_source) + '">' +
      esc(refText) + '</span>' +
      '</div>' +
      '<div class="cp-kv"><span class="lbl">命令</span>' +
      '<pre class="cp-cmd">' + esc(checkpoint.command) + '</pre></div>' +
      '<div class="cp-kv"><span class="lbl">期望输出</span>' +
      '<pre class="cp-exp">' + esc(checkpoint.expected_output) + '</pre></div>' +
      '</div>';
  }

  function cardHTML(art) {
    var status = artifactStatus(art);
    var counts = countsOf(art);
    var editable = state.mode === 'blank';
    var badgeTitle = deriveLine(art) + '（只读派生徽章；' +
      (editable ? '点下方三态方框编辑' : '答案态全 ■、只读') + '）';
    var deps = (art.depends_on || []).map(function (dep) {
      var target = ART_BY_ID[dep];
      return target ? '#' + pad2(target.no) + ' ' + target.name.replace(/`/g, '')
        : String(dep);
    }).join(' · ');
    return '<article class="card" data-card="' + esc(art.id) + '">' +
      '<header class="card-h">' +
      '<span class="card-no">#' + pad2(art.no) + '</span>' +
      '<span class="card-tag">' + esc(art.kind.replace(/`/g, '')) + '</span>' +
      '<button type="button" class="card-x" data-close="' + esc(art.id) +
      '" aria-label="关闭 ' + esc(art.name.replace(/`/g, '')) + ' 的检验卡">×</button>' +
      '</header>' +
      '<h2 class="card-name">' + rich(art.name) + '</h2>' +
      '<div class="card-loc">' + rich(art.location) + '</div>' +
      '<div class="card-status">' +
      '<span class="derived-badge" data-derived-card="' + esc(art.id) +
      '" data-status="' + esc(status) + '" title="' + esc(badgeTitle) + '">' + GLYPH[status] +
      '</span>' +
      '<span class="state-name">' + esc(NAME[status]) + '</span>' +
      '<span class="ro-tag">只读派生</span>' +
      '<span class="derive" title="' + esc(deriveLine(art)) + '">' +
      counts.built + '■ ' + counts.unverified + '◧ ' + counts.unbuilt + '▢</span>' +
      '</div>' +
      '<div class="card-meta">' +
      '<span class="cm">检验点 <b>' + counts.total + '</b> 个</span>' +
      '<span class="cm">页签 ' + art.pages.map(pageLink).join(' ') + '</span>' +
      (deps ? '<span class="cm">前置 ' + esc(deps) + '</span>' : '') +
      '</div>' +
      '<div class="cps">' + art.checkpoints.map(function (checkpoint, index) {
        return checkpointHTML(art, checkpoint, index, editable);
      }).join('') + '</div>' +
      '<div class="card-foot">' + esc(art.id) + ' · 本卡徽章由本件 ' + counts.total +
      ' 个检验点派生；每格「命令 → 期望输出」都可按页签回原文复核。</div>' +
      '</article>';
  }

  function renderCards() {
    var host = document.getElementById('cards');
    var scrollTop = host.scrollTop;
    host.classList.toggle('is-empty', state.open.length === 0);
    if (!state.open.length) {
      host.innerHTML = '<div class="empty">点左侧任意一行 → 在这里开一张「本件检验卡」<br>' +
        '每张卡 = 该件交付物的 1–3 个检验点（判据 + 命令 + 期望输出），可同时开多张卡。<br>' +
        '空白态下点检验点左边的三态方框，按 ▢ → ◧ → ■ → ▢ 循环，' +
        '行徽章与顶部判定实时派生。</div>';
    } else {
      host.innerHTML = state.open.map(function (id) {
        return cardHTML(ART_BY_ID[id]);
      }).join('');
    }
    host.scrollTop = scrollTop;
    document.getElementById('card-count').textContent = state.open.length + ' 张';
    document.getElementById('close-all').disabled = state.open.length === 0;
  }

  // ---------- 渲染：完备判据（用 data.json 的 completeness_criteria） ----------
  function renderCriteria() {
    var host = document.getElementById('criteria');
    if (!host) { return; }
    var items = (DATA.completeness_criteria || []).map(function (item) {
      return '<span class="cr-item" title="' + esc(item.hint || '') + '">' +
        '<span class="cr-mark">' + esc(item.mark || '■') + '</span>' +
        rich(item.text) + '</span>';
    }).join('');
    host.innerHTML = '<span class="cr-title">完备判据</span>' + items +
      '<span class="cr-note">三条全绿 ⇒ 右上「建成证明 ✓」印章</span>';
  }

  // ---------- 渲染：状态条 ----------
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
    setStat('stat-rows', '行 ■', result.rowsPass, result.rowsTotal,
      result.rowsPass === result.rowsTotal,
      '行 ■ = 本件 1–3 个检验点全 ■ 的交付物行数（◧ / ▢ 行不算）。当前 ' +
      result.rowsPass + '/' + result.rowsTotal + ' 行。');
    setStat('stat-checks', '检验点 ■', result.checksPass, result.checksTotal,
      result.checksPass === result.checksTotal,
      '检验点 ■ = 已建且判据通过的格数（◧ 已建未验不算）。当前 ' +
      result.checksPass + '/' + result.checksTotal + ' 格。');
    var e2e = document.getElementById('stat-e2e');
    e2e.classList.toggle('pass', result.e2ePass);
    e2e.classList.toggle('fail', !result.e2ePass);
    e2e.title = '端到端链 = 第 12 件「端到端链路」的 ' + result.e2eTotal +
      ' 个检验点全 ■；判据：浏览器 :8081 → nginx → :8000 → A4–A8 → MySQL :3307 跑出 41099.5';
    e2e.innerHTML = '<span class="k">端到端链</span><b>' + (result.e2ePass ? '✓' : '✗') + '</b>';
    var stamp = document.getElementById('stamp');
    stamp.hidden = !result.all;
    stamp.title = result.all
      ? '三条全绿：行 ■ ' + result.rowsTotal + '/' + result.rowsTotal + ' · 检验点 ■ ' +
        result.checksTotal + '/' + result.checksTotal + ' · 端到端链 ✓ ⇒ 建成证明'
      : '未全绿：行 ■ ' + result.rowsPass + '/' + result.rowsTotal + ' · 检验点 ■ ' +
        result.checksPass + '/' + result.checksTotal + ' · 端到端链 ' +
        (result.e2ePass ? '✓' : '✗');
    return result;
  }

  function renderNavState() {
    Array.prototype.forEach.call(document.querySelectorAll('#aon [data-activity]'), function (node) {
      node.classList.toggle('is-on', state.navhl === node.getAttribute('data-activity'));
    });
  }

  function renderAll() {
    renderRows();
    renderCards();
    renderStatus();
    renderNavState();
  }

  // ---------- 交互 ----------
  function toggleCard(artId) {
    if (!ART_BY_ID[artId]) { return false; }
    var at = state.open.indexOf(artId);
    var opening = at < 0;
    if (opening) { state.open.push(artId); } else { state.open.splice(at, 1); }
    renderAll();
    if (opening) {
      var card = document.querySelector('.card[data-card="' + artId + '"]');
      if (card && card.scrollIntoView) {
        try { card.scrollIntoView({ block: 'nearest' }); } catch (err) {}
      }
    }
    return true;
  }

  function cycleCheck(artId, index) {
    if (state.mode !== 'blank') { return false; }
    var art = ART_BY_ID[artId];
    if (!art) { return false; }
    var at = Number(index);
    if (!(at >= 1 && at <= art.checkpoints.length)) { return false; }
    var current = checkStatus(art, at - 1);
    state.checks[artId][at - 1] = CYCLE[current] || 'unbuilt';
    persist();
    renderAll();
    var button = document.querySelector('.card[data-card="' + artId + '"] .box' +
      '[data-check="' + artId + '"][data-cp="' + at + '"]');
    if (button && !button.disabled) { button.focus(); }
    return true;
  }

  function resetEdits() {
    if (state.mode !== 'blank') { return; }
    state.checks = blankChecks();
    persist();
    renderAll();
    showToast('已重置：' + TOTAL_CHECKS + ' 个检验点恢复 ▢（行徽章随之 ▢），本机手改进度已清空。');
  }

  function showToast(message) {
    var el = document.getElementById('toast');
    if (!el) { return; }
    el.textContent = message;
    el.hidden = false;
    el.classList.add('show');
    if (showToast.timer) { clearTimeout(showToast.timer); }
    showToast.timer = setTimeout(function () {
      el.classList.remove('show');
      el.hidden = true;
    }, 3600);
  }

  function applyModeUI() {
    var mode = state.mode;
    Array.prototype.forEach.call(document.querySelectorAll('.mode-btn'), function (button) {
      var on = button.getAttribute('data-mode') === mode;
      button.classList.toggle('is-on', on);
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    var hint = document.getElementById('mode-hint');
    if (mode === 'answer') {
      hint.textContent = '答案态（参考答案）：' + TOTAL_CHECKS + ' 个检验点全 ■ → ' +
        ARTS.length + ' 件交付物全 ■、只读；点左侧行开卡，对照「命令 / 期望输出」，' +
        '行与卡顶徽章都是派生结果。';
    } else {
      hint.textContent = '空白态（编辑态）：点卡片里的三态方框，按 ▢ → ◧ → ■ → ▢ 循环；' +
        '行徽章由本件检验点派生、顶部三条判据与印章实时重算。' +
        (STORAGE_OK ? '进度存在本机浏览器（localStorage），可点「重置」清空。'
                    : '本机浏览器不允许存进度，刷新会丢；点「重置」可清空。');
    }
    var reset = document.getElementById('reset');
    reset.disabled = mode !== 'blank';
    reset.title = mode === 'blank'
      ? '把 ' + TOTAL_CHECKS + ' 个检验点全部恢复 ▢（清空本机手改进度）'
      : '答案态无需重置；先切到空白态';
    var note = document.getElementById('edit-note');
    note.hidden = mode !== 'blank';
  }

  function switchMode(mode) {
    if (mode !== 'answer' && mode !== 'blank') { return; }
    if (mode === state.mode) { return; }
    var hadEdits = false;
    ARTS.forEach(function (art) {
      (state.checks[art.id] || []).forEach(function (status) {
        if (status !== 'unbuilt') { hadEdits = true; }
      });
    });
    state.mode = mode;
    state.checks = blankChecks();
    if (mode === 'blank') { persist(); } else { clearSaved(); }
    applyModeUI();
    renderAll();
    if (mode === 'answer') {
      showToast(hadEdits
        ? '已切回答案态：手动改过的检验点已丢弃，恢复全 ■。'
        : '已切回答案态：' + TOTAL_CHECKS + ' 个检验点全 ■、只读预览。');
    }
  }

  // ---------- 事件 ----------
  var rowsHost = document.getElementById('rows');
  rowsHost.addEventListener('click', function (ev) {
    var target = ev.target;
    if (target.closest && target.closest('.row-badge')) { return; }   // 行首徽章只读
    if (target.closest && target.closest('a')) { return; }            // 页签链接跳转
    var row = target.closest ? target.closest('tr.mrow') : null;
    if (!row) { return; }
    toggleCard(row.getAttribute('data-art'));
  });
  rowsHost.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Enter' && ev.key !== ' ') { return; }
    var row = ev.target.closest ? ev.target.closest('tr.mrow') : null;
    if (!row) { return; }
    ev.preventDefault();
    toggleCard(row.getAttribute('data-art'));
  });

  var cardsHost = document.getElementById('cards');
  cardsHost.addEventListener('click', function (ev) {
    var target = ev.target;
    var box = target.closest ? target.closest('[data-check]') : null;
    if (box) {
      cycleCheck(box.getAttribute('data-check'), box.getAttribute('data-cp'));
      return;
    }
    var close = target.closest ? target.closest('[data-close]') : null;
    if (close) { toggleCard(close.getAttribute('data-close')); return; }
    var badge = target.closest ? target.closest('[data-derived-card]') : null;
    if (badge) { return; }                                            // 卡顶徽章只读，不改状态
  });

  document.getElementById('close-all').addEventListener('click', function () {
    state.open = [];
    renderAll();
  });
  document.getElementById('reset').addEventListener('click', resetEdits);
  Array.prototype.forEach.call(document.querySelectorAll('.mode-btn'), function (button) {
    button.addEventListener('click', function () {
      switchMode(button.getAttribute('data-mode'));
    });
  });

  // AON 导航：只高亮左侧对应行，不改任何检验点状态
  document.getElementById('aon').addEventListener('click', function (ev) {
    var node = ev.target.closest ? ev.target.closest('[data-activity]') : null;
    if (!node) { return; }
    var act = node.getAttribute('data-activity');
    state.navhl = (state.navhl === act) ? null : act;
    renderRows();
    renderNavState();
  });

  // ---------- 静态文案 ----------
  // 页眉 kicker 用 D43 口径（data.kicker 仍是 D42 样例阶段「供确认后再全量替换 v1」，
  // 那句在 D43 已完成替换后已过期；标题 / 副标题 / 12×24 内容仍逐字取单源 data.json）
  document.getElementById('kicker').textContent = 'D43 · v2 物料清单式 · 行=交付物（' +
    ARTS.length + ' 件）· 格=检验点（' + TOTAL_CHECKS + ' 个）';
  document.getElementById('title').textContent = DATA.title || '建成证明';
  document.getElementById('subtitle').textContent = DATA.subtitle || '';
  document.getElementById('art-count').textContent = ARTS.length;
  document.getElementById('aon').title = DATA.order_hint || '';
  document.title = (DATA.title || '建成证明') + ' · 可交互';

  // ---------- 调试 / 验收用只读句柄（离线，无副作用） ----------
  window.__EXPLORER__ = {
    data: DATA,
    state: state,
    glyph: GLYPH,
    legend: NAME,
    desc: DESC,
    storageKey: STORAGE_KEY,
    storageOk: STORAGE_OK,
    totalChecks: TOTAL_CHECKS,
    e2eId: E2E_ART ? E2E_ART.id : null,
    activityArts: ACTIVITY_ARTS,
    statusOfCheck: function (artId, index) {
      var art = ART_BY_ID[artId];
      return art ? checkStatus(art, Number(index) - 1) : null;
    },
    statusOfArtifact: function (artId) {
      var art = ART_BY_ID[artId];
      return art ? artifactStatus(art) : null;
    },
    countsOfArtifact: function (artId) {
      var art = ART_BY_ID[artId];
      return art ? countsOf(art) : null;
    },
    deriveLine: function (artId) {
      var art = ART_BY_ID[artId];
      return art ? deriveLine(art) : '';
    },
    compute: compute,
    openCard: function (artId) {
      if (ART_BY_ID[artId] && state.open.indexOf(artId) < 0) {
        state.open.push(artId);
        renderAll();
      }
    },
    closeAll: function () { state.open = []; renderAll(); },
    toggleCard: toggleCard,
    setMode: switchMode,
    cycleCheck: cycleCheck,
    resetEdits: resetEdits,
    setNav: function (act) {
      state.navhl = (state.navhl === act) ? null : act;
      renderRows();
      renderNavState();
    },
    render: renderAll,
    savedRaw: savedRaw
  };

  // ---------- 启动：有空白态本机进度就恢复，否则答案态 ----------
  var savedChecks = readSaved();
  if (savedChecks) {
    state.mode = 'blank';
    state.checks = savedChecks;
  } else {
    state.mode = 'answer';
    state.checks = blankChecks();
  }
  applyModeUI();
  renderCriteria();
  renderAll();
})();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------ 产物静态自检

def check_html(text: str, data: dict) -> dict:
    if DATA_TOKEN in text:
        fail("HTML 里残留占位符 %s：JSON 没内联进去" % DATA_TOKEN)
    if AON_TOKEN in text:
        fail("HTML 里残留占位符 %s：AON 导航没渲染" % AON_TOKEN)
    if "Noto Sans CJK SC" not in text:
        fail("CSS 没有指定中文字体 Noto Sans CJK SC")
    if "DejaVu Sans Mono" not in text:
        fail("命令 / 输出没有指定等宽字体 DejaVu Sans Mono")
    for bad in FORBIDDEN:
        if bad in text:
            fail("产物里出现禁用字符串 %r（不许用户名 / 绝对路径）" % bad)

    marker = '<script id="completeness-data" type="application/json">'
    if text.count(marker) != 1:
        fail("应有且只有一个内联数据 script（%r）" % marker)
    start = text.index(marker) + len(marker)
    end = text.index("</script>", start)
    payload = text[start:end]
    shell = text[:start] + text[end:]
    try:
        embedded = json.loads(payload.replace("<\\/", "</"))
    except json.JSONDecodeError as exc:
        fail("内联 JSON 解析失败：%s" % exc)
    if embedded != data:
        fail("内联进 HTML 的 JSON 与 v2/data.json 不一致")
    if text.count("<script") != 2:
        fail("应只有两段内联 script（数据 + 逻辑），实际 %d 段" % text.count("<script"))

    for bad in EXTERNAL_SHELL:
        if bad in shell:
            fail("静态壳里出现外部资源痕迹 %r（必须离线可用）" % bad)
    for bad in ("data-tri=", "<iframe", "<img", "onclick=", "<input", "type=\"checkbox\""):
        if bad in text:
            fail("产物里出现禁用构件 %r" % bad)
    if re.search(r"<button[^>]*data-derived-(?:row|card)=", text):
        fail("派生徽章被渲染成 button（应为只读 span）")
    if not re.search(r"<span[^>]*data-derived-row=", text):
        fail("缺少行首只读派生徽章 data-derived-row")
    if not re.search(r"<span[^>]*data-derived-card=", text):
        fail("缺少卡顶只读派生徽章 data-derived-card")
    if not re.search(r"<button[^>]*data-check=", text):
        fail("缺少检验点三态方框按钮 data-check")
    if 'class="card"' not in text and "class='card'" not in text and 'class="card ' not in text:
        fail("缺少检验卡模板")
    if "<style" not in text or "<style" in text.split("<body>")[-1]:
        fail("CSS 应内联在 head 里")

    # AON 导航：10 个活动节点，只导航、不可勾选
    if shell.count("data-activity=") != 10:
        fail("AON 导航应有 10 个 data-activity 节点，实际 %d 个" % shell.count("data-activity="))
    if shell.count("data-arts=") != 10:
        fail("AON 导航应有 10 个 data-arts 位置映射，实际 %d 个" % shell.count("data-arts="))
    nav_start = shell.find('id="aon"')
    nav_end = shell.find("</nav>", nav_start)
    nav_html = shell[nav_start:nav_end]
    if nav_start < 0 or nav_end < 0:
        fail("找不到 AON 导航段")
    if "data-check" in nav_html:
        fail("AON 导航里出现了可勾选控件（D43 要求只做位置导航，不参与勾选）")
    if "data-activity=" not in nav_html:
        fail("AON 导航段里没有活动节点")

    # 内部 URL 只允许 127.0.0.1 命令文本（数据内容，不是资源引用）
    urls = URL_RE.findall(payload)
    bad_urls = sorted({url for url in urls if url.split(":")[0] not in ("127.0.0.1", "localhost")})
    if bad_urls:
        fail("内联数据里出现非本机 URL：%r" % bad_urls)
    if "https://" in payload:
        fail("内联数据里出现 https 外链")

    required = [
        "data-derived-row", "data-derived-card", "data-check", "cycleCheck",
        "localStorage", STORAGE_KEY, "由本件", "只读派生", "建成证明 ✓",
        "点一下切下一态", "本机浏览器", "全部关闭", "重置", "AON 流水",
        "物料清单", "检验卡", "行 ■", "检验点 ■", "端到端链", "D43 · v2 物料清单式",
        "完备判据",
    ]
    for needle in required:
        if needle not in text:
            fail("产物缺少 D43 构件 / 文案 %r" % needle)

    return embedded


# ------------------------------------------------------------------ DOM 链路自检（无头 Chrome 真跑）

DOM_CHECK_JS = r"""
<script id="explorer-dom-selfcheck">
(function () {
  'use strict';
  var fails = [];
  var info = {};

  function check(cond, msg) { if (!cond) { fails.push(msg); } }
  function q(sel) { return document.querySelector(sel); }
  function qa(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  function txt(sel) { var el = q(sel); return el ? el.textContent.trim() : '<missing ' + sel + '>'; }
  function api() { return window.__EXPLORER__; }
  function cardCount() { return qa('.card').length; }
  function rowBadge(artId) {
    var el = q('[data-derived-row="' + artId + '"]');
    return el ? { tag: el.tagName, glyph: el.textContent.trim(),
                  status: el.getAttribute('data-status'), title: el.getAttribute('title') || '' } : null;
  }
  function cardBadge(artId) {
    var el = q('.card[data-card="' + artId + '"] [data-derived-card]');
    return el ? { tag: el.tagName, glyph: el.textContent.trim(),
                  status: el.getAttribute('data-status'), title: el.getAttribute('title') || '' } : null;
  }
  function box(artId, index) {
    var el = q('.card[data-card="' + artId + '"] .box[data-check="' + artId +
      '"][data-cp="' + index + '"]');
    return el ? { glyph: el.textContent.trim(), status: el.getAttribute('data-status'),
                  disabled: el.disabled, title: el.getAttribute('title') || '' } : null;
  }
  function clickEl(sel) {
    var el = q(sel);
    if (!el) { fails.push('找不到 ' + sel); return null; }
    el.click();
    return el;
  }
  function clickRow(artId) { return clickEl('tr.mrow[data-art="' + artId + '"]'); }
  function snap() { return JSON.stringify(api().state.checks); }
  function stats() {
    return {
      rows: txt('#stat-rows b'), checks: txt('#stat-checks b'), e2e: txt('#stat-e2e b'),
      stamp: q('#stamp') ? !q('#stamp').hidden : null,
      rowsDom: qa('#material-table tbody tr.mrow').length,
      rowBadges: qa('[data-derived-row]').length,
      cards: cardCount(), cardBadges: qa('.card [data-derived-card]').length,
      boxes: qa('.card .box[data-check]').length,
      disabledBoxes: qa('.card .box[data-check]').filter(function (el) { return el.disabled; }).length,
      aonNodes: qa('#aon [data-activity]').length,
      inputs: qa('input').length
    };
  }
  function expectStats(label, rows, checks, e2e, stamp) {
    var s = stats();
    check(s.rows === rows && s.checks === checks && s.e2e === e2e && s.stamp === stamp,
      label + ' 应为 行 ' + rows + ' · 检验点 ' + checks + ' · 端到端 ' + e2e +
      ' · 印章 ' + stamp + '，实际 行 ' + s.rows + ' · 检验点 ' + s.checks +
      ' · 端到端 ' + s.e2e + ' · 印章 ' + s.stamp);
  }
  function allRows(status, label) {
    qa('[data-derived-row]').forEach(function (el) {
      check(el.getAttribute('data-status') === status && el.textContent.trim() === api().glyph[status],
        label + '：行徽章应 ' + api().glyph[status] + '，实际 ' +
        el.getAttribute('data-derived-row') + '=' + el.textContent.trim());
    });
  }
  function checkPageLinks() {
    var bad = qa('a.pg').map(function (a) { return a.getAttribute('href') || ''; })
      .filter(function (href) { return !/^\.\.\/page-\d{2}\.md$/.test(href); });
    check(bad.length === 0, '页签链接只允许本地相对路径 ../page-0X.md，异常：' + bad.join(' , '));
  }

  function run() {
    var ref = api();
    check(!!ref, '缺少 __EXPLORER__ 验收句柄');
    if (!ref) { return; }
    var ARTS = ref.data.artifacts;
    var total = ARTS.reduce(function (n, art) { return n + art.checkpoints.length; }, 0);
    check(ARTS.length === 12, '交付物应为 12 件，实际 ' + ARTS.length);
    check(total === 24, '检验点应为 24 个，实际 ' + total);
    ARTS.forEach(function (art) {
      check(art.checkpoints.length >= 1 && art.checkpoints.length <= 3,
        '#' + art.no + ' 检验点应 1–3 个，实际 ' + art.checkpoints.length);
    });
    check(ref.storageKey === 'completeness-v2/checks-v1',
      'localStorage 键应为 completeness-v2/checks-v1，实际 ' + ref.storageKey);
    check(ref.e2eId === 'e2e-chain', '端到端链应指向第 12 件 e2e-chain，实际 ' + ref.e2eId);

    // ===== 1) 答案态 =====
    check(ref.state.mode === 'answer', '初始应为答案态');
    var s = stats();
    check(s.rowsDom === 12, '左侧物料表应有 12 行，实际 ' + s.rowsDom);
    check(s.rowBadges === 12, '每行应有一个只读派生徽章，实际 ' + s.rowBadges);
    check(s.inputs === 0, '不应有 input / checkbox，实际 ' + s.inputs);
    check(s.aonNodes === 10, 'AON 导航应有 A0–A9 共 10 个活动，实际 ' + s.aonNodes);
    check(qa('#aon [data-check]').length === 0, 'AON 导航里不应有可勾选控件');
    expectStats('答案态', '12/12', '24/24', '✓', true);
    allRows('built', '答案态');
    check(q('#reset').disabled === true, '答案态「重置」应不可用');
    var firstBadge = q('[data-derived-row]');
    check(firstBadge && firstBadge.tagName === 'SPAN', '行徽章应为只读 span，实际 ' +
      (firstBadge ? firstBadge.tagName : '<missing>'));
    var leftW = q('.left').getBoundingClientRect().width;
    var rightW = q('.right').getBoundingClientRect().width;
    var ratio = leftW / (leftW + rightW);
    check(ratio >= 0.44 && ratio <= 0.51,
      '左栏应占 45–50%，实际 ' + ratio.toFixed(3) + '（左 ' + Math.round(leftW) +
      ' / 右 ' + Math.round(rightW) + ' px）');
    if (ref.storageOk) {
      check(localStorage.getItem('completeness-explorer/cells-v1') === null,
        '不应再使用 v1 的 localStorage 键');
    }

    // 开 3 张卡（3 / 1 / 2 个检验点），验证卡顶派生徽章与响应式网格
    clickRow('env'); clickRow('dw-tables'); clickRow('dw-data');
    s = stats();
    check(s.cards === 3, '点 3 行应同时开 3 张卡，实际 ' + s.cards);
    check(s.cardBadges === 3, '每张卡应有一个只读派生徽章，实际 ' + s.cardBadges);
    check(s.boxes === 6 && s.disabledBoxes === 6,
      '答案态已开卡的 6 个检验点方框应全部只读（disabled），实际 ' +
      s.disabledBoxes + '/' + s.boxes);
    var envBadge = cardBadge('env');
    check(envBadge && envBadge.tag === 'SPAN' && envBadge.status === 'built' &&
      envBadge.glyph === '■', '答案态 env 卡顶徽章应为只读 span ■');
    check(envBadge && envBadge.title.indexOf('由本件 3 个检验点派生：3■ 0◧ 0▢') === 0,
      '答案态 env 卡顶 tooltip 应为「由本件 3 个检验点派生：3■ 0◧ 0▢」，实际 ' +
      (envBadge ? envBadge.title : '<missing>'));
    var envRow = rowBadge('env');
    check(envRow && envRow.title.indexOf('由本件 3 个检验点派生：3■ 0◧ 0▢') === 0,
      '答案态 env 行徽章 tooltip 应写派生数，实际 ' + (envRow ? envRow.title : '<missing>'));
    var c0 = qa('.card')[0].getBoundingClientRect();
    var c1 = qa('.card')[1].getBoundingClientRect();
    check(Math.abs(c0.top - c1.top) < 2 && Math.abs(c0.left - c1.left) > 40,
      '卡片区应为响应式网格（前两张同排并排），实际 top ' + Math.round(c0.top) + '/' +
      Math.round(c1.top) + ' left ' + Math.round(c0.left) + '/' + Math.round(c1.left));
    checkPageLinks();

    // ===== 2) 负向对照：只读徽章 / 答案态点格 / 未知 id 均无效 =====
    var before = snap();
    var beforeCards = cardCount();
    clickEl('[data-derived-row="env"]');
    check(snap() === before, '负向对照：点行首徽章不应改变任何检验点状态');
    check(cardCount() === beforeCards, '负向对照：点行首徽章不应开 / 关卡片');
    var cardTopBadge = q('.card[data-card="env"] [data-derived-card]');
    if (cardTopBadge) { cardTopBadge.click(); }
    check(snap() === before && cardCount() === beforeCards,
      '负向对照：点卡顶派生徽章不应改变状态 / 开卡');
    var envBox = q('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    if (envBox) { envBox.click(); }
    check(snap() === before, '负向对照：答案态点检验点方框不应改变状态');
    check(ref.cycleCheck('env', 1) === false, '负向对照：答案态直接调用 cycleCheck 应返回 false');
    check(ref.cycleCheck('no-such-art', 1) === false, '负向对照：未知交付物 id 应被拒绝');
    check(ref.cycleCheck('env', 99) === false, '负向对照：未知检验点序号 99 应被拒绝');
    check(ref.cycleCheck('env', 0) === false, '负向对照：检验点序号 0 应被拒绝');
    check(ref.toggleCard('no-such-art') === false, '负向对照：未知 id 不应开卡');
    check(cardCount() === beforeCards, '负向对照后卡片数应不变');

    // AON 导航：只高亮，不勾选
    var navBefore = snap();
    clickEl('#aon [data-activity="A2"]');
    var highlighted = qa('tr.mrow.is-navhl').map(function (row) {
      return row.getAttribute('data-art');
    });
    check(highlighted.length === 2 && highlighted.indexOf('dw-tables') >= 0 &&
      highlighted.indexOf('dw-data') >= 0,
      '点 A2 应只高亮 dw-tables / dw-data 两行，实际 [' + highlighted.join(', ') + ']');
    check(snap() === navBefore, '负向对照：AON 导航点击不应改变检验点状态');
    check(ref.state.navhl === 'A2', 'AON 导航应记录当前高亮活动 A2');
    clickEl('#aon [data-activity="A2"]');
    check(qa('tr.mrow.is-navhl').length === 0, '再点同一活动应取消行高亮');
    check(snap() === navBefore, '负向对照：取消导航高亮不应改变检验点状态');

    // 行再点关闭 / 再开
    clickRow('dw-tables');
    check(cardCount() === 2, '再点已开行应关闭该卡，实际 ' + cardCount());
    clickRow('dw-tables');
    check(cardCount() === 3, '再点应重新开卡，实际 ' + cardCount());

    // ===== 3) 空白态：全 ▢、可编辑、写本机进度 =====
    clickEl('.mode-btn[data-mode="blank"]');
    check(ref.state.mode === 'blank', '应切到空白态');
    expectStats('空白态初始', '0/12', '0/24', '✗', false);
    allRows('unbuilt', '空白态');
    s = stats();
    check(s.boxes === 6 && s.disabledBoxes === 0,
      '空白态已开 3 张卡里的 6 个方框都应可编辑，实际 ' + s.disabledBoxes + '/' + s.boxes);
    check(q('#reset').disabled === false, '空白态「重置」应可用');
    check(txt('#mode-hint').indexOf('本机浏览器') >= 0, '空白态提示应注明进度存本机浏览器');
    if (ref.storageOk) {
      var raw = ref.savedRaw();
      check(typeof raw === 'string' && raw.indexOf('"mode":"blank"') >= 0 &&
        raw.indexOf('"v":1') >= 0,
        '切到空白态应写入 localStorage 进度（键 completeness-v2/checks-v1）');
    }

    // ===== 4) 主链路：改一格 → 行 ◧ → 计数变化 → 其余格 ■ 后行 ■ =====
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    var env1 = box('env', 1);
    check(env1 && env1.status === 'unverified' && env1.glyph === '◧',
      'env 第 1 格点一下应 ▢ → ◧');
    check(box('env', 2).status === 'unbuilt' && box('env', 3).status === 'unbuilt',
      'env 第 2 / 3 格应仍 ▢');
    envRow = rowBadge('env');
    check(envRow && envRow.status === 'unverified' && envRow.glyph === '◧',
      '一格 ◧ 时行徽章应派生 ◧');
    check(txt('#stat-rows b') === '0/12', '一格 ◧ 时行 ■ 应仍 0/12，实际 ' + txt('#stat-rows b'));
    check(txt('#stat-checks b') === '0/24', '◧ 不计入检验点 ■，应仍 0/24，实际 ' + txt('#stat-checks b'));
    check(cardBadge('env').title.indexOf('由本件 3 个检验点派生：0■ 1◧ 2▢') === 0,
      '卡顶 tooltip 应 0■ 1◧ 2▢，实际 ' + cardBadge('env').title);
    check(stats().stamp === false, '只有 1 格 ◧ 时不应显示建成证明印章');

    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="2"]');
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="3"]');
    check(rowBadge('env').status === 'unverified', '三格 ◧◧◧ 时行仍 ◧');
    check(txt('#stat-checks b') === '0/24', '三格全 ◧ 时检验点 ■ 仍 0/24');
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    check(rowBadge('env').status === 'unverified', '两格 ◧、一格 ■ 时行仍 ◧');
    check(txt('#stat-checks b') === '1/24',
      '一格 ■ 后检验点 ■ 应 1/24，实际 ' + txt('#stat-checks b'));
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="2"]');
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="3"]');
    check(ref.statusOfArtifact('env') === 'built', 'env 三格全 ■ 后行应派生 ■');
    envRow = rowBadge('env');
    check(envRow && envRow.status === 'built' && envRow.glyph === '■', '行徽章应 ■');
    check(txt('#stat-rows b') === '1/12', '一行全 ■ 后行 ■ 应 1/12，实际 ' + txt('#stat-rows b'));
    check(txt('#stat-checks b') === '3/24', '三格 ■ 后检验点 ■ 应 3/24，实际 ' + txt('#stat-checks b'));
    check(ref.countsOfArtifact('env').built === 3, 'env 计数应为 3■');
    check(txt('#stat-e2e b') === '✗', 'env 全 ■ 不等于端到端链，端到端应仍 ✗');
    check(stats().stamp === false, '未满 12 行不应显示建成证明印章');

    // 三态循环必须闭环：■ 再点一下回 ▢，再点两下回到 ■
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    var back = box('env', 1);
    check(back && back.status === 'unbuilt' && back.glyph === '▢',
      '■ 再点一下应回 ▢（循环 ▢ → ◧ → ■ → ▢）');
    check(txt('#stat-rows b') === '0/12' && txt('#stat-checks b') === '2/24',
      '■ → ▢ 后行 / 检验点计数应回退（0/12 · 2/24），实际 ' +
      txt('#stat-rows b') + ' · ' + txt('#stat-checks b'));
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    check(ref.statusOfArtifact('env') === 'built' && txt('#stat-checks b') === '3/24',
      '再点两下应回到 env 全 ■（3/24）');

    // 端到端链 = 第 12 件「端到端链路」全部检验点 ■
    clickRow('e2e-chain');
    clickEl('.card[data-card="e2e-chain"] .box[data-check="e2e-chain"][data-cp="1"]');
    clickEl('.card[data-card="e2e-chain"] .box[data-check="e2e-chain"][data-cp="1"]');
    clickEl('.card[data-card="e2e-chain"] .box[data-check="e2e-chain"][data-cp="2"]');
    clickEl('.card[data-card="e2e-chain"] .box[data-check="e2e-chain"][data-cp="2"]');
    check(ref.statusOfArtifact('e2e-chain') === 'built', 'e2e-chain 两格全 ■ 后应为 ■');
    check(txt('#stat-e2e b') === '✓', '端到端链应为 ✓，实际 ' + txt('#stat-e2e b'));
    check(txt('#stat-rows b') === '2/12', '2 行全 ■ 时应 2/12，实际 ' + txt('#stat-rows b'));
    check(txt('#stat-checks b') === '5/24', '5 格 ■ 时应 5/24，实际 ' + txt('#stat-checks b'));
    check(stats().stamp === false, '只有 2 行 ■ 时不应出印章（印章要 12 行全绿）');

    // ===== 5) 重置 / 切回答案态丢弃手改 =====
    clickEl('#reset');
    expectStats('重置后', '0/12', '0/24', '✗', false);
    allRows('unbuilt', '重置后');
    check(ref.statusOfArtifact('env') === 'unbuilt' && ref.statusOfArtifact('e2e-chain') === 'unbuilt',
      '重置后 env / e2e-chain 应回 ▢');
    if (ref.storageOk) {
      check(ref.savedRaw() !== null, '重置后仍处于空白态（本机存的是全 ▢ 进度）');
    }
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    check(ref.statusOfArtifact('env') === 'unverified', '重置后应能再次编辑（env 一格 ◧）');
    clickEl('.mode-btn[data-mode="answer"]');
    check(ref.state.mode === 'answer', '应切回答案态');
    expectStats('切回答案态', '12/12', '24/24', '✓', true);
    allRows('built', '切回答案态');
    s = stats();
    check(s.disabledBoxes === s.boxes && s.boxes > 0, '答案态所有方框应恢复只读');
    if (ref.storageOk) {
      check(ref.savedRaw() === null, '切回答案态应清掉 localStorage 进度（丢弃手改）');
    }
    check(txt('#toast').indexOf('丢弃') >= 0,
      '切回答案态应提示「丢弃手改」，实际 toast：' + txt('#toast'));
    clickEl('.mode-btn[data-mode="blank"]');
    expectStats('再切空白态', '0/12', '0/24', '✗', false);
    check(ref.statusOfArtifact('env') === 'unbuilt', '再切空白态时先前手改应已丢弃（全 ▢）');
    // 留一格 ■ 在本机进度里，供第二阶段（刷新恢复）验证（env 有 3 格 → 恢复后行应 ◧）
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    clickEl('.card[data-card="env"] .box[data-check="env"][data-cp="1"]');
    check(ref.statusOfCheck('env', 1) === 'built', '刷新前应在 env 第 1 格留下 ■');
    if (ref.storageOk) {
      check((ref.savedRaw() || '').indexOf('"built"') >= 0,
        '可恢复的 ■ 进度应已写进 localStorage');
    }

    info = {
      rows: txt('#stat-rows b'), checks: txt('#stat-checks b'), e2e: txt('#stat-e2e b'),
      rowsDom: stats().rowsDom, boxes: qa('.box[data-check]').length,
      cards: cardCount(), storageOk: !!ref.storageOk
    };
  }

  function finish() {
    var pass = fails.length === 0;
    var marker = 'DOM_SELF' + 'CHECK_';
    document.title = marker + (pass ? 'PASS' : 'FAIL') +
      (pass ? '' : ' ' + fails.slice(0, 8).join(' || '));
    var pre = document.createElement('pre');
    pre.id = 'explorer-dom-selfcheck';
    pre.textContent = (pass ? 'PASS' : 'FAIL') + '\n' + fails.join('\n') + '\n' +
      JSON.stringify(info);
    document.body.appendChild(pre);
  }
  function start() {
    try { run(); } catch (err) {
      fails.push('异常：' + (err && err.message ? err.message : err));
    }
    finish();
  }
  if (document.readyState === 'complete') { start(); }
  else { window.addEventListener('load', start); }
})();
</script>
"""


DOM_RESTORE_JS = r"""
<script id="explorer-dom-restore">
(function () {
  'use strict';
  var fails = [];
  function check(cond, msg) { if (!cond) { fails.push(msg); } }
  function txt(sel) { var el = document.querySelector(sel); return el ? el.textContent.trim() : '<missing ' + sel + '>'; }
  function go() {
    try {
      var E = window.__EXPLORER__;
      check(!!E, '缺少 __EXPLORER__ 验收句柄');
      if (!E) { return; }
      check(E.state.mode === 'blank', '刷新恢复后应仍为空白态，实际 ' + E.state.mode);
      check(E.statusOfCheck('env', 1) === 'built',
        'env 第 1 格应从 localStorage 恢复为 ■，实际 ' + E.statusOfCheck('env', 1));
      check(E.statusOfArtifact('env') === 'unverified',
        'env 行应派生 ◧，实际 ' + E.statusOfArtifact('env'));
      check(txt('#stat-rows b') === '0/12', '恢复后行 ■ 应 0/12，实际 ' + txt('#stat-rows b'));
      check(txt('#stat-checks b') === '1/24', '恢复后检验点 ■ 应 1/24，实际 ' + txt('#stat-checks b'));
      var badge = document.querySelector('[data-derived-row="env"]');
      check(!!badge && badge.textContent.trim() === '◧',
        '恢复后 env 行徽章应为 ◧，实际 ' + (badge ? badge.textContent.trim() : '<missing>'));
    } catch (err) {
      fails.push('异常：' + (err && err.message ? err.message : err));
    }
    var pass = fails.length === 0;
    document.title = 'DOM_RESTORE_' + (pass ? 'PASS' : 'FAIL');
    var pre = document.createElement('pre');
    pre.id = 'explorer-dom-restore';
    pre.textContent = (pass ? 'PASS' : 'FAIL') + '\n' + fails.join('\n');
    document.body.appendChild(pre);
  }
  if (document.readyState === 'complete') { go(); }
  else { window.addEventListener('load', go); }
})();
</script>
"""


def find_chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return ""


def run_chrome(chrome: str, work: Path, page: Path, extra: list[str]) -> subprocess.CompletedProcess:
    cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
           "--disable-dev-shm-usage", "--virtual-time-budget=6000",
           "--user-data-dir=%s" % (work / "chrome-profile")] + extra + [page.as_uri()]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=240,
                          encoding="utf-8", errors="replace")


def check_dom(text: str) -> None:
    chrome = find_chrome()
    if not chrome:
        print("  ⚠ 未找到 google-chrome / chromium，跳过 DOM 链路自检（静态断言仍然生效）")
        return
    with tempfile.TemporaryDirectory(prefix="explorer-domcheck-") as tmp:
        work = Path(tmp)
        page = work / "explorer-selfcheck.html"
        window = ["--window-size=%d,%d" % (SHOT_W, SHOT_H), "--dump-dom"]

        def run_page(script: str) -> str:
            page.write_text(text.replace("</body>", script + "\n</body>"), encoding="utf-8")
            proc = run_chrome(chrome, work, page, window)
            return proc.stdout or ""

        # 阶段 1：交互链路 + 负向对照
        dom = run_page(DOM_CHECK_JS)
        if not ("DOM_SELFCHECK_PASS" in dom and '<pre id="explorer-dom-selfcheck">PASS' in dom):
            match = re.search(r"<title>(DOM_SELFCHECK_FAIL[^<]*)</title>", dom)
            detail = match.group(1) if match else (dom[-2500:] or "chrome 无输出")
            fail("DOM 链路自检未通过：%s" % detail)
        info_match = re.search(
            r'<pre id="explorer-dom-selfcheck">PASS[^<]*?(\{[^<]*\})</pre>', dom)
        storage_ok = True
        if info_match:
            try:
                storage_ok = bool(json.loads(info_match.group(1)).get("storageOk"))
            except (json.JSONDecodeError, AttributeError):
                pass

        # 阶段 2：同一个 Chrome profile 再开一次 → localStorage 进度应恢复（刷新等价）
        restored = False
        if storage_ok:
            dom2 = run_page(DOM_RESTORE_JS)
            if not ("DOM_RESTORE_PASS" in dom2
                    and '<pre id="explorer-dom-restore">PASS' in dom2):
                match = re.search(r"<title>(DOM_RESTORE_FAIL[^<]*)</title>", dom2)
                detail = match.group(1) if match else (dom2[-2500:] or "chrome 无输出")
                fail("DOM 刷新恢复自检未通过：%s" % detail)
            restored = True

    ok("DOM 链路自检（无头 Chrome 真跑）：答案态 12/12 · 24/24 · 端到端 ✓；"
       "点一格 → 行 ◧、计数不变 → 同件其余格 ■ 后行 ■、计数变化 → "
       "端到端 ✓ 但 12 行不全不出印章 → 重置回 ▢ → 切答案态恢复全 ■；"
       "含负向对照（行 / 卡顶只读徽章、答案态点格、未知 id、AON 导航只高亮）"
       + ("；本机进度刷新恢复 ✓（键 %s）" % STORAGE_KEY if restored else "；本机进度不可用，跳过刷新恢复"))


# ------------------------------------------------------------------ 验证截图

SHOT_JS = r"""
<script id="explorer-shot-setup">
(function () {
  'use strict';
  function go() {
    try {
      var E = window.__EXPLORER__;
      if (!E) { document.title = 'SHOT_FAIL|no-api'; return; }
      __SETUP__
      var result = E.compute();
      var stamp = document.getElementById('stamp');
      var badge = '';
      if (E.state.open.length) {
        var el = document.querySelector('.card[data-card="' + E.state.open[0] +
          '"] [data-derived-card]');
        badge = el ? el.textContent.trim() : '';
      }
      document.title = 'SHOT_READY|mode=' + E.state.mode +
        '|rows=' + result.rowsPass + '/' + result.rowsTotal +
        '|checks=' + result.checksPass + '/' + result.checksTotal +
        '|e2e=' + (result.e2ePass ? '✓' : '✗') +
        '|stamp=' + (stamp && !stamp.hidden ? '1' : '0') +
        '|cards=' + E.state.open.length + '|badge=' + badge;
    } catch (err) {
      document.title = 'SHOT_FAIL|' + (err && err.message ? err.message : err);
    }
  }
  if (document.readyState === 'complete') { go(); }
  else { window.addEventListener('load', go); }
})();
</script>
"""


def generate_shots(text: str) -> None:
    chrome = find_chrome()
    if not chrome:
        print("  ⚠ 未找到 google-chrome / chromium，跳过验证截图（静态 / DOM 自检仍然生效）")
        return
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, desc, shot_w, shot_h, setup in SHOTS:
        with tempfile.TemporaryDirectory(prefix="explorer-shot-") as tmp:
            work = Path(tmp)
            page = work / "shot.html"
            page.write_text(text.replace("</body>",
                                         SHOT_JS.replace("__SETUP__", setup) + "\n</body>"),
                            encoding="utf-8")
            # 1) 先用 dump-dom 真跑注入脚本，确认状态与关键数字（截图前的事实依据）
            probe = run_chrome(chrome, work, page,
                               ["--window-size=%d,%d" % (shot_w, shot_h), "--dump-dom"])
            dom = probe.stdout or ""
            match = re.search(r"<title>(SHOT_(?:READY|FAIL)[^<]*)</title>", dom)
            title = match.group(1) if match else ""
            if not title.startswith("SHOT_READY"):
                fail("截图 %s 的状态注入失败：%s" %
                     (filename, title or ((probe.stderr or dom or "")[-1500:])))
            info = {}
            for part in title.split("|")[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    info[key] = value
            # 2) 真截图（同一注入脚本）
            shot = work / "shot.png"
            cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                   "--disable-dev-shm-usage", "--force-device-scale-factor=%d" % SHOT_SCALE,
                   "--window-size=%d,%d" % (shot_w, shot_h),
                   "--virtual-time-budget=6000",
                   "--user-data-dir=%s" % (work / "shot-profile"),
                   "--screenshot=%s" % shot, page.as_uri()]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240,
                                  encoding="utf-8", errors="replace")
            if not shot.exists() or shot.stat().st_size == 0:
                fail("截图 %s 失败：%s" % (filename, (proc.stderr or proc.stdout)[-1500:]))
            width, height = png_size(shot)
            if (width, height) != (shot_w * SHOT_SCALE, shot_h * SHOT_SCALE):
                fail("截图 %s 尺寸 %dx%d，应为 %dx%d"
                     % (filename, width, height, shot_w * SHOT_SCALE, shot_h * SHOT_SCALE))
            (SHOT_DIR / filename).write_bytes(shot.read_bytes())
            print("  ✓ %s  %d×%d  %s · 行 %s · 检验点 %s · 端到端 %s · 印章 %s · 卡片 %s 张 · 首卡徽章 %s"
                  % (filename, width, height, desc, info.get("rows", "?"),
                     info.get("checks", "?"), info.get("e2e", "?"),
                     "显示" if info.get("stamp") == "1" else "隐藏",
                     info.get("cards", "?"), info.get("badge", "?")))


# ------------------------------------------------------------------ 主流程

def build(shots_enabled: bool) -> None:
    print("《建成证明》v2 · 可交互原型：v2/data.json → explorer.html（单文件 / 零依赖 / 离线）")
    data = load_data()
    validate_data(data)
    flow = load_flow()
    check_flow(data, flow)

    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    text = TEMPLATE.replace(AON_TOKEN, aon_nav_html(data, flow)).replace(DATA_TOKEN, payload)
    embedded = check_html(text, data)
    if embedded != data:
        fail("内联进 HTML 的 JSON 与 data.json 不一致")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    size = OUT_PATH.stat().st_size
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if size < 30000:
        fail("产物只有 %d 字节，像是模板没渲染" % size)
    local_urls = len(URL_RE.findall(payload))
    ok("产物自检：无外链 / 无外字体 / 无图片 / 无 fetch / 无用户名与绝对路径"
       "（数据内 %d 处 URL 均为 127.0.0.1 命令文本）" % local_urls)
    ok("产物构件：物料清单 12 行 · 只读派生行徽章 · 卡顶派生徽章 · 检验点三态方框 · "
       "AON 位置导航 · 答案/空白态 · 重置 · localStorage（%s）" % STORAGE_KEY)
    ok("内联 JSON 与 v2/data.json 逐字节等价（%d 字节数据）" % len(payload.encode("utf-8")))
    print("  输出：%s  %d 字节（%.1f KB）  sha256 %s"
          % (OUT_PATH.relative_to(REPO), size, size / 1024.0, digest[:16]))

    check_dom(text)
    if shots_enabled:
        generate_shots(text)
    else:
        print("  提示：加 --shots 可重出 3 张验证截图（manual/review/explorer-shots/v2-*.png）")
    print("完成：一个文件即可离线双击打开，不发起任何网络请求。"
          "（重跑：python3 manual/shots/build_explorer.py%s）"
          % (" --shots" if not shots_enabled else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="由 v2 单源 data.json 生成《建成证明》可交互原型 explorer.html")
    parser.add_argument("--shots", action="store_true",
                        help="同时生成 3 张验证截图到 manual/review/explorer-shots/")
    args = parser.parse_args(argv)
    build(shots_enabled=args.shots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
