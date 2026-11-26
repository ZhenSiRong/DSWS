#!/usr/bin/env python3
"""决策生长（design-doc-growth）渐进稿生成器（D57 版式）。

数据驱动：每链一份 materials/design/decision-growth/<chain>/data.yaml，
本脚本渲染 spread.html，--render 时再用 Chrome 出 PNG 并转 PDF。

版式（D57）：左页 2×2 四格、Z 字阅读 v1→v2→v3→v4（每格：做法 + 被什么打脸 +
补上了什么；v4 格标「当前」）+ 编撰声明；右页终态设计 + 证据 + 可重跑命令。

用法：
  python3 make_decision_growth.py                 # 渲染所有已有 data.yaml 的链
  python3 make_decision_growth.py security contract
  python3 make_decision_growth.py --render [链…]  # 渲染 HTML 并出 PNG/PDF
"""
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "materials/design/decision-growth"

DEFAULT_ASSUME = (
    "编撰声明：这些版本是教学重构（D57），不是 commit 历史或逐日日记；"
    "终态由右页代码/契约锚定，后续 reconciler 只改叙事、不改源码/配置。"
)

CSS = """
:root { --ink:#211b15; --muted:#6f6557; --paper:#fbf7ee; --line:#d9cebb; --red:#a9362a; --green:#2f5d46; --orange:#c2410c; --mono:"Noto Sans Mono CJK SC",monospace; --sans:"Noto Sans Mono CJK SC","Noto Sans CJK SC",sans-serif; }
* { box-sizing:border-box; } html,body { margin:0; background:#ddd6c7; }
.spread { position:relative; width:3200px; height:1170px; background:#ddd6c7; font-family:var(--sans); color:var(--ink); overflow:hidden; }
.page { position:absolute; top:25px; width:1540px; height:1120px; background:var(--paper); padding:34px 42px 28px; overflow:hidden; }
.page.one { left:25px; } .page.two { left:1610px; }
.page.two h1 { font-size:44px; }
.page:after { content:attr(data-page); position:absolute; right:28px; bottom:16px; font-family:var(--mono); font-size:10px; color:var(--muted); }
.kicker { margin:0; font-family:var(--mono); font-size:14px; font-weight:700; color:var(--orange); letter-spacing:1.3px; }
.kicker span { border:1px solid var(--orange); padding:2px 6px; margin-left:7px; }
h1 { margin:10px 0 0; font-size:50px; line-height:1.08; letter-spacing:-.5px; }
.lead { margin:12px 0 0; font-size:18px; line-height:1.55; color:var(--muted); }
.rule { height:2px; background:var(--ink); margin:18px 0 14px; }
/* page one — 2×2 生长格（D57） */
.grid2 { display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:12px; margin-top:4px; height:770px; }
.vcell { border:1px solid var(--line); background:#fffdf8; padding:14px 16px 12px; position:relative; display:flex; flex-direction:column; }
.vcell:before { content:""; position:absolute; left:-1px; top:0; bottom:0; width:6px; background:var(--red); }
.vcell.v2:before { background:#b7791f; } .vcell.v3:before { background:#8a6d3b; } .vcell.v4:before { background:var(--green); }
.vbadge { font-family:var(--mono); font-size:17px; font-weight:800; color:#fff; background:var(--red); padding:3px 10px; align-self:flex-start; }
.vcell.v2 .vbadge { background:#b7791f; } .vcell.v3 .vbadge { background:#8a6d3b; } .vcell.v4 .vbadge { background:var(--green); }
.vbody h3 { margin:10px 0 0; font-size:22px; line-height:1.2; }
.vbody p { margin:6px 0 0; font-size:13px; line-height:1.5; color:#4a4135; }
.vfail { margin-top:8px; font-size:12px; line-height:1.45; color:var(--red); }
.vadd { margin-top:auto; padding-top:8px; border-top:1px dashed var(--line); font-size:12px; line-height:1.45; color:var(--green); }
.vadd b { display:block; font-family:var(--mono); font-size:9px; color:var(--muted); margin-bottom:2px; }
.assume { margin-top:12px; border-top:2px solid var(--ink); padding-top:7px; font-size:10.5px; line-height:1.5; color:var(--muted); }
.assume b { color:var(--ink); }
.foot { position:absolute; left:42px; right:42px; bottom:8px; border-top:1px solid var(--line); padding-top:6px; font-size:9px; line-height:1.45; color:var(--muted); font-family:var(--mono); }
/* page two */
.answer { margin-top:12px; border-left:6px solid var(--green); background:#f1f6ef; padding:12px 14px; font-size:21px; line-height:1.4; font-weight:800; }
.answer small { display:block; font-size:12px; font-weight:400; color:var(--muted); margin-top:4px; }
.p2grid { display:grid; grid-template-columns:690px 1fr; gap:14px; margin-top:11px; }
.figure { border:1px solid var(--line); background:#fff; padding:5px; }
.figure img { width:auto; max-width:100%; max-height:520px; display:block; margin:0 auto; }
.figcap { margin-top:4px; font-size:10px; line-height:1.4; color:#443b2f; }
.evidence { display:flex; flex-direction:column; gap:7px; }
.ev { border:1px solid var(--line); background:#fffdf8; padding:8px 10px; }
.ev .tag { font-family:var(--mono); font-size:8px; color:var(--red); }
.ev h3 { margin:3px 0 0; font-size:14px; line-height:1.2; } .ev p { margin:3px 0 0; font-size:10px; line-height:1.35; color:#4a4135; }
.ev .out { margin-top:4px; border-top:1px dashed var(--line); padding-top:3px; font-family:var(--mono); font-size:8.5px; line-height:1.35; color:var(--ink); }
.checks { margin-top:10px; border:1px solid var(--ink); background:#fff; padding:8px 10px; display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.checks h3 { margin:0 0 3px; font-size:13px; } .checks .cmd { font-family:var(--mono); font-size:8.5px; line-height:1.45; }
.unknown { margin-top:8px; border:1px dashed #d2b5ae; padding:7px 9px; background:#fff8f4; font-size:10px; line-height:1.4; color:#5b473c; }
.unknown b { color:var(--red); }
.take { margin-top:8px; background:var(--ink); color:#fff; padding:8px 11px; font-size:16px; line-height:1.35; font-weight:800; }
.tags { display:flex; gap:4px; flex-wrap:wrap; margin-top:6px; } .tg { font-family:var(--mono); font-size:7.5px; border:1px solid var(--line); color:var(--muted); padding:1px 4px; }
"""


def render(chain: str, d: dict) -> Path:
    versions = d["versions"]
    assert len(versions) == 4, f"{chain}: versions 必须恰好 4 个（v1–v4），实际 {len(versions)}"
    cells = []
    for i, v in enumerate(versions):
        cls = f"v{i + 1}"
        badge = v["badge"]
        if i == 3:
            badge += " · 当前"
        cells.append(
            f'<div class="vcell {cls}"><div class="vbadge">{badge}</div>'
            f'<div class="vbody"><h3>{v["name"]}</h3><p>{v["desc"]}</p>'
            f'<div class="vfail">被打脸：{v["fail"]}</div></div>'
            f'<div class="vadd"><b>补上</b>{v["add"]}</div></div>'
        )
    ev = "".join(
        f'<div class="ev"><div class="tag">{a}</div><h3>{b}</h3><p>{c}</p><div class="out">{o}</div></div>'
        for a, b, c, o in d["ev"]
    )
    checks = "".join(f'<div class="cmd">{x}</div>' for x in d["checks"])
    tags = "".join(f'<span class="tg">{t.strip()}</span>' for t in d["tags"].split("  ") if t.strip())
    figuri = (ROOT / d["fig"]).resolve().as_uri()
    assume = d.get("assume", DEFAULT_ASSUME)
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{d['title']}</title><style>{CSS}</style></head><body><div class="spread">
<section class="page one" data-page="{d['kicker']} · 1/2"><p class="kicker">{d['kicker']}<span>渐进稿</span></p><h1>{d['growth']}</h1><p class="lead">{d.get('lead', '左页看设计怎么长出来：每一格是「做法 → 被什么打脸 → 补上了什么」；右页才是今天的设计与证据。')}</p><div class="rule"></div>
<div class="grid2">{''.join(cells)}</div>
<div class="assume"><b>{assume}</b></div>
<div class="foot">来源：{d['sources']}<br>左页只负责“怎么长出来”；右页是终态设计 + 本地证据 + 可重跑命令。</div></section>
<section class="page two" data-page="{d['kicker']} · 2/2"><p class="kicker">{d['kicker']}<span>证据与落地</span></p><h1>{d.get('answer_title', d['title'])}</h1><div class="answer">{d['answer']}<small>{d['answer_small']}</small></div>
<div class="p2grid"><div><div class="figure"><img src="{figuri}" alt="设计图"><div class="figcap">{d['figcap']}</div></div></div><div class="evidence">{ev}</div></div>
<div class="checks"><div><h3>今天怎么验</h3>{checks}</div><div><h3>证据状态</h3><div class="cmd">{tags}</div></div></div>
<div class="unknown"><b>未知 / 反悔点：</b>{d['unknown']}</div><div class="take">{d['take']}</div>
<div class="foot">来源：{d['sources']}<br>右页：一张设计图 + 一组本地证据 + 可重跑命令；没有证据的“行业惯例”不进来。</div></section>
</div></body></html>"""
    out = BASE / chain
    out.mkdir(parents=True, exist_ok=True)
    (out / "spread.html").write_text(html, encoding="utf-8")
    return out / "spread.html"


def render_png_pdf(chain: str) -> None:
    out = BASE / chain
    png, pdf, html = out / "spread.png", out / "spread.pdf", out / "spread.html"
    subprocess.run(
        ["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--allow-file-access-from-files", "--force-device-scale-factor=1.25",
         "--window-size=3200,1170", f"--screenshot={png}", html.as_uri()],
        check=True, capture_output=True, timeout=120,
    )
    subprocess.run(["convert", str(png), str(pdf)], check=True, capture_output=True, timeout=60)
    print(f"{chain}: {png} + {pdf}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    do_render = "--render" in sys.argv
    chains = args or sorted(p.parent.name for p in BASE.glob("*/data.yaml"))
    if not chains:
        print("没有找到任何 data.yaml", file=sys.stderr)
        return 1
    for chain in chains:
        data_file = BASE / chain / "data.yaml"
        if not data_file.exists():
            print(f"{chain}: 缺 {data_file}", file=sys.stderr)
            return 1
        d = yaml.safe_load(data_file.read_text(encoding="utf-8"))
        path = render(chain, d)
        print(path)
        if do_render:
            render_png_pdf(chain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
