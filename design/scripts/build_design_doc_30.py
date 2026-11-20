#!/usr/bin/env python3
"""构建精选版设计文档 design/design-doc-30.pdf（30 张图，一图一页）。

与 build_design_doc.py（78 页完整版）的区别：
- 读同一份 diagrams/reading-paths.json，但按「32 → 30 选图表」过滤，只保留 30 张；
- 一图一页（A4 横向）：图页只放 图号 / 图名 / 一句读图提示，不再生成「读图地图」页；
- 第 2 页是「精选目录 + 32→30 选图表」，含被删 2 张图的删除理由；
- 共 32 页 = 封面 1 + 选图说明 1 + 图页 30（PRD 要求 ≥30 页，本版落在 30–32 页内）。

用法（临时 venv；本机 design/style-lab/.venv 不存在）：
    uv venv /tmp/dd30 && uv pip install --python /tmp/dd30/bin/python weasyprint
    /tmp/dd30/bin/python design/scripts/build_design_doc_30.py

不改旧脚本、不改图源、不改 reading-paths.json；只写 design/design-doc-30.pdf。
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from weasyprint import HTML
except ImportError as exc:  # pragma: no cover - 只是给重跑的人一条明路
    raise SystemExit(
        "缺 WeasyPrint。先建临时 venv：\n"
        "  uv venv /tmp/dd30 && uv pip install --python /tmp/dd30/bin/python weasyprint\n"
        "  /tmp/dd30/bin/python design/scripts/build_design_doc_30.py"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]          # design/
OUT = ROOT / "design-doc-30.pdf"
DATA = ROOT / "diagrams" / "reading-paths.json"

# 32 → 30 选图表：只删 2 张。理由写进 PDF 第 2 页，也写进交付报告。
DELETE = {
    "03": "纯实现细节：文件级 import 关系，实现时看源码即可；架构层已有 02 容器图 / 04 前端文件树",
    "32": "证据台账类：✅/🟡/⚪ 状态清单属于过程证据而非设计内容；78 页完整版已收录",
}

# 保留 30 张，各给一句「覆盖点」，用于选图表里说明为什么留。
WHY_KEEP = {
    "01": "系统边界与外部依赖（必留）",
    "02": "容器 / 进程拓扑（必留）",
    "04": "前端真实现落点（React19+Tailwind）",
    "05": "S0→S8 重建策略",
    "06": "构建时 vs 查询时分离",
    "07": "一次问数全链路（必留）",
    "08": "S2 三存储写入顺序",
    "09": "S3 三存储召回与合并",
    "10": "NL2SQL 生成（必留）",
    "11": "SQL 安全校验 + 执行（必留）",
    "12": "自校验自纠错闭环（必留）",
    "13": "SSE 流式契约（前端重点）",
    "14": "数仓 5 表 grain / 主外键（必留）",
    "15": "契约对象与字段（必留）",
    "16": "契约→三存储映射（必留）",
    "17": "S2 数据血缘",
    "18": "5 张 Meta 表结构",
    "19": "值域决策（哪些列进 ES）",
    "20": "信任边界与攻击面（必留）",
    "21": "五层纵深防御",
    "22": "SQL 六关策略判定（必留）",
    "23": "dw_reader 只读账号（必留）",
    "24": "16 错误码 / 3 class（必留）",
    "25": "六服务 Compose 拓扑（必留）",
    "26": "宿主 / 容器端口暴露面",
    "27": "启动顺序与失败停点",
    "28": "旧系统隔离边界",
    "29": "五层测试金字塔（必留）",
    "30": "S0–S7 阶段门禁（必留）",
    "31": "失败注入矩阵（必留）",
}

# 图页布局预算（A4 横向：297 × 210mm，页边距 12/9/8mm）
BOX_W_MM = 273.0  # 内容宽
BOX_H_MM = 160.0  # 图最大高（给页眉 / 读图提示 / 页脚留余量）

CSS = """
@page {
  size: A4 landscape;
  margin: 9mm 12mm 8mm;
  @bottom-left { content: "DSWS 设计文档 · 精选 30 图 · 一图一页"; font-size: 7.5pt; color: #9a9188; }
  @bottom-right { content: counter(page); font-size: 9pt; color: #8a8178; }
}
@page cover { margin: 0; }

* { box-sizing: border-box; }
body { font-family: "Noto Sans CJK SC", "Noto Sans CJK JP", sans-serif; color: #1a1a1a; font-size: 10pt; line-height: 1.6; margin: 0; }

/* ---------- 封面 ---------- */
.cover { page: cover; width: 297mm; height: 210mm; padding: 24mm 26mm; background: #f8efe7; }
.cover .rule { width: 30mm; height: 5px; background: #b24a2e; margin-bottom: 9mm; }
.cover .kicker { color: #2f5d46; font-size: 11pt; letter-spacing: 1px; }
.cover h1 { font-size: 46pt; margin: 3mm 0 2mm; letter-spacing: 1px; line-height: 1.05; }
.cover .sub { font-size: 18pt; color: #5b5b5b; margin-bottom: 9mm; }
.cover .meta { font-size: 9.8pt; color: #5b5b5b; line-height: 1.85; }
.cover .meta b { color: #1a1a1a; }
.cover .badge { display: inline-block; margin-top: 7mm; padding: 2.4mm 6mm; background: #111; color: #fff; font-size: 10pt; }
.cover .route { margin-top: 7mm; padding: 3mm 5mm; background: #fff; border-left: 3px solid #2f5d46; font-size: 8.6pt; color: #5b5b5b; }
.cover .route b { color: #2f5d46; margin-right: 3mm; }
.cover .foot { margin-top: 5mm; font-size: 8pt; color: #8a8178; }

/* ---------- 第 2 页：精选目录 + 32→30 选图表 ---------- */
.toc { break-before: page; }
.toc .kicker { color: #2f5d46; font-size: 9pt; letter-spacing: 1px; }
.toc h2 { font-size: 19pt; margin: 1mm 0 2mm; }
.toc .lead { font-size: 8.3pt; color: #5b5b5b; margin: 0 0 3mm; line-height: 1.5; }
.toc h3 { font-size: 10pt; margin: 0 0 1mm; }
.toc table.sel { width: 49.3%; float: left; border-collapse: collapse; font-size: 7.8pt; line-height: 1.34; table-layout: fixed; }
.toc table.sel.r { float: right; }
.toc table.sel th { text-align: left; border-bottom: 1pt solid #1a1a1a; padding: 0.9mm 1mm; font-weight: 700; }
.toc table.sel td { border-bottom: 0.4pt solid #d9d3c7; padding: 0.9mm 1mm; vertical-align: top; }
.toc td.pg { color: #b24a2e; font-weight: 700; }
.toc td.track { color: #2f5d46; }
.toc td.keep { color: #15803d; font-weight: 700; text-align: center; }
.toc td.drop { color: #b91c1c; font-weight: 700; text-align: center; }
.toc tr.del td.reason { color: #b91c1c; }
.toc .note { clear: both; margin-top: 3mm; padding-top: 2mm; border-top: 1pt solid #1a1a1a; font-size: 7.7pt; color: #5b5b5b; line-height: 1.55; }
.toc .note b { color: #1a1a1a; }

/* ---------- 图页：一图一页 ---------- */
.fig { break-before: page; }
.fig-head { border-bottom: 1.5px solid #1a1a1a; padding-bottom: 2mm; line-height: 1.2; overflow: hidden; }
.fig-head .num { color: #b24a2e; font-weight: 700; font-size: 12pt; margin-right: 3mm; }
.fig-head h2 { display: inline; font-size: 16pt; margin: 0; }
.fig-head .track { float: right; color: #2f5d46; font-size: 8.5pt; border: 0.6pt solid #2f5d46; border-radius: 2mm; padding: 0.5mm 2.2mm; }
/* 图 + 一句读图提示在页眉下方剩余高度里垂直居中（按图高算上边距，窄长图不再全部挤在页顶） */
.fig img { display: block; margin: 0 auto; }
.fig .hint { text-align: center; color: #8a8178; font-size: 8.5pt; margin: 3mm 0 0; line-height: 1.45; }
.fig .hint b { color: #2f5d46; }
"""


def clean_title(title: str) -> tuple[str, str]:
    """'01 · C4-L1 系统上下文' → ('01', 'C4-L1 系统上下文')。"""
    m = re.match(r"(\d{2})\s*·\s*(.+)", title)
    return (m.group(1), m.group(2)) if m else ("", title)


def svg_natural_mm(path: Path) -> tuple[float, float]:
    """取 SVG 的固有尺寸（mm）。无单位按 CSS px（1/96in）换算。"""
    root = ET.parse(path).getroot()

    def to_mm(value: str) -> float:
        value = value.strip()
        for unit, factor in (("pt", 25.4 / 72), ("px", 25.4 / 96), ("mm", 1.0), ("cm", 10.0), ("in", 25.4)):
            if value.endswith(unit):
                return float(value[: -len(unit)]) * factor
        return float(value) * 25.4 / 96  # 无单位 = px

    w, h = root.get("width"), root.get("height")
    if w and h:
        return to_mm(w), to_mm(h)
    vb = root.get("viewBox")
    if vb:
        parts = [float(x) for x in vb.replace(",", " ").split()]
        if len(parts) == 4:
            return parts[2] * 25.4 / 96, parts[3] * 25.4 / 96
    raise ValueError(f"SVG 无尺寸：{path}")


def fig_size_mm(svg_path: Path) -> tuple[float, float]:
    """在 273 × 160mm 盒子里等比适配，不放大（放大只会暴露图源 viewBox 缺陷）。"""
    w, h = svg_natural_mm(svg_path)
    scale = min(BOX_W_MM / w, BOX_H_MM / h, 1.0)
    return round(w * scale, 1), round(h * scale, 1)


def fig_page(e: dict, page_no: int) -> str:
    num, title = clean_title(e["title"])
    hint = " → ".join(f"{i + 1} {p}" for i, p in enumerate(e["path"]))
    svg = ROOT / e["svg"]
    width, height = fig_size_mm(svg)
    # 垂直居中：页眉下可用 180mm，内容 = 图 + 3mm 间距 + 一句提示（约 4.4mm）
    pad = round(max(0.0, (180.0 - height - 7.5) / 2), 1)
    return f"""
<section class="fig">
  <div class="fig-head"><span class="num">图 {num or e['id']}</span><span class="track">{html.escape(e['track'])}</span><h2>{html.escape(title)}</h2></div>
  <img src="{html.escape(e['svg'])}" style="width:{width}mm; margin-top:{pad}mm">
  <p class="hint"><b>读图提示</b> · {html.escape(hint)}</p>
</section>"""


def sel_row(e: dict, page_no: int | None) -> str:
    num, title = clean_title(e["title"])
    track = html.escape(e["track"])
    if page_no is None:
        reason = html.escape(DELETE[e["id"]])
        return (
            f"<tr class='del'><td class='pg'>—</td><td>{num or e['id']}</td>"
            f"<td>{html.escape(title)}</td><td class='track'>{track}</td>"
            f"<td class='drop'>删</td><td class='reason'>{reason}</td></tr>"
        )
    reason = html.escape(WHY_KEEP[e["id"]])
    return (
        f"<tr><td class='pg'>{page_no}</td><td>{num or e['id']}</td>"
        f"<td>{html.escape(title)}</td><td class='track'>{track}</td>"
        f"<td class='keep'>留</td><td class='reason'>{reason}</td></tr>"
    )


def sel_table(rows: list[str], right: bool) -> str:
    return f"""
<table class="sel{' r' if right else ''}">
  <colgroup><col style="width:7%"><col style="width:5.5%"><col style="width:41%"><col style="width:9%"><col style="width:7%"><col style="width:30.5%"></colgroup>
  <thead><tr><th>页</th><th>#</th><th>图名</th><th>层级</th><th>留/删</th><th>覆盖点 / 删除理由</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""


def main() -> int:
    entries = json.loads(DATA.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in entries}
    if len(entries) != 32 or set(by_id) != set(WHY_KEEP) | set(DELETE):
        raise SystemExit(f"选图表与 reading-paths.json 不一致：{len(entries)} 条")
    if set(WHY_KEEP) & set(DELETE):
        raise SystemExit("同一张图不能既留又删")

    kept = [e for e in entries if e["id"] not in DELETE]
    kept_pages = {e["id"]: 3 + i for i, e in enumerate(kept)}  # 封面=1，选图页=2，图页从 3 起
    if len(kept) != 30:  # 硬约束：30 图 + 封面 + 选图页 = 32 页 ∈ [30, 32]
        raise SystemExit(f"期望保留 30 张，实际 {len(kept)}")

    rows = [sel_row(e, kept_pages.get(e["id"])) for e in entries]
    toc_page = f"""
<section class="toc">
  <div class="kicker">DESIGN LAB · 精选版</div>
  <h2>精选目录 · 32 图选 30</h2>
  <p class="lead">页 3–32 每页一张图，页脚为真实页码；图页只留「图号 + 图名 + 一句读图提示」，不再有读图地图页。
  选图原则：PRD 重点图必留（NL2SQL / LangGraph 运行时 / 自校验自纠错 / React 19 + Tailwind 前端），
  其余按「架构 → 运行时 → 数据 → 安全 → 部署 → 测试」每层保留代表图；只删 2 张，理由见下表红字。</p>
  {sel_table(rows[:16], right=False)}
  {sel_table(rows[16:], right=True)}
  <div class="note">
    <b>页数口径</b>：封面 1 + 本页 1 + 图页 30 = <b>32 页</b>，满足 PRD「设计文档 ≥30 页」，且不超 32 页上限。
    原版 <b>design/design-doc.pdf</b> 78 页 = 1 封面 + 3 目录 + 32 图页 + 42 读图地图页；本版去掉地图页、删 2 图，信息密度更高、每页更聚焦。
    被删的 03 / 32 仍可在 78 页完整版与 <b>diagrams/</b> 图源中追溯，不影响设计信息完整性。
  </div>
</section>"""

    cover = f"""
<section class="cover">
  <div class="rule"></div>
  <div class="kicker">DSWS · 电商问数智能体</div>
  <h1>设计文档</h1>
  <div class="sub">精选 30 图 · 一图一页</div>
  <div class="meta">
    读者：评审者、实现者、后续维护者<br>
    范围：架构 / 运行时 / 数据 / 安全 / 部署 / 测试；PRD 重点 = NL2SQL · LangGraph 12 节点 · SQL 自校验自纠错 · React 19 + Tailwind<br>
    口径：从 78 页完整版（32 图 + 每图读图地图）精选 30 张图，去掉地图页，每图配一句读图提示<br>
    读法：先看第 2 页「32→30 选图表」，再按图号顺序一图一页读；页脚为真实页码<br>
    版本：2026-11-20
  </div>
  <div class="badge">30 图 · 32 页 · 一图一页 · 一图一句读图提示</div>
  <div class="route"><b>推荐阅读路线</b>01 / 02 系统边界 → 06 构建时 vs 查询时 → 07 端到端 → 10–13 生成 / 校验 / 纠错 / SSE → 14–16 数据与契约 → 20–24 安全 → 25–28 部署 → 29–31 测试</div>
  <div class="foot">完整版（78 页，含读图地图）：design/design-doc.pdf · 图源：design/diagrams/</div>
</section>"""

    fig_pages = "".join(fig_page(e, kept_pages[e["id"]]) for e in kept)

    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>DSWS 设计文档 · 精选 30 图 · 一图一页</title>
<meta name="author" content="DSWS 设计工作树">
<meta name="description" content="从 78 页完整版精选 30 张设计图，一图一页；32→30 选图表与删除理由见第 2 页。">
<meta name="keywords" content="DSWS, NL2SQL, LangGraph, 设计文档, 精选版">
<meta name="dcterms.created" content="2026-11-20">
<style>{CSS}</style></head><body>
{cover}
{toc_page}
{fig_pages}
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc_obj = HTML(string=doc, base_url=str(ROOT)).render()
    doc_obj.write_pdf(str(OUT), optimize_images=True, pdf_version="1.7")

    expected = 2 + len(kept)
    pages = len(doc_obj.pages)
    print(f"wrote {OUT} · {pages} pages（期望 {expected}）· {OUT.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"选图表：32 图 → 留 {len(kept)} / 删 {len(DELETE)}；页数 = 封面 1 + 选图页 1 + 图页 {len(kept)} = {expected}")
    for e in kept:
        print(f"  p{kept_pages[e['id']]:>2}  图 {e['id']}  {clean_title(e['title'])[1]}")
    if pages != expected:
        print(f"WARNING 页数不符：{pages} != {expected}（内容溢出，需缩版面）")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
