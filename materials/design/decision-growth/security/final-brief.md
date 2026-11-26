# 安全链 · Final brief（CP2）

> 教学编撰声明（D57）：生长时间线是教学重构，非 commit 历史；结论均由代码/契约/真跑证据锚定。

## 结论（3 句）

SQL 安全不靠模型自觉，也不靠一道更严的关：是 guard / policy / dw_reader 三层独立防线各自拒绝，策略拒绝发生在连库之前。拒绝按「整类拒 + 白名单」，36/36 注入全拒、11/11 正常零误杀、8/8 基线过策略，原因码精确匹配。失败出口统一为 SQL_REJECTED 一个通道码（细因入 reason_code，16 码 / 3 class），且它永不进校正闭环。

## 产物链接

- 渐进稿：[`spread.png`](spread.png)（本目录已渲染；`spread.html` / `spread.pdf` 同目录）
- 机器可读 claims：[`claims.yaml`](claims.yaml)；人读版：[`claims.md`](claims.md)；CP1：[`storyboard.md`](storyboard.md)

## 已跑命令 / 结果

| 命令 | 结果 | 何时 |
|---|---|---|
| `(cd system/backend && .venv/bin/python -m app.scripts.security --check)` | 36/36 拒 + 11/11 放 + 8/8 基线，S5 PASS | 本轮实跑 |
| `(cd system/backend && .venv/bin/python -m app.scripts.failures --check)` | 9 场景全对、错误码表 16 码，S6 PASS | 本轮实跑 |
| `make stage5` | 813 passed / 30 skipped，S5 PASS | 本轮（2026-11-27）记录（page-19 同口径） |
| page-19 拆一刀（`forbid_set_operations: false`） | FAIL: 2——2 条 UNION 原因码退化 SQL_NOT_READ_ONLY，漏到执行 0 条 | 重放记录 |
| 真库 `SHOW GRANTS FOR 'dw_reader'` + `UPDATE`（真栈补验） | USAGE + SELECT ON dw.*；UPDATE/INSERT 实测 ERROR 1142；didilili=ALL 吻合 | 2026-11-27 真栈 probe |

## 已知未知

- 真实 MySQL 的 `SHOW GRANTS` / `UPDATE 1142` 已实证（2026-11-27 真栈 probe）：SHOW GRANTS = USAGE + SELECT ON dw.*，UPDATE/INSERT 实测 ERROR 1142，didilili=ALL 负向对照吻合 → S6 `verified`。
- 注入语料是有限集合（36 条），不能证明挡住「所有攻击」——保留为边界陈述（非缺口）→ S7 `verified`。
- [当前值] `default_limit=1000` / `max_execution_time_ms=5000` 是当前配置，不是设计原则。

## 学生可读性检查（三项复述答案）

1. **N / 参数是什么**：语料 36 条注入 + 11 条零误杀 + 8 条 S4 基线；错误码 16 个（= 6 可重试 + 10 不可重试）/ 3 class；LIMIT 默认与上限 1000 [当前值]。
2. **哪些错误不能重试**：SQL_REJECTED（retryable: false）永不进 correct_sql——拿被拒 SQL 问模型「改一下」等于给注入开重试口子；同类不可重试的还有 TIMEOUT / LLM_REFUSAL / SQL_NOT_READ_ONLY / SQL_MULTIPLE_STATEMENTS。
3. **拆掉什么会红**：`forbid_set_operations: false` → 门禁 FAIL: 2（2 条 UNION 原因码退化）；`forbid_executable_comments: false` → 两行「竟然被放行了」（真漏到执行层）；SQL_REJECTED 的 retryable 翻 true → sql_rejected 场景红。

## 后续动作

- 有：S6/S7 已由 2026-11-27 真栈 probe 提级（SHOW GRANTS + UPDATE 1142 实证）；余下只有语料边界跟进——持续补变体、`security --corpus` 判定表对账。
- 合入主 PDF 时按 D57 版式替换图 22/23/24 页，合入前按 workflow §9 重跑本链 probe（security --check + failures --check）。
- 无须改教程/契约：page-19 与 sql.policy.yaml / errors.yaml 口径本轮已对上。
