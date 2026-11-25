#!/usr/bin/env python3
"""Render book/book.html to book/pdf/dsws-design-atlas.pdf with WeasyPrint."""
from __future__ import annotations

import sys
from pathlib import Path

from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book"
SRC = BOOK / "book.html"
OUT = BOOK / "pdf" / "dsws-design-atlas.pdf"


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}; run scripts/build_book.py first")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = HTML(filename=str(SRC), base_url=str(BOOK)).render()
    doc.write_pdf(
        str(OUT),
        optimize_images=True,
        uncompressed_pdf=False,
        pdf_version="1.7",
    )
    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"wrote {OUT} · {len(doc.pages)} pages · {size_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
