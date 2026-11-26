#!/usr/bin/env python3
"""渐进稿画布溢出检查（D57 版式 QA）。

对每链 spread.html 做程序化检查（模型看不了图，用 DOM 度量代替目测）：
1. 每个 .page 内的元素包围盒不得越出页面矩形（top/bottom/left/right）；
2. overflow:hidden 容器不得有内容被裁（scrollHeight/scrollWidth 超出）；
3. .grid2 四格高度一致、v1→v4 顺序完整。

用法：python3 check_spread.py [链…]   # 默认检查所有有 spread.html 的链
退出码：0 全部通过；1 有溢出/裁切。
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "materials/design/decision-growth"

QA_JS = """
<script>
window.addEventListener('load', () => {
  const problems = [];
  document.querySelectorAll('.page').forEach((page, pi) => {
    const pr = page.getBoundingClientRect();
    const clipped = [];
    page.querySelectorAll('*').forEach(el => {
      if (el.closest('.foot') || el.classList.contains('foot')) return;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return;
      const over = [];
      if (r.bottom > pr.bottom + 1) over.push('bottom+' + Math.round(r.bottom - pr.bottom));
      if (r.top < pr.top - 1) over.push('top+' + Math.round(pr.top - r.top));
      if (r.right > pr.right + 1) over.push('right+' + Math.round(r.right - pr.right));
      if (r.left < pr.left - 1) over.push('left+' + Math.round(pr.left - r.left));
      if (over.length) {
        const txt = (el.textContent || el.tagName).trim().slice(0, 24);
        clipped.push(el.tagName + '.' + el.className + ' [' + over.join(',') + '] «' + txt + '»');
      }
      const cs = getComputedStyle(el);
      if (cs.overflow === 'hidden' || cs.overflowY === 'hidden') {
        if (el.scrollHeight > el.clientHeight + 2)
          clipped.push('CUT ' + el.tagName + '.' + el.className + ' scrollH ' + el.scrollHeight + ' > clientH ' + el.clientHeight);
        if (el.scrollWidth > el.clientWidth + 2)
          clipped.push('CUT ' + el.tagName + '.' + el.className + ' scrollW ' + el.scrollWidth + ' > clientW ' + el.clientWidth);
      }
    });
    if (clipped.length) problems.push('page' + (pi + 1) + ': ' + clipped.join(' | '));
  });
  const cells = document.querySelectorAll('.grid2 .vcell');
  if (cells.length !== 4) problems.push('grid2 cells = ' + cells.length + ' (应为 4)');
  const hs = [...cells].map(c => Math.round(c.getBoundingClientRect().height));
  if (hs.length === 4 && Math.max(...hs) - Math.min(...hs) > 2) problems.push('cell 高度不齐: ' + hs.join(','));
  // 内容完整性：Python dict repr 乱码、明显截断（孤立未闭括号）
  const bodyText = document.body.innerText;
  if (bodyText.includes("{'") || bodyText.includes(String.fromCharCode(92,39))) problems.push('BAD-REPR: 渲染出 Python dict 样式乱码');
  document.querySelectorAll('.unknown, .ev .out, .vfail, .cmd').forEach(el => {
    const t = el.textContent || '';
    const open = (t.match(/（/g) || []).length, close = (t.match(/）/g) || []).length;
    if (open !== close) problems.push('BAD-PARENS: «' + t.trim().slice(0, 30) + '…» 括号未闭合');
    if (/…?$/.test(t.trim()) === false && t.trim().endsWith('PRD')) problems.push('BAD-CUT: «' + t.trim().slice(-20) + '» 疑似截断');
  });
  const badges = [...cells].map(c => c.querySelector('.vbadge') ? c.querySelector('.vbadge').textContent.trim() : '?');
  problems.push('BADGES: ' + badges.join(' → '));
  const out = problems.join('\\n');
  const bad = problems.filter(p => !p.startsWith('BADGES'));
  document.title = 'QA-RESULT:' + (bad.length ? 'FAIL' : 'PASS');
  const pre = document.createElement('pre');
  pre.id = 'qa-result';
  pre.textContent = out;
  document.body.appendChild(pre);
});
</script>
"""


def check(chain: str) -> bool:
    html_path = BASE / chain / "spread.html"
    if not html_path.exists():
        print(f"{chain}: 缺 spread.html")
        return False
    html = html_path.read_text(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp()) / f"qa-{chain}.html"
    tmp.write_text(html.replace("</body>", QA_JS + "</body>"), encoding="utf-8")
    r = subprocess.run(
        ["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--allow-file-access-from-files", "--force-device-scale-factor=1",
         "--window-size=3200,1170", "--virtual-time-budget=4000", "--dump-dom", tmp.as_uri()],
        capture_output=True, text=True, timeout=120,
    )
    m = re.search(r'id="qa-result">(.*?)</pre>', r.stdout, re.S)
    title = re.search(r"<title>(.*?)</title>", r.stdout, re.S)
    ok = bool(title and "QA-RESULT:PASS" in title.group(1))
    print(f"== {chain}: {'PASS' if ok else 'FAIL'}")
    if m:
        for line in m.group(1).strip().splitlines():
            print("  " + line)
    else:
        print("  (没有拿到 QA 结果块)")
        ok = False
    return ok


def main() -> int:
    chains = sys.argv[1:] or sorted(p.parent.name for p in BASE.glob("*/spread.html"))
    if not chains:
        print("没有可检查的链")
        return 1
    results = [check(c) for c in chains]
    print(f"溢出检查：{sum(results)}/{len(results)} 通过")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
