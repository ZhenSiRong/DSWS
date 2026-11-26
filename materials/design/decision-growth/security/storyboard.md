# 安全链 · Storyboard（CP1 一页 brief）

> 教学编撰声明（D57）：生长时间线 v1→v4 是**教学重构**，不是 commit 历史；终态结论全部由代码/契约/真跑证据锚定。

**链名**：安全链（图 22/23/24 · `materials/design/diagrams/04-security/`）

**核心问题（一句话）**：SQL 安全，靠模型自觉、策略，还是数据库？——答案：不是一道更严的关，是三层独立防线（guard / policy / dw_reader）+ 一个统一出口。

## Claim 表

| id | 主张 | 类型 | status |
|---|---|---|---|
| S1 | SQL_REJECTED 永不进校正闭环（retryable: false + graph 闸） | invariant | verified |
| S2 | 36/36 注入拒 + 11/11 放行 + 8/8 基线，原因码精确匹配 | invariant | verified |
| S3 | 整类拒 + 白名单，不是黑名单逐个补 | decision | verified |
| S4 | 三层防线（guard / policy / dw_reader）各自拒绝，策略拒绝不连库 | decision | verified |
| S5 | 统一出口 SQL_REJECTED + reason_code；16 码 / 3 class | decision | verified |
| S6 | dw_reader 只有 SELECT（真库实证 SHOW GRANTS / 1142） | invariant | verified |
| S7 | 真库缺口已关闭；语料 36 条有限是边界陈述 | descriptive | verified |

（详见 `claims.yaml` / `claims.md`。）

## 候选与剪枝（决策空间，[重构] 表示重构的候选，不是真实历史）

| 候选 | 被什么打脸 / 留下 |
|---|---|
| C1 [重构] 只靠 prompt 约束模型「只生成 SELECT」 | **杀**：UNION、多语句、`/*! ... */` 可执行注释全绕过；sql.policy.yaml 头注审计 D6 实测 UPDATE 过 EXPLAIN、多语句第二句照常执行 |
| C2 [重构] 黑名单逐个补（见到 UNION SELECT 就拒） | **杀**：`UNION ALL` 变体漏；`/*! DROP */` 解析器看不见、服务端执行（page-19 对账实测口径） |
| C3 [重构] 只做策略一道关 | **杀/降级**：策略软件被绕过就全无兜底 → 补只读账号第三层（E2）；账号 ALL 权限是负向入口（didilili） |
| C4 [当前] 三层防线 + 统一出口（guard / policy / dw_reader + ChannelError 16 码） | **留**：36/36 + 11/11 + 8/8 实跑、failures --check S6 PASS；拒绝不连库、失败可展示 |

参数只标 [当前值]，不当原则：`default_limit=1000`、`max_limit=1000`、`max_execution_time_ms=5000`、`read_timeout_s=10`（`sql.policy.yaml#limits/#timeout`）。

## 未知 / 反悔点

- **[已实证]** 真实 MySQL 的 `SHOW GRANTS` / `UPDATE 1142`（2026-11-27 真栈）：dw_reader = USAGE + SELECT ON dw.*，UPDATE/INSERT 得 1142，didilili=ALL 负向对照吻合（S6/S7 转 verified）。
- **[边界]** 注入语料是有限集合（36 条），不能证明挡住「所有攻击」；语料边界就是反悔点。
- 反悔点：retryable 翻 true（S1 倒）；码表分叉（S5 倒）；三层合并成一层（S4 倒）。

## 两页布局（D57 版式）

- **左页**：2×2 四格、Z 字阅读 v1→v2→v3→v4。每格「做法 + 被什么打脸 + 补上了什么」：v1 信模型 → v2 只读账号+guard → v3 policy 六关 → v4 三层防线+出口（标「当前」）。教学编撰声明放页脚。
- **右页**：终态设计 + 证据 + 可重跑命令。上半：图 22（策略六关，figcap 原文）+ 三层防线示意；下半：证据 E1 36/36+11/11+8/8（`security --check`）、E2 只读账号兜底（account.py + didilili 负向入口）、E3 16 码/3 class（`failures --check`）；右下固定一个 `[未知]` 框（真库 SHOW GRANTS/1142 已实证 + 语料有限边界）。

## 请用户决定（CP1）

1. S6 真库验证（`make docker-smoke` 第 7/8 + 真库 UPDATE 1142）排不排期？排了才能把 S6/S7 从 inferred/unknown 提到 verified。
2. 左页 v1 格要不要放「审计 D6 实测」那两条旧系统反例（UPDATE 过 EXPLAIN、多语句第二句执行）？放了更有打脸感，但篇幅紧。
3. [当前值]（default_limit=1000 等）放右页脚注还是左页 v4 格内？口径要求它们不得像设计原则。
