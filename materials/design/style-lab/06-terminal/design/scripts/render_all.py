#!/usr/bin/env python3
"""Render every Mermaid (.mmd) and Graphviz (.dot) source under design/diagrams.

Mermaid is rendered by headless Chrome (the local mermaid.min.js is bundled), then
the serialized SVG is extracted from the dumped DOM. Graphviz uses `dot -Tsvg`.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "diagrams"
MERMAID_JS = ROOT / "assets" / "mermaid.min.js"
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")

MERMAID_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>body{{margin:0;padding:24px;background:#fff;font-family:"Noto Sans CJK SC",sans-serif}}</style>
</head><body>
<pre class="mermaid">{source}</pre>
<script src="{mermaid_js}"></script>
<script>
(async () => {{
  mermaid.initialize({{
    startOnLoad: false,
    securityLevel: 'loose',
    htmlLabels: false,
    fontFamily: '"Noto Sans CJK SC", "Noto Sans SC", sans-serif',
    flowchart: {{ htmlLabels: false, curve: 'basis' }},
    sequence: {{ useMaxWidth: false }},
    theme: 'base',
    themeVariables: {{
      fontFamily: '"Noto Sans CJK SC", sans-serif',
      fontSize: '14px',
      primaryColor: '#eff6ff',
      primaryBorderColor: '#1d4ed8',
      primaryTextColor: '#1e3a8a',
      lineColor: '#6b7280',
      secondaryColor: '#ecfdf5',
      tertiaryColor: '#fff7ed'
    }}
  }});
  await mermaid.run();
  document.body.setAttribute('data-rendered', '1');
}})().catch(e => {{
  document.body.setAttribute('data-error', String(e));
  console.error(e);
}});
</script>
</body></html>
"""


def render_mermaid(src: Path, out: Path) -> tuple[bool, str]:
    if not CHROME:
        return False, "google-chrome/chromium not found"
    if not MERMAID_JS.exists():
        return False, f"missing {MERMAID_JS}"
    text = src.read_text(encoding="utf-8")
    page = MERMAID_TEMPLATE.format(source=html.escape(text), mermaid_js=MERMAID_JS.as_uri())
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        fh.write(page)
        tmp = Path(fh.name)
    try:
        proc = subprocess.run(
            [
                CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--hide-scrollbars", "--virtual-time-budget=12000",
                "--dump-dom", tmp.as_uri(),
            ],
            capture_output=True, text=True, timeout=120,
        )
        dom = proc.stdout
        err_match = re.search(r'<body[^>]*data-error="([^"]*)"', dom)
        if err_match:
            return False, f"mermaid error: {err_match.group(1)}"
        if not re.search(r'<body[^>]*data-rendered="1"', dom):
            return False, "mermaid did not finish rendering"
        svg_match = re.search(r"<svg\b.*?</svg>", dom, re.S)
        if not svg_match:
            return False, "no <svg> in dumped DOM"
        svg = svg_match.group(0)
        # Work on the root <svg> tag only: nested elements also have width/height.
        root_match = re.match(r"<svg\b[^>]*>", svg)
        if not root_match:
            return False, "malformed <svg> root"
        root = root_match.group(0)
        rest = svg[len(root):]
        if 'xmlns="http://www.w3.org/2000/svg"' not in root:
            root = root.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        root = re.sub(r'style="[^"]*max-width:[^"]*"', "", root, count=1)
        vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', root)
        if vb:
            w, h = float(vb.group(3)), float(vb.group(4))
            root = re.sub(r'\s(width|height)="[^"]*"', "", root)
            root = root.replace("<svg", f'<svg width="{w:.0f}" height="{h:.0f}"', 1)
        svg = root + rest
        out.write_text(svg, encoding="utf-8")
        return True, "ok"
    finally:
        tmp.unlink(missing_ok=True)


def render_dot(src: Path, out: Path) -> tuple[bool, str]:
    dot = shutil.which("dot")
    if not dot:
        return False, "graphviz dot not found"
    text = src.read_text(encoding="utf-8", errors="ignore")
    fixed = text.lstrip().startswith("// layout: neato-fixed")
    if fixed:
        neato = shutil.which("neato")
        if not neato:
            return False, "graphviz neato not found"
        cmd = [neato, "-n", "-Tsvg", str(src), "-o", str(out)]
    else:
        cmd = [dot, "-Tsvg", str(src), "-o", str(out)]
    proc = subprocess.run(
        cmd,
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip()
    return True, "ok"


def main() -> int:
    if not DIAGRAMS.exists():
        print(f"no diagrams directory: {DIAGRAMS}")
        return 1
    force = "--force" in sys.argv[1:]
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    mmd = sorted(DIAGRAMS.rglob("*.mmd"))
    dot = sorted(DIAGRAMS.rglob("*.dot"))
    if only:
        wanted = {Path(p).stem for p in only}
        mmd = [p for p in mmd if p.stem in wanted]
        dot = [p for p in dot if p.stem in wanted]
    failures = 0
    skipped = 0
    for src in mmd:
        out = src.with_suffix(".svg")
        if not force and out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
            skipped += 1
            continue
        ok, msg = render_mermaid(src, out)
        print(f"{'OK ' if ok else 'FAIL'} {src.relative_to(ROOT)} -> {out.name} ({msg})")
        failures += 0 if ok else 1
    for src in dot:
        out = src.with_suffix(".svg")
        if not force and out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
            skipped += 1
            continue
        ok, msg = render_dot(src, out)
        print(f"{'OK ' if ok else 'FAIL'} {src.relative_to(ROOT)} -> {out.name} ({msg})")
        failures += 0 if ok else 1
    print(f"\n{len(mmd)} mermaid, {len(dot)} graphviz, {failures} failure(s), {skipped} up-to-date")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
