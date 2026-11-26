#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_flow.py —— 把练本总览图 `tutorial/flow.mmd` 渲染成 `tutorial/images/flow-aon.png`。

一条命令重跑（在仓库根目录）：

    python3 tutorial/shots/render_flow.py

它做四件事：

1. **核对**：读 `tutorial/flow.mmd`，用图里的工期和 FS 箭头重算一遍 CPM
   （正推 ES/EF、逆推 LS/LF），与节点里写的数值逐项比对；对不上就报错退出。
   顺带核对：10 个活动 A0–A9、每条箭头都标 `FS`、关键路径的 `class ... critical`
   与「总浮动 = 0」的集合一致、不出现「验证」节点。
2. **渲染**：把 mermaid@11（CDN，`https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js`）
   内联进临时 HTML，用 google-chrome 无头浏览器跑出 SVG。
3. **截图**：`--dump-dom` 读回 SVG 的自然尺寸 → 按该尺寸 `--screenshot`
   （`--force-device-scale-factor=2` 超采样，保证缩到目标宽度后文字仍清晰）。
4. **落盘**：`convert -trim` 裁掉白边 → 缩到约定宽度（默认 1100px，与练本其它截图
   同宽）→ 四周补白边 → 校验最终宽度和「不含用户名/绝对路径」→ 写 PNG。

依赖：本机已有的 python3 / google-chrome / ImageMagick(convert)，能访问 CDN。
不新增依赖，不改 `term_render.py` / `web_shots.py` / `prep_render.py`。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent      # tutorial/shots
REPO = HERE.parents[1]                      # 仓库根目录
MMD = REPO / "manual" / "flow.mmd"
OUT = REPO / "manual" / "images" / "flow-aon.png"

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
DEFAULT_WIDTH = 1100   # 与 tutorial/shots/term_render.py 的 WINDOW_W 一致
MARGIN = 16            # 最终 PNG 四周留白（px）
FORBIDDEN = ["/home/", "/Users/", "/tmp/", "zhensirong", "root@", ".dsh"]

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
        "wrappingWidth": 600,   # 不自动折行；节点内换行全部由 <br/> 控制
        "nodeSpacing": 16,
        "rankSpacing": 18,
        "padding": 6,   # 节点内文字与边框的呼吸；太小会贴边
        "diagramPadding": 4,
    },
    "themeVariables": {"fontSize": "22px"},
}

# 图注/图例字号（px，按 mermaid 字号等比放大，缩小到目标宽度后仍与节点文字同量级）
FIG_TITLE_PX = 30
FIG_SMALL_PX = 22

FONT_STACK = "Noto Sans CJK SC,Source Han Sans SC,Microsoft YaHei,sans-serif"


# ------------------------------------------------------------------ 1. 读 + 核对

def show(path: Path) -> str:
    """给日志用：仓库内文件显示相对路径，仓库外显示原路径。"""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def read_mmd() -> tuple[str, dict, list[tuple[str, str]], dict]:
    """读 flow.mmd，返回 (原文, 节点标签, 箭头, class 定义)。"""
    text = MMD.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("%%")]
    body = "\n".join(lines)

    if not re.search(r"^flowchart\s+LR\s*$", body, re.M):
        raise SystemExit(f"{MMD} 必须以 `flowchart LR` 声明（单代号网络图从左到右排）")

    nodes: dict[str, str] = {}
    for m in re.finditer(r'^\s*([A-Za-z]\w*)\["(.*)"\]\s*$', body, re.M):
        nodes[m.group(1)] = m.group(2)
    if list(nodes) != [f"A{i}" for i in range(10)]:
        raise SystemExit(f"节点必须恰好是 A0–A9 十个构建活动，实际读到：{list(nodes)}")

    edges: list[tuple[str, str]] = []
    for m in re.finditer(r"^\s*([A-Za-z]\w*)\s*-->(?:\|([^|]*)\|)?\s*([A-Za-z]\w*)\s*$", body, re.M):
        if (m.group(2) or "").strip() != "FS":
            raise SystemExit(f"箭头 {m.group(1)}→{m.group(3)} 没有标 FS（本图只用完成-开始关系）")
        edges.append((m.group(1), m.group(3)))

    classes: dict[str, list[str]] = {}
    for m in re.finditer(r"^\s*class[ \t]+([\w, \t]+?)[ \t]+(critical|normal)[ \t]*$", body, re.M):
        classes[m.group(2)] = [x.strip() for x in m.group(1).split(",") if x.strip()]
    return text, nodes, edges, classes


def cpm(nodes: dict[str, str], edges: list[tuple[str, str]]):
    """按 mmd 里的工期和 FS 箭头独立重算 CPM（Kahn 拓扑序正推 + 逆推）。"""
    dur = {}
    for nid, label in nodes.items():
        m = re.search(r"工期\s*(\d+)", label)
        if not m:
            raise SystemExit(f"{nid} 的节点里没有「工期 N」")
        dur[nid] = int(m.group(1))

    succ: dict[str, list[str]] = {n: [] for n in nodes}
    pred: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
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
        raise SystemExit("网络图有环，不是合法 AON")

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

    # 关键路径：从无紧前的活动出发，沿「紧后且总浮动为 0」一直走到终点
    starts = [n for n in topo if not pred[n]]
    path = [starts[0]]
    while True:
        nxt = [s for s in succ[path[-1]] if TF[s] == 0]
        if not nxt:
            break
        if len(nxt) > 1:
            raise SystemExit(f"关键路径在 {path[-1]} 分叉，图里需要人工确认")
        path.append(nxt[0])
    if EF[path[-1]] != T:
        raise SystemExit("关键路径没有走到工期终点，检查 mmd")
    return dur, ES, EF, LS, LF, TF, T, path


def check_against_mmd(nodes: dict[str, str], edges: list[tuple[str, str]],
                      classes: dict[str, list[str]]):
    dur, ES, EF, LS, LF, TF, T, path = cpm(nodes, edges)
    for nid, label in nodes.items():
        m = re.search(r"ES(\d+)\s+EF(\d+)\s+LS(\d+)\s+LF(\d+)", label)
        if not m:
            raise SystemExit(f"{nid} 的节点里没有「ES.. EF.. LS.. LF..」")
        got = tuple(int(x) for x in m.groups())
        want = (ES[nid], EF[nid], LS[nid], LF[nid])
        if got != want:
            raise SystemExit(f"{nid} 的 CPM 数值与重算不符：mmd 写 {got}，重算 {want}")
    crit_written = set(classes.get("critical", []))
    crit_computed = {n for n in nodes if TF[n] == 0}
    if crit_written != crit_computed:
        raise SystemExit(f"class critical 与总浮动=0 的集合不符：mmd {sorted(crit_written)} vs 重算 {sorted(crit_computed)}")
    if "验证" in "".join(nodes.values()):
        raise SystemExit("节点里出现了「验证」—— 验证只能是完成判据，不能单独成节点")

    print(f"✅ CPM 核对通过：总工期 {T} 分钟；关键路径 {' → '.join(path)}")
    print(f"{'编号':<4}{'工期':>4}{'ES':>4}{'EF':>4}{'LS':>4}{'LF':>4}{'总浮动':>6}  关键")
    for nid in nodes:
        print(f"{nid:<4}{dur[nid]:>6}{ES[nid]:>6}{EF[nid]:>6}{LS[nid]:>6}{LF[nid]:>6}{TF[nid]:>8}  {'★' if TF[nid] == 0 else ''}")
    return T, path


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
    title = "图 1 · 单代号网络图（AON / 紧前关系法 PDM）"
    sub = (
        f"十个构建活动 · 总工期 {total} 分钟 · "
        f"关键路径 {' → '.join(crit_path)}（总浮动 0）"
    )
    legend = (
        "<b>橙色粗框 / 粗箭头</b> = 关键路径（总浮动 0） ｜ "
        "箭头上的 <b>FS</b> = 完成–开始紧前关系（紧前做完，紧后才开始）<br/>"
        "节点内：编号 + 活动名 / 工期 / ES EF LS LF / 完成判据（看到它才算这个活动做完）<br/>"
        "验证 = 完成判据，不单独成节点 ｜ 工期与 ES/EF/LS/LF 单位：分钟"
    )
    # mmd 原文里只有 <br/> 一种 HTML 标签，可直接放进 <pre>（mermaid 读 innerHTML）
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>flow</title>
<style>
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
body {{ display: inline-block; }}
.fig {{ padding: 18px 22px; font-family: {FONT_STACK}; color: #1a1a1a; }}
.fig-title {{ font-size: {FIG_TITLE_PX}px; font-weight: 600; line-height: 1.5; margin: 0 0 2px; }}
.fig-sub {{ font-size: {FIG_SMALL_PX}px; line-height: 1.6; color: #555; margin: 0 0 10px; }}
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


def measure(html: Path, work: Path) -> tuple[int, int]:
    proc = chrome([
        "--window-size=4000,2600",
        "--virtual-time-budget=20000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", html.as_uri(),
    ])
    m = re.search(r"<title>DIM (\d+) (\d+)</title>", proc.stdout)
    if not m:
        err = re.search(r"<title>ERR ([^<]*)</title>", proc.stdout)
        raise SystemExit(f"mermaid 渲染失败：{err.group(1) if err else (proc.stderr or proc.stdout)[-2000:]}")
    return int(m.group(1)), int(m.group(2))


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
    cw, ch = identify(trimmed)
    inner = width - 2 * MARGIN
    run_convert([
        str(trimmed), "-resize", f"{inner}x",
        "-bordercolor", "#ffffff", "-border", str(MARGIN),
        str(out),
    ])
    return identify(out)


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description="把 tutorial/flow.mmd 渲染成 tutorial/images/flow-aon.png")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                    help=f"输出 PNG 宽度（默认 {DEFAULT_WIDTH}px；答辩投影可用 1400）")
    ap.add_argument("--out", type=Path, default=OUT, help="输出 PNG 路径")
    args = ap.parse_args()
    if args.width < 700:
        raise SystemExit("--width 太小，8 列网络图会看不清")

    text, nodes, edges, classes = read_mmd()
    total, crit_path = check_against_mmd(nodes, edges, classes)

    print(f"🖼 渲染 {show(MMD)} → {show(args.out)}")
    with tempfile.TemporaryDirectory(prefix="flow-render-") as tmp:
        work = Path(tmp)
        mermaid_js = fetch_mermaid()
        html = work / "flow.html"
        html.write_text(build_html(text, mermaid_js, total, crit_path), encoding="utf-8")

        size = measure(html, work)
        print(f"   自然尺寸 {size[0]}x{size[1]}（1:1）")
        raw = work / "flow.raw.png"
        screenshot(html, raw, size, work)

        visible = re.sub(r"<script>.*?</script>", "", html.read_text(encoding="utf-8"),
                         flags=re.S)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        w, h = trim_and_resize(raw, args.out, args.width, work)

    if w != args.width:
        raise SystemExit(f"输出宽度 {w}px，不等于约定的 {args.width}px")
    leaked = [p for p in FORBIDDEN if p in text + visible]
    if leaked:
        args.out.unlink(missing_ok=True)
        raise SystemExit(f"图里出现了不该有的信息：{leaked}")
    print(f"🖼 完成 {show(args.out)}  {w}x{h}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
