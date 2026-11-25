#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_aon_l2_l5.py —— L2–L5 合并 AON 的独立断言脚本（只读，不渲染）。

它故意**不 import** render_flow_l2_l5.py 里的任何解析 / CPM 实现：从 `manual/flow-l2-l5.mmd`
原文重新解析节点 / 泳道 / 工期 / 依赖（级内实线 + 级间虚线计入 CPM，回流点线不计），用另一套
算法（逐轮松弛到不动点，而不是 Kahn 拓扑序）重算 ES/EF/LS/LF/浮动，再逐节点和 mmd 里写的
数值比对；关键路径「节点集合」与注释、class critical、linkStyle 四方对账。最后查 PNG 尺寸 /
配色，并用 tesseract 对 PNG 做 OCR，确认 P10–P23 与 G2–G5 真的画在图上。

一条命令（在仓库根目录）：

    python3 manual/shots/check_aon_l2_l5.py          # 人看的对账表
    python3 manual/shots/check_aon_l2_l5.py -q       # 只留结论与失败
    python3 manual/shots/check_aon_l2_l5.py --no-ocr # 环境没有 tesseract 时跳过 OCR

退出码 0 = 通过；1 = 有断言失败（明细打在 stderr）。
依赖：python3 + ImageMagick(convert/identify)；OCR 可选，需 tesseract（eng 语言包即可）。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent      # manual/shots
REPO = HERE.parents[1]                      # 仓库根目录
MMD = REPO / "manual" / "flow-l2-l5.mmd"
PNG = REPO / "manual" / "images" / "aon-l2-l5.png"
WIDTH = 1600                                # 合并图约定宽度（任务口径：1100 或 1600）
CRIT_STROKE = (230, 81, 0)                  # #e65100
CRIT_FILL = (255, 241, 224)                 # #fff1e0
NORMAL_FILL = (246, 247, 249)               # #f6f7f9

# 期望结构（独立写在 checker 里，和渲染脚本各写一份，互为对照）
LANES = [
    ("L2", ["P10", "P11", "P12", "P13", "G2"]),
    ("L3", ["P14", "P15", "P16", "P17", "G3"]),
    ("L4", ["P18", "P19", "P20", "P21", "P22", "G4"]),
    ("L5", ["P23", "G5"]),
]
SOLID = [
    ("P10", "P12"), ("P11", "P12"), ("P12", "P13"), ("P13", "G2"),
    ("P14", "P15"), ("P15", "P16"), ("P16", "P17"), ("P17", "G3"),
    ("P18", "P19"), ("P19", "P20"), ("P20", "P21"), ("P21", "P22"),
    ("P18", "P22"), ("P19", "P22"), ("P20", "P22"), ("P22", "G4"),
    ("P23", "G5"),
]
INTER = [("G2", "P14"), ("G3", "P18"), ("G4", "P23")]
FEEDBACK = [("P17", "P15")]
DUR = {
    "P10": 25, "P11": 20, "P12": 25, "P13": 20, "G2": 10,
    "P14": 30, "P15": 25, "P16": 20, "P17": 25, "G3": 10,
    "P18": 15, "P19": 20, "P20": 20, "P21": 20, "P22": 20, "G4": 15,
    "P23": 20, "G5": 10,
}
LEVEL_DUR = {"L2": 80, "L3": 110, "L4": 110, "L5": 30}   # 级内关键链时长（= 旧三图 80/110/110 + L5 30）
ROOTS = ["P10", "P11"]
CONVERGE = {"P12": {"P10", "P11"}, "P22": {"P18", "P19", "P20", "P21"}}
NAMES = {
    "P10": "换真数据", "P11": "换真契约", "P12": "换真执行器", "P13": "换真部署",
    "P14": "审召回", "P15": "审生成", "P16": "审校验", "P17": "审纠错",
    "P18": "守账号", "P19": "守策略", "P20": "守取消", "P21": "守可观测", "P22": "守回归",
    "P23": "装成熟前端", "G2": "级考核", "G3": "级考核", "G4": "级考核", "G5": "级考核",
}


class CheckError(Exception):
    """一条断言失败：最后由 main 汇总。"""


# ------------------------------------------------------------------ 解析（独立实现）

def parse_mmd(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    comments = [ln for ln in text.splitlines() if ln.lstrip().startswith("%%")]
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%%"))
    if not re.search(r"^flowchart\s+LR\s*$", body, re.M):
        raise CheckError("首行声明不是 `flowchart LR`")

    lanes: list[tuple[str, list[str]]] = []
    labels: dict[str, str] = {}
    lane_of: dict[str, str] = {}
    cur = None
    for ln in body.splitlines():
        m = re.match(r'^\s*subgraph\s+(\w+)\["([^"]*)"\]\s*$', ln)
        if m:
            cur = m.group(1)
            lanes.append((cur, []))
            continue
        if re.match(r"^\s*end\s*$", ln):
            cur = None
            continue
        m = re.match(r'^\s*([A-Za-z]\w*)\["(.*)"\]\s*$', ln)
        if m:
            labels[m.group(1)] = m.group(2)
            if cur is None:
                raise CheckError(f"节点 {m.group(1)} 不在任何泳道子图里")
            lanes[-1][1].append(m.group(1))
            lane_of[m.group(1)] = cur

    solid, inter, feedback = [], [], []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*(-->|-\.->)\|([^|]*)\|\s*([A-Za-z]\w*)\s*$", body, re.M):
        u, arrow, lab, v = m.group(1), m.group(2), m.group(3).strip(), m.group(4)
        if u not in labels or v not in labels:
            raise CheckError(f"依赖边 {u}→{v} 引用了不存在的节点")
        if arrow == "-->":
            if lab != "FS":
                raise CheckError(f"实线 {u}→{v} 没标 FS")
            solid.append((u, v))
        elif "回流" in lab:
            feedback.append((u, v))
        elif "级间" in lab:
            inter.append((u, v))
        else:
            raise CheckError(f"虚线 {u}→{v} 标签「{lab}」既不是级间也不是回流")

    classes = {}
    for m in re.finditer(r"^\s*class[ \t]+([\w, \t]+?)[ \t]+(critical|normal)[ \t]*$", body, re.M):
        classes[m.group(2)] = [x.strip() for x in m.group(1).split(",") if x.strip()]
    links = {"critical": [], "normal": [], "inter": [], "feedback": []}
    for m in re.finditer(r"^\s*linkStyle\s+([\d,]+)\s+(.*)$", body, re.M):
        idx = [int(x) for x in m.group(1).split(",") if x.strip()]
        st = m.group(2)
        if "dasharray" in st and "e65100" in st:
            links["inter"].extend(idx)
        elif "dasharray" in st:
            links["feedback"].extend(idx)
        elif "e65100" in st:
            links["critical"].extend(idx)
        else:
            links["normal"].extend(idx)

    # 边的全局序号（linkStyle 用）：按源文件书写顺序数一遍（三类边混排，故不能分组重建）
    actual_order = []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*(-->|-\.->)\|([^|]*)\|\s*([A-Za-z]\w*)\s*$", body, re.M):
        actual_order.append((m.group(1), m.group(4)))
    if sorted(actual_order) != sorted(solid + inter + feedback) or len(actual_order) != len(solid) + len(inter) + len(feedback):
        raise CheckError("边的书写顺序解析结果与分类结果不一致（linkStyle 序号会错）")
    return dict(text=text, comments=comments, labels=labels, lanes=lanes, lane_of=lane_of,
                solid=solid, inter=inter, feedback=feedback, classes=classes,
                links=links, edge_idx={e: i for i, e in enumerate(actual_order)})


def label_fields(nid: str, label: str) -> dict:
    parts = [p.strip() for p in label.split("<br/>")]
    if not (5 <= len(parts) <= 7):
        raise CheckError(f"{nid} 的节点标签应有 5–7 行，实际 {len(parts)} 行")
    title = re.sub(r"</?b>", "", parts[0]).strip()
    if not title.startswith(nid + " "):
        raise CheckError(f"{nid} 的标题应以「{nid} 」开头，实际「{title}」")
    if not parts[1].startswith("工期") or "（估）" not in parts[1]:
        raise CheckError(f"{nid} 的工期行没有「工期 N（估）」：{parts[1]}")
    dur = re.search(r"工期\s*(\d+)", parts[1])
    cpm = re.match(r"^ES(\d+)\s+EF(\d+)\s+LS(\d+)\s+LF(\d+)$", parts[2])
    if not dur or not cpm:
        raise CheckError(f"{nid} 缺工期或 ES/EF/LS/LF 行")
    crit = parts[3:]
    if not crit or not crit[0].startswith("判据："):
        raise CheckError(f"{nid} 缺「判据：」行")
    if any("验证" in c for c in crit):
        raise CheckError(f"{nid} 的判据里出现「验证」——验证只能是完成判据，不能单独成节点")
    return dict(title=title, dur=int(dur.group(1)),
                ES=int(cpm.group(1)), EF=int(cpm.group(2)),
                LS=int(cpm.group(3)), LF=int(cpm.group(4)), crit=crit)


# ------------------------------------------------------------------ CPM（另一套算法：松弛到不动点）

def cpm_relaxation(dur: dict[str, int], edges: list[tuple[str, str]], find_path: bool = True):
    ids = list(dur)
    pred = {n: [] for n in ids}
    succ = {n: [] for n in ids}
    for u, v in edges:
        if u not in dur or v not in dur:
            raise CheckError(f"依赖边 {u}→{v} 引用了不存在的节点")
        pred[v].append(u)
        succ[u].append(v)

    # 正推：反复松弛 ES = max(EF of preds)，EF = ES + dur，直到不动点（DAG 最多 |V| 轮）
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
        raise CheckError("正推松弛不收敛（FS 依赖可能有环）")
    total = max(EF.values())

    # 逆推：反复松弛 LF = min(LS of succs)（终点取总工期），LS = LF - dur
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
        raise CheckError("逆推松弛不收敛（FS 依赖可能有环）")

    TF = {n: LS[n] - ES[n] for n in ids}
    if not find_path:
        return dict(dur=dur, ES=ES, EF=EF, LS=LS, LF=LF, TF=TF, total=total,
                    path=[], pred=pred, succ=succ)
    roots = [n for n in ids if not pred[n]]
    crit_roots = [n for n in roots if TF[n] == 0]
    if len(crit_roots) != 1:
        raise CheckError(f"关键路径起点应唯一，实际 {crit_roots or roots}")
    path = [crit_roots[0]]
    while True:
        nxt = [s for s in succ[path[-1]] if TF[s] == 0 and EF[path[-1]] == ES[s]]
        if len(nxt) > 1:
            raise CheckError(f"关键路径在 {path[-1]} 分叉：{nxt}")
        if not nxt:
            break
        path.append(nxt[0])
    if EF[path[-1]] != total:
        raise CheckError("关键路径没有走到总工期终点")
    return dict(dur=dur, ES=ES, EF=EF, LS=LS, LF=LF, TF=TF, total=total,
                path=path, pred=pred, succ=succ)


def _has_cycle(dur: dict[str, int], edges: list[tuple[str, str]]) -> bool:
    indeg = {n: 0 for n in dur}
    succ = {n: [] for n in dur}
    for u, v in edges:
        indeg[v] += 1
        succ[u].append(v)
    queue = [n for n in dur if indeg[n] == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    return seen != len(dur)


# ------------------------------------------------------------------ 断言

def verify_cpm(parsed: dict, quiet: bool) -> dict:
    labels = parsed["labels"]
    expect_nodes = [n for _, lst in LANES for n in lst]
    if list(labels) != expect_nodes:
        raise CheckError(f"节点集合/顺序应为 {expect_nodes}，实际 {list(labels)}")
    if [lane for lane, _ in parsed["lanes"]] != [lane for lane, _ in LANES]:
        raise CheckError(f"泳道应恰好是 {[x[0] for x in LANES]}，实际 {[x[0] for x in parsed['lanes']]}")
    for (lane, want), (_, got) in zip(LANES, parsed["lanes"]):
        if got != want:
            raise CheckError(f"泳道 {lane} 的节点应恰好是 {want}，实际 {got}")

    fields = {nid: label_fields(nid, lb) for nid, lb in labels.items()}
    dur = {nid: f["dur"] for nid, f in fields.items()}
    if dur != DUR:
        raise CheckError(f"工期与冻结表不符：mmd {dur}，期望 {DUR}")
    for nid, name in NAMES.items():
        if name not in fields[nid]["title"]:
            raise CheckError(f"{nid} 的标题应含活动名「{name}」，实际「{fields[nid]['title']}」")
    # P23 = L5 装成熟版原版前端：判据里必须同时有 8088 成熟版与 8080 教学版脚手架口径
    p23_crit = "".join(fields["P23"]["crit"])
    for tok, why in [("docker compose up -d", "起栈命令"), ("8088", "成熟版 nginx 容器端口"),
                     ("41,099.5", "结果 41,099.5"), ("41099.5", "数值 41099.5"),
                     ("教学版", "教学版脚手架对照"), ("8080", "教学版 8080 端口")]:
        if tok not in p23_crit:
            raise CheckError(f"P23 的判据里缺「{tok}」——{why}")

    if parsed["solid"] != SOLID:
        raise CheckError(f"级内实线依赖应为 {SOLID}，实际 {parsed['solid']}")
    if parsed["inter"] != INTER:
        raise CheckError(f"级间虚线依赖应为 {INTER}，实际 {parsed['inter']}")
    if parsed["feedback"] != FEEDBACK:
        raise CheckError(f"回流点线边应为 {FEEDBACK}，实际 {parsed['feedback']}")

    # 关键：级间虚线计入 CPM；回流点线不计
    merged = cpm_relaxation(dur, parsed["solid"] + parsed["inter"])
    alone = cpm_relaxation(dur, parsed["solid"], find_path=False)   # 只算级内 = 四条互不相连的网
    if merged["total"] != 330:
        raise CheckError(f"合并图总工期应为 330 分钟，实际 {merged['total']}")
    if alone["total"] != max(LEVEL_DUR.values()):
        raise CheckError(f"不计级间依赖时应是四级里的最大一段（110），实际 {alone['total']}")
    # 回流点线是重试路径：它必须从后往前指、且把级内算成环（前面已断言顶点级不回退）
    if _has_cycle(dur, parsed["solid"] + parsed["inter"] + parsed["feedback"]):
        pass    # 期望：把回流当依赖会成环 —— 恰好证明它不能计入 CPM
    else:
        raise CheckError("回流点线没有被识别为重试回边（当成依赖也不成环）")

    # 级内关键链时长 = 旧的 80/110/110 + 新的 30
    for lane, lst in LANES:
        seg = [n for n in merged["path"] if n in lst]
        span = sum(dur[n] for n in seg)
        if span != LEVEL_DUR[lane]:
            raise CheckError(f"{lane} 级内关键链应为 {LEVEL_DUR[lane]} 分钟，实际 {span}")

    # 逐节点逐字段与 mmd 标注比对（全等）
    fields_total = fields_equal = 0
    for nid, f in fields.items():
        want = dict(ES=merged["ES"][nid], EF=merged["EF"][nid],
                    LS=merged["LS"][nid], LF=merged["LF"][nid])
        for k, v in want.items():
            fields_total += 1
            if f[k] == v:
                fields_equal += 1
            else:
                raise CheckError(f"{nid}.{k}：mmd 写 {f[k]}，独立重算 {v}")

    # CPM 自洽 + 浮动非负
    for nid in labels:
        if merged["EF"][nid] != merged["ES"][nid] + dur[nid]:
            raise CheckError(f"{nid} EF≠ES+工期")
        if merged["LS"][nid] != merged["LF"][nid] - dur[nid]:
            raise CheckError(f"{nid} LS≠LF−工期")
        if merged["TF"][nid] != merged["LF"][nid] - merged["EF"][nid]:
            raise CheckError(f"{nid} 浮动 LS−ES ≠ LF−EF")
        if merged["TF"][nid] < 0:
            raise CheckError(f"{nid} 总浮动为负：{merged['TF'][nid]}")
    floats = {n: merged["TF"][n] for n in labels if merged["TF"][n] > 0}
    if floats != {"P11": 5}:
        raise CheckError(f"浮动应恰好只有 P11 = 5 分钟，实际 {floats}")

    # 关键集合三方对账：浮动=0 / class critical / 注释关键路径
    crit = {n for n in labels if merged["TF"][n] == 0}
    if set(parsed["classes"].get("critical", [])) != crit:
        raise CheckError(f"class critical {sorted(parsed['classes'].get('critical', []))} ≠ 浮动0集合 {sorted(crit)}")
    if set(parsed["classes"].get("normal", [])) != set(labels) - crit:
        raise CheckError("class normal ≠ 非关键集合")
    comment_text = "\n".join(parsed["comments"])
    m = re.search(r"%%\s*关键路径：([^，\n]+)，总工期\s*(\d+)\s*分钟", comment_text)
    if not m:
        raise CheckError("注释里缺「%% 关键路径：…，总工期 N 分钟」")
    declared = [x.strip() for x in re.split(r"→", m.group(1)) if x.strip()]
    if declared != merged["path"]:
        raise CheckError(f"注释关键路径 {declared} ≠ 重算 {merged['path']}")
    if int(m.group(2)) != merged["total"]:
        raise CheckError(f"注释总工期 {m.group(2)} ≠ 重算 {merged['total']}")
    if set(declared) != crit:
        raise CheckError("注释关键路径节点集合 ≠ 浮动=0 集合")
    for nid, tf in floats.items():
        if not re.search(rf"{nid}（[^）]*）[^\n]*总浮动 {tf} 分钟", comment_text):
            raise CheckError(f"注释没写 {nid} 的总浮动 {tf} 分钟")
    if "总浮动 0" not in comment_text:
        raise CheckError("注释没声明其余节点「总浮动 0」")

    # linkStyle 三方对账（橙色实线 = 关键级内边；橙虚线 = 级间；灰点线 = 回流）
    path_pairs = set(zip(merged["path"], merged["path"][1:]))
    crit_edges = {parsed["edge_idx"][e] for e in SOLID if e in path_pairs}
    normal_edges = {parsed["edge_idx"][e] for e in SOLID} - crit_edges
    inter_idx = {parsed["edge_idx"][e] for e in INTER}
    fb_idx = {parsed["edge_idx"][e] for e in FEEDBACK}
    if set(parsed["links"]["critical"]) != crit_edges:
        raise CheckError(f"linkStyle 橙色实线 {sorted(parsed['links']['critical'])} ≠ 关键级内边 {sorted(crit_edges)}")
    if set(parsed["links"]["normal"]) != normal_edges:
        raise CheckError("linkStyle 灰色实线 ≠ 非关键级内边")
    if set(parsed["links"]["inter"]) != inter_idx:
        raise CheckError(f"linkStyle 橙色虚线 {sorted(parsed['links']['inter'])} ≠ 级间边 {sorted(inter_idx)}")
    if set(parsed["links"]["feedback"]) != fb_idx:
        raise CheckError(f"linkStyle 灰色点线 {sorted(parsed['links']['feedback'])} ≠ 回流边 {sorted(fb_idx)}")

    # 结构：根 / 汇聚 / 回流方向 / 级间是紧贴 FS
    roots = [n for n in labels if not merged["pred"][n]]
    if roots != ROOTS:
        raise CheckError(f"根节点应为 {ROOTS}（都只依赖图外的 L1 交付），实际 {roots}")
    for nid, want in CONVERGE.items():
        if set(merged["pred"][nid]) != want:
            raise CheckError(f"{nid} 的紧前应为 {sorted(want)}，实际 {sorted(merged['pred'][nid])}")
    for u, v in FEEDBACK:
        if merged["ES"][u] + dur[u] <= merged["ES"][v]:
            raise CheckError(f"回流边 {u}→{v} 不是从后往前指，看起来像正向依赖")
    for u, v in INTER:
        if merged["ES"][v] != merged["EF"][u]:
            raise CheckError(f"级间依赖 {u}→{v} 不是紧贴 FS（ES({v})={merged['ES'][v]} ≠ EF({u})={merged['EF'][u]}）")

    # 工期口径与来源（注释里必须写清）
    for need, why in [
        ("估算值", "工期口径必须写「估算值」"),
        ("不是验收时限", "工期口径必须写「不是验收时限」"),
        ("计入 CPM", "级间虚线必须写清「计入 CPM」"),
        ("不计 CPM", "回流点线必须写清「不计 CPM」"),
        ("L1 交付", "起点必须写「L1 交付」"),
        ("flow.mmd", "必须写清 L1 旧图见 flow.mmd"),
        ("render_flow_l2_l5.py", "必须写清渲染命令"),
    ]:
        if need not in comment_text:
            raise CheckError(f"注释缺少「{need}」——{why}")

    # 打印对账表
    if not quiet:
        print(f"   节点 {len(labels)}：{' '.join(labels)}；泳道 {' / '.join(l for l, _ in LANES)}")
        print(f"   {'编号':<4}{'工期':>5}{'ES':>5}{'EF':>5}{'LS':>5}{'LF':>5}{'浮动':>5}  关键")
        for nid in labels:
            print(f"   {nid:<4}{dur[nid]:>6}{merged['ES'][nid]:>6}{merged['EF'][nid]:>6}"
                  f"{merged['LS'][nid]:>6}{merged['LF'][nid]:>6}{merged['TF'][nid]:>6}"
                  f"  {'★' if merged['TF'][nid] == 0 else ''}")
        print(f"   标注比对：{fields_equal}/{fields_total} 字段全等 ✓；自洽：EF=ES+工期、LS=LF−工期 ✓；浮动非负 ✓")
        print(f"   关键路径（{len(merged['path'])} 节点）：{' → '.join(merged['path'])}")
        print(f"   总工期 330 = L2 {LEVEL_DUR['L2']} + L3 {LEVEL_DUR['L3']} + L4 {LEVEL_DUR['L4']} + L5 {LEVEL_DUR['L5']}"
              f"（级间串行；不计级间时最大一段 {alone['total']}）✓")
        print(f"   浮动：P11 = 5 分钟（不进关键路径）；其余节点 0 ✓；class critical {len(crit)} 个一致 ✓")
        print(f"   边：级内实线 {len(SOLID)} + 级间虚线 {len(INTER)}（计入 CPM）+ 回流点线 {len(FEEDBACK)}（不计）✓")
    return merged


# ------------------------------------------------------------------ 断言：PNG + OCR

def histogram(png: Path) -> dict[tuple[int, int, int], int]:
    proc = subprocess.run(["convert", str(png), "-format", "%c", "histogram:info:-"],
                          capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise CheckError(f"ImageMagick 读直方图失败：{png.name}")
    out = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*(\d+):\s*\((\d+),(\d+),(\d+)\)", line)
        if m:
            out[(int(m.group(2)), int(m.group(3)), int(m.group(4)))] = int(m.group(1))
    return out


def verify_png(quiet: bool) -> dict:
    if not PNG.exists():
        raise CheckError(f"缺图：{PNG}")
    proc = subprocess.run(["identify", "-format", "%w %h", str(PNG)],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise CheckError("identify 读不出 PNG")
    w, h = (int(x) for x in proc.stdout.split())
    if w != WIDTH:
        raise CheckError(f"PNG 宽度 {w} ≠ {WIDTH}（任务口径：与现有 AON 同宽 1100 或 1600）")
    if not 800 <= h <= 2000:
        raise CheckError(f"PNG 高度 {h} 不在合理区间 800–2000")
    counts = histogram(PNG)
    total = sum(counts.values())
    non_white = total - counts.get((255, 255, 255), 0)
    if non_white < 30000:
        raise CheckError(f"PNG 几乎空白（非白 {non_white} 像素）")
    orange = sum(c for px, c in counts.items()
                 if (px[0] - CRIT_STROKE[0]) ** 2 + (px[1] - CRIT_STROKE[1]) ** 2
                 + (px[2] - CRIT_STROKE[2]) ** 2 <= 40 * 40)
    if orange < 3000:
        raise CheckError(f"PNG 找不到关键路径橙色描边（{orange} 像素）")
    if counts.get(CRIT_FILL, 0) < 3000:
        raise CheckError(f"PNG 找不到关键节点浅橙底（{counts.get(CRIT_FILL, 0)} 像素）")
    if counts.get(NORMAL_FILL, 0) < 1000:
        raise CheckError(f"PNG 找不到普通节点（P11）灰色底（{counts.get(NORMAL_FILL, 0)} 像素）")
    if not quiet:
        print(f"   图片：{w}x{h}px；非白 {non_white} 像素；橙色描边 {orange} 像素；"
              f"关键浅橙 {counts.get(CRIT_FILL, 0)} 像素；普通灰底 {counts.get(NORMAL_FILL, 0)} 像素 ✓")
    return dict(w=w, h=h, non_white=non_white)


def ocr_text(png: Path) -> str:
    """2x 灰度 + 锐化后跑 tesseract（eng 足够认 P/G 编号与数字）；返回 psm 6+11 合并文本。"""
    with tempfile.TemporaryDirectory(prefix="aon-ocr-") as tmp:
        pre = Path(tmp) / "up.png"
        proc = subprocess.run(
            ["convert", str(png), "-resize", "200%", "-colorspace", "Gray",
             "-sharpen", "0x1", str(pre)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 or not pre.exists():
            raise CheckError("OCR 预处理失败（ImageMagick）")
        texts = []
        for psm in ("6", "11"):
            r = subprocess.run(["tesseract", str(pre), "stdout", "-l", "eng", "--psm", psm],
                               capture_output=True, text=True, timeout=180)
            texts.append(r.stdout)
        return "\n".join(texts)


def verify_ocr(quiet: bool) -> None:
    tags = [f"P{i}" for i in range(10, 24)] + ["G2", "G3", "G4", "G5"]
    text = ocr_text(PNG)
    flat = re.sub(r"\s+", "", text)
    missing = [tag for tag in tags if tag not in flat]
    if missing:
        raise CheckError(f"OCR 没在图里命中 {missing}（命中：{[t for t in tags if t in flat]}）")
    if not quiet:
        print(f"   OCR（tesseract eng，psm 6+11，200%）：{' '.join(f'{t}✓' for t in tags)}")


def shutil_which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description="独立断言 L2–L5 合并 AON 的 CPM、关键路径、PNG 与 OCR")
    ap.add_argument("-q", "--quiet", action="store_true", help="只打印结论与失败")
    ap.add_argument("--no-ocr", action="store_true", help="跳过 OCR（环境没有 tesseract 时）")
    args = ap.parse_args()

    ocr_ok = shutil_which("tesseract") is not None and not args.no_ocr
    print(f"== L2–L5 合并 AON：{MMD.relative_to(REPO)} → {PNG.relative_to(REPO)}")
    try:
        parsed = parse_mmd(MMD)
        cpm_relaxation(  # 先单独跑一遍松弛，确认 DAG 合法（级内 + 级间）
            {n: label_fields(n, lb)["dur"] for n, lb in parsed["labels"].items()},
            parsed["solid"] + parsed["inter"])
        merged = verify_cpm(parsed, args.quiet)
        verify_png(args.quiet)
        if ocr_ok:
            verify_ocr(args.quiet)
        elif not args.quiet:
            print("   OCR：跳过（tesseract 不可用或 --no-ocr）；以 mmd 关键字 + PNG 配色为准")
        if not args.quiet:
            print(f"   ✔ 通过：CPM 标注全等 / 关键路径四方一致 / 级间计入·回流不计 / 图片与 OCR 命中")
    except CheckError as exc:
        print(f"   ✘ 失败：{exc}", file=sys.stderr)
        print(f"\n❌ 结果：合并 AON 未通过（{exc}）")
        return 1
    print(f"\n✅ 结果：L2–L5 合并 AON 通过（18 节点 / 330 分钟 / 关键路径 "
          f"{' → '.join(merged['path'])}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
