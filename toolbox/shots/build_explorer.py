#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_explorer.py —— 由 v2 单源 data.json + city/data.json 生成《建成证明》可交互原型 explorer.html。

在仓库根目录一条命令重跑：

    python3 tutorial/shots/build_explorer.py                      # 生成 explorer.html + 静态 / DOM 自检
    python3 tutorial/shots/build_explorer.py --shots              # 另出 4 张验证截图（v2-01/02/03 + v3-01）
    python3 tutorial/shots/build_explorer.py --shots --shot v3-01 # 只重出城市地图那张截图

依据 `materials/humen-desicions/09-ablation-course.md` 的 **D39 / D40 / D41 / D42 / D43**（物料清单视图）
与 **D44 / D45**（城市地图视图）：
D39 中分视图（左材料总览、右可多开卡片）；D40 编辑入口只在卡片上、总览只读派生；
D41 状态粒度下沉到「一格一状态」；D42 行=交付物、格=检验点（1–3 个、命令+期望输出）；
D43 交互页改吃 v2 单源、行状态由检验点派生、保留一条只做位置导航的 AON 流水条；
D44 四级 + D50 追加 L5 装 = 五种工程动作（造→换→审→守→装）；D45 主隐喻换成城市（4 区 / 10 设施 / 真楼嵌套，
粒度表见 GLOSSARY.md），L1 十个设施 ↔ 十页。

它做六件事：

1. **读单源**：物料清单只读 `tutorial/completeness/v2/data.json`（12 件交付物 × 24 个检验点）；
   城市地图只读 `tutorial/city/data.json`（4 区 / 10 设施 P0–P9，P2→P1、P4–P8→P3 真楼嵌套 /
   11 条道路 / 23 页标题 / 12 件交付物编号），交付物名字逐字取 v2 data；
   五阶段口径统一到 `tutorial/city/data-24.json` 的 `levels`（D50 正典；level / theme / pages / count / desc
   的唯一事实源）；`tutorial/city/stages-city.json` 存在时只补城市说法 name / subtitle，其
   level / action / theme / pages 必须与 levels 逐字一致，不存在时 name 用 D44 文字回退；
   页标题运行期从 `tutorial/page-0X.md` 的 H1 读（不手写）。
2. **数据一致性自检**：v2 12 件 / 每件 1–3 个检验点 / 合计 24 / id 唯一 / 依赖无环 /
   页与行号可解析；城市 4 区非空 / 10 设施 P0–P9 / parent 合法（存在、同区、只一层、父级是楼）/
   12 件交付物各一次 / 10 页页标题与 md H1 逐字一致 / 五阶段 5 段。
3. **flow.mmd 交叉核对**：解析 A0–A9 活动名与 FS 紧前关系；核对 12 件交付物 → A0–A9 位置映射；
   导航只取位置，**不参与勾选**。
4. **内联**：两份 JSON 原样内联进单文件 HTML，AON 导航条由生成器静态渲染；
   产物零外部请求、可离线双击打开。
5. **自检产物 + DOM 链路真跑**（无头 Chrome）：
   - 静态：物料清单全部原有断言保留；城市地图 4 区 / 10 设施 / parent / 10 页卡 /
     页标题逐字对 md / 12 件交付物 / 五阶段只读 / 无外链、无外部资源痕迹。
   - DOM 物料清单：答案态 12/12 · 24/24 · 端到端 ✓ → 三态编辑 → 重置 / 恢复 / 负向对照。
   - DOM 城市地图：默认物料清单 → 切「城市地图」→ 4 区 / 10 设施 / 10 页卡齐、标题逐字对上、
     点设施↔页卡双向高亮、选中卡滚入视野、配对条逐字（P4 ↔ 第 4 页 · 长出 ⑥）、
     城市五阶段只读、零外部请求、联动不改物料清单勾选 / 答案空白态。
6. **两个视图**：
   物料清单（默认）——行=交付物，检验点三态 ▢/◧/■ 可编辑、行状态派生、AON 只定位；
   城市地图——顶部 `物料清单 / 城市地图` 切换。左列按 4 区分组的 10 个设施（区名 + 设施城市名 +
   问题句；楼内房间标「楼内 · 属于 P1/P3」）；右列 10 张页卡（页码 + 运行期 H1 +
   「这一页造什么」（city data 的 solution/soft）+ 长出交付物圆牌 + `../page-0X.md` 相对链接）；
   点设施 → 同号页卡高亮并滚入视野，点页卡 → 同号设施高亮；顶部配对条；底部城市五阶段条只读。

依赖：python3；DOM 自检与截图需要本机 `google-chrome`（或 `chromium`）。截图用
`--force-device-scale-factor=2`：v2-01 / v2-03 为 1600×1050 视口（→ 3200×2100），v2-02 加高到
1600×1320（→ 3200×2640）以便 3 张卡都完整入镜；v3-01 为城市地图，1600×1000 视口（→ 3200×2000），
状态是点 P4 后第 4 页页卡高亮。
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

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
MANUAL = REPO / "manual"
DATA_PATH = MANUAL / "completeness" / "v2" / "data.json"
FLOW_MMD = MANUAL / "flow.mmd"
OUT_PATH = MANUAL / "completeness" / "explorer.html"
SHOT_DIR = MANUAL / "review" / "explorer-shots"

SHOT_W, SHOT_H = 1600, 1050                     # 默认截图视口（CSS px）；--shots 各张可单独指定高
SHOT_SCALE = 2                                  # → 3200×2100 PNG（v2-02 更高以容纳 3 张卡）
CITY_DOM_W, CITY_DOM_H = 900, 720                # 城市地图 DOM 自检视口：故意小，逼出左右两列真滚动

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
CITY_TOKEN = "__CITY_JSON__"

# 城市地图（4 区 / 10 设施 ↔ 10 页）的数据源与口径（D45：真楼嵌套）
CITY_DATA_PATH = MANUAL / "city" / "data.json"           # 单源：4 区 / 10 设施 / 11 路 / 23 标题 / 12 件
CITY_24_PATH = MANUAL / "city" / "data-24.json"          # D50 正典：五级 levels（前 4 级与冻结 data.json 逐字对账）
CITY_STAGES_PATH = MANUAL / "city" / "stages-city.json"  # 只补阶段城市名 / subtitle（可部分覆盖，L5 回退）；计数口径以 levels 为准
CITY_PAGES = ["page-%02d" % i for i in range(10)]        # 与 page-0X.md 文件名一一对应
CITY_SCHEMA = "explorer-city/1"
STAGE_ORDER = ["L1", "L2", "L3", "L4", "L5"]
# 城市五阶段名（D44 四种工程动作 + D50 追加 L5 装 → 城市说法；stages-city.json 缺省时用这段文字）
CITY_STAGE_NAMES = ("荒地工地", "通水电网", "智慧城市", "城市安防", "精装交付")
CITY_STAGE_ACTIONS = ("造", "换", "审", "守", "装")

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
    ("v3-01-cityview.png", "城市地图视图：点 P4 → 第 4 页页卡高亮", 1600, 1000,
     "E.setView('city'); E.citySelect(4);"),
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


# ------------------------------------------------------------------ 城市地图模型（4 区 / 10 设施 ↔ 10 页）

def load_json(path: Path, what: str) -> dict:
    if not path.exists():
        fail("缺 %s（%s）" % (path.relative_to(REPO), what))
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("%s 不是合法 JSON：%s" % (path.relative_to(REPO), exc))
    if not isinstance(obj, dict):
        fail("%s 顶层必须是对象" % path.relative_to(REPO))
    return obj


def read_page_title(page_id: str) -> str:
    """运行期从 page-0X.md 读 H1（不手写页标题；这是城市地图页标题的唯一来源）。"""
    path = page_file(page_id)
    if not path.exists():
        fail("缺页文件 %s.md（页标题要运行期从它读）" % page_id)
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    fail("%s.md 里找不到 H1（一级标题）" % page_id)
    return ""


def build_city_stages(city_data: dict) -> tuple[list[dict], str]:
    """城市五阶段条（只读，不参与勾选）。口径统一（避免两份单源漂移）：

    - **level / theme / pages / count / desc 一律以 `tutorial/city/data-24.json` 的 `levels` 为准**
      （D50 后全书 24 页五级的正典单源；count = 本阶段页数，第一段显示 0/设施数 = 还没造）。
      冻结的 `tutorial/city/data.json` 只供 L1 几何，其 levels（前 4 级）必须与 24 单源逐字一致。
    - `tutorial/city/stages-city.json` 只补「城市说法」：name（阶段城市名）与 subtitle；
      按 level 代码匹配（可部分覆盖，L5 缺省时回退），其 level / action / theme / pages
      必须与 levels 逐字一致，不一致直接报错，不做静默覆盖。
      （stages-city.json 的 badges.label 是「12 件交付物」口径，与本条「N 页」口径不同，见下。）
    - 某阶段在 stages-city.json 缺省时，name 用 D44+D50 文字回退（CITY_STAGE_NAMES），sub 由 levels 拼。
    """
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    doc24 = load_json(CITY_24_PATH, "city/data-24.json（五级 levels 正典）")
    levels = doc24.get("levels") or []
    need(isinstance(levels, list) and len(levels) == 5,
         "city/data-24.json 应有 5 个 level（L1–L5），实际 %r"
         % (len(levels) if isinstance(levels, list) else levels))
    levels = levels if isinstance(levels, list) else []
    need(levels[:4] == (city_data.get("levels") or []),
         "city/data-24.json 前 4 级与冻结的 city/data.json levels 不逐字一致（漂移）")
    level_by_code: dict[str, dict] = {}
    for idx, level in enumerate(levels):
        raw = str(level.get("level") or "")
        code = raw.split()[0] if raw else ""
        need(code == STAGE_ORDER[idx] if idx < len(STAGE_ORDER) else False,
             "city/data-24.json 第 %d 个 level 应为 %r，实际 %r"
             % (idx + 1, STAGE_ORDER[idx] if idx < len(STAGE_ORDER) else "?", raw))
        for key in ("theme", "pages", "desc"):
            need(bool(str(level.get(key, "")).strip()),
                 "city/data-24.json 的 level %r 缺 %s" % (raw, key))
        need(isinstance(level.get("count"), int),
             "city/data-24.json 的 level %r 的 count 应为整数" % raw)
        if code in STAGE_ORDER:
            level_by_code[code] = level

    action = dict(zip(STAGE_ORDER, CITY_STAGE_ACTIONS))
    city_names: dict[str, str] = {}
    city_subs: dict[str, str] = {}
    source = "D44 文字（stages-city.json 不存在）"
    if CITY_STAGES_PATH.exists():
        source = "tutorial/city/stages-city.json"
        raw_doc = load_json(CITY_STAGES_PATH, "城市五阶段（城市名 / 副标题）")
        raw_stages = raw_doc.get("stages")
        if not isinstance(raw_stages, list):
            raw_stages = raw_doc if isinstance(raw_doc, list) else []
        need(len(raw_stages) in (4, 5),
             "stages-city.json 应有 4 或 5 个阶段（L5 可缺省回退），实际 %d 个" % len(raw_stages))
        seen_codes: list[str] = []
        for idx, stage in enumerate(raw_stages):
            level = str(stage.get("level") or stage.get("id") or "")
            code = level.split()[0] if level else ""
            need(code in STAGE_ORDER and code not in seen_codes,
                 "stages-city.json 第 %d 个阶段 level 应在 L1–L5 且不重复，实际 %r"
                 % (idx + 1, level))
            seen_codes.append(code)
            name = str(stage.get("name") or "").strip()
            sub = str(stage.get("subtitle") or "").strip()
            need(bool(name), "stages-city.json 第 %d 个阶段缺 name（城市名）" % (idx + 1))
            level_data = level_by_code.get(code)
            if level_data is not None:
                need(str(stage.get("action") or "") == action[code],
                     "stages-city.json 第 %d 个阶段 action 应为 %r，实际 %r"
                     % (idx + 1, action[code], stage.get("action")))
                for key in ("theme", "pages"):
                    mine = str(stage.get(key) or "")
                    want = str(level_data.get(key) or "")
                    need(mine == want,
                         "stages-city.json 第 %d 个阶段 %s 与 city/data-24.json levels 不一致"
                         "（%r ≠ %r；以 levels 为准）" % (idx + 1, key, mine, want))
            if code:
                city_names[code] = name
                city_subs[code] = sub

    total = len(city_data.get("facilities") or [])
    stages: list[dict] = []
    for idx, level in enumerate(levels):
        code = STAGE_ORDER[idx]
        n = int(level.get("count") or 0)
        stages.append({
            "level": code,
            "name": city_names.get(code) or CITY_STAGE_NAMES[idx],
            "count": ("0/%d" % total) if idx == 0 else ("%d 页" % n),
            "sub": city_subs.get(code) or
                   ("%s · %s · %s" % (action[code], level.get("theme"), level.get("pages"))),
            "desc": str(level.get("desc") or ""),
        })

    need(len(stages) == 5, "城市五阶段应恰好 5 段，实际 %d 段" % len(stages))
    if errs:
        print("✗ 城市五阶段校验失败（%d 条）：" % len(errs))
        for err in errs:
            print("  - " + err)
        raise SystemExit(1)
    return stages, source


def build_city_model(data: dict, city_data: dict) -> dict:
    """把 city/data.json（4 区 / 10 设施 / 真楼嵌套 / 12 件交付物编号）+ page-0X.md 的 H1
    + v2 data 的交付物名字，合成内联进 HTML 的城市地图模型；任何一条对不上就退出。"""
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    # ---- city/data.json 顶层 ----
    need(city_data.get("schema") == "manual-city/1",
         "city/data.json schema 应为 manual-city/1，实际 %r" % city_data.get("schema"))
    need(city_data.get("decision") == "D45",
         "city/data.json decision 应为 D45（城市隐喻真楼嵌套），实际 %r" % city_data.get("decision"))
    for key in ("title", "kicker", "one_liner"):
        need(bool(str(city_data.get(key, "")).strip()), "city/data.json 缺 %s" % key)

    # ---- 4 区 ----
    zones = city_data.get("zones")
    need(isinstance(zones, list) and len(zones) == 4,
         "city/data.json 应有 4 个区，实际 %r 个"
         % (len(zones) if isinstance(zones, list) else zones))
    zones = zones if isinstance(zones, list) else []
    zone_ids: list[str] = []
    for idx, zone in enumerate(zones):
        tag = "城市第 %d 区" % (idx + 1)
        zid = str(zone.get("id") or "")
        need(bool(SLUG_RE.match(zid)), "%s 的 id %r 不是小写 slug" % (tag, zid))
        need(zid not in zone_ids, "%s 的 id %r 重复" % (tag, zid))
        zone_ids.append(zid)
        for key in ("name", "layer", "level", "maps_to"):
            need(bool(str(zone.get(key, "")).strip()), "%s 缺 %s" % (tag, key))

    # ---- 10 设施：P0–P9 / 四区分组 / parent 真楼嵌套 ----
    facilities = city_data.get("facilities")
    need(isinstance(facilities, list) and len(facilities) == 10,
         "city/data.json 应有 10 个设施（P0–P9），实际 %r 个"
         % (len(facilities) if isinstance(facilities, list) else facilities))
    facilities = facilities if isinstance(facilities, list) else []
    v2_arts = {int(art.get("no")): art for art in data["artifacts"]}
    fac_by_no: dict[str, dict] = {}
    for idx, fac in enumerate(facilities):
        tag = "设施 P%d" % idx
        no = fac.get("no")
        need(no == "P%d" % idx, "%s 的编号应为 P%d，实际 %r" % (tag, idx, no))
        if not isinstance(no, str):
            continue
        fac_by_no[no] = fac
        for key in ("name", "kind", "soft", "problem", "solution"):
            need(bool(str(fac.get(key, "")).strip()), "%s 缺 %s" % (tag, key))
        page_id = str(fac.get("page_id") or "")
        need(page_id == CITY_PAGES[idx],
             "%s 的 page_id 应为 %r，实际 %r" % (tag, CITY_PAGES[idx], page_id))
        need(str(fac.get("page") or "") == "第 %d 页" % idx,
             "%s 的 page 应为「第 %d 页」，实际 %r" % (tag, idx, fac.get("page")))
        zone_id = str(fac.get("zone") or "")
        need(zone_id in zone_ids, "%s 的 zone %r 不在 4 区里" % (tag, zone_id))
        short = fac.get("short") or {}
        for key in ("q", "a"):
            need(bool(str(short.get(key, "")).strip()), "%s 的 short.%s 为空" % (tag, key))
        arts = fac.get("artifacts")
        need(isinstance(arts, list) and bool(arts), "%s 的 artifacts 应为非空数组" % tag)
        for value in (arts if isinstance(arts, list) else []):
            need(isinstance(value, int) and value in v2_arts,
                 "%s 的交付物编号 %r 不在 v2 data 的 1–%d"
                 % (tag, value, len(data["artifacts"])))

    # parent 合法性：真楼嵌套（楼内房间 → 楼，只一层，同一区，父级必须是「楼」）
    for idx, fac in enumerate(facilities):
        tag = "设施 P%d" % idx
        parent = fac.get("parent")
        if parent in (None, ""):
            continue
        need(isinstance(parent, str) and parent in fac_by_no,
             "%s 的 parent %r 不是已存在的设施" % (tag, parent))
        if not (isinstance(parent, str) and parent in fac_by_no):
            continue
        parent_fac = fac_by_no[parent]
        need(parent != fac.get("no"), "%s 的 parent 指回自己" % tag)
        need(parent_fac.get("parent") in (None, ""),
             "%s 的 parent %r 自身还有 parent（只许「楼 + 楼内房间」一层嵌套）" % (tag, parent))
        need(parent_fac.get("zone") == fac.get("zone"),
             "%s 与 parent %r 不在同一个区" % (tag, parent))
        need(parent_fac.get("kind") == "楼",
             "%s 的 parent %r 应是「楼」（实际 kind %r）"
             % (tag, parent, parent_fac.get("kind")))

    # ---- 设施模型 + 交付物：12 件各一次（city artifacts 只存编号，名字逐字取 v2 data） ----
    seen_arts: list[int] = []
    fac_models: list[dict] = []
    for idx, fac in enumerate(facilities):
        arts = [int(v) for v in (fac.get("artifacts") or []) if isinstance(v, int)]
        seen_arts.extend(arts)
        fac_models.append({
            "index": idx,
            "no": fac.get("no"),
            "name": fac.get("name"),
            "kind": fac.get("kind"),
            "soft": fac.get("soft"),
            "problem": fac.get("problem"),
            "solution": fac.get("solution"),
            "zone": fac.get("zone"),
            "parent": fac.get("parent") or None,
            "page": fac.get("page"),
            "page_no": idx,
            "page_id": fac.get("page_id"),
            "artifacts": [{"no": int(value), "name": v2_arts[int(value)]["name"]} for value in arts],
        })
    need(sorted(seen_arts) == list(range(1, len(data["artifacts"]) + 1)),
         "city/data.json 的 %d 件交付物应各出现一次，实际 %r"
         % (len(data["artifacts"]), sorted(seen_arts)))

    # ---- 页卡：10 页，页标题运行期从 page-0X.md 的 H1 读；页码前缀必须与文件名一致 ----
    pages: list[dict] = []
    for idx, page_id in enumerate(CITY_PAGES):
        title = read_page_title(page_id)
        prefix = re.match(r"^第\s*(\d+)\s*页", title)
        need(bool(prefix), "%s.md 的 H1 应以「第 N 页」开头（页码前缀），实际 %r" % (page_id, title))
        if prefix:
            need(int(prefix.group(1)) == idx,
                 "%s.md 的 H1 页码前缀「第 %s 页」与文件名 page-%02d 不一致"
                 % (page_id, prefix.group(1), idx))
        fac = fac_models[idx] if idx < len(fac_models) else {}
        pages.append({
            "page": page_id,
            "no": idx,
            "title": title,
            "solution": fac.get("solution"),
            "soft": fac.get("soft"),
            "facility": {"no": fac.get("no"), "name": fac.get("name")},
            "artifacts": fac.get("artifacts") or [],
        })

    # ---- 4 区分组（组内保持 P0–P9 编号顺序） ----
    zone_models: list[dict] = []
    for zone in zones:
        members = [fac for fac in fac_models if fac.get("zone") == zone.get("id")]
        need(bool(members), "区 %r 一个设施都没有（4 区都应非空）" % zone.get("name"))
        zone_models.append({
            "id": zone.get("id"),
            "name": zone.get("name"),
            "layer": zone.get("layer"),
            "level": zone.get("level"),
            "maps_to": zone.get("maps_to"),
            "facilities": members,
        })
    need(sum(len(zone["facilities"]) for zone in zone_models) == len(fac_models),
         "4 区分组应恰好覆盖 %d 个设施各一次" % len(fac_models))

    # ---- 城市五阶段（只读，不参与勾选） ----
    stages, stages_source = build_city_stages(city_data)

    if errs:
        print("✗ 城市地图数据校验失败（%d 条）：" % len(errs))
        for err in errs:
            print("  - " + err)
        raise SystemExit(1)

    city_model = {
        "schema": CITY_SCHEMA,
        "decision": city_data.get("decision"),
        "title": city_data.get("title"),
        "kicker": city_data.get("kicker"),
        "one_liner": city_data.get("one_liner"),
        "note": city_data.get("note"),
        "sources": {
            "city": "tutorial/city/data.json（4 区 / 10 设施 / 真楼嵌套 / page_id ↔ 页码）",
            "titles": "tutorial/page-00.md – page-09.md 的 H1（运行期读取，不手写）",
            "artifacts": "tutorial/completeness/v2/data.json 的 1–12 件交付物（名字逐字取它）",
            "stages": stages_source,
        },
        "zones": zone_models,
        "facilities": fac_models,
        "pages": pages,
        "stages": stages,
        "stages_source": stages_source,
    }
    titles_ok = all(page["title"] == read_page_title(page["page"]) for page in city_model["pages"])
    parented = [fac for fac in fac_models if fac["parent"]]
    badge_total = sum(len(page["artifacts"]) for page in city_model["pages"])
    ok("城市地图：4 区（%s）· 10 设施 P0–P9 · %d 件交付物各一次"
       % (" / ".join("%s %d 件" % (zone["name"], len(zone["facilities"]))
                     for zone in zone_models), badge_total))
    ok("城市地图：楼内嵌套 %d 件（%s）· 10 条页标题运行期取自 page-0X.md 的 H1（页码前缀与文件名一致 ✓）"
       % (len(parented), " · ".join("%s→%s" % (fac["no"], fac["parent"]) for fac in parented)))
    ok("城市地图：%d 张页卡共长出 %d 件交付物 · 五阶段 %d 段（来源 %s）"
       % (len(city_model["pages"]), badge_total, len(city_model["stages"]), stages_source))
    if not titles_ok:  # 读两次应当等价；防运行期被别的进程改页
        fail("页标题两次从 md 读取结果不一致（page-0X.md 在构建过程中被改过）")
    return city_model


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

/* ---------- 视图切换：物料清单 / 城市地图 ---------- */
.view-row{display:flex;align-items:center;gap:9px;}
.views{display:flex;border:2px solid var(--ink);border-radius:6px;overflow:hidden;}
.view-btn{border:0;border-right:1.5px solid var(--ink);background:#fff;color:var(--ink);
          font:inherit;font-size:12.5px;font-weight:800;padding:4px 13px;cursor:pointer;
          letter-spacing:.5px;white-space:nowrap;}
.view-btn:last-child{border-right:0;}
.view-btn:hover{background:#eeeeee;}
.view-btn.is-on{background:var(--ink);color:#fff;}
.view-hint{font-size:10.6px;color:var(--mute);white-space:nowrap;overflow:hidden;
           text-overflow:ellipsis;max-width:330px;}
.app.view-city .mode-row{display:none;}

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

/* ---------- 城市地图视图（4 区 · 10 设施 ↔ 10 页） ---------- */
#cityview{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;background:#fff;}
#cityview[hidden],.split[hidden],.statusbar[hidden],.aon[hidden]{display:none;}
.city-head{display:flex;align-items:baseline;gap:12px;padding:6px 20px;
           border-bottom:1.5px solid var(--ink);background:var(--soft);flex:0 0 auto;}
.ch-kicker{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:10.5px;
           font-weight:900;letter-spacing:.4px;white-space:nowrap;}
.ch-title{font-size:12.3px;color:var(--ink2);white-space:nowrap;overflow:hidden;
          text-overflow:ellipsis;min-width:0;}
.ch-pair{margin-left:auto;flex:0 0 auto;font-size:10.8px;color:#333;white-space:nowrap;}
.ch-pair b{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-weight:900;}
.city-body{display:flex;flex:1 1 auto;min-height:0;}
.city-col{display:flex;flex-direction:column;min-width:0;min-height:0;}
.city-left{flex:0 0 42%;border-right:2px solid var(--ink);}
.city-right{flex:1 1 58%;background:#fafafa;}
.cv-head{display:flex;align-items:baseline;gap:8px;padding:5px 16px;
         border-bottom:1.4px solid var(--ink);background:#efefef;flex:0 0 auto;}
.cv-head b{font-size:11.3px;font-weight:900;letter-spacing:.2px;}
.cv-head .cv-note{font-size:9.8px;color:var(--mute);white-space:nowrap;}
.cv-head .cv-n{margin-left:auto;font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;
               font-size:10px;color:#555;white-space:nowrap;}
.city-list{flex:1 1 auto;min-height:0;overflow:auto;padding:6px 12px 10px;
           display:flex;flex-direction:column;gap:6px;}
.zone-group{flex:0 0 auto;border:1.4px solid #9a9a9a;border-radius:7px;background:#fcfcfc;overflow:hidden;}
.zone-head{display:flex;align-items:baseline;gap:7px;padding:3px 10px;background:#e9e9e9;
           border-bottom:1px solid #bdbdbd;}
.zone-name{font-size:11.4px;font-weight:900;letter-spacing:.2px;white-space:nowrap;}
.zone-layer{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:9.4px;
            font-weight:800;color:#555;border:1px solid #999;border-radius:3px;
            padding:0 4px;background:#fff;white-space:nowrap;}
.zone-maps{font-size:9.6px;color:#555;overflow:hidden;text-overflow:ellipsis;
           white-space:nowrap;min-width:0;}
.zone-n{margin-left:auto;font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;
        font-size:9.6px;color:#555;white-space:nowrap;}
.zone-items{display:flex;flex-direction:column;gap:4px;padding:5px 6px 6px;}
.fac-line{margin:0;padding:0;display:flex;min-width:0;}
.fac-item{display:flex;align-items:flex-start;gap:8px;width:100%;text-align:left;
          border:1.4px solid var(--ink);border-radius:6px;background:#fff;color:var(--ink);
          font:inherit;padding:4px 8px 5px;cursor:pointer;min-width:0;
          box-shadow:0 1px 0 #e5e5e5;}
.fac-item:hover{background:#f0f0f0;}
.fac-no{flex:0 0 auto;min-width:28px;height:22px;border:1.6px solid var(--ink);border-radius:11px;
        display:flex;align-items:center;justify-content:center;background:#fff;color:var(--ink);
        font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:11px;
        font-weight:900;line-height:1;margin-top:1px;}
.fac-txt{min-width:0;}
.fac-top{display:flex;align-items:baseline;gap:5px;flex-wrap:wrap;}
.fac-name{font-size:12.6px;font-weight:900;line-height:1.22;}
.fac-kind{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:9.2px;
          font-weight:800;color:#444;border:1px solid #999;border-radius:3px;
          padding:0 4px;white-space:nowrap;background:#f4f4f4;}
.fac-problem{display:block;font-size:10.1px;color:#444;line-height:1.33;margin-top:1px;}
.fac-parent{display:inline-block;font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;
            font-size:9.2px;color:#333;border:1px dashed #888;border-radius:3px;
            padding:0 4px;margin-top:2px;background:#f7f7f7;white-space:nowrap;}
.fac-item.is-hot{background:var(--ink);color:#fff;border-color:var(--ink);
                 box-shadow:0 0 0 2px #999,0 1px 0 #999;}
.fac-item.is-hot .fac-no{background:#fff;color:var(--ink);}
.fac-item.is-hot .fac-kind{color:#111;background:#fff;border-color:#fff;}
.fac-item.is-hot .fac-problem{color:#e8e8e8;}
.fac-item.is-hot .fac-parent{color:#f0f0f0;border-color:#bbb;background:transparent;}
.fac-item.is-dim{opacity:.35;}
.city-cards{flex:1 1 auto;min-height:0;overflow:auto;padding:6px 16px 10px;
            display:flex;flex-direction:column;gap:5px;}
.city-card{display:grid;grid-template-columns:32px minmax(0,1fr) auto;gap:9px;
           align-items:center;border:1.4px solid var(--ink);border-radius:6px;background:#fff;
           padding:4px 10px 5px;cursor:pointer;min-width:0;box-shadow:0 1px 0 #e5e5e5;
           flex:1 0 auto;}
.city-card:hover{background:#f0f0f0;}
.city-card:focus-visible{outline:2px solid var(--ink);outline-offset:1px;}
.cc-no{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:12px;
       font-weight:900;background:var(--ink);color:#fff;border-radius:4px;
       padding:3px 0;text-align:center;}
.cc-main{min-width:0;}
.cc-title{margin:0;font-size:13.2px;font-weight:900;line-height:1.22;white-space:nowrap;
          overflow:hidden;text-overflow:ellipsis;}
.cc-build{font-size:10.4px;color:#333;line-height:1.33;margin-top:1px;overflow:hidden;
          display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;}
.cc-soft{font-size:9.8px;color:#555;line-height:1.3;margin-top:1px;overflow:hidden;
         display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;}
.cc-build .lbl,.cc-soft .lbl,.cc-arts .lbl{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;
         font-size:9.2px;font-weight:800;color:#777;letter-spacing:.3px;margin-right:4px;}
.cc-side{display:flex;flex-direction:column;align-items:flex-end;gap:2px;white-space:nowrap;}
.cc-arts{display:flex;align-items:center;gap:3px;}
.art-badge{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:11.5px;
           font-weight:900;border:1.2px solid var(--ink);border-radius:50%;min-width:19px;
           height:19px;display:inline-flex;align-items:center;justify-content:center;
           background:#f2f2f2;color:var(--ink);padding:0 2px;}
.cc-open{font-size:9.8px;color:var(--ink);text-decoration:none;border-bottom:1px solid var(--ink);}
.cc-open:hover{background:var(--ink);color:#fff;}
.city-card.is-hot{background:var(--ink);color:#fff;border-color:var(--ink);
                  box-shadow:0 0 0 2px #999,0 1px 0 #999;}
.city-card.is-hot .cc-no{background:#fff;color:var(--ink);}
.city-card.is-hot .cc-title{color:#fff;}
.city-card.is-hot .cc-build{color:#f0f0f0;}
.city-card.is-hot .cc-soft{color:#dcdcdc;}
.city-card.is-hot .cc-build .lbl,.city-card.is-hot .cc-soft .lbl,
.city-card.is-hot .cc-arts .lbl{color:#cfcfcf;}
.city-card.is-hot .art-badge{background:#fff;color:var(--ink);border-color:#fff;}
.city-card.is-hot .cc-open{color:#fff;border-bottom-color:#fff;}
.city-card.is-dim{opacity:.33;}
.city-stages{flex:0 0 auto;display:flex;align-items:center;gap:10px;padding:6px 20px 7px;
             border-top:2px solid var(--ink);background:#fff;}
.cs-title{font-size:10.6px;font-weight:900;white-space:nowrap;}
.cs-title span{font-size:9.6px;font-weight:400;color:#666;}
.cs-bar{display:flex;gap:6px;flex:1 1 auto;min-width:0;}
.cs-seg{flex:1 1 0;min-width:0;border:1.4px solid var(--ink);border-radius:5px;
        padding:2px 8px 2px;display:flex;align-items:baseline;gap:6px;white-space:nowrap;
        overflow:hidden;background:#fff;}
.cs-seg b{font-size:10.8px;font-weight:900;}
.cs-count{font-family:"DejaVu Sans Mono","Noto Sans CJK SC",monospace;font-size:11px;
          font-weight:900;letter-spacing:.3px;}
.cs-sub{font-size:9.7px;color:#555;overflow:hidden;text-overflow:ellipsis;}
.cs-seg.l1{background:#f3f3f3;border-style:dashed;}
.cs-seg.l5{background:var(--ink);color:#fff;}
.cs-seg.l5 .cs-sub{color:#dcdcdc;}
@media (max-width:1280px){
  .city-left{flex-basis:45%;}
  .ch-title{display:none;}
  .cs-sub{display:none;}
}

/* ---------- 提示条 ---------- */
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
<div class="app" id="app">
  <header class="top">
    <div class="brand">
      <div class="kicker" id="kicker"></div>
      <h1><span id="title"></span> <span class="mid">·</span> 可交互</h1>
      <div class="sub" id="subtitle"></div>
    </div>
    <div class="controls">
      <div class="view-row">
        <div class="views" role="group" aria-label="视图切换">
          <button type="button" class="view-btn is-on" data-view="material"
                  aria-pressed="true">物料清单</button>
          <button type="button" class="view-btn" data-view="city"
                  aria-pressed="false">城市地图</button>
        </div>
        <span class="view-hint" id="view-hint">视图：物料清单 · 12 件 × 24 检验点</span>
      </div>
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
      <span class="aon-note">A0–A9 活动名 / 顺序取自 tutorial/flow.mmd · 点它只高亮左侧零件行，<b>不参与勾选</b></span>
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

  <section class="cityview" id="cityview" hidden aria-label="城市地图：4 区 · 10 设施 ↔ 10 页">
    <div class="city-head">
      <span class="ch-kicker" id="city-kicker">城市地图 · 4 区 · 10 设施 ↔ 10 页</span>
      <span class="ch-title" id="city-title"></span>
      <span class="ch-pair" id="city-pair">点左列设施 → 右列同页页卡高亮并滚入视野；点右列页卡 → 左列同号设施高亮</span>
    </div>
    <div class="city-body">
      <section class="city-col city-left" aria-label="左列：按 4 个区分组的 10 个设施">
        <div class="cv-head">
          <b>① 城市 · 按 4 个区分组的 10 个设施</b>
          <span class="cv-note">设施 = 运行单元；楼内房间不单独占楼</span>
          <span class="cv-n" id="city-fac-n">10 设施 · 4 区</span>
        </div>
        <div class="city-list" id="city-list"></div>
      </section>
      <section class="city-col city-right" aria-label="右列：十页页卡（交付层）">
        <div class="cv-head">
          <b>② 我们的页面 · 这一页造出什么</b>
          <span class="cv-note">交付层：盖完应该看到什么</span>
          <span class="cv-n" id="city-page-n">10 页 · 12 件交付物</span>
        </div>
        <div class="city-cards" id="city-cards"></div>
      </section>
    </div>
    <div class="city-stages" id="city-stages" aria-label="城市五阶段（只读口径，不参与勾选）">
      <span class="cs-title">城市五阶段 <span>· D44+D50 口径 · 不参与勾选</span></span>
      <div class="cs-bar" id="cs-bar"></div>
    </div>
  </section>
</div>
<div class="toast" id="toast" role="status" aria-live="polite" hidden></div>

<script id="completeness-data" type="application/json">__DATA_JSON__</script>
<script id="city-data" type="application/json">__CITY_JSON__</script>
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

  // 城市地图（4 区 / 10 设施 ↔ 10 页）：数据由生成器从 tutorial/city/data.json + page-0X.md 的 H1
  // + v2 data 的交付物名 + D44+D50 五阶段文字合成后内联；页标题不在这里手写。
  var CITY = JSON.parse(document.getElementById('city-data').textContent);
  var CITY_ZONES = CITY.zones || [];
  var CITY_FACS = CITY.facilities || [];
  var CITY_PAGES = CITY.pages || [];

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

  // 唯一可变状态：view（物料清单 / 城市地图）、mode（答案态 / 空白态）、
  // checks（检验点级真源）、open（打开的卡片）、navhl、citySel（城市地图选中的页）
  var state = { view: 'material', mode: 'answer', checks: {}, open: [], navhl: null, citySel: null };

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

  // ---------- 城市地图视图（4 区 · 10 设施 ↔ 10 页） ----------
  function circleNo(number) {
    var n = Number(number);
    return n >= 1 && n <= 20 ? String.fromCharCode(0x2460 + n - 1) : '#' + pad2(n);
  }

  function facilityItemHTML(fac) {
    var tip = fac.no + ' ' + fac.name + ' · ' + fac.kind + ' · 问题：' + fac.problem +
      ' · 点它高亮第 ' + fac.page_no + ' 页页卡';
    var parent = fac.parent
      ? '<span class="fac-parent">楼内 · 属于 ' + esc(fac.parent) + '</span>'
      : '';
    return '<li class="fac-line"><button type="button" class="fac-item"' +
      ' data-city-fac="' + fac.index + '" data-facility="' + esc(fac.no) +
      '" data-page="' + esc(fac.page) + '" aria-pressed="false" title="' + esc(tip) + '">' +
      '<span class="fac-no">' + esc(fac.no) + '</span>' +
      '<span class="fac-txt"><span class="fac-top"><span class="fac-name">' + esc(fac.name) +
      '</span><span class="fac-kind">' + esc(fac.kind) + '</span></span>' +
      '<span class="fac-problem">' + esc(fac.problem) + '</span>' + parent +
      '</span></button></li>';
  }

  function zoneGroupHTML(zone) {
    var items = (zone.facilities || []).map(facilityItemHTML).join('');
    return '<section class="zone-group" data-city-zone="' + esc(zone.id) + '">' +
      '<div class="zone-head"><span class="zone-name">' + esc(zone.name) + '</span>' +
      '<span class="zone-layer">' + esc(zone.layer + ' · ' + zone.level) + '</span>' +
      '<span class="zone-maps">' + esc(zone.maps_to) + '</span>' +
      '<span class="zone-n">' + (zone.facilities || []).length + ' 设施</span></div>' +
      '<div class="zone-items">' + items + '</div></section>';
  }

  function cityCardHTML(page) {
    var badges = (page.artifacts || []).map(function (art) {
      var tip = '#' + pad2(art.no) + ' ' + String(art.name).replace(/`/g, '');
      return '<span class="art-badge" data-art-no="' + esc(art.no) + '" title="' + esc(tip) +
        '">' + circleNo(art.no) + '</span>';
    }).join('');
    var tipCard = '城市页卡 ' + page.no + ' · ' + page.title + ' · 这一页长出 ' +
      (page.artifacts || []).length + ' 件交付物 · 点它高亮左列同号设施';
    return '<article class="city-card" data-city-page="' + esc(page.page) + '" data-page-no="' +
      page.no + '" tabindex="0" role="button" aria-pressed="false" title="' + esc(tipCard) + '">' +
      '<span class="cc-no">#' + pad2(page.no) + '</span>' +
      '<div class="cc-main"><h3 class="cc-title">' + esc(page.title) + '</h3>' +
      '<div class="cc-build"><span class="lbl">这一页造什么</span>' + rich(page.solution) + '</div>' +
      '<div class="cc-soft"><span class="lbl">软件对应</span>' + rich(page.soft) + '</div></div>' +
      '<div class="cc-side"><div class="cc-arts"><span class="lbl">长出</span>' + badges +
      '</div><a class="cc-open" href="../' + esc(page.page) + '.md" title="打开 ' +
      esc(page.page) + '.md（相对路径 ../）">打开这一页</a></div></article>';
  }

  function cityStageHTML(stage) {
    var cls = 'cs-seg' + (stage.level === 'L1' ? ' l1' : '') +
      (stage.level === 'L5' ? ' l5' : '');
    return '<div class="' + cls + '" data-stage="' + esc(stage.level) + '" title="' +
      esc(stage.desc || '') + '"><b>' + esc(stage.level + ' ' + stage.name) + '</b>' +
      '<span class="cs-count">' + esc(stage.count) + '</span>' +
      '<span class="cs-sub">' + esc(stage.sub || '') + '</span></div>';
  }

  function sumCityArtifacts() {
    return CITY_PAGES.reduce(function (sum, page) {
      return sum + (page.artifacts || []).length;
    }, 0);
  }

  function renderCity() {
    var list = document.getElementById('city-list');
    var host = document.getElementById('city-cards');
    if (!list || !host) { return; }
    list.innerHTML = CITY_ZONES.map(zoneGroupHTML).join('');
    host.innerHTML = CITY_PAGES.map(cityCardHTML).join('');
    var kicker = document.getElementById('city-kicker');
    var title = document.getElementById('city-title');
    var facN = document.getElementById('city-fac-n');
    var pageN = document.getElementById('city-page-n');
    var bar = document.getElementById('cs-bar');
    if (kicker) { kicker.textContent = CITY.kicker || '城市地图'; }
    if (title) { title.textContent = CITY.title || ''; }
    if (facN) { facN.textContent = CITY_FACS.length + ' 设施 · ' + CITY_ZONES.length + ' 区'; }
    if (pageN) {
      pageN.textContent = CITY_PAGES.length + ' 页 · ' + sumCityArtifacts() + ' 件交付物';
    }
    if (bar) { bar.innerHTML = (CITY.stages || []).map(cityStageHTML).join(''); }
    renderCitySelection();
  }

  function renderCitySelection() {
    var sel = state.citySel;
    Array.prototype.forEach.call(
      document.querySelectorAll('#city-list [data-city-fac]'), function (node) {
        var on = sel !== null && Number(node.getAttribute('data-city-fac')) === sel;
        node.classList.toggle('is-hot', on);
        node.classList.toggle('is-dim', sel !== null && !on);
        node.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    Array.prototype.forEach.call(
      document.querySelectorAll('#city-cards [data-city-page]'), function (node) {
        var on = sel !== null && Number(node.getAttribute('data-page-no')) === sel;
        node.classList.toggle('is-hot', on);
        node.classList.toggle('is-dim', sel !== null && !on);
        node.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    var pair = document.getElementById('city-pair');
    if (!pair) { return; }
    if (sel === null || !CITY_PAGES[sel] || !CITY_FACS[sel]) {
      pair.textContent = '点左列设施 → 右列同页页卡高亮并滚入视野；' +
        '点右列页卡 → 左列同号设施高亮';
      return;
    }
    var page = CITY_PAGES[sel];
    var fac = CITY_FACS[sel];
    var arts = (page.artifacts || []).map(function (art) { return circleNo(art.no); }).join('');
    pair.innerHTML = '<b>' + esc(fac.no + ' ' + fac.name) + '</b> ↔ ' + esc(page.title) +
      ' · 长出 ' + esc(arts);
  }

  function scrollInside(container, element) {
    if (!container || !element || !container.getBoundingClientRect) { return; }
    var c = container.getBoundingClientRect();
    var r = element.getBoundingClientRect();
    var delta = 0;
    if (r.top < c.top) { delta = r.top - c.top - 4; }
    else if (r.bottom > c.bottom) { delta = r.bottom - c.bottom + 4; }
    if (delta) { container.scrollTop = Math.max(0, container.scrollTop + delta); }
  }

  function scrollCitySelection() {
    var sel = state.citySel;
    if (sel === null) { return; }
    scrollInside(document.getElementById('city-cards'),
      document.querySelector('#city-cards [data-page-no="' + sel + '"]'));
    scrollInside(document.getElementById('city-list'),
      document.querySelector('#city-list [data-city-fac="' + sel + '"]'));
  }

  function citySelect(index) {
    var at = Number(index);
    if (!(at >= 0 && at < CITY_PAGES.length)) { return false; }
    state.citySel = at;
    renderCitySelection();
    if (state.view === 'city') { scrollCitySelection(); }
    return true;
  }

  function applyViewUI() {
    var isCity = state.view === 'city';
    var app = document.getElementById('app');
    if (app) { app.classList.toggle('view-city', isCity); }
    var cityview = document.getElementById('cityview');
    var split = document.querySelector('.split');
    var statusbar = document.querySelector('.statusbar');
    var aon = document.getElementById('aon');
    if (cityview) { cityview.hidden = !isCity; }
    if (split) { split.hidden = isCity; }
    if (statusbar) { statusbar.hidden = isCity; }
    if (aon) { aon.hidden = isCity; }
    Array.prototype.forEach.call(document.querySelectorAll('.view-btn'), function (button) {
      var on = button.getAttribute('data-view') === state.view;
      button.classList.toggle('is-on', on);
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    var hint = document.getElementById('view-hint');
    if (hint) {
      hint.textContent = isCity
        ? '视图：城市地图 · ' + CITY_ZONES.length + ' 区 / ' + CITY_FACS.length + ' 设施 / ' +
          CITY_PAGES.length + ' 页 · 只读联动'
        : '视图：物料清单 · ' + ARTS.length + ' 件 × ' + TOTAL_CHECKS + ' 检验点';
    }
    if (isCity) {
      var modeHint = document.getElementById('mode-hint');
      if (modeHint) {
        modeHint.textContent = '城市地图（只读联动）：点左列设施 → 右列同页页卡高亮并滚入视野；' +
          '点右列页卡 → 左列同号设施高亮。物料清单的勾选 / 空白态进度不受影响。';
      }
      var reset = document.getElementById('reset');
      if (reset) { reset.disabled = state.mode !== 'blank'; }
    } else {
      applyModeUI();
    }
    if (isCity) {
      renderCitySelection();
      if (state.citySel !== null) { scrollCitySelection(); }
    }
  }

  function switchView(view) {
    if (view !== 'material' && view !== 'city') { return false; }
    if (view === state.view) { return false; }
    state.view = view;
    applyViewUI();
    return true;
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

  // ---------- 视图切换：物料清单 / 城市地图 ----------
  Array.prototype.forEach.call(document.querySelectorAll('.view-btn'), function (button) {
    button.addEventListener('click', function () {
      switchView(button.getAttribute('data-view'));
    });
  });

  // 城市地图左列：点设施 → 右列同页页卡高亮并滚入视野
  document.getElementById('city-list').addEventListener('click', function (ev) {
    var node = ev.target.closest ? ev.target.closest('[data-city-fac]') : null;
    if (!node) { return; }
    citySelect(node.getAttribute('data-city-fac'));
  });

  // 城市地图右列：点页卡 → 左列同号设施高亮；「打开这一页」是普通相对链接，不拦截
  var cityCardsHost = document.getElementById('city-cards');
  cityCardsHost.addEventListener('click', function (ev) {
    var target = ev.target;
    if (target.closest && target.closest('a')) { return; }
    var card = target.closest ? target.closest('[data-city-page]') : null;
    if (!card) { return; }
    citySelect(card.getAttribute('data-page-no'));
  });
  cityCardsHost.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Enter' && ev.key !== ' ') { return; }
    if (ev.target.closest && ev.target.closest('a')) { return; }
    var card = ev.target.closest ? ev.target.closest('[data-city-page]') : null;
    if (!card) { return; }
    ev.preventDefault();
    citySelect(card.getAttribute('data-page-no'));
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
    cityData: CITY,
    cityZones: CITY_ZONES,
    cityFacilities: CITY_FACS,
    cityPages: CITY_PAGES,
    setView: switchView,
    citySelect: citySelect,
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
  renderCity();
  renderAll();
  applyViewUI();
})();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------ 产物静态自检

def check_html(text: str, data: dict, city_model: dict) -> dict:
    if DATA_TOKEN in text:
        fail("HTML 里残留占位符 %s：JSON 没内联进去" % DATA_TOKEN)
    if AON_TOKEN in text:
        fail("HTML 里残留占位符 %s：AON 导航没渲染" % AON_TOKEN)
    if CITY_TOKEN in text:
        fail("HTML 里残留占位符 %s：城市地图 JSON 没内联进去" % CITY_TOKEN)
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
    if text.count("<script") != 3:
        fail("应只有三段内联 script（物料数据 + 城市数据 + 逻辑），实际 %d 段" % text.count("<script"))

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

    # ---- 城市地图视图（4 区 · 10 设施 ↔ 10 页）：静态断言 ----
    city_marker = '<script id="city-data" type="application/json">'
    if shell.count(city_marker) != 1:
        fail("应有且只有一个内联城市数据 script（%r），实际 %d 个"
             % (city_marker, shell.count(city_marker)))
    cstart = shell.index(city_marker) + len(city_marker)
    cend = shell.index("</script>", cstart)
    city_payload = shell[cstart:cend]
    city_shell = shell[:cstart] + shell[cend:]
    try:
        embedded_city = json.loads(city_payload.replace("<\\/", "</"))
    except json.JSONDecodeError as exc:
        fail("内联城市 JSON 解析失败：%s" % exc)
    if embedded_city != city_model:
        fail("内联进 HTML 的城市 JSON 与生成器从 city/data.json + md 合成的地图模型不一致")
    if "://" in city_payload:
        fail("内联城市数据里出现外链（必须离线可开）")
    for bad in EXTERNAL_SHELL:
        if bad in city_shell:
            fail("城市地图静态壳里出现外部资源痕迹 %r（必须离线可用）" % bad)
    if 'id="cityview" hidden' not in text:
        fail("城市地图视图应默认 hidden（默认进物料清单视图）")
    if text.count('class="view-btn') != 2:
        fail("顶部应有「物料清单 / 城市地图」两个视图切换按钮，实际 %d 个"
             % text.count('class="view-btn'))
    if 'data-view="material"' not in text or 'data-view="city"' not in text:
        fail("视图切换按钮缺 data-view=material / data-view=city")
    if '>城市地图</button>' not in text:
        fail("顶部第二个视图按钮文案应为「城市地图」")
    if '<span class="view-hint" id="view-hint">' not in text:
        fail("缺少视图切换提示 view-hint")
    for bad in ("data-map-action", "data-map-page", "mapSelect", "工地地图", "全书地图",
                "四阶段成熟度", "site-timeline"):
        if bad in text:
            fail("产物里残留旧「工地地图」实现的痕迹 %r（D45 后应换成城市地图）" % bad)

    # 城市数据模型：4 区 / 10 设施 / parent 真楼嵌套 / 10 页卡 / 12 件交付物
    zones_model = embedded_city.get("zones") or []
    facilities_model = embedded_city.get("facilities") or []
    pages_model = embedded_city.get("pages") or []
    if not isinstance(zones_model, list) or len(zones_model) != 4:
        fail("城市地图应有 4 个区，实际 %r"
             % (len(zones_model) if isinstance(zones_model, list) else zones_model))
    if not isinstance(facilities_model, list) or len(facilities_model) != 10:
        fail("城市地图应有 10 个设施（P0–P9），实际 %r"
             % (len(facilities_model) if isinstance(facilities_model, list) else facilities_model))
    if not isinstance(pages_model, list) or len(pages_model) != 10:
        fail("城市地图应有 10 张页卡，实际 %r"
             % (len(pages_model) if isinstance(pages_model, list) else pages_model))
    zone_ids = [zone.get("id") for zone in zones_model]
    if len(set(zone_ids)) != 4 or any(not str(zid).strip() for zid in zone_ids):
        fail("4 个区 id 应非空且不重复，实际 %r" % zone_ids)
    fac_by_no = {fac.get("no"): fac for fac in facilities_model}
    if sorted(fac_by_no) != ["P%d" % i for i in range(10)]:
        fail("设施编号应恰为 P0–P9，实际 %r" % sorted(fac_by_no))
    parented: list[tuple[str, str]] = []
    for idx, fac in enumerate(facilities_model):
        tag = "城市设施 P%d" % idx
        if fac.get("no") != "P%d" % idx:
            fail("%s 的编号应为 P%d，实际 %r" % (tag, idx, fac.get("no")))
        for key in ("name", "kind", "soft", "problem", "solution", "zone", "page", "page_id"):
            if not str(fac.get(key, "")).strip():
                fail("%s 缺 %s" % (tag, key))
        if fac.get("page_id") != "page-%02d" % idx:
            fail("%s 的 page_id 应为 page-%02d，实际 %r" % (tag, idx, fac.get("page_id")))
        if fac.get("page") != "第 %d 页" % idx:
            fail("%s 的 page 应为「第 %d 页」，实际 %r" % (tag, idx, fac.get("page")))
        if fac.get("zone") not in zone_ids:
            fail("%s 的 zone %r 不在 4 区里" % (tag, fac.get("zone")))
        parent = fac.get("parent")
        if parent is not None:
            if parent not in fac_by_no:
                fail("%s 的 parent %r 不是已存在的设施" % (tag, parent))
            else:
                parent_fac = fac_by_no[parent]
                if parent_fac.get("parent") is not None:
                    fail("%s 的 parent %r 自身还有 parent（只许一层楼内嵌套）" % (tag, parent))
                if parent_fac.get("zone") != fac.get("zone"):
                    fail("%s 与 parent %r 不在同一个区" % (tag, parent))
                if parent_fac.get("kind") != "楼":
                    fail("%s 的 parent %r 应是「楼」，实际 kind %r"
                         % (tag, parent, parent_fac.get("kind")))
                parented.append((fac.get("no"), parent))
        arts = fac.get("artifacts") or []
        if not arts:
            fail("%s 一件交付物都没长出" % tag)
        for art in arts:
            art_no = art.get("no")
            if not isinstance(art_no, int) or not (1 <= art_no <= len(data["artifacts"])):
                fail("%s 的交付物编号 %r 不在 1–%d" % (tag, art_no, len(data["artifacts"])))
    if not parented:
        fail("城市地图应至少有一个楼内嵌套（parent），否则「楼内 · 属于」标注无处可考")
    seen_art_no = sorted(art.get("no") for fac in facilities_model
                         for art in (fac.get("artifacts") or []))
    if seen_art_no != [art["no"] for art in data["artifacts"]]:
        fail("10 设施应共长出 %d 件交付物（每件恰好一次），实际 %r"
             % (len(data["artifacts"]), seen_art_no))

    # 4 区分组：每区非空、恰好覆盖 10 设施各一次、组内属于该区
    seen_in_zones: list[str] = []
    for zone in zones_model:
        if not str(zone.get("name", "")).strip():
            fail("区 %r 缺 name" % zone.get("id"))
        members = zone.get("facilities") or []
        if not members:
            fail("区 %r 一个设施都没有（4 区都应非空）" % zone.get("name"))
        for fac in members:
            seen_in_zones.append(fac.get("no"))
            if fac.get("zone") != zone.get("id"):
                fail("区 %r 里混进了 zone=%r 的设施 %r"
                     % (zone.get("name"), fac.get("zone"), fac.get("no")))
    if len(seen_in_zones) != 10 or sorted(seen_in_zones) != ["P%d" % i for i in range(10)]:
        fail("4 区分组应恰好覆盖 P0–P9 各一次，实际 %r" % sorted(seen_in_zones))

    # 10 张页卡：页码 / 运行期 H1 / 这一页造什么（solution + soft）/ 交付物圆牌 / 相对链接
    page_badge_total = 0
    for idx, page in enumerate(pages_model):
        tag = "城市第 %d 页（page-%02d）" % (idx, idx)
        if page.get("page") != "page-%02d" % idx:
            fail("%s 的 page 字段应为 page-%02d，实际 %r" % (tag, idx, page.get("page")))
        if page.get("no") != idx:
            fail("%s 的 no 应为 %d，实际 %r" % (tag, idx, page.get("no")))
        title = str(page.get("title") or "")
        expected_title = read_page_title("page-%02d" % idx)   # 运行期从 md 读，不是手写
        if title != expected_title:
            fail("%s 的页标题 %r 与 page-%02d.md 的 H1 %r 不一致（标题必须运行期从 md 读）"
                 % (tag, title, idx, expected_title))
        prefix = re.match(r"^第\s*(\d+)\s*页", title)
        if not prefix or int(prefix.group(1)) != idx:
            fail("%s 的页标题页码前缀应与文件名 page-%02d.md 一致（实际标题 %r）"
                 % (tag, idx, title))
        fac = facilities_model[idx]
        if page.get("solution") != fac.get("solution"):
            fail("%s 的「这一页造什么」应逐字取 city data 的 solution" % tag)
        if page.get("soft") != fac.get("soft"):
            fail("%s 的「软件对应」应逐字取 city data 的 soft" % tag)
        page_fac = page.get("facility") or {}
        if page_fac.get("no") != fac.get("no") or page_fac.get("name") != fac.get("name"):
            fail("%s 的设施应指向 %r" % (tag, fac.get("no")))
        arts = page.get("artifacts") or []
        fac_arts = fac.get("artifacts") or []
        if [(art.get("no"), art.get("name")) for art in arts] != \
                [(art.get("no"), art.get("name")) for art in fac_arts]:
            fail("%s 的交付物圆牌应与设施 P%d 的 artifacts 一致" % (tag, idx))
        for art in arts:
            v2_art = next((item for item in data["artifacts"] if item["no"] == art.get("no")), None)
            if v2_art is None or art.get("name") != v2_art.get("name"):
                fail("%s 的交付物 #%r 名字应逐字取 v2 data" % (tag, art.get("no")))
            page_badge_total += 1
    if page_badge_total != len(data["artifacts"]):
        fail("10 页应共长出 %d 件交付物，实际 %d 个圆牌"
             % (len(data["artifacts"]), page_badge_total))

    # 城市五阶段：5 段、L1–L5、D44+D50 城市说法、只读口径
    stage_model = embedded_city.get("stages") or []
    if len(stage_model) != 5:
        fail("城市地图应有 5 段城市五阶段，实际 %d 段" % len(stage_model))
    if [stage.get("level") for stage in stage_model] != STAGE_ORDER:
        fail("城市五阶段的 level 应依次为 L1–L5，实际 %r"
             % [stage.get("level") for stage in stage_model])
    expected_stage_names = list(CITY_STAGE_NAMES)
    actual_stage_names = [str(stage.get("name") or "") for stage in stage_model]
    if actual_stage_names != expected_stage_names:
        fail("城市五阶段名应为 %r（D44+D50 城市说法），实际 %r"
             % (expected_stage_names, actual_stage_names))
    if str(stage_model[0].get("count") or "") != "0/%d" % len(facilities_model):
        fail("第一阶段「荒地工地」计数应为 0/%d，实际 %r"
             % (len(facilities_model), stage_model[0].get("count")))
    for stage in stage_model[1:]:
        if not re.match(r"^\d+\s*页$", str(stage.get("count") or "")):
            fail("第 2–5 阶段计数应为「N 页」，实际 %r" % stage.get("count"))
    for idx, stage in enumerate(stage_model):
        if not str(stage.get("sub") or "").strip():
            fail("城市五阶段第 %d 段缺说明文字" % (idx + 1))
    if embedded_city.get("stages_source") not in (
            "D44 文字（stages-city.json 不存在）", "tutorial/city/stages-city.json"):
        fail("stages_source 标记异常：%r" % embedded_city.get("stages_source"))

    for needle in ("城市地图", "data-city-fac=", "data-city-page=", "data-city-zone=",
                   "楼内 · 属于 ", "打开这一页", "城市五阶段", "不参与勾选",
                   "citySelect", "switchView", "荒地工地", "通水电网", "智慧城市",
                   "城市安防", "精装交付", "这一页造什么", "软件对应", "点左列设施", "点右列页卡"):
        if needle not in text:
            fail("产物缺少城市地图构件 / 文案 %r" % needle)

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


DOM_CITY_CHECK_JS = r"""
<script id="explorer-city-selfcheck">
(function () {
  'use strict';
  var fails = [];
  var info = {};

  function check(cond, msg) { if (!cond) { fails.push(msg); } }
  function q(sel) { return document.querySelector(sel); }
  function qa(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  function txt(sel) { var el = q(sel); return el ? el.textContent.trim() : '<missing ' + sel + '>'; }
  function api() { return window.__EXPLORER__; }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function pageId(n) { return 'page-' + pad2(n); }
  function circleNo(n) {
    return n >= 1 && n <= 20 ? String.fromCharCode(0x2460 + n - 1) : '#' + pad2(n);
  }
  function strip(text) {
    return String(text === null || text === undefined ? '' : text).replace(/`/g, '');
  }
  function visibleIn(container, element) {
    if (!container || !element) { return false; }
    var c = container.getBoundingClientRect();
    var r = element.getBoundingClientRect();
    return r.top >= c.top - 2 && r.bottom <= c.bottom + 2;
  }

  function run() {
    var E = api();
    check(!!E, '缺少 __EXPLORER__ 验收句柄');
    if (!E) { return; }
    var CITY = E.cityData;
    check(!!CITY, '缺少内联城市数据 __EXPLORER__.cityData');
    if (!CITY) { return; }
    var zones = CITY.zones || [];
    var facs = CITY.facilities || [];
    var pages = CITY.pages || [];
    var v2ByNo = {};
    E.data.artifacts.forEach(function (art) { v2ByNo[art.no] = art; });

    check(zones.length === 4, '内联城市区数据应有 4 个区，实际 ' + zones.length);
    check(facs.length === 10, '内联城市设施数据应有 10 个设施（P0–P9），实际 ' + facs.length);
    check(pages.length === 10, '内联城市页数据应有 10 页，实际 ' + pages.length);
    check((CITY.stages || []).length === 5, '内联城市五阶段应有 5 段');

    // ===== 0) 默认视图 = 物料清单，城市地图隐藏，原行为不变 =====
    check(E.state.view === 'material', '默认视图应为物料清单（material），实际 ' + E.state.view);
    check(q('#cityview') && q('#cityview').hidden === true, '默认视图下城市地图应 hidden');
    check(q('.split') && q('.split').hidden === false, '默认视图下物料清单应可见');
    check(qa('.view-btn').length === 2, '顶部应有 2 个视图切换按钮，实际 ' + qa('.view-btn').length);
    check(q('.view-btn[data-view="material"]').classList.contains('is-on') &&
      q('.view-btn[data-view="city"]').classList.contains('is-on') === false,
      '默认应高亮「物料清单」按钮');
    check(txt('#view-hint').indexOf('物料清单') >= 0,
      '默认视图提示应写物料清单，实际 ' + txt('#view-hint'));
    check(qa('#material-table tbody tr.mrow').length === 12, '默认物料清单应仍有 12 行');
    var baseStats = { rows: txt('#stat-rows b'), checks: txt('#stat-checks b') };
    var baseChecks = JSON.stringify(E.state.checks);
    var baseMode = E.state.mode;

    // ===== 1) 切到城市地图视图 =====
    q('.view-btn[data-view="city"]').click();
    check(E.state.view === 'city', '点「城市地图」后 state.view 应为 city，实际 ' + E.state.view);
    check(q('#cityview').hidden === false, '切到城市地图后 #cityview 应可见');
    check(q('.split').hidden === true, '切到城市地图后物料清单应隐藏（不是删除）');
    check(q('.statusbar').hidden === true && q('#aon').hidden === true,
      '城市地图视图应隐藏只属于物料清单的状态条 / AON 导航');
    check(q('.view-btn[data-view="city"]').classList.contains('is-on'), '「城市地图」按钮应高亮');
    check(txt('#view-hint').indexOf('城市地图') >= 0,
      '城市地图视图提示应写城市地图，实际 ' + txt('#view-hint'));

    // ===== 2) 左列：按 4 区分组的 10 个设施 =====
    var zoneGroups = qa('#city-list [data-city-zone]');
    check(zoneGroups.length === 4, '左列应有 4 个区分组，实际 ' + zoneGroups.length);
    var seenZoneFacs = [];
    zones.forEach(function (zone) {
      var group = q('#city-list [data-city-zone="' + zone.id + '"]');
      check(!!group, '缺少区 ' + zone.id + ' 的分组');
      if (!group) { return; }
      var zoneName = group.querySelector('.zone-name');
      check(zoneName && zoneName.textContent.trim() === zone.name,
        '区 ' + zone.id + ' 的区名应为 «' + zone.name + '»，实际 «' +
        (zoneName ? zoneName.textContent.trim() : '<missing>') + '»');
      var items = group.querySelectorAll('[data-city-fac]');
      check(items.length === (zone.facilities || []).length,
        '区 ' + zone.name + ' 应有 ' + (zone.facilities || []).length + ' 个设施，实际 ' + items.length);
      Array.prototype.forEach.call(items, function (node) {
        seenZoneFacs.push(node.getAttribute('data-city-fac'));
      });
    });
    check(seenZoneFacs.length === 10, '左列设施应恰好 10 个，实际 ' + seenZoneFacs.length);

    facs.forEach(function (fac, i) {
      var node = q('#city-list [data-city-fac="' + i + '"]');
      check(!!node, '缺少设施 P' + i + ' 的按钮');
      if (!node) { return; }
      check(node.getAttribute('data-facility') === fac.no,
        '设施 P' + i + ' 的 data-facility 应为 ' + fac.no);
      check(node.getAttribute('data-page') === fac.page,
        '设施 P' + i + ' 的 data-page 应为 «' + fac.page + '»');
      var no = node.querySelector('.fac-no');
      check(no && no.textContent.trim() === fac.no,
        '设施 P' + i + ' 的编号应为 ' + fac.no + '，实际 ' +
        (no ? no.textContent.trim() : '<missing>'));
      var nameEl = node.querySelector('.fac-name');
      check(nameEl && nameEl.textContent.trim() === fac.name,
        '设施 P' + i + ' 的城市名应与 city/data.json 逐字一致（«' + fac.name + '»），实际 «' +
        (nameEl ? nameEl.textContent.trim() : '<missing>') + '»');
      var problem = node.querySelector('.fac-problem');
      check(problem && problem.textContent.trim() === fac.problem,
        '设施 P' + i + ' 的问题句应与 city/data.json 逐字一致，实际 «' +
        (problem ? problem.textContent.trim() : '<missing>') + '»');
      var parent = node.querySelector('.fac-parent');
      if (fac.parent) {
        check(!!parent && parent.textContent.indexOf('楼内 · 属于 ' + fac.parent) >= 0,
          '楼内设施 P' + i + ' 应标「楼内 · 属于 ' + fac.parent + '」，实际 «' +
          (parent ? parent.textContent.trim() : '<missing>') + '»');
      } else {
        check(!parent, '独立设施 P' + i + ' 不应标「楼内 · 属于」');
      }
    });
    // 真楼嵌套：P2 → P1，P4–P8 → P3，共 6 个楼内设施
    check(qa('#city-list .fac-parent').length === 6,
      '左列应有 6 个楼内设施标注，实际 ' + qa('#city-list .fac-parent').length);

    // ===== 3) 右列：10 张页卡（页码 + 运行期 H1 + 造什么 / 软件对应 + 圆牌 + 链接） =====
    var cards = qa('#city-cards [data-city-page]');
    check(cards.length === 10, '右列页卡应有 10 张，实际 ' + cards.length);
    pages.forEach(function (page, i) {
      var card = q('#city-cards [data-city-page="' + pageId(i) + '"]');
      check(!!card, '缺少第 ' + i + ' 页页卡');
      if (!card) { return; }
      check(card.getAttribute('data-page-no') === String(i),
        '第 ' + i + ' 页页卡的 data-page-no 应为 ' + i);
      var titleEl = card.querySelector('.cc-title');
      var title = titleEl ? titleEl.textContent.trim() : '';
      check(title === page.title,
        '第 ' + i + ' 页标题应与 page-' + pad2(i) + '.md 的 H1 逐字一致（期望 «' + page.title +
        '»），实际 «' + title + '»');
      var prefix = title.match(/^第\s*(\d+)\s*页/);
      check(!!prefix && Number(prefix[1]) === i,
        '第 ' + i + ' 页标题的页码前缀应与文件名 page-' + pad2(i) + ' 一致，实际 «' + title + '»');
      var buildEl = card.querySelector('.cc-build');
      check(buildEl && buildEl.textContent.indexOf('这一页造什么') >= 0,
        '第 ' + i + ' 页卡应标注「这一页造什么」');
      check(buildEl && buildEl.textContent.indexOf(strip(page.solution)) >= 0,
        '第 ' + i + ' 页卡「这一页造什么」应与 city/data.json 的 solution 逐字一致');
      var softEl = card.querySelector('.cc-soft');
      check(softEl && softEl.textContent.indexOf('软件对应') >= 0,
        '第 ' + i + ' 页卡应标注「软件对应」');
      check(softEl && softEl.textContent.indexOf(strip(page.soft)) >= 0,
        '第 ' + i + ' 页卡「软件对应」应与 city/data.json 的 soft 逐字一致');
      var badges = qa('#city-cards [data-city-page="' + pageId(i) + '"] .art-badge');
      check(badges.length === page.artifacts.length,
        '第 ' + i + ' 页应长出 ' + page.artifacts.length + ' 件交付物圆牌，实际 ' + badges.length);
      page.artifacts.forEach(function (art, k) {
        var badge = badges[k];
        check(!!badge && badge.getAttribute('data-art-no') === String(art.no),
          '第 ' + i + ' 页第 ' + (k + 1) + ' 个圆牌编号应为 #' + pad2(art.no));
        check(!!badge && badge.textContent.trim() === circleNo(art.no),
          '第 ' + i + ' 页圆牌应显示 ' + circleNo(art.no) + '，实际 ' +
          (badge ? badge.textContent.trim() : '<missing>'));
        check(!!badge && (badge.getAttribute('title') || '').indexOf(strip(art.name)) >= 0,
          '第 ' + i + ' 页圆牌 tooltip 应含交付物名「' + art.name + '」');
        var v2Art = v2ByNo[art.no];
        check(!!v2Art && art.name === v2Art.name,
          '第 ' + i + ' 页交付物 #' + art.no + ' 的名字应逐字取 v2 data');
      });
      var link = card.querySelector('a.cc-open');
      check(!!link && link.getAttribute('href') === '../' + pageId(i) + '.md',
        '第 ' + i + ' 页「打开这一页」应链到相对路径 ../' + pageId(i) + '.md，实际 ' +
        (link ? link.getAttribute('href') : '<missing>'));
      check(!!link && link.textContent.trim() === '打开这一页',
        '第 ' + i + ' 页链接文案应为「打开这一页」');
    });
    // 10 页 → 12 件反查（每件恰好一次、编号 1–12 齐）
    var seen = [];
    pages.forEach(function (page) {
      page.artifacts.forEach(function (art) { seen.push(art.no); });
    });
    check(seen.length === 12 &&
      seen.slice().sort(function (a, b) { return a - b; }).join(',') ===
        '1,2,3,4,5,6,7,8,9,10,11,12',
      '10 页应共长出 12 件交付物（每件恰好一次），实际 [' + seen.join(', ') + ']');

    // ===== 4) 无外链 / 无绝对路径 / 零外部请求 =====
    var cityLinks = qa('#cityview a[href]').map(function (a) {
      return a.getAttribute('href') || '';
    });
    check(cityLinks.length === 10, '城市地图应恰好 10 个本地页链接，实际 ' + cityLinks.length);
    var badLinks = cityLinks.filter(function (href) {
      return !/^\.\.\/page-\d{2}\.md$/.test(href);
    });
    check(badLinks.length === 0, '城市地图链接只允许 ../page-0X.md，异常：' + badLinks.join(' , '));
    var cityHTML = q('#cityview').innerHTML;
    ['http://', 'https://', '//cdn', '/home/', '/Users/', 'src=', 'fetch(',
     '<img', '<iframe', '<link', 'XMLHttpRequest'].forEach(function (bad) {
      check(cityHTML.indexOf(bad) < 0,
        '城市地图 DOM 不应出现外链 / 绝对路径痕迹 ' + JSON.stringify(bad));
    });
    check(cityHTML.indexOf('../page-') >= 0, '城市地图应使用 ../page-0X.md 相对链接');
    check(qa('#cityview script').length === 0, '城市地图里不应再有 script');
    var resources = (window.performance && window.performance.getEntriesByType)
      ? window.performance.getEntriesByType('resource') : [];
    var resourceNames = resources.map(function (entry) { return entry.name; });
    check(resources.length === 0, '单文件应零资源请求（离线可开），实际 ' + resources.length +
      ' 个资源：' + resourceNames.slice(0, 6).join(' , '));

    // ===== 5) 点左列设施 3 → 右列同号页卡高亮、其余压暗；配对条逐字 =====
    check(E.state.citySel === null, '进入城市地图时默认不预选任何页，实际 ' + E.state.citySel);
    check(qa('#city-cards .city-card.is-hot').length === 0, '默认不应有高亮页卡');
    check(qa('#city-list .fac-item.is-hot').length === 0, '默认不应有高亮设施');
    q('#city-list [data-city-fac="3"]').click();
    check(E.state.citySel === 3, '点设施 3 后 state.citySel 应为 3，实际 ' + E.state.citySel);
    var hotCards = qa('#city-cards .city-card.is-hot');
    check(hotCards.length === 1 && hotCards[0].getAttribute('data-page-no') === '3',
      '点设施 3 应只高亮第 3 页页卡，实际高亮 ' + hotCards.length + ' 张');
    check(qa('#city-cards .city-card.is-dim').length === 9,
      '其余 9 张页卡应压暗，实际 ' + qa('#city-cards .city-card.is-dim').length);
    check(q('.city-card[data-page-no="3"]').getAttribute('aria-pressed') === 'true',
      '高亮页卡 aria-pressed 应为 true');
    check(qa('#city-list .fac-item.is-hot').length === 1 &&
      q('#city-list .fac-item.is-hot').getAttribute('data-city-fac') === '3',
      '左列设施 3 也应同步高亮');
    check(qa('#city-list .fac-item.is-dim').length === 9, '其余 9 个设施应压暗');
    check(txt('#city-pair').indexOf('P3') >= 0 && txt('#city-pair').indexOf(pages[3].title) >= 0,
      '顶部配对条应写 «P3» + 第 3 页标题，实际 ' + txt('#city-pair'));
    check(txt('#city-pair').indexOf(circleNo(pages[3].artifacts[0].no)) >= 0,
      '顶部配对条应带出该页交付物圆牌 ' + circleNo(pages[3].artifacts[0].no));

    // ===== 6) 点右列页卡 8 → 左列同号设施高亮；两侧都能滚入视野 =====
    var cardScroller = q('#city-cards');
    var facScroller = q('#city-list');
    var cardScrollBefore = cardScroller.scrollTop;
    var facScrollBefore = facScroller.scrollTop;
    q('.city-card[data-page-no="8"]').click();
    check(E.state.citySel === 8, '点页卡 8 后 state.citySel 应为 8，实际 ' + E.state.citySel);
    var hotFacs = qa('#city-list .fac-item.is-hot');
    check(hotFacs.length === 1 && hotFacs[0].getAttribute('data-city-fac') === '8',
      '点页卡 8 应同步高亮左列设施 8，实际 ' + hotFacs.length + ' 个高亮');
    check(qa('#city-list .fac-item.is-dim').length === 9, '其余 9 个设施应压暗');
    check(visibleIn(facScroller, q('#city-list [data-city-fac="8"]')),
      '点页卡 8 后设施 8 应滚入左列视野（scrollTop ' + facScrollBefore + ' → ' +
      facScroller.scrollTop + '）');
    check(visibleIn(cardScroller, q('.city-card[data-page-no="8"]')),
      '点页卡 8 后页卡 8 应在右列视野内');
    check(txt('#city-pair').indexOf('P8') >= 0 && txt('#city-pair').indexOf(pages[8].title) >= 0,
      '配对条应写 «P8» + 第 8 页标题，实际 ' + txt('#city-pair'));

    // 点设施 9（列表末尾）→ 页卡 9 必须被滚进视野（证明“滚入视野”真生效）
    var card9VisibleBefore = visibleIn(cardScroller, q('.city-card[data-page-no="9"]'));
    var cardScrollBefore9 = cardScroller.scrollTop;
    var fac9VisibleBefore = visibleIn(facScroller, q('#city-list [data-city-fac="9"]'));
    var facScrollBefore9 = facScroller.scrollTop;
    q('#city-list [data-city-fac="9"]').click();
    check(E.state.citySel === 9, '点设施 9 后 state.citySel 应为 9，实际 ' + E.state.citySel);
    check(visibleIn(cardScroller, q('.city-card[data-page-no="9"]')),
      '点设施 9 后页卡 9 应滚入右列视野（scrollTop ' + cardScrollBefore9 + ' → ' +
      cardScroller.scrollTop + '）');
    check(visibleIn(facScroller, q('#city-list [data-city-fac="9"]')),
      '点设施 9 后设施 9 应在左列视野内');
    if (!card9VisibleBefore) {
      check(cardScroller.scrollTop > cardScrollBefore9,
        '点设施 9 后右列应真的滚动（scrollTop ' + cardScrollBefore9 + ' → ' +
        cardScroller.scrollTop + '）');
    }
    if (!fac9VisibleBefore) {
      check(facScroller.scrollTop > facScrollBefore9,
        '点设施 9 后左列应真的滚动（scrollTop ' + facScrollBefore9 + ' → ' +
        facScroller.scrollTop + '）');
    }
    var scrollProof = {
      cardScrollBefore: cardScrollBefore, cardScrollAfter: cardScroller.scrollTop,
      facScrollBefore: facScrollBefore, facScrollAfter: facScroller.scrollTop,
      cardScrollHeight: cardScroller.scrollHeight, cardClientHeight: cardScroller.clientHeight,
      facScrollHeight: facScroller.scrollHeight, facClientHeight: facScroller.clientHeight,
      card9VisibleBefore: card9VisibleBefore, fac9VisibleBefore: fac9VisibleBefore
    };

    // ===== 7) 底部城市五阶段条（只读，不参与勾选） =====
    var segs = qa('#city-stages .cs-seg');
    check(segs.length === 5, '底部城市五阶段应有 5 段，实际 ' + segs.length);
    var levels = segs.map(function (seg) { return seg.getAttribute('data-stage'); });
    check(levels.join(' ') === 'L1 L2 L3 L4 L5',
      '城市五阶段 level 应依次为 L1–L5，实际 ' + levels.join(' '));
    var stageNames = segs.map(function (seg) {
      var el = seg.querySelector('b');
      return el ? el.textContent.trim() : '<missing>';
    });
    check(stageNames.join(' ') === 'L1 荒地工地 L2 通水电网 L3 智慧城市 L4 城市安防 L5 精装交付',
      '城市五阶段名应为 荒地工地 / 通水电网 / 智慧城市 / 城市安防 / 精装交付，实际 ' + stageNames.join(' '));
    var counts = segs.map(function (seg) {
      var el = seg.querySelector('.cs-count');
      return el ? el.textContent.trim() : '<missing>';
    });
    check(counts.join(' ') === '0/10 4 页 4 页 5 页 1 页',
      '城市五阶段计数应为 0/10 → 4 页 → 4 页 → 5 页 → 1 页，实际 ' + counts.join(' '));
    check(qa('#city-stages [data-check]').length === 0 &&
      qa('#city-stages input').length === 0 &&
      qa('#city-stages button').length === 0,
      '城市五阶段条不得带可勾选控件（它不参与勾选）');
    check(txt('#city-stages').indexOf('不参与勾选') >= 0, '城市五阶段条应注明不参与勾选');
    check(txt('#city-stages').indexOf('城市五阶段') >= 0, '城市五阶段条应有标题');

    // ===== 8) 城市地图联动不改物料清单状态；切回后原状态保留 =====
    q('#city-list [data-city-fac="5"]').click();
    q('.city-card[data-page-no="9"]').click();
    check(JSON.stringify(E.state.checks) === baseChecks, '城市地图联动不得改动检验点状态');
    check(E.state.mode === baseMode, '城市地图联动不得改动答案 / 空白态');
    check(txt('#stat-rows b') === baseStats.rows && txt('#stat-checks b') === baseStats.checks,
      '城市地图下物料清单计数应保持不变（原行为不变），实际 ' + txt('#stat-rows b') + ' / ' +
      txt('#stat-checks b'));

    q('.view-btn[data-view="material"]').click();
    check(E.state.view === 'material', '点「物料清单」应切回 material，实际 ' + E.state.view);
    check(q('#cityview').hidden === true, '切回物料清单后城市地图应隐藏');
    check(q('.split').hidden === false, '切回物料清单后物料清单应可见');
    check(q('.statusbar').hidden === false && q('#aon').hidden === false,
      '切回物料清单后状态条 / AON 导航应恢复可见');
    check(qa('#material-table tbody tr.mrow').length === 12, '切回后物料清单仍应有 12 行');
    check(E.state.mode === baseMode && JSON.stringify(E.state.checks) === baseChecks,
      '切回物料清单后答案 / 空白态与检验点状态应保持');

    // ===== 9) 负向对照：非法视图 / 非法选中不生效 =====
    check(E.setView('nope') === false, '负向对照：非法视图名应被拒绝');
    check(E.setView('material') === false, '负向对照：重复切到当前视图应返回 false');
    var selBefore = E.state.citySel;
    check(E.citySelect(-1) === false, '负向对照：选中 -1 应被拒绝');
    check(E.citySelect(10) === false, '负向对照：选中 10（越界）应被拒绝');
    check(E.citySelect('x') === false, '负向对照：选中非数字应被拒绝');
    check(E.state.citySel === selBefore,
      '负向对照后选中项应保持不变，实际 ' + E.state.citySel + ' / 期望 ' + selBefore);
    check(JSON.stringify(E.state.checks) === baseChecks, '负向对照后检验点状态应不变');

    info = {
      zones: zones.length, facilities: facs.length, cards: cards.length, pages: pages.length,
      stageCounts: counts.join(' '), view: E.state.view, citySel: E.state.citySel,
      scrollProof: scrollProof
    };
  }

  function finish() {
    var pass = fails.length === 0;
    var marker = 'DOM_CITY_SELF' + 'CHECK_';
    document.title = marker + (pass ? 'PASS' : 'FAIL') +
      (pass ? '' : ' ' + fails.slice(0, 8).join(' || '));
    var pre = document.createElement('pre');
    pre.id = 'explorer-city-selfcheck';
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
        city_window = ["--window-size=%d,%d" % (CITY_DOM_W, CITY_DOM_H), "--dump-dom"]

        def run_page(script: str, extra: list[str] | None = None) -> str:
            page.write_text(text.replace("</body>", script + "\n</body>"), encoding="utf-8")
            proc = run_chrome(chrome, work, page, extra or window)
            return proc.stdout or ""

        # 阶段 0：城市地图视图（放最前面 = 全新 profile、默认答案态，不依赖本机进度）
        dom_city = run_page(DOM_CITY_CHECK_JS, city_window)
        if not ("DOM_CITY_SELFCHECK_PASS" in dom_city
                and '<pre id="explorer-city-selfcheck">PASS' in dom_city):
            match = re.search(r"<title>(DOM_CITY_SELFCHECK_FAIL[^<]*)</title>", dom_city)
            detail = match.group(1) if match else (dom_city[-2500:] or "chrome 无输出")
            fail("DOM 城市地图视图自检未通过：%s" % detail)

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
    ok("DOM 城市地图视图自检（无头 Chrome 真跑，%d×%d 视口）：默认物料清单 → 切城市地图 → "
       "4 区分组 / 10 设施 / 10 张页卡齐 · 城市名与问题句逐字、页标题逐字对上、"
       "楼内嵌套标注 6 件 · 点设施↔点页卡双向高亮、其余压暗、选中卡 / 设施都滚入视野 · "
       "城市五阶段 0/10 → 4 页 → 4 页 → 5 页 → 1 页只读 · 联动不改物料清单勾选 / 答案空白态；"
       "含无外链 / 无绝对路径 / 零外部请求负向对照（%d×%d 视口触发真滚动）"
       % (CITY_DOM_W, CITY_DOM_H, CITY_DOM_W, CITY_DOM_H))


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
        '|view=' + E.state.view +
        '|citysel=' + (E.state.citySel === null ? '-' : E.state.citySel) +
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


def generate_shots(text: str, only: str | None = None) -> None:
    chrome = find_chrome()
    if not chrome:
        print("  ⚠ 未找到 google-chrome / chromium，跳过验证截图（静态 / DOM 自检仍然生效）")
        return
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    selected = [shot for shot in SHOTS
                if only is None or shot[0].startswith(only + "-")]
    if not selected:
        fail("--shot %r 没有匹配的截图；可选前缀：%s"
             % (only, " / ".join(name.rsplit("-", 1)[0] for name, *_ in SHOTS)))
    for filename, desc, shot_w, shot_h, setup in selected:
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
            print("  ✓ %s  %d×%d  %s · 视图 %s · 城市选中 %s · 行 %s · 检验点 %s · "
                  "端到端 %s · 印章 %s · 卡片 %s 张 · 首卡徽章 %s"
                  % (filename, width, height, desc,
                     info.get("view", "?"), info.get("citysel", "?"),
                     info.get("rows", "?"), info.get("checks", "?"),
                     info.get("e2e", "?"),
                     "显示" if info.get("stamp") == "1" else "隐藏",
                     info.get("cards", "?"), info.get("badge", "?")))


# ------------------------------------------------------------------ 主流程

def build(shots_enabled: bool, shot_only: str | None = None) -> None:
    print("《建成证明》v2 · 可交互原型：v2/data.json + city/data.json → explorer.html"
          "（单文件 / 零依赖 / 离线）")
    data = load_data()
    validate_data(data)
    flow = load_flow()
    check_flow(data, flow)
    city_data = load_json(CITY_DATA_PATH,
                          "城市地图数据（4 区 / 10 设施 / 12 件交付物 / 23 页标题）")
    city_model = build_city_model(data, city_data)

    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    city_payload = json.dumps(city_model, ensure_ascii=False, indent=2).replace("</", "<\\/")
    text = (TEMPLATE.replace(AON_TOKEN, aon_nav_html(data, flow))
            .replace(CITY_TOKEN, city_payload)
            .replace(DATA_TOKEN, payload))
    embedded = check_html(text, data, city_model)
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
    ok("产物构件：顶部视图切换「物料清单 / 城市地图」（默认物料清单）· 城市左 4 区分组 10 设施"
       "（区名 + 城市名 + 问题句 + 楼内嵌套标注）· 右 10 张页卡（运行期 H1 + 这一页造什么 + "
       "软件对应 + 交付物圆牌 + ../page-0X.md 链接）· 顶部配对条 · 城市五阶段条只读 · "
       "点设施↔页卡双向高亮")
    ok("内联 JSON 与 v2/data.json 逐字节等价（%d 字节数据）· 内联城市 JSON 与 city/data.json "
       "+ page-0X.md 合成模型逐字段等价（%d 字节）"
       % (len(payload.encode("utf-8")), len(city_payload.encode("utf-8"))))
    print("  输出：%s  %d 字节（%.1f KB）  sha256 %s"
          % (OUT_PATH.relative_to(REPO), size, size / 1024.0, digest[:16]))

    check_dom(text)
    if shots_enabled:
        generate_shots(text, shot_only)
    else:
        print("  提示：加 --shots 可重出 4 张验证截图（tutorial/review/explorer-shots/"
              "v2-01 / v2-02 / v2-03 / v3-01）")
    print("完成：一个文件即可离线双击打开，不发起任何网络请求。"
          "（重跑：python3 tutorial/shots/build_explorer.py%s）"
          % (" --shots" if not shots_enabled else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="由 v2 单源 data.json + city/data.json 生成《建成证明》可交互原型 explorer.html")
    parser.add_argument("--shots", action="store_true",
                        help="同时生成 4 张验证截图到 tutorial/review/explorer-shots/")
    parser.add_argument("--shot", metavar="PREFIX", default=None,
                        help="配合 --shots，只重出文件名以该前缀开头的截图（如 v3-01）")
    args = parser.parse_args(argv)
    if args.shot and not args.shots:
        parser.error("--shot 需要配合 --shots 使用")
    build(shots_enabled=args.shots, shot_only=args.shot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
