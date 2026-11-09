# 23 · 只读账号权限模型（dw_reader 与应用账号分离）

**一句话**：执行器只用 `dw_reader` 连 `dw`，该账号在 `dw` 上只有一条 `GRANT SELECT`；建库与写 Meta 用应用账号；旧系统的 `didilili` 拥有 `ALL PRIVILEGES`，是新系统明确不复用的负向入口。

**这张图回答**：`dw_reader` 是谁、怎么创建、怎么验证？执行器和构建任务用的是不是同一个账号？旧 `GRANT ALL` 为什么危险？应用账号与只读账号怎么分离？

**图例**：橙色=一次性初始化；绿色=验证；红色=安全底线与被拒能力；紫色=应用账号；青色=数据库。

**关键元素**：
- 初始化（root）：`DROP USER IF EXISTS 'dw_reader'@'%'` → `CREATE USER ... IDENTIFIED BY '环境变量'` → `GRANT SELECT ON dw.*` → `FLUSH PRIVILEGES`。
- 密码只来自 `REBUILD_DW_RO_PASSWORD`，仓库不存秘密。
- 验证两步：`SHOW GRANTS` 扫描 `ALL PRIVILEGES / INSERT / UPDATE / DELETE / DROP / CREATE / ALTER / INDEX / REFERENCES / TRIGGER / EXECUTE / FILE / PROCESS / SUPER / SHUTDOWN / GRANT OPTION`；再执行 `UPDATE fact_order ... WHERE 1 = 0`，期望 MySQL 1142 拒绝。
- 运行时：`ReadOnlyExecutor` 以 `dw_reader` 执行 SELECT；S2 构建/Meta 写入用应用账号 `didilili` 写 `meta_rebuild`。
- `dw_reader` 明确没有 INSERT / UPDATE / DELETE / DROP / CREATE / ALTER / GRANT / FILE。

**攻击者能做什么、被哪一层挡住、证据在哪**：

| 攻击者动作 | 被哪一层挡住 | 证据 |
|---|---|---|
| 绕过策略直接执行 `UPDATE` / `DELETE` | 数据库权限：`dw_reader` 只有 SELECT，MySQL 返回 1142 | `backend/app/security/account.py` L31–L47、L142–L190 |
| 建表 / 删表 / 改结构 | 无 DDL 权限 | `contracts/sql.policy.yaml` L84–L93；`account.py` L31–L47 |
| 通过 `FILE` 读写服务器文件 | 无 FILE 权限；策略同时禁 `LOAD_FILE` / `INTO OUTFILE` | `account.py` L31–L47；`sql.policy.yaml` L44–L68 |
| 借旧系统 `didilili` 的 ALL 权限写 `dw` | 新执行路径不复用该账号；只读账号独立创建 | `fixtures/dw.sql` L9；`sql.policy.yaml` L84–L93 |
| 从仓库或镜像里找密码 | 密码只由环境变量提供，不在仓库 | `executor.py` L31–L32、L193–L198；`account.py` L65–L70 |

**证据**：
- `backend/app/security/account.py` L17–L112：`AccountSpec` 与确定性开通语句。
- `backend/app/security/account.py` L142–L190：`verify_account` 静态 + 实写验证。
- `backend/app/scripts/security.py` L240–L300：`--provision-ro-account` / `--verify-ro-account` CLI。
- `backend/app/security/executor.py` L187–L215：只读连接参数与去多语句标志。
- `contracts/sql.policy.yaml` L84–L93：账号、库、唯一授权。
- `fixtures/dw.sql` L9：旧 `GRANT ALL PRIVILEGES ON dw.* TO 'didilili'@'%'`。
- `design/inventory/facts.md` L103–L108：账号分离摘要。

**边界**：`--verify-ro-account` 需要真实 MySQL，本机未执行（⚪）；本图的开通语句与禁止清单来自代码与契约，未做线上 `SHOW GRANTS` 抓取。`didilili` 在 `meta_rebuild` 上仍有建表/写入权限，这是应用账号的职责范围，不是只读执行账号。
