# 第 17 页 · 执行轨迹左右对照（真跑 · 真代码路径）runbook
> 补的动态证据：左栏 12 节点 SSE 时间轴，右栏 `sys.settrace` 行级代码窗口；不改页面/判据，不上 UI。
> 产物：`images/page-17-exec-trace.gif`、`images/page-17-exec-trace.png`、`review/exec-trace.jsonl`(+meta)、`shots/trace_query.py`、`shots/render_exec_trace.py`。

## 1. 原理（为什么这么追）
- 左栏：`AgentRunner.events()` 的真实 SSE（progress/result），每条带 wall-clock；节点状态 = 截至该时刻最后一条 progress 的 status。
- 右栏：`sys.settrace` 行级轨迹，**只追 4 个文件**——`agent/graph.py`（12 节点与条件边）、`agent/correct.py`（一次校正）、`generate/guard.py`（S4 静态校验）、`security/policy.py`（S5 安全策略）。它们是这次问数真正做判断的四个代码点；追全部文件只会看到 sqlglot/httpx 内部行。
- LangGraph 节点跑在**工作线程**（主线程只消费事件），所以 `threading.settrace` 也要装：实测只装 `sys.settrace` 只能追到主线程的构图代码（第一次 489 行全是编译期，节点里 0 行）。
- 记录 `file:lineno`/`function`/时间戳 + 白名单局部变量（sql/sql_before/sql_after/error/attempts/prompt 等，≤120 字符）；变量名带 key/token/secret/password 的不记，值里出现 API key 整段替换。
- 渲染：每帧拼深色终端风 HTML（1200×800 CSS），Chrome @2x 截图 → 缩到 1600px 宽 → ImageMagick 合 GIF；左栏按 SSE、右栏按行事件（两者差毫秒，左栏不能用行时间反查，否则会“右边在跑校正、左边还红着”）。

## 2. 怎么重跑（仓库根目录；单栈，跑完 down -v）
```bash
export MYSQL_HOST_PORT=13397 ES_HOST_PORT=19297 QDRANT_HOST_PORT=16397 \
       BACKEND_HOST_PORT=18197 FRONTEND_HOST_PORT=18097 FRONTEND_BIND=127.0.0.1
docker compose -p p17trace --env-file .env up -d --no-build mysql elasticsearch qdrant   # 等 3 个 healthy
curl -s -X PUT http://127.0.0.1:19297/_cluster/settings -H 'Content-Type: application/json' \
  -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false}}'          # 磁盘 90%，关水位
docker compose -p p17trace --env-file .env up -d --no-build init backend                 # init Exited(0) → backend healthy
mkdir -p /tmp/p17trace-out && chmod 777 /tmp/p17trace-out                                # 容器里是 app 用户（10001）
docker compose -p p17trace --env-file .env run --rm --no-deps \
  -v "$PWD/manual/shots/trace_query.py:/tmp/trace_query.py:ro" -v /tmp/p17trace-out:/out \
  backend python /tmp/trace_query.py --out-dir /out
cp /tmp/p17trace-out/exec-trace.jsonl /tmp/p17trace-out/exec-trace.meta.json manual/review/
python3 manual/shots/render_exec_trace.py                 # 重出 GIF/PNG + 全部断言
python3 manual/shots/render_exec_trace.py --verify-only   # 只验证已有产物
```
## 3. 期望看到什么（本次实测）
- 27 帧 SSE：9 个上下文节点 → `generate_sql` running→success（13.0s）→ `validate_sql` running→**error**（220ms）→ `correct_sql` running→success（9.8s）→ `validate_sql` running→success（498ms）→ `run_sql` running→success（314ms）→ `result` 5 行。
- 第一次校验真实错误码是 **`SQL_UNKNOWN_TABLE`**（“限定符 t 不在契约上下文里”），**不是**任务示例里的 `SQL_UNKNOWN_COLUMN`；校正后的候选 SQL 重过 guard+policy 才变绿（correct_sql 只 1 轮）。
- 关键帧 PNG 停在 `correct.py::propose_correction` 的 L202（`try:`，下一行 203 就是 `corrector.correct(...)`），变量表 `sql_before`/`error`/`attempts` 齐全；左栏此刻 `validate_sql` 红叉 + `correct_sql` 转圈。
- GIF：1600×1067 / 41 帧 / 8.95s / 2.19MB（≤3MB）；末帧 12 节点全绿 + 证据链（含 `correct_sql: success`、`SQL_UNKNOWN_TABLE`、`validate#2: success`、`run_sql: success`）。

## 4. 诚实边界
- **单次采样**：LLM 温度 0 也不保证每次同一路径；本次第 1 次即触发（更早一次真跑第 2 次才触发），不能把单次当成功率。
- **行级轨迹 ≠ 完整调用栈**：只追 4 个文件；上下文 8 阶段内部、`pipeline.py`/`validate.py`、sqlglot/httpx 内部都不记，模型等待帧只有调用点。
- **settrace 有开销**：墙钟 27.67s；generate 13.0s / correct 9.8s 是真实模型等待，校验 220/498ms、执行 314ms 被 tracer 放大，别当性能基线。
- **500KB 上限**：原始 3159 行事件（565,861 B）按“关键帧全留 + 每 2 条抽 1 条”裁到 1589 行（288,568 B）；27 条 SSE 与 4 条 LLM 记录一条不丢。
- 画面无用户名/绝对路径/API key/隔离端口；代码窗口只显示仓库相对路径；`make audit` 敏感串 4/4 已过。

## 5. 清理
```bash
docker compose -p p17trace down -v --remove-orphans && rm -rf /tmp/p17trace-out
git checkout -- backend/uv.lock 2>/dev/null; docker ps -aq | sort | wc -l   # 回到 24（用户栈 ID 集合不变）
```
