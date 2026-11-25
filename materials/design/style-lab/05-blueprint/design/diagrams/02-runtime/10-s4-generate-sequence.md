# 10 · S4 生成 SQL 流水线

**一句话**：S4 把上下文压成 7 个提示词槽位交给生成器，拿到载荷后**先校验形状**（`sql_or_refusal` 契约）、**再校验内容**（sqlglot 静态规则）；两道关任一不过，产物都降级成「有名字的拒答」，不存在第三种状态。

**这张图回答**：上下文怎么进提示词？生成器有两种，怎么选？为什么形状校验必须在静态校验之前？

**图例**：紫色 = 查询时服务；灰色 = 外部 LLM（未验证）；红色语义 = 违规即拒答。

## 参与者（真实进程 / 类）

| 图上名字 | 真实实体 | 文件 |
|---|---|---|
| `AgentRunner` | `draft_sql()` / `validate_draft()` 的调用方 | `backend/app/agent/orchestrator.py` L245 / L293 |
| `ContextBuilder` | `OfflineContextBuilder` 或 `context_from_recall_state()` | `backend/app/generate/context.py` L94 / L409 |
| `SlotBuilder` | `build_slots()`，固定 7 个槽位 | `backend/app/generate/provider.py` L109 |
| `PromptRenderer` | `render_prompt()`，缺槽抛 `PromptSlotError` | `backend/app/generate/prompts.py` L56 / L182 |
| `Generator` | `DeterministicGenerator` / `HttpLlmGenerator` | `backend/app/generate/provider.py` L138 |
| `LLM` | OpenAI 兼容端点（`HttpLlmGenerator.from_env()`） | `backend/app/generate/provider.py` |
| `OutputSchema` | `validate_payload(payload, "sql_or_refusal")` | `backend/app/generate/output_schema.py` L34 |
| `Guard` | `check_sql()`，sqlglot AST | `backend/app/generate/guard.py` L151 |

## 主线

1. `draft_sql()`：`build_slots()` → `render_prompt("generate_sql")` → `engine.generate()` → `validate_payload()`（`pipeline.py` L72–L133）。
2. 生成器二选一：配了 LLM 环境变量用 `HttpLlmGenerator`，否则 `DeterministicGenerator`（`main.py` L104–L110）。不配模型时 `_build_corrector()` 返回 `None`，`correct_sql` 显式 skipped。
3. `validate_draft()`：`check_sql()` 返回 `GuardReport`；`ok=False` 时取第一条违规降级为 `Refusal`（`pipeline.py` L135–L177）。

## 两道关的顺序为什么不能换

形状不对的产物（非 JSON、缺 `sql`/`refusal` 键）根本进不到 AST 解析——先解析会抛 `ParseError`，把「模型没按契约说话」误报成「SQL 语法错误」。所以：`validate_payload` 在前，`check_sql` 在后。

## 静态校验的硬规则（`guard.py`）

| 规则 | 违规码 | 可重试 |
|---|---|---|
| SQL 为空 | `SQL_EMPTY` | false |
| 多条语句 | `SQL_MULTIPLE_STATEMENTS` | false |
| 非只读（含写关键字兜底） | `SQL_NOT_READ_ONLY` | false |
| 表 / 列不在上下文 | `SQL_UNKNOWN_TABLE` / `SQL_UNKNOWN_COLUMN` | true |
| 投影常量 / NULL | `SQL_CONSTANT_PROJECTION` | true |
| 排名意图缺 `ORDER BY` / `LIMIT` | `SQL_MISSING_ORDER_BY` / `SQL_MISSING_LIMIT` | true |
| 无法解析 | `SQL_SYNTAX` | true |

## `correct_sql` 的条件性

校正**不在** S4 里发生。它由 S6 编排器在「校验失败 且 `retryable=true` 且 `attempts < max_attempts`」时插入一次（`orchestrator.py` L305–L340），`max_attempts` 来自 `contracts/errors.yaml` 的 `correction.max_attempts: 1`。没有校正器（未配 LLM）时这一步显式 skipped。

## 证据

| 结论 | 状态 | 出处 |
|---|---|---|
| 7 个槽位、缺槽即抛 | ✅ | `provider.py` L109–L124、`prompts.py` L56 |
| 形状校验先于静态校验 | ✅ | `pipeline.py` L112–L133 与 L156–L176 |
| 生成器默认确定性、可选 LLM | ✅ | `main.py` L104–L110 |
| `max_attempts: 1` | ✅ | `contracts/errors.yaml` `correction` 段 |
| 真实 LLM 返回 JSON 的形状 | ⚪ | 无端点 / 无 Key，本机未跑 |
| 确定性生成器 10 题基线 | 🟡 | 需跑 `make stage4`；本次未执行 |

## 边界

- 本图不画 `correct_sql` 的完整闭环，只画它的触发条件；状态机见 12。
- `render_prompt()` 读的是 `contracts/prompts/generate_sql.prompt` 的 frontmatter，改提示词不改代码。
- `HttpLlmGenerator` 的超时 / 重试策略不在本图范围，属 S8。
