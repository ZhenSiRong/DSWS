# 第 17 页 · 执行轨迹左右对照（真前端 × 真代码 · 同一次真跑）runbook v2

> 用户要求：**左栏必须是真前端界面（不是节点列表）**，右栏是真执行轨迹；**左右必须来自同一次真跑**。
> 本文件是 2026-11-20 重做版（v2）的复现说明。v1（在 backend 容器里另起进程跑 `AgentRunner`、
> 左栏画 12 节点 SSE 时间轴）已退役——`manual/shots/trace_query.py` 保留作参考，本页产物不再用它。
> 只描述现场与重跑方法，不改页面、不改判据。

## 0. 产物清单

| 文件 | 内容 |
|:--|:--|
| `manual/images/page-17-exec-trace.gif` | 左真前端截图 / 右行级代码，1600×1337 / 229 帧 / 18.32s / ~1.2MB |
| `manual/images/page-17-exec-trace.png` | 关键帧：阶段 c「校正SQL 转圈」——左红叉+转圈，右 `correct.py` L202/203 + `sql_before/error/attempts` |
| `manual/review/exec-trace-v2/meta.json` | 真跑时间轴、触发帧序、4 次尝试、对齐方法 |
| `manual/review/exec-trace-v2/trace.jsonl` | 同一请求的行级轨迹（2514 行 / 294,704 B ≤ 500KB） |
| `manual/review/exec-trace-v2/capture-frames.json` | 选中的 13 张真截图 + 每帧 DOM 探针（节点状态 / rect / 时间戳） |
| `manual/review/exec-trace-v2/frames/*.png` | 左栏真截图（800×1151，裁掉侧栏；可据此重渲染） |
| `manual/review/exec-trace-v2/render.json` | 渲染/断言报告（帧计划、每阶段停留表、OCR、对齐抽样） |
| `manual/shots/trace_server.py` | 新增：注入 `sitecustomize` tracer + 真前端截图循环 + 取证据 |
| `manual/shots/render_exec_trace.py` | 改：左=浏览器帧 / 右=代码帧，18–25s 教学可读节奏 |
| 旧 `review/exec-trace.jsonl` / `.meta.json` / `.render.json` | **已删除**（v1 证据，被 `exec-trace-v2/` 取代） |

## 1. 原理：为什么这次左栏是“真前端”，而且左右同源

```
浏览器（成熟版原版前端 dist + nginx）  ── POST /api/query (SSE) ──►  uvicorn（backend 容器，1 进程）
        │                                                                    │
        │ 每 ~360ms page.screenshot() 一帧 + DOM 探针                          │ sitecustomize 注入的 settrace
        │ 记 t_shot（浏览器 Date.now 的 epoch）                                │ 只追 4 个文件，每行一条 JSONL
        ▼                                                                    ▼
   frames/*.png + capture-frames.json                              trace.jsonl（t = time.time，同一台宿主时钟）
        └──────────────────────────  渲染时按帧时间戳对齐  ─────────────────────────┘
                     左帧 t  →  取 trace 中 ≤ t 的最后一个决定性事件（右栏）
```

- **真前端**：不是节点列表重绘。左图是 `deliverable/v2/original-frontend/dist`（react 19 + tailwind）
  在 headless Chrome 里的真实渲染；nginx `proxy_buffering off` 把 SSE 原样转给浏览器，
  流程图 12 个节点是前端按 SSE 事件自己点亮的。
- **真同一跑**：浏览器只发 1 次 `/api/query`；后端 uvicorn 那个进程一边跑一边写行级轨迹。
  两侧时间戳都来自**同一台宿主**（容器共用宿主时钟）：浏览器 `Date.now()`、后端 `time.time()`，
  单位 epoch 秒/毫秒，可以直接相减。
- **后端注入**：`sitecustomize.py` 在 Python 解释器启动时自动 import；**只有环境变量 `TRACE_OUT`
  存在时才启用**。`sys.settrace` + `threading.settrace`（LangGraph 节点跑在工作线程里，
  只装 `sys.settrace` 只能看到主线程构图代码）。只追 4 个文件：

      backend/app/agent/graph.py      12 节点图 / 条件边 / 二次校验 / 执行节点
      backend/app/agent/correct.py    一次校正：触发条件、提示词、corrector 调用、结论
      backend/app/generate/guard.py   S4 静态校验：表/列/常量投影/ORDER BY/LIMIT
      backend/app/security/policy.py  S5 安全策略：白名单/单语句/危险函数/LIMIT 补全

  每条 line 事件写一行 JSONL：`{"t","file","rel","lineno","func","vars"}`；`vars` 只收白名单
  （`sql / state.sql / original_sql / corrected_sql / attempts / failure / error / prompt / query /
  payload / proposal / sql_before / sql_after`，外加 `violations[0]` 用来显示拒绝规则），
  值截断 ≤120 字符，名字像 key/token/secret/password 的一律不记，值里出现 `.env` 的
  `REBUILD_LLM_API_KEY` 整段替换成 `<redacted>`。

## 2. 起隔离栈（`p17t2`；仓库根目录；镜像已缓存，一律 `--no-build`）

磁盘已 90%，依赖顺序不能反：先起 mysql/ES/qdrant → 关 ES 磁盘水位 → init → backend。

```bash
export MYSQL_HOST_PORT=13317 ES_HOST_PORT=19217 QDRANT_HOST_PORT=16317 \
       BACKEND_HOST_PORT=18117 FRONTEND_HOST_PORT=18017 FRONTEND_BIND=127.0.0.1
# 给 backend 注入 TRACE_OUT 环境变量（不改仓库里的 compose.yaml）
cat > /tmp/p17t2-override.yaml <<'EOF'
services:
  backend:
    environment:
      - TRACE_OUT=/tmp/trace.jsonl
      - TRACE_ROOT=/app
EOF

docker compose -p p17t2 --env-file .env -f compose.yaml -f /tmp/p17t2-override.yaml \
  up -d --no-build mysql elasticsearch qdrant                          # 等 3 个 healthy
curl -s -X PUT http://127.0.0.1:19217/_cluster/settings -H 'Content-Type: application/json' \
  -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false}}'
docker compose -p p17t2 --env-file .env -f compose.yaml -f /tmp/p17t2-override.yaml \
  up -d --no-build init backend                                        # init Exited(0) → backend healthy
docker exec p17t2-backend-1 python -c \
  "from app.generate.provider import HttpLlmGenerator; print(HttpLlmGenerator.from_env().name)"   # http-llm
```

成熟版前端（**不启 compose 的 frontend 服务**，省出端口；nginx 进 `p17t2_default` 才解析到 `backend`）：

```bash
docker run -d --name p17t2-mature --network p17t2_default -p 127.0.0.1:8088:80 \
  -v "$PWD/deliverable/v2/original-frontend/dist:/usr/share/nginx/html:ro" \
  -v "$PWD/deliverable/v2/original-frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  "$(grep '^NGINX_IMAGE=' .env | cut -d= -f2)"
curl -s http://127.0.0.1:8088/api/health     # {"status":"ok","stage":"S7"}
```

> 端口/容器名都能覆盖：`trace_server.py` 的 `--app-url / --container / --health-url / --work-dir`。

## 3. 注入 tracer（一条命令）

```bash
python3 manual/shots/trace_server.py inject
```

它做四件事：读容器真实 `site.getsitepackages()`（backend 是 python 3.12 + venv，路径
`/app/backend/.venv/lib/python3.12/site-packages`）→ `docker cp` 内嵌的 `sitecustomize.py`
（docker cp 会带 root 权限，需 `docker exec -u 0 chmod 644 + chown 10001:10001`）→
`docker restart` backend 并等 `/api/health` 200 → **原地清空** trace 文件。

> **坑（v2 第一版踩过）**：清空 trace 必须 `: > /tmp/trace.jsonl`，**不能 `rm`**。uvicorn 启动时
> 已用 `O_APPEND` 打开这个 inode；`rm` 之后它的行事件全部写进“已删除文件”，`docker cp` 只能拿到
> 0 字节——第一次真跑（attempt 2）就这样白跑，只能重跑。`trace_server.py` 的 `truncate_trace()`
> 已按原地截断实现，并检查 `/proc/1/fd` 里 uvicorn 是否真的打开着这个文件。

验证 tracer 真的在写：`docker exec p17t2-backend-1 sh -c ': > /tmp/trace.jsonl'` 清空后，
`docker exec p17t2-backend-1 python -c "import sys;sys.path.insert(0,'/app/backend');
from app.agent.correct import propose_correction;propose_correction(None,'select 1',None,corrector=None)"`
会立即写出若干条 `correct.py` 行事件（再清空即可；这不是问数请求、不花模型调用）。
实测：注入后重启到 healthy 约 8s；启动时 import 会记 ~420 行模块级事件，真跑前会被清空。

## 4. 真跑：同一次请求 = 左截图 + 右轨迹

```bash
python3 manual/shots/trace_server.py capture --attempts 4
python3 manual/shots/trace_server.py crop          # 选帧 / 裁图 / 存证据（≤500KB trace）
python3 manual/shots/render_exec_trace.py          # 出 GIF/PNG + 全部断言
python3 manual/shots/render_exec_trace.py --verify-only   # 只复验已有产物
```

`capture` 每次尝试：原地清空 trace → 打开成熟版 → 往 textarea 填
`查询销售额大于平均销售额的商品` → 点「发送」（记录点击 epoch = 时间轴 0）→
每 ~360ms `page.screenshot()` 一帧并写 DOM 探针（12 节点状态、cardRects、结果表 rect、
`scrollHeight/clientHeight`）→ 监听到 result 且发送按钮复位后再拍 15 帧 → 取回 trace。

- **触发判读**（`judge_trigger`）：SSE 序列必须满足
  `validate_sql:error` → `correct_sql:running` → `correct_sql:success`（**只 1 轮**）→
  二次 `validate_sql:success` → `run_sql:success` → `result`。
  真实模型**不保证每次触发**（本页第 2 次采样时校验一次就过了、校正未触发）；不触发的尝试丢弃重跑，
  `--attempts` 次都没触发就报错退出，**不出假图**。
- 视图：`1440×1640 @1.5x`。选这个高度是让结果 5 行时页面一屏放下（`scrollHeight 1447` vs
  `clientHeight 1441`，只有 6px 滚动），左图裁掉 300px 侧栏后 1140×1640 → 缩到 800×1151。
- 客户端 SSE 用 `addInitScript` 包了一层 `fetch`，把每个 event 的**到达时刻**记下来
  （与后端同一时钟），既做对齐，也做“同一跑只发过 1 次请求”的断言。

本次 4 次尝试（全部真跑；LLM 每次 2 次调用，见 `meta.json.attempts`）：

| # | 结果 | 时长 | 帧 | trace 行 | 处置 |
|:-:|:--|--:|--:|--:|:--|
| 1 | 校正未触发（一次校验就过，校正SQL=未触发） | 20.7s | 29 | 0 | 丢弃重跑 |
| 2 | 触发且成功，但 trace 落进已删除 inode | 28.6s | 41 | 0 | 作废（坑见 §3） |
| 3 | 触发且成功 | 32.9s | 48 | 2694 | 探针还没有 rect 字段，被第 4 次取代 |
| 4 | 触发且成功 | 27.8s | 42 | 2514 | **保留**（本页全部证据） |

每次真跑的 LLM 调用：没有触发校正的尝试只 1 次（`generate_sql`）；触发并校正成功的尝试 2 次
（`generate_sql` + `correct_sql`）。所以保留这次 **2 次**，4 次尝试合计 **7 次**
（`meta.json.llm_calls` / `llm_calls_all_attempts`）。

保留这次的真实时间轴（相对点击，秒；`meta.json.timeline_s`）：

```
request 0.044 → 8 个上下文节点 0.099–0.132 → generate running 0.153
generate success 11.117（真实等待 10.983s）→ validate1 running 11.119 → error 11.153（33.4ms）
→ correct running 11.170（trace L203 在 11.175）→ success 18.468（真实等待 7.309s）
→ validate2 running 18.472 → success 18.541（66.9ms）→ run_sql success 18.604（60.3ms）
→ result 18.606      真实一次跑（request→result）= 18.562s
```

第一次校验的真实错误码是 **`SQL_UNKNOWN_TABLE`**（“限定符 t 不在契约上下文里”），
不是任务示例里的 `SQL_UNKNOWN_COLUMN`；`correct_sql` 只 1 轮，校正后的候选 SQL 重过
guard + policy 才变绿。LLM 调用次数 **2**（generate 1 + correct 1，轨迹里 `graph.py:239
draft_sql(...)` 与 `correct.py:203 corrector.correct(...)` 各只出现 1 次；对应两段真实等待）。

## 5. 渲染：18–25s 教学可读节奏

| 阶段 | 内容 | 真实耗时 | GIF 停留 |
|:-:|:--|--:|--:|
| 0 输入真问题 | 真 textarea 里已填好问题（未发送）；右栏说明 tracer/证据源 | — | 2.48s |
| 1 提交 → 构图 | 左「正在连接问数智能体…」；右 `build_agent_graph()` L456 返回 `graph.compile()` | 0.10s | 1.20s |
| 2 生成SQL 执行中 | 左「生成SQL」转圈；右 `graph.py:239 draft = draft_sql(` 停在调用行 | 10.98s | 3.04s |
| 3 校验SQL 红叉 | 左「校验SQL」红叉 + 「校正SQL」转圈；右 `guard.py:306 if violations: return GuardReport(False)` + `violations[0].code` | 33ms | 2.64s |
| 4 校正SQL 转圈 | 左校正SQL 转圈；右 `correct.py:202/203 try / payload = corrector.correct(...)` + `sql_before / error / attempts 0/1` | 7.31s | 3.12s |
| 5 校正成功 + 二次校验 | 左三节点变绿；右 `graph.py:296 _emit(VALIDATE_STEP,"success")` + `sql_after / state.attempts 1` | 67ms | 2.64s |
| 6 结果表 5 行 | 左真结果表（5 行 × 3 列）；右 `graph.py:404 _emit(RUN_STEP,"success")` | 60ms | 3.20s |

- 229 帧 × 80ms = **18.32s** 循环（GIF 每帧延迟 8cs = 12.5fps）；末帧结果表停 3.20s（≥2.5s）。
- 每帧左上角是「阶段 n/6 · 阶段名 · 真实耗时」chip；底部固定条写
  **「时间轴已压缩，非实速」+ 本 GIF 循环时长 + 真实一次跑（生成 10.98s / 校正 7.31s）**。
- 左栏高亮框的位置**来自该帧的 DOM 探针 rect**（换算到 800×1151 截图坐标），不是手画的；
  每段真截图按 2 帧一换轮播（spinner 真的在转），d/e 两个阶段用同一张终态真截图、靠高亮/右栏区分。
- 右栏长等待（阶段 2/4）不假装“实时”：锚点是那个已经被执行过的调用行，对齐卡会写
  **「差 X s：不是错位，是“仍停在这一行”」**——按帧时刻它确实还阻塞在 `draft_sql()` /
  `corrector.correct()`；其余阶段（3/5/6）抽样对齐误差 <1s（见 `render.json.alignment.samples`）。
- 关键帧 PNG 取阶段 4 的中间帧（帧 137/229）：左「校验SQL 红叉 + 校正SQL 转圈」，
  右 `backend/app/agent/correct.py propose_correction()` L203 高亮 + `sql_before`（第一次的
  SQL）/`error.code=SQL_UNKNOWN_TABLE`/`error.message=限定符 t 不在契约上下文里`/`attempts 0 / max 1`。
- GIF 合成用 ffmpeg 两遍法（抽样生成全局调色板 → paletteuse）；帧序列用固定 `framerate=12.5`
  输入，保证每帧延迟都是 8cs。体积超 5MB 时按候选降宽（1600→1500→1440→1400→1300→1200）或
  降色，不砍停留。

## 6. 本机验证结果（`render.json` 可复核）

- trace 断言 **15/15**：`validate:error` 在 `correct` 前、`correct` 只 1 轮 running/success、
  二次 `validate:success`、`run_sql:success`、`result` 在其后、4 个目标文件都有行事件、
  时间戳单调、无 API key、无绝对路径/用户名/隔离端口、≤500KB、`correct.py:203`/`guard.py:306` 被追到。
- 产物断言（`--verify-only` 可复跑）：1600×1337、229 帧、18.32s、1250KB、12.5fps、关键帧在阶段 4、
  首/中/末帧像素差 >0、末帧 OCR 读到 `查询结果` + `71992/55992/56994/22400/32994` + 节点名
  `召回字段信息/生成SQL/执行SQL`，第一帧 OCR 读到输入框里的「查询销售额大于平均销售额的商品」
  与「电商问数 / 智能数据分析」，画面里没有用户名/绝对路径/隔离端口。
- LLM 调用次数：保留这次 **2 次**（generate 1 + correct 1，轨迹里 `graph.py:239` / `correct.py:203`
  各只出现 1 次，对应两段真实等待 10.983s / 7.309s）；4 次尝试合计 7 次（见 §4）。
- 对齐抽样（左帧 ↔ 右锚点）：阶段 3 差 0.273s、阶段 5 差 0.393s、阶段 6 差 0.328s（均 <1s）；
  阶段 2/4 是长等待态，按“仍停在该行”表达（`meta.json.alignment`）。
- 结构审计：`python3 manual/shots/audit_book.py` 末行 `页面：24/24 通过；README 坏链：0`；
  `make audit` 4/4（结构 / 空白 / uv.lock / 敏感串）。

## 7. 诚实边界

- **单次采样**：LLM 温度 0 也不保证每次同一路径。本次 2 次采样里 1 次触发校正（第 1 次没触发），
  本证据只保留“触发且成功”的那一次；**不能当成功率**，判据仍按 `trials>=3` 写。
- **行级轨迹 ≠ 完整调用栈**：只追 4 个文件；`pipeline.py` / `validate.py` / sqlglot / httpx
  内部与 8 个上下文节点内部都不记；模型等待帧只有调用点，没有 HTTP 细节。
- **时间轴压缩**：生成 10.98s / 校正 7.31s 在 GIF 里分别停 3.04s / 3.12s；真实耗时才写在
  chip 与底部条里，不是实速回放。
- **阶段 5 的左帧**：二次校验只 67ms、浏览器没单独画过“校验绿但还没结果”的一帧，
  所以阶段 5 用的是整条闭环完成后的同一张真截图（结果表也在画面里），靠高亮三节点区分；
  阶段 6 再单独高亮结果表。没有拿别的时刻的帧冒充。
- **OCR 中文依赖 `chi_sim`**：本机 `/usr/share/tesseract-ocr` 只有 eng/osd，脚本会尝试从
  `tessdata_fast` 下载一份到 `/tmp/p17t2-tessdata`（`TESSDATA_PREFIX`）；没网时中文断言退化为
  只有英文/数字 + DOM 证据（`render.json.output_check.ocr.chinese=false`）。
- **任务示例里的 `41099.5` 不属于这个问题**：`41099.5` 是第 23 页「华北销售额」的答案；
  本问题「查询销售额大于平均销售额的商品」返回的是 5 行商品（销售额 71992/55992/56994/22400/32994），
  所以断言按本次真实数值写，不写死 `41099.5`。
- 画面里没有用户名 / 主机名 / 绝对路径 / API key / 隔离端口；代码窗口只显示仓库相对路径。

## 8. 清理

```bash
docker rm -f p17t2-mature
docker compose -p p17t2 --env-file .env -f compose.yaml -f /tmp/p17t2-override.yaml \
  down -v --remove-orphans
rm -f /tmp/p17t2-override.yaml && rm -rf /tmp/p17t2-run /tmp/p17t2-work
git checkout -- backend/uv.lock 2>/dev/null
docker ps -aq | sort > /tmp/after.txt && diff <(sort /tmp/p17-baseline.txt) /tmp/after.txt && echo "用户栈 24 容器 ID 不变"
```

（清理前后都要对比容器 ID 集合：基线 24 个，其中 16 个 running。`down -v` 只删 `p17t2_*` 的容器/卷/网络，
不碰 `dsws-trace` / `dsws-lab-ui` / `downloads` 等用户栈。）
