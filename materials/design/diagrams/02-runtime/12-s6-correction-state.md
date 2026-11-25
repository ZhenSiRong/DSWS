# 12 · S6 校正闭环状态机

**一句话**：一次问数是一条**单向前进、只允许一次回退**的状态机：校验失败且 `retryable=true` 时回到「校验」重来一次；`retryable=false` 或次数用尽就直接终止，执行阶段的失败永不回退。

**这张图回答**：什么情况下会走 `correct_sql`？走完之后为什么必须重新校验？哪些失败是不可重试的？

**图例**：绿色 = 正常收尾；红色 = 失败收尾；灰色 = 取消收尾。

## 状态与真实事件

| 状态 | 对应 `steps.yaml` 步骤 | 真实工作 |
|---|---|---|
| 初始 · 收到 query | — | `query()` 建 `request_id` + 取消开关 |
| 上下文 8 阶段 | 前 8 个 step | `OfflineContextBuilder.phases()` |
| 生成 generate_sql | `generate_sql` | `draft_sql()` |
| 校验 validate_sql | `validate_sql` | `validate_sql(gates=("guard","policy"))` |
| 校正 correct_sql ×1 | `correct_sql`（`conditional: true`） | `propose_correction()` |
| 执行 run_sql | `run_sql` | `ReadOnlyExecutor.execute()` |
| result | — | `to_result_payload()` |
| error · EMPTY_RESULT | `run_sql` 仍为 success | 0 行，`class=empty` |
| error · 终止 | 出错的那一步 | 码来自 `errors.yaml` |
| error · CANCELLED | — | `class=cancelled` |

## 唯一的回退边

`校验 → 校正 → 校验` 是全图**唯一**的环，条件写死在 `orchestrator.py` L305：

```python
if attempts >= max_attempts or not failure.retryable:
    ... 终止
correction_attempted = True
proposal = yield from self._correct(...)
attempts += 1
continue          # 回到循环顶部，重新校验
```

- `max_attempts` 来自 `contracts/errors.yaml` 的 `correction.max_attempts: 1`。
- `retryable` 来自错误码表：`SQL_REJECTED` / `SQL_NOT_READ_ONLY` / `SQL_MULTIPLE_STATEMENTS` / `SQL_EMPTY` / `EMPTY_RESULT` / `TIMEOUT` / `CANCELLED` / `LLM_REFUSAL` 都是 `false`。
- 重试必须**重新过 guard + policy**（`revalidate: true`，`revalidate_with: [guard, policy]`）——校正后的 SQL 不享受任何豁免。

## `retryable=false` 为什么直接终止

安全策略的拒绝永远不可重试：把被拒的 SQL 再喂给模型「改一下」，等于给注入开了一条重试通道（`contracts/errors.yaml` 顶部注释）。

## 证据

| 结论 | 状态 | 出处 |
|---|---|---|
| 只有一条回退边，且最多 1 次 | ✅ | `orchestrator.py` L282、L305–L340 |
| `retryable` 从错误码表读 | ✅ | `backend/app/agent/errors.py` L292 |
| `max_attempts: 1` + `revalidate` | ✅ | `contracts/errors.yaml` `correction` 段 |
| 执行阶段失败不校正 | ✅ | `orchestrator.py` L392–L415 |
| 每个状态在 SSE 上都有 running/success/error/skipped | ✅ | `orchestrator.py` L168–L180、L426–L440 |
| 一次真实校正的往返 | ⚪ | 需要 LLM；本次未跑 |

## 边界

- 状态名是中文标签 + ASCII id，便于在 Mermaid 里稳定渲染；id 与代码无耦合。
- 「校正失败」包含两种情况：没有校正器（`corrector is None`）与校正器返回 `ok=False`。
- `EMPTY_RESULT` 是**收尾状态**，不是失败：`run_sql` 那一步在 SSE 上仍是 `success`。
