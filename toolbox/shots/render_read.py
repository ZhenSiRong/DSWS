#!/usr/bin/env python3
"""阅读版渲染：tutorial/page-XX.md → tutorial/read/page-XX.html。

md 正典是唯一事实来源，本脚本只转换排版、不改内容（第 4 轮 Q2 修订后转正）。
样式复用 materials/assets/lesson.css ＋ materials/assets/read.css，不新建样式体系。

用法：
    python3 tutorial/shots/render_read.py 17          # 单页
    python3 tutorial/shots/render_read.py 13 18 21    # 多页
    python3 tutorial/shots/render_read.py --all       # 全书 24 页
    python3 tutorial/shots/render_read.py 17 --embed  # 自包含单文件（CSS/图片内嵌，可分享）

默认输出相对链接（../images/、../../assets/），浏览器直接打开 file:// 即可；
--embed 输出到 tutorial/review/reading-layer-preview/pXX-read.html（预览/分享用）。
"""
import argparse
import base64
import re
import sys
from pathlib import Path

import markdown

REPO = Path(__file__).resolve().parents[2]
MANUAL = REPO / "tutorial"
ASSETS = REPO / "materials" / "assets"


def embed_images(html: str) -> str:
    def repl(m):
        p = MANUAL / "images" / m.group(1)
        mime = "image/webp" if p.suffix == ".webp" else "image/png"
        return f'src="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"'
    return re.sub(r'src="images/([^"]+)"', repl, html)


def render(page: str, embed: bool) -> Path:
    md_path = MANUAL / f"page-{page}.md"
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = body.replace("<p>▲", '<p class="caption">▲')
    m = re.search(r"^# (.+)$", text, re.M)
    title = m.group(1) if m else f"第 {page} 页"

    if embed:
        css = (ASSETS / "lesson.css").read_text(encoding="utf-8") + "\n" + \
              (ASSETS / "read.css").read_text(encoding="utf-8")
        head = f"<style>\n{css}\n</style>"
        body = embed_images(body)
        out = MANUAL / "materials/review/reading-layer-preview" / f"p{page}-read.html"
    else:
        head = ('<link rel="stylesheet" href="../../assets/lesson.css">\n'
                '<link rel="stylesheet" href="../../assets/read.css">')
        body = body.replace('src="images/', 'src="../images/')
        out = MANUAL / "read" / f"page-{page}.html"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · 阅读版</title>
{head}
</head>
<body>
<main class="page">
<p class="kicker">练本 · 阅读版（md 正典派生，改内容请改 tutorial/page-{page}.md）</p>
{body}
</main>
</body>
</html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pages", nargs="*", help="页号，如 17 或 00")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--embed", action="store_true")
    args = ap.parse_args()

    if args.all:
        pages = sorted(p.stem.removeprefix("page-") for p in MANUAL.glob("page-*.md"))
    else:
        pages = [p.zfill(2) for p in args.pages]
    if not pages:
        ap.error("给页号或 --all")
    for page in pages:
        if not (MANUAL / f"page-{page}.md").exists():
            sys.exit(f"page-{page}.md 不存在")
        out = render(page, args.embed)
        print(f"📖 {out.relative_to(REPO)}  {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()