#!/usr/bin/env python3
"""组版 PDF 逐页质检：空白/残页检测 + 页数判据。

用法：python3 check_pdf_pages.py [pdf路径]   # 默认 materials/design/design-doc.pdf
判定：每页墨迹覆盖率 ≥ 0.8%（纯空白/残页判 FAIL）；总页数 ≥30 且 ≤45（组版预期 31±2，上限放宽给 claims 表自然分页）。
退出码：0 通过；1 有空白页或页数越界。
"""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
PDF = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "materials/design/design-doc.pdf"


def ink_fraction(png: Path) -> float:
    # mean brightness 0(黑)-255(白)；墨迹覆盖率 ≈ (255-mean)/255
    out = subprocess.run(["convert", str(png), "-colorspace", "Gray", "-format", "%[fx:mean]", "info:"],
                         check=True, capture_output=True, text=True).stdout.strip()
    return 1.0 - float(out)


def main() -> int:
    info = subprocess.run(["pdfinfo", str(PDF)], check=True, capture_output=True, text=True).stdout
    pages = int(next(l.split(":")[1] for l in info.splitlines() if l.startswith("Pages:")))
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["pdftoppm", "-png", "-r", "36", str(PDF), str(tmp / "p")],
                   check=True, capture_output=True, timeout=300)
    pngs = sorted(tmp.glob("p-*.png"))
    bad = []
    for i, p in enumerate(pngs, 1):
        ink = ink_fraction(p)
        flag = ""
        if ink < 0.008:
            flag = "  ← 空白/残页"
            bad.append(i)
        print(f"p{i:>2}  ink={ink * 100:5.2f}%{flag}")
    ok_pages = 30 <= pages <= 45
    print(f"页数 {pages}（判据 30–45：{'OK' if ok_pages else 'FAIL'}）")
    if bad:
        print(f"空白/残页：{bad}")
    result = ok_pages and not bad
    print(f"PDF 逐页质检：{'PASS' if result else 'FAIL'}")
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
