# 第 3–5 页 · 学生视角重放报告

**一句话结论：3 页中 2 页可“照抄即通”（第 4、5 页）；第 3 页仅在 8000 空闲时可跟做——本机 8000 被占、照抄即报 Errno 98，但 3 页的代码块与“你应该看到”本身全部正确，没有代码级阻断错误。**

重放环境：工作区 `/tmp/replay35`（不污染仓库）；三页代码块用 `manual/page-03/04/05.md` 的字节原样提取后运行（非手抄，另做了 `py_compile`）；Python 3.14.8 / fastapi 0.162.0 / uvicorn 0.54.0 / pydantic 2.14.1。按委派避开 8000，但开跑时 8001 也被另一 python/uvicorn 占用（pid 914823，非本会话创建、未动它），故页面里的 `8000` 统一换成 **8011**，其余文字逐字执行；未读 backend 实现与任何脚本。

| 页 | 指令可执行? | 期望输出一致? | 衔接? | 问题条数 | 严重度(阻断/困惑/文案) |
|---|---|---|---|---|---|
| 第 3 页 | 条件可执行（8000 空闲时；本机被占） | 是（启动 4 行逐字一致；访问日志格式一致；`{"ok":true}`） | 缺口：收工停服 ↔ 下一页前置要“服务在跑”；换端口不向下传递 | 5 | 阻断1、困惑1、文案3 |
| 第 4 页 | 是 | 是（两次输出 A==B，逐字符合期望块） | 矛盾：4:76 说第 7 页填 sql，5:8/88 说第 6 页拼 SQL | 2 | 困惑1、文案1 |
| 第 5 页 | 是 | 是（两行 JSON 逐字符合期望块） | 小缺口：自己改一下打乱 METRICS 后无还原提示 | 3 | 困惑1、文案2 |

## 问题清单（页:行 | 原文摘录 | 问题 | 建议改法）

1. 3:35,73 | `backend/.venv/bin/python -m uvicorn lab.app:app --port 8000` / “嫌吵就换端口……但后面第 4–9 页里写 `8000` 的地方要一起改” | 8000 被占用时（本机实测）照抄报 `ERROR: [Errno 98] error while attempting to bind on address ('127.0.0.1', 8000): address already in use`；页面只在“嫌吵”语境提换端口，没给“占用”的处理；换端口后第 4、5 页命令与期望块里的 8000 不会自动跟着改 | 3 页补端口处置：“若报 `[Errno 98] address already in use`，改用 `--port 8010`，之后所有页命令里的 8000 都换成 8010”；4:46、5:58 各加“端口沿用你实际启动的端口”
2. 3:72 | “如果启动命令报 `No module named lab.app`：你没站在仓库根目录，或者文件建成了 `lab/app.py.py`” | 实测两种原因都不报这个字符串：不在仓库根目录 → 一大段 traceback，末行 `ModuleNotFoundError: No module named 'lab'`；文件叫 `lab/app.py.py` → `ERROR:    Error loading ASGI app. Could not import module "lab.app".`。按字符串搜的学生会以为遇到第三种问题 | 拆成两条：“报 `ModuleNotFoundError: No module named 'lab'`（带长 traceback）→ 不在仓库根目录”；“报 `Error loading ASGI app. Could not import module "lab.app"` → 文件名写成 `app.py.py` 或拼错”
3. 3:63 | “收工就在终端 1 按 Ctrl+C。” | 与 4:3、5:3 前置“接第 X 页留下的 lab/app.py 与 8000 端口的服务”矛盾：按“收工”停掉后，下一页假设的服务已不存在（实测停服后 8011 无监听），学生要先怀疑自己是不是漏做了上一页 | 改成：“本页做完先不要关终端 1（下一页继续用），全部做完再 Ctrl+C”；或把 4:3 前置改成“若服务已停，先跑步骤 2 的重启命令”
4. 3:79-80 | “旧的 `/health` 现在通吗？（参考：`/healthz` 回 `{"ok":true}`；旧 `/health` 回 `{"detail":"Not Found"}`，HTTP 状态码 404。）” | 从第 3 页起给的查看方式一直是 `curl -s`，只回 body，看不到“状态码 404”；学生得自己想到加 `-i` 或去终端 1 访问日志里找 | 参考里补：“用 `curl -s -i http://127.0.0.1:8000/health` 可看到 `HTTP/1.1 404 Not Found`”（或注明“状态码看终端 1 访问日志”）
5. 3:59 / 4:61-66 / 5:73-76 | “你应该看到 `{"ok":true}`” / 两行 JSON 期望块 | `curl -s` 输出不带结尾换行：真实终端里提示符紧贴 `}`（实测 `{"ok":true}<<END`），两页截图却把提示符画到下一行；两条 curl 一起粘贴时两段 JSON 会连成一行，和“两次输出一字不差（两行）”的观感不符 | 三页 curl 末尾统一加 `-w '\n'`；或在这三处各加一句“JSON 后没有换行、提示符紧跟其后，属正常”
6. 4:17 | “把 `lab/app.py` **整个替换**成下面这段（第 3 页的代码全部删掉，不要留）：” | 没写“保存”（3:18 有写“保存”）。不按 Ctrl+S 直接重启，服务继续跑旧代码：实测页 4 返回 `HTTP 404 {"detail":"Not Found"}`，与期望两行 JSON 完全不同，学生会去怀疑接口路径/curl 写法 | 步骤结尾加：“（Ctrl+S 保存后再重启）”
7. 4:76 | “第 5 页填 `keywords`，第 7 页填 `sql` 和 `rows`” | 与页 5 两处“第 6 页拼 SQL”（5:8、5:88）矛盾，至少一处页码错：学生翻页会找错地方 | 以实际分工统一：若第 6 页确为“拼 SQL”，改成“第 6 页填 `sql`，第 7 页填 `rows`”；否则改页 5 两处
8. 5:17 | “把 `lab/app.py` **整个替换**成下面这段：” | 比 4:17 同一句少了“第 4 页的代码全部删掉，不要留”。实测把页 5 代码追加在页 4 代码下面不报错、输出仍对（因为 `app = FastAPI()` 被重新赋值），但留下重复的 import/app/Query//health 路由，学生以后自己改代码会被重复定义绕住 | 与 4:17 对齐：“（第 4 页的代码全部删掉，不要留）”
9. 5:17 | 同上 | 同样没写“保存”；不保存重启后仍是页 4 代码，两次 curl 的 `keywords` 都是 `[]`，与期望不符，学生会怀疑词表/抽词函数写错 | 与 #6 一起：步骤结尾加“（Ctrl+S 保存后再重启）”
10. 5:92-93 | “再把 `METRICS` 里两个词对调位置，重启，发 `{"question": "华北销售额和订单量"}`——列表里两个指标的顺序变了吗？” | 做完页 5 后文件停在 `METRICS = ["订单量", "销售额"]` 的改乱状态，没有“做完改回”的提示；若第 6 页不是整段替换，会带着打乱的顺序进入下一页 | 补一句：“验完把 `METRICS` 改回 `["销售额", "订单量"]` 再进入第 6 页”

## 附：最终 /tmp/replay35/lab/app.py（= 页 5 代码块字节原样，36 行）

```python
# lab/app.py —— 从问题里抽关键词（纯字符串规则，不用 AI）
from fastapi import FastAPI
from pydantic import BaseModel

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


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/query")
def query(q: Query):
    keywords = extract_keywords(q.question)
    return {
        "question": q.question,
        "keywords": keywords,
        "sql": None,
        "rows": [],
    }
```

## 真实输出摘录（页面写 8000，重放统一用 8011；PID/端口允许不同）

第 3 页终端 1（含 1 次访问日志）：
```text
INFO:     Started server process [923344]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8011 (Press CTRL+C to quit)
INFO:     127.0.0.1:55312 - "GET /health HTTP/1.1" 200 OK
```
第 3 页终端 2：`{"ok":true}`

第 4 页两次（逐字相同）：
```text
{"question":"华北销售额","keywords":[],"sql":null,"rows":[]}
{"question":"华北销售额","keywords":[],"sql":null,"rows":[]}
```
第 5 页两次：
```text
{"question":"华北销售额","keywords":["华北","销售额"],"sql":null,"rows":[]}
{"question":"华东的销售额是多少","keywords":["华东","销售额"],"sql":null,"rows":[]}
```
“自己改一下”复核：3 页 `/healthz`→200、旧 `/health`→404 `{"detail":"Not Found"}`；4 页 `"sql":"SELECT 1"`；5 页“昨天天气”→`[]`、METRICS 对调后→`["华北","订单量","销售额"]`——均与页面参考一致。三页截图内容与文字期望块一致（页 4/5 截图的提示符换行问题见 #5）。

最该先修：#6+#9（补“保存”，高频卡点）→ #1（端口占用闭环，本机直接阻断）→ #3（收工与下一页前置矛盾）。

清理：已 kill 本会话遗留在 8011 的 uvicorn（pid 941817，cwd 已删）并确认 8011 释放；`/tmp/replay35` 与 `/tmp/page-0*-code.py` 已删除；未修改任何 `manual/page-*.md`（`git status` 只有本报告为新增）。
