#!/usr/bin/env python3
"""Assemble book/chapters/*.md into a single print-ready HTML file.

- Reads book/manifest.txt (one chapter path per line, relative to book/).
- Converts Markdown to HTML with tables, fenced code, and heading ids.
- Turns image paragraphs into <figure> with captions.
- Builds a TOC with real page numbers via CSS target-counter.
- Embeds diagrams as file:// SVGs so WeasyPrint can render them.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_all import render_mermaid  # noqa: E402
from status_icons import replace_status_markers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book"
CHAPTERS = BOOK / "chapters"
OUT_HTML = BOOK / "book.html"
MANIFEST = BOOK / "manifest.txt"

TITLE = "DSWS 从零到一"
SUBTITLE = "电商问数智能体 · 设计图集与开发手册"
VERSION = "v1.0"
BASELINE = "eea5e75"
DATE = "2026-10-29"

MD_EXTENSIONS = [
    "extra",          # tables, fenced_code, attr_list, md_in_html
    "toc",            # heading ids
    "sane_lists",
    "smarty",
]


def read_manifest() -> list[Path]:
    if not MANIFEST.exists():
        raise SystemExit(f"missing {MANIFEST}")
    files: list[Path] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path = (BOOK / line).resolve()
        if not path.exists():
            raise SystemExit(f"manifest entry missing: {path}")
        files.append(path)
    return files


def render_mermaid_blocks(text: str, chapter: Path) -> str:
    """Replace ```mermaid blocks with rendered SVG images (for the PDF)."""
    generated = BOOK / "generated"
    generated.mkdir(exist_ok=True)

    def repl(match: re.Match[str]) -> str:
        source = match.group(1).strip()
        caption = (match.group(2) or "").strip() or f"图 {chapter.stem}"
        index = len(list(generated.glob(f"{chapter.stem}-*.mmd"))) + 1
        stem = f"{chapter.stem}-{index:02d}"
        mmd = generated / f"{stem}.mmd"
        svg = generated / f"{stem}.svg"
        mmd.write_text(source + "\n", encoding="utf-8")
        ok, msg = render_mermaid(mmd, svg)
        if not ok:
            raise SystemExit(f"mermaid block render failed in {chapter.name}: {msg}")
        return f"![{caption}](../generated/{stem}.svg)"

    return re.sub(
        r"```mermaid\n(.*?)```[ \t]*\n(?:[ \t]*\*([^*\n]+)\*[ \t]*\n)?",
        repl,
        text,
        flags=re.S,
    )


def preprocess_images(text: str, chapter: Path) -> str:
    """![alt](relative) -> <figure><img src="file://..."><figcaption>alt</figcaption></figure>."""

    def repl(match: re.Match[str]) -> str:
        alt, src = match.group(1), match.group(2)
        src = src.strip()
        if src.startswith(("http://", "https://", "file://")):
            url = src
            target = None
        else:
            target = (chapter.parent / src).resolve()
            url = target.as_uri()
        alt_html = html.escape(alt, quote=True)
        cls = ""
        if target is not None and target.suffix.lower() == ".svg" and target.exists():
            head = target.read_text(encoding="utf-8", errors="ignore")[:4000]
            vb = re.search(r'viewBox="[\d.-]+ [\d.-]+ ([\d.]+) ([\d.]+)"', head)
            if vb:
                w, h = float(vb.group(1)), float(vb.group(2))
                if w / max(h, 1) > 1.55:
                    cls = ' class="wide"'
                elif h / max(w, 1) > 1.15:
                    cls = ' class="tall"'
        return (
            f'<figure{cls}><img src="{url}" alt="{alt_html}">'
            f'<figcaption>{html.escape(alt)}</figcaption></figure>'
        )

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, text)

    # Drop a duplicate italic caption immediately after a figure.
    text = re.sub(
        r"(</figure>)\s*\n+\s*\*([^*\n]{2,120})\*\s*\n",
        r"\1\n",
        text,
    )
    return text


def add_table_captions(html_text: str) -> str:
    """Paragraphs like '表 2-1 · ...' immediately before a table become captions."""
    pattern = re.compile(r"<p>(表\s*[\w\-.]+\s*·[^<]{0,160})</p>\s*(<table>)", re.S)

    def repl(m: re.Match[str]) -> str:
        return f'<p class="table-caption">{m.group(1)}</p>\n{m.group(2)}'

    return pattern.sub(repl, html_text)


def decorate_body(body: str) -> str:
    """Presentation-only markup for structures Markdown leaves as plain text.

    Nothing in the chapters changes: task syntax "[ ]" becomes a real checkbox,
    the review-question hint line becomes its own line, and the difficulty
    bracket 【易】/【中】/【难】 is wrapped so it can be set in small type.
    """
    body = re.sub(r"<li>\[ \] ", '<li class="task">', body)
    body = re.sub(
        r"\n[ \t]+(自检线索：[^\n]*?)(</li>)",
        r'<span class="hint">\1</span>\2',
        body,
    )
    body = re.sub(r"<li>【(易|中|难)】", r'<li><span class="diff">【\1】</span>', body)
    return body


def strip_tags(value: str) -> str:
    # 图标没有文字子节点，取 aria-label，目录里才不会剩下「： / / 」。
    def icon_label(m: re.Match[str]) -> str:
        label = re.search(r'aria-label="([^"]*)"', m.group(0))
        return label.group(1) if label else ""

    value = re.sub(r"<svg\b[^>]*>.*?</svg>", icon_label, value, flags=re.S)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def build_toc(body: str) -> str:
    """目录：部分名（lvl1）+ 小节名（lvl2），页码由 CSS target-counter 生成。"""
    headings = re.findall(r'<h([12])\s+id="([^"]+)"[^>]*>(.*?)</h\1>', body, re.S)
    items: list[str] = []
    for level, hid, label in headings:
        text = strip_tags(label)
        if not text or text in {"目录", "封面"}:
            continue
        cls = "lvl1" if level == "1" else "lvl2"
        items.append(
            f'<li class="{cls}"><a href="#{html.escape(hid, quote=True)}">{html.escape(text)}</a></li>'
        )
    return '<nav class="toc-wrap"><ul class="toc">' + "\n".join(items) + "</ul></nav>"


def cover_html() -> str:
    """封面：只有字、一条 30mm 竖线、纸色，没有图、没有色块。"""
    return f"""
<section class="cover">
  <div class="mark">DSWS</div>
  <div class="rule"></div>
  <div class="titleblock">
    <h1>DSWS<br>从零到一</h1>
    <p class="subtitle">电商问数智能体 · 设计图集与开发手册</p>
  </div>
  <div class="foot">
    <p class="line">32 张设计图 · S0–S8 全流程</p>
    <div class="hr"></div>
    <div class="meta">
      <span>baseline {BASELINE} · {DATE}</span>
      <span>{VERSION} · 教学与评审双用途</span>
    </div>
  </div>
</section>
"""


def main() -> int:
    chapters = read_manifest()
    pieces: list[str] = []
    for chapter in chapters:
        raw = chapter.read_text(encoding="utf-8")
        raw = render_mermaid_blocks(raw, chapter)
        raw = preprocess_images(raw, chapter)
        pieces.append(raw.strip())
    # Convert once so heading ids are unique across the whole book.
    body = markdown.markdown("\n\n".join(pieces), extensions=MD_EXTENSIONS, output_format="html5")
    body = add_table_captions(body)
    body = replace_status_markers(body)
    body = decorate_body(body)
    toc = build_toc(body)
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{html.escape(TITLE)} · {html.escape(SUBTITLE)}</title>
<link rel="stylesheet" href="book.css">
</head>
<body>
{cover_html()}
<section class="toc-page">
  <h1>目录</h1>
  {toc}
</section>
{body}
</body>
</html>
"""
    OUT_HTML.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT_HTML} ({len(chapters)} chapters, {len(doc):,} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
