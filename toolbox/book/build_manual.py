#!/usr/bin/env python3
"""新手册构建管线：tutorial/page-*.md + OVERVIEW.md → 单文件 HTML + A4 PDF。

产物（默认）：
  materials/deliverable/tutorial-book/tutorial-book.html   自包含 HTML（CSS/图片内嵌）
  materials/deliverable/tutorial-book/tutorial-book.pdf    A4 打印版（WeasyPrint）

用法：
  uv run --offline --with weasyprint --with markdown python3 toolbox/book/build_manual.py
  python3 toolbox/book/build_manual.py --html        # 只出 HTML（不需要 weasyprint）
  python3 toolbox/book/build_manual.py --pdf         # 只出 PDF
  python3 toolbox/book/build_manual.py --out /tmp/book --no-embed
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "tutorial"
CSS_FILE = Path(__file__).resolve().parent / "book.css"
BOOK_OVERVIEW = Path(__file__).resolve().parent / "overview.md"
BOOK_VISUALS = Path(__file__).resolve().parent / ".visuals"
DEFAULT_OUT = ROOT / "materials" / "deliverable" / "tutorial-book"

TITLE = "电商问数 · 工程手册"
SUBTITLE = "24 章，把一座城从空地造到能交付"
KICKER = "DSWS · 消融式工程教程"
VERSION = "v2.0"

LEVELS = {
    **{i: ("L1", "造", "造：从一片空地开始") for i in range(0, 10)},
    **{i: ("L2", "换", "换：把演示件换成真件") for i in range(10, 14)},
    **{i: ("L3", "审", "审：证明它凭什么可信") for i in range(14, 18)},
    **{i: ("L4", "守", "守：让它敢被交付") for i in range(18, 23)},
    23: ("L5", "装", "装：体验层只换门面"),
}
LEVEL_ORDER = [("L1", "造", "造：从一片空地开始", range(0, 10)),
               ("L2", "换", "换：把演示件换成真件", range(10, 14)),
               ("L3", "审", "审：证明它凭什么可信", range(14, 18)),
               ("L4", "守", "守：让它敢被交付", range(18, 23)),
               ("L5", "装", "装：体验层只换门面", range(23, 24))]

MD_EXTENSIONS = ["extra", "sane_lists"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def safe_name(path: Path, used: dict[str, Path]) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", path.name)
    if base not in used or used[base] == path:
        used[base] = path
        return base
    stem, suffix = path.stem, path.suffix
    n = 2
    while f"{stem}-{n}{suffix}" in used:
        n += 1
    name = f"{stem}-{n}{suffix}"
    used[name] = path
    return name


def resolve_image(src: str, chapter_dir: Path) -> Path | None:
    src = src.strip().strip('<>')
    if src.startswith(("http://", "https://", "data:", "file:")):
        return None
    p = (chapter_dir / src).resolve()
    if p.is_file():
        book = BOOK_VISUALS / p.name
        return book if book.is_file() else p
    p2 = (TUTORIAL / src).resolve()
    if p2.is_file():
        book = BOOK_VISUALS / p2.name
        return book if book.is_file() else p2
    return None


def preprocess_images(md_text: str, chapter_dir: Path, images: dict[str, Path], image_dir: str, embed: bool) -> str:
    def repl(m: re.Match[str]) -> str:
        alt, src = m.group(1).strip(), m.group(2).strip()
        p = resolve_image(src, chapter_dir)
        if p is None:
            return m.group(0)
        name = safe_name(p, images)
        rel = f"{image_dir}/{name}"
        alt_h = html.escape(alt, quote=True)
        if embed:
            mime = "image/svg+xml" if p.suffix.lower() == ".svg" else \
                   "image/webp" if p.suffix.lower() == ".webp" else \
                   "image/gif" if p.suffix.lower() == ".gif" else \
                   "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            data = base64.b64encode(p.read_bytes()).decode()
            src_attr = f"data:{mime};base64,{data}"
        else:
            src_attr = rel
        return f'<figure class="fig"><img src="{src_attr}" alt="{alt_h}"><figcaption>{alt_h}</figcaption></figure>'
    return re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)", repl, md_text)


def preprocess_links(md_text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        label, href = m.group(1), m.group(2)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        mm = re.search(r"page-(\d{2})\.md", href)
        if mm:
            return f"[{label}](#page-{mm.group(1)})"
        if "OVERVIEW.md" in href:
            return f"[{label}](#overview)"
        if href.endswith("README.md"):
            return f"[{label}](#intro)"
        return m.group(0)
    return re.sub(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)", repl, md_text)


def convert(md_text: str, chapter_dir: Path, image_dir: str, images: dict[str, Path], embed: bool) -> str:
    text = preprocess_images(md_text, chapter_dir, images, image_dir, embed)
    text = preprocess_links(text)
    return markdown.markdown(text, extensions=MD_EXTENSIONS)


def first_h1(md_text: str) -> str:
    m = re.search(r"^#\s+(.+)$", md_text, re.M)
    return m.group(1).strip() if m else "（无标题）"


def strip_first_h1(md_text: str) -> str:
    return re.sub(r"^#\s+.+\n", "", md_text, count=1, flags=re.M)


def page_block(page: int, images: dict[str, Path], image_dir: str, embed: bool) -> tuple[str, str, str]:
    path = TUTORIAL / f"page-{page:02d}.md"
    md_text = chapterize(path.read_text(encoding="utf-8"))
    title = first_h1(md_text)
    body = convert(strip_first_h1(md_text), TUTORIAL, image_dir, images, embed)
    level, short, _ = LEVELS[page]
    cls = f"theme-{level.lower()}"
    block = f'''<section class="chapter {cls}" id="page-{page:02d}">
<header class="ch-head">
  <div class="ch-meta"><span class="level" data-level="{level} · {short}">{level} · {short}</span><span class="ch-no">CHAPTER {page:02d}</span></div>
  <h1>{html.escape(title)}</h1>
</header>
<div class="ch-body">
{body}
</div>
</section>'''
    return block, title, level


def chapterize(text: str) -> str:
    """只改书的渲染层：教程页 → 章；不写回 md 正典，也不动网页版。"""
    text = re.sub(r"第\s*(\d+)\s*页", r"第 \1 章", text)
    text = re.sub(r"第([一二三四五六七八九十]+)页", r"第\1章", text)
    text = text.replace("这一页", "这一章").replace("每一页", "每一章")
    text = text.replace("本页", "本章").replace("下一页", "下一章").replace("前一页", "前一章")
    return text


def page_summary(page: int) -> str:
    text = chapterize((TUTORIAL / f"page-{page:02d}.md").read_text(encoding="utf-8"))
    m = re.search(r"## 这一[页章]构建什么\n\n(.+?)(?:\n\n|\n## )", text, re.S)
    raw = m.group(1) if m else ""
    raw = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", raw)
    raw = re.sub(r"[*_`>#]", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    m2 = re.search(r"^(.+?[。；])", raw)
    s = m2.group(1) if m2 else raw
    return s[:64] + ("…" if len(s) > 64 else "")


def page_index_table(pages: list[tuple[int, str]]) -> str:
    rows = []
    for level, short, desc, rng in LEVEL_ORDER:
        rows.append(f'<tr class="level-row"><td colspan="3"><span class="pi-level">{level} · {short}</span> {html.escape(desc)}</td></tr>')
        for page, title in pages:
            if page in rng:
                rows.append(f'<tr><td class="pi-no">第 {page} 章</td><td class="pi-title">{html.escape(title)}</td><td class="pi-sum">{html.escape(page_summary(page))}</td></tr>')
    return ('<table class="page-index"><thead><tr><th>章</th><th>标题</th><th>这一章构建什么</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table>')


def front_block(images: dict[str, Path], image_dir: str, embed: bool, pages: list[tuple[int, str]]) -> tuple[str, str]:
    path = BOOK_OVERVIEW
    md_text = chapterize(path.read_text(encoding="utf-8"))
    title = first_h1(md_text)
    md_text = md_text.replace("{{PAGE_INDEX}}", page_index_table(pages))
    body = convert(strip_first_h1(md_text), TUTORIAL, image_dir, images, embed)
    body = body.replace("<h2>24 章一览</h2>", '<h2 class="page-index-heading">24 章一览</h2>')
    block = f'''<section class="chapter front-map" id="overview">
<header class="ch-head">
  <div class="ch-meta"><span class="level">全书地图</span><span class="ch-no">OVERVIEW</span></div>
  <h1>{html.escape(title)}</h1>
</header>
<div class="ch-body">
{body}
</div>
</section>'''
    return block, title


def intro_block() -> str:
    return '''<section class="intro front" id="intro">
<div class="intro-mark">DSWS</div>
<h1>怎么用这本手册</h1>
<p class="lead">这不是一本“读完就会”的书，是一本“照着做、能对账”的练本。全书 24 章，分成五级：<b>造 → 换 → 审 → 守 → 装</b>。每一章只做一件事，每一章都留下一条你能亲手跑出来的判据。</p>
<div class="intro-cols">
<div><h2>先看地图</h2><p>先读 <b>全书地图</b>：一片空地上有十座设施，每一章盖一座、接一段管网。左边回答“为什么是这个顺序”，右边回答“这一章做完手里有什么”。</p></div>
<div><h2>再翻一页</h2><p>每章固定六段：这一章构建什么 → 猜一猜 → 动手 → 你应该看到 → 对账 → 拆一刀。先猜，再动手；看到真实输出，再对账；最后拆掉一个组件，看系统怎么坏。</p></div>
<div><h2>对账比读完重要</h2><p>把“你应该看到”里的真实输出和你的屏幕逐行对。对不上就停在这一章；能对账，才算学会。书的正文是 <code>tutorial/page-*.md</code>，这本 HTML/PDF 只是它的渲染版。PDF 版页眉的 <code>CHAPTER NN</code> 是手册章编号，页脚数字是 PDF 物理页；附录 A 有逐章对照表。</p></div>
</div>
</section>'''


def toc_block(front_title: str, pages: list[tuple[int, str]]) -> str:
    items = ['<li class="toc-row"><a href="#intro"><span class="toc-t">怎么用这本手册</span></a></li>',
             f'<li class="toc-row"><a href="#overview"><span class="toc-t">{html.escape(front_title)}</span></a></li>']
    for level, short, desc, rng in LEVEL_ORDER:
        items.append(f'<li class="toc-level"><span class="toc-lv">{level} · {short}</span><span class="toc-desc">{html.escape(desc)}</span></li>')
        for page, title in pages:
            if page in rng:
                items.append(f'<li class="toc-row"><a href="#page-{page:02d}"><span class="toc-no">{page:02d}</span><span class="toc-t">{html.escape(title)}</span></a></li>')
    return '<section class="toc front" id="toc"><div class="toc-head"><div class="toc-k">Contents</div><h1>目录</h1></div><ol class="toc-list">' + "\n".join(items) + '</ol></section>'


def page_map_block(page_map: dict, pages: list[tuple[int, str]]) -> str:
    mapping = page_map.get("mapping", {})
    rows = []
    for page, title in pages:
        v = mapping.get(f"{page:02d}")
        if not v:
            continue
        rows.append(f'<tr><td><b>第 {page} 章</b></td><td>{html.escape(title)}</td>'
                    f'<td class="num">{v["start"]}</td><td class="num">{v["end"]}</td><td class="num">{v["pages"]}</td></tr>')
    return f'''<section class="chapter page-map" id="page-map">
<header class="ch-head">
  <div class="ch-meta"><span class="level">附录 A</span><span class="ch-no">CHAPTER MAP</span></div>
  <h1>手册章 ↔ PDF 物理页对照</h1>
</header>
<div class="ch-body">
<p>教程章（CHAPTER NN）是内容单位；A4 打印版一章会排成多张 PDF 页，所以两者不是 1:1。页眉的 <code>CHAPTER NN</code> 是手册章编号，页脚的阿拉伯数字是 PDF 物理页；本表用于互查，TOC 里的页码也是 PDF 物理页。</p>
<table class="page-map-table"><thead><tr><th>手册章</th><th>标题</th><th>PDF 起</th><th>PDF 止</th><th>页数</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p class="map-note">共 {len(pages)} 章手册内容；PDF 物理页数见 PDF 属性。</p>
</div>
</section>'''


def cover_block(date: str, head: str) -> str:
    return f'''<section class="cover">
<div class="cover-top"><span>{KICKER}</span><span class="cover-right">STUDENT HANDBOOK</span></div>
<div class="cover-main">
  <div class="cover-index">24 章 · 14 次拆一刀</div>
  <h1>电商问数<br><em>工程手册</em></h1>
  <p class="cover-sub">{SUBTITLE}</p>
  <div class="cover-rule"></div>
  <p class="cover-deck">从契约、数据、生成、执行，到校验、安全、可观测与交付；<br>L2–L5 共 14 次拆一刀：先写预测，再看哪条判据变红。</p>
</div>
<div class="cover-foot"><span>{VERSION} · {date}</span><span>baseline {head}</span><span class="r">DSWS · 2026</span></div>
</section>'''


def build_html(out: Path, embed: bool, page_map: dict | None = None) -> tuple[str, dict[str, Path], list[tuple[int, str]]]:
    out.mkdir(parents=True, exist_ok=True)
    image_dir = "assets/images"
    images: dict[str, Path] = {}
    pages: list[tuple[int, str]] = []
    blocks = []
    for p in range(24):
        block, title, _ = page_block(p, images, image_dir, embed)
        pages.append((p, title))
        blocks.append(block)
    front, front_title = front_block(images, image_dir, embed, pages)
    date = _dt.date.today().isoformat()
    head = git_head()
    map_html = page_map_block(page_map, pages) if page_map else ""
    css = CSS_FILE.read_text(encoding="utf-8")
    doc = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE} · {VERSION}</title>
<style>
{css}
</style>
</head>
<body>
<div class="book">
{cover_block(date, head)}
{intro_block()}
{toc_block(front_title, pages)}
{front}
{''.join(blocks)}
{map_html}
<section class="back-cover"><p>全书 24 章 · 五级 · 一条可复现的工程学习线</p><p class="bc-small">正文正典：{TUTORIAL.name}/page-*.md · 构建 {date} · baseline {head}</p></section>
</div>
</body>
</html>'''
    # 复制图片（PDF/外链 HTML 用；自包含 HTML 已经内嵌）
    if not embed:
        assets = out / "assets" / "images"
        assets.mkdir(parents=True, exist_ok=True)
        for name, src in images.items():
            shutil.copy2(src, assets / name)
    return doc, images, pages


def write_html(out: Path, embed: bool, page_map: dict | None = None) -> Path:
    html_doc, _, _ = build_html(out, embed, page_map)
    target = out / "tutorial-book.html"
    target.write_text(html_doc, encoding="utf-8")
    return target


def write_print_html(out: Path, page_map: dict | None = None) -> Path:
    html_doc, _, _ = build_html(out, embed=False, page_map=page_map)
    print_html = out / ".print.html"
    print_html.write_text(html_doc, encoding="utf-8")
    return print_html


def write_pdf(out: Path) -> Path:
    try:
        from weasyprint import HTML  # noqa: F401
    except Exception as e:  # noqa: BLE001
        raise SystemExit(
            "缺少 WeasyPrint；请用管线：make book-pdf（内部用 uv run --offline --with weasyprint）"
        ) from e
    print_html = write_print_html(out)
    pdf = out / "tutorial-book.pdf"
    doc = HTML(filename=str(print_html), base_url=str(out)).render()
    doc.write_pdf(str(pdf), optimize_images=True)
    print_html.unlink(missing_ok=True)
    (out / "tutorial-book.pdf.meta").write_text(f"pages={len(doc.pages)}\nsha256={sha256(pdf)}\nhead={git_head()}\n", encoding="utf-8")
    return pdf


def write_readme(out: Path) -> Path:
    text = f'''# {TITLE} · {VERSION}

由 `toolbox/book/build_manual.py` 从 `tutorial/` 正典生成；不要手改产物。

- `tutorial-book.html`：自包含 HTML（CSS/图片内嵌，可直接分享）
- `tutorial-book.pdf`：A4 打印版（WeasyPrint，含目录页码/页眉页脚；附录 A 为「手册章 ↔ PDF 物理页」对照）
- 构建：`make book`（内部两遍：先渲染取页码，再写入附录 A 后重渲染）
- 来源：`tutorial/OVERVIEW.md` + `tutorial/page-00..23.md`；图片来自 `tutorial/images/`
- 生成日期：{_dt.date.today().isoformat()} · baseline `{git_head()}`
- 注意：改内容请改 md，然后重跑；本目录是生成物。
'''
    p = out / "README.md"
    p.write_text(text, encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--html", action="store_true", help="只生成 HTML")
    ap.add_argument("--pdf", action="store_true", help="只生成 PDF")
    ap.add_argument("--no-embed", action="store_true", help="HTML 不内嵌图片（生成 assets/ 目录）")
    ap.add_argument("--print-html", action="store_true", help="只生成给 PDF 用的 .print.html + assets（不渲染 PDF）")
    ap.add_argument("--page-map", type=Path, help="page-map.json（附录 A：手册章→PDF 页对照）")
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    do_html = args.html or not args.pdf
    do_pdf = args.pdf or not args.html
    page_map = None
    if args.page_map and args.page_map.is_file():
        page_map = __import__("json").loads(args.page_map.read_text(encoding="utf-8"))
    if args.print_html:
        target = write_print_html(out, page_map)
        print(f"PRINT: {target}  {target.stat().st_size/1024/1024:.1f} MB")
        readme = write_readme(out)
        print(f"README: {readme}")
        return
    if do_html:
        target = write_html(out, embed=not args.no_embed, page_map=page_map)
        print(f"HTML: {target}  {target.stat().st_size/1024/1024:.1f} MB")
    if do_pdf:
        target = write_pdf(out)
        print(f"PDF : {target}  {target.stat().st_size/1024/1024:.1f} MB")
    readme = write_readme(out)
    print(f"README: {readme}")


if __name__ == "__main__":
    main()
