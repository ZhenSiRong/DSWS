#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_aoa.py —— 把双代号（AOA/ADM）对照图源 `tutorial/flow-aoa.mmd` 渲染成
`tutorial/images/flow-aoa.png`，供 `tutorial/README.md` 末尾的对照附录使用。

一条命令重跑（在仓库根目录）：

    python3 tutorial/shots/render_aoa.py

它和 `render_flow.py` 同一套技术（mermaid CDN + 无头 Chrome + ImageMagick trim），
但独立成文件，只服务 AOA 图；**不改** `render_flow.py`、`flow.mmd`、`flow-aon.png`。

它做五件事：

1. **核对图源**：读 `tutorial/flow-aoa.mmd`，要求 `flowchart LR`、10 个活动 A0–A9
   各出现且只出现一次、工期与 AON/CPM 表一致、**0 条虚活动**（出现 `-.->` 直接报错）、
   10 个事件圆圈 e1–e10（每个事件一个编号）、节点里只放事件编号。
2. **重算 CPM**：不信任图上的颜色，按箭线上的工期独立算一遍 AOA 的 CPM——正推事件
   最早时间 ETE、逆推最迟时间 LTE、再算活动 ES/EF/LS/LF 与总浮动 TF；关键活动集合
   （TF=0）必须正好是图里 `linkStyle ... #e65100` 标橙的箭线，非关键正好是灰色那两条。
3. **渲染**：mermaid@11（CDN）内联进临时 HTML，用 google-chrome 无头浏览器跑出
   SVG，再按自然尺寸截图（`--force-device-scale-factor=2` 超采样，文字 1:1 可读）。
4. **落盘**：`convert -trim` 裁白边 → 缩到约定宽度（默认 1100px）→ 四周补白 → 写 PNG。
5. **自检**：从渲染后的 DOM 里核对 e1…e10、A0…A9 的编号全在；核对橙色/灰色
   linkStyle 真的生效；检查 PNG 尺寸、关键路径橙色像素、无色块裁切、不含用户名/
   绝对路径；装了 tesseract 就顺带 OCR 复核一遍 A0–A9（OCR 只作旁证，主判据是 DOM）。

**为什么是 10 个事件、0 条虚活动**：这张图是串并联形状——汇聚事件 e6 同时收 A2 与
A6，不需要为「只依赖其一」另设事件，也没有两个活动共享同一对起止事件，所以 0 条虚
活动；因此 10 条实箭线只需要 10 个事件（e1–e10）。

依赖：本机已有的 python3 / google-chrome / ImageMagick(convert)，能访问 CDN；
Pillow 与 tesseract 可选（有就多做两项旁证，没有不影响出图）。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent      # tutorial/shots
REPO = HERE.parents[1]                      # 仓库根目录
MMD = REPO / "manual" / "flow-aoa.mmd"
OUT = REPO / "manual" / "images" / "flow-aoa.png"

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
DEFAULT_WIDTH = 1100   # 与 flow-aon.png / 练本其它截图同宽
MARGIN = 16            # 最终 PNG 四周留白（px）
FORBIDDEN = ["/home/", "/Users/", "/tmp/", "zhensirong", "root@", ".dsh"]

# 事实基线：活动工期必须与 AON 图 / README 的 CPM 表一致（单位：分钟）
EXPECT_DUR = {"A0": 10, "A1": 3, "A2": 2, "A3": 5, "A4": 4,
              "A5": 8, "A6": 10, "A7": 6, "A8": 10, "A9": 8}
EXPECT_CRIT = ["A0", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
EXPECT_TOTAL = 61
EXPECT_EVENTS = [f"e{i}" for i in range(1, 11)]   # 10 个事件 e1–e10

# mermaid 渲染参数：字号/间距在这里统一调，mmd 只存内容与关键路径样式
MERMAID_CFG = {
    "startOnLoad": False,
    "securityLevel": "loose",
    "theme": "default",
    "fontFamily": "'Noto Sans CJK SC','Source Han Sans SC','Microsoft YaHei',sans-serif",
    "flowchart": {
        "useMaxWidth": False,   # 让 SVG 有自然尺寸，才能按自然尺寸截图
        "htmlLabels": True,
        "curve": "linear",
        "wrappingWidth": 600,
        "nodeSpacing": 46,
        "rankSpacing": 56,
        "padding": 8,
        "diagramPadding": 6,
    },
    "themeVariables": {"fontSize": "22px"},
}

FIG_TITLE_PX = 30
FIG_SMALL_PX = 21
FONT_STACK = "Noto Sans CJK SC,Source Han Sans SC,Microsoft YaHei,sans-serif"


# ------------------------------------------------------------------ 1. 读 + 核对图源

def show(path: Path) -> str:
    """给日志用：仓库内文件显示相对路径，仓库外显示原路径。"""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def read_mmd() -> tuple[str, str, dict[str, int], list[dict]]:
    """读 flow-aoa.mmd，返回 (原文, 去注释正文, 事件→编号, 箭线列表)。"""
    text = MMD.read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%%"))

    if not re.search(r"^flowchart\s+LR\s*$", body, re.M):
        raise SystemExit(f"{MMD} 必须以 `flowchart LR` 声明（双代号网络图从左到右排）")

    if re.search(r"-\.+->|-\.-", body):
        raise SystemExit("本网络不需要虚活动：flow-aoa.mmd 里不允许出现 `-.->` 虚箭线")

    nodes: dict[str, int] = {}
    for m in re.finditer(r"(e\d+)\(\((\d+)\)\)", body):
        nid, num = m.group(1), int(m.group(2))
        if nid in nodes and nodes[nid] != num:
            raise SystemExit(f"事件 {nid} 的圆圈编号前后不一致：{nodes[nid]} vs {num}")
        nodes[nid] = num
    if not nodes:
        raise SystemExit("flow-aoa.mmd 里没有找到 `eN((N))` 形式的事件圆圈")

    # 去掉圆圈声明，剩下的每行都应是「事件 -->|活动 工期| 事件」
    body2 = re.sub(r"\(\(\d+\)\)", "", body)
    edges: list[dict] = []
    for m in re.finditer(r'^\s*(e\d+)\s*-->\s*(?:\|"([^"]*)"\|)?\s*(e\d+)\s*$', body2, re.M):
        u, label, v = m.group(1), (m.group(2) or "").strip(), m.group(3)
        if not label:
            raise SystemExit(f"箭线 {u}→{v} 没写「活动编号 工期」")
        am = re.fullmatch(r"(A\d+)\s+(\d+)", label)
        if not am:
            raise SystemExit(f"箭线 {u}→{v} 的标签 {label!r} 不是「A编号 工期」")
        edges.append({"act": am.group(1), "dur": int(am.group(2)), "u": u, "v": v})
    if body2.count("-->") != len(edges):
        raise SystemExit("有 `-->` 不是「事件 -->|活动 工期| 事件」的写法，检查 flow-aoa.mmd")

    # 事件：10 个事件 e1–e10，编号连号不留空；圆圈里的数字必须与事件编号一致
    used = {e["u"] for e in edges} | {e["v"] for e in edges}
    if set(nodes) != used:
        raise SystemExit(f"事件圆圈与箭线端点不一致：圆圈 {sorted(nodes)}，端点 {sorted(used)}")
    for nid, num in nodes.items():
        if int(nid[1:]) != num:
            raise SystemExit(f"事件 {nid} 圆圈里应写 {nid[1:]}，实际写 {num}")
    if set(nodes) != set(EXPECT_EVENTS):
        raise SystemExit(f"事件节点必须正好是 {EXPECT_EVENTS}，实际 {sorted(nodes)}")

    # 活动：A0–A9 各一次，工期与事实基线一致
    acts = [e["act"] for e in edges]
    if sorted(acts) != sorted(EXPECT_DUR):
        raise SystemExit(f"箭线必须正好是活动 A0–A9 各一次，实际 {acts}")
    for e in edges:
        if EXPECT_DUR[e["act"]] != e["dur"]:
            raise SystemExit(f"{e['act']} 工期写 {e['dur']}，应为 {EXPECT_DUR[e['act']]}")
    return text, body, nodes, edges


def aoa_cpm(nodes: dict[str, int], edges: list[dict]) -> dict:
    """按箭线上的工期独立重算 AOA 的 CPM（事件 ETE/LTE → 活动 ES/EF/LS/LF/TF）。"""
    succ = {e: [] for e in nodes}
    pred = {e: [] for e in nodes}
    for e in edges:
        succ[e["u"]].append(e)
        pred[e["v"]].append(e)

    indeg = {e: len(pred[e]) for e in nodes}
    queue = sorted((e for e in nodes if indeg[e] == 0), key=lambda x: int(x[1:]))
    topo: list[str] = []
    while queue:
        cur = queue.pop(0)
        topo.append(cur)
        for ed in succ[cur]:
            indeg[ed["v"]] -= 1
            if indeg[ed["v"]] == 0:
                queue.append(ed["v"])
    if len(topo) != len(nodes):
        raise SystemExit("网络图有环，不是合法 AOA")

    ETE = {e: 0 for e in nodes}
    for u in topo:
        for ed in succ[u]:
            ETE[ed["v"]] = max(ETE[ed["v"]], ETE[u] + ed["dur"])
    sinks = [e for e in nodes if not succ[e]]
    if set(sinks) != {"e10"}:
        raise SystemExit(f"网络必须只有一个终点事件 e10，实际终点 {sorted(sinks)}")
    total = ETE["e10"]
    if total != EXPECT_TOTAL:
        raise SystemExit(f"总工期重算为 {total}，应为 {EXPECT_TOTAL}")

    LTE = {e: total for e in nodes}
    for u in reversed(topo):
        if succ[u]:
            LTE[u] = min(LTE[ed["v"]] - ed["dur"] for ed in succ[u])

    rows = []
    for ed in edges:
        ES = ETE[ed["u"]]
        EF = ES + ed["dur"]
        LF = LTE[ed["v"]]
        LS = LF - ed["dur"]
        TF = LS - ES
        rows.append({**ed, "ES": ES, "EF": EF, "LS": LS, "LF": LF, "TF": TF,
                     "critical": TF == 0})
    crit_computed = [r["act"] for r in rows if r["critical"]]
    if set(crit_computed) != set(EXPECT_CRIT):
        raise SystemExit(
            f"关键活动重算为 {sorted(crit_computed)}，应正好是 {sorted(EXPECT_CRIT)}")

    # 关键路径：从起点沿 TF=0 的箭线一路走到终点
    tf = {r["act"]: r["TF"] for r in rows}
    starts = [e for e in nodes if not pred[e]]
    if starts != ["e1"]:
        raise SystemExit(f"网络必须只有一个起点事件 e1，实际 {sorted(starts)}")
    path, cur = [], "e1"
    while True:
        nxt = [ed for ed in succ[cur] if tf[ed["act"]] == 0]
        if not nxt:
            break
        if len(nxt) > 1:
            raise SystemExit(f"关键路径在 {cur} 分叉，需要人工确认")
        path.append(nxt[0]["act"])
        cur = nxt[0]["v"]
    if path != EXPECT_CRIT or cur != "e10":
        raise SystemExit(f"关键路径为 {path}（终点 {cur}），应为 {EXPECT_CRIT} → e10")
    return {"ETE": ETE, "LTE": LTE, "rows": rows, "total": total, "path": path}


def check_styles(body: str, nodes: dict[str, int], edges: list[dict],
                 rows: list[dict]) -> None:
    """核对 linkStyle 的橙色/灰色箭线集合与重算的「关键 / 非关键」一致。"""
    styles = re.findall(r"^\s*linkStyle\s+([\d,\s]+?)\s+(.+?)\s*$", body, re.M)
    if not styles:
        raise SystemExit("flow-aoa.mmd 里没有 linkStyle，关键路径无法标橙")

    orange, gray = set(), set()
    for idxs, style in styles:
        idx = {int(x) for x in idxs.split(",") if x.strip()}
        s = style.replace(" ", "")
        if "#e65100" in s:
            if "stroke-width:4px" not in s:
                raise SystemExit("关键路径 linkStyle 必须 `stroke:#e65100;stroke-width:4px`")
            orange |= idx
        elif "#9aa0a6" in s:
            if "stroke-width:2px" not in s:
                raise SystemExit("非关键 linkStyle 必须 `stroke:#9aa0a6;stroke-width:2px`")
            gray |= idx
        else:
            raise SystemExit(f"linkStyle 只允许橙色关键 / 灰色非关键两种样式：{style!r}")
    if orange & gray:
        raise SystemExit("同一条箭线既标关键又标非关键")
    if orange | gray != set(range(len(edges))):
        raise SystemExit(f"linkStyle 没覆盖全部 {len(edges)} 条箭线："
                         f"橙色 {sorted(orange)}，灰色 {sorted(gray)}")

    acts = [e["act"] for e in edges]
    orange_acts = {acts[i] for i in orange}
    gray_acts = {acts[i] for i in gray}
    crit = {r["act"] for r in rows if r["critical"]}
    if orange_acts != crit:
        raise SystemExit(f"橙色箭线 {sorted(orange_acts)} 与重算关键活动 {sorted(crit)} 不符")
    if gray_acts != set(acts) - crit:
        raise SystemExit(f"灰色箭线 {sorted(gray_acts)} 与重算非关键活动不符")

    m = re.search(r"^\s*class\s+([\w,\s]+?)\s+event\s*$", body, re.M)
    if not m or "classDef event" not in body:
        raise SystemExit("flow-aoa.mmd 缺少事件圆圈样式（classDef event / class ... event）")
    styled = {x.strip() for x in m.group(1).split(",") if x.strip()}
    if styled != set(nodes):
        raise SystemExit(f"事件样式没覆盖全部事件圆圈：{sorted(styled)}")


def print_table(cpm: dict) -> None:
    print(f"✅ AOA CPM 核对通过：{len(EXPECT_DUR)} 条实箭线、{len(cpm['ETE'])} 个事件、"
          f"0 条虚活动；总工期 {cpm['total']} 分钟")
    print(f"{'活动':<4}{'箭线':<8}{'工期':>4}{'ES':>4}{'EF':>4}{'LS':>4}{'LF':>4}"
          f"{'总浮动':>6}  关键")
    for r in cpm["rows"]:
        print(f"{r['act']:<6}{r['u'] + '→' + r['v']:<10}{r['dur']:>4}{r['ES']:>4}"
              f"{r['EF']:>4}{r['LS']:>4}{r['LF']:>4}{r['TF']:>6}  "
              f"{'★' if r['critical'] else ''}")
    print(f"关键路径：{' → '.join(cpm['path'])}（总工期 {cpm['total']} 分钟）")


# ------------------------------------------------------------------ 2. HTML + 渲染

def fetch_mermaid() -> str:
    print(f"↓ 从 CDN 取 mermaid@11 … {MERMAID_URL}")
    try:
        req = urllib.request.Request(MERMAID_URL, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
    except Exception as exc:  # noqa: BLE001 - 网络异常的提示要具体
        raise SystemExit(f"取 mermaid 失败（需要能访问 CDN）：{exc}") from exc
    if len(data) < 1_000_000 or b"mermaid" not in data[:200_000]:
        raise SystemExit("CDN 返回的不是 mermaid 脚本，检查网络/URL")
    return data.decode("utf-8")


def build_html(mmd: str, mermaid_js: str, total: int, crit_path: list[str]) -> str:
    title = "图 2 · 双代号网络图（AOA / 箭线图法 ADM）—— 对照附录"
    sub = (
        f"同一个系统的另一种画法：活动全在箭线上，圆圈只是事件 · 总工期 {total} 分钟<br/>"
        f"关键路径 {' → '.join(crit_path)}（橙色粗箭线，总浮动 0）"
    )
    legend = (
        "<b>圆圈</b> = 事件（e1–e10，事件不耗时） ｜ "
        "箭线 = 活动（线上标「活动编号 工期」，单位：分钟）<br/>"
        "<b>橙色粗箭线</b> = 关键路径（总浮动 0） ｜ "
        "灰色 = 非关键活动 A1、A2（总浮动各 22 分钟）<br/>"
        "实箭线 10 条、虚活动 0 条"
    )
    # mmd 原文里只有 <br/> 一种 HTML 标签，可直接放进 <pre>（mermaid 读 innerHTML）
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>flow-aoa</title>
<style>
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
body {{ display: inline-block; }}
.fig {{ padding: 18px 22px; font-family: {FONT_STACK}; color: #1a1a1a; }}
.fig-title {{ font-size: {FIG_TITLE_PX}px; font-weight: 600; line-height: 1.5; margin: 0 0 2px; }}
.fig-sub {{ font-size: {FIG_SMALL_PX}px; line-height: 1.65; color: #555; margin: 0 0 8px; }}
#holder svg {{ display: block; }}
.fig-legend {{ font-size: {FIG_SMALL_PX}px; line-height: 1.7; color: #444; margin: 10px 0 0; }}
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
  mermaid.initialize({json.dumps(MERMAID_CFG)});
  mermaid.run({{ querySelector: '.mermaid' }}).then(() => {{
    const r = document.querySelector('.fig').getBoundingClientRect();
    document.title = 'DIM ' + Math.ceil(r.width) + ' ' + Math.ceil(r.height);
  }}).catch((e) => {{ document.title = 'ERR ' + (e && e.message ? e.message : e); }});
</script>
</body></html>
"""


def chrome(args: list[str]) -> subprocess.CompletedProcess:
    cmd = ["google-chrome", "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars"]
    return subprocess.run(cmd + args, capture_output=True, text=True, timeout=240)


def measure(html: Path, work: Path) -> tuple[int, int, str]:
    proc = chrome([
        "--window-size=4000,2600",
        "--virtual-time-budget=20000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", html.as_uri(),
    ])
    m = re.search(r"<title>DIM (\d+) (\d+)</title>", proc.stdout)
    if not m:
        err = re.search(r"<title>ERR ([^<]*)</title>", proc.stdout)
        raise SystemExit(
            f"mermaid 渲染失败：{err.group(1) if err else (proc.stderr or proc.stdout)[-2000:]}")
    return int(m.group(1)), int(m.group(2)), proc.stdout


def screenshot(html: Path, png: Path, size: tuple[int, int], work: Path) -> None:
    png.unlink(missing_ok=True)
    proc = chrome([
        f"--window-size={size[0] + 4},{size[1] + 4}",
        "--force-device-scale-factor=2",
        "--virtual-time-budget=20000",
        f"--user-data-dir={work / 'chrome-shot'}",
        f"--screenshot={png}", html.as_uri(),
    ])
    if not png.exists() or png.stat().st_size == 0:
        raise SystemExit(f"chrome 截图失败：{(proc.stderr or proc.stdout)[-2000:]}")


def run_convert(args: list[str]) -> None:
    proc = subprocess.run(["convert"] + args, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise SystemExit("ImageMagick 失败：" + (proc.stderr or proc.stdout)[-2000:])


def identify(path: Path) -> tuple[int, int]:
    proc = subprocess.run(
        ["identify", "-format", "%w %h", str(path)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    w, h = proc.stdout.split()
    return int(w), int(h)


def trim_and_resize(raw: Path, out: Path, width: int, work: Path) -> tuple[int, int]:
    trimmed = work / "trim.png"
    run_convert([str(raw), "-trim", "+repage", str(trimmed)])
    inner = width - 2 * MARGIN
    run_convert([
        str(trimmed), "-resize", f"{inner}x",
        "-bordercolor", "#ffffff", "-border", str(MARGIN),
        str(out),
    ])
    return identify(out)


# ------------------------------------------------------------------ 3. 渲染后自检

def check_rendered_dom(dom: str, nodes: dict[str, int], edges: list[dict]) -> None:
    """从渲染后的 DOM 里核对：事件编号、活动标签、橙色/灰色 linkStyle 是否都真的画出来了。"""
    node_ids = set(re.findall(r"-flowchart-(e\d+)-\d+", dom))
    if node_ids != set(nodes):
        raise SystemExit(f"渲染出的 DOM 里事件节点 {sorted(node_ids)} 与图源 {sorted(nodes)} 不符")
    for nid in nodes:
        if f"-flowchart-{nid}-" not in dom:
            raise SystemExit(f"渲染出的 DOM 里找不到事件 {nid}")

    for e in edges:
        label = f"{e['act']} {e['dur']}"
        if label not in dom:
            raise SystemExit(f"渲染出的 DOM 里找不到箭线标签「{label}」")

    if "__e65100" not in dom:
        raise SystemExit("渲染出的 DOM 里没有橙色箭线（#e65100 的箭头标记缺失），linkStyle 没生效")
    if "__9aa0a6" not in dom:
        raise SystemExit("渲染出的 DOM 里没有灰色箭线（#9aa0a6 的箭头标记缺失），linkStyle 没生效")

    # 10 个事件 e1–e10 必须逐个出现在渲染结果里
    missing = [eid for eid in EXPECT_EVENTS if f"-flowchart-{eid}-" not in dom]
    if missing:
        raise SystemExit(f"图里缺少这些事件编号：{missing}")
    have_acts = [e["act"] for e in edges]
    if sorted(have_acts) != sorted(EXPECT_DUR):
        raise SystemExit(f"图里活动编号不全：{have_acts}")


def check_png(png: Path, width: int) -> tuple[int, int, int, int]:
    """检查 PNG 尺寸、四周留白、关键路径橙色与灰色箭线的像素是否真的存在。"""
    w, h = identify(png)
    if w != width:
        raise SystemExit(f"输出宽度 {w}px，不等于约定的 {width}px")
    if h < 120:
        raise SystemExit(f"输出高度异常（{h}px），图可能没渲染出来")

    try:
        from PIL import Image  # noqa: PLC0415 - Pillow 是可选的
    except ImportError:
        print("⚠ 没装 Pillow，跳过 PNG 像素自检（橙色/灰色箭线、留白）")
        return w, h, 0, 0

    im = Image.open(png).convert("RGB")
    if im.size != (w, h):
        raise SystemExit(f"PIL 读到的尺寸 {im.size} 与 identify 不一致")

    # 留白：补边后最外 3px 必须全白（说明 trim 没把内容裁掉）
    px = im.load()
    for x in range(w):
        for y in (0, 1, 2, h - 1, h - 2, h - 3):
            if px[x, y] != (255, 255, 255):
                raise SystemExit("PNG 上下边缘不是白色留白，trim/补边有问题")
    for y in range(h):
        for x in (0, 1, 2, w - 1, w - 2, w - 3):
            if px[x, y] != (255, 255, 255):
                raise SystemExit("PNG 左右边缘不是白色留白，trim/补边有问题")

    orange = gray = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r > 170 and 40 <= g <= 135 and b < 90:
                orange += 1
            elif 125 <= r <= 185 and 130 <= g <= 190 and 135 <= b <= 200 and abs(r - g) < 35:
                gray += 1
    if orange < 200:
        raise SystemExit(f"PNG 里几乎找不到橙色关键路径箭线（橙色采样点 {orange}）")
    if gray < 200:
        raise SystemExit(f"PNG 里几乎找不到灰色非关键箭线（灰色采样点 {gray}）")
    return w, h, orange, gray


def ocr_activity_labels(png: Path) -> list[str]:
    """OCR 旁证：识别 PNG 里的 ASCII 活动标签；装了 tesseract 才跑，不通过也不报错。"""
    exe = shutil.which("tesseract")
    if not exe:
        print("⚠ 没装 tesseract，跳过 OCR 旁证")
        return []
    try:
        proc = subprocess.run(
            [exe, str(png), "stdout", "-l", "eng", "--psm", "11",
             "-c", "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # noqa: BLE001
        print(f"⚠ OCR 跑不起来，跳过旁证：{exc}")
        return []
    found = sorted({tok for tok in re.findall(r"A[0-9OQDG]{1,2}", proc.stdout.upper())})
    return found


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="把 tutorial/flow-aoa.mmd 渲染成 tutorial/images/flow-aoa.png")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                    help=f"输出 PNG 宽度（默认 {DEFAULT_WIDTH}px）")
    ap.add_argument("--out", type=Path, default=OUT, help="输出 PNG 路径")
    args = ap.parse_args()
    if args.width < 700:
        raise SystemExit("--width 太小，网络图会看不清")

    text, body, nodes, edges = read_mmd()
    cpm = aoa_cpm(nodes, edges)
    check_styles(body, nodes, edges, cpm["rows"])
    print_table(cpm)

    print(f"🖼 渲染 {show(MMD)} → {show(args.out)}")
    with tempfile.TemporaryDirectory(prefix="aoa-render-") as tmp:
        work = Path(tmp)
        mermaid_js = fetch_mermaid()
        html = work / "flow-aoa.html"
        html.write_text(build_html(text, mermaid_js, cpm["total"], cpm["path"]),
                        encoding="utf-8")

        size = measure(html, work)
        print(f"   自然尺寸 {size[0]}x{size[1]}（1:1）")
        raw = work / "flow-aoa.raw.png"
        screenshot(html, raw, (size[0], size[1]), work)

        visible = re.sub(r"<script>.*?</script>", "", html.read_text(encoding="utf-8"),
                         flags=re.S)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        w, h = trim_and_resize(raw, args.out, args.width, work)

    check_rendered_dom(size[2], nodes, edges)
    print(f"✅ 编号自检：事件 e1–e10 共 {len(nodes)} 个圆圈全部在渲染结果里")
    print(f"✅ 活动自检：A0–A9 共 {len(edges)} 条箭线的「活动编号 工期」标签全部在渲染结果里")

    pw, ph, orange, gray = check_png(args.out, args.width)
    print(f"✅ PNG 自检：{pw}x{ph}px；橙色关键路径采样点 {orange}，灰色非关键采样点 {gray}；"
          f"四周留白正常")

    leaked = [p for p in FORBIDDEN if p in text + visible]
    if leaked:
        args.out.unlink(missing_ok=True)
        raise SystemExit(f"图里出现了不该有的信息：{leaked}")

    found = ocr_activity_labels(args.out)
    if found:
        print(f"ℹ OCR 旁证（eng，允许字符集）：识别到 {found}")
    print(f"🖼 完成 {show(args.out)}  {pw}x{ph}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
