#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_reading_aon.py —— 把阅读层全书铺开 AON 渲染成 PNG（第 4 轮渐进式铺开计划）。

一条命令重跑（在仓库根目录）：

    python3 scripts/render_reading_aon.py               # 核对 CPM + 渲染 + PNG 自检
    python3 scripts/render_reading_aon.py --width 3000  # 更宽的图（文字更大）

源文件（唯一内容源，只改它）：
    humen-desicions/reading-layer-aon.mmd → humen-desicions/reading-layer-aon.png

它做四件事：

1. **核对**：读 mmd 的节点工期与 FS 箭头，用「逐轮松弛到不动点」独立重算 CPM
   （正推 ES/EF、逆推 LS/LF；与 render_flow.py 的 Kahn 拓扑序是两套算法），逐节点比对
   节点里写的 ES/EF/LS/LF；再核对结构（17 节点 / 22 条边 / 根 / 汇聚）、注释里的
   「关键路径」「总工期」「浮动」、class crit/norm/review 与 linkStyle 橙/灰箭头。
   本图有两条并行关键支路（B20/B19 同浮动 0），关键路径按「节点集合 + 驱动边」对账，
   不强行选一条单链。工期是估算值、不是验收时限（R0 已完成，工期 0 是实测口径）。
2. **渲染**：mmd 原样交给仓库内 mermaid@11 离线副本（design/assets/mermaid.min.js）
   自动布局渲染——classDef/linkStyle 直接生效，图与源文件不会两套样式漂移。
3. **截图**：google-chrome 无头按自然尺寸 @2x 超采样截图，裁白边、缩到约定宽度。
4. **自检**：PNG 宽度 / 非空白 / 关键路径橙描边 / 关键浅橙底 / 普通灰底 / 复核绿底，
   有效字号不低于 10px，图上不得出现本机用户名 / 绝对路径。

依赖：本机已有的 python3 / google-chrome / ImageMagick(identify/convert)，仓库内 mermaid 副本。
不新增依赖；不改 manual/ 任何页面与旧图（本图是规划图，不是练本插图）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MMD = REPO / "humen-desicions" / "reading-layer-aon.mmd"
OUT = REPO / "humen-desicions" / "reading-layer-aon.png"
MERMAID_LOCAL = REPO / "design" / "assets" / "mermaid.min.js"

# 复用 L1 渲染脚本的浏览器 / 截图 / 裁剪逻辑（不改它，只 import 函数与常量）
sys.path.insert(0, str(REPO / "manual" / "shots"))
import render_flow as rf  # noqa: E402

DEFAULT_WIDTH = 2600   # 规划图口径：11 列 LR 网络比练本插图宽，取 2600 保证有效字号 ≥10px
MIN_FONT_PX = 10       # 缩到目标宽度后节点文字的有效字号下限
FONT_PX = 20           # mermaid 节点字号（themeVariables.fontSize）

# 配色与 mmd 的 classDef 一致（核对 PNG 直方图用）
CRIT_FILL = (255, 243, 224)     # #fff3e0
CRIT_STROKE = (230, 81, 0)      # #e65100
NORMAL_FILL = (246, 247, 249)   # #f6f7f9
REVIEW_FILL = (232, 242, 236)   # #e8f2ec

# 期望结构（写死在这里：mmd 改坏了，自检会先报错，而不是画出错的图）
EXPECTED_NODES = ["R0", "A21", "A13", "A18", "GA", "RA",
                  "B20", "B19", "B23", "B15", "B10", "GB", "RB",
                  "C", "GC", "RC", "F"]
EXPECTED_DUR = {"R0": 0, "A21": 25, "A13": 20, "A18": 20, "GA": 10, "RA": 5,
                "B20": 15, "B19": 15, "B23": 12, "B15": 12, "B10": 10,
                "GB": 10, "RB": 5, "C": 60, "GC": 10, "RC": 5, "F": 10}
EXPECTED_EDGES = [
    ("R0", "A21"), ("R0", "A13"), ("R0", "A18"),
    ("A21", "GA"), ("A13", "GA"), ("A18", "GA"),
    ("GA", "RA"),
    ("RA", "B20"), ("RA", "B19"), ("RA", "B23"), ("RA", "B15"), ("RA", "B10"),
    ("B20", "GB"), ("B19", "GB"), ("B23", "GB"), ("B15", "GB"), ("B10", "GB"),
    ("GB", "RB"), ("RB", "C"), ("C", "GC"), ("GC", "RC"), ("RC", "F"),
]
EXPECTED_ROOTS = ["R0"]
EXPECTED_CONVERGE = {"GA": {"A21", "A13", "A18"},
                     "GB": {"B20", "B19", "B23", "B15", "B10"}}
CRIT_CLASS = {"R0", "A21", "GA", "B20", "B19", "GB", "C", "GC", "F"}
REVIEW_CLASS = {"RA", "RB", "RC"}   # 用户复核里程碑：在关键路径上，但画绿色菱形
NORMAL_CLASS = {"A13", "A18", "B23", "B15", "B10"}
ORANGE_IDX = {0, 3, 6, 7, 8, 12, 13, 17, 18, 19, 20, 21}   # 关键驱动边（linkStyle 序号）
EXPECTED_FLOATS = {"A13": 5, "A18": 5, "B23": 3, "B15": 3, "B10": 5}
EXPECTED_TOTAL = 155
# 注释声明的关键路径（B20/B19 是并行关键支路，展开成两条单链分别核对）
DECLARED_PATH = ["R0", "A21", "GA", "RA", "B20/B19", "GB", "RB", "C", "GC", "RC", "F"]


# ------------------------------------------------------------------ 1. 读 + 核对

def parse_mmd(path: Path) -> dict:
    """读 mmd：注释 / 节点（矩形与六边形两种声明）/ FS 边（按书写顺序，带全局序号）/ class / linkStyle。"""
    text = path.read_text(encoding="utf-8")
    comments = [ln for ln in text.splitlines() if ln.lstrip().startswith("%%")]
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%%"))
    if not re.search(r"^flowchart\s+LR\s*$", body, re.M):
        raise SystemExit(f"{rf.show(path)} 必须以 `flowchart LR` 声明（单代号网络图从左到右排）")

    nodes: dict[str, str] = {}
    shapes: dict[str, str] = {}
    for ln in body.splitlines():
        m = re.match(r'^\s*([A-Za-z]\w*)\["(.*)"\]\s*$', ln)
        if m:
            nodes[m.group(1)] = m.group(2)
            shapes[m.group(1)] = "rect"
            continue
        m = re.match(r'^\s*([A-Za-z]\w*)\{\{"(.*)"\}\}\s*$', ln)
        if m:
            nodes[m.group(1)] = m.group(2)
            shapes[m.group(1)] = "hex"
    if not nodes:
        raise SystemExit(f"{rf.show(path)} 里没有读到任何节点")

    edges: list[tuple[str, str]] = []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*-->\s*([A-Za-z]\w*)\s*$", body, re.M):
        u, v = m.group(1), m.group(2)
        if u not in nodes or v not in nodes:
            raise SystemExit(f"{rf.show(path)} 依赖边 {u}→{v} 引用了不存在的节点")
        edges.append((u, v))

    classes: dict[str, list[str]] = {}
    for m in re.finditer(r"^\s*class[ \t]+([\w, \t]+?)[ \t]+(crit|norm|review)[ \t]*$", body, re.M):
        classes[m.group(2)] = [x.strip() for x in m.group(1).split(",") if x.strip()]

    links: dict[str, list[int]] = {"orange": [], "gray": []}
    for m in re.finditer(r"^\s*linkStyle\s+([\d,]+)\s+(.*)$", body, re.M):
        idx = [int(x) for x in m.group(1).split(",") if x.strip()]
        if "e65100" in m.group(2):
            links["orange"].extend(idx)
        else:
            links["gray"].extend(idx)
    return dict(text=text, comments=comments, nodes=nodes, shapes=shapes,
                edges=edges, classes=classes, links=links)


def label_fields(nid: str, label: str) -> dict:
    """拆节点标签：标题 / 工期行 / ES EF / LS LF 行 / 判据行（恰好 4 行）。"""
    parts = [p.strip() for p in label.split("<br/>")]
    if len(parts) != 4:
        raise SystemExit(f"{nid} 的节点标签应有 4 行（标题/工期/CPM/判据），实际 {len(parts)} 行")
    if not parts[0].startswith(nid + " "):
        raise SystemExit(f"{nid} 的标题第一行必须是「{nid} 活动名」，实际「{parts[0]}」")
    m = re.match(r"^工期\s*(\d+)（(估|已完成)）$", parts[1])
    if not m:
        raise SystemExit(f"{nid} 的工期行必须是「工期 N（估）」或「工期 0（已完成）」，实际「{parts[1]}」")
    m2 = re.match(r"^ES(\d+)\s+EF(\d+)\s*/\s*LS(\d+)\s+LF(\d+)$", parts[2])
    if not m2:
        raise SystemExit(f"{nid} 的第三行必须是「ES… EF… / LS… LF…」，实际「{parts[2]}」")
    if not parts[3].startswith("判据："):
        raise SystemExit(f"{nid} 的判据行必须以「判据：」开头，实际「{parts[3]}」")
    return dict(title=parts[0], name=parts[0][len(nid) + 1:], dur=int(m.group(1)),
                ES=int(m2.group(1)), EF=int(m2.group(2)),
                LS=int(m2.group(3)), LF=int(m2.group(4)), crit=parts[3])


def cpm_relaxation(dur: dict[str, int], edges: list[tuple[str, str]]) -> dict:
    """独立重算 CPM：逐轮松弛到不动点（不是 Kahn 拓扑序），正推 ES/EF、逆推 LS/LF。"""
    ids = list(dur)
    pred: dict[str, list[str]] = {n: [] for n in ids}
    succ: dict[str, list[str]] = {n: [] for n in ids}
    for u, v in edges:
        pred[v].append(u)
        succ[u].append(v)

    ES = {n: 0 for n in ids}
    EF = {n: dur[n] for n in ids}
    for _ in range(len(ids) + 1):
        changed = False
        for v in ids:
            es = max((EF[u] for u in pred[v]), default=0)
            ef = es + dur[v]
            if es != ES[v] or ef != EF[v]:
                ES[v], EF[v] = es, ef
                changed = True
        if not changed:
            break
    else:
        raise SystemExit("正推松弛不收敛（FS 依赖可能有环）")
    total = max(EF.values())

    LF = {n: total for n in ids}
    LS = {n: total - dur[n] for n in ids}
    for _ in range(len(ids) + 1):
        changed = False
        for v in reversed(ids):
            lf = min((LS[s] for s in succ[v]), default=total)
            ls = lf - dur[v]
            if lf != LF[v] or ls != LS[v]:
                LF[v], LS[v] = lf, ls
                changed = True
        if not changed:
            break
    else:
        raise SystemExit("逆推松弛不收敛（FS 依赖可能有环）")
    TF = {n: LS[n] - ES[n] for n in ids}
    return dict(ES=ES, EF=EF, LS=LS, LF=LF, TF=TF, total=total, pred=pred, succ=succ)


def check_structure(parsed: dict, c: dict, fields: dict) -> None:
    """核对结构、CPM 标注、class/linkStyle、注释声明（四方对账）。"""
    nodes = parsed["nodes"]
    if list(nodes) != EXPECTED_NODES:
        raise SystemExit(f"节点应恰好是 {EXPECTED_NODES}，实际 {list(nodes)}")
    if parsed["edges"] != EXPECTED_EDGES:
        raise SystemExit(f"依赖边与设计不符：\n  mmd {parsed['edges']}\n  期望 {EXPECTED_EDGES}")
    dur = {nid: f["dur"] for nid, f in fields.items()}
    if dur != EXPECTED_DUR:
        raise SystemExit(f"工期与冻结表不符：\n  mmd {dur}\n  期望 {EXPECTED_DUR}")

    # 逐节点比对 CPM 标注 + 自洽
    for nid, f in fields.items():
        got = (f["ES"], f["EF"], f["LS"], f["LF"])
        want = (c["ES"][nid], c["EF"][nid], c["LS"][nid], c["LF"][nid])
        if got != want:
            raise SystemExit(f"{nid} 的 CPM 数值与重算不符：mmd 写 {got}，重算 {want}")
        if c["EF"][nid] != c["ES"][nid] + dur[nid] or c["LS"][nid] != c["LF"][nid] - dur[nid]:
            raise SystemExit(f"{nid} 的 CPM 自洽断言失败（EF=ES+工期 / LS=LF−工期）")
        if c["TF"][nid] != c["LF"][nid] - c["EF"][nid] or c["TF"][nid] < 0:
            raise SystemExit(f"{nid} 的浮动不自洽或为负：{c['TF'][nid]}")
    if c["total"] != EXPECTED_TOTAL:
        raise SystemExit(f"总工期应为 {EXPECTED_TOTAL} 分钟（估），实际 {c['total']}")
    floats = {n: c["TF"][n] for n in nodes if c["TF"][n] > 0}
    if floats != EXPECTED_FLOATS:
        raise SystemExit(f"浮动应恰好是 {EXPECTED_FLOATS}，实际 {floats}")

    # class：crit ∪ review = 浮动 0 集合（复核里程碑在关键路径上但画绿色）；norm = 其余
    crit0 = {n for n in nodes if c["TF"][n] == 0}
    if set(parsed["classes"].get("crit", [])) != CRIT_CLASS:
        raise SystemExit(f"class crit 应为 {sorted(CRIT_CLASS)}，实际 {parsed['classes'].get('crit')}")
    if set(parsed["classes"].get("review", [])) != REVIEW_CLASS:
        raise SystemExit(f"class review 应为 {sorted(REVIEW_CLASS)}，实际 {parsed['classes'].get('review')}")
    if set(parsed["classes"].get("norm", [])) != NORMAL_CLASS:
        raise SystemExit(f"class norm 应为 {sorted(NORMAL_CLASS)}，实际 {parsed['classes'].get('norm')}")
    if CRIT_CLASS | REVIEW_CLASS != crit0:
        raise SystemExit(f"crit∪review 与浮动=0 集合不符：{sorted(CRIT_CLASS | REVIEW_CLASS)} vs {sorted(crit0)}")
    if NORMAL_CLASS != set(nodes) - crit0:
        raise SystemExit("class norm 应恰好是非关键节点")
    for nid in REVIEW_CLASS:
        if parsed["shapes"][nid] != "hex":
            raise SystemExit(f"复核里程碑 {nid} 必须画成六边形（{{{{…}}}}），实际 {parsed['shapes'][nid]}")

    # linkStyle：橙 = 关键驱动边（两端浮动 0 且 EF[u]==ES[v]）；灰 = 其余
    drive = {i for i, (u, v) in enumerate(parsed["edges"])
             if c["TF"][u] == 0 and c["TF"][v] == 0 and c["EF"][u] == c["ES"][v]}
    if drive != ORANGE_IDX:
        raise SystemExit(f"重算的关键驱动边 {sorted(drive)} 与冻结表 {sorted(ORANGE_IDX)} 不符")
    if set(parsed["links"]["orange"]) != drive:
        raise SystemExit(f"linkStyle 橙色箭头与关键驱动边不符：mmd {sorted(parsed['links']['orange'])} vs {sorted(drive)}")
    if set(parsed["links"]["gray"]) != set(range(len(parsed["edges"]))) - drive:
        raise SystemExit("linkStyle 灰色箭头应恰好是非关键依赖边")

    # 注释声明：关键路径（含并行支路）/ 总工期 / 浮动 / 口径 / 渲染命令
    comment_text = "\n".join(parsed["comments"])
    m = re.search(r"%%\s*关键路径：([^，\n]+)，总工期\s*(\d+)\s*分钟", comment_text)
    if not m:
        raise SystemExit(f"{rf.show(MMD)} 注释里缺少「%% 关键路径：…，总工期 N 分钟」")
    declared = [x.strip() for x in m.group(1).split("→") if x.strip()]
    if declared != DECLARED_PATH:
        raise SystemExit(f"注释关键路径 {declared} 与冻结表 {DECLARED_PATH} 不符")
    if int(m.group(2)) != c["total"]:
        raise SystemExit(f"注释总工期 {m.group(2)} ≠ 重算 {c['total']}")
    # 展开 B20/B19 并行支路：每条单链都要边存在、EF 紧贴、节点全在浮动 0 集合里
    declared_set = {x for tok in declared for x in tok.split("/")}
    if declared_set != crit0:
        raise SystemExit(f"注释关键路径节点集合 {sorted(declared_set)} ≠ 浮动=0 集合 {sorted(crit0)}")
    edge_set = set(parsed["edges"])
    branches = [[t] if "/" not in t else t.split("/") for t in declared]
    for choice in range(max(len(b) for b in branches)):
        chain = [b[min(choice, len(b) - 1)] for b in branches]
        for u, v in zip(chain, chain[1:]):
            if (u, v) not in edge_set:
                raise SystemExit(f"注释关键路径的边 {u}→{v} 在 mmd 里不存在")
            if c["EF"][u] != c["ES"][v]:
                raise SystemExit(f"注释关键路径 {u}→{v} 不是紧贴 FS（EF {c['EF'][u]} ≠ ES {c['ES'][v]}）")
    mf = re.search(r"%%\s*浮动：([^\n]+)", comment_text)
    if not mf:
        raise SystemExit(f"{rf.show(MMD)} 注释里缺少「%% 浮动：…」")
    declared_floats: dict[str, int] = {}
    for grp in mf.group(1).split("；"):
        mm = re.match(r"([A-Za-z0-9/]+)\s*(?:各\s*)?(\d+)", grp.strip())
        if not mm:
            raise SystemExit(f"浮动注释段「{grp.strip()}」解析不出「节点 浮动值」")
        for nid in mm.group(1).split("/"):
            declared_floats[nid] = int(mm.group(2))
    if declared_floats != EXPECTED_FLOATS:
        raise SystemExit(f"注释浮动 {declared_floats} ≠ 重算 {EXPECTED_FLOATS}")
    for need, why in [
        ("不是验收时限", "工期口径必须写「不是验收时限」"),
        ("render_reading_aon.py", "注释里必须写清渲染命令"),
    ]:
        if need not in comment_text:
            raise SystemExit(f"{rf.show(MMD)} 注释缺少「{need}」——{why}")

    # 结构：根 / 汇聚
    roots = [n for n in nodes if not c["pred"][n]]
    if roots != EXPECTED_ROOTS:
        raise SystemExit(f"根节点应为 {EXPECTED_ROOTS}，实际 {roots}")
    for nid, want in EXPECTED_CONVERGE.items():
        if set(c["pred"][nid]) != want:
            raise SystemExit(f"{nid} 的紧前应为 {sorted(want)}，实际 {sorted(c['pred'][nid])}")


def check_summary(parsed: dict, c: dict, fields: dict) -> None:
    print(f"✅ CPM 核对通过：{len(fields)} 个节点 / {len(parsed['edges'])} 条 FS 边 / "
          f"总工期 {c['total']} 分钟（估）")
    print(f"   关键路径（B20/B19 并行支路）：{' → '.join(DECLARED_PATH)}")
    print(f"{'编号':<5}{'工期':>5}{'ES':>5}{'EF':>5}{'LS':>5}{'LF':>5}{'总浮动':>7}  关键")
    for nid in fields:
        print(f"{nid:<5}{fields[nid]['dur']:>6}{c['ES'][nid]:>6}{c['EF'][nid]:>6}"
              f"{c['LS'][nid]:>6}{c['LF'][nid]:>6}{c['TF'][nid]:>8}  {'★' if c['TF'][nid] == 0 else ''}")


# ------------------------------------------------------------------ 2. HTML + 渲染

def mermaid_cfg() -> dict:
    cfg = json.loads(json.dumps(rf.MERMAID_CFG))
    cfg["flowchart"].update({"wrappingWidth": 420, "nodeSpacing": 26,
                             "rankSpacing": 40, "padding": 8})
    cfg["themeVariables"]["fontSize"] = f"{FONT_PX}px"
    return cfg


def build_html(mmd: str, mermaid_js: str) -> str:
    title = "阅读层全书铺开 · 单代号网络图（AON / 紧前关系法 PDM）"
    sub = (f"第 4 轮渐进式铺开 · 17 个活动 · 总工期 {EXPECTED_TOTAL} 分钟（估算，不是验收时限）· "
           f"关键路径 R0 → A21 → GA → RA → B20/B19 → GB → RB → C → GC → RC → F")
    legend = (
        "<b>橙色粗框 / 橙色箭头</b> = 关键路径（总浮动 0）｜ 灰色 = 有浮动（A13/A18 各 5、B23/B15 各 3、B10 5 分钟）｜ "
        "<b>绿色六边形</b> = 用户复核里程碑（RA/RB/RC，在关键路径上，批间闸门）<br/>"
        "节点内：编号 + 活动名 / 工期（估）/ ES EF / LS LF / 完成判据 ｜ 箭头 = FS 完成–开始依赖 ｜ "
        "R0 阅读版转正已完成（工期 0）｜ 三批 = A 试点（21/13/18）→ B（20/19/23/15/10）→ C 快通 12 页<br/>"
        "<b>工期 = 估算值（分钟）</b>，只表达依赖与顺序，<b>不是验收时限</b>；每批四道闸门 = audit 24/24 + 代码块一致 + 保护区 + 阅读版 HTML"
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>reading-aon</title>
<style>
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
body {{ display: inline-block; }}
.fig {{ padding: 18px 22px; font-family: {rf.FONT_STACK}; color: #1a1a1a; }}
.fig-title {{ font-size: {rf.FIG_TITLE_PX}px; font-weight: 600; line-height: 1.5; margin: 0 0 2px; }}
.fig-sub {{ font-size: {rf.FIG_SMALL_PX}px; line-height: 1.6; color: #555; margin: 0 0 10px; }}
#holder svg {{ display: block; }}
.fig-legend {{ font-size: {rf.FIG_SMALL_PX}px; line-height: 1.7; color: #444; margin: 10px 0 0; max-width: 1800px; }}
.fig-legend b {{ color: #e65100; font-weight: 600; }}
</style></head><body>
<div class="fig">
  <div class="fig-title">{title}</div>
  <div class="fig-sub">{sub}</div>
  <div id="holder"><pre class="mermaid">
{mmd}
</pre></div>
  <div class="fig-legend">{legend}</div>
</div>
<script>{mermaid_js}</script>
<script>
  mermaid.initialize({json.dumps(mermaid_cfg())});
  mermaid.run({{ querySelector: '.mermaid' }}).then(() => {{
    const r = document.querySelector('.fig').getBoundingClientRect();
    const svg = document.querySelector('#holder svg');
    const n = svg ? svg.querySelectorAll('g.node').length : -1;
    const bad = svg && svg.innerHTML.includes('Syntax error') ? 1 : 0;
    document.title = 'DIM ' + Math.ceil(r.width) + ' ' + Math.ceil(r.height) + ' N ' + n + ' BAD ' + bad;
  }}).catch((e) => {{ document.title = 'ERR ' + (e && e.message ? e.message : e); }});
</script>
</body></html>
"""


def measure(html: Path, work: Path) -> tuple[int, int, int, str]:
    proc = rf.chrome([
        "--window-size=6000,3000",
        "--virtual-time-budget=30000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", html.as_uri(),
    ])
    m = re.search(r"<title>DIM (\d+) (\d+) N (-?\d+) BAD (\d+)</title>", proc.stdout)
    if not m:
        err = re.search(r"<title>ERR ([^<]*)</title>", proc.stdout)
        raise SystemExit("mermaid 渲染失败：" + (err.group(1) if err else (proc.stderr or proc.stdout)[-2000:]))
    w, h, n, bad = (int(x) for x in m.groups())
    if bad:
        raise SystemExit("mmd 交给 mermaid 渲染出现语法错误标记")
    return w, h, n, proc.stdout


# ------------------------------------------------------------------ 3. PNG 自检

def color_counts(png: Path) -> dict[tuple[int, int, int], int]:
    proc = subprocess.run(["convert", str(png), "-format", "%c", "histogram:info:-"],
                          capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise SystemExit("ImageMagick 直方图失败：" + (proc.stderr or proc.stdout)[-1000:])
    counts: dict[tuple[int, int, int], int] = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*(\d+):\s*\((\d+),(\d+),(\d+)\)", line)
        if m:
            counts[(int(m.group(2)), int(m.group(3)), int(m.group(4)))] = int(m.group(1))
    return counts


def check_png(png: Path, width: int) -> tuple[int, int]:
    w, h = rf.identify(png)
    if w != width:
        raise SystemExit(f"{rf.show(png)} 宽度 {w}px，不等于约定 {width}px")
    if not 400 <= h <= 2400:
        raise SystemExit(f"{rf.show(png)} 高度 {h}px 不在合理区间（400–2400）")
    counts = color_counts(png)
    non_white = sum(c for px, c in counts.items() if px != (255, 255, 255))
    if non_white < 30000:
        raise SystemExit(f"{rf.show(png)} 几乎空白（非白像素只有 {non_white}）")
    orange = sum(c for px, c in counts.items()
                 if (px[0] - CRIT_STROKE[0]) ** 2 + (px[1] - CRIT_STROKE[1]) ** 2
                 + (px[2] - CRIT_STROKE[2]) ** 2 <= 40 * 40)
    if orange < 2000:
        raise SystemExit(f"{rf.show(png)} 没有足够的关键路径橙色描边（{orange} 像素）")
    if counts.get(CRIT_FILL, 0) < 2000:
        raise SystemExit(f"{rf.show(png)} 没有足够的关键节点浅橙底（{counts.get(CRIT_FILL, 0)} 像素）")
    if counts.get(NORMAL_FILL, 0) < 800:
        raise SystemExit(f"{rf.show(png)} 没有普通节点的灰色底（{counts.get(NORMAL_FILL, 0)} 像素）")
    if counts.get(REVIEW_FILL, 0) < 500:
        raise SystemExit(f"{rf.show(png)} 没有复核里程碑的绿色底（{counts.get(REVIEW_FILL, 0)} 像素）")
    print(f"   PNG 自检：{w}x{h}px / 非白 {non_white} / 橙描边 {orange} / "
          f"关键浅橙 {counts.get(CRIT_FILL, 0)} / 普通灰 {counts.get(NORMAL_FILL, 0)} / 复核绿 {counts.get(REVIEW_FILL, 0)}")
    return w, h


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="把阅读层铺开 AON（humen-desicions/reading-layer-aon.mmd）渲染成 PNG")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                    help=f"输出 PNG 宽度（默认 {DEFAULT_WIDTH}px；最小 2000）")
    ap.add_argument("--out", type=Path, default=OUT, help="输出 PNG 路径")
    args = ap.parse_args()
    if args.width < 2000:
        raise SystemExit("--width 太小，11 列网络文字会看不清（≥2000）")
    if not MERMAID_LOCAL.exists():
        raise SystemExit(f"缺仓库内 mermaid 副本：{rf.show(MERMAID_LOCAL)}")

    parsed = parse_mmd(MMD)
    fields = {nid: label_fields(nid, lb) for nid, lb in parsed["nodes"].items()}
    c = cpm_relaxation({nid: f["dur"] for nid, f in fields.items()}, parsed["edges"])
    check_structure(parsed, c, fields)
    check_summary(parsed, c, fields)

    mermaid_js = MERMAID_LOCAL.read_text(encoding="utf-8")
    html_text = build_html(parsed["text"], mermaid_js)
    with tempfile.TemporaryDirectory(prefix="reading-aon-") as tmp:
        work = Path(tmp)
        html = work / "reading-aon.html"
        html.write_text(html_text, encoding="utf-8")
        w, h, node_count, dom = measure(html, work)
        if node_count != len(fields):
            raise SystemExit(f"mermaid 画出 {node_count} 个节点，期望 {len(fields)} 个")
        scale = (args.width - 2 * rf.MARGIN) / w
        eff_font = FONT_PX * scale
        if eff_font < MIN_FONT_PX:
            raise SystemExit(f"缩到 {args.width}px 后有效字号只有 {eff_font:.1f}px（<{MIN_FONT_PX}），"
                             f"自然尺寸 {w}x{h} 太宽——加 --width 或精简节点文字")
        print(f"🖼 mermaid 自然尺寸 {w}x{h}；节点 {node_count} 个；缩到 {args.width}px 后有效字号 {eff_font:.1f}px")
        # 语法错误已由 measure 的 BAD 标志（只查 svg.innerHTML）断言；
        # 不能扫全 DOM——内联的 mermaid.min.js 源码本身就含 "Syntax error" 字符串。
        raw = work / "reading-aon.raw.png"
        rf.screenshot(html, raw, (w, h), work)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        ww, hh = rf.trim_and_resize(raw, args.out, args.width, work)

    visible = re.sub(r"<script>.*?</script>", "", html_text, flags=re.S)
    leaked = [p for p in rf.FORBIDDEN if p in parsed["text"] + visible]
    if leaked:
        args.out.unlink(missing_ok=True)
        raise SystemExit(f"图里出现了不该有的信息：{leaked}")
    ww, hh = check_png(args.out, args.width)
    print(f"🖼 完成 {rf.show(args.out)}  {ww}x{hh}px（@2x 超采样后缩到 {args.width} 宽）")
    print("\n✅ 阅读层铺开 AON：CPM 独立重算通过 / 标注四方对账通过 / 渲染成功 / PNG 自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())