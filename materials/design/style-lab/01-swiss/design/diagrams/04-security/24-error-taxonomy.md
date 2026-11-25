# 24 · 错误码分类（16 码 / 3 class / retryable）

**一句话**：`contracts/errors.yaml` 给每一种失败一个名字，并按 `failure` / `empty` / `cancelled` 三类决定 UI；只有 6 个码允许一次 `correct_sql` 校正，`SQL_REJECTED` 永不可重试。

**这张图回答**：16 个错误码分别属于哪个 class？哪些能自动校正？空结果和用户取消为什么不算失败？失败最后怎么变成 SSE 事件？

**图例**：红色=`failure`；灰色=`empty`；紫色=`cancelled`；橙色=统一错误通道。节点内列出该组的全部码。

**关键元素（16/16）**：

| class | retryable | 错误码 |
|---|---|---|
| `failure` | true | `SQL_SYNTAX`、`SQL_UNKNOWN_COLUMN`、`SQL_UNKNOWN_TABLE`、`SQL_CONSTANT_PROJECTION`、`SQL_MISSING_ORDER_BY`、`SQL_MISSING_LIMIT` |
| `failure` | false | `SQL_REJECTED`、`LLM_REFUSAL`、`TIMEOUT`、`SQL_NOT_READ_ONLY`、`SQL_MULTIPLE_STATEMENTS`、`SQL_EMPTY`、`SQL_EXECUTION_ERROR`、`INTERNAL_ERROR` |
| `empty` | false | `EMPTY_RESULT` |
| `cancelled` | false | `CANCELLED` |

- `failure`：红框 + 失败步骤红叉，共 14 个。
- `empty`：查询成功但没有数据，空态卡，**不标红**（审计 FP-8），只有 `EMPTY_RESULT`。
- `cancelled`：用户主动停止，取消态，**既不算 done 也不算失败**，只有 `CANCELLED`。
- 校正：`max_attempts=1`，`prompt=correct_sql`，`revalidate=true`，校正后的 SQL 必须重过 `guard` 与 `policy`。
- `SQL_REJECTED` 是策略拒绝的通道码；拿被拒 SQL 去问模型「改一下」等于给注入开重试口子，所以 `retryable=false`。

**证据**：
- `contracts/errors.yaml` L34–L48：三个合法 class 与校正策略。
- `contracts/errors.yaml` L50–L148：16 个码的 `label` / `class` / `retryable` / `message`。
- `backend/app/agent/errors.py` L155–L220：严格加载、class 校验、路线图 7 码核对。
- `backend/app/agent/errors.py` L340–L350：拒答码映射规则（表内保留，表外归 `LLM_REFUSAL`）。
- `backend/app/agent/errors.py` L274–L319：`ChannelError` 与 `to_event()`。
- `backend/app/agent/correct.py` L144–L232：一次校正、不可重试直接返回、产物校验。

**边界**：`class` 与 `retryable` 是契约事实，不是 UI 自行推断；`EMPTY_RESULT` 的 `retryable=false` 表示「没有数据」不应自动重试。`ChannelError.klass` 在运行时再查表，若码不在表里会抛 `ErrorTableError`，不会静默降级成 `INTERNAL_ERROR`。
