#!/usr/bin/env python3
"""QA gate for the design atlas and book."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "diagrams"
BOOK = ROOT / "book"
PDF = BOOK / "pdf" / "dsws-design-atlas.pdf"
HTML_FILE = BOOK / "book.html"

PLACEHOLDERS = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|\{\{[^}]+\}\}")


def main() -> int:
    problems: list[str] = []
    svgs = sorted(DIAGRAMS.rglob("*.svg"))
    mmd = sorted(DIAGRAMS.rglob("*.mmd"))
    dots = sorted(DIAGRAMS.rglob("*.dot"))
    print(f"diagrams: {len(svgs)} svg ({len(mmd)} mermaid, {len(dots)} graphviz)")

    if len(svgs) < 24:
        problems.append(f"only {len(svgs)} diagrams; need >= 24")

    if not HTML_FILE.exists():
        problems.append("book/book.html missing")
    if not PDF.exists():
        problems.append("book/pdf/dsws-design-atlas.pdf missing")
    else:
        pages = len(HTML(filename=str(HTML_FILE), base_url=str(BOOK)).render().pages)
        print(f"pdf pages: {pages}")
        if pages < 30:
            problems.append(f"PDF only {pages} pages; need >= 30")

    # Placeholder scan in chapters and inventory.
    for path in sorted((BOOK / "chapters").glob("*.md")) + sorted((ROOT / "inventory").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for m in PLACEHOLDERS.finditer(text):
            line = text[: m.start()].count("\n") + 1
            problems.append(f"placeholder {m.group(0)!r} in {path.relative_to(ROOT)}:{line}")

    # Missing image references.
    for path in sorted((BOOK / "chapters").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for alt, src in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text):
            if src.startswith(("http://", "https://", "file://")):
                continue
            target = (path.parent / src).resolve()
            if not target.exists():
                problems.append(f"missing image {src} in {path.name}")

    if problems:
        print("\nFAIL")
        for p in problems:
            print(f" - {p}")
        return 1

    print("\nPASS: diagrams, book, PDF page count, placeholders, image links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
