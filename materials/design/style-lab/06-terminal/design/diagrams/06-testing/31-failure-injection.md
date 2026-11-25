# 31 · 失败注入矩阵

**一句话**：六类失败只靠两个替身注入——假模型与假数据库；校验、安全策略、校正闭环和 SSE 都是真代码，所以每一类失败都能映射到一个确定的错误码。

**这张图回答**：失败从哪里注入？落到哪个错误码？属于 `failure` / `empty` / `cancelled` 哪一类？哪些会触发校正闭环？界面上长什么样？

**图例**：红色=失败与安全拒绝；橙色=夹具场景；紫色=注入替身与执行器；灰色=合法空态与用户取消；蓝色=错误码契约。

**关键元素**：

| 场景 id | 注入点 | 错误码 | class | 可重试 | 失败步骤 | 界面 |
|---|---|---|---|---|---|---|
| `sql_rejected` | Generator 返回 UNION 外带 | `SQL_REJECTED` | failure | 否 | `validate_sql` | 红框 + 红叉 |
| `sql_syntax` | Generator 返回括号不配对 | `SQL_SYNTAX` | failure | 是（1 次） | `validate_sql` | 红框 + 红叉 |
| `sql_unknown_column` | Generator 引用上下文外的列 | `SQL_UNKNOWN_COLUMN` | failure | 是（1 次） | `validate_sql` | 红框 + 红叉 |
| `empty_result` | Executor 返回 0 行 | `EMPTY_RESULT` | empty | 否 | `run_sql` | 空态卡，不标红 |
| `timeout` | Executor 抛超时 | `TIMEOUT` | failure | 否 | `run_sql` | 红框 + 红叉 |
| `llm_refusal` | Generator 主动拒答 | `LLM_REFUSAL` | failure | 否 | `generate_sql` | 红框 + 红叉 |
| 取消按钮 | `POST /api/cancel`（慢查询场景） | `CANCELLED` | cancelled | 否 | 步骤边界 | 取消态，不计完成 |

- 校正闭环：`SQL_SYNTAX` / `SQL_UNKNOWN_COLUMN` 可重试；`correct_sql` 最多 1 次，校正后的 SQL **重新过** `guard` + `policy`；被拒则落回 `SQL_REJECTED`。
- 安全红线：`SQL_REJECTED` **永远不可重试**——拿被拒的 SQL 去问模型「改一下」等于给注入开重试口子。

**证据**：
- `fixtures/failures/scenarios.yaml` L51–L73（`sql_rejected`）、L75–L94（`sql_syntax`）、L96–L111（`sql_unknown_column`）、L113–L132（`empty_result`）、L134–L150（`llm_refusal`）、L152–L171（`timeout`）、L173–L191（`slow`，供取消演练）。
- `contracts/errors.yaml` L42–L49（`correction.max_attempts=1`、`revalidate_with: guard + policy`）、L52–L92（七个通道码与 `class` / `retryable`）。
- `backend/tests/agent/test_scenarios.py` L20–L30：6 类失败场景清单；每个场景实际跑一遍流水线并与 `expect` 对账。
- `Makefile` L108–L133：`stage6` 的 `--check` / `--table` / `--scenarios` + `tests/agent` + 前端 SSE / 构建。
- `docs/SETUP-FROM-SCRATCH.md` §2.9 L608–L665：场景表与期望；§7 记录 `stage6-ui` 在真实 Edge 上给出 6 种不同状态。

**边界**：场景测试只替换模型与数据库，不需要 MySQL / LLM（✅ `Makefile` 注释与 `tests/agent/conftest.py`）；但本工作树没有重跑它们（🟡）。浏览器验收 `stage6-ui` 需要 Chrome / Edge，本次未跑（⚪）。`CANCELLED` 没有场景夹具——它由取消接口在慢查询上触发。
