# claims.md · 用户旅程设计（journey）· 人读版

> 对应机器可读版 `claims.yaml`。规则（`toolbox/workflows/design-doc-growth.md` §3.1）：
> 没有 source 的 claim 不合法；没有 probe/ablation 的 claim 只能是 `inferred/unknown`。
> 终态由源码/契约锚定；v1–v4 生长时间线是教学编撰（D57），编撰声明由生成器自动带上。

## Claim 表

| id | 主张（一句） | 类型 | status | 证据锚点 | 可跑 probe |
|---|---|---|---|---|---|
| J1 | 一次问数 = 一张 12 节点图，节点 id 逐字来自 steps.yaml，按 10 stage 分组 | invariant | verified | `graph.py#AGENT_STEP_IDS` · `contracts/steps.yaml#stages` | pytest test_steps_stages + test_s6_langgraph → **9 passed** |
| J2 | SSE 流必以 result 或 error 收尾，异常兜成 INTERNAL_ERROR，绝不静默 | invariant | verified | `orchestrator.py#AgentRunner.events` · `main.py#_stream` | 同上 → **9 passed** |
| J3 | validate_sql 双关：guard 语义 + policy 安全，拒绝在执行前变成错误事件 | invariant | verified | `validate.py#validate_sql,DEFAULT_GATES` · `guard.py#check_sql` · `policy.py#enforce` | pytest tests/security → **179 passed / 2 skipped** |
| J4 | correct_sql ≤1 次、校正后回 validate 重验；SQL_REJECTED 永不进 correction | invariant | verified | `correct.py#propose_correction` · `graph.py#_route_after_validate` · `errors.yaml#correction` | pytest test_s6_langgraph → 9 passed 组内 |
| J5 | run_sql 拒绝不连库；dw_reader 仅 SELECT、去 MULTI_STATEMENTS、会话超时 | invariant | verified | `executor.py#ReadOnlyExecutor` · `account.py#verify_account` | pytest tests/security → **179 passed / 2 skipped** |
| J6 | 前端按契约解析：未知类型留痕不报错、坏帧 PROTOCOL_ERROR、无终态补 STREAM_INCOMPLETE | descriptive | verified | `api.ts#parseAgentEvent,SseParser` · `App.tsx#ask` | `npm test` → **40 passed** |
| J7 | 结果表不猜类型（columns[].type）；空结果=空态；伪 SQL 数据行有止损卡 | descriptive | verified | `ResultTable.tsx#formatCell` · `result.ts#looksLikePseudoError` · `orchestrator.py#_finish_execution` | `npm test` → **40 passed** |
| J8 | 3024→TIMEOUT 已真库实测转正；1205/1317 未真触发（仅参数化单测）；取消竞态无真并发测试 | descriptive | unknown | `executor.py#_ERROR_CODE_MAP` · `account.py#verify_account` · `graph.py#_run_node` | 2 skipped = 拒答题（OUT_OF_RANGE/UNSUPPORTED_INTENT）runtime skip，非真库用例 |

## 证据与消融（ablation）要点

- **J1**：改名 steps.yaml 任一节点 → `test_steps_stages` 红。机器校验「没有节点漏掉阶段」，12 节点 / 10 步与 prd 数字一致——12 个节点分属 steps.yaml 的 10 个 stage 分组（第 2 阶段「召回」含 3 个节点：列/值/指标），correct_sql（第 9 阶段）是条件节点，界面在 12 步上标「1 条件步」。
- **J3/J4**：把 `DEFAULT_GATES` 去掉 policy、或把 `SQL_REJECTED` 的 `retryable` 改 true → 安全语义用例红。双保险的边界（拒绝不重试）是**契约决定**，不是模型自觉。错误码 16 码 = 6 可重试 + 10 不可重试。
- **J5**：删 `execute()` 的 `enforce` 前置 → 被拒 SQL 会连库，安全用例红。「拒绝不连库」在 `ReadOnlyExecutor.execute` 里是第一行。
- **J6/J7**：`npm test` 里 sse 26 例 + result 14 例覆盖契约解析、SSE 半帧、空结果、伪 SQL 识别。

## 反悔点（什么时候这些 claim 会翻）

1. **J1 的「10 步」口径**：10 是 `stages` 的教学分组数，不是「10 条 SSE 事件」——SSE 上是每节点一条 progress。若后续把 stages 重排，J1 的表述要跟着改。
2. **J4 的次数**：max_attempts=1（即纠错链的补考上限 N，契约名 `correction.max_attempts`）是 `[当前值]`（契约现值），不是设计原则；改成 2 并不违反「双保险」，但会改变「校正后重验」的叙事重量。
3. **J8**：3024 已真库实测转 TIMEOUT；1205/1317 未真触发（仅参数化单测，仍依赖 MySQL 版本行为），真触发一次才转正；取消竞态待真并发实测。
4. **v1–v4 生长线**：教学编撰（D57）。每格「被打脸」锚定的是源码注释里的审计记录（D4/D6/B4/F3/F11/FP-8）与旧系统缺陷引用（旧 `App.tsx:149`），不是 commit 时间序；拿到真实史料可替换并撤编撰声明。
