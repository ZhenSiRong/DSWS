#!/usr/bin/env python3
"""构建独立的设计文档 design/design-doc.pdf。

结构：封面 → 32 张图的地图目录 → 每张图两页（图页 + 地图页）。

用法（需要 WeasyPrint 的 venv）：
    design/style-lab/.venv/bin/python design/scripts/build_design_doc.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import markdown
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design-doc.pdf"
DATA = ROOT / "diagrams" / "reading-paths.json"

CSS = """
@page {
  size: A4 portrait;
  margin: 18mm 16mm 16mm;
  @bottom-center { content: counter(page); font-size: 9pt; color: #8a8178; }
}
@page landscape { size: A4 landscape; margin: 10mm 12mm 12mm; }
@page cover { size: A4 portrait; margin: 0; }

* { box-sizing: border-box; }
body { font-family: "Noto Sans CJK SC", sans-serif; color: #1a1a1a; font-size: 10pt; line-height: 1.65; }

.cover { page: cover; height: 297mm; padding: 34mm 28mm; background: #f8efe7; }
.cover .rule { width: 34mm; height: 6px; background: #b24a2e; margin-bottom: 12mm; }
.cover .kicker { color: #2f5d46; font-size: 12pt; letter-spacing: 1px; }
.cover h1 { font-size: 40pt; margin: 6mm 0 4mm; letter-spacing: 1px; }
.cover .sub { font-size: 15pt; color: #5b5b5b; margin-bottom: 14mm; }
.cover .meta { font-size: 10.5pt; color: #5b5b5b; line-height: 2; }
.cover .badge { display: inline-block; margin-top: 18mm; padding: 3mm 6mm; background: #111; color: #fff; font-size: 10pt; }

.toc { break-before: page; }
.toc h2 { font-size: 22pt; margin: 0 0 6mm; }
.toc p.lead { color: #5b5b5b; margin-bottom: 6mm; }
.toc table { width: 100%; border-collapse: collapse; font-size: 8.4pt; }
.toc th { text-align: left; border-bottom: 1.5px solid #1a1a1a; padding: 2mm 1.5mm; }
.toc td { border-bottom: 0.5px solid #d9d3c7; padding: 1.6mm 1.5mm; vertical-align: top; }
.toc td.n { color: #b24a2e; font-weight: 700; width: 8mm; }
.toc td.path { color: #5b5b5b; width: 62mm; }

.diagram { page: landscape; break-before: page; }
.diagram .fig-head { display: flex; align-items: baseline; gap: 4mm; border-bottom: 1.5px solid #1a1a1a; padding-bottom: 2mm; }
.diagram .num { color: #b24a2e; font-weight: 700; font-size: 12pt; white-space: nowrap; }
.diagram h2 { font-size: 16pt; margin: 0; }
.diagram img { display: block; max-width: 100%; max-height: 162mm; margin: 6mm auto 0; }
.diagram .hint { text-align: center; color: #8a8178; font-size: 8.5pt; margin-top: 2mm; }

.map { break-before: page; }
.map .num { color: #b24a2e; font-weight: 700; font-size: 10pt; }
.map h2 { font-size: 20pt; margin: 1mm 0 5mm; }
.map .one { font-size: 11pt; background: #f8f5ed; border-left: 4px solid #2f5d46; padding: 3mm 4mm; margin: 0 0 4mm; }
.map .q { font-size: 10.5pt; margin: 0 0 4mm; }
.map .path { background: #e7edf8; padding: 3mm 4mm; margin: 0 0 4mm; }
.map .path ol { margin: 1mm 0 0 4mm; padding: 0; }
.map .path li { margin: 0.6mm 0; }
.map .fail { color: #b24a2e; font-size: 9.5pt; margin: 0 0 5mm; }
.map .body { column-count: 2; column-gap: 8mm; font-size: 8.8pt; line-height: 1.6; }
.map .body h1, .map .body h2 { font-size: 11pt; margin: 3mm 0 1.5mm; break-after: avoid; }
.map .body h3 { font-size: 9.8pt; margin: 2mm 0 1mm; break-after: avoid; }
.map .body p { margin: 0 0 2mm; }
.map .body table { width: 100%; border-collapse: collapse; font-size: 8pt; margin: 2mm 0; }
.map .body th, .map .body td { border: 0.5px solid #d9d3c7; padding: 1mm 1.5mm; vertical-align: top; }
.map .body code { background: #f1ece3; padding: 0 1mm; font-size: 8pt; }
.map .body pre { background: #111; color: #f8f5ed; padding: 2mm 3mm; font-size: 7.6pt; white-space: pre-wrap; break-inside: avoid; }
"""


def clean_title(title: str) -> tuple[str, str]:
    m = re.match(r"(\d{2})\s*·\s*(.+)", title)
    return (m.group(1), m.group(2)) if m else ("", title)


def body_html(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    lines = [
        ln for ln in text.splitlines()
        if not ln.startswith("# ")
        and not re.match(r"\*\*一句话", ln)
        and not re.match(r"\*\*这张图回答", ln)
    ]
    return markdown.markdown("\n".join(lines), extensions=["tables", "fenced_code"])


def main() -> int:
    entries = json.loads(DATA.read_text(encoding="utf-8"))

    toc_rows = []
    for e in entries:
        num, title = clean_title(e["title"])
        q = e["question"] or e["one_liner"]
        path = " → ".join(f"{i + 1} {p}" for i, p in enumerate(e["path"]))
        toc_rows.append(
            f"<tr><td class='n'>{num or e['id']}</td><td><strong>{html.escape(title)}</strong><br>"
            f"<span style='color:#5b5b5b'>{html.escape(q)}</span></td>"
            f"<td class='path'>{html.escape(path)}</td></tr>"
        )

    sections = []
    for e in entries:
        num, title = clean_title(e["title"])
        path_items = "".join(f"<li>{html.escape(p)}</li>" for p in e["path"])
        sections.append(f"""
<section class="diagram">
  <div class="fig-head"><span class="num">图 {num or e['id']}</span><h2>{html.escape(title)}</h2></div>
  <img src="{e['svg']}">
  <p class="hint">{html.escape(e['track'])} · 读图说明见下一页</p>
</section>
<section class="map">
  <span class="num">图 {num or e['id']} · {html.escape(e['track'])}</span>
  <h2>{html.escape(title)}</h2>
  <p class="one">{html.escape(e['one_liner'])}</p>
  <p class="q"><strong>这张图回答：</strong>{html.escape(e['question'])}</p>
  <div class="path"><strong>读图 1→2→3</strong><ol>{path_items}</ol></div>
  <p class="fail">{html.escape(e['failure'])}</p>
  <div class="body">{body_html(ROOT / e['md'])}</div>
</section>""")

    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>DSWS 设计文档 · 32 张图与读图地图</title><style>{CSS}</style></head><body>
<section class="cover">
  <div class="rule"></div>
  <div class="kicker">DSWS · 电商问数智能体</div>
  <h1>设计文档</h1>
  <div class="sub">32 张图 + 每张图的读图地图</div>
  <div class="meta">
    读者：评审者、实现者、后续维护者<br>
    内容：系统边界、运行时、数据、安全、部署、测试<br>
    版本：2026-11-09
  </div>
  <div class="badge">一图一页 · 一图一地图</div>
</section>
<section class="toc">
  <h2>地图目录</h2>
  <p class="lead">先读这张表：每张图回答一个问题，按 3 步读。正文按图号顺序排列。</p>
  <table><thead><tr><th>#</th><th>图与它回答的问题</th><th>读图 1→2→3</th></tr></thead>
  <tbody>{''.join(toc_rows)}</tbody></table>
</section>
{''.join(sections)}
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc_obj = HTML(string=doc, base_url=str(ROOT)).render()
    doc_obj.write_pdf(str(OUT), optimize_images=True, pdf_version="1.7")
    print(f"wrote {OUT} · {len(doc_obj.pages)} pages · {OUT.stat().st_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
