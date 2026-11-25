# 附录

附录最容易犯的错，是跳过论证直接查表抄列名。`dim_region` 没有 `city` 列，`dim_product` 没有 `price` 列；记反了，SQL 看起来合理，校验时才会报未知列。

这份附录只做三件事：索引、速查、对账。数字都指回正文或 `design/inventory/facts.md`，✅ / 🟡 / ⚪ 保留原状态。

附录把散落在各章的可查项集中成八类速查表与索引：图、步骤、错误码、数据模型、命令、术语、文件、证据。正文里不必背，动手时回来查。

所有条目都以仓库当前基线为准：`eea5e75`（2026-10-29）。计数与 `design/inventory/facts.md` 一致；路径是相对仓库根目录的路径。

---

## A. 32 张图索引

图分六个角度：架构（01–06）、运行时（07–13）、数据（14–19）、安全（20–24）、部署（25–28）、测试（29–32）。源文件统一放在 `design/diagrams/<角度>/` 下，扩展名 `.mmd`（Mermaid）或 `.dot`（Graphviz）；同名 `.md` 是说明。本索引只列路径，不嵌图；源文件列省略公共前缀 `design/diagrams/`。

表 A-1 · 图 01–16

| 编号 | 标题 | 角度 | 源文件 | 一句话 |
|---|---|---|---|---|
| 01 | C4-L1 系统上下文 | 架构 | `01-architecture/01-c4-context.mmd` | 用户、浏览器、DSWS、三存储、可选 LLM 与旧系统的边界 |
| 02 | C4-L2 容器图 | 架构 | `01-architecture/02-c4-container.mmd` | 前端、FastAPI、AgentRunner、构建 CLI 与三存储的容器关系 |
| 03 | 后端模块依赖 | 架构 | `01-architecture/03-backend-modules.dot` | `backend/app/` 的 import 与调用方向 |
| 04 | 前端组件树 | 架构 | `01-architecture/04-frontend-tree.mmd` | `App.tsx` 到 Composer / StepRail / ResultTable / ErrorCard |
| 05 | 阶段演进 S0–S8 | 架构 | `01-architecture/05-stage-evolution.mmd` | 每个阶段新增的能力、不确定性与可停点 |
| 06 | 构建时 vs 查询时 | 架构 | `01-architecture/06-build-vs-query.mmd` | S2 退出后，查询时只读三存储 |
| 07 | 端到端请求生命周期 | 运行时 | `02-runtime/07-end-to-end-request.mmd` | 浏览器到 MySQL 再以 SSE 返回的完整链路 |
| 08 | S2 构建流水线时序 | 运行时 | `02-runtime/08-s2-build-sequence.mmd` | plan → Meta → ES → Qdrant → manifest → exit |
| 09 | S3 召回流水线时序 | 运行时 | `02-runtime/09-s3-recall-sequence.mmd` | 关键词 → 值召回 → 列/指标召回 → 合并 → 过滤 |
| 10 | S4 生成 SQL 流水线 | 运行时 | `02-runtime/10-s4-generate-sequence.mmd` | 上下文八阶段 → 生成 → 输出校验 → 静态 guard |
| 11 | S5 安全校验与执行 | 运行时 | `02-runtime/11-s5-security-sequence.mmd` | 策略判定 → 只读执行器 → 结果或错误 |
| 12 | S6 校正闭环状态机 | 运行时 | `02-runtime/12-s6-correction-state.mmd` | 校验 → 可重试则校正一次 → 再校验 → 执行 |
| 13 | S7 SSE 事件序列 | 运行时 | `02-runtime/13-s7-sse-sequence.mmd` | progress / result / error 到三个 UI 组件 |
| 14 | 数仓 ER 图 | 数据 | `03-data/14-er-diagram.mmd` | 5 表、主键、逻辑外键与粒度 |
| 15 | 契约模型 | 数据 | `03-data/15-contract-model.mmd` | Table / Column / Metric / ValueDomain / ColumnMetric |
| 16 | 三存储知识布局 | 数据 | `03-data/16-three-store-layout.mmd` | 一份契约怎么翻译成 Meta 行、ES 文档、Qdrant 点 |

表 A-2 · 图 17–32

| 编号 | 标题 | 角度 | 源文件 | 一句话 |
|---|---|---|---|---|
| 17 | S2 数据 lineage | 数据 | `03-data/17-s2-lineage.mmd` | 契约 + 数据 → BuildPlan → 三存储 + manifest |
| 18 | Meta 表结构 | 数据 | `03-data/18-meta-schema.mmd` | `table_info` / `column_info` / `metric_info` / `column_metric` / `build_manifest` |
| 19 | 值域分类决策树 | 数据 | `03-data/19-value-domain-decision.mmd` | enum 写 ES，range 不写；`sync_values` 的边界 |
| 20 | 信任边界与攻击面 | 安全 | `04-security/20-trust-boundary.mmd` | 浏览器、前端、FastAPI、LLM、三存储、旧系统的信任线 |
| 21 | 五层防御纵深 | 安全 | `04-security/21-defense-in-depth.mmd` | 白名单 → guard → policy → 只读执行器 → 错误通道 |
| 22 | SQL 策略判定流程 | 安全 | `04-security/22-sql-policy-flow.mmd` | 单语句 → 只读 → 表/列白名单 → 常量 → 排序/限量 |
| 23 | 只读账号权限模型 | 安全 | `04-security/23-readonly-grants.mmd` | `dw_reader` 只有 SELECT，应用账号与它分离 |
| 24 | 错误码分类与 UI 映射 | 安全 | `04-security/24-error-taxonomy.mmd` | 16 个码按 failure / empty / cancelled 分类 |
| 25 | Docker Compose 拓扑 | 部署 | `05-deployment/25-compose-topology.mmd` | 六个服务、三个卷、一个默认网络 |
| 26 | 端口与网络暴露面 | 部署 | `05-deployment/26-port-exposure.mmd` | 哪些端口只绑 `127.0.0.1`，哪个对外 |
| 27 | 启动顺序与健康检查 | 部署 | `05-deployment/27-startup-order.mmd` | 三存储 → init → backend → frontend |
| 28 | 旧系统 / rebuild 隔离 | 部署 | `05-deployment/28-legacy-isolation.mmd` | `*_rebuild` 命名、5273 / 5173、8100 |
| 29 | 测试金字塔与阶段门禁 | 测试 | `06-testing/29-test-pyramid.mmd` | 单元 / 契约 / 集成 / 场景 / 端到端的分层 |
| 30 | S0–S7 阶段门禁 | 测试 | `06-testing/30-stage-gates.dot` | 每阶段的硬命令与「通过」判据 |
| 31 | 失败注入矩阵 | 测试 | `06-testing/31-failure-injection.mmd` | 6 类失败 → 错误码 → UI 状态 |
| 32 | 证据台账 | 测试 | `06-testing/32-evidence-ledger.mmd` | ✅ / 🟡 / ⚪ 三类证据的来源与去向 |

使用索引时注意两件事：编号在全书唯一，不按目录重新计数；某张图若被合并，合并说明写在对应 `.md` 里，索引不删除编号。

读图有一个顺序建议：先看 01 / 02 建立「谁是谁」的地图，再看 07 建立「一次请求经过谁」的时间感，然后按你当前要改的部分跳到对应角度。改数据模型看 14–19，改安全策略看 20–24，部署排障看 25–28，写测试看 29–32。不要从第一张图顺序读到第三十二张——图集是索引，不是小说。

按角度清点，六个角度合计 32 张，既不重复编号，也不把「合并图」算成两张：

表 A-3 · 按角度清点

| 角度 | 编号范围 | 张数 | 主要回答 |
|---|---|---:|---|
| 架构 | 01–06 | 6 | 系统边界、容器、模块、组件、阶段、构建/查询分界 |
| 运行时 | 07–13 | 7 | 一次请求与各阶段流水线在时间上经过谁 |
| 数据 | 14–19 | 6 | 表、契约、三存储布局、lineage、Meta、值域 |
| 安全 | 20–24 | 5 | 信任边界、纵深、策略、只读账号、错误分类 |
| 部署 | 25–28 | 4 | Compose 拓扑、端口暴露、启动顺序、旧系统隔离 |
| 测试 | 29–32 | 4 | 金字塔、阶段门禁、失败注入、证据台账 |

图号和章节不是一一对应：第 1–2 部分按阶段讲能力，会同时引用架构图与运行时图；第 3 部分讲数据与安全；第 5 部分集中使用 25–31。找不到某张图时，先看它的 `.md` 说明里的「这张图回答」，再回到正文对应小节，不要只凭文件名猜内容。

每张图都配一份 `.md`，里面有一句话结论、这张图回答什么问题、图例、关键元素、证据文件与已知边界。只看 SVG 容易把「推断」当成「事实」；`.md` 里的证据表才是判断依据。

---

## B. 12 个步骤

步骤目录的唯一事实源是 `contracts/steps.yaml`，前端启动时从 `GET /api/steps` 拉取，不硬编码。12 个步骤里有且只有一个条件步骤：`correct_sql`。

表 B-1 · 步骤目录

| # | 阶段 | id | label | 条件执行 | 证据 / 说明 |
|---:|---:|---|---|:---:|---|
| 1 | 1 | `extract_keywords` | 抽取关键词 | 否 | `contracts/steps.yaml` |
| 2 | 2 | `recall_column` | 召回字段信息 | 否 | 同上 |
| 3 | 2 | `recall_value` | 召回字段取值 | 否 | 同上 |
| 4 | 2 | `recall_metric` | 召回指标信息 | 否 | 同上 |
| 5 | 3 | `merge_retrieved_info` | 合并召回信息 | 否 | 同上 |
| 6 | 4 | `filter_table` | 过滤表信息 | 否 | 同上 |
| 7 | 5 | `filter_metric` | 过滤指标信息 | 否 | 同上 |
| 8 | 6 | `add_extra_context` | 添加额外上下文 | 否 | 同上 |
| 9 | 7 | `generate_sql` | 生成SQL | 否 | 同上 |
| 10 | 8 | `validate_sql` | 校验SQL | 否 | 同上 |
| 11 | 9 | `correct_sql` | 校正SQL | 是 | `conditional: true`；未触发时后端显式发 `skipped` |
| 12 | 10 | `run_sql` | 执行SQL | 否 | 同上 |

`contracts/steps.yaml` 里同时有 `stages`（10 段）与每个节点的 `stage` 字段；`backend/tests/test_steps_stages.py` 守着「12 个节点不重不漏地落进 10 段」。这是读图分组，不是新事件——SSE 仍然每个节点一条 `progress`。

`correct_sql` 的「条件执行」不是「可能永远灰着」。旧前端硬编码 12 个节点，导致校正节点永远 pending；新契约要求后端在未触发时显式发 `status: "skipped"`，前端据此显示「未触发」，而不是一个永远转圈的灰块。

每个步骤在 SSE 里由一条 `progress` 事件推进，状态只有四种合法值；`duration_ms` 的取值跟着状态走：

表 B-2 · 步骤状态与耗时

| `status` | 含义 | `duration_ms` | 前端表现 |
|---|---|---|---|
| `running` | 正在执行 | 必须为 `null` | 转圈或高亮当前节点 |
| `success` | 成功完成 | 必须是数字 | 打勾，显示耗时 |
| `error` | 该步失败 | 必须是数字 | 红叉，错误卡指向该步 |
| `skipped` | 条件未触发 | 必须为 `null` | 显示「未触发」，不转圈、不算失败 |

这张小表解释了一个常见误解：`skipped` 不是 `success` 的别名，也不是失败。它表示「这个条件步骤这次不需要执行」，所以既不能打勾，也不能标红。前端如果把它当成功，用户会以为校正跑过了；当失败，用户会以为系统坏了。两种情况都是协议误读。

按职责把这 12 步分成四段，查问题时更容易定位：

- 第 1–4 步是「取料」：抽关键词，再从三个存储分别取列、取值、指标。取料阶段失败通常不是代码逻辑，而是 S2 没构建好或索引名不对。
- 第 5–8 步是「整理」：合并四路召回，过滤掉与问题无关的表与指标，再补上时间范围、粒度之类的额外上下文。这一段决定模型看到的上下文是不是干净。
- 第 9–11 步是「生成与校验」：生成 SQL、静态校验、必要时校正一次。`validate_sql` 失败会带错误码，`correct_sql` 只在 `retryable` 为真时出现。
- 第 12 步是「执行」：只读执行器跑单条 SELECT，结果以 `result` 事件返回，或按错误码以 `error` 收尾。

注意 S4 只到第 11 步，不执行 SQL；S5 才把第 12 步接上。所以「S4 通过」不等于「SQL 能跑」，它只证明生成了合法、只读、在白名单内的 SQL。

---

## C. 16 个错误码

错误码表来自 `contracts/errors.yaml`。三个 `class` 决定 UI：`failure` 红框、`empty` 空态不标红、`cancelled` 取消态。`retryable` 决定是否进入校正闭环；`SQL_REJECTED` 永远不可重试。

表 C-1 · 错误码全表（16/16）

| code | label | class | retryable | 用户看到什么 |
|---|---|---|:---:|---|
| `SQL_REJECTED` | SQL 被安全策略拒绝 | failure | 否 | 红框，提示未通过安全策略，已拒绝执行 |
| `SQL_SYNTAX` | SQL 语法错误 | failure | 是 | 红框，提示 SQL 无法解析 |
| `SQL_UNKNOWN_COLUMN` | 引用了不存在的列 | failure | 是 | 红框，提示列不在 schema 里 |
| `EMPTY_RESULT` | 查询成功但没有数据 | empty | 否 | 空态卡，**不标红** |
| `LLM_REFUSAL` | 模型明确拒答 | failure | 否 | 红框，提示现有数据无法回答 |
| `TIMEOUT` | 执行超时 | failure | 否 | 红框，提示已中止 |
| `CANCELLED` | 用户取消 | cancelled | 否 | 取消态，不算完成也不算失败 |
| `SQL_UNKNOWN_TABLE` | 引用了不存在的表 | failure | 是 | 红框，提示表不在白名单 |
| `SQL_NOT_READ_ONLY` | 不是只读查询 | failure | 否 | 红框，提示只允许 SELECT |
| `SQL_MULTIPLE_STATEMENTS` | 不是单条语句 | failure | 否 | 红框，提示只能有一条语句 |
| `SQL_CONSTANT_PROJECTION` | 投影了常量 | failure | 是 | 红框，提示 SELECT 列表不能有字面量 |
| `SQL_MISSING_ORDER_BY` | 缺 ORDER BY | failure | 是 | 红框，提示排名意图必须排序 |
| `SQL_MISSING_LIMIT` | 缺 LIMIT | failure | 是 | 红框，提示限定名次必须限量 |
| `SQL_EMPTY` | SQL 为空 | failure | 否 | 红框，提示没有可执行 SQL |
| `SQL_EXECUTION_ERROR` | 数据库执行出错 | failure | 否 | 红框，提示数据库执行失败 |
| `INTERNAL_ERROR` | 系统内部错误 | failure | 否 | 红框，兜底文案，不泄露内部细节 |

分类统计：`failure` 14 个，`empty` 1 个（`EMPTY_RESULT`），`cancelled` 1 个（`CANCELLED`）。可重试的是 `SQL_SYNTAX`、`SQL_UNKNOWN_COLUMN`、`SQL_UNKNOWN_TABLE`、`SQL_CONSTANT_PROJECTION`、`SQL_MISSING_ORDER_BY`、`SQL_MISSING_LIMIT` 这 6 个，其余 10 个都不可重试。校正策略是 `max_attempts: 1`，校正后重新过 `guard` 与 `policy`。

读这张表要和代码里的映射规则一起读。生成器或校验层可能产生表里没有的内部码（例如 `OUT_OF_RANGE`、`UNSUPPORTED_INTENT`、`INVALID_OUTPUT`），进入通道时统一映射成 `LLM_REFUSAL`，原码保留在 `detail.reason_code`。这样既不丢名字，也不需要在两张表之间手工同步。

`class` 的三个取值是 UI 分支，不是文案分类：前端拿到 `error` 事件后，先看 `class` 再决定渲染哪个组件。`failure` 走红框与失败步骤红叉；`empty` 走空态卡，绝不能标红；`cancelled` 走取消态，步骤条停止推进。把 `empty` 当 `failure` 是审计 FP-8 记录的旧缺陷；把 `cancelled` 当 `done` 是另一条旧缺陷。

`retryable` 也不是「重试一下也许能好」。它只表示这条失败是否允许进入 `correct_sql`；`SQL_REJECTED` 永远为假，因为拿被策略拒绝的 SQL 去问模型「改一下」，等于给注入开重试的口子。`TIMEOUT` 与 `SQL_EXECUTION_ERROR` 同样不可重试：重试只会再超时或再报错一次。

---

## D. 5 表 24 列 6 指标

数据契约在 `contracts/schema.contract.yaml`。5 张表、24 列、6 个指标、9 条列—指标关系；数据覆盖 2025 Q1，115 行事实。

表 D-1 · 五张表

| 表名 | 粒度 | 列数 | 关键列 |
|---|---|---:|---|
| `dim_region` | 一行一个 `region_id`（省级） | 4 | `region_id`、`province`、`region_name`、`country` |
| `dim_customer` | 一行一个 `customer_id` | 4 | `customer_id`、`customer_name`、`gender`、`member_level` |
| `dim_product` | 一行一个 `product_id` | 4 | `product_id`、`product_name`、`category`、`brand` |
| `dim_date` | 一行一个 `date_id`（一天） | 5 | `date_id`、`year`、`quarter`、`month`、`day` |
| `fact_order` | 一行一个 `order_id`（一单） | 7 | `order_id`、四个外键、`order_quantity`、`order_amount` |

合计 4 + 4 + 4 + 5 + 7 = 24 列。两个容易记错的点：`dim_region` 没有 `city` 列，粒度只到省；`dim_product` 没有 `price` 列，单价只能由金额与件数推导。

表 D-2 · 六个指标

| 指标 | 公式 | 粒度 | 期望值 |
|---|---|---|---:|
| `GMV` | `SUM(fact_order.order_amount)` | 订单 | 279159.5 |
| `AOV` | `SUM(order_amount) / COUNT(DISTINCT order_id)` | 订单 | 2427.47 |
| `订单量` | `COUNT(DISTINCT fact_order.order_id)` | 订单 | 115 |
| `销量` | `SUM(fact_order.order_quantity)` | 订单 | 622 |
| `平均件单价` | `SUM(order_amount) / SUM(order_quantity)` | 件 | 448.81 |
| `平均每单件数` | `SUM(order_quantity) / COUNT(DISTINCT order_id)` | 订单 | 5.41 |

`AOV` 的 `rejected_values` 明确排除了 `448.81`（平均件单价）与 `5.41`（平均每单件数）。这三个数长得很像，旧系统把它们混成一个「客单价」，是 S1 负向夹具要抓的核心错误之一。

逻辑外键四条：`fact_order.customer_id → dim_customer.customer_id`、`product_id → dim_product.product_id`、`date_id → dim_date.date_id`、`region_id → dim_region.region_id`。物理 DDL 不一定有外键约束，契约表达的是查询时的连接语义。

9 条列—指标关系记录在 `column_metric` 表里，回答的是「这个问题该看哪一列」。例如 `销售额` 指向 `fact_order.order_amount`，`订单数` 指向 `fact_order.order_id`，`件单价` 同时指向前两者。列级别名与指标级别名共用一套空间，所以「销售额」只放在指标 `GMV` 上，不放在 `order_amount` 列上——否则同一个词会召回两条互相冲突的元知识。

指标与粒度的关系还要单独记一笔：`GMV`、`订单量`、`AOV`、`平均每单件数` 的粒度是「订单」，`销量` 与 `平均件单价` 的粒度是「件」。粒度写错，SQL 的 `GROUP BY` 就会错。`fact_order` 一行一单，`order_quantity` 是单内件数，不是订单数；这是全章最容易被误读的一列。

---

## E. 命令速查

表 E-1 · 阶段门禁

| 命令 | 作用 | 需要三存储 |
|---|---|:---:|
| `make install` | 安装后端与前端依赖 | 否 |
| `make stage0` | 契约 + 前端协议 + 构建 | 否 |
| `make stage0-ui` | 真实浏览器冒烟（临时 8101/5274） | 否 |
| `make stage1` | 契约 ↔ DDL/数据；旧系统必须红 | 否 |
| `make stage2` | dry-run → `--fresh` → `--verify` → 幂等 | 是 |
| `make stage3` | 三存储对账 + 20 题召回 + CLI YAML | 是 |
| `make stage4` | 10 题基线 + 生成层测试 | 否 |
| `make stage5` | 策略 + 36 条注入语料 + 零误杀 | 否 |
| `make stage5-live` | 只读账号开通 / 验证 + 两屏对比 | 仅 MySQL |
| `make stage6` | 16 错误码 + 6 类失败 + 校正 + 取消 | 否 |
| `make stage6-ui` | 六类失败各一个浏览器用例 | 否（要浏览器） |
| `make stage7` | 生成物新鲜度 + SSE 夹具 + 前端契约 | 否 |
| `make stage7-ui` | 13 条 F 缺陷各一个浏览器用例 | 否（要浏览器） |
| `make baseline` | 单独打印 10 题基线表 | 否 |

表 E-2 · Docker 与诊断

| 命令 | 作用 |
|---|---|
| `make docker-env` | 生成 `.env`（已存在则跳过） |
| `make docker-up` | 构建并启动五服务 + 一次性 init |
| `make docker-down` | 停止并删除容器与网络，保留卷 |
| `make docker-logs` | 跟踪全部服务日志 |
| `make docker-smoke` | 八步完整验收 |
| `make docker-reset` | 输入 `yes` 后 `down -v`，删三个卷 |
| `docker compose ps -a` | 看全部服务状态，含已退出的 init |
| `docker compose logs -f backend` | 只看后端日志 |
| `docker compose port frontend 80` | 查前端实际发布的宿主机端口 |
| `docker compose exec -T frontend nginx -T` | 取 nginx 完整生效配置 |
| `docker compose run --rm --no-deps init` | 重跑一次性初始化 |
| `source scripts/export-docker-env.sh` | 把 `.env` 导出为宿主 CLI 的 `REBUILD_*` |
| `docker compose config --quiet` | 校验 Compose 文件（不打印密码） |

两条纪律：`docker compose config` 不加 `--quiet` 会把 `.env` 里的真实密码打印出来；`docker compose down -v` 不要手动执行，走 `make docker-reset`。

典型组合有三条。第一次上机：`make install` → `make stage0` → `make stage1`，先确认不依赖存储的部分是绿的。准备构建：`make docker-env` → `docker compose up -d mysql elasticsearch qdrant` → `source scripts/export-docker-env.sh` → `make stage2` → `make stage3`。全量交付：`make docker-up` → `curl -fsS http://127.0.0.1:8080/api/health` → `make docker-smoke`。

排障时优先用「只读」命令：`docker compose ps -a`、`logs`、`port`、`exec -T ... nginx -T`。不要一上来就 `down` / `rm` / `reset`；先确定问题在哪一层，再决定要不要动容器。`docker compose run --rm --no-deps init` 会重跑初始化的全部步骤，属于「有副作用但可重复」的操作，跑之前先确认三存储已经在跑。

---

## F. 术语表

表 F-1 · 术语

| 术语 | 含义 |
|---|---|
| 契约（contract） | 前后端与构建/查询共用的唯一事实源，放在 `contracts/`；改契约不改代码是缺陷 |
| 构建时（build time） | S2 一次性 CLI 运行期间；结束后进程退出，查询时不再运行 |
| 查询时（query time） | 用户发起问数到 SSE 收尾的链路；只读三存储，不写 |
| 召回（recall） | 从 ES / Qdrant / Meta 取回列、取值、指标与表信息 |
| 值域（value domain） | 一列允许的取值集合；enum 写 ES，range 不写 |
| manifest | S2 构建结束时写的对账清单，记录计数与目标，供 `--verify` 使用 |
| SSE | Server-Sent Events，后端以 `data: <json>` 逐条推送 progress / result / error |
| 幂等（idempotent） | 同一输入重复构建不产生新写入；S2 用 `--assert-idempotent` 验证 |
| 只读执行器 | `ReadOnlyExecutor`，只允许单条 SELECT，带 `max_execution_time` |
| 校正闭环 | 可重试错误进入 `correct_sql`，最多一次，校正后重新过 guard 与 policy |
| 阶段门禁 | 每个 S 阶段的硬验收命令，必须能红也能绿 |
| 证据等级 | ✅ 已验证 / 🟡 推断 / ⚪ 未验证，禁止把 🟡 写成 ✅ |
| 一次性任务 | `init` 容器，成功退出 0 后不再运行；`ps` 要加 `-a` 才看得到 |
| 假阳性 | 验收脚本报 PASS，但它验的东西根本没验；例如用 `assert` 写的检查 |
| 两屏对比 | S5 实战里旧执行器接受、新策略拒绝的并排演示 |

表 F-2 · 工程与测试术语

| 术语 | 含义 |
|---|---|
| 契约测试 | 只验契约与代码是否一致、不碰外部依赖的测试，如 `test_s0_contract.py` |
| 黄金集 | 20 道问题与期望召回结果的固定集合，S3 用它防召回回归 |
| 场景应用 | S6 的验收用 FastAPI 工厂，替换模型与数据库，其余全真 |
| 回放夹具 | S7 录下的 SSE 响应，浏览器验收时按场景 id 回放 |
| 事实源 | 同一件事只允许有一个可编辑来源；契约就是计数与形状的事实源 |
| 阶段（S0–S8） | 每阶段消灭一个不确定性，并有独立门禁；S8 尚未实现 |

---

## G. 文件地图

表 G-1 · 什么时候读哪个文件

| 路径 | 作用 | 什么时候读 |
|---|---|---|
| `compose.yaml` | 六服务、卷、端口、健康检查 | 部署 / 排障 |
| `Makefile` | 阶段门禁与 docker 命令的入口 | 跑验收 |
| `contracts/schema.contract.yaml` | 5 表 / 24 列 / 6 指标的事实源 | 改数据模型 / 查口径 |
| `contracts/steps.yaml` | 12 个步骤 | 改流水线 / 查步骤 |
| `contracts/errors.yaml` | 16 个错误码与校正策略 | 改失败通道 |
| `contracts/sse.schema.json` | 3 种 SSE 事件 | 改前端协议 |
| `contracts/sql.policy.yaml` | 只读、单语句、白名单等策略 | 改安全边界 |
| `backend/app/main.py` | FastAPI 入口、五个端点 | 查 API |
| `backend/app/agent/orchestrator.py` | 查询时编排 | 查步骤顺序 |
| `backend/app/build_meta_knowledge.py` | S2 CLI 入口 | 构建 / 对账 |
| `backend/app/security/policy.py` | AST 策略判定 | 排查拒绝原因 |
| `backend/app/security/executor.py` | 只读执行器 | 排查执行错误 |
| `scripts/docker-smoke.sh` | 八步验收 | 部署后验收 |
| `scripts/smoke_checks.py` | smoke 的具体判据 | 改验收 / 查假阳性 |
| `scripts/export-docker-env.sh` | 导出宿主 CLI 凭据 | 跑 S2/S3/S5-live 前 |
| `docs/DOCKER-DEPLOY.md` | 部署手册 | 首次部署 / 轮换密码 |
| `docs/SETUP-FROM-SCRATCH.md` | 从零搭建与故障表 | 新机器 / 查症状 |
| `fixtures/failures/scenarios.yaml` | 6 类失败剧本 | 改失败通道 / 跑 S6 |
| `design/inventory/facts.md` | 共享事实底稿 | 引用任何计数前 |

文件地图的使用方式是「从问题倒推」：想知道一个端口从哪来，查 `compose.yaml`；想知道一个错误码为什么出现，查 `contracts/errors.yaml` 与 `backend/app/agent/errors.py`；想知道一次查询走了哪几步，查 `contracts/steps.yaml` 与 `backend/app/agent/orchestrator.py`。不要从目录树第一行开始读，目录树不告诉你优先级。

`docs/` 与 `design/` 的分工也要分清：`docs/` 是随代码维护的操作文档，`design/` 是这次重建的设计产物与书稿。两者冲突时，以 `contracts/` 与 `compose.yaml` 的当前内容为准，`design/inventory/facts.md` 是仲裁记录。

---

## H. 证据台账

表 H-1 · ✅ 已验证

| 事实 | 证据 |
|---|---|
| 拉取基线 `eea5e75` | `git pull --ff-only` 成功 |
| `--dry-run` 计数 5 / 24 / 6 / 9 / 76 / 98 / 22 | 2026-10-27 本机输出 |
| 旧系统计数未变 | 2026-10-25/26 本机记录 |
| `make stage0`–`stage7` 曾在 Windows / Linux 跑绿 | `docs/SETUP-FROM-SCRATCH.md` §7 |
| Docker smoke 八步通过 | `docs/DOCKER-HANDOFF.md` §6.1（那次环境） |
| 后端 782 passed / 31 skipped | `docs/DOCKER-HANDOFF.md` §5.1（那次环境） |
| 端口 / 服务名 / 卷名 | `compose.yaml` 逐字 |

表 H-2 · 🟡 推断

| 事实 | 推导链 |
|---|---|
| 写入总数 241 | 44 Meta 行 + 76 ES + 98 + 22 Qdrant + 1 manifest，按代码公式 |
| 本工作树的 782 测试 | README 与交接文档声称，本工作树未跑 |
| 阶段测试数会随代码增长 | 文档快照来自不同时间点 |
| `/api/health` 能证明进程活着 | 只证明 FastAPI 起来了，不证明数据面 |

表 H-3 · ⚪ 未验证

| 事实 | 缺什么 |
|---|---|
| Docker 全栈从零启动 | 本机无 Docker socket 权限 |
| `--fresh` 真实写三存储 | 同上；计数来自 dry-run |
| `make stage5-live` 只读账号 | 无运行中的 MySQL |
| 真实 LLM 生成 / 校正 | 无端点、无 Key |
| 浏览器验收 stage0-ui / 6-ui / 7-ui | 本机未装 Chrome/Edge |
| 真实召回接入 `/api/query` | S8 才收口，当前上下文离线裁剪 |

使用这份台账的规则很简单：写任何结论前，先在表 H-1 找到它；找不到就降到 🟡，连推导链都写不清就标 ⚪。⚪ 不是羞耻，把 ⚪ 写成 ✅ 才是。

台账还要定期复查。代码一改，昨天的 ✅ 可能今天就变成 🟡：例如 README 里的测试数会随新增用例变化，Docker 交接文档里的「线上栈在跑」也会随环境消失。复查时不要只改数字，要连带改证据行；没有证据行的数字，一律按 🟡 处理。

这份台账只记录「会写进书里的结论」，不记录过程日志。过程日志留在 `design/inventory/` 的交接文件里；书里的证据行要能让人顺着一条命令或一个文件行号复核。三条状态决定读者该不该相信下一句话。
