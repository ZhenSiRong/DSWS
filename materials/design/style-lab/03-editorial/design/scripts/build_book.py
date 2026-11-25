#!/usr/bin/env python3
"""Assemble book/chapters/*.md into a single print-ready HTML file.

- Reads book/manifest.txt (one chapter path per line, relative to book/).
- Converts Markdown to HTML with tables, fenced code, and heading ids.
- Turns image paragraphs into <figure> with captions.
- Builds a TOC with real page numbers via CSS target-counter.
- Embeds diagrams as file:// SVGs so WeasyPrint can render them.

风格 03「编辑杂志」：封面与目录由 cover_html() / build_toc() 生成；正文按
「部分 → 小节」包一层 <section class="theme-*">，让每个 S 阶段有自己的主题色。
章节 Markdown 一个字都不改，所有加工都在这一层做。
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

# ---------- 主题色 ----------
# 部分号 → 主题；S 阶段 → 主题。前部（00-front）走中性墨色，进入 S5 才开始上色。
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
PART_RE = re.compile(r"第([一二三四五六七八九十]+)部分")
STAGE_RE = re.compile(r"S(\d)\s*·")
H2_NUM_RE = re.compile(r"^([56])\.")
PART_THEME = {1: "ink", 3: "s5"}
STAGE_THEME = {5: "s5", 6: "s6", 7: "s7", 8: "s8"}

# 目录里每个部分的一句短说明：逐字摘自正文，不改写。
TOC_DESC = {
    1: "契约是事实源，图是论证，阶段是施工顺序，证据是发言资格。",
    3: "拒绝要可判定，错误要有名字，类型要保真，部署边界要说清。",
}

# 拉引：正文原句，插入在它所在段落之后。
PULL_QUOTES = [
    "没有报错，也没有红框。",
    "拒绝要可判定，错误要有名字，类型要保真，部署边界要说清。",
    "形状合法，语义完全错。",
]


def cn_int(raw: str) -> int:
    if raw == "十":
        return 10
    if "十" in raw:
        tens, _, ones = raw.partition("十")
        return (CN_NUM.get(tens, 1) if tens else 1) * 10 + (CN_NUM.get(ones, 0) if ones else 0)
    return CN_NUM.get(raw, 0)


def part_theme(no: int) -> str:
    return PART_THEME.get(no, "ink")


def section_theme(part_no: int, text: str) -> str:
    m = STAGE_RE.search(text)
    if m:
        return STAGE_THEME.get(int(m.group(1)), part_theme(part_no))
    if H2_NUM_RE.match(text):        # 5. 走到这里 / 6. 复习题 回到中性墨色
        return "ink"
    return part_theme(part_no)


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
    """Replace mermaid code blocks with rendered SVG images (for the PDF)."""
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
        r"\x60\x60\x60mermaid\n(.*?)\x60\x60\x60[ \t]*\n(?:[ \t]*\*([^*\n]+)\*[ \t]*\n)?",
        repl,
        text,
        flags=re.S,
    )


def preprocess_images(text: str, chapter: Path) -> str:
    """![alt](relative) -> <figure><img src="file://..."><figcaption>alt</figcaption></figure>."""

    def repl(match: re.Match[str]) -> str:
        alt_raw, src = match.group(1), match.group(2)
        side = alt_raw.strip().startswith("side ")
        alt = alt_raw.strip()
        if side:
            alt = alt[len("side "):].strip()
        src = src.strip()
        if src.startswith(("http://", "https://", "file://")):
            url = src
            target = None
        else:
            target = (chapter.parent / src).resolve()
            url = target.as_uri()
        alt_html = html.escape(alt, quote=True)
        cls = ""
        if side:
            cls = ' class="side"'
        elif target is not None and target.suffix.lower() == ".svg" and target.exists():
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
    """Paragraphs like 表 2-1 · ... immediately before a table become captions."""
    pattern = re.compile(r"<p>(表\s*[\w\-.]+[^<]{0,160})</p>\s*(<table>|(<table) )", re.S)

    def repl(m: re.Match[str]) -> str:
        cap = m.group(1)
        mm = re.match(r"^(表\s*[\w\-.]+)\s*·\s*(.*)$", cap)
        if mm:
            inner = f'<span class="tno">{mm.group(1)}</span> · {mm.group(2)}'
        else:
            inner = f'<span class="tno">表</span> {cap}'
        return f'<p class="table-caption">{inner}</p>\n{m.group(2)}'

    return pattern.sub(repl, html_text)


def split_figure_captions(html_text: str) -> str:
    """图 07 · 端到端请求生命周期 -> 图号标签 + 说明。"""

    def repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        mm = re.match(r"^(图\s*[\w\-.]+)\s*·\s*(.+)$", inner, re.S)
        if not mm:
            return m.group(0)
        return f'<figcaption><span class="fno">{mm.group(1)}</span> · {mm.group(2)}</figcaption>'

    return re.sub(r"<figcaption>(.*?)</figcaption>", repl, html_text, flags=re.S)


def checkboxes(html_text: str) -> str:
    """清单项 [ ] 换成可排版的方框。"""
    return re.sub(r"<li>\[ \]\s*", '<li class="check">', html_text)


def strip_tags(value: str) -> str:
    # Status icons are line art with no text child; use their aria-label so a
    # heading like "5. 证据等级：✅ / 🟡 / ⚪" keeps readable TOC text.
    def icon_label(m: re.Match[str]) -> str:
        label = re.search(r'aria-label="([^"]*)"', m.group(0))
        return label.group(1) if label else ""

    value = re.sub(r"<svg\b[^>]*>.*?</svg>", icon_label, value, flags=re.S)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


H1_SPLIT_RE = re.compile(
    r"<h1\b([^>]*)>(第[一二三四五六七八九十]+部分)(\s*·\s*)(.*?)</h1>", re.S
)


def split_part_title(chunk: str) -> str:
    """第一部分 · 先读这一页 -> 眉标 + 大标题（文字一个不少）。"""

    def repl(m: re.Match[str]) -> str:
        return (
            f'<h1{m.group(1)}><span class="kicker">{m.group(2)}{m.group(3)}</span>'
            f'<span class="ttl">{m.group(4)}</span></h1>'
        )

    return H1_SPLIT_RE.sub(repl, chunk)


def lead_paragraph(piece: str) -> str:
    """给标题后的第一段加首字下沉，只在该段以汉字开头且够长时。"""
    m = re.match(r"(<h[12]\b[^>]*>.*?</h[12]>)\s*(<p>)(.*?)</p>", piece, re.S)
    if not m:
        return piece
    text = strip_tags(m.group(3))
    if not text or not ("\u4e00" <= text[0] <= "\u9fff") or len(text) < 50:
        return piece
    return piece[: m.start(2)] + '<p class="lead">' + piece[m.end(2):]


def wrap_parts(body: str) -> str:
    """按 h1 分部分、按 h2 分小节，套上主题色。"""
    out: list[str] = []
    chunks = re.split(r"(?=<h1\b)", body)
    for idx, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        head = re.match(r"<h1\b[^>]*>(.*?)</h1>", chunk, re.S)
        if not head:
            out.append(chunk)
            continue
        title = strip_tags(head.group(1))
        pm = PART_RE.search(title)
        part_no = cn_int(pm.group(1)) if pm else idx
        theme = part_theme(part_no)

        inner: list[str] = []
        for i, piece in enumerate(re.split(r"(?=<h2\b)", chunk)):
            if not piece.strip():
                continue
            if i == 0:
                inner.append(split_part_title(piece))
                continue
            hm = re.match(r"<h2\b[^>]*>(.*?)</h2>", piece, re.S)
            th = section_theme(part_no, strip_tags(hm.group(1)) if hm else "")
            inner.append(
                f'<section class="sec theme-{th}">\n{lead_paragraph(piece)}\n</section>'
            )
        joined = "\n".join(inner)
        # 每个部分的第一张表反白，其余表格保持浅底。
        joined = joined.replace("<table>", '<table class="tbl-dark">', 1)
        out.append(
            f'<section class="part theme-{theme}" data-part="{part_no:02d}">\n'
            f'<div class="part-no" aria-hidden="true">{part_no:02d}</div>\n'
            f"{joined}\n</section>"
        )
    return "\n".join(out)


def insert_pull_quotes(body: str) -> str:
    for quote in PULL_QUOTES:
        pos = body.find(quote)
        if pos < 0:
            continue
        end = body.find("</p>", pos)
        if end < 0:
            continue
        end += len("</p>")
        body = body[:end] + f'\n<aside class="pull">{quote}</aside>\n' + body[end:]
    return body


def build_toc(body: str) -> str:
    heads = re.findall(r'<h([12])\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</h\1>', body, re.S)
    parts: list[dict] = []
    for level, hid, label in heads:
        text = strip_tags(label)
        if not text or text in {"目录", "封面"}:
            continue
        if level == "1":
            m = PART_RE.search(text)
            no = cn_int(m.group(1)) if m else len(parts) + 1
            parts.append({"no": no, "id": hid, "title": text, "items": []})
        elif parts:
            parts[-1]["items"].append((hid, text))

    blocks: list[str] = []
    for part in parts:
        items = "\n".join(
            f'<li><a href="#{html.escape(hid, quote=True)}">{html.escape(t)}</a></li>'
            for hid, t in part["items"]
        )
        desc = TOC_DESC.get(part["no"], "")
        blocks.append(
            f'<section class="toc-part theme-{part_theme(part["no"])}">\n'
            f'  <div class="toc-part-head">\n'
            f'    <div class="no">{part["no"]:02d}</div>\n'
            f'    <h2>{html.escape(part["title"])}</h2>\n'
            f'    <p class="desc">{html.escape(desc)}</p>\n'
            f'    <a class="pp" href="#{html.escape(part["id"], quote=True)}"></a>\n'
            f'  </div>\n'
            f'  <ul class="toc-list">\n{items}\n  </ul>\n'
            f'</section>'
        )
    return "\n".join(blocks)


def cover_html() -> str:
    """杂志封面：满版深钴蓝、衬线巨标题、巨大的 05—08 底纹、右下角阶段刻度图。"""
    heights = [15, 20, 25, 30, 35, 43, 48, 53, 58]
    bars = []
    for i, h in enumerate(heights):
        x = 2 + i * 12.6
        fill = "#C58B1B" if i >= 5 else "#C3CCDD"
        bars.append(f'<rect x="{x:.1f}" y="{59 - h}" width="7" height="{h}" fill="{fill}"/>')
    plate = (
        '<svg viewBox="0 0 120 62" xmlns="http://www.w3.org/2000/svg">'
        + "".join(bars)
        + '<line x1="0" y1="59.6" x2="120" y2="59.6" stroke="#16305F" stroke-width="0.9"/>'
        + "</svg>"
    )
    return f"""
<section class="cover">
  <div class="ghost">05—08</div>
  <div class="topline">DSWS · REBUILD ATLAS<span class="right">设计图集 · DESIGN ATLAS</span></div>
  <h1><span class="latin">DSWS</span><br>从零到一</h1>
  <div class="rule"></div>
  <p class="subtitle">{SUBTITLE}</p>
  <p class="deck">从契约、构建、召回到生成、安全、失败通道与前端收口</p>
  <div class="plate">{plate}<div class="cap">S0 — S8</div></div>
  <div class="foot">
    <span>baseline {BASELINE} · {DATE}</span>
    <span>32 张设计图 · S0–S8 全流程</span>
    <span class="r">{VERSION} · 教学与评审双用途</span>
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
    body = split_figure_captions(body)
    body = checkboxes(body)
    toc = build_toc(body)
    body = insert_pull_quotes(wrap_parts(body))
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
  <header class="toc-mast">
    <div class="word">Contents</div>
    <div class="cn">目录</div>
    <div class="sub">baseline {BASELINE} · {DATE}</div>
  </header>
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
