#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_flow_l2_l5.py —— 把 L2–L5 合并单代号网络图（AON / PDM）渲染成 PNG。

一条命令重跑（在仓库根目录）：

    python3 tutorial/shots/render_flow_l2_l5.py              # 渲染 + CPM / 结构 / 图形自检
    python3 tutorial/shots/render_flow_l2_l5.py --width 1400 # 答辩投影用更窄的图

源文件（唯一内容源，只改它）：
    tutorial/flow-l2-l5.mmd → tutorial/images/aon-l2-l5.png

它做五件事：

1. **核对**：读 mmd，用图里的工期和 FS 箭头（级内实线 + 级间虚线；回流点线不计）重算 CPM
   （正推 ES/EF、逆推 LS/LF），逐节点比对节点里写的数值；再核对结构（18 节点 / 四条泳道 /
   17 条级内依赖 / 3 条级间依赖 / 1 条回流 / 汇聚节点 / 根节点），以及注释里的
   「关键路径」「总工期」「浮动」与重算结果一致，class critical / linkStyle 与关键路径一致。
   工期不是验收时限（每个节点都标「工期 N（估）」），这一点也在这里断言。
2. **语法自检**：把 mmd 原样交给 mermaid@11（仓库内离线副本）渲染一遍，确认它仍是合法 mermaid
   图（18 个节点、0 个语法错误）。**注意**：mermaid 自动布局会把这条 18 节点链拉成一条长条
   （子图方向与跨子图边互斥，见 tutorial/aon/README.md），所以正式出图不走 mermaid 自动布局，
   而是第 3 步按四条泳道重排。
3. **布局 + 画 SVG**：按 mmd 里的子图把节点排成四条泳道（L2 换 / L3 审 / L4 守 / L5 装），
   级内从左到右、段间蛇形换向，级间用短竖箭头衔接；节点尺寸由节点文字量决定（并断言不溢出）；
   关键路径橙色、普通节点灰色、级考核菱形化、回流点线。全部几何由脚本算出（不手绘坐标）。
4. **截图**：用 google-chrome 无头浏览器按自然尺寸截图（@2x 超采样），再裁白边、缩到约定宽度。
5. **落盘 + 图形自检**：检查 PNG 宽度、非空白、关键路径橙色描边 / 浅橙底 / 普通节点灰底，
   以及 SVG/DOM 里 18 个节点、18 个活动名、四条泳道标题、级间与回流标签都在，文字 0 溢出。

依赖：本机已有的 python3 / google-chrome / ImageMagick(identify/convert)，仓库内 mermaid 副本。
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

HERE = Path(__file__).resolve().parent      # tutorial/shots
REPO = HERE.parents[1]                      # 仓库根目录
MMD = REPO / "manual" / "flow-l2-l5.mmd"
OUT = REPO / "manual" / "images" / "aon-l2-l5.png"
MERMAID_LOCAL = REPO / "design" / "assets" / "mermaid.min.js"

# 复用 L1 渲染脚本的浏览器 / 截图 / 裁剪逻辑（不改它，只 import 函数与常量）
sys.path.insert(0, str(HERE))
import render_flow as rf  # noqa: E402

DEFAULT_WIDTH = 1600       # 任务口径：与现有 AON 同宽（1100）或 1600；合并图信息多，取 1600
MARGIN = rf.MARGIN         # 最终 PNG 四周留白（px）
FORBIDDEN = rf.FORBIDDEN   # 图上不得出现的本机信息
FIG_TITLE_PX = 28
FIG_SMALL_PX = 18

# 关键路径橙 / 普通节点灰：与 flow.mmd、render_flow.py 完全同一套配色
CRIT_FILL = (255, 241, 224)     # #fff1e0
CRIT_STROKE = (230, 81, 0)      # #e65100
NORMAL_FILL = (246, 247, 249)   # #f6f7f9

# 节点内部排版（px，1:1 画布坐标系；最后整体缩到 --width）
FONT_TITLE = 20
FONT_META = 16
LINE_TITLE = 26
LINE = 22
NODE_PAD_X = 14
NODE_PAD_Y = 10
GATE_R = 10             # 级考核六边形里程碑的斜边宽度
NODE_GAP_X = 44         # 同一条泳道内相邻节点的水平间距（放箭头）
LANE_GAP_Y = 84         # 相邻泳道之间的竖直间距（放级间箭头 + 回流通道）
BAND_PAD_TOP = 33       # 泳道标题行的高度
BAND_PAD_BOTTOM = 12

# 期望结构（写死在这里：mmd 改坏了，自检会先报错，而不是画出错的图）
EXPECTED_LANES = [
    ("L2", ["P10", "P11", "P12", "P13", "G2"]),
    ("L3", ["P14", "P15", "P16", "P17", "G3"]),
    ("L4", ["P18", "P19", "P20", "P21", "P22", "G4"]),
    ("L5", ["P23", "G5"]),
]
# 泳道读向：+1 = 从左到右，-1 = 从右到左（段间蛇形，让级间箭头是短竖线）
LANE_DIRS = {"L2": 1, "L3": -1, "L4": 1, "L5": -1}
EXPECTED_SOLID = [
    ("P10", "P12"), ("P11", "P12"), ("P12", "P13"), ("P13", "G2"),
    ("P14", "P15"), ("P15", "P16"), ("P16", "P17"), ("P17", "G3"),
    ("P18", "P19"), ("P19", "P20"), ("P20", "P21"), ("P21", "P22"),
    ("P18", "P22"), ("P19", "P22"), ("P20", "P22"), ("P22", "G4"),
    ("P23", "G5"),
]
EXPECTED_INTER = [("G2", "P14"), ("G3", "P18"), ("G4", "P23")]
EXPECTED_FEEDBACK = [("P17", "P15")]
EXPECTED_CONVERGE = {
    "P12": {"P10", "P11"},
    "P22": {"P18", "P19", "P20", "P21"},
}
EXPECTED_ROOTS = ["P10", "P11"]
# 工期（分钟，估）：L2–L4 沿用三张分图的冻结估算值（旧图已退役，数值见 git 历史）；
# L5 是新页，按同一口径给估算值（P23 一个页面动作 20 + 级考核 10）。
EXPECTED_DUR = {
    "P10": 25, "P11": 20, "P12": 25, "P13": 20, "G2": 10,
    "P14": 30, "P15": 25, "P16": 20, "P17": 25, "G3": 10,
    "P18": 15, "P19": 20, "P20": 20, "P21": 20, "P22": 20, "G4": 15,
    "P23": 20, "G5": 10,
}
LANE_LABELS = {
    "L2": "L2 换 ｜ P10–P13 + G2 级考核 ｜ 读向 → ｜ 起点 = L1 交付（A0–A9 全绿，图外）",
    "L3": "L3 审 ｜ P14–P17 + G3 级考核 ｜ 读向 ← ｜ 级间：G2 绿了才开始（虚线）",
    "L4": "L4 守 ｜ P18–P22 + G4 级考核 ｜ 读向 → ｜ P22 是汇聚节点（前四项全完成才回归）",
    "L5": "L5 装 ｜ P23 + G5 级考核 ｜ 读向 ← ｜ 级间：G4 绿了才开始（虚线）",
}


# ------------------------------------------------------------------ 1. 读 + 核对

def show(path: Path) -> str:
    return rf.show(path)


def parse_mmd(path: Path) -> dict:
    """读合并图：注释 / 节点（按声明顺序）/ 子图（=泳道）/ 依赖边（按源文件顺序，带全局序号）。

    边分三类：
      * 实线 -->|FS|          级内 FS 依赖（计入 CPM）
      * 虚线 -.->|级间FS|     级间 FS 依赖（L2→L3→L4→L5 串行，计入 CPM）
      * 点线 -.->|回流|       回流 / 重试路径（不计 CPM）
    """
    text = path.read_text(encoding="utf-8")
    comments = [ln for ln in text.splitlines() if ln.lstrip().startswith("%%")]
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%%"))

    if not re.search(r"^flowchart\s+LR\s*$", body, re.M):
        raise SystemExit(f"{show(path)} 必须以 `flowchart LR` 声明（单代号网络图从左到右排）")

    # 节点 + 所属子图（泳道）
    lanes: list[tuple[str, list[str]]] = []
    nodes: dict[str, str] = {}
    cur_lane: str | None = None
    for ln in body.splitlines():
        m = re.match(r'^\s*subgraph\s+(\w+)\["([^"]*)"\]\s*$', ln)
        if m:
            if cur_lane is not None:
                raise SystemExit(f"{show(path)} 子图嵌套了，合并图只允许一层泳道子图")
            cur_lane = m.group(1)
            lanes.append((cur_lane, []))
            continue
        if re.match(r"^\s*end\s*$", ln):
            if cur_lane is None:
                raise SystemExit(f"{show(path)} 出现多余的 end")
            cur_lane = None
            continue
        m = re.match(r'^\s*([A-Za-z]\w*)\["(.*)"\]\s*$', ln)
        if m:
            nid, label = m.group(1), m.group(2)
            if nid in nodes:
                raise SystemExit(f"{show(path)} 节点 {nid} 声明了两次")
            nodes[nid] = label
            if cur_lane is None:
                raise SystemExit(f"{show(path)} 节点 {nid} 不在任何泳道子图里")
            lanes[-1][1].append(nid)
    if not nodes:
        raise SystemExit(f"{show(path)} 里没有读到任何节点")

    # 依赖边（全局序号 = 源文件书写顺序，mermaid linkStyle 就是这么数的）
    edges: list[dict] = []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*(-->|-\.->)\|([^|]*)\|\s*([A-Za-z]\w*)\s*$", body, re.M):
        u, arrow, label, v = m.group(1), m.group(2), m.group(3).strip(), m.group(4)
        if u not in nodes or v not in nodes:
            raise SystemExit(f"{show(path)} 依赖边 {u}→{v} 引用了不存在的节点")
        if arrow == "-->":
            if label != "FS":
                raise SystemExit(f"{show(path)} 实线 {u}→{v} 必须标 FS（级内依赖只用完成-开始关系）")
            kind = "solid"
        elif "回流" in label:
            kind = "feedback"
        elif "级间" in label:
            kind = "inter"
        else:
            raise SystemExit(f"{show(path)} 虚线 {u}→{v} 的标签「{label}」既不是级间也不是回流")
        edges.append(dict(u=u, v=v, kind=kind, label=label, idx=len(edges)))

    if not any(e["kind"] == "solid" for e in edges):
        raise SystemExit(f"{show(path)} 没有级内实线依赖")
    if not any(e["kind"] == "inter" for e in edges):
        raise SystemExit(f"{show(path)} 没有级间虚线依赖——L2–L5 必须是串行的")

    classes: dict[str, list[str]] = {}
    for m in re.finditer(r"^\s*class[ \t]+([\w, \t]+?)[ \t]+(critical|normal)[ \t]*$", body, re.M):
        classes[m.group(2)] = [x.strip() for x in m.group(1).split(",") if x.strip()]

    links: dict[str, list[int]] = {"critical": [], "normal": [], "inter": [], "feedback": []}
    for m in re.finditer(r"^\s*linkStyle\s+([\d,]+)\s+(.*)$", body, re.M):
        idx = [int(x) for x in m.group(1).split(",") if x.strip()]
        style = m.group(2)
        if "dasharray" in style and "e65100" in style:
            links["inter"].extend(idx)
        elif "dasharray" in style:
            links["feedback"].extend(idx)
        elif "e65100" in style:
            links["critical"].extend(idx)
        else:
            links["normal"].extend(idx)

    return dict(text=text, comments=comments, body=body, nodes=nodes, lanes=lanes,
                edges=edges, classes=classes, links=links)


def label_fields(nid: str, label: str) -> dict:
    """拆节点标签：标题 / 工期行 / ES EF LS LF 行 / 判据行（1–4 行）。"""
    parts = [p.strip() for p in label.split("<br/>")]
    if not (5 <= len(parts) <= 7):
        raise SystemExit(f"{nid} 的节点标签应有 5–7 行（标题/工期/CPM/1–4 行判据），实际 {len(parts)} 行")
    title = re.sub(r"</?b>", "", parts[0]).strip()
    if not re.match(rf"^{nid} \S", title):
        raise SystemExit(f"{nid} 的节点标题第一行必须是「{nid} 活动名」，实际「{title}」")
    if not parts[1].startswith("工期"):
        raise SystemExit(f"{nid} 的第二行必须是工期行，实际「{parts[1]}」")
    if "（估）" not in parts[1]:
        raise SystemExit(f"{nid} 的工期没有标「（估）」——工期口径必须写清是估算值")
    m = re.search(r"工期\s*(\d+)", parts[1])
    if not m:
        raise SystemExit(f"{nid} 的工期行没有「工期 N」")
    m2 = re.match(r"^ES(\d+)\s+EF(\d+)\s+LS(\d+)\s+LF(\d+)$", parts[2])
    if not m2:
        raise SystemExit(f"{nid} 的第三行必须是「ES… EF… LS… LF…」，实际「{parts[2]}」")
    crit = parts[3:]
    if not crit or not crit[0].startswith("判据："):
        raise SystemExit(f"{nid} 的判据行必须以「判据：」开头")
    name = title[len(nid) + 1:]
    return dict(title=title, name=name, dur=int(m.group(1)),
                ES=int(m2.group(1)), EF=int(m2.group(2)),
                LS=int(m2.group(3)), LF=int(m2.group(4)),
                meta=[parts[1], parts[2]], crit=crit)


def cpm(nodes: dict[str, str], edges: list[dict]):
    """按 mmd 里的工期和 FS 箭头（级内 + 级间）独立重算 CPM（Kahn 拓扑序正推 + 逆推）。"""
    fields = {nid: label_fields(nid, lb) for nid, lb in nodes.items()}
    dur = {nid: f["dur"] for nid, f in fields.items()}

    succ: dict[str, list[str]] = {n: [] for n in nodes}
    pred: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        if e["kind"] == "feedback":
            continue                      # 回流点线是重试路径，不计入 CPM
        succ[e["u"]].append(e["v"])
        pred[e["v"]].append(e["u"])

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
        raise SystemExit("FS 依赖（级内 + 级间，不含回流）有环，不是合法 AON")

    ES, EF = {}, {}
    for n in topo:
        ES[n] = max((EF[p] for p in pred[n]), default=0)
        EF[n] = ES[n] + dur[n]
    total = max(EF.values())

    LS, LF = {}, {}
    for n in reversed(topo):
        LF[n] = min((LS[s] for s in succ[n]), default=total)
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
    if EF[path[-1]] != total:
        raise SystemExit("关键路径没有走到工期终点，检查 mmd")
    return dict(fields=fields, dur=dur, ES=ES, EF=EF, LS=LS, LF=LF, TF=TF,
                total=total, path=path, pred=pred, succ=succ)


def check_structure(parsed: dict, c: dict) -> None:
    """核对结构、CPM 标注、class/linkStyle、注释声明。"""
    nodes = parsed["nodes"]
    # 泳道 = 子图，节点顺序 = 泳道内声明顺序
    if [lane for lane, _ in parsed["lanes"]] != [lane for lane, _ in EXPECTED_LANES]:
        raise SystemExit(f"泳道应恰好是 {[x[0] for x in EXPECTED_LANES]}，实际 {[x[0] for x in parsed['lanes']]}")
    for (lane, want), (_, got) in zip(EXPECTED_LANES, parsed["lanes"]):
        if got != want:
            raise SystemExit(f"泳道 {lane} 的节点应恰好是 {want}，实际 {got}")
    expected_nodes = [n for _, lst in EXPECTED_LANES for n in lst]
    if list(nodes) != expected_nodes:
        raise SystemExit(f"节点应恰好是 {expected_nodes}，实际 {list(nodes)}")

    solid = [(e["u"], e["v"]) for e in parsed["edges"] if e["kind"] == "solid"]
    inter = [(e["u"], e["v"]) for e in parsed["edges"] if e["kind"] == "inter"]
    feedback = [(e["u"], e["v"]) for e in parsed["edges"] if e["kind"] == "feedback"]
    if solid != EXPECTED_SOLID:
        raise SystemExit(f"级内实线依赖与设计不符：\n  mmd {solid}\n  期望 {EXPECTED_SOLID}")
    if inter != EXPECTED_INTER:
        raise SystemExit(f"级间虚线依赖与设计不符：{inter} / 期望 {EXPECTED_INTER}")
    if feedback != EXPECTED_FEEDBACK:
        raise SystemExit(f"回流点线边与设计不符：{feedback} / 期望 {EXPECTED_FEEDBACK}")

    # 工期冻结表（L2–L4 沿用旧三图估算值，L5 同口径）
    if c["dur"] != EXPECTED_DUR:
        raise SystemExit(f"工期与冻结表不符：\n  mmd {c['dur']}\n  期望 {EXPECTED_DUR}")

    # 逐节点比对 CPM 标注 + 自洽
    for nid, f in c["fields"].items():
        got = (f["ES"], f["EF"], f["LS"], f["LF"])
        want = (c["ES"][nid], c["EF"][nid], c["LS"][nid], c["LF"][nid])
        if got != want:
            raise SystemExit(f"{nid} 的 CPM 数值与重算不符：mmd 写 {got}，重算 {want}")
        if c["EF"][nid] != c["ES"][nid] + c["dur"][nid] or c["LS"][nid] != c["LF"][nid] - c["dur"][nid]:
            raise SystemExit(f"{nid} 的 CPM 自洽断言失败（EF=ES+工期 / LS=LF-工期）")
        if c["TF"][nid] < 0:
            raise SystemExit(f"{nid} 的总浮动为负：{c['TF'][nid]}")
        if "验证" in "".join(c["fields"][nid]["crit"]):
            raise SystemExit(f"{nid} 的判据里出现了「验证」节点 —— 验证只能是完成判据")

    # class critical / normal 与「总浮动 = 0」集合一致
    crit_computed = {n for n in nodes if c["TF"][n] == 0}
    if set(parsed["classes"].get("critical", [])) != crit_computed:
        raise SystemExit("class critical 与总浮动=0 的集合不符："
                         f"mmd {sorted(parsed['classes'].get('critical', []))} vs 重算 {sorted(crit_computed)}")
    if set(parsed["classes"].get("normal", [])) != set(nodes) - crit_computed:
        raise SystemExit("class normal 应恰好是非关键节点")

    # linkStyle：橙色实线 = 关键驱动边；橙虚线 = 3 条级间；灰点线 = 回流
    path_pairs = set(zip(c["path"], c["path"][1:]))
    crit_edges = {e["idx"] for e in parsed["edges"]
                  if e["kind"] == "solid" and (e["u"], e["v"]) in path_pairs}
    normal_edges = {e["idx"] for e in parsed["edges"] if e["kind"] == "solid"} - crit_edges
    inter_idx = {e["idx"] for e in parsed["edges"] if e["kind"] == "inter"}
    fb_idx = {e["idx"] for e in parsed["edges"] if e["kind"] == "feedback"}
    if set(parsed["links"]["critical"]) != crit_edges:
        raise SystemExit(f"linkStyle 橙色实线箭头与关键路径不符：mmd {sorted(parsed['links']['critical'])} vs 期望 {sorted(crit_edges)}")
    if set(parsed["links"]["normal"]) != normal_edges:
        raise SystemExit("linkStyle 灰色实线箭头应恰好是非关键依赖边")
    if set(parsed["links"]["inter"]) != inter_idx:
        raise SystemExit(f"linkStyle 橙色虚线箭头应恰好是级间依赖：mmd {sorted(parsed['links']['inter'])} vs {sorted(inter_idx)}")
    if set(parsed["links"]["feedback"]) != fb_idx:
        raise SystemExit(f"linkStyle 灰色点线箭头应恰好是回流边：mmd {sorted(parsed['links']['feedback'])} vs {sorted(fb_idx)}")

    # 注释声明：关键路径 / 总工期 / 浮动 / 口径
    comment_text = "\n".join(parsed["comments"])
    m = re.search(r"%%\s*关键路径：([^，\n]+)，总工期\s*(\d+)\s*分钟", comment_text)
    if not m:
        raise SystemExit(f"{show(MMD)} 注释里缺少「%% 关键路径：…，总工期 N 分钟」")
    declared_path = [x.strip() for x in re.split(r"→", m.group(1)) if x.strip()]
    if declared_path != c["path"]:
        raise SystemExit(f"{show(MMD)} 注释声明的关键路径 {declared_path} 与重算 {c['path']} 不符")
    if int(m.group(2)) != c["total"]:
        raise SystemExit(f"{show(MMD)} 注释声明的总工期 {m.group(2)} ≠ 重算 {c['total']}")
    floats = [n for n in nodes if c["TF"][n] > 0]
    if floats != ["P11"] or c["TF"]["P11"] != 5:
        raise SystemExit(f"浮动应恰好只有 P11 = 5 分钟，实际 {[(n, c['TF'][n]) for n in floats]}")
    for n in floats:
        if f"{n}（" not in comment_text or f"总浮动 {c['TF'][n]} 分钟" not in comment_text:
            raise SystemExit(f"注释没有写清 {n} 的 {c['TF'][n]} 分钟总浮动")
    if "总浮动 0" not in comment_text:
        raise SystemExit("注释没有声明其余节点「总浮动 0」")
    for need, why in [
        ("估算值", "工期口径必须写「估算值」"),
        ("不是验收时限", "工期口径必须写「不是验收时限」"),
        ("计入 CPM", "级间虚线必须写清「计入 CPM」"),
        ("不计 CPM", "回流点线必须写清「不计 CPM」"),
        ("L1 交付", "起点必须写「L1 交付」"),
        ("flow.mmd", "必须写清 L1 旧图见 flow.mmd"),
        ("render_flow_l2_l5.py", "注释里必须写清渲染命令"),
    ]:
        if need not in comment_text:
            raise SystemExit(f"{show(MMD)} 注释缺少「{need}」——{why}")

    # 结构：根 / 汇聚 / 回流方向 / 级间是 FS 串行
    roots = [n for n in nodes if not c["pred"][n]]
    if roots != EXPECTED_ROOTS:
        raise SystemExit(f"根节点应为 {EXPECTED_ROOTS}（都只依赖图外的 L1 交付），实际 {roots}")
    for nid, want in EXPECTED_CONVERGE.items():
        if set(c["pred"][nid]) != want:
            raise SystemExit(f"{nid} 的紧前应为 {sorted(want)}，实际 {sorted(c['pred'][nid])}")
    for u, v in EXPECTED_FEEDBACK:
        if c["ES"][u] + c["dur"][u] <= c["ES"][v]:
            raise SystemExit(f"回流边 {u}→{v} 必须是从后往前指（重试路径），实际看起来是正向依赖")
    for u, v in EXPECTED_INTER:
        if c["ES"][v] != c["EF"][u]:
            raise SystemExit(f"级间依赖 {u}→{v} 必须是紧贴的 FS（{v} 的 ES={c['ES'][v]} 应等于 {u} 的 EF={c['EF'][u]}）")


def check_summary(c: dict, parsed: dict) -> None:
    print(f"✅ CPM 核对通过：18 个节点 / 总工期 {c['total']} 分钟（估）；"
          f"关键路径 {' → '.join(c['path'])}")
    print(f"   级内实线 {sum(1 for e in parsed['edges'] if e['kind'] == 'solid')} 条、"
          f"级间虚线 {sum(1 for e in parsed['edges'] if e['kind'] == 'inter')} 条（计入 CPM）、"
          f"回流点线 {sum(1 for e in parsed['edges'] if e['kind'] == 'feedback')} 条（不计 CPM）")
    print(f"{'编号':<4}{'工期':>5}{'ES':>5}{'EF':>5}{'LS':>5}{'LF':>5}{'总浮动':>7}  关键")
    for nid in c["fields"]:
        print(f"{nid:<4}{c['dur'][nid]:>6}{c['ES'][nid]:>6}{c['EF'][nid]:>6}"
              f"{c['LS'][nid]:>6}{c['LF'][nid]:>6}{c['TF'][nid]:>8}  {'★' if c['TF'][nid] == 0 else ''}")


# ------------------------------------------------------------------ 2. mmd 语法自检（mermaid）

def check_mmd_is_mermaid(parsed: dict, work: Path) -> None:
    """把 mmd 原样交给 mermaid 渲染一遍：它必须仍是合法 mermaid 图（18 个节点、0 语法错误）。"""
    if not MERMAID_LOCAL.exists():
        raise SystemExit(f"缺仓库内 mermaid 副本：{show(MERMAID_LOCAL)}（本图语法自检需要它）")
    js = MERMAID_LOCAL.read_text(encoding="utf-8")
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>mmd</title>
<style>html,body{{margin:0;padding:0;background:#fff}}</style></head><body>
<pre class="mermaid">{parsed['text']}</pre>
<script>{js}</script>
<script>
  mermaid.initialize({json.dumps(rf.MERMAID_CFG)});
  mermaid.run({{ querySelector: '.mermaid' }}).then(() => {{
    const svg = document.querySelector('svg');
    const n = svg ? svg.querySelectorAll('g.node').length : -1;
    const bad = svg && svg.innerHTML.includes('Syntax error') ? 1 : 0;
    document.title = 'MMD ' + n + ' ' + bad;
  }}).catch((e) => {{ document.title = 'ERR ' + (e && e.message ? e.message : e); }});
</script></body></html>"""
    html_path = work / "mmd-syntax.html"
    html_path.write_text(html, encoding="utf-8")
    proc = rf.chrome(["--window-size=1200,1200", "--virtual-time-budget=30000",
                      f"--user-data-dir={work / 'chrome-mmd'}", "--dump-dom", html_path.as_uri()])
    dom = proc.stdout
    m = re.search(r"<title>MMD (-?\d+) (\d+)</title>", dom)
    if not m:
        err = re.search(r"<title>ERR ([^<]*)</title>", dom)
        raise SystemExit("mmd 交给 mermaid 渲染失败（不再是合法 mermaid）："
                         + (err.group(1) if err else (proc.stderr or dom)[-2000:]))
    count, bad = int(m.group(1)), int(m.group(2))
    if bad:
        raise SystemExit("mmd 交给 mermaid 渲染出现语法错误标记")
    if count != len(parsed["nodes"]):
        raise SystemExit(f"mmd 交给 mermaid 渲染出 {count} 个节点，期望 {len(parsed['nodes'])} 个")
    print(f"✅ mmd 语法自检：仍是合法 mermaid 图（{count} 个节点、0 语法错误）")


# ------------------------------------------------------------------ 3. 文字宽度估计 + 布局

NARROW = set("·'’")
FULLWIDTH = set("：（）「」、，。！？；→◆｜—–“”‘’…／")


def text_w(s: str, size: float, bold: bool = False) -> float:
    """估计一行文字的宽度（px）：CJK/全角标点按 1em，ASCII 按 0.60em（偏保守，宁可留白）。"""
    w = 0.0
    for ch in s:
        o = ord(ch)
        if ch in NARROW:
            w += 0.50 * size
        elif o >= 0x2E80 or ch in FULLWIDTH:
            w += 1.00 * size
        elif ch == " ":
            w += 0.30 * size
        else:
            w += 0.60 * size
    return w * (1.03 if bold else 1.0)


def plan_layout(parsed: dict, c: dict) -> dict:
    """算节点尺寸、四条泳道的节点坐标、画布大小。"""
    fields = c["fields"]
    node_w: dict[str, int] = {}
    max_lines = 0
    for nid, f in fields.items():
        max_lines = max(max_lines, 1 + len(f["meta"]) + len(f["crit"]))
        w = text_w(f["title"], FONT_TITLE, bold=True)
        for ln in f["meta"]:
            w = max(w, text_w(ln, FONT_META))
        for ln in f["crit"]:
            w = max(w, text_w(ln, FONT_META))
        w += 2 * NODE_PAD_X + 8
        if is_gate(nid):
            w += 2 * GATE_R
        node_w[nid] = int(round(w))
    node_h = LINE_TITLE + (max_lines - 1) * LINE + 2 * NODE_PAD_Y + 4

    band_h = node_h + BAND_PAD_TOP + BAND_PAD_BOTTOM
    # 先按「同一泳道内首尾相接」排 x，再按级间对齐做整体平移
    lane_of = {n: lane for lane, lst in EXPECTED_LANES for n in lst}
    # 每条泳道的相邻节点：按声明顺序（读向由 LANE_DIRS 决定）
    pos: dict[str, tuple[float, float]] = {}
    lane_top: dict[str, float] = {}
    for i, (lane, lst) in enumerate(EXPECTED_LANES):
        lane_top[lane] = i * (band_h + LANE_GAP_Y)
    # 第 1 条泳道从 x=0 开始往右排
    x = 0.0
    for n in EXPECTED_LANES[0][1]:
        pos[n] = (x, 0.0)
        x += node_w[n] + NODE_GAP_X
    # 其余泳道：首节点与上一条泳道末节点「同中心对齐」，再按自己的读向排
    for (prev_lane, prev_nodes), (lane, lst) in zip(EXPECTED_LANES, EXPECTED_LANES[1:]):
        anchor = prev_nodes[-1]
        ax = pos[anchor][0] + node_w[anchor] / 2.0
        pos[lst[0]] = (ax - node_w[lst[0]] / 2.0, lane_top[lane])
        for prev, cur in zip(lst, lst[1:]):
            px, _ = pos[prev]
            if LANE_DIRS[lane] > 0:
                pos[cur] = (px + node_w[prev] + NODE_GAP_X, lane_top[lane])
            else:
                pos[cur] = (px - node_w[cur] - NODE_GAP_X, lane_top[lane])

    # 断言级间依赖的箭头是竖线（同一 x 中心）
    for e in parsed["edges"]:
        if e["kind"] != "inter":
            continue
        u, v = e["u"], e["v"]
        cu = pos[u][0] + node_w[u] / 2.0
        cv = pos[v][0] + node_w[v] / 2.0
        if abs(cu - cv) > 1.0:
            raise SystemExit(f"级间依赖 {u}→{v} 没有对齐成竖箭头（中心 {cu:.1f} vs {cv:.1f}），检查泳道读向/锚点")

    col_of = {n: i for _, lst in EXPECTED_LANES for i, n in enumerate(lst)}
    min_x = min(x for x, _ in pos.values())
    max_x = max(pos[n][0] + node_w[n] for n in pos)
    svg_w = max_x - min_x + 2 * 16
    svg_h = len(EXPECTED_LANES) * band_h + (len(EXPECTED_LANES) - 1) * LANE_GAP_Y + 12
    shift = 16 - min_x
    pos = {n: (x + shift, y + 6) for n, (x, y) in pos.items()}
    lane_top = {lane: y + 6 for lane, y in lane_top.items()}

    return dict(node_w=node_w, node_h=node_h, band_h=band_h, pos=pos, lane_top=lane_top,
                col_of=col_of, svg_w=int(round(svg_w)), svg_h=int(round(svg_h)), width=svg_w)


def is_gate(nid: str) -> bool:
    return nid.startswith("G")


# ------------------------------------------------------------------ 4. 画 SVG

C_CRIT = "#e65100"
C_CRIT_FILL = "#fff1e0"
C_NORMAL = "#b6bcc4"
C_NORMAL_FILL = "#f6f7f9"
C_LANE_FILL = "#fafbfc"
C_LANE_STROKE = "#dfe3e8"
C_INK = "#333333"
C_LANE_INK = "#4a5560"
C_FEEDBACK = "#7a8088"


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def node_svg(nid: str, f: dict, x: float, y: float, w: int, h: int, crit: bool) -> str:
    fill = C_CRIT_FILL if crit else C_NORMAL_FILL
    stroke = C_CRIT if crit else C_NORMAL
    sw = 4 if crit else 2
    if is_gate(nid):
        r = GATE_R
        pts = (f"{x + r},{y} {x + w - r},{y} {x + w},{y + h / 2:.1f} "
               f"{x + w - r},{y + h} {x + r},{y + h} {x},{y + h / 2:.1f}")
        shape = (f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
                 f'stroke-linejoin="round"/>')
        fx, fw = x + r + 2, w - 2 * r - 4
    else:
        shape = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" ry="7" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        fx, fw = x, w
    title = esc(f["title"])
    if is_gate(nid):
        title = "◆ " + title
    lines = "".join(
        f'<div class="ln meta">{esc(ln)}</div>' for ln in f["meta"]
    ) + "".join(
        f'<div class="ln crit">{esc(ln)}</div>' for ln in f["crit"]
    )
    return (f'<g class="node{" crit" if crit else ""}" id="node-{nid}">{shape}'
            f'<foreignObject x="{fx + 4}" y="{y + NODE_PAD_Y}" width="{fw - 8}" height="{h - 2 * NODE_PAD_Y}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="nb">'
            f'<div class="ln title">{title}</div>{lines}</div></foreignObject></g>')


def edge_paths(parsed: dict, c: dict, lay: dict) -> list[str]:
    """画依赖边：级内实线（直连 / 绕行）、级间虚线竖箭头、回流点线绕行。返回 SVG 片段列表。"""
    pos, nw, nh = lay["pos"], lay["node_w"], lay["node_h"]
    lane_y = {lane: y for lane, y in lay["lane_top"].items()}
    band_h = lay["band_h"]
    out: list[str] = []
    skip_channel: dict[str, int] = {}       # 泳道 -> 已用绕行通道数
    skip_by_target: dict[str, int] = {}     # 目标 -> 已有几条绕行边（落点错开）
    skip_total: dict[str, int] = {}
    for e in parsed["edges"]:
        if e["kind"] == "solid":
            u, v = e["u"], e["v"]
            same_lane = abs(pos[u][1] - pos[v][1]) < 1.0
            if same_lane and abs(lay["col_of"][v] - lay["col_of"][u]) > 1:
                skip_total[v] = skip_total.get(v, 0) + 1

    def cy(nid):  # 节点竖直中心
        return pos[nid][1] + nh / 2.0

    # 先画灰色（普通）边，再画橙色（关键）边，最后级间与回流，保证橙色在上
    order = {"normal": 0, "critical": 1, "inter": 2, "feedback": 3}
    path_pairs = set(zip(c["path"], c["path"][1:]))
    edges = []
    for e in parsed["edges"]:
        if e["kind"] == "solid":
            klass = "critical" if (e["u"], e["v"]) in path_pairs else "normal"
        else:
            klass = e["kind"]
        edges.append((order[klass], e, klass))
    edges.sort(key=lambda t: t[0])

    for _, e, klass in edges:
        u, v, kind = e["u"], e["v"], e["kind"]
        ux, uy = pos[u]
        vx, vy = pos[v]
        uw, vw = nw[u], nw[v]
        if klass == "critical":
            stroke, sw, marker, dash = C_CRIT, 4, "ah-crit", ""
        elif klass == "normal":
            stroke, sw, marker, dash = "#9aa0a6", 2, "ah-normal", ""
        elif klass == "inter":
            stroke, sw, marker, dash = C_CRIT, 4, "ah-crit", ' stroke-dasharray="10 6"'
        else:
            stroke, sw, marker, dash = C_FEEDBACK, 3, "ah-fb", ' stroke-dasharray="2 7"'
        style = f'stroke="{stroke}" stroke-width="{sw}" fill="none"{dash} marker-end="url(#{marker})"'

        if kind == "inter":
            # 级间：上一级末端节点底部 → 下一级首节点顶部（同一 x 中心）
            x = ux + uw / 2.0
            y0 = uy + nh
            y1 = vy
            out.append(f'<path d="M {x:.1f} {y0:.1f} L {x:.1f} {y1:.1f}" {style}/>')
            out.append(f'<text class="elab" x="{x - 10:.1f}" y="{(y0 + y1) / 2 + 5:.1f}" '
                       f'text-anchor="end" fill="{C_CRIT}">级间 FS</text>')
            continue

        if kind == "feedback":
            # 回流：从后一节点顶部绕到前一节点顶部（从后往前指，重试路径）
            ch = uy - 12
            x0 = ux + uw / 2.0
            x1 = vx + vw / 2.0
            out.append(f'<path d="M {x0:.1f} {uy:.1f} L {x0:.1f} {ch:.1f} '
                       f'L {x1:.1f} {ch:.1f} L {x1:.1f} {vy:.1f}" {style}/>')
            out.append(f'<text class="elab fb" x="{(x0 + x1) / 2:.1f}" y="{ch - 5:.1f}" '
                       f'text-anchor="middle" fill="{C_FEEDBACK}">回流（重试，不计 CPM）</text>')
            continue

        if abs(cy(u) - cy(v)) < 1.0:
            # 同一条泳道：相邻列直连，跨列（并行/汇聚边）从节点下方绕行
            if abs(lay["col_of"][v] - lay["col_of"][u]) == 1:
                if vx > ux:
                    x0, x1 = ux + uw + 2, vx - 2
                else:
                    x0, x1 = ux - 2, vx + vw + 2
                out.append(f'<path d="M {x0:.1f} {cy(u):.1f} L {x1:.1f} {cy(u):.1f}" {style}/>')
            else:
                lane = _lane_of(u)
                idx = skip_channel.get(lane, 0)
                skip_channel[lane] = idx + 1
                ch = uy + nh + 16 + idx * 17
                x0 = ux + uw / 2.0
                k = skip_by_target.get(v, 0)
                skip_by_target[v] = k + 1
                n = skip_total.get(v, 1)
                x1 = vx + vw / 2.0 + (k - (n - 1) / 2.0) * 26
                out.append(f'<path d="M {x0:.1f} {uy + nh:.1f} L {x0:.1f} {ch:.1f} '
                           f'L {x1:.1f} {ch:.1f} L {x1:.1f} {vy + nh:.1f}" {style}/>')
        else:
            raise SystemExit(f"边 {u}→{v} 跨了泳道但不是级间依赖，布局不支持")
    return out


def _lane_of(nid: str) -> str:
    for lane, lst in EXPECTED_LANES:
        if nid in lst:
            return lane
    raise SystemExit(f"{nid} 不在任何泳道里")


def build_svg(parsed: dict, c: dict, lay: dict) -> str:
    w, h = lay["svg_w"], lay["svg_h"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             f'viewBox="0 0 {w} {h}" font-family="{rf.FONT_STACK}">']
    parts.append(
        "<defs>"
        '<marker id="ah-crit" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="14" markerHeight="14" '
        f'markerUnits="userSpaceOnUse" orient="auto"><path d="M1,1 L13,7 L1,13 z" fill="{C_CRIT}"/></marker>'
        '<marker id="ah-normal" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" '
        f'markerUnits="userSpaceOnUse" orient="auto"><path d="M1,1 L11,6 L1,11 z" fill="#9aa0a6"/></marker>'
        '<marker id="ah-fb" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" '
        f'markerUnits="userSpaceOnUse" orient="auto"><path d="M1,1 L11,6 L1,11 z" fill="{C_FEEDBACK}"/></marker>'
        '<style>'
        f'.nb{{font-size:{FONT_META}px;line-height:{LINE}px;text-align:center;color:{C_INK};'
        'overflow:hidden;width:100%;height:100%;display:flex;flex-direction:column;'
        'justify-content:center;align-items:center}'
        f'.nb .ln{{white-space:nowrap}}'
        f'.nb .title{{font-size:{FONT_TITLE}px;line-height:{LINE_TITLE}px;font-weight:600}}'
        f'.nb .meta{{color:#4a5560}}'
        f'.nb .crit{{color:#2f3a45}}'
        f'.elab{{font-size:15px;font-weight:600}}'
        f'.elab.fb{{font-size:14px;font-weight:500}}'
        f'.lane-lab{{font-size:17px;font-weight:600;fill:{C_LANE_INK}}}'
        '</style></defs>'
    )
    # 泳道底板 + 标题（标题放在「级间箭头不进来的那一侧」，避免被竖箭头穿过）
    inter_targets = {e["v"] for e in parsed["edges"] if e["kind"] == "inter"}
    for lane, lst in EXPECTED_LANES:
        y0 = lay["lane_top"][lane]
        band_y = y0 - BAND_PAD_TOP
        parts.append(f'<rect class="band" x="8" y="{band_y:.1f}" width="{w - 16}" '
                     f'height="{lay["band_h"]}" rx="10" ry="10" fill="{C_LANE_FILL}" '
                     f'stroke="{C_LANE_STROKE}" stroke-width="1.2"/>')
        arrow_left = any(n in inter_targets and lay["pos"][n][0] + lay["node_w"][n] / 2.0 < w / 2
                         for n in lst)
        if arrow_left:
            parts.append(f'<text class="lane-lab" x="{w - 22}" y="{band_y + 22:.1f}" '
                         f'text-anchor="end">{esc(LANE_LABELS[lane])}</text>')
        else:
            parts.append(f'<text class="lane-lab" x="22" y="{band_y + 22:.1f}">{esc(LANE_LABELS[lane])}</text>')
    # 依赖边
    parts.extend(edge_paths(parsed, c, lay))
    # 节点（关键路径最后画，压在最上层）
    for nid in c["fields"]:
        x, y = lay["pos"][nid]
        parts.append(node_svg(nid, c["fields"][nid], x, y, lay["node_w"][nid], lay["node_h"],
                              c["TF"][nid] == 0))
    parts.append("</svg>")
    return "\n".join(parts)


# ------------------------------------------------------------------ 5. HTML + 截图

LEGEND = [
    "<b>橙色粗框 / 橙色箭头</b> = 关键路径（总浮动 0） ｜ 实线箭头 = 级内 FS ｜ "
    "虚线箭头 = 级间 FS（L2→L3→L4→L5 串行，计入 CPM） ｜ 点线箭头 = 回流重试（不计 CPM）",
    "节点内：编号 + 活动名 / 工期（估）/ ES EF LS LF / 完成判据（看到它才算这一页做完）；"
    "◆ = 该级级考核（末页「拆一刀」）；菱形节点 = 里程碑式级考核",
    "<b>工期 = 估算值（分钟）</b>，只用于表达判据依赖与关键路径，<b>不是验收时限</b>；"
    "验证 = 完成判据，不单独成节点 ｜ 起点 = L1 交付（L1 网络见旧图 flow.mmd，本图不重画）",
    "级内并行与汇聚：P10 / P11 并行（P12 等两者）｜ P22 是汇聚节点（P18/P19/P20 三条汇聚边，"
    "前四项全完成才回归）｜ P17⇢P15 回流是纠错重试路径 ｜ 本图是<b>判据依赖网</b>，不是施工工期",
]

SUB = ("四条泳道 = L2 换 / L3 审 / L4 守 / L5 装 · 18 个节点 · 总工期 330 分钟（估算）· "
       "关键路径 P10 → … → G5（总浮动 0）· 起点 = L1 交付（图外）")


def build_html(svg: str, c: dict) -> str:
    legend = "".join(f"<div>{ln}</div>" for ln in LEGEND)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>aon-l2-l5</title>
<style>
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
body {{ display: inline-block; }}
.fig {{ padding: 18px 22px; font-family: {rf.FONT_STACK}; color: #1a1a1a; }}
.fig-title {{ font-size: {FIG_TITLE_PX}px; font-weight: 600; line-height: 1.5; margin: 0 0 2px; }}
.fig-sub {{ font-size: {FIG_SMALL_PX}px; line-height: 1.6; color: #555; margin: 0 0 12px; }}
#holder svg {{ display: block; }}
.fig-legend {{ font-size: {FIG_SMALL_PX}px; line-height: 1.75; color: #444; margin: 12px 0 0; }}
.fig-legend b {{ color: #e65100; font-weight: 600; }}
</style></head><body>
<div class="fig">
  <div class="fig-title">图 2 · L2–L5 合并单代号网络图（AON / 紧前关系法 PDM）</div>
  <div class="fig-sub">{SUB}</div>
  <div id="holder">{svg}</div>
  <div class="fig-legend">{legend}</div>
</div>
<script>
  document.fonts.ready.then(() => {{
    const r = document.querySelector('.fig').getBoundingClientRect();
    const nodes = document.querySelectorAll('#holder g.node').length;
    let ovf = 0;
    document.querySelectorAll('#holder .nb').forEach((el) => {{
      if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) ovf += 1;
    }});
    document.title = 'DIM ' + Math.ceil(r.width) + ' ' + Math.ceil(r.height) + ' N ' + nodes + ' OVF ' + ovf;
  }});
</script>
</body></html>
"""


def measure(html: Path, work: Path) -> tuple[int, int, int, int, str]:
    proc = rf.chrome([
        "--window-size=4000,2600",
        "--virtual-time-budget=30000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", html.as_uri(),
    ])
    m = re.search(r"<title>DIM (\d+) (\d+) N (\d+) OVF (\d+)</title>", proc.stdout)
    if not m:
        raise SystemExit("渲染失败（页面没测出尺寸）：" + (proc.stderr or proc.stdout)[-2000:])
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), proc.stdout


# ------------------------------------------------------------------ 6. 图形自检

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
    proc = subprocess.run(["identify", "-format", "%w %h", str(png)],
                          capture_output=True, text=True, timeout=60, check=True)
    w, h = (int(x) for x in proc.stdout.split())
    if w != width:
        raise SystemExit(f"{show(png)} 宽度 {w}px，不等于约定 {width}px")
    if not 800 <= h <= 2000:
        raise SystemExit(f"{show(png)} 高度 {h}px 不在合理区间（800–2000）")
    counts = color_counts(png)
    non_white = sum(c for px, c in counts.items() if px != (255, 255, 255))
    if non_white < 30000:
        raise SystemExit(f"{show(png)} 几乎空白（非白像素只有 {non_white}）")
    orange = sum(c for px, c in counts.items()
                 if (px[0] - CRIT_STROKE[0]) ** 2 + (px[1] - CRIT_STROKE[1]) ** 2
                 + (px[2] - CRIT_STROKE[2]) ** 2 <= 40 * 40)
    if orange < 3000:
        raise SystemExit(f"{show(png)} 没有足够的关键路径橙色描边（{orange} 像素）")
    if counts.get(CRIT_FILL, 0) < 3000:
        raise SystemExit(f"{show(png)} 没有足够的关键节点浅橙底（{counts.get(CRIT_FILL, 0)} 像素）")
    if counts.get(NORMAL_FILL, 0) < 1000:
        raise SystemExit(f"{show(png)} 没有普通节点（P11）的灰色底（{counts.get(NORMAL_FILL, 0)} 像素）")
    print(f"   PNG 自检：宽度 {w}px（约定 {width}px）/ 高度 {h}px / 非白 {non_white} 像素 / "
          f"橙色描边 {orange} 像素 / 关键浅橙 {counts.get(CRIT_FILL, 0)} / 普通灰 {counts.get(NORMAL_FILL, 0)}")
    return w, h


def check_dom(dom_visible: str, parsed: dict, c: dict) -> None:
    """图形自检 A：DOM/SVG 里真的画出了每个节点 / 活动名 / 泳道 / 级间与回流标签。"""
    for nid in c["fields"]:
        if f'id="node-{nid}"' not in dom_visible:
            raise SystemExit(f"SVG/DOM 里没有节点 {nid}")
        name = c["fields"][nid]["name"]
        if name not in dom_visible:
            raise SystemExit(f"SVG/DOM 里没有节点 {nid} 的活动名「{name}」")
    for lane, _ in EXPECTED_LANES:
        if f"L{lane[1]}" not in dom_visible:   # L2 → "L2"
            raise SystemExit(f"SVG/DOM 里没有泳道标题 {lane}")
        if LANE_LABELS[lane][:6] not in dom_visible:
            raise SystemExit(f"SVG/DOM 里没有泳道标签「{LANE_LABELS[lane][:6]}」")
    for text, why in [("级间 FS", "级间依赖标签"), ("回流（重试，不计 CPM）", "回流标签"),
                      ("◆", "级考核菱形角标")]:
        if text not in dom_visible:
            raise SystemExit(f"SVG/DOM 里没有{why}「{text}」")
    print(f"   SVG 自检：{len(c['fields'])} 个节点 / 活动名齐全 / 4 条泳道 / 级间与回流标签都在")


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="把 L2–L5 合并 AON（tutorial/flow-l2-l5.mmd）渲染成 tutorial/images/aon-l2-l5.png")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                    help=f"输出 PNG 宽度（默认 {DEFAULT_WIDTH}px；最小 1100）")
    ap.add_argument("--out", type=Path, default=OUT, help="输出 PNG 路径")
    args = ap.parse_args()
    if args.width < 1100:
        raise SystemExit("--width 太小，合并图文字会看不清（≥1100）")

    parsed = parse_mmd(MMD)
    c = cpm(parsed["nodes"], parsed["edges"])
    check_structure(parsed, c)
    check_summary(c, parsed)
    lay = plan_layout(parsed, c)

    with tempfile.TemporaryDirectory(prefix="aon-l2-l5-") as tmp:
        work = Path(tmp)
        check_mmd_is_mermaid(parsed, work)

        svg = build_svg(parsed, c, lay)
        html = work / "aon-l2-l5.html"
        html.write_text(build_html(svg, c), encoding="utf-8")
        print(f"🖼 布局：画布 {lay['svg_w']}x{lay['svg_h']}（1:1）；渲染 {show(MMD)} → {show(args.out)}")
        w, h, node_count, ovf, dom = measure(html, work)
        if node_count != len(c["fields"]):
            raise SystemExit(f"DOM 里画了 {node_count} 个节点，期望 {len(c['fields'])} 个")
        if ovf:
            raise SystemExit(f"有 {ovf} 个节点的文字溢出节点框（需要缩字或加宽节点）")
        print(f"   自然尺寸 {w}x{h}（1:1）；DOM 节点 {node_count} 个；文字溢出 0")
        check_dom(dom, parsed, c)

        raw = work / "aon-l2-l5.raw.png"
        rf.screenshot(html, raw, (w, h), work)
        visible = re.sub(r"<script>.*?</script>", "", html.read_text(encoding="utf-8"), flags=re.S)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        ww, hh = rf.trim_and_resize(raw, args.out, args.width, work)

    leaked = [p for p in FORBIDDEN if p in parsed["text"] + visible]
    if leaked:
        args.out.unlink(missing_ok=True)
        raise SystemExit(f"图里出现了不该有的信息：{leaked}")
    ww, hh = check_png(args.out, args.width)
    print(f"🖼 完成 {show(args.out)}  {ww}x{hh}px（@2x 超采样后缩到 {args.width} 宽）")
    print(f"\n✅ 合并 AON：CPM 自检通过 / mmd 语法通过 / 渲染成功 / PNG 自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
