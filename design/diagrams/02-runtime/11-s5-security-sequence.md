# 11 · S5 安全校验与执行

**一句话**：一条 SQL 先过 `policy.enforce()` 的策略判定，过了才连只读账号执行；策略拒绝、超时、执行错误是三个**互不重叠**的出口，每个都有 `contracts/errors.yaml` 里的码。

**这张图回答**：策略在哪两个地方各查一次？被拒绝时会不会连库？超时是怎么产生的？

**图例**：红色 = 安全与失败；青色 = MySQL。

## 参与者（真实进程 / 类）

| 图上名字 | 真实实体 | 文件 |
|---|---|---|
| `AgentRunner` | `_execute()` → `executor.execute()` | `backend/app/agent/orchestrator.py` L444 |
| `Policy` | `enforce(sql, whitelist, config)` | `backend/app/security/policy.py` L298 |
| `ReadOnlyExecutor` | `execute()` / `_run()` | `backend/app/security/executor.py` L226 / L243 |
| `MySQL` | `dw_reader` 只读账号 | `backend/app/security/executor.py` L187 |

## 三个出口

| 出口 | 触发 | 错误码 | 是否连库 |
|---|---|---|---|
| **策略拒绝** | 多语句 / 写操作 / 非白名单表 / 缺 `ORDER BY`·`LIMIT` / 可执行注释 | `SQL_REJECTED` | **否**（`execute()` L229–L241 直接返回） |
| **超时** | MySQL `3024` / `1205` / `1317`，或客户端 `2006` / `2013` | `TIMEOUT` | 是 |
| **执行错误** | 其它数据库异常 | `SQL_EXECUTION_ERROR` | 是 |

错误码映射在 `_map_error()`（`executor.py` L136–L159）。

## 两次策略检查（纵深防御）

1. **校验步骤**：`validate_sql(gates=("guard","policy"))` 会先跑 `enforce()`，让「这条 SQL 不该被执行」在执行**之前**就变成一条错误事件（`backend/app/agent/validate.py` L56–L70）。
2. **执行器内部**：`execute()` 再查一次（`executor.py` L228）。别的调用方（`secure_execute`、测试、脚本）绕不过这一层。

## 连接层的三道保险

- 只读账号：`user = config.account_user`（`dw_reader`），密码只从 `REBUILD_DW_RO_PASSWORD` 读，缺了直接 `ExecutorError`，**不降级**（`executor.py` L32、L187–L196）。
- 禁用多语句：`CLIENT.CAPABILITIES & ~CLIENT.MULTI_STATEMENTS`（L204）。
- 服务端超时：`SET SESSION max_execution_time = ...`，设置失败会抛（`_prepare_session()` L218–L223）。

## 证据

| 结论 | 状态 | 出处 |
|---|---|---|
| 策略不通过时**不连库** | ✅ | `executor.py` L226–L241 |
| 两次 `enforce()` | ✅ | `validate.py` L56–L70 + `executor.py` L228 |
| `max_execution_time` 会话级设置 | ✅ | `executor.py` L218–L223 |
| 错误码 3024/1205/1317/2006/2013 映射 | ✅ | `executor.py` L65–L71、L136–L159 |
| 真实 MySQL 超时行为 | ⚪ | 需要三存储起来；本次未连库 |
| `contracts/sql.policy.yaml` 的具体规则集 | 🟡 | 本图只画判定位置，不逐条列举 |

## 边界

- 执行阶段的失败**不再校正**：能走到这里说明 SQL 已过 guard + policy，数据库层的错误不是「最小必要修正」能可靠修好的（`orchestrator.py` L392–L415 注释）。
- `_prepare_session()` 失败会抛 `ExecutorError`，被 `_run()` 重新抛出，最终由编排器兜成 `INTERNAL_ERROR`——**不会**被当成「这条 SQL 失败了」。
- 本图不含结果集转换（`to_result_payload()`），那在 07 与 13。
