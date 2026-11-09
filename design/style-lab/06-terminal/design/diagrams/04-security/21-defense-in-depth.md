# 21 · 五层纵深防御

**一句话**：安全由五层各自生效的关卡组成：契约白名单、静态 guard、策略判定、只读执行器、错误通道与审计。

**这张图回答**：一条 SQL 从模型出来到数据库要过几关？每关挡住什么？为什么说「策略被绕过也还有数据库权限兜底」？失败最终怎么到 UI？

**图例**：蓝色=契约层；紫色=查询时校验；红色=安全/失败层；青色=数据库；绿色=成功结果；虚线=失败路径。

**关键元素**：
- 第 1 层 · 契约白名单：`schema.contract.yaml` 派生表/列集合，策略不从提示词读白名单。
- 第 2 层 · 静态 guard：单语句、只读、表列存在、无常量投影、排名意图的 ORDER BY / LIMIT。
- 第 3 层 · 策略判定：AST 复查 + 集合运算/危险函数 + 词法兜底 + 表列白名单 + 自动 LIMIT。
- 第 4 层 · 只读执行器：`dw_reader` 只有 SELECT、`max_execution_time`、客户端超时、禁多语句。
- 第 5 层 · 错误通道与审计：`ChannelError` 统一形状，16 码 / 3 class，SSE `type=error`。

**攻击者能做什么、被哪一层挡住、证据在哪**：

| 攻击者动作 | 挡住它的层 | 证据 |
|---|---|---|
| 让模型引用契约外的表/列 | 第 1、2、3 层都会拒绝 | `policy.py` L436–L503；`guard.py` L225–L272 |
| 生成 `UPDATE` / `DELETE` / DDL | 第 2 层只读判定 + 第 3 层写节点 | `guard.py` L205–L223；`policy.py` L390–L411 |
| 多语句、UNION、可执行注释 | 第 3 层 | `policy.py` L324–L388 |
| 用 `SLEEP` / `BENCHMARK` 拖垮服务 | 第 3 层禁函数 + 第 4 层 5 秒语句超时 | `sql.policy.yaml` L62–L68、L76–L82；`executor.py` L218–L223 |
| 绕过策略直接连库写数据 | 第 4 层：`dw_reader` 只有 SELECT | `account.py` L31–L47、L142–L190；`contracts/sql.policy.yaml` L84–L93 |
| 失败被吞掉、界面全绿 | 第 5 层：所有失败必须变成 `ChannelError` | `backend/app/agent/errors.py` L274–L350 |

**证据**：
- `backend/app/agent/validate.py` L1–L70：guard 与 policy 两道关的调用顺序。
- `backend/app/generate/guard.py` L151–L315：静态校验五项。
- `backend/app/security/policy.py` L298–L528：策略十二步。
- `backend/app/security/executor.py` L1–L20、L161–L287：四道闸与执行主流程。
- `backend/app/agent/errors.py` L43–L69、L274–L350：16 码与唯一失败形状。
- `contracts/errors.yaml` L50–L148：码表本身。

**边界**：五层都依赖同一个契约事实源，契约写错会同时削弱多层。真实数据库权限验证 `--verify-ro-account` 需要 MySQL，本机未跑（⚪），只读结论来自 `account.py` 的静态检查与测试代码。
