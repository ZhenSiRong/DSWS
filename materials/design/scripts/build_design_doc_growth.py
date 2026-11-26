#!/usr/bin/env python3
"""整份设计文档组版（D56）：A 类 5 链渐进稿 + A 类图页 + 文字章节 → design-doc.pdf。

组成（≥30 页，不含 B/C 类图页）：
  p1 封面 · p2 目录/读法 · p3 prd 四要素映射 · p4 生长总览
  · 5 链 × 2 页渐进稿（spread 左右半页）· A 类图一图一页
  · 每链 claims/证据摘要一页 · 未知汇总 · 命令汇总 · 术语表

用法：python3 build_design_doc_growth.py           # 组版到 materials/design/design-doc.pdf
      python3 build_design_doc_growth.py --check   # 只算页数/构成，不写 PDF
"""
from pathlib import Path
import html
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "materials/design/decision-growth"
DIAG = ROOT / "materials/design/diagrams"
OUT = ROOT / "materials/design/design-doc.pdf"

CHAINS = ["correction", "security", "contract", "runtime", "journey"]
CHAIN_CN = {
    "correction": "纠错链", "security": "安全链", "contract": "契约链",
    "runtime": "运行链", "journey": "用户旅程设计",
}
# A 类图（9 张既有 + 用户旅程图在 journey 链内），一图一页
A_FIGS = [
    ("02-runtime/12-s6-correction-state.svg", "图 12 · S6 校正闭环状态机（纠错链）"),
    ("06-testing/31-failure-injection.svg", "图 31 · 失败注入矩阵（纠错链）"),
    ("04-security/22-sql-policy-flow.svg", "图 22 · SQL 策略六关（安全链）"),
    ("04-security/23-readonly-grants.svg", "图 23 · dw_reader 只读账号（安全链）"),
    ("04-security/24-error-taxonomy.svg", "图 24 · 16 错误码 / 3 class（安全链）"),
    ("03-data/15-contract-model.svg", "图 15 · 契约模型（契约链）"),
    ("03-data/16-three-store-layout.svg", "图 16 · 契约→三存储（契约链）"),
    ("03-data/19-value-domain-decision.svg", "图 19 · 值域决策树（契约链）"),
    ("05-deployment/27-startup-order.svg", "图 27 · 启动顺序与失败停点（运行链）"),
]

CSS = """
@page { size: A4 landscape; margin: 12mm 12mm 10mm; }
@page cover { margin: 0; }
body { font-family:"Noto Sans CJK SC",sans-serif; color:#211b15; font-size:10.5pt; line-height:1.5; }
h1 { font-size:22pt; margin:0 0 6mm; } h2 { font-size:14pt; margin:0 0 4mm; }
table { border-collapse:collapse; width:100%; font-size:8.6pt; }
th,td { border:0.4pt solid #b9ab93; padding:1.6mm 2mm; vertical-align:top; }
th { background:#efe7d6; text-align:left; }
.cover { page:cover; height:210mm; background:#2c2620; color:#f5efe2; padding:28mm 24mm; }
.cover h1 { font-size:30pt; color:#fff; } .cover .sub { font-size:13pt; color:#d9cdb7; margin-top:6mm; }
.cover .meta { position:absolute; bottom:20mm; left:24mm; right:24mm; font-size:9.5pt; color:#bfb39c; }
img.spread-half { width:100%; display:block; border:0.4pt solid #cfc2ab; }
.figwrap { text-align:center; } .figwrap img { max-width:100%; max-height:150mm; }
.figcap { font-size:8.5pt; color:#6f6557; margin-top:2mm; }
.foot { font-size:8pt; color:#8a7c66; margin-top:3mm; }
.pagebreak { page-break-after: always; }
.chip { display:inline-block; border:0.4pt solid #b9ab93; padding:0 1.4mm; margin-right:1.4mm; font-size:8pt; }
"""


def half_images(chain: str, tmp: Path) -> tuple[Path, Path]:
    png = BASE / chain / "spread.png"
    left, right = tmp / f"{chain}-L.png", tmp / f"{chain}-R.png"
    for src, dst, off in ((png, left, "+0+0"), (png, right, "+1600+0")):
        subprocess.run(["convert", str(src), "-crop", "1600x1170" + off, "+repage", str(dst)],
                       check=True, capture_output=True, timeout=60)
    return left, right


def page_quickref() -> str:
    return """<h1>速查 · 阅读顺序 / 术语三件套 / 参数表</h1>
<h2>阅读顺序（= 本卷装订顺序）</h2>
<p><b>纠错链 → 安全链 → 契约链 → 运行链 → 用户旅程设计</b>：先看失败怎么被有边界地补考，再看 SQL 为什么必须不被信任，
然后是契约怎么防漂移、启动怎么防假绿，最后把全程旅程串起来。
guard / policy / dw_reader 的定义见下表（纠错链里直接用的 guard / policy 就是这里的两道关），不必先跳读。</p>
<h2>术语三件套（安全链定义，全书通用）</h2>
<table><tr><th>术语</th><th>一句话</th></tr>
<tr><td>guard（静态检查）</td><td>SQL 还没进语义层就被拦的粗筛：单语句、只读、表列存在等。</td></tr>
<tr><td>policy（安全策略）</td><td>AST 逐关复查 + 白名单 + 自动 LIMIT；拒绝不连库。</td></tr>
<tr><td>dw_reader（只读账号）</td><td>执行器专用数据库账号，只有 SELECT——策略被绕过时的兜底。</td></tr></table>
<h2>参数表（都是当前值，不是设计原则）</h2>
<table><tr><th>参数</th><th>值</th><th>在哪</th></tr>
<tr><td>补考上限 N（correction.max_attempts）</td><td>1</td><td>errors.yaml；纠错链 / 旅程链</td></tr>
<tr><td>init 轮询间隔 / 上限</td><td>2s / 180s</td><td>运行链（docker_init）</td></tr>
<tr><td>低基数阈值（值域分类）</td><td>1000（不同取值 ≤1000 的列才把完整值同步 ES；与自动 LIMIT 无关）</td><td>契约链</td></tr>
<tr><td>安全关卡 / 错误码</td><td>AST 六关；16 码 = 6 可重试 + 10 不可重试（6 码名见纠错链 v2）</td><td>安全链 / errors.yaml</td></tr>
<tr><td>自动 LIMIT</td><td>1000（无 LIMIT 自动补；超限截到 1000；与低基数阈值无关）[当前值]</td><td>安全链 / sql.policy.yaml</td></tr>
<tr><td>工作流</td><td>12 节点 / 10 步（第 2 阶段召回含 3 节点；correct_sql 为条件节点）</td><td>旅程链 / steps.yaml</td></tr></table>
<div class="foot">三问速答索引：每链右页「今天怎么验」给可敲命令；「拆掉什么会红」见各链拆一刀（未跑的已在命令行内标注）。命令入口 uv run --frozen python 与 .venv/bin/python 任选其一。</div>
<div class="pagebreak"></div>"""


def page_cover() -> str:
    return f"""<section class="cover"><h1>电商问数智能体系统<br>设计文档 · 决策生长版</h1>
<div class="sub">A 类 5 条链：设计是怎么长出来的 —— 渐进稿 + 终态证据<br>锚定 prd：自然语言问数 NL2SQL · LangGraph 12 节点 10 步 · validate_sql + correct_sql 双保险 · React 19 + Tailwind 前端</div>
<div class="meta">范围（D56）：A 类 5 链渐进稿合入本卷，B/C 类图不入卷 · 版式与编撰口径（D57）：2×2 v1–v4 + 编撰声明<br>
生成：materials/design/scripts/build_design_doc_growth.py · 链产物：materials/design/decision-growth/</div></section><div class="pagebreak"></div>"""


def page_toc(data: dict) -> str:
    rows = "".join(
        f"<tr><td>{CHAIN_CN[c]}</td><td>{html.escape(data[c]['growth'])}</td>"
        f"<td>{html.escape(data[c]['answer'])}</td></tr>"
        for c in CHAINS if c in data)
    return f"""<h1>目录与读法</h1>
<h2>读法：每条链两页</h2>
<p><b>左页 = 生长（v1→v4，Z 字阅读）</b>：每一格是「做法 → 被什么打脸 → 补上了什么」，v4 格是当前设计。
版本叙事是<b>教学编撰</b>（带编撰声明），不是 commit 历史。<br>
<b>右页 = 终态与证据</b>：今天的设计一张图 + 三组本地证据 + 可重跑命令 + 未知/反悔点。结论只认右页的锚定。</p>
<h2>五条链一览</h2>
<table><tr><th>链</th><th>它在回答的问题（左页标题）</th><th>今天的答案</th></tr>{rows}</table>
<div class="foot">本卷结构：封面 · 目录 · prd 映射 · 生长总览 · 5 链 × 2 页 · A 类图页 · 每链 claim 摘要 · 未知/命令/术语汇总。</div>
<div class="pagebreak"></div>"""


def page_prd() -> str:
    return """<h1>prd 四要素 ↔ 设计映射</h1>
<table><tr><th>prd 要求</th><th>设计落点（链 → 终态锚定）</th><th>证据入口</th></tr>
<tr><td>自然语言问数（NL2SQL）：中文提问 → 生成 SQL 并执行</td>
<td>用户旅程设计链（输入→路由→编排→执行→SSE→表格全程锚定源码）+ 契约链（SQL 输出契约）</td>
<td>journey/claims.yaml（源码路径+符号）· system/contracts/sql.output.schema.json</td></tr>
<tr><td>LangGraph 多节点工作流：12 个节点按 10 步分阶段执行</td>
<td>用户旅程链 v4（graph.py:417 build_agent_graph，12 节点；steps.yaml 10 步映射）</td>
<td>journey/claims.yaml · system/contracts/steps.yaml · StepRail 12 节点进度</td></tr>
<tr><td>SQL 自校验与自纠错：validate_sql + correct_sql 双保险</td>
<td>纠错链（S6 校正闭环 + 失败注入矩阵）+ 安全链（策略拒绝不进纠错）</td>
<td>correction/claims.yaml（图 12/31）· security/claims.yaml（SQL_REJECTED 不重试）</td></tr>
<tr><td>React 19 + Tailwind 前端：聊天式提问、可视化结果表格</td>
<td>用户旅程链（Composer→streamQuery→SSE→ResultTable/ErrorCard）</td>
<td>journey/claims.yaml · system/frontend/src/</td></tr>
<tr><td>设计文档 ≥30 页</td><td>本卷（决策生长版）；页数见目录页脚与 MANIFEST</td><td>materials/design/design-doc.pdf</td></tr></table>
<div class="foot">四要素均落在至少一条链的 claim 上；每条 claim 有 source + probe/ablation 或 [unknown]。</div>
<div class="pagebreak"></div>"""


def page_overview(data: dict) -> str:
    rows = "".join(
        f"<tr><td>{CHAIN_CN[c]}</td><td>{html.escape(data[c].get('kicker',''))}</td>"
        f"<td>{' → '.join(v['badge'] for v in data[c]['versions'])}</td>"
        f"<td>{html.escape(data[c]['sources'][:60])}…</td></tr>"
        for c in CHAINS if c in data)
    return f"""<h1>设计生长总览</h1>
<p>五个设计问题，五条被「打脸」逼出来的生长线。每条线的版本数相同（v1–v4），终点都是当前实现。
读的时候只问三件事：<b>这一格防的是什么打脸？补上的东西今天在哪份代码里？剩下的缺口标了 [unknown] 吗？</b></p>
<table><tr><th>链</th><th>文档头</th><th>版本</th><th>来源（截断）</th></tr>{rows}</table>
<div class="foot">叙事 = 教学编撰（D57）；终态 = 代码/契约/真跑锚定。二者分界就是左右页分界。</div>
<div class="pagebreak"></div>"""


def page_spreads(chain: str, left: Path, right: Path, d: dict) -> str:
    out = []
    for img, label in ((left, "左页 · 生长 v1→v4"), (right, "右页 · 终态与证据")):
        out.append(f"""<h2>{CHAIN_CN[chain]} · {html.escape(d['growth'])} — {label}</h2>
<img class="spread-half" src="{img.as_uri()}">
<div class="foot">来源：{html.escape(d['sources'])}</div><div class="pagebreak"></div>""")
    return "".join(out)


def page_fig(rel: str, cap: str) -> str:
    p = DIAG / rel
    return f"""<div class="figwrap"><h2>{html.escape(cap)}</h2><img src="{p.resolve().as_uri()}"></div>
<div class="figcap">来源：materials/design/diagrams/{html.escape(rel)}</div><div class="pagebreak"></div>"""


def page_claims(chain: str) -> str:
    cf = BASE / chain / "claims.yaml"
    if not cf.exists():
        return f"<h1>{CHAIN_CN[chain]} · claims 摘要</h1><p>claims.yaml 尚未生成。</p><div class='pagebreak'></div>"
    try:
        c = yaml.safe_load(cf.read_text(encoding="utf-8"))
        items = c.get("items", []) if isinstance(c, dict) else []
    except yaml.YAMLError as e:
        return (f"<h1>{CHAIN_CN[chain]} · claims 摘要</h1><p>claims.yaml 解析失败："
                f"{html.escape(str(e).splitlines()[0])}</p><div class='pagebreak'></div>")
    rows = "".join(
        f"<tr><td>{html.escape(str(it.get('id','')))}</td><td>{html.escape(str(it.get('claim','')))}</td>"
        f"<td>{html.escape(str(it.get('type','')))}</td><td>{html.escape(str(it.get('status','')))}</td>"
        f"<td>{html.escape('; '.join(map(str, it.get('sources',[])))[:80])}</td>"
        f"<td>{html.escape('; '.join(map(str, it.get('probe') or it.get('ablation') or []))[:60])}</td></tr>"
        for it in c.get("items", []))
    return f"""<h1>{CHAIN_CN[chain]} · claims 摘要</h1>
<table><tr><th>id</th><th>claim</th><th>type</th><th>status</th><th>sources</th><th>probe/ablation</th></tr>{rows}</table>
<div class="foot">完整版见 materials/design/decision-growth/{chain}/claims.yaml 与 claims.md。</div>
<div class="pagebreak"></div>"""


def page_summary(data: dict) -> str:
    unk = "".join(
        f"<tr><td>{CHAIN_CN[c]}</td><td>{html.escape(data[c]['unknown'])}</td></tr>"
        for c in CHAINS if c in data)
    def chk(x):
        if isinstance(x, dict):
            return html.escape(" ".join(str(v) for v in x.values()))
        return html.escape(str(x))
    cmds = "".join(
        f"<tr><td>{CHAIN_CN[c]}</td><td>" + "<br>".join(chk(x) for x in data[c]["checks"]) + "</td></tr>"
        for c in CHAINS if c in data)
    p1 = f"""<h1>未知 / 反悔点汇总</h1>
<p>以下缺口今晚照实标注，不用「行业惯例」补空；每条都是「什么情况下结论会倒」的候选。</p>
<table><tr><th>链</th><th>未知 / 反悔点</th></tr>{unk}</table><div class="pagebreak"></div>"""
    p2 = f"""<h1>可重跑命令汇总</h1>
<table><tr><th>链</th><th>命令与预期</th></tr>{cmds}</table>
<div class="foot">命令以 claims.yaml 的 probe 为准；跑不回预期输出就说明环境或实现漂移了。</div><div class="pagebreak"></div>"""
    p3 = """<h1>术语（白话）</h1>
<table><tr><th>术语</th><th>白话</th></tr>
<tr><td>渐进稿</td><td>一条链两页：左页看设计怎么被「打脸」逼着长，右页看今天的样子和证据。</td></tr>
<tr><td>教学编撰</td><td>v1→v4 的故事是为教学重构的，不是真实开发日记；结论只认右页锚定的代码/契约。</td></tr>
<tr><td>被打脸 / 补上</td><td>某做法在什么场景下失效 / 为堵这个失效加了什么。每格必须成对出现。</td></tr>
<tr><td>[unknown]</td><td>今晚没验证的缺口；禁止用「最佳实践」填成绿色。</td></tr>
<tr><td>claim</td><td>一条可复核的主张：有来源、有 probe/消融、有 status（verified/inferred/unknown）。</td></tr>
<tr><td>拆一刀</td><td>把刚补上的防线故意拆掉，判据应该变红；不红的防线是装饰。</td></tr>
</table>
<div class="foot">完整术语以仓库根 GLOSSARY.md 为准。</div>"""
    return p1 + p2 + p3


def main() -> int:
    data = {}
    for c in CHAINS:
        f = BASE / c / "data.yaml"
        if f.exists():
            data[c] = yaml.safe_load(f.read_text(encoding="utf-8"))
    missing = [c for c in CHAINS if c not in data]
    if missing:
        print(f"缺链 data.yaml：{missing}", file=sys.stderr)
        return 1
    tmp = Path(tempfile.mkdtemp())
    check_only = "--check" in sys.argv
    parts = [page_cover(), page_toc(data), page_quickref(), page_prd(), page_overview(data)]
    n_pages = 5
    for c in CHAINS:
        if check_only:
            n_pages += 2
            continue
        left, right = half_images(c, tmp)
        parts.append(page_spreads(c, left, right, data[c]))
        n_pages += 2
    for rel, cap in A_FIGS:
        p = DIAG / rel
        if not p.exists():
            print(f"缺图：{p}", file=sys.stderr)
            return 1
        parts.append(page_fig(rel, cap))
        n_pages += 1
    for c in CHAINS:
        parts.append(page_claims(c))
        n_pages += 1
    parts.append(page_summary(data))
    n_pages += 3
    doc = f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(parts)}</body></html>"
    if "--check" in sys.argv:
        print(f"预计 {n_pages} 页（≥30 {'OK' if n_pages >= 30 else '不足'}）；构成：4 起步 + 5 链×2 + 9 图 + 5 claims + 3 汇总")
        return 0 if n_pages >= 30 else 1
    from weasyprint import HTML
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html_out = OUT.with_suffix(".html")
    html_out.write_text(doc, encoding="utf-8")
    doc_obj = HTML(string=doc, base_url=str(ROOT)).render()
    doc_obj.write_pdf(OUT)
    print(f"wrote {OUT} · {len(doc_obj.pages)} pages · {OUT.stat().st_size / 1024 / 1024:.2f} MB")
    if len(doc_obj.pages) < 30:
        print("WARNING 页数 < 30，不满足 prd")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
