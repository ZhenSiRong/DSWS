# 第 6–9 页 · 学生视角重放报告

**一句话结论：** 4 页的代码块与“你应该看到”全部对得上（4 页都能跟做）；本机 8000/8081/3307 全被占用，逐字照抄 0 页能通，换成 8012/8082/3308 后 4 页一次跑通。第 6 页最独立（不用 DB 和服务），第 7 页起依赖第 1–2 页 MySQL，第 9 页还依赖 Docker。最该先修：6/7/8 三页都缺“保存”、端口不向下传递、第 7 页“函数体整个换掉”的措辞会静默出错。

| 页 | 指令可执行? | 期望输出一致? | 衔接? | 问题数 | 严重度 |
|---|---|---|---|---|---|
| 第 6 页 | 是（`python -m lab.app` 通；21/3 切法有歧义） | 是（5 行 SQL 逐字一致） | 是（终端 1 服务开着不冲突，已验证） | 2 | 困惑1、文案1 |
| 第 7 页 | 是（本机需把 3307 换 3308；三处改法可行） | 是（41099.5；自己改一下 107373.0 / 26） | 缺口：3307 与重启端口不跟随前页；缺“保存” | 5 | 困惑4、文案1 |
| 第 8 页 | 是（两处改法可行） | 是（12 progress+1 result、1.81s、1245B） | 缺口：缺“保存”→`/api/stream` 404；重启端口 | 2 | 困惑2 |
| 第 9 页 | 是（本机需换 8000/8081 + 容器改名） | 是（浏览器 41099.5；403/502/断链全对） | 缺口：8000/8081 全页写死 4 处，无替换提示 | 2 | 困惑2 |

**问题清单（页:行 ｜ 原文摘录 ｜ 问题 ｜ 建议改法）**
- **6:45**｜“把前 21 行插中间。从 `CONTRACT = {` 到 `build_sql` 的 `return sql` 这 21 行”｜该范围实际只有 20 行（第 21 行是 `return sql` 后的空行）；两种切法（20+4 / 21+3）都能跑通，但学生要逐行复核、怀疑自己数错｜改成“前 20 行（`CONTRACT = {` 到 `return sql`）再加它后面那个空行，共 21 行”，或直接写“第 1–20 行插中间、第 21–24 行追加末尾”
- **6:16、6:51–55**｜“要改的文件是 `lab/app.py`”“然后在仓库根目录跑”｜这两步没写“保存”；不保存直接跑，退出码 0、输出 0 字节（页 5 文件没有 `__main__` 块，实测），学生会去查目录/Python/命令｜6:16 或命令前加“（Ctrl+S 保存）”，并在对账补“输出为空 = 没保存”
- **7:30、7:41**｜`port=3307`；“`127.0.0.1:3307` 是第 1 页 `-p 127.0.0.1:3307:3306` 里宿主机那一侧”｜第 1 页明说“3307 若也被占，换一个（比如 3308），后面写 3307 的页跟着改”，但本页仍写死且不提醒；本机 3307 被别的 MySQL 占，照抄会连到别人的库｜7:41 末补：“若第 1 页换过端口，把这里和 `port=` 一起换成你实际用的端口（本次重放用 3308）”
- **7:43**｜“把 `query()` 的函数体整个换掉”，但给出的块含 `@app.post("/api/query")` 和 `def query(q: Query):` 两行｜字面“只换函数体”粘贴时：编辑器自动缩进→函数体内嵌一层带装饰器的 def，`POST /api/query` 回 200 `null`（无报错无 traceback）；不自动缩进→`IndentationError: expected an indented block`，uvicorn 起不来（两种均实测）｜改成“把整个 `query` 函数（含 `@app.post` 与 `def` 两行）替换成下面这段”，或把代码块拆成只含 3 行函数体的版本
- **7:54**｜“回终端 1，按 Ctrl+C 停掉，再用第 3 页那条命令原样重启”｜① 没写“保存”：不保存重启仍是第 6 页代码，curl 回 `"sql":null,"rows":[]`（实测）；② “原样”与第 3 页“换过端口要全改”冲突，换过端口会绑回 8000｜改成“保存后 Ctrl+C，用你实际用的端口重启：`backend/.venv/bin/python -m uvicorn lab.app:app --port <你的端口>`”
- **7:31–32、7:81**｜`region = next(k for k in keywords if ...)`；对账“MySQL 没起会回 500，先看终端 1”｜`keywords` 为空时（页 5 自己改一下的“昨天天气”）`next()` 抛 StopIteration：POST 回 500、SSE 发完 12 条 progress 后断流无 result（均实测）；与“500=MySQL 没起”的排错说明冲突，学生会查错方向｜7:31 前加 guard（空列表返回空 SQL 或捕获 StopIteration 回可读错误），或在页 7/8 注明“本课只支持同时含地区和指标的问题”
- **7:69**｜期望块是一整行 JSON｜`curl -s` 输出不带行尾换行，终端里提示符紧贴 `}`（复制对账时易与下一行粘连）；内容本身与期望逐字一致｜curl 加 `-w '\n'`，或在 7:71 补“JSON 末尾无换行、提示符紧跟其后，属正常”
- **8:19、8:55**｜“还是改 `lab/app.py`，两处”；“Ctrl+C 停服务，再用第 3 页那条命令重启”｜同 6/7 页缺“保存”；不保存重启后 `GET /api/stream` 回 404 `{"detail":"Not Found"}`（实测，服务仍跑第 7 页代码）｜改“保存后 Ctrl+C，再重启”，对账补“404 = 没保存/上一页没生效”
- **8:55**｜“第 3 页那条命令重启”｜第 3 页命令带 `--port 8000`；若学生按第 3 页换过端口，这里照抄会绑回 8000（本机 8000 被占→Errno 98）｜统一写“用你实际端口重启”（第 7 页同问题）
- **9:3、9:18–24、9:66、9:105**｜“接…8000 端口的服务”“`--port 8000`”“`-p 127.0.0.1:8081:80`”“页面 → nginx:8081 → uvicorn:8000 → MySQL:3307”｜第 9 页写死 3 个端口共 4 处（uvicorn 命令、`default.conf` 的 `proxy_pass`、`docker -p`、浏览器地址），没有像第 1/3 页那样说“换过端口这里一起改”；本机 8000/8081 被占，照抄直接 bind 失败，且 `default.conf` 里的 8000 不改会 502｜9:18、9:66 各加一句“8000/8081 换成你实际端口（含 default.conf 的 proxy_pass 与浏览器地址）”
- **9:66**｜`docker run -d --name lab-nginx ...`｜改错重跑/上次容器没删时报 `Conflict. The container name "/lab-nginx" is already in use`；页面直到 9:94 才出现 `docker rm -f lab-nginx`，且不在起容器前｜9:66 前加“若报 name already in use：先 `docker rm -f lab-nginx` 再重跑”

**真实输出摘录（页面端口 8000/8081/3307 → 重放用 8012/8082/3308；PID/耗时允许差异）**
- 第 6 页 `python -m lab.app`（exit 0）：`SELECT dim_region.region_name, SUM(fact_order.order_amount) AS sales` / `FROM fact_order` / `JOIN dim_region ON fact_order.region_id = dim_region.region_id` / `WHERE dim_region.region_name = '华北'` / `GROUP BY dim_region.region_name`——与期望块 diff 为空。第 7 页 curl：`…"rows":[{"region_name":"华北","sales":41099.5}]}` 整行与期望逐字一致；自己改一下 华东=107373.0、华南订单量=26 一致。
- 第 8 页 `curl -sN -G`：12 条 `progress` + 1 条 `result`，`duration_ms` 150.1–150.4，总 1.81s / 1245 B，末尾 `data: {"type": "result", "data": {"rows": [{"region_name": "华北", "sales": 41099.5}]}}`；sleep 0.5 实测 6.03s、progress 仍 12；`?q=中文` 原样发回 400 `Invalid HTTP request received.`。第 9 页 headless Chrome：初始 `out=''` → 12 个步骤名依次出现（首个 155ms）→ 1820.8ms 停在 `41099.5`；输入框改 华东销售额 → `107373`；`chmod 600`→403、回 644→200；去掉 `--host`→经 nginx 502；删 nginx 容器→8082 `ERR_CONNECTION_REFUSED`、直连 8012 仍回 result。

**端口/环境替换声明：** 本机 8000（他人 python 进程）、8081（他人 lab-nginx 容器）、3307（他人 lab-mysql 容器）均被占用、未触碰 → 8000→**8012**（所有命令）、8081→**8082**（`docker -p`、浏览器地址）、3307→**3308**（第 7 页 `run_sql` 的 `port=`；第 1 页明确授权）；容器名 lab-mysql→**replay69-mysql**、lab-nginx→**replay69-nginx**（同名已被占）；工作区 `/tmp/replay69`，Python 用仓库 `backend/.venv/bin/python`（绝对路径），`.env.example` 与 `fixtures/dw.sql` 只读复制；未改任何 `manual/page-*.md`，未读 `backend/` 实现与脚本。

**附：最终完整 `lab/app.py`（= 页 5 代码块 + 页 6 的 21/3 两步 + 页 7 三处 + 页 8 两处；为守 120 行上限把连续空行压成 1 行——实际文件 95 行、语句逐字未动，`port` 已按本机换 3308）**
```python
# lab/app.py —— 从问题里抽关键词（纯字符串规则，不用 AI）
import pymysql
from fastapi import FastAPI
from pydantic import BaseModel
import json
import time
from fastapi.responses import StreamingResponse

app = FastAPI()

REGIONS = ["华北", "华东", "华南", "西南", "华中"]
METRICS = ["销售额", "订单量"]

class Query(BaseModel):
    question: str

def extract_keywords(question: str) -> list[str]:
    keywords = []
    for word in REGIONS + METRICS:
        if word in question:
            keywords.append(word)
    return keywords

CONTRACT = {
    "tables": {
        "fact_order": ["region_id", "order_amount", "order_id"],
        "dim_region": ["region_id", "region_name"],
    },
    "metrics": {"销售额": "SUM(fact_order.order_amount)",
                "订单量": "COUNT(DISTINCT fact_order.order_id)"},
    "region_values": ["华北", "华东", "华南", "西南", "华中"],
}

def build_sql(keywords: list[str]) -> str:
    region = next(k for k in keywords if k in CONTRACT["region_values"])
    metric = next(k for k in keywords if k in CONTRACT["metrics"])
    sql = f"""SELECT dim_region.region_name, {CONTRACT['metrics'][metric]} AS sales
FROM fact_order
JOIN dim_region ON fact_order.region_id = dim_region.region_id
WHERE dim_region.region_name = '{region}'
GROUP BY dim_region.region_name"""
    return sql

def run_sql(sql: str) -> list[dict]:
    conn = pymysql.connect(host="127.0.0.1", port=3308, user="root",
                           password="labpass", database="dw",
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    finally:
        conn.close()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/query")
def query(q: Query):
    keywords = extract_keywords(q.question)
    sql = build_sql(keywords)
    return {"question": q.question, "keywords": keywords,
            "sql": sql, "rows": run_sql(sql)}

STEPS = ["extract_keywords", "recall_column", "recall_value", "recall_metric",
         "merge_retrieved_info", "filter_table", "filter_metric", "add_extra_context",
         "generate_sql", "validate_sql", "correct_sql", "run_sql"]

def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

@app.get("/api/stream")
def stream(q: str):
    def gen():
        for step in STEPS:
            t0 = time.perf_counter()
            time.sleep(0.15)  # 假装在干活，让你肉眼看到一条条到
            yield sse({"type": "progress", "step": step, "status": "success",
                       "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})
        rows = run_sql(build_sql(extract_keywords(q)))
        yield sse({"type": "result", "data": {"rows": rows}})

    return StreamingResponse(gen(), media_type="text/event-stream")

if __name__ == "__main__":
    print(build_sql(extract_keywords("华北销售额")))
```
