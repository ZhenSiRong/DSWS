# 22 · SQL 策略判定流程（六关 + 收尾）

**一句话**：候选 SQL 必须依次回答六个问题——单语句、只读、表白名单、列白名单、无常量投影、排名有 ORDER BY/LIMIT——全过才补 LIMIT 并执行重新序列化后的 SQL。

**这张图回答**：每一关拒绝什么？拒绝后会不会连库？为什么执行的不是模型返回的原文？guard 和 policy 的先后顺序是什么？

**图例**：蓝色=校验关卡；绿色=放行与执行；红色=拒绝；灰色=读图说明。

**关键元素**：
- ① 单语句：S4 guard 与 S5 policy 都查；多语句对应 `SQL_MULTIPLE_STATEMENTS`。
- ② 只读：根节点必须是 `Select`；任何 DML/DDL/`INTO` 对应 `SQL_NOT_READ_ONLY`；集合运算与危险函数对应 `SQL_FORBIDDEN_CONSTRUCT`。
- ③ 表白名单：S5 用契约派生的 `SqlWhitelist`，库名只允许 `dw`；违规原因码 `SQL_TABLE_NOT_ALLOWED`。
- ④ 列白名单：先解析别名，再比对；违规原因码 `SQL_COLUMN_NOT_ALLOWED`。
- ⑤ 常量投影：S4 guard 检查 SELECT 列表的字面量或裸 NULL；违规码 `SQL_CONSTANT_PROJECTION`。
- ⑥ ORDER BY / LIMIT：问题有排名意图时必须有 ORDER BY；显式「前 N / 最高 / 最低」还必须有 LIMIT；违规码 `SQL_MISSING_ORDER_BY` / `SQL_MISSING_LIMIT`。
- 收尾：S5 补 `LIMIT 1000`（超过则截断到 1000），剥掉注释并重新序列化；执行器跑的是 `decision.sql`。

**实际调用顺序**：`validate_sql` 先跑完整 guard（语义），再跑 policy（安全）；policy 会重新检查单语句与只读，并做白名单与 LIMIT。图中按「六个必答问题」排序，两关各自独立拒绝，顺序不影响最终结论。策略拒绝对外统一为 `SQL_REJECTED`，细因放 `reason_code`；guard 的违规码直接作为通道码。

**证据**：
- `backend/app/agent/validate.py` L31–L70：guard → policy 的调用与错误映射。
- `backend/app/generate/guard.py` L151–L315：单语句、只读、表列、常量、排名五段。
- `backend/app/security/policy.py` L298–L528：`enforce` 的十二步。
- `contracts/sql.policy.yaml` L19–L82：单语句、允许根、禁集合运算、禁可执行注释、禁词、LIMIT、超时。
- `contracts/sql.policy.yaml` L94–L125：`SQL_REJECTED` 通道码与 8 个 `reason_codes`。
- `backend/app/security/executor.py` L226–L241：策略不通过时直接返回，不连库。
- `backend/app/security/policy.py` L508–L528：LIMIT 与重新序列化。

**边界**：常量投影与 ORDER BY/LIMIT 属于 S4 guard 的**语义**断言，不是 S5 策略；图把它们放在同一条流程里，是因为用户看到的是「校验SQL」一个步骤。列白名单的「无限定符」分支会检查该列是否存在于任一白名单表，因此同名但不同表的歧义列不会被误放行。
