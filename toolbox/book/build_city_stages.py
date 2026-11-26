#!/usr/bin/env python3
"""生成「五级城市」可编辑页首图：L1–L4 + L5 装修。

固定画布 1600×1000；所有文字是实时 HTML；editor.html 由 editable-design 的
wire-editor 生成。输出：
  toolbox/book/city-stages/index.html
  toolbox/book/city-stages/editor.html
  toolbox/book/city-stages/poster.json
  toolbox/book/city-stages/out/poster.png
  tutorial/images/city-5stages.png
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJ = Path(__file__).resolve().parent / "city-stages"
SKILL = Path.home() / ".agents" / "skills" / "editable-design"
W, H = 1600, 1000

STAGES = [
    dict(level="L1", action="造", name="荒地工地", sub="只有围挡和毛坯，能站人不能用", cross="骨架", pages="P00–P09",
         action_text="先造骨架：每章一个设施，看到它能跑。", deliver="一座能问数的城", stats=[("10 章", "P0–P9"), ("3 座", "P1/P3/P9"), ("12 件", "空心徽章")], chapters=["P0 环境", "P1 容器", "P2 数据", "P3 服务", "P9 入口"], judge="make doctor 12/12 · 浏览器 8081 = 41099.5", evidence=["$ make doctor", "12/12 · 3307/8000/8081 空着", "浏览器 8081 → 41099.5"], state="draft"),
    dict(level="L2", action="换", name="通水电网", sub="楼立起来、水电管网接通", cross="数据与部署的真实性", pages="P10–P13",
         action_text="把演示件换成真件：数据 / 契约 / 执行器 / 部署。", deliver="真数据 · 真契约 · 真执行器", stats=[("4 章", "P10–P13"), ("2 条", "水电管网"), ("4/4", "接线点")], chapters=["P10 真数据", "P11 契约", "P12 执行器", "P13 部署"], judge="S1 PASS → S3 PASS · DOCKER SMOKE PASS", evidence=["$ make docker-smoke", "S1 / S2 / S3 PASS", "DOCKER SMOKE PASS"], state="wired"),
    dict(level="L3", action="审", name="智慧城市", sub="城市大脑上线：会看、会算、会自查", cross="生成与校验的正确性", pages="P14–P17",
         action_text="先写判据，再让机器去撞。", deliver="检索 · 生成 · 校验 · 纠错", stats=[("4 章", "P14–P17"), ("9 路", "数据流"), ("4/4", "接线点")], chapters=["P14 检索", "P15 生成", "P16 校验", "P17 纠错"], judge="S3 PASS · 26 passed · S6 PASS", evidence=["$ make stage3", "41 passed · S3 PASS", "26 passed · S6 PASS"], state="smart"),
    dict(level="L4", action="守", name="城市安防", sub="门禁、城管、监控、应急都到位", cross="安全、可观测、可运维", pages="P18–P22",
         action_text="把防线拆掉，看哪条判据变红。", deliver="只读 · 策略 · 取消 · 观测 · 回归", stats=[("5 章", "P18–P22"), ("6 个", "摄像头"), ("5/5", "接线点")], chapters=["P18 账号", "P19 策略", "P20 取消", "P21 观测", "P22 回归"], judge="S5 PASS · S6 PASS · S7 PASS", evidence=["$ make stage5", "36/36 · 11/11 · S5 PASS", "S7 PASS · 14 夹具"], state="secure"),
    dict(level="L5", action="装", name="装修", sub="只换前端门面，不换承重墙", cross="体验层（不新增设施）", pages="P23",
         action_text="换成熟前端入口，仍问同一个数。", deliver="8088 成熟版 + 8080 教学版 = 41099.5", stats=[("1 章", "P23"), ("3 个", "入口"), ("41099.5", "同一个数")], chapters=["P23 装修"], judge="8088 = 41099.5 · 8080 = 41,099.5", evidence=["$ docker run …8088", "41099.5（成熟版）", "41,099.5（教学版）"], state="front"),
]


def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def diagram(stage):
    # 四区 + 设施点的极简城市示意图；所有文字/标记仍可另加，不乱画地图。
    zones = [("市政", "场"), ("仓储", "仓"), ("服务", "楼"), ("门户", "门")]
    dots = {
        "draft": [], "wired": [(1, 2), (2, 1), (3, 1)], "smart": [(0, 1), (1, 2), (2, 2), (3, 1)],
        "secure": [(0, 1), (1, 2), (2, 2), (3, 1), (2, 0)], "front": [(3, 2)],
    }[stage["state"]]
    z = "".join(f'<div class="zone"><span>{esc(n)}</span><small>{esc(t)}</small></div>' for n, t in zones)
    ds = "".join(f'<i class="dot" style="left:{18+x*27}%;top:{12+y*31}%"></i>' for x, y in dots)
    label = {"draft": "围挡 / 毛坯", "wired": "楼体 / 管网", "smart": "数据流 / 大脑", "secure": "门禁 / 监控", "front": "入口 / 门面"}[stage["state"]]
    return f'<div class="mini" data-layer-id="mini-{stage["level"]}"><div class="zones">{z}{ds}</div><div class="mini-cap">{esc(label)}</div></div>'


def main() -> int:
    panels = []
    for s in STAGES:
        stats = "".join(f'<div><b>{esc(v)}</b><span>{esc(l)}</span></div>' for v, l in s["stats"])
        panels.append(f'''<section class="stage stage-{s["level"].lower()}" data-layer-id="stage-{s["level"]}">
<div class="stage-upper">
<div class="stage-top"><span class="badge">{s["level"]}</span><span class="action">{s["action"]}</span><span class="pages">{s["pages"]}</span></div>
<h2>{esc(s["name"])}</h2><p class="sub">{esc(s["sub"])}</p>
{diagram(s)}
<div class="row"><span>横切</span><b>{esc(s["cross"])}</b></div>
<div class="row"><span>学生</span><b>{esc(s["action_text"])}</b></div>
</div>
<div class="stage-lower">
<div class="deliver">{esc(s["deliver"])}</div>
<div class="chips">{''.join(f'<span class="chip">{esc(c)}</span>' for c in s["chapters"])}</div>
<div class="judge"><span>判据</span>{esc(s["judge"])}</div>
<div class="evidence"><div class="ev-h">关键命令 / 输出</div>{''.join(f'<div>{esc(e)}</div>' for e in s["evidence"])}</div>
<div class="stats">{stats}</div>
</div>
</section>''')
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>五级城市 · 从荒地到装修</title>
<style>
:root {{ --ink:#1f1b16; --muted:#6b6254; --paper:#fbf7ee; --line:#d9cfbd; --accent:#c2410c; --sans:"Noto Sans CJK SC",sans-serif; --mono:"Noto Sans Mono CJK SC",monospace; }}
* {{ box-sizing:border-box; }} html,body {{ margin:0; padding:0; background:#e8e2d7; }}
.poster {{ position:relative; width:{W}px; height:{H}px; background:var(--paper); color:var(--ink); font-family:var(--sans); overflow:hidden; }}
.head {{ position:absolute; left:40px; right:40px; top:28px; height:96px; border-bottom:2px solid var(--ink); }}
.kicker {{ margin:0; font-family:var(--mono); font-size:13px; font-weight:700; letter-spacing:1.2px; color:var(--accent); }}
h1 {{ margin:8px 0 0; font-size:38px; line-height:1.1; letter-spacing:-.5px; }}
.subtitle {{ margin:8px 0 0; color:var(--muted); font-size:16px; }}
.grid {{ position:absolute; left:40px; right:40px; top:140px; display:grid; grid-template-columns:repeat(5,1fr); gap:10px; height:710px; }}
.stage {{ position:relative; border:1.5px solid var(--ink); background:#fffdf8; overflow:hidden; }}
.stage-upper {{ position:absolute; left:0; right:0; top:0; height:360px; padding:12px 12px 0; }}
.stage-lower {{ position:absolute; left:12px; right:12px; top:360px; bottom:0; border-top:1px solid var(--line); padding-top:8px; }}
.stage-l5 {{ background:#fff3e8; border-color:var(--accent); }}
.stage-top {{ display:flex; align-items:center; gap:7px; }}
.badge {{ font-family:var(--mono); font-size:12px; font-weight:800; background:var(--ink); color:#fff; padding:2px 6px; }}
.action {{ font-size:26px; font-weight:900; color:var(--accent); }}
.pages {{ margin-left:auto; font-family:var(--mono); font-size:10px; color:var(--muted); }}
h2 {{ margin:8px 0 0; font-size:25px; line-height:1.1; }}
.sub {{ margin:5px 0 0; font-size:12px; line-height:1.4; color:var(--muted); min-height:34px; }}
.mini {{ margin-top:6px; border:1px solid var(--line); padding:6px; background:#f7f2e7; height:150px; }}
.zones {{ position:relative; display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:3px; height:112px; }}
.zone {{ border:1px dashed #b9ad96; padding:4px; font-size:9px; color:#756b5a; }}
.zone small {{ display:block; font-size:8px; color:#a49882; }}
.dot {{ position:absolute; width:8px; height:8px; border-radius:50%; background:var(--accent); border:1px solid #fff; transform:translate(-50%,-50%); }}
.mini-cap {{ margin-top:4px; font-family:var(--mono); font-size:9px; color:var(--accent); }}
.row {{ display:flex; gap:5px; margin-top:7px; font-size:10px; line-height:1.35; }}
.row span {{ flex:0 0 26px; color:var(--accent); font-weight:700; }}
.row b {{ font-weight:500; color:#3e362b; }}
.deliver {{ margin-top:6px; border-top:1px solid var(--line); padding-top:5px; font-size:10px; line-height:1.35; color:#2e2922; }}
.chips {{ display:flex; flex-wrap:wrap; gap:3px; margin-top:7px; }}
.chip {{ border:1px solid #d6cbb7; padding:2px 4px; font-size:8px; line-height:1.2; color:#594f41; background:#faf6ee; }}
.judge {{ margin-top:7px; border-top:1px solid var(--line); padding-top:5px; font-size:9px; line-height:1.35; color:#c2410c; }}
.judge span {{ font-weight:800; margin-right:4px; }}
.evidence {{ margin-top:7px; border-top:1px dashed var(--line); padding-top:5px; font-family:var(--mono); font-size:8px; line-height:1.45; color:#4a4135; }}
.ev-h {{ color:var(--accent); font-weight:700; margin-bottom:2px; }}
.stats {{ position:absolute; left:0; right:0; bottom:8px; display:flex; gap:3px; }}
.stats div {{ flex:1; border-top:1px solid var(--line); padding-top:4px; text-align:center; }}
.stats b {{ display:block; font-size:13px; }}
.stats span {{ display:block; font-size:8px; color:var(--muted); }}
.foot {{ position:absolute; left:40px; right:40px; bottom:22px; border-top:1.5px solid var(--ink); padding-top:8px; display:flex; justify-content:space-between; font-size:11px; color:var(--muted); }}
.foot b {{ color:var(--ink); }}
</style></head><body><div class="poster" data-canvas-width="{W}" data-canvas-height="{H}">
<div class="head" data-layer-id="head"><p class="kicker">D44 × D45 × D50 · 同一片城区 · 同一座标</p><h1>五级，从荒地工地到能交付的装修</h1>
<p class="subtitle">前四级是同一座城的四套横切系统；L5 不新增设施，只换前端入口。<b>24 章 = L1–L4 的 23 章 + L5 的 1 章。</b></p></div>
<div class="grid" data-layer-id="grid">{''.join(panels)}</div>
<div class="foot" data-layer-id="foot"><span><b>L5 不是第五座楼</b>：不新增设施、不改接口 / 契约 / SSE，只换入口；同一问仍出 41099.5。</span><span>城市只借骨架，不借结论 · 页章对照见附录 A</span></div>
</div></body></html>'''
    PROJ.mkdir(parents=True, exist_ok=True)
    (PROJ / "index.html").write_text(html, encoding="utf-8")
    (PROJ / "poster.json").write_text('{"canvas":{"width":1600,"height":1000}}\n', encoding="utf-8")
    subprocess.run(["node", str(SKILL/"scripts"/"wire-editor.mjs"), str(PROJ/"index.html")], check=True, capture_output=True, text=True)
    (PROJ / "out").mkdir(exist_ok=True)
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--window-size=1600,1000",
                    f"--screenshot={PROJ/'out'/'poster.png'}", (PROJ/"index.html").as_uri()],
                   check=True, capture_output=True)
    subprocess.run(["convert", str(PROJ/"out"/"poster.png"), "-resize", "3200x2000", str(ROOT/"tutorial"/"images"/"city-5stages.png")], check=True, capture_output=True)
    print(f'city stages: {PROJ}  image: {ROOT/"tutorial/images/city-5stages.png"}')
    return 0

if __name__ == "__main__":
    sys.exit(main())
