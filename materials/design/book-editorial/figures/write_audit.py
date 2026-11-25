#!/usr/bin/env python3
"""Write the audit markdown and the pilot preview HTML.

Usage:
    python3 write_audit.py content/fig-3-0-three-silent-failures.json
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / "pilot"

GATE_MAP = {
    "spelling": ["spelling_manifest", "spelling_expected", "spelling_review"],
    "layout": ["layout_text_overlap", "layout_rect_overlap", "layout_bounds"],
    "color": ["color_palette", "color_cobalt", "color_rust", "color_forest", "color_tint"],
    "typography": [
        "typography_sizes",
        "typography_title",
        "typography_section",
        "typography_label",
        "typography_note",
        "typography_small",
    ],
    "uniqueness": ["uniqueness"],
    "style_card": ["color_palette", "typography_sizes"],
}

MANUAL_GATES = {
    "teaching_5s": "5 秒读懂：三盘都上了，但没有一盘能吃；每幕底部给出新系统的止损点。",
    "no_figure_needed": "删图门：§3 是 3 个小节 + 1 张表，读者要在脑内把三种失败并排比较；餐厅三幕用同一个故事把三种失败串起来，保留。",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path, limit: int = 8000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except FileNotFoundError:
        return "(missing)"


def gate_result(checks: dict, names: list[str]) -> tuple[str, str]:
    rows = [checks["by_name"][n] for n in names if n in checks["by_name"]]
    if not rows:
        return "manual", "no automated check"
    ok = all(r["pass"] for r in rows)
    parts = []
    for r in rows:
        if r["gate"] == "spelling_review":
            parts.append(r["evidence"])
        else:
            parts.append(f"{r['gate']}={r['pass']}")
    return ("pass" if ok else "fail"), "; ".join(parts)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: write_audit.py <content.json>", file=sys.stderr)
        return 2
    content_path = Path(sys.argv[1])
    data = json.loads(content_path.read_text(encoding="utf-8"))
    base = HERE / data["id"]
    checks = json.loads(Path(str(base) + ".checks.json").read_text(encoding="utf-8"))
    checks["by_name"] = {c["gate"]: c for c in checks["checks"]}
    review_path = Path(str(base) + "-review-flash.txt")
    if not review_path.is_file():
        review_path = Path(str(base) + "-review-hy4free.txt")
    review = read_text(review_path)
    ocr = read_text(review_path.with_name(review_path.stem + "-tesseract.txt"))
    review_label = read_text(Path(str(review_path) + ".model")).strip() or "review"
    manifest = json.loads(Path(str(base) + ".text-manifest.json").read_text(encoding="utf-8"))
    layout = json.loads(Path(str(base) + ".layout.json").read_text(encoding="utf-8"))

    # Spelling gate against the actual vision review. Whitespace is ignored
    # because the model may insert spaces after full-width punctuation.
    norm = lambda s: re.sub(r"\s+", "", s)
    review_norm = norm(review)
    missing_review = [s["text"] for s in manifest["strings"] if norm(s["text"]) not in review_norm]
    review_check = {
        "gate": "spelling_review",
        "pass": not missing_review,
        "evidence": f"{len(manifest['strings']) - len(missing_review)}/{len(manifest['strings'])} manifest strings found in {review_label} review; missing={missing_review[:5]}",
    }
    existing = checks["by_name"].get("spelling_review")
    if existing is not None:
        existing.update(review_check)
    else:
        checks["checks"].append(review_check)
        checks["by_name"]["spelling_review"] = review_check
    checks["all_pass"] = all(c["pass"] for c in checks["checks"])
    Path(str(base) + ".checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    png_rel = f"../figures/{data['id']}.png"
    md = []
    md.append(f"# {data['id']}\n")
    md.append(f"**{data['title']}**\n")
    md.append(f"_{data['subtitle']}_\n")

    md.append("## 1. 来源\n")
    ref = data["source_ref"]
    md.append(f"- 教材：*{ref['book_title']}*，{ref['chapter_title']}，{ref['section']}")
    md.append(f"- 原稿：`{ref['manuscript']}`，行 {ref['lines']}")
    md.append(f"- 代码/契约：{', '.join(f'`{p}`' for p in ref['code_refs'])}")
    md.append("- 旧书：`design/book/book.html` 与 `design/book/pdf/dsws-design-atlas.pdf`（本轮未重建）\n")

    md.append("## 2. 事实核对\n")
    md.append("| # | 事实 | 原文摘录（≤50 字） | 出处 | 核对 |")
    md.append("|---|---|---|---|---|")
    for i, fact in enumerate(data["facts"], 1):
        quote = fact["quote"].replace("|", "\\|")
        source = fact["source"].replace("|", "\\|")
        locator = fact["locator"].replace("|", "\\|")
        md.append(f"| {i} | {fact['text']} | “{quote}” | {source}<br>`{locator}` | {'✅' if fact['verified'] else '❌'} |")
    md.append("")

    md.append("## 3. 读图路径\n")
    for i, step in enumerate(data.get("reading_path", []), 1):
        md.append(f"{i}. {step}")
    md.append("")

    md.append("## 4. 风格卡\n")
    md.append(f"- 画布：{layout['width']}×{layout['height']}，纸色 `#FFFDF8`")
    md.append("- 墨色 `#111111`；次级 `#5B5B5B`；分隔线 `#D9D3C7`")
    md.append("- 钴蓝 `#1F4E9C`；锈红 `#B24A2E`；森林绿 `#2F5D46`；芥末 `#C58B1B`")
    md.append("- 字体：`Noto Sans CJK SC`；字号：42 / 30 / 26 / 24 / 22 / 18")
    md.append("- 三格漫画，每格：餐厅场景 → 用户看到 → 实际发生 → 新系统挡住")
    md.append("- 图注由书里的 `figcaption` 生成，图内不重复图号\n")

    md.append("## 5. 门禁\n")
    md.append("| 门 | 结果 | 证据 |")
    md.append("|---|---|---|")
    for gate, names in GATE_MAP.items():
        result, evidence = gate_result(checks, names)
        md.append(f"| {gate} | {result} | {evidence} |")
    for gate, note in MANUAL_GATES.items():
        md.append(f"| {gate} | manual | {note} |")
    md.append("")

    md.append(f"## 6. {review_label} 逐字复核\n")
    md.append("```text")
    md.append(review.strip() or "(empty)")
    md.append("```\n")
    md.append(f"_OCR 旁证：`{review_path.stem}-tesseract.txt`（本机 tesseract 仅装 eng，中文不可用，不参与门禁）。_\n")

    md.append("## 7. 版面验收\n")
    page_info_path = PILOT / "page-info.json"
    if page_info_path.exists():
        info = json.loads(page_info_path.read_text(encoding="utf-8"))
        md.append(f"- 新书 PDF：`design/book-editorial/pdf/dsws-design-editorial.pdf`（{info.get('new_pages', '?')} 页）")
        md.append(f"- §3 起始页：新书第 {info.get('new_section_page', '?')} 页；旧书第 {info.get('old_section_page', '?')} 页")
        md.append(f"- 改前页：`pilot/before-{info.get('old_section_page', '?')}.png`")
        md.append(f"- 改后页：`pilot/after-{info.get('new_section_page', '?')}.png`")
    else:
        md.append("- 待构建：新书 PDF 与改前/改后页图尚未生成。")
    md.append("")

    md.append("## 8. 产物\n")
    for suffix in (".svg", ".png", ".layout.json", ".text-manifest.json", ".checks.json"):
        path = Path(str(base) + suffix)
        if path.exists():
            md.append(f"- `{path.relative_to(HERE.parent)}` — sha256 `{sha256(path)}`")
    md.append("")

    md.append("## 9. 未决问题\n")
    if checks["all_pass"]:
        md.append("- 自动门禁全部通过；`teaching_5s` 与 `no_figure_needed` 待人工确认。")
    else:
        failed = [c["gate"] for c in checks["checks"] if not c["pass"]]
        md.append(f"- 自动门禁失败：{failed}。需修 content JSON 后重跑。")
    md.append("- 旧书 PDF 未重建；新书 PDF 的 §3 版面是本轮验收对象。")
    md.append("")

    md_path = Path(str(base) + ".md")
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Preview HTML
    PILOT.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, fact in enumerate(data["facts"], 1):
        rows.append(
            "<tr>"
            f"<td>{i}</td><td>{html.escape(fact['text'])}</td>"
            f"<td>“{html.escape(fact['quote'])}”</td>"
            f"<td>{html.escape(fact['source'])}<br><code>{html.escape(fact['locator'])}</code></td>"
            f"<td>{'✅' if fact['verified'] else '❌'}</td></tr>"
        )
    gate_rows = []
    for gate, names in GATE_MAP.items():
        result, evidence = gate_result(checks, names)
        gate_rows.append(f"<tr><td>{gate}</td><td class='{result}'>{result}</td><td>{html.escape(evidence)}</td></tr>")
    for gate, note in MANUAL_GATES.items():
        gate_rows.append(f"<tr><td>{gate}</td><td class='manual'>manual</td><td>{html.escape(note)}</td></tr>")

    page_info_path = PILOT / "page-info.json"
    page_block = ""
    if page_info_path.exists():
        info = json.loads(page_info_path.read_text(encoding="utf-8"))
        old_page = info.get("old_section_page")
        new_page = info.get("new_section_page")
        if old_page and new_page:
            page_block = f"""
  <h2>改前 / 改后</h2>
  <div class="compare">
    <figure><img src="before-{old_page}.png" alt="旧书第 {old_page} 页"><figcaption>旧书 · 第 {old_page} 页</figcaption></figure>
    <figure><img src="after-{new_page}.png" alt="新书第 {new_page} 页"><figcaption>新书 · 第 {new_page} 页</figcaption></figure>
  </div>
"""

    preview = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{html.escape(data['id'])} · pilot preview</title>
<style>
  :root {{ --paper:#FFFDF8; --ink:#111111; --ink2:#5B5B5B; --line:#D9D3C7; --cobalt:#1F4E9C; --rust:#B24A2E; --forest:#2F5D46; }}
  body {{ margin:0; background:#F1EDE4; color:var(--ink); font-family:"Noto Serif CJK SC",serif; }}
  main {{ max-width:1280px; margin:0 auto; padding:32px 24px 64px; }}
  h1 {{ font-size:30px; margin:0 0 6px; color:var(--ink); }}
  h2 {{ font-size:20px; margin:34px 0 12px; color:var(--cobalt); border-left:4px solid var(--cobalt); padding-left:10px; }}
  .sub {{ color:var(--ink2); margin-bottom:24px; }}
  img {{ width:100%; border:1px solid var(--line); border-radius:4px; background:var(--paper); }}
  .compare {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
  .compare figure {{ margin:0; }}
  .compare figcaption {{ font-size:13px; color:var(--ink2); margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--paper); border:1px solid var(--line); }}
  th, td {{ text-align:left; vertical-align:top; padding:10px 12px; border-bottom:1px solid #E9E3D7; font-size:13px; }}
  th {{ background:#F8F5ED; color:var(--cobalt); }}
  .pass {{ color:var(--forest); font-weight:700; }}
  .fail {{ color:var(--rust); font-weight:700; }}
  .manual {{ color:#9a6700; font-weight:700; }}
  pre {{ background:var(--paper); border:1px solid var(--line); border-radius:4px; padding:12px; white-space:pre-wrap; font-size:13px; }}
  .meta {{ color:var(--ink2); font-size:13px; }}
  code {{ font-family:"DejaVu Sans Mono",monospace; font-size:12px; }}
</style>
</head>
<body>
<main>
  <h1>{html.escape(data['title'])}</h1>
  <div class="sub">{html.escape(data['subtitle'])}</div>
  <img src="{png_rel}" alt="{html.escape(data['id'])}">
  <p class="meta">图：<code>figures/{html.escape(data['id'])}.png</code> · 审计：<code>figures/{html.escape(data['id'])}.md</code></p>
{page_block}
  <h2>事实核对</h2>
  <table><thead><tr><th>#</th><th>事实</th><th>原文摘录</th><th>出处</th><th>核对</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>

  <h2>门禁</h2>
  <table><thead><tr><th>门</th><th>结果</th><th>证据</th></tr></thead>
  <tbody>{''.join(gate_rows)}</tbody></table>

  <h2>hy4free 逐字复核</h2>
  <pre>{html.escape(review.strip() or '(empty)')}</pre>
</main>
</body>
</html>
"""
    html_path = PILOT / (data["id"] + "-preview.html")
    html_path.write_text(preview, encoding="utf-8")

    print(md_path)
    print(html_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
