#!/usr/bin/env python3
"""从已生成的 PDF 提取「手册章（CHAPTER NN）→ PDF 物理页」对照。

页眉由 book.css 的 @top-left/right 与 .ch-meta .ch-no 生成；pdftotext 提取后
按 "CHAPTER NN"（兼容旧 "PAGE NN"）归一化匹配。输出 JSON 给 build_manual.py --page-map 用。

用法： python3 toolbox/book/extract_page_map.py PDF [OUT.json]
"""
from __future__ import annotations
import json, re, subprocess, sys
from datetime import date
from pathlib import Path


def page_text(pdf: Path, n: int) -> str:
    p = subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), "-layout", str(pdf), "-"],
                       capture_output=True, text=True)
    return p.stdout


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__); return 2
    pdf = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else pdf.with_suffix(".page-map.json")
    if not pdf.is_file():
        raise SystemExit(f"missing {pdf}")
    total = 0
    for line in subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout.splitlines():
        if line.startswith("Pages:"):
            total = int(line.split()[1])
    starts: dict[str, int] = {}
    for n in range(1, total + 1):
        text = page_text(pdf, n)
        head = " ".join(text.splitlines()[:5])
        compact = re.sub(r"\s+", "", head).upper()
        m = re.search(r"(?:CHAPTER|PAGE)0*(\d{1,2})", compact)
        if m:
            num = int(m.group(1))
            key = f"{num:02d}"
            if 0 <= num < 24 and key not in starts:
                starts[key] = n
    # 附录 A 的页眉是 "CHAPTER MAP"，不是 CHAPTER NN；用它确定最后一章真正的结束页。
    appendix_start = None
    for n in range(1, total + 1):
        head = " ".join(page_text(pdf, n).splitlines()[:5])
        compact = re.sub(r"\s+", "", head).upper()
        if "CHAPTERMAP" in compact or "PAGEMAP" in compact or "手册章" in head:
            appendix_start = n
            break
    ordered = sorted(starts.items(), key=lambda kv: kv[1])
    mapping = {}
    for i, (key, start) in enumerate(ordered):
        if i + 1 < len(ordered):
            end = ordered[i + 1][1] - 1
        elif appendix_start and appendix_start > start:
            end = appendix_start - 1
        else:
            end = total - 1
        mapping[key] = {"start": start, "end": end, "pages": end - start + 1}
    payload = {"generated": date.today().isoformat(), "pdf_pages": total, "mapping": mapping}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"page-map: {len(mapping)} chapters / {total} PDF pages → {out}")
    for k in sorted(mapping):
        v = mapping[k]
        print(f"  CHAPTER {k}: {v['start']:>3}–{v['end']:<3} ({v['pages']} 页)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
