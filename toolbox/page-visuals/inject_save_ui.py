#!/usr/bin/env python3
"""给 editable-design 生成的 editor.html 注入「另存为 / 覆盖保存」按钮脚本。"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
TAG = '<script src="../_shared/editor-save-ui.js"></script>'
pages = [a.zfill(2) for a in sys.argv[1:]] or [p.name.removeprefix('page-') for p in (ROOT/'manual'/'designs').glob('page-*')]
n = 0
for page in pages:
    p = ROOT/'toolbox'/'page-visuals'/f'page-{page}'/'editor.html'
    if not p.is_file():
        continue
    s = p.read_text(encoding='utf-8')
    if TAG in s:
        continue
    if '</body>' not in s:
        print(f'page-{page}: no </body>'); continue
    s = s.replace('</body>', TAG + '\n</body>', 1)
    p.write_text(s, encoding='utf-8'); n += 1
print(f'injected {n} editor(s)')
