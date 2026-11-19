#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_flow_levels.py —— 把 L2/L3/L4 的三张单代号网络图（AON / PDM）渲染成 PNG。

一条命令重跑（在仓库根目录；默认三张全渲染）：

    python3 manual/shots/render_flow_levels.py              # 渲染 L2/L3/L4 + 全部自检
    python3 manual/shots/render_flow_levels.py --level l2   # 只渲染一张
    python3 manual/shots/render_flow_levels.py --width 1400 # 答辩投影用更宽的图

源文件（只改这些，再跑本脚本）：
    manual/flow-l2.mmd → manual/images/aon-l2.png
    manual/flow-l3.mmd → manual/images/aon-l3.png
    manual/flow-l4.mmd → manual/images/aon-l4.png

它做四件事（与 render_flow.py 的 L1 图同一条流水线）：

1. **核对**：读 mmd，用图里的工期和实线 FS 箭头重算一遍 CPM（正推 ES/EF、逆推 LS/LF），
   逐项比对节点里写的数值；再核对结构（节点集合 / 依赖边 / 根节点 / 汇聚节点 / 关键路径的
   class 与 linkStyle），以及注释里的「关键路径」「总工期」「浮动」与重算结果一致。
   工期不是验收时限（三张图里每个节点都标了「工期 N（估）」），这一点也在这里断言。
2. **渲染**：把 mermaid@11 内联进临时 HTML，用 google-chrome 无头浏览器跑出 SVG。
   mermaid 优先用仓库内副本 `design/assets/mermaid.min.js`（11.17.2，离线可重跑），
   本机没有时才回退 render_flow.py 的 CDN 取法（CDN 不可达只影响回退路径）。
3. **截图**：`--dump-dom` 读回 SVG 的自然尺寸 → 按该尺寸 `--screenshot`
   （`--force-device-scale-factor=2` 超采样，保证缩到目标宽度后文字仍清晰）。
4. **落盘 + 图形自检**：`convert -trim` 裁白边 → 缩到约定宽度 1100px（与 L1 的
   `flow-aon.png` 同宽）→ 四周补白边；然后检查 PNG 宽度、非空白、关键路径橙色像素、
   普通节点灰色像素，以及 SVG 里真的画出了每个节点、每个活动名、回流标签，并且 0 个
   mermaid 语法错误。

依赖：本机已有的 python3 / google-chrome / ImageMagick(convert)，以及仓库内的 mermaid 副本。
不新增依赖；不改 `render_flow.py`、`flow.mmd`、`flow-aoa.mmd`、任何页面或旧图。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent      # manual/shots
REPO = HERE.parents[1]                      # 仓库根目录
IMAGES = REPO / "manual" / "images"
MERMAID_LOCAL = REPO / "design" / "assets" / "mermaid.min.js"

# 复用 L1 渲染脚本的浏览器 / 截图 / 裁剪逻辑（不改它，只 import 函数与常量）
sys.path.insert(0, str(HERE))
import render_flow as rf  # noqa: E402

DEFAULT_WIDTH = 1100       # 与 L1 的 flow-aon.png 同宽
MARGIN = rf.MARGIN         # 最终 PNG 四周留白（px）
FORBIDDEN = rf.FORBIDDEN   # 图上不得出现的本机信息

# 关键路径橙 / 普通节点灰：与 flow.mmd、render_flow.py 完全同一套配色
CRIT_FILL = (255, 241, 224)     # #fff1e0
CRIT_STROKE = (230, 81, 0)      # #e65100
NORMAL_FILL = (246, 247, 249)   # #f6f7f9

# 每级的元信息 + 期望结构（结构写死在这里：mmd 改坏了，自检会先报错，而不是画出错的图）
LEVELS = {
    "l2": {
        "mmd": REPO / "manual" / "flow-l2.mmd",
        "png": IMAGES / "aon-l2.png",
        "fig_no": 2,
        "name": "L2「换」",
        "count_text": "四个换真件 + 一个级考核",
        "nodes": ["P10", "P11", "P12", "P13", "G2"],
        "solid": [("P10", "P12"), ("P11", "P12"), ("P12", "P13"), ("P13", "G2")],
        "feedback": [],
        "converge": {"P12": ["P10", "P11"]},
        "legend_extra": (
            "起点 = L1 交付（A0–A9 全绿，图外）｜ "
            "真数据 P10 与真契约 P11 并行（都只依赖 L1），执行器等两者、部署等执行器"
        ),
    },
    "l3": {
        "mmd": REPO / "manual" / "flow-l3.mmd",
        "png": IMAGES / "aon-l3.png",
        "fig_no": 3,
        "name": "L3「审」",
        "count_text": "四个审的动作 + 一个级考核",
        "nodes": ["P14", "P15", "P16", "P17", "G3"],
        "solid": [("P14", "P15"), ("P15", "P16"), ("P16", "P17"), ("P17", "G3")],
        "feedback": [("P17", "P15")],
        "converge": {},
        "legend_extra": (
            "虚线 P17 → P15 = 纠错失败/可重试时回生成重试（回流边是重试路径，不计入 CPM）｜ "
            "起点 = L2 终局 G2（图外）"
        ),
    },
    "l4": {
        "mmd": REPO / "manual" / "flow-l4.mmd",
        "png": IMAGES / "aon-l4.png",
        "fig_no": 4,
        "name": "L4「守」",
        "count_text": "五个守的动作 + 一个级考核",
        "nodes": ["P18", "P19", "P20", "P21", "P22", "G4"],
        "solid": [("P18", "P19"), ("P19", "P20"), ("P20", "P21"), ("P21", "P22"),
                  ("P18", "P22"), ("P19", "P22"), ("P20", "P22"), ("P22", "G4")],
        "feedback": [],
        "converge": {"P22": ["P18", "P19", "P20", "P21"]},
        "legend_extra": (
            "P22 回归是汇聚节点：前四项全部完成才能开始（P18/P19/P20 直连 P22 的三条是汇聚边，"
            "不是驱动边）｜ 起点 = L3 终局 G3（图外）"
        ),
    },
}


# ------------------------------------------------------------------ 1. 读 + 核对

def show(path: Path) -> str:
    """给日志用：仓库内文件显示相对路径，仓库外显示原路径。"""
    return rf.show(path)


def read_mmd(path: Path):
    """读一张 AON，返回 (原文, 注释行, 节点标签, 实线边, 虚线回流边, class 集合, linkStyle)。"""
    text = path.read_text(encoding="utf-8")
    comments = [ln for ln in text.splitlines() if ln.lstrip().startswith("%%")]
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%%"))

    if not re.search(r"^flowchart\s+LR\s*$", body, re.M):
        raise SystemExit(f"{show(path)} 必须以 `flowchart LR` 声明（单代号网络图从左到右排）")

    nodes: dict[str, str] = {}
    for m in re.finditer(r'^\s*([A-Za-z]\w*)\["(.*)"\]\s*$', body, re.M):
        nodes[m.group(1)] = m.group(2)
    if not nodes:
        raise SystemExit(f"{show(path)} 里没有读到任何节点")

    solid: list[tuple[str, str]] = []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*-->\|([^|]*)\|\s*([A-Za-z]\w*)\s*$", body, re.M):
        if m.group(2).strip() != "FS":
            raise SystemExit(f"{show(path)} 箭头 {m.group(1)}→{m.group(3)} 没有标 FS（依赖只用完成-开始关系）")
        solid.append((m.group(1), m.group(3)))

    feedback: list[tuple[str, str]] = []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*-\.->\|([^|]*)\|\s*([A-Za-z]\w*)\s*$", body, re.M):
        if "回流" not in m.group(2):
            raise SystemExit(f"{show(path)} 虚线边 {m.group(1)}→{m.group(3)} 必须标「回流」（它是重试路径，不是 FS 依赖）")
        feedback.append((m.group(1), m.group(3)))

    classes: dict[str, list[str]] = {}
    for m in re.finditer(r"^\s*class[ \t]+([\w, \t]+?)[ \t]+(critical|normal)[ \t]*$", body, re.M):
        classes[m.group(2)] = [x.strip() for x in m.group(1).split(",") if x.strip()]

    links: dict[str, list[int]] = {"critical": [], "normal": [], "feedback": []}
    for m in re.finditer(r"^\s*linkStyle\s+([\d,]+)\s+(.*)$", body, re.M):
        idx = [int(x) for x in m.group(1).split(",") if x.strip()]
        style = m.group(2)
        if "e65100" in style:
            links["critical"].extend(idx)
        elif "dasharray" in style:
            links["feedback"].extend(idx)
        else:
            links["normal"].extend(idx)
    return text, comments, nodes, solid, feedback, classes, links


def cpm(nodes: dict[str, str], solid: list[tuple[str, str]]):
    """按 mmd 里的工期和 FS 箭头独立重算 CPM（Kahn 拓扑序正推 + 逆推）。"""
    dur = {}
    for nid, label in nodes.items():
        m = re.search(r"工期\s*(\d+)", label)
        if not m:
            raise SystemExit(f"{nid} 的节点里没有「工期 N」")
        dur[nid] = int(m.group(1))

    succ: dict[str, list[str]] = {n: [] for n in nodes}
    pred: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in solid:
        if u not in nodes or v not in nodes:
            raise SystemExit(f"依赖边 {u}→{v} 引用了不存在的节点")
        succ[u].append(v)
        pred[v].append(u)

    indeg = {n: len(pred[n]) for n in nodes}
    queue = [n for n in nodes if indeg[n] == 0]
    topo: list[str] = []
    while queue:
        cur = queue.pop(0)
        topo.append(cur)
        for nxt in succ[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(topo) != len(nodes):
        raise SystemExit("实线 FS 依赖有环，不是合法 AON（回流虚线不参与 CPM，不能替代依赖）")

    ES, EF = {}, {}
    for n in topo:
        ES[n] = max((EF[p] for p in pred[n]), default=0)
        EF[n] = ES[n] + dur[n]
    T = max(EF.values())

    LS, LF = {}, {}
    for n in reversed(topo):
        LF[n] = min((LS[s] for s in succ[n]), default=T)
        LS[n] = LF[n] - dur[n]
    TF = {n: LS[n] - ES[n] for n in nodes}

    starts = [n for n in topo if not pred[n]]
    crit_starts = [n for n in starts if TF[n] == 0]
    if len(crit_starts) != 1:
        raise SystemExit(f"关键路径起点应唯一，实际 {crit_starts or starts}")
    path = [crit_starts[0]]
    while True:
        nxt = [s for s in succ[path[-1]] if TF[s] == 0 and EF[path[-1]] == ES[s]]
        if len(nxt) > 1:
            raise SystemExit(f"关键路径在 {path[-1]} 分叉，图里需要人工确认")
        if not nxt:
            break
        path.append(nxt[0])
    if EF[path[-1]] != T:
        raise SystemExit("关键路径没有走到工期终点，检查 mmd")
    return dur, ES, EF, LS, LF, TF, T, path, pred, succ


def check_network(level: str, meta: dict):
    """核对一张网：结构 + CPM 字段 + class/linkStyle + 注释声明。返回 CPM 结果。"""
    path = meta["mmd"]
    text, comments, nodes, solid, feedback, classes, links = read_mmd(path)

    if list(nodes) != meta["nodes"]:
        raise SystemExit(f"{show(path)} 节点必须恰好是 {meta['nodes']}，实际读到 {list(nodes)}")
    if solid != meta["solid"]:
        raise SystemExit(f"{show(path)} 实线依赖与设计不符：\n  mmd {solid}\n  期望 {meta['solid']}")
    if feedback != meta["feedback"]:
        raise SystemExit(f"{show(path)} 虚线回流边与设计不符：{feedback} / 期望 {meta['feedback']}")

    # 节点标签的硬指标：四行结构（编号+活动名 / 工期（估）/ ES EF LS LF / 判据）+ 不带「验证」节点
    for nid, label in nodes.items():
        if not re.match(rf"<b>{nid} \S", label):
            raise SystemExit(f"{nid} 的节点标签第一行必须是 <b>编号 活动名</b>")
        if "工期" not in label or "（估）" not in label:
            raise SystemExit(f"{nid} 的工期没有标「（估）」——工期口径必须写清是估算值")
        if "ES" not in label or "LS" not in label:
            raise SystemExit(f"{nid} 的节点里没有 ES/EF/LS/LF")
        if "判据：" not in label:
            raise SystemExit(f"{nid} 的节点里没有「判据：」")
    if "验证" in "".join(nodes.values()):
        raise SystemExit("节点里出现了「验证」—— 验证只能是完成判据，不能单独成节点")

    dur, ES, EF, LS, LF, TF, T, path, pred, succ = cpm(nodes, solid)

    # 逐节点比对 mmd 标注
    for nid, label in nodes.items():
        m = re.search(r"ES(\d+)\s+EF(\d+)\s+LS(\d+)\s+LF(\d+)", label)
        if not m:
            raise SystemExit(f"{nid} 的节点里没有「ES.. EF.. LS.. LF..」")
        got = tuple(int(x) for x in m.groups())
        want = (ES[nid], EF[nid], LS[nid], LF[nid])
        if got != want:
            raise SystemExit(f"{nid} 的 CPM 数值与重算不符：mmd 写 {got}，重算 {want}")
        if EF[nid] != ES[nid] + dur[nid] or LS[nid] != LF[nid] - dur[nid]:
            raise SystemExit(f"{nid} 的 CPM 自洽断言失败（EF=ES+工期 / LS=LF-工期）")
        if TF[nid] < 0:
            raise SystemExit(f"{nid} 的总浮动为负：{TF[nid]}")

    # class critical / normal 与「总浮动 = 0」集合一致
    crit_computed = {n for n in nodes if TF[n] == 0}
    if set(classes.get("critical", [])) != crit_computed:
        raise SystemExit(f"class critical 与总浮动=0 的集合不符：mmd {sorted(classes.get('critical', []))} vs 重算 {sorted(crit_computed)}")
    if set(classes.get("normal", [])) != set(nodes) - crit_computed:
        raise SystemExit("class normal 应恰好是非关键节点")

    # linkStyle 的橙色箭头 = 关键路径上的驱动边；虚线 = 回流边
    path_pairs = set(zip(path, path[1:]))
    crit_edges = {i for i, (u, v) in enumerate(solid) if (u, v) in path_pairs}
    if set(links["critical"]) != crit_edges:
        raise SystemExit(f"linkStyle 橙色箭头与关键路径不符：mmd {sorted(links['critical'])} vs 期望 {sorted(crit_edges)}")
    fb_idx = set(range(len(solid), len(solid) + len(feedback)))
    if set(links["feedback"]) != fb_idx:
        raise SystemExit(f"linkStyle 虚线序号与回流边不符：mmd {sorted(links['feedback'])} vs 期望 {sorted(fb_idx)}")
    if set(links["normal"]) != set(range(len(solid))) - crit_edges:
        raise SystemExit("linkStyle 灰色箭头应恰好是非关键依赖边")

    # 注释声明：关键路径、总工期、浮动
    comment_text = "\n".join(comments)
    m = re.search(r"%%\s*关键路径：([^，\n]+)，总工期\s*(\d+)\s*分钟", comment_text)
    if not m:
        raise SystemExit(f"{show(path)} 注释里缺少「%% 关键路径：…，总工期 N 分钟」")
    declared_path = [x.strip() for x in re.split(r"→", m.group(1)) if x.strip()]
    if declared_path != path:
        raise SystemExit(f"{show(path)} 注释声明的关键路径 {declared_path} 与重算 {path} 不符")
    if int(m.group(2)) != T:
        raise SystemExit(f"{show(path)} 注释声明的总工期 {m.group(2)} ≠ 重算 {T}")
    floats = [n for n in nodes if TF[n] > 0]
    if floats:
        for n in floats:
            if f"{n}（" not in comment_text or f"总浮动 {TF[n]} 分钟" not in comment_text:
                raise SystemExit(f"{show(path)} 注释没有写清 {n} 的 {TF[n]} 分钟总浮动")
    elif "总浮动 0" not in comment_text:
        raise SystemExit(f"{show(path)} 注释没有声明「所有节点总浮动 0」")

    # 结构断言：根 / 汇聚（依赖表是不是真的按设计连的）
    roots = [n for n in nodes if not pred[n]]
    if level == "l2":
        if set(roots) != {"P10", "P11"}:
            raise SystemExit(f"L2 的起点应是 P10/P11（都只依赖 L1 交付），实际 {roots}")
    else:
        if roots != [meta["nodes"][0]]:
            raise SystemExit(f"{level} 的起点应唯一 = {meta['nodes'][0]}，实际 {roots}")
    for nid, want_preds in meta["converge"].items():
        if set(pred[nid]) != set(want_preds):
            raise SystemExit(f"{nid} 的紧前应是 {sort_nodes(want_preds)}，实际 {sort_nodes(pred[nid])}")
    if level == "l2" and len(pred["P12"]) != 2:
        raise SystemExit("L2 执行器 P12 必须同时依赖真数据与真契约")
    if level == "l3":
        for u, v in feedback:
            if ES[u] + dur[u] <= ES[v]:
                raise SystemExit(f"回流边 {u}→{v} 必须是从后往前指（重试路径），实际看起来是正向依赖")
    return dict(dur=dur, ES=ES, EF=EF, LS=LS, LF=LF, TF=TF, T=T, path=path,
                nodes=nodes, solid=solid, feedback=feedback, text=text)


def sort_nodes(ids) -> list[str]:
    return sorted(ids, key=lambda x: (x[0], int(re.sub(r"\D", "", x) or 0)))


# ------------------------------------------------------------------ 2. HTML + 渲染

def fetch_mermaid() -> str:
    """优先仓库内副本（离线可重跑）；没有才回退 render_flow.py 的 CDN 取法。"""
    if MERMAID_LOCAL.exists():
        data = MERMAID_LOCAL.read_text(encoding="utf-8")
        if len(data) > 1_000_000 and "mermaid" in data[:200_000]:
            print(f"↓ 使用仓库内 mermaid：{show(MERMAID_LOCAL)}")
            return data
        raise SystemExit(f"仓库内 mermaid 副本异常（大小 {len(data)}）：{show(MERMAID_LOCAL)}")
    print("↓ 仓库内没有 design/assets/mermaid.min.js，回退 CDN …")
    return rf.fetch_mermaid()


def build_html(meta: dict, mmd: str, mermaid_js: str, total: int, path: list[str],
               floats: list[str], tf: dict) -> str:
    title = f"图 {meta['fig_no']} · {meta['name']}的单代号网络图（AON / 紧前关系法 PDM）"
    if floats:
        float_note = " · " + "、".join(f"{n} 总浮动 {tf[n]} 分钟" for n in floats)
    else:
        float_note = " · 全串行，总浮动 0"
    sub = (
        f"{meta['count_text']} · 总工期 {total} 分钟（估算）· "
        f"关键路径 {' → '.join(path)}{float_note}"
    )
    legend = (
        "<b>橙色粗框 / 粗箭头</b> = 关键路径（总浮动 0） ｜ "
        "箭头上的 <b>FS</b> = 完成–开始紧前关系（紧前判据绿了，紧后才开始）<br/>"
        "节点内：编号 + 活动名 / 工期（估）/ ES EF LS LF / 完成判据（看到它才算这一页做完）<br/>"
        "<b>工期 = 估算值（分钟）</b>，只用于表达判据依赖与关键路径，<b>不是验收时限</b>；"
        "验证 = 完成判据，不单独成节点<br/>"
        f"{meta['legend_extra']}"
    )
    # mmd 原文里只有 <br/> 一种 HTML 标签，可直接放进 <pre>（mermaid 读 innerHTML）
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>flow-levels</title>
<style>
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
body {{ display: inline-block; }}
.fig {{ padding: 18px 22px; font-family: {rf.FONT_STACK}; color: #1a1a1a; }}
.fig-title {{ font-size: {rf.FIG_TITLE_PX}px; font-weight: 600; line-height: 1.5; margin: 0 0 2px; }}
.fig-sub {{ font-size: {rf.FIG_SMALL_PX}px; line-height: 1.6; color: #555; margin: 0 0 10px; }}
#holder svg {{ display: block; }}
.fig-legend {{ font-size: {rf.FIG_SMALL_PX}px; line-height: 1.7; color: #444; margin: 10px 0 0; }}
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
  mermaid.initialize({json.dumps(rf.MERMAID_CFG)});
  mermaid.run({{ querySelector: '.mermaid' }}).then(() => {{
    const r = document.querySelector('.fig').getBoundingClientRect();
    document.title = 'DIM ' + Math.ceil(r.width) + ' ' + Math.ceil(r.height);
  }}).catch((e) => {{ document.title = 'ERR ' + (e && e.message ? e.message : e); }});
</script>
</body></html>
"""


def measure(html: Path, work: Path) -> tuple[int, int, str]:
    """量自然尺寸，并返回 dump-dom 的完整 HTML（后面用来自检 SVG 里画了什么）。"""
    proc = rf.chrome([
        "--window-size=4000,2600",
        "--virtual-time-budget=20000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", html.as_uri(),
    ])
    dom = proc.stdout
    m = re.search(r"<title>DIM (\d+) (\d+)</title>", dom)
    if not m:
        err = re.search(r"<title>ERR ([^<]*)</title>", dom)
        raise SystemExit(
            "mermaid 渲染失败："
            + (err.group(1) if err else (proc.stderr or dom)[-2000:])
        )
    return int(m.group(1)), int(m.group(2)), dom


def check_svg(dom: str, meta: dict, cpm_data: dict) -> None:
    """图形自检 A：SVG 里真的画出了每个节点 / 活动名 / 回流标签，且没有语法错误。"""
    i = dom.find("<svg")
    j = dom.find("</svg>")
    if i < 0 or j < 0:
        raise SystemExit("dump-dom 里找不到 <svg>：mermaid 没画出来")
    svg = dom[i:j + 6]
    if "Syntax error" in svg:
        raise SystemExit("SVG 里出现 mermaid 语法错误标记")
    count = len(re.findall(r'class="node ', svg))
    if count != len(meta["nodes"]):
        raise SystemExit(f"SVG 里画了 {count} 个节点，期望 {len(meta['nodes'])} 个")
    for nid in meta["nodes"]:
        if nid not in svg:
            raise SystemExit(f"SVG 里没有节点编号 {nid}")
        name = cpm_data["nodes"][nid].split("</b>")[0].replace(f"<b>{nid} ", "")
        if name not in svg:
            raise SystemExit(f"SVG 里没有节点 {nid} 的活动名「{name}」")
    for u, v in meta["feedback"]:
        if "回流" not in svg:
            raise SystemExit(f"SVG 里没有「回流」标签（虚线 {u}→{v}）")
    if "#e65100" not in svg:
        raise SystemExit("SVG 里没有关键路径橙色（classDef 没生效）")


def color_counts(png: Path) -> dict[tuple[int, int, int], int]:
    """用 ImageMagick 的直方图数像素：不引入 PIL，沿用本仓库 render 脚本的 convert 依赖。"""
    proc = subprocess.run(
        ["convert", str(png), "-format", "%c", "histogram:info:-"],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise SystemExit("ImageMagick 直方图失败：" + (proc.stderr or proc.stdout)[-1000:])
    counts: dict[tuple[int, int, int], int] = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*(\d+):\s*\((\d+),(\d+),(\d+)\)", line)
        if m:
            counts[(int(m.group(2)), int(m.group(3)), int(m.group(4)))] = int(m.group(1))
    return counts


def check_png(png: Path, meta: dict, width: int, has_normal: bool) -> tuple[int, int]:
    """图形自检 B：PNG 尺寸、非空白、关键路径橙色、普通节点灰色都真的存在。"""
    proc = subprocess.run(["identify", "-format", "%w %h", str(png)],
                          capture_output=True, text=True, timeout=60, check=True)
    w, h = (int(x) for x in proc.stdout.split())
    if w != width:
        raise SystemExit(f"{show(png)} 宽度 {w}px，不等于约定 {width}px")
    if not 150 <= h <= 900:
        raise SystemExit(f"{show(png)} 高度 {h}px 不在合理区间（150–900）")
    counts = color_counts(png)
    non_white = sum(c for px, c in counts.items() if px != (255, 255, 255))
    if non_white < 20000:
        raise SystemExit(f"{show(png)} 几乎空白（非白像素只有 {non_white}）")
    # 描边经过缩采样后不会全是精确的 #e65100（抗锯齿会把边缘混进背景色），
    # 所以描边按「接近橙」统计；填充看精确色（节点内部大面积保持原色）。
    orange = sum(c for px, c in counts.items()
                 if (px[0] - CRIT_STROKE[0]) ** 2 + (px[1] - CRIT_STROKE[1]) ** 2
                 + (px[2] - CRIT_STROKE[2]) ** 2 <= 40 * 40)
    if orange < 3000:
        raise SystemExit(f"{show(png)} 没有足够的关键路径橙色描边（{orange} 像素）")
    if counts.get(CRIT_FILL, 0) < 3000:
        raise SystemExit(f"{show(png)} 没有足够的关键节点浅橙底（{counts.get(CRIT_FILL, 0)} 像素）")
    if has_normal and counts.get(NORMAL_FILL, 0) < 1000:
        raise SystemExit(f"{show(png)} 没有普通节点的灰色底（{counts.get(NORMAL_FILL, 0)} 像素）")
    return w, h


def render_one(level: str, meta: dict, width: int, mermaid_js: str) -> tuple[int, int]:
    cpm_data = check_network(level, meta)
    T, path, TF = cpm_data["T"], cpm_data["path"], cpm_data["TF"]
    nodes = cpm_data["nodes"]

    print(f"\n== {level.upper()} · {show(meta['mmd'])}")
    print(f"✅ CPM 核对通过：总工期 {T} 分钟（估）；关键路径 {' → '.join(path)}")
    print(f"{'编号':<4}{'工期':>4}{'ES':>4}{'EF':>4}{'LS':>4}{'LF':>4}{'总浮动':>6}  关键")
    for nid in nodes:
        print(f"{nid:<4}{cpm_data['dur'][nid]:>6}{cpm_data['ES'][nid]:>6}"
              f"{cpm_data['EF'][nid]:>6}{cpm_data['LS'][nid]:>6}{cpm_data['LF'][nid]:>6}"
              f"{TF[nid]:>8}  {'★' if TF[nid] == 0 else ''}")
    floats = [n for n in nodes if TF[n] > 0]

    print(f"🖼 渲染 {show(meta['mmd'])} → {show(meta['png'])}")
    with tempfile.TemporaryDirectory(prefix=f"aon-{level}-") as tmp:
        work = Path(tmp)
        html = work / f"aon-{level}.html"
        html.write_text(build_html(meta, cpm_data["text"], mermaid_js, T, path, floats, TF),
                        encoding="utf-8")
        size = measure(html, work)
        print(f"   自然尺寸 {size[0]}x{size[1]}（1:1）")
        check_svg(size[2], meta, cpm_data)
        print(f"   SVG 自检：{len(nodes)} 个节点 / 活动名齐全 / 回流标签 {len(meta['feedback'])} / 语法错误 0")

        raw = work / f"aon-{level}.raw.png"
        rf.screenshot(html, raw, (size[0], size[1]), work)

        visible = re.sub(r"<script>.*?</script>", "", html.read_text(encoding="utf-8"), flags=re.S)
        meta["png"].parent.mkdir(parents=True, exist_ok=True)
        w, h = rf.trim_and_resize(raw, meta["png"], width, work)

    leaked = [p for p in FORBIDDEN if p in cpm_data["text"] + visible]
    if leaked:
        meta["png"].unlink(missing_ok=True)
        raise SystemExit(f"图里出现了不该有的信息：{leaked}")
    has_normal = any(TF[n] > 0 for n in nodes)
    w, h = check_png(meta["png"], meta, width, has_normal)
    if has_normal:
        print(f"   PNG 自检：宽度 {w}px（= L1 同宽）/ 非空 / 关键橙色 + 普通灰底都在")
    else:
        print(f"   PNG 自检：宽度 {w}px（= L1 同宽）/ 非空 / 关键橙色都在（本图无普通节点）")
    print(f"🖼 完成 {show(meta['png'])}  {w}x{h}px（@2x 超采样后缩到 {width} 宽）")
    return w, h


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="把 L2/L3/L4 的 flow-l*.mmd 渲染成 manual/images/aon-l*.png（含 CPM 与图形自检）")
    ap.add_argument("--level", choices=sorted(LEVELS), action="append",
                    help="只渲染指定级（可重复；默认三张全渲染）")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                    help=f"输出 PNG 宽度（默认 {DEFAULT_WIDTH}px，与 L1 的 flow-aon.png 同宽；答辩投影可用 1400）")
    args = ap.parse_args()
    if args.width < 900:
        raise SystemExit("--width 太小，节点文字会看不清（≥900）")

    targets = args.level or ["l2", "l3", "l4"]
    mermaid_js = fetch_mermaid()
    results = {}
    for level in targets:
        results[level] = render_one(level, LEVELS[level], args.width, mermaid_js)

    print(f"\n✅ {len(targets)}/3 张网络图：CPM 自检通过、渲染成功、PNG 自检通过")
    for level in targets:
        w, h = results[level]
        print(f"   {show(LEVELS[level]['png'])}  {w}x{h}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
