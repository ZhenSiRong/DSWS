#!/usr/bin/env python3
"""页首图构建器：data/page-NN.json → page-NN/index.html → out/poster.png → images/page-NN-visual.webp

用法：
  python3 manual/designs/build_visuals.py            # 构建全部已登记页
  python3 manual/designs/build_visuals.py 03 04      # 只构建指定页
  python3 manual/designs/build_visuals.py --no-render # 只生成 HTML/editor
  python3 manual/designs/build_visuals.py --no-editor # 不生成 editor.html
"""
from __future__ import annotations
import json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGNS = ROOT / "manual" / "designs"
DATA_DIR = DESIGNS / "data"
ICONS = DESIGNS / "_shared" / "icons"
SKILL = Path.home() / ".agents" / "skills" / "editable-design"
W, H = 1600, 1000

FONT_BODY = '"Noto Sans CJK SC", "Source Han Sans SC", sans-serif'
FONT_MONO = '"Noto Sans Mono CJK SC", "Noto Sans Mono", monospace'

DATA = {
 "03": {"eyebrow":"第 3 页 · L1 造 · 服务","title":"把服务开到 8000","subtitle":"一个 HTTP 服务，一个接口，一次真正的“对外说话”","layout":"steps","steps":[
   {"n":"1","title":"写服务","detail":"FastAPI 应用，只留一个 GET /health","judge":"app = FastAPI()"},
   {"n":"2","title":"跑起来","detail":"uvicorn 监听本机 8000","judge":"Uvicorn running on http://127.0.0.1:8000"},
   {"n":"3","title":"一问一答","detail":"curl 探活，服务回 JSON","judge":"{\"ok\":true}"}],
   "footer":"curl http://127.0.0.1:8000/health → {\"ok\":true}"},
 "04": {"eyebrow":"第 4 页 · L1 造 · 接口","title":"加一个能收问题的接口","subtitle":"先修通“收发 JSON”这条路，不查库、不生成 SQL","layout":"steps","steps":[
   {"n":"1","title":"POST /api/query","detail":"收一个 JSON：question","judge":"{\"question\":\"华北销售额\"}"},
   {"n":"2","title":"只回显","detail":"keywords / sql / rows 先留空","judge":"不查库、不拼 SQL"},
   {"n":"3","title":"一字不差","detail":"同一请求两次，响应完全相同","judge":"硬编码 JSON"}],
   "footer":"{\"question\":\"华北销售额\",\"keywords\":[],\"sql\":null,\"rows\":[]}"},
 "05": {"eyebrow":"第 5 页 · L1 造 · 关键词","title":"从一句话里抽出关键词","subtitle":"纯函数 + 词表匹配，不调 AI、不分析语法","layout":"compare",
   "left":{"title":"输入：一句话","lines":["华北销售额","华东的销售额是多少"]},
   "right":{"title":"输出：关键词列表","lines":["[\"华北\",\"销售额\"]","[\"华东\",\"销售额\"]"]},
   "footer":"extract_keywords(question)：词表里出现哪个词，就抽哪个词"},
 "06": {"eyebrow":"第 6 页 · L1 造 · 生成","title":"照契约生成那条带 JOIN 的 SQL","subtitle":"契约字典 + build_sql(keywords)：把关键词拼成 5 行 SELECT","layout":"steps","steps":[
   {"n":"1","title":"CONTRACT 字典","detail":"表、列、指标口径写进 Python","judge":"表 / 列 / 口径"},
   {"n":"2","title":"build_sql(keywords)","detail":"照契约拼 JOIN，不靠猜","judge":"fact_order JOIN dim_region"},
   {"n":"3","title":"5 行 SELECT","detail":"可直接交给 MySQL 执行","judge":"WHERE region_name = '华北'"}],
   "footer":"SELECT … FROM fact_order JOIN dim_region ON … WHERE region_name='华北' GROUP BY …"},
 "07": {"eyebrow":"第 7 页 · L1 造 · 执行","title":"把 SQL 真交给 MySQL","subtitle":"pymysql 真执行，把结果填回 sql 和 rows","layout":"steps","steps":[
   {"n":"1","title":"pymysql 执行","detail":"第 6 页那 5 行 SELECT 真跑","judge":"cursor.execute(sql)"},
   {"n":"2","title":"填回响应","detail":"sql / rows 不再为空","judge":"sql + rows"},
   {"n":"3","title":"41099.5","detail":"华北销售额从库里取回来","judge":"rows[0] = 华北 41099.5"}],
   "footer":"rows → [{\"region_name\":\"华北\",\"sales\":41099.5}]"},
 "08": {"eyebrow":"第 8 页 · L1 造 · 流式","title":"让答案一条条推送出来（SSE）","subtitle":"12 条 progress + 1 条 result，text/event-stream","layout":"steps","steps":[
   {"n":"1","title":"12 条 progress","detail":"每个步骤一条事件","judge":"recall_column / generate_sql …"},
   {"n":"2","title":"最后 1 条 result","detail":"结果只在最后出现","judge":"rows: [{region_name: 华北, sales: 41099.5}]"},
   {"n":"3","title":"text/event-stream","detail":"事件之间一个空行","judge":"EventSource 接流"},
   {"n":"4","title":"前端逐步渲染","detail":"用户能看到走到第几步","judge":"12 progress + 1 result"}],
   "footer":"GET /api/stream?q=… → 12 条 progress + 1 条 result"},
 "09": {"eyebrow":"第 9 页 · L1 造 · 入口","title":"给浏览器一个入口","subtitle":"nginx 反代 + 17 行页面 + docker run","layout":"steps","steps":[
   {"n":"1","title":"nginx.conf 8 行","detail":"/api/ 反代到 backend:8000","judge":"proxy_pass http://backend:8000"},
   {"n":"2","title":"17 行页面","detail":"输入框 + EventSource 接收","judge":"浏览器自带 EventSource"},
   {"n":"3","title":"docker run 8081","detail":"浏览器打开入口、问一句","judge":"41099.5"}],
   "footer":"浏览器 → 8081 → nginx → /api/stream → 41099.5"},
 "10": {"eyebrow":"第 10 页 · L2 换 · 真数据","title":"换真数据：把演示数据换成甲方数据","subtitle":"115 行演示数据 → 410 行真数据；先洗，再报数","layout":"table",
   "headers":["口径","演示数据","真数据"],
   "rows":[["行数","115","410"],["不洗直接 SUM","1,144,735.50","1,144,735.50"],["清洗后","—","1,136,341.10"],["差额","—","8,394.40"]],
   "footer":"门禁只读快照：换完真数据它还是绿的 —— 门禁绿 ≠ 数据真"},
 "11": {"eyebrow":"第 11 页 · L2 换 · 真契约","title":"让 SQL 从契约里长出来","subtitle":"删掉手抄 CONTRACT，改成加载唯一的契约文件","layout":"steps","steps":[
   {"n":"1","title":"删手抄字典","detail":"lab/app.py 里的 CONTRACT = {...}","judge":"副本不可信"},
   {"n":"2","title":"加载契约","detail":"contracts/schema.contract.yaml","judge":"唯一事实源"},
   {"n":"3","title":"逐字一致","detail":"build_sql 输出与第 6 页一模一样","judge":"5 行 SELECT"}],
   "footer":"契约文件是唯一事实源；手抄字典只是副本"},
 "12": {"eyebrow":"第 12 页 · L2 换 · 真执行器","title":"给临时通道装上四道闸","subtitle":"lab/db.py：dict 行、Decimal 精度、自动 LIMIT、只读","layout":"cards","cards":[
   {"icon":"mysql","name":"行是 dict","role":"按列名取值，不再靠下标","judge":"{'sales': Decimal('1144735.50')}"},
   {"icon":"python","name":"Decimal 原样","role":"金额不丢精度","judge":"-0.0005455017"},
   {"name":"自动 LIMIT 1000","role":"没写 LIMIT 就补上限","judge":"dim_date 1461 行 → 1000"},
   {"name":"非 SELECT 拒绝","role":"只读闸门，执行前拦下","judge":"PermissionError"}],
   "footer":"四道闸：dict / Decimal / LIMIT / 只读"},
 "13": {"eyebrow":"第 13 页 · L2 换 · 真部署","title":"一条命令起整座城","subtitle":"compose.yaml 编排六个服务，一条 docker-smoke 验收","layout":"steps","steps":[
   {"n":"1","title":"compose.yaml","detail":"mysql / elasticsearch / qdrant / init / backend / frontend","judge":"6 个服务"},
   {"n":"2","title":"init 跑一次","detail":"先 Started 再 Exited，不算长驻","judge":"Exited (0)"},
   {"n":"3","title":"backend / frontend","detail":"最后都 Healthy","judge":"Up (healthy)"},
   {"n":"4","title":"docker-smoke","detail":"一条命令验收整座城","judge":"DOCKER SMOKE PASS"}],
   "footer":"起得来 ≠ 部署好：六个服务 + init 一次性任务"},
 "14": {"eyebrow":"第 14 页 · L3 审 · 检索","title":"召回空了的答案，你凭什么信","subtitle":"20 题黄金集 + 三条判据；停掉检索存储，看谁在兜底","layout":"compare",
   "left":{"title":"20 题黄金集","lines":["该命中：必须命中","不该出现：不能出现","输出规模：有上限"]},
   "right":{"title":"停掉 ES / Qdrant","lines":["查数仍回 41099.5：契约离线裁剪兜底","黄金集整片变红：检索层没兜住"]},
   "footer":"检索是增强，契约才是底线"},
 "15": {"eyebrow":"第 15 页 · L3 审 · 生成","title":"同一把尺子，量模板也量模型","subtitle":"10 题基线 + 语义断言，模板与模型都跑同一套尺子","layout":"cards","cards":[
   {"name":"10 题基线","role":"问题 → SQL/拒答 → 判定","judge":"baseline.yaml"},
   {"name":"语义断言","role":"不看字面，看语义是否等价","judge":"122 passed, 5 skipped"},
   {"name":"拒答也要对","role":"该拒答的必须拒","judge":"S4 PASS"}],
   "footer":"同一把尺子：模板和模型都量，不靠单次演示"},
 "16": {"eyebrow":"第 16 页 · L3 审 · 校验","title":"错单要在执行前被拦下","subtitle":"20 条错单 + 16 个错误码 + 9 个场景：每条被哪个码、在哪一步拦","layout":"compare",
   "left":{"title":"执行前的门","lines":["20 条带 expect_code 错单","16 个错误码 / 3 类","9 场景：6 失败 + 3 对照"]},
   "right":{"title":"拆掉一条校验规则","lines":["错单从“拦”变“放”","正确地红：失败矩阵能定位","26 passed 是基线"]},
   "footer":"校验是执行前的门，不是出错后的日志"},
 "17": {"eyebrow":"第 17 页 · L3 审 · 纠错","title":"一次重试能修好什么、修不好什么","subtitle":"把纠错当成一次有上限的赌博来审：只重试 1 次，改完必须重新过校验","layout":"steps","steps":[
   {"n":"1","title":"validate_sql → error","detail":"静态校验先拦下","judge":"SQL_UNKNOWN_COLUMN"},
   {"n":"2","title":"三个触发条件","detail":"有校正器 / 可重试 / 契约允许","judge":"max_attempts: 1"},
   {"n":"3","title":"只校正一次","detail":"一次重试，改出的 SQL 重过两道关","judge":"attempted=True"},
   {"n":"4","title":"二次校验","detail":"改完的 SQL 还要过 guard + policy","judge":"error=None"},
   {"n":"5","title":"真执行","detail":"过校验才交给 MySQL","judge":"rows=5 行"}],
   "footer":"14 passed / S6 PASS；成功率按多次采样写，不写“已修复”"},
 "18": {"eyebrow":"第 18 页 · L4 守 · 账号","title":"只读账号真的写不了吗","subtitle":"把“只读”从约定搬进数据库权限：dw_reader 只有 SELECT","layout":"compare",
   "left":{"title":"约定：应用层","lines":["提示词 / 校验 / 策略","全部失效也还有最后一道"]},
   "right":{"title":"能力边界：数据库权限","lines":["GRANT SELECT ON dw.*","UPDATE → 1142 command denied"]},
   "footer":"只读要从“约定”变成“能力边界”"},
 "19": {"eyebrow":"第 19 页 · L4 守 · 策略","title":"36 条注入全拒、11 条正常零误杀","subtitle":"执行前按类别拦：单语句 / 只读 / 集合运算 / 注释 / 危险函数 / 白名单","layout":"table",
   "headers":["语料","数量","判据"],
   "rows":[["注入语料","36","36/36 拒绝"],["零误杀语料","11","11/11 放行"],["S4 基线","8","8/8 通过"]],
   "footer":"整类拒 + 白名单：36/36 · 11/11 · S5 PASS"},
 "20": {"eyebrow":"第 20 页 · L4 守 · 取消","title":"点了停止，系统真的停了吗","subtitle":"取消是独立状态：不是 done，也不是失败","layout":"steps","steps":[
   {"n":"1","title":"点“停止”","detail":"客户端发取消请求","judge":"cancel"},
   {"n":"2","title":"服务端真的停","detail":"不再继续跑、不再写结果","judge":"状态回到 idle"},
   {"n":"3","title":"发 CANCELLED 事件","detail":"SSE 里显式告诉前端","judge":"type=error, code=CANCELLED"},
   {"n":"4","title":"界面标“已取消”","detail":"不是“失败”，也不是“完成”","judge":"已取消"}],
   "footer":"停止是一个状态，不是「不返回」"},
 "21": {"eyebrow":"第 21 页 · L4 守 · 可观测","title":"12 条进度 + 14 条夹具能证明什么","subtitle":"给一次问数装上可对账的观测面：步骤、错误码、SSE 回放","layout":"cards","cards":[
   {"name":"/api/steps","role":"12 条进度：11 常驻 + 1 条件","judge":"12，条件步骤 correct_sql"},
   {"name":"/api/errors","role":"错误码表：16 个码 / 3 类","judge":"16"},
   {"name":"SSE 回放","role":"14 条夹具逐字节对账","judge":"S7 SSE RECORD PASS"}],
   "footer":"可观测：12 进度 + 16 错误码 + 14 夹具"},
 "22": {"eyebrow":"第 22 页 · L4 守 · 回归","title":"一套门禁能不能替你值班","subtitle":"8 步 smoke、stage0–7、全量 pytest、前端测试拼成一张回归网","layout":"table",
   "headers":["门禁","命令","抓什么"],
   "rows":[["docker-smoke","8 步","部署/健康/只读账号"],["stage0–7","逐级","每一层的判据"],["全量 pytest","backend","代码回归"],["前端测试","npm test","协议/组件回归"]],
   "footer":"全绿不是目标，红了能定位才是"},
 "23": {"eyebrow":"第 23 页 · L5 装 · 体验","title":"装修不换承重墙","subtitle":"同一后端、同一份契约、同一条 SSE：三种入口，同一个数","layout":"table",
   "headers":["入口","谁渲染","结果"],
   "rows":[["8081 · 17 行 HTML","手写页面","41099.5"],["8080 · 教学版","从零重建 · 教学版","41,099.5"],["8088 · 成熟版","shopkeeper-agent 原版","41099.5"]],
   "footer":"装修只换入口载体，不换承重墙"},
}

CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #e8e8e8; }
.poster { position: relative; width: 1600px; height: 1000px; overflow: hidden; background:#fff; color:#1a1a1a; font-family:%(body)s; }
.head { position:absolute; left:72px; top:48px; width:1456px; }
.eyebrow { margin:0; font-family:%(mono)s; font-size:19px; font-weight:700; color:#E65100; letter-spacing:1.5px; }
h1 { margin:10px 0 0; font-size:58px; font-weight:900; line-height:1.1; letter-spacing:-1px; }
.sub { margin:12px 0 0; color:#585858; font-size:23px; line-height:1.45; }
.rule { margin-top:20px; height:2px; background:#1a1a1a; }
.body { position:absolute; left:72px; right:72px; top:285px; height:585px; display:flex; align-items:center; }
.cards { width:100%; display:grid; grid-template-columns:repeat(3, 1fr); gap:18px; }
.cards.c4 { grid-template-columns:repeat(2, 1fr); }
.card { border:2px solid #1a1a1a; padding:22px 24px 20px; background:#fff; min-height:330px; position:relative; }
.cards.c4 .card { min-height:250px; }
.card .num { position:absolute; right:16px; top:12px; color:#c9c9c9; font-family:%(mono)s; font-size:18px; }
.card .icon { width:44px; height:44px; object-fit:contain; margin-bottom:10px; }
.card h2 { margin:6px 0 0; font-size:29px; font-weight:800; }
.card .role { margin:10px 0 0; font-size:19px; line-height:1.45; color:#1a1a1a; }
.card .judge { margin-top:14px; padding-top:10px; border-top:1px solid #c9c9c9; font-family:%(mono)s; font-size:15px; color:#E65100; line-height:1.4; }
.steps { width:100%; display:flex; align-items:stretch; gap:0; }
.step { flex:1; border:2px solid #1a1a1a; padding:22px 20px; margin-right:26px; position:relative; min-height:350px; }
.step:last-child { margin-right:0; }
.step:after { content:"→"; position:absolute; right:-24px; top:50%; transform:translateY(-50%); font-size:24px; color:#E65100; font-weight:900; }
.step:last-child:after { content:""; }
.step .n { font-family:%(mono)s; font-size:20px; font-weight:700; color:#E65100; }
.step h2 { margin:8px 0 0; font-size:26px; font-weight:800; line-height:1.25; }
.step .detail { margin:10px 0 0; font-size:18px; line-height:1.45; color:#1a1a1a; }
.step .judge { margin-top:14px; padding-top:10px; border-top:1px solid #c9c9c9; font-family:%(mono)s; font-size:14px; color:#585858; line-height:1.4; }
.compare { width:100%; display:grid; grid-template-columns:1fr 1fr; gap:28px; }
.col { border:2px solid #1a1a1a; padding:26px 28px; min-height:400px; }
.col .tag { display:inline-block; background:#E65100; color:#fff; font-family:%(mono)s; font-size:15px; padding:2px 8px; }
.col h2 { margin:12px 0 0; font-size:30px; font-weight:800; }
.col ul { margin:16px 0 0; padding-left:22px; }
.col li { font-size:20px; line-height:1.55; margin:8px 0; font-family:%(mono)s; }
.table { width:100%; border:2px solid #1a1a1a; display:flex; flex-direction:column; justify-content:center; }
.table .tr { display:grid; grid-template-columns:1.1fr 1fr 1fr; border-bottom:1px solid #1a1a1a; }
.table .tr:last-child { border-bottom:0; }
.table .th { background:#1a1a1a; color:#fff; font-family:%(mono)s; font-size:17px; }
.table .td { padding:24px 24px; font-size:24px; line-height:1.4; }
.table .td.mono { font-family:%(mono)s; font-size:18px; }
.foot { position:absolute; left:72px; right:72px; bottom:56px; border-top:2px solid #1a1a1a; padding-top:16px; display:flex; align-items:flex-start; gap:16px; }
.tag { flex:0 0 auto; background:#E65100; color:#fff; font-family:%(mono)s; font-size:18px; font-weight:700; padding:3px 10px; }
.foot p { margin:0; font-size:21px; line-height:1.45; }
"""

def icon_path(name: str) -> str | None:
    p = ICONS / f"{name}.svg"
    return f"../_shared/icons/{name}.svg" if p.is_file() else None

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def render(data: dict) -> str:
    body = ""
    layout = data["layout"]
    if layout == "cards":
        cards = []
        for i, c in enumerate(data["cards"], 1):
            ip = icon_path(c.get("icon")) if c.get("icon") else None
            icon = f'<img class="icon" src="{ip}" alt="">' if ip else ""
            cards.append(f'<div class="card" data-layer-id="card-{i}"><span class="num">{i:02d}</span>{icon}'
                         f'<h2>{esc(c["name"])}</h2><p class="role">{esc(c["role"])}</p>'
                         f'<p class="judge">{esc(c["judge"])}</p></div>')
        body = f'<div class="cards{" c4" if len(data["cards"])==4 else ""}">{"".join(cards)}</div>'
    elif layout == "steps":
        steps = []
        for s in data["steps"]:
            steps.append(f'<div class="step" data-layer-id="step-{s["n"]}"><span class="n">STEP {s["n"]}</span>'
                         f'<h2>{esc(s["title"])}</h2><p class="detail">{esc(s["detail"])}</p>'
                         f'<p class="judge">{esc(s["judge"])}</p></div>')
        body = f'<div class="steps">{"".join(steps)}</div>'
    elif layout == "compare":
        def col(side: dict) -> str:
            lis = "".join(f"<li>{esc(x)}</li>" for x in side["lines"])
            return f'<div class="col" data-layer-id="col-{side["title"]}"><span class="tag">对比</span><h2>{esc(side["title"])}</h2><ul>{lis}</ul></div>'
        body = f'<div class="compare">{col(data["left"])}{col(data["right"])}</div>'
    elif layout == "table":
        head = "".join(f'<div class="td th">{esc(h)}</div>' for h in data["headers"])
        rows = "".join('<div class="tr">' + "".join(f'<div class="td{" mono" if j>0 else ""}">{esc(c)}</div>' for j,c in enumerate(r)) + "</div>" for r in data["rows"])
        body = f'<div class="table"><div class="tr">{head}</div>{rows}</div>'
    else:
        raise ValueError(layout)
    css = CSS.replace("%(body)s", FONT_BODY).replace("%(mono)s", FONT_MONO)
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{esc(data["title"])}</title>
<style>{css}</style></head>
<body><div class="poster" data-layer-id="poster" data-canvas-width="1600" data-canvas-height="1000">
<div class="head" data-layer-id="head"><p class="eyebrow">{esc(data["eyebrow"])}</p>
<h1>{esc(data["title"])}</h1><p class="sub">{esc(data["subtitle"])}</p><div class="rule"></div></div>
<main class="body" data-layer-id="body">{body}</main>
<div class="foot" data-layer-id="footer"><span class="tag">判据</span><p>{esc(data["footer"])}</p></div>
</div></body></html>'''

def render_png(page: str) -> None:
    proj = DESIGNS / f"page-{page}"
    out = proj / "out"; out.mkdir(exist_ok=True)
    url = (proj / "index.html").resolve().as_uri()
    png = out / "poster.png"
    cmd = ["google-chrome","--headless=new","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=1",
           "--window-size=1600,1000",f"--screenshot={png}",url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not png.is_file():
        raise RuntimeError(f"render failed {page}: {r.stderr[-400:]}")
    webp = ROOT / "manual" / "images" / f"page-{page}-visual.webp"
    subprocess.run(["convert", str(png), "-quality", "82", str(webp)], check=True,
                   capture_output=True)
    print(f"  render page-{page}: {png.stat().st_size}B → {webp.stat().st_size}B webp")

def wire_editor(page: str) -> None:
    proj = DESIGNS / f"page-{page}"
    r = subprocess.run(["node", str(SKILL/"scripts"/"wire-editor.mjs"), str(proj/"index.html")],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"  editor skip page-{page}: {r.stderr[-300:]}")
    else:
        print(f"  editor page-{page} ok")

def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_render = "--no-render" in sys.argv
    no_editor = "--no-editor" in sys.argv
    pages = args or [p for p in DATA if (DESIGNS/f"page-{p}").exists() or True]
    for page in pages:
        data = DATA[page]
        proj = DESIGNS / f"page-{page}"
        proj.mkdir(parents=True, exist_ok=True)
        (proj/"assets").mkdir(exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR/f"page-{page}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        (proj/"index.html").write_text(render(data), encoding="utf-8")
        (proj/"poster.json").write_text(json.dumps({"canvas":{"width":W,"height":H}}, ensure_ascii=False)+"\n", encoding="utf-8")
        print(f"page-{page}: html written")
        if not no_editor: wire_editor(page)
        if not no_render: render_png(page)

if __name__ == "__main__":
    main()
