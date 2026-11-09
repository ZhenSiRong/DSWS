# 20 · 信任边界与攻击面

**一句话**：浏览器与 LLM 输出都不可信；前端不持有凭据；FastAPI 是可信计算基；三个存储与 `dw` 都只被只读访问；旧系统只作为夹具，不参与运行。

**这张图回答**：一次问数跨过哪些信任边界？谁持有数据库凭据？LLM 能拿到什么、拿不到什么？旧系统会不会被新系统写入？

**图例**：红色=不可信输入；紫色=查询时服务；青色=数据存储；灰色=前端 / 外部 LLM / 旧系统边界；虚线=隔离关系。

**关键元素**：
- `Browser`：用户问题、注入文本，全部不可信。
- `Frontend`（nginx :8080）：静态资源与同源代理，不含数据库凭据。
- `FastAPI` :8100：`/api/query` 与 `AgentRunner`，负责召回、生成、校验、执行。
- `LLM`：只接收表/列/指标摘要；**没有 DSN、没有密码**；返回的 SQL 是候选，必须重新过 guard 与 policy。
- `Meta MySQL` / `ES` / `Qdrant`：查询时读元知识与索引。
- `MySQL dw`：执行器用 `dw_reader`，只有 SELECT。
- 旧 `meta` / `value_index` / 旧 collection：只读夹具，不作为运行依赖。

**攻击者能做什么、被哪一层挡住、证据在哪**：

| 攻击者动作 | 被哪一层挡住 | 证据 |
|---|---|---|
| 在问题里塞 `DROP TABLE` / `UPDATE` | S4 静态 guard 判只读 + S5 策略写节点 + `dw_reader` 无写权限 | `backend/app/generate/guard.py` L205–L223；`backend/app/security/policy.py` L390–L411；`contracts/sql.policy.yaml` L44–L58；`backend/app/security/account.py` L31–L47 |
| `SELECT 1; DROP TABLE x` 多语句 | 策略单语句判定 + 连接标志去掉 `CLIENT_MULTI_STATEMENTS` | `policy.py` L353–L371；`executor.py` L201–L214 |
| `UNION` 把别的表数据并进结果外带 | 策略禁止集合运算 | `policy.py` L375–L388；`sql.policy.yaml` L27–L31 |
| `SELECT ... INTO OUTFILE` / `LOAD_FILE` / `SLEEP` | AST 写节点 + 词法禁词 + 危险函数表 | `policy.py` L274–L295、L413–L424；`sql.policy.yaml` L44–L68 |
| 用 `/*! ... */` 可执行注释绕过解析器 | 解析前先拒绝可执行注释 | `policy.py` L324–L332；`sql.policy.yaml` L33–L35 |
| 从 LLM 或提示词里偷数据库密码 | LLM 上下文不含凭据；密码只在执行器环境变量 | `executor.py` L32、L193–L214；`backend/app/recall/catalog.py` 只暴露表/列/指标字段 |
| 诱导模型引用不存在的表/列（`city`、`price`） | 契约白名单 + guard 表列存在检查 | `policy.py` L436–L503；`guard.py` L225–L272；`contracts/schema.contract.yaml` L29–L31、L126 |
| 让新系统写旧系统数据 | rebuild 目标全部 `*_rebuild`；旧库不在建库/删库路径里 | `backend/app/build/config.py` L53–L68；`meta_store.py` L202–L210 |

**证据**：
- `backend/app/security/executor.py` L1–L20：四道闸的设计说明。
- `backend/app/security/policy.py` L298–L528：`enforce` 全流程。
- `contracts/sql.policy.yaml` L84–L93：执行账号 `dw_reader` 只应有 SELECT。
- `fixtures/dw.sql` L9：旧 `didilili` 的 `GRANT ALL PRIVILEGES ON dw.*`，是新系统明确不复用的负向证据。
- `design/inventory/facts.md` L103–L108：安全边界摘要。

**边界**：这张图是信任分区，不是网络拓扑；端口与容器网络见部署图 25–28。真实 LLM 端点未接（⚪），所以「LLM 只拿到 schema 摘要」由代码构造的上下文推导，未做线上抓包验证。
