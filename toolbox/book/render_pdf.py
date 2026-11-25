#!/usr/bin/env python3
"""把 build_manual.py 产出的 .print.html 渲染成 A4 PDF（只依赖 WeasyPrint）。

单独拆出来是因为 `uv run --offline --with weasyprint` 的环境里没有 markdown；
HTML 由系统 python + markdown 生成，PDF 只在 WeasyPrint 环境里渲染。

用法：
  uv run --offline --with weasyprint python3 toolbox/book/render_pdf.py \
      materials/deliverable/tutorial-book/.print.html \
      materials/deliverable/tutorial-book/tutorial-book.pdf
"""
from __future__ import annotations
import sys
from pathlib import Path

from weasyprint import HTML


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__); return 2
    src = Path(sys.argv[1]).resolve()
    dst = Path(sys.argv[2]).resolve()
    if not src.is_file():
        raise SystemExit(f"missing {src}; 先跑 build_manual.py --print-html")
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc = HTML(filename=str(src), base_url=str(src.parent)).render()
    doc.write_pdf(str(dst), optimize_images=True)
    meta = dst.with_suffix(".pdf.meta")
    meta.write_text(f"pages={len(doc.pages)}\nbytes={dst.stat().st_size}\nsource={src.name}\n", encoding="utf-8")
    print(f"PDF: {dst} · {len(doc.pages)} pages · {dst.stat().st_size/1024/1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
