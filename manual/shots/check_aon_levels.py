#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_aon_levels.py —— L2/L3/L4 三张 AON 的独立断言脚本（只读，不渲染）。

它故意**不 import** render_flow_levels.py 的 CPM 实现：从 mmd 原文重新解析节点/工期/依赖，
用另一套算法（逐轮松弛到不动点，而不是 Kahn 拓扑序）重算 ES/EF/LS/LF/浮动，再逐节点和
mmd 里写的数值比对；关键路径节点集合与注释、class critical 三方对账。最后查 PNG 尺寸/配色，
并用 tesseract 对 PNG 做 OCR，确认 P10–P13 / P14–P17 / P18–P22 与级考核节点真的画在图上。

一条命令（在仓库根目录）：

    python3 manual/shots/check_aon_levels.py          # 人看的对账表
    python3 manual/shots/check_aon_levels.py -q       # 只留结论与失败
    python3 manual/shots/check_aon_levels.py --no-ocr # 环境没有 tesseract 时跳过 OCR

退出码 0 = 三张网全部通过；1 = 有断言失败（明细打在 stderr）。
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
WIDTH = 1100                                # 与 L1 的 flow-aon.png 同宽
CRIT_STROKE = (230, 81, 0)                  # #e65100
CRIT_FILL = (255, 241, 224)                 # #fff1e0
NORMAL_FILL = (246, 247, 249)               # #f6f7f9

LEVELS = [
    {
        "key": "L2",
        "mmd": REPO / "manual" / "flow-l2.mmd",
        "png": REPO / "manual" / "images" / "aon-l2.png",
        "pages": ["P10", "P11", "P12", "P13", "G2"],
        "names": ["换真数据", "换真契约", "换真执行器", "换真部署", "级考核"],
        "roots": ["P10", "P11"],
        "converge": {"P12": ["P10", "P11"]},
        "feedback": [],
    },
    {
        "key": "L3",
        "mmd": REPO / "manual" / "flow-l3.mmd",
        "png": REPO / "manual" / "images" / "aon-l3.png",
        "pages": ["P14", "P15", "P16", "P17", "G3"],
        "names": ["审召回", "审生成", "审校验", "审纠错", "级考核"],
        "roots": ["P14"],
        "converge": {},
        "feedback": [("P17", "P15")],
    },
    {
        "key": "L4",
        "mmd": REPO / "manual" / "flow-l4.mmd",
        "png": REPO / "manual" / "images" / "aon-l4.png",
        "pages": ["P18", "P19", "P20", "P21", "P22", "G4"],
        "names": ["守账号", "守策略", "守取消", "守可观测", "守回归", "级考核"],
        "roots": ["P18"],
        "converge": {"P22": ["P18", "P19", "P20", "P21"]},
        "feedback": [],
    },
]


class CheckError(Exception):
    """一条断言失败：带级别前缀，最后由 main 汇总。"""


# ------------------------------------------------------------------ 解析（独立实现）

def parse_mmd(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%%"))
    comments = [ln for ln in text.splitlines() if ln.lstrip().startswith("%%")]

    if not re.search(r"^flowchart\s+LR\s*$", body, re.M):
        raise CheckError(f"{path.name} 首行声明不是 `flowchart LR`")

    labels = {}
    for m in re.finditer(r'^\s*([A-Za-z]\w*)\["(.*)"\]\s*$', body, re.M):
        labels[m.group(1)] = m.group(2)

    solid, feedback = [], []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*-->\|([^|]*)\|\s*([A-Za-z]\w*)\s*$", body, re.M):
        if m.group(2).strip() != "FS":
            raise CheckError(f"{path.name} 实线 {m.group(1)}→{m.group(3)} 没标 FS")
        solid.append((m.group(1), m.group(3)))
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*-\.->\|([^|]*)\|\s*([A-Za-z]\w*)\s*$", body, re.M):
        if "回流" not in m.group(2):
            raise CheckError(f"{path.name} 虚线 {m.group(1)}→{m.group(3)} 没标「回流」")
        feedback.append((m.group(1), m.group(3)))

    classes = {}
    for m in re.finditer(r"^\s*class[ \t]+([\w, \t]+?)[ \t]+(critical|normal)[ \t]*$", body, re.M):
        classes[m.group(2)] = [x.strip() for x in m.group(1).split(",") if x.strip()]
    return dict(text=text, comments=comments, labels=labels, solid=solid,
                feedback=feedback, classes=classes)


def label_fields(label: str) -> dict:
    dur = re.search(r"工期\s*(\d+)", label)
    cpm = re.search(r"ES(\d+)\s+EF(\d+)\s+LS(\d+)\s+LF(\d+)", label)
    if not dur or not cpm:
        raise CheckError(f"节点缺工期或 ES/EF/LS/LF：{label[:40]}")
    name = re.search(r"<b>[A-Za-z0-9]+ ([^<]+)</b>", label)
    return dict(dur=int(dur.group(1)),
                ES=int(cpm.group(1)), EF=int(cpm.group(2)),
                LS=int(cpm.group(3)), LF=int(cpm.group(4)),
                name=name.group(1) if name else "")


# ------------------------------------------------------------------ CPM（另一套算法：松弛到不动点）

def cpm_relaxation(dur: dict[str, int], solid: list[tuple[str, str]]):
    ids = list(dur)
    pred = {n: [] for n in ids}
    succ = {n: [] for n in ids}
    for u, v in solid:
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
        raise CheckError("正推松弛不收敛（实线依赖可能有环）")
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
        raise CheckError("逆推松弛不收敛（实线依赖可能有环）")

    TF = {n: LS[n] - ES[n] for n in ids}
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


# ------------------------------------------------------------------ 断言：CPM / 注释 / class

def verify_cpm(level: dict, parsed: dict, quiet: bool) -> dict:
    labels = parsed["labels"]
    fields = {nid: label_fields(lb) for nid, lb in labels.items()}
    dur = {nid: f["dur"] for nid, f in fields.items()}
    if list(labels) != level["pages"]:
        raise CheckError(f"节点集合/顺序应为 {level['pages']}，实际 {list(labels)}")
    for nid, name in zip(level["pages"], level["names"]):
        if name not in labels[nid]:
            raise CheckError(f"{nid} 的活动名应含「{name}」，实际标签：{labels[nid][:60]}")
        if "（估）" not in labels[nid]:
            raise CheckError(f"{nid} 的工期没标「（估）」")
        if "判据：" not in labels[nid]:
            raise CheckError(f"{nid} 没有「判据：」")

    c = cpm_relaxation(dur, parsed["solid"])

    # 1) 逐节点逐字段与 mmd 标注比对（全等）
    fields_total = fields_equal = 0
    for nid, f in fields.items():
        want = dict(ES=c["ES"][nid], EF=c["EF"][nid], LS=c["LS"][nid], LF=c["LF"][nid])
        for k, v in want.items():
            fields_total += 1
            if f[k] == v:
                fields_equal += 1
            else:
                raise CheckError(f"{nid}.{k}：mmd 写 {f[k]}，独立重算 {v}")

    # 2) CPM 自洽：EF=ES+工期；LS=LF-工期；浮动=LS-ES=LF-EF 且非负
    for nid in labels:
        if c["EF"][nid] != c["ES"][nid] + dur[nid]:
            raise CheckError(f"{nid} EF≠ES+工期")
        if c["LS"][nid] != c["LF"][nid] - dur[nid]:
            raise CheckError(f"{nid} LS≠LF-工期")
        if c["TF"][nid] != c["LF"][nid] - c["EF"][nid]:
            raise CheckError(f"{nid} 浮动 LS-ES ≠ LF-EF")
        if c["TF"][nid] < 0:
            raise CheckError(f"{nid} 总浮动为负：{c['TF'][nid]}")

    # 3) 关键集合三方对账：浮动=0 / class critical / 注释关键路径
    crit = {n for n in labels if c["TF"][n] == 0}
    if set(parsed["classes"].get("critical", [])) != crit:
        raise CheckError(f"class critical {sorted(parsed['classes'].get('critical', []))} ≠ 浮动0集合 {sorted(crit)}")
    if set(parsed["classes"].get("normal", [])) != set(labels) - crit:
        raise CheckError("class normal ≠ 非关键集合")
    comment_text = "\n".join(parsed["comments"])
    m = re.search(r"%%\s*关键路径：([^，\n]+)，总工期\s*(\d+)\s*分钟", comment_text)
    if not m:
        raise CheckError("注释里缺「%% 关键路径：…，总工期 N 分钟」")
    declared_path = [x.strip() for x in re.split(r"→", m.group(1)) if x.strip()]
    if declared_path != c["path"]:
        raise CheckError(f"注释关键路径 {declared_path} ≠ 重算 {c['path']}")
    if int(m.group(2)) != c["total"]:
        raise CheckError(f"注释总工期 {m.group(2)} ≠ 重算 {c['total']}")
    if set(declared_path) != crit:
        raise CheckError("注释关键路径节点集合 ≠ 浮动=0 集合")
    for nid in labels:
        if c["TF"][nid] > 0 and not re.search(rf"{nid}（[^）]*）[^\n]*总浮动 {c['TF'][nid]} 分钟", comment_text):
            raise CheckError(f"注释没写 {nid} 的总浮动 {c['TF'][nid]} 分钟")

    # 4) 结构：根节点 / 汇聚节点 / 回流边方向 / 虚线不参与 CPM（实线无环已由松弛收敛保证）
    roots = [n for n in labels if not c["pred"][n]]
    if roots != level["roots"]:
        raise CheckError(f"根节点应为 {level['roots']}，实际 {roots}")
    for nid, want in level["converge"].items():
        if set(c["pred"][nid]) != set(want):
            raise CheckError(f"{nid} 的紧前应为 {sorted(want)}，实际 {sorted(c['pred'][nid])}")
    if parsed["feedback"] != level["feedback"]:
        raise CheckError(f"虚线回流边应为 {level['feedback']}，实际 {parsed['feedback']}")
    for u, v in parsed["feedback"]:
        if c["ES"][u] + dur[u] <= c["ES"][v]:
            raise CheckError(f"回流边 {u}→{v} 不是从后往前指，看起来像正向依赖")

    # 5) 打印对账表
    if not quiet:
        print(f"   节点 {len(labels)}：{' '.join(labels)}；注释总工期 {m.group(2)} 分钟 = 重算 {c['total']} ✓")
        print(f"   {'编号':<4}{'工期':>4}{'ES':>4}{'EF':>4}{'LS':>4}{'LF':>4}{'浮动':>5}  关键")
        for nid in labels:
            print(f"   {nid:<4}{dur[nid]:>5}{c['ES'][nid]:>5}{c['EF'][nid]:>5}"
                  f"{c['LS'][nid]:>5}{c['LF'][nid]:>5}{c['TF'][nid]:>5}  {'★' if c['TF'][nid] == 0 else ''}")
        print(f"   标注比对：{fields_equal}/{fields_total} 字段全等 ✓"
              f"；自洽：EF=ES+工期 {len(labels)}/{len(labels)} ✓"
              f"；LS=LF−工期 {len(labels)}/{len(labels)} ✓"
              f"；浮动非负 ✓")
        floats = [f"{n}={c['TF'][n]}" for n in labels if c["TF"][n] > 0]
        print(f"   关键路径：{' → '.join(c['path'])}；注释一致 ✓；class critical {len(crit)} 个一致 ✓"
              + (f"；非关键浮动 {'、'.join(floats)} ✓" if floats else "；无浮动节点 ✓"))
    return c


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


def verify_png(level: dict, quiet: bool) -> dict:
    png = level["png"]
    if not png.exists():
        raise CheckError(f"缺图：{png}")
    proc = subprocess.run(["identify", "-format", "%w %h", str(png)],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise CheckError(f"identify 读不出 {png.name}")
    w, h = (int(x) for x in proc.stdout.split())
    if w != WIDTH:
        raise CheckError(f"{png.name} 宽度 {w} ≠ {WIDTH}（应与 L1 的 flow-aon.png 同宽）")
    if not 150 <= h <= 900:
        raise CheckError(f"{png.name} 高度 {h} 不在合理区间 150–900")

    counts = histogram(png)
    total = sum(counts.values())
    white = counts.get((255, 255, 255), 0)
    non_white = total - white
    if non_white < 20000:
        raise CheckError(f"{png.name} 几乎空白（非白 {non_white} 像素）")
    orange = sum(c for px, c in counts.items()
                 if (px[0] - CRIT_STROKE[0]) ** 2 + (px[1] - CRIT_STROKE[1]) ** 2
                 + (px[2] - CRIT_STROKE[2]) ** 2 <= 40 * 40)
    if orange < 3000:
        raise CheckError(f"{png.name} 找不到关键路径橙色描边（{orange} 像素）")
    if counts.get(CRIT_FILL, 0) < 3000:
        raise CheckError(f"{png.name} 找不到关键节点浅橙底（{counts.get(CRIT_FILL, 0)} 像素）")
    has_normal = level["key"] == "L2"   # 只有 L2 有非关键节点 P11（5 分钟浮动）
    if has_normal and counts.get(NORMAL_FILL, 0) < 1000:
        raise CheckError(f"{png.name} 找不到普通节点灰色底（{counts.get(NORMAL_FILL, 0)} 像素）")
    if not quiet:
        print(f"   图片：{w}x{h}px；非白 {non_white} 像素；橙色描边 {orange} 像素；"
              f"关键浅橙 {counts.get(CRIT_FILL, 0)} 像素"
              + (f"；普通灰底 {counts.get(NORMAL_FILL, 0)} 像素" if has_normal else "") + " ✓")
    return dict(w=w, h=h, non_white=non_white)


def ocr_text(png: Path) -> str:
    """2x 灰度 + 锐化后跑 tesseract（eng 足够认 P/G/L 编号与数字）；返回 psm 6+11 合并文本。"""
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


def verify_ocr(level: dict, quiet: bool) -> None:
    text = ocr_text(level["png"])
    flat = re.sub(r"\s+", "", text)
    missing = [tag for tag in level["pages"] if tag not in flat]
    if missing:
        raise CheckError(f"OCR 没在图里命中 {missing}（命中：{[t for t in level['pages'] if t in flat]}）")
    if not quiet:
        print(f"   OCR（tesseract eng，psm 6+11）：{' '.join(f'{t}✓' for t in level['pages'])}")


def shutil_which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description="独立断言 L2/L3/L4 三张 AON 的 CPM、关键路径、PNG 与 OCR")
    ap.add_argument("-q", "--quiet", action="store_true", help="只打印每级结论与失败明细")
    ap.add_argument("--no-ocr", action="store_true", help="跳过 OCR（环境没有 tesseract 时）")
    args = ap.parse_args()

    ocr_ok = shutil_which("tesseract") is not None and not args.no_ocr
    failures = 0
    passed = 0
    for level in LEVELS:
        print(f"\n== {level['key']}：{level['mmd'].relative_to(REPO)} → {level['png'].relative_to(REPO)}")
        try:
            parsed = parse_mmd(level["mmd"])
            c = verify_cpm(level, parsed, args.quiet)
            verify_png(level, args.quiet)
            if ocr_ok:
                verify_ocr(level, args.quiet)
            elif not args.quiet:
                print("   OCR：跳过（tesseract 不可用或 --no-ocr）；以 mmd 关键字 + PNG 配色为准")
            if not args.quiet:
                print(f"   ✔ {level['key']} 通过：CPM 标注全等 / 关键路径三方一致 / 图片与 OCR 命中")
            passed += 1
        except CheckError as exc:
            failures += 1
            print(f"   ✘ {level['key']} 失败：{exc}", file=sys.stderr)

    print(f"\n{'✅' if failures == 0 else '❌'} 结果：{passed}/{len(LEVELS)} 张网通过"
          f"（CPM 独立重算 + 标注比对 + 关键路径 + PNG + {'OCR' if ocr_ok else '关键字'}）")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
