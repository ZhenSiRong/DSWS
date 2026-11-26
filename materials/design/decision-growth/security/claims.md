# 安全链 · claims（人读版）

> 教学编撰声明（D57）：v1→v4 的生长时间线是**教学重构**，不是 commit 历史；下面每条 claim 的结论都由代码/契约/真跑证据锚定。
> status 口径：`verified` = 本轮实跑 probe 或本轮/重放记录里的真跑证据（probe 里写了复核命令）；`inferred` = 只有代码/契约可证；`unknown` = 证据缺口。
> 数字口径：全部来自 `materials/design/decision-growth/security/data.yaml` 及其引用的原始出处（page-19 / 契约 / 代码），不引入新数字。

## Claim 表

| id | 主张 | 类型 | status | 一句话证据 |
|---|---|---|---|---|
| S1 | SQL_REJECTED 永不进校正闭环 | invariant | verified | errors.yaml `retryable: false` + graph.py:316 重试闸；failures --check S6 PASS |
| S2 | 36/36 拒 + 11/11 放 + 8/8 基线，且原因码精确 | invariant | verified | 本轮实跑 `security --check` → S5 PASS |
| S3 | 整类拒 + 白名单，不是黑名单逐个补 | decision | verified | sql.policy.yaml 构造级开关 + page-19 拆一刀实测 |
| S4 | 三层防线（guard / policy / dw_reader）各自拒绝，策略拒绝不连库 | decision | verified | pipeline.py 头注 + validate.py:5 + page-19 三层分工 |
| S5 | 统一出口：SQL_REJECTED 一个通道码，细因入 reason_code；16 码 / 3 class | decision | verified | sql.policy.yaml#errors + errors.yaml 码表；failures --check 打出 16 码 |
| S6 | dw_reader 只有 SELECT；didilili 的 ALL 是负向入口 | invariant | verified | 真库实证（2026-11-27）：SHOW GRANTS = USAGE + SELECT ON dw.*，UPDATE/INSERT 得 1142 |
| S7 | 真库只读验证缺口已关闭；语料 36 条有限是边界陈述 | descriptive | verified | 真栈 probe 实证（SHOW GRANTS/1142）；语料是固定清单 |

## 每条的证据与反悔点

### S1 · SQL_REJECTED 永不进校正闭环（verified）

- **证据**：`system/contracts/errors.yaml` 里 `SQL_REJECTED.retryable: false`，文件头注写明「拿被拒的 SQL 去问模型『改一下』，等于给注入开了重试的口子」；`system/backend/app/agent/graph.py:316` 只有 `failure.retryable` 才进 correction 分支；`system/backend/app/agent/correct.py` 文件头再次声明 SQL_REJECTED 不参与校正。**真跑**：`failures --check` 的 `sql_rejected` 场景期望结局就是 SQL_REJECTED，本轮实跑 S6 PASS。
- **反悔点**：产品口径若变成「安全拒绝也想让模型自动修一次」（把 retryable 翻 true），这条倒——而且注入语料会变成可重放的攻击面；或者校正闭环换了入口、绕开 graph.py:316 的闸。

### S2 · 36/36 拒 + 11/11 放 + 8/8 基线（verified）

- **证据**：`tutorial/page-19.md` 第 2 步判据（`app.scripts.security --check` 逐条比对原因码），本轮实跑输出与 page-19 记录一致：`36/36 条按预期拒绝 / 11/11 条放行 / 8/8 条 SQL 通过策略 / S5 PASS`。11 条 allow 语料专钉误杀点（字符串里的分号、块注释里的 `; DROP`、中文别名、`SELECT *`、子查询）。
- **反悔点**：语料扩了新类攻击而策略没跟上（36 条不再是全集）；或原因码契约（`sql.policy.yaml#errors.reason_codes`）改了而 --check 的期望没同步——「拒仍是拒、码变了」也算红（page-19 拆一刀实测口径）。

### S3 · 整类拒 + 白名单（verified）

- **证据**：`sql.policy.yaml#statement` 的 `forbid_set_operations` / `forbid_executable_comments` / `allowed_roots: [Select]` 按构造拒；表白/列白由 `schema.contract.yaml` 派生（sql.policy.yaml 头注：再抄一份表名清单就是把漂移再造一遍）。page-19 对账：类别规则 10 条（注释 2 + FORBIDDEN_CONSTRUCT 8）接住最会变形的载荷，剩下 26 条由结构规则与白名单接住。**实测**（page-19 拆一刀）：`forbid_set_operations: false` → 漏到执行 0 条，但 2 条 UNION 原因码退化 `SQL_FORBIDDEN_CONSTRUCT → SQL_NOT_READ_ONLY`，`FAIL: 2`；`forbid_executable_comments: false` → 两行「竟然被放行了」。
- **反悔点**：出现解析器看不见、服务端执行的**新构造**（可执行注释是已知一例，编码变体是潜在一例）；或契约派生白名单的链路断了（有人在 policy 里手抄表清单）。

### S4 · 三层防线各自拒绝（verified）

- **证据**：`app/security/pipeline.py` 头注把链路写成 generate（S4 静态校验）→ enforce（S5 策略）→ execute（只读账号+超时），enforce 不过就是 SQL_REJECTED、不进 execute；guard 的定义在 `app/agent/validate.py:5`（S4 静态校验）；page-19 对账给三层分工：guard 问「对不对」、policy 问「危不危险」、账号管「能不能写」，且拆掉 guard 的列校验时 policy 列白名单接住（实测口径）。
- **反悔点**：有人把三层合并成一层（比如只留 policy），或执行器换账号、绕过 account.py 的 SHOW GRANTS 校验——「策略软件被绕过时账号兜底」这句就不再成立。

### S5 · 统一出口 16 码 / 3 class（verified）

- **证据**：`sql.policy.yaml#errors` 规定对外只暴露 `SQL_REJECTED`、细因放 `reason_code`（8 个取值）；`errors.yaml` 全表 16 码（= 6 可重试 + 10 不可重试），class 只有 failure（14）/ empty（1）/ cancelled（1）三类，取消与空结果与失败分开。**真跑**：`failures --check` 本轮 S6 PASS，末段打出「错误码表：16 个码，路线图要求的 7 个全在」；page-16/17 的 20 条错单语料与 9 场景是同一批码的实跑记录。
- **反悔点**：对外码表分叉（策略把细因拆成多个对外码），下游第 16/17 页的状态机与重试判定就得按码分支——那正是 errors.yaml 头注要防的「失败没有可表达的通道」。

### S6 · dw_reader 只有 SELECT（verified）

- **证据**：`sql.policy.yaml#account` 声明 `grants: [SELECT]`；`app/security/account.py:31` 的 `FORBIDDEN_GRANT_PATTERNS` + `SHOW GRANTS` 校验（多一项就是配置事故）；负向入口是 `system/fixtures/dw.sql:9` 的 `GRANT ALL PRIVILEGES ON dw.* TO 'didilili'@'%'`。**真库实证**（2026-11-27 真栈 probe）：`SHOW GRANTS FOR 'dw_reader'@'%'` = USAGE + SELECT ON dw.*；UPDATE/INSERT 实测 ERROR 1142；didilili=ALL 负向对照吻合。
- **反悔点**：真库上 `SHOW GRANTS FOR 'dw_reader'` 出现 SELECT 之外的权限；或 init 开通账号的路径被换掉、account.py 的校验不再跑。

### S7 · 真库缺口已关闭，语料边界仍在（verified）

- **证据**：真库缺口已关闭——SHOW GRANTS / UPDATE 1142 于 2026-11-27 真栈实证（见 S6）；「注入语料是有限集合，不能证明『所有攻击』」保留为**边界陈述**（data.yaml#unknown 同口径）。
- **反悔点**：语料边界靠持续补充变体、跑 `security --corpus` 判定表对账；真库权限若漂移（SHOW GRANTS 出现 SELECT 之外），S6 的反悔点先触发。
