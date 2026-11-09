#!/usr/bin/env python3
"""Assemble book/chapters/*.md into a single print-ready HTML file.

- Reads book/manifest.txt (one chapter path per line, relative to book/).
- Converts Markdown to HTML with tables, fenced code, and heading ids.
- Turns image paragraphs into <figure> with captions.
- Builds a TOC with real page numbers via CSS target-counter.
- Embeds diagrams as file:// SVGs so WeasyPrint can render them.

风格 05「工程蓝图」：封面与目录由 cover_html() / build_toc() 生成；
正文标题上的图号（data-sheet）按「阶段号即图号」的规则计算，不随页码自增。
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
DRAWING_NO = "DSWS-DA-01"
COVER_FIGURE = ROOT / "diagrams" / "01-architecture" / "05-stage-evolution.svg"

FENCE = "```"

MD_EXTENSIONS = [
    "extra",          # tables, fenced_code, attr_list, md_in_html
    "toc",            # heading ids
    "sane_lists",
    "smarty",
]

# 阶段号：标题写成 "1. S5 · 安全边界" 时，图号就是 05，不随页码自增。
# 只认 "S<n> ·" 这种章节名，避免把 "4. S0–S8 地图" 误判成阶段 S0。
STAGE_RE = re.compile(r"S(\d)\s*·")
PART_RE = re.compile(r"第([一二三四五六七八九十]+)部分")
CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def part_number(text: str, fallback: int) -> int:
    """从「第三部分 · …」里取回部分号，取不到就用出现顺序。"""
    m = PART_RE.search(text)
    if not m:
        return fallback
    raw = m.group(1)
    if raw == "十":
        return 10
    if "十" in raw:
        tens, _, ones = raw.partition("十")
        return (CN_DIGITS.get(tens, 1) if tens else 1) * 10 + (CN_DIGITS.get(ones, 0) if ones else 0)
    return CN_DIGITS.get(raw, fallback)
HEAD_RE = re.compile(r"<h([12])\b([^>]*)>(.*?)</h\1>", re.S)
ID_RE = re.compile(r'id="([^"]+)"')
NUMERIC_CELL_RE = re.compile(r"<td>([^<]{1,16})</td>")


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
        FENCE + r"mermaid\n(.*?)" + FENCE + r"[ \t]*\n(?:[ \t]*\*([^*\n]+)\*[ \t]*\n)?",
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
                if w / max(h, 1) > 2.2:
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
    pattern = re.compile(r"<p>(表\s*[\w\-.]+[^<]{0,160})</p>\s*(<table>)", re.S)

    def repl(m: re.Match[str]) -> str:
        return f'<p class="table-caption">{m.group(1)}</p>\n{m.group(2)}'

    return pattern.sub(repl, html_text)


def strip_tags(value: str) -> str:
    # 图标没有文字子节点，取 aria-label，目录里才不会剩下「： / / 」。
    def icon_label(m: re.Match[str]) -> str:
        label = re.search(r'aria-label="([^"]*)"', m.group(0))
        return label.group(1) if label else ""

    value = re.sub(r"<svg\b[^>]*>.*?</svg>", icon_label, value, flags=re.S)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


# ---------------------------------------------------------------- 图号 / 标注


def annotate_html(body: str) -> tuple[str, list[dict]]:
    """给 h1/h2 打上图号，并把图号、表号、数字单元格包成可排版的片段。

    图号规则（工程图纸编号，不看页码）：
      - 标题里出现 S<n> 的章节   -> 0<n>            （S5 -> [05]，S6 -> [06]）
      - 第一部分（前言）的章节   -> 00.<序号>        （00.1 … 00.7）
      - 其余章节                -> 接续上一个阶段号  （04、09、10）
    """
    matches = list(HEAD_RE.finditer(body))
    items: list[dict] = []
    part = 1
    seen = 0

    for m in matches:
        level = int(m.group(1))
        attrs, inner = m.group(2), m.group(3)
        text = strip_tags(inner)
        idm = ID_RE.search(attrs)
        hid = idm.group(1) if idm else ""
        if level == 1:
            seen += 1
            part = part_number(text, seen)
            items.append(
                {"level": 1, "part": part, "sheet": "", "range": "", "text": text,
                 "id": hid, "attrs": attrs, "inner": inner, "stage_no": 0}
            )
            continue
        stage = STAGE_RE.search(text)
        items.append(
            {"level": 2, "part": part, "sheet": "", "range": "", "text": text,
             "id": hid, "attrs": attrs, "inner": inner,
             "stage_no": int(stage.group(1)) if stage else 0}
        )

    # 图号分配：阶段章节 = 阶段号；前言 = 00.<序号>；其余接续上一个阶段号。
    groups: dict[int, list[dict]] = {}
    for it in items:
        groups.setdefault(it["part"], []).append(it)

    cursor = 0
    for pnum in sorted(groups):
        chapters = [x for x in groups[pnum] if x["level"] == 2]
        stages = [x["stage_no"] for x in chapters if x["stage_no"]]
        if not stages and pnum == 1:
            for k, it in enumerate(chapters, 1):
                it["sheet"] = f"00.{k}"
            continue
        if stages:
            before = 0
            for it in chapters:
                if it["stage_no"]:
                    break
                before += 1
            cursor = stages[0] - before
        else:
            cursor += 1
        for it in chapters:
            if it["stage_no"]:
                it["sheet"] = f"{it['stage_no']:02d}"
                cursor = it["stage_no"] + 1
            else:
                it["sheet"] = f"{cursor:02d}"
                cursor += 1

    for i, item in enumerate(items):
        if item["level"] != 1:
            continue
        sheets = [x["sheet"] for x in items[i + 1:] if x["level"] == 2 and x["part"] == item["part"]]
        item["sheet"] = sheets[0] if sheets else ""
        if len(sheets) > 1:
            item["range"] = f"{sheets[0]} — {sheets[-1]}"
        elif sheets:
            item["range"] = sheets[0]

    out: list[str] = []
    cursor = 0
    for item, m in zip(items, matches):
        out.append(body[cursor:m.start()])
        cursor = m.end()
        attrs = item["attrs"]
        if item["level"] == 1:
            attrs = (
                attrs
                + f' data-part="{item["part"]:02d}" data-sheet="{item["sheet"]}"'
                + f' data-range="{item["range"]}"'
            )
            out.append(f"<h1{attrs}>{item['inner']}</h1>")
        else:
            extra = ' data-sheet="%s"' % item["sheet"]
            if item["stage_no"]:
                if 'class="' in attrs:
                    attrs = attrs.replace('class="', 'class="sheet ', 1)
                else:
                    attrs = attrs + ' class="sheet"'
            out.append(f"<h2{attrs}{extra}>{item['inner']}</h2>")
    out.append(body[cursor:])
    annotated = "".join(out)

    # 图号 / 表号包成号牌，文字本身不改。
    annotated = re.sub(
        r"(<figcaption>)(图\s*[\w\-.]+)",
        r'\1<span class="fignum">\2</span>',
        annotated,
    )
    annotated = re.sub(
        r'(<p class="table-caption">)(表\s*[\w\-.]+)',
        r'\1<span class="tabnum">\2</span>',
        annotated,
    )

    # 纯数字单元格右对齐 + 等宽。
    def num_repl(m: re.Match[str]) -> str:
        value = m.group(1).strip()
        if not value or not re.fullmatch(r"[0-9][0-9\s.,]*%?", value):
            return m.group(0)
        return f'<td class="num">{m.group(1)}</td>'

    annotated = NUMERIC_CELL_RE.sub(num_repl, annotated)

    # 检查清单的 [ ] 保留原文，只去掉多余的项目符号。
    annotated = annotated.replace("<li>[ ] ", '<li class="task"><span class="box">[ ]</span> ')

    return annotated, items


def build_toc(headings: list[dict]) -> str:
    rows: list[str] = []
    for h in headings:
        hid = html.escape(h["id"], quote=True)
        text = html.escape(h["text"])
        if h["level"] == 1:
            rows.append(
                f'<tr class="row-part"><td class="c-sheet">PART {h["part"]:02d}</td>'
                f'<td class="c-title"><a href="#{hid}">{text}</a></td>'
                f'<td class="c-page"><a class="pg" href="#{hid}"></a></td></tr>'
            )
        else:
            rows.append(
                f'<tr class="row-sheet"><td class="c-sheet">{html.escape(h["sheet"])}</td>'
                f'<td class="c-title"><a href="#{hid}">{text}</a></td>'
                f'<td class="c-page"><a class="pg" href="#{hid}"></a></td></tr>'
            )
    return (
        '<table class="toc">'
        "<thead><tr>"
        '<th class="c-sheet">SHEET</th><th class="c-title">TITLE</th><th class="c-page">PAGE</th>'
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def cover_html() -> str:
    fig = COVER_FIGURE.as_uri()
    return f"""
<section class="cover">
  <div class="cover-grid"></div>
  <div class="cover-frame-outer"></div>
  <div class="cover-frame-inner"></div>
  <div class="cover-head">
    <span>DSWS · DRAWING SET 01</span>
    <span class="r">A4 · 210 × 297</span>
  </div>
  <div class="cover-kicker">DESIGN ATLAS &amp; BUILD MANUAL · S0–S8</div>
  <h1 class="cover-title"><span>DSWS</span> 从零到一</h1>
  <div class="cover-rule"></div>
  <p class="cover-sub">电商问数智能体 · 设计图集与开发手册</p>
  <figure class="cover-fig"><img src="{fig}" alt="">
    <div class="cover-fig-label">REF. 05 · S0–S8 阶段演进 · 缩略 1:1</div>
  </figure>
  <table class="titleblock">
    <tr><th>PROJECT</th><td>DSWS 从零到一</td><th>DWG NO.</th><td>{DRAWING_NO}</td></tr>
    <tr><th>BASELINE</th><td>baseline {BASELINE} · {DATE}</td><th>SCALE</th><td>1:1 · A4</td></tr>
    <tr><th>STATUS</th><td>{VERSION} · 教学与评审双用途</td><th>SHEETS</th><td>32 张设计图 · S0–S8 全流程</td></tr>
  </table>
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
    body, headings = annotate_html(body)
    toc = build_toc(headings)
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
  <div class="toc-kicker">DRAWING INDEX</div>
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
