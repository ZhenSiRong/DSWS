# DSWS 软件普查

> 基线：`eea5e75`（2026-10-29）· 工作树 `/home/zhensirong/VM-Share/DSWS-design`
> 口径：本文件只写**能指到文件、命令或契约**的事实；计数以 `facts.md` 为准。
> 标记：✅ 本机已核对；🟡 从代码/文档推导但未实跑；⚪ 环境不具备、未执行。

## 0. 一句话结论

DSWS 是一套**契约驱动**的电商问数实现：一条一次性 S2 构建任务把契约写进
MySQL / ES / Qdrant 三份元知识，查询时 FastAPI 在同一进程里跑
「上下文 8 阶段 → 生成 → 校验 → 可选校正 → 只读执行」，并以 3 种 SSE 事件
收尾；失败被 16 个错误码、3 个 `class` 命名，而不是一律变成红框。

---

## 1. 代码规模

| 口径 | 计数 | 命令 / 出处 | 状态 |
|---|---:|---|---|
| 后端 Python 文件（`backend/app`） | 60 | `find backend/app -name '*.py' \| wc -l` | ✅ |
| 后端测试文件（`test_*.py`） | 45 | `find backend/tests -name 'test_*.py' \| wc -l` | ✅ |
| 后端测试目录全部 `.py` | 47 | 45 个 `test_*.py` + `conftest.py` + `shellkit.py` | ✅ |
| 前端 `src/` 文件 | 17 | 14 个 `.ts/.tsx` + 1 个 `.css` + 2 个 `.json` | ✅ |
| 前端 `src/` 中 `.ts/.tsx` | 14 | `find frontend/src -name '*.ts' -o -name '*.tsx' \| wc -l` | ✅ |
| 前端浏览器/回放测试脚本（`frontend/tests`） | 5 | `chrome.mjs`、`replay-server.mjs`、`s0_smoke.mjs`、`s6_failures.mjs`、`s7_frontend.mjs` | ✅ |
| 前端单测文件 | 2 | `src/lib/result.test.ts`、`src/lib/sse.test.ts` | ✅ |
| 契约文件 | 13 | `find contracts -type f \| wc -l` | ✅ |
| 其中提示词 | 7 | `contracts/prompts/*.prompt` | ✅ |
| 夹具文件 | 19 | `find fixtures -type f \| wc -l`（含 14 条 SSE 夹具） | ✅ |
| 后端测试通过数 | 782 passed / 31 skipped | `README.md` 声称；本机未跑全量 | 🟡 |

**口径提醒**

- 「前端源文件数 17」是 `frontend/src/` 全部文件；其中 3 个是
  `generated/` 机器产物（`sse.ts`、`sse.schema.json`、`contract.json`），
  2 个是测试文件，1 个是样式表。
- `docs/SETUP-FROM-SCRATCH.md` §3 写的是 **665 passed / 31 skipped**，
  与 `README.md` 的 782 不一致。按 `facts.md` 以 README 的 782 为准并标 🟡，
  差异记录见 §12。

---

## 2. 分层清单

| 层 | 阶段 | 路径 | 职责 | 关键入口 | 时相 |
|---|---|---|---|---|---|
| 契约层 | S0/S1 | `contracts/` | 步骤、SSE、Schema、策略、错误码、提示词的唯一事实源 | YAML / JSON 文件 | 构建与查询都读 |
| 构建层 | S2 | `backend/app/build/`、`build_meta_knowledge.py`、`scripts/docker_init.py` | 契约 → 三存储元知识 + manifest，幂等 | `python -m app.build_meta_knowledge` | 构建时（一次性） |
| 召回层 | S3 | `backend/app/recall/`、`scripts/recall.py` | 关键词 → ES/Qdrant/Meta 批量召回 → 过滤 → 上下文 | `python -m app.scripts.recall` | 阶段验收 / 集成测试 |
| 生成层 | S4 | `backend/app/generate/`、`schema_contract.py`、`sqllex.py`、`scripts/generate.py` | 离线裁剪上下文、7 槽位提示词、确定性/LLM 生成、AST 静态校验 | `app.generate.pipeline.draft_sql` | 查询时 |
| 安全层 | S5 | `backend/app/security/`、`scripts/security.py` | AST 策略 + 只读账号 + 超时 + 单语句执行 | `app.security.policy.enforce` / `ReadOnlyExecutor` | 查询时 |
| 失败通道 | S6 | `backend/app/agent/`、`scenarios/`、`scripts/failures.py` | 16 错误码、校正闭环、取消、SSE 编排 | `AgentRunner.events()` | 查询时 |
| 前端 | S7 | `frontend/src/`、`scripts/contracts_gen.py` | 契约生成类型、SSE 解析、步骤条、三类失败 UI | `App.tsx` | 查询时 |
| 场景/夹具 | S6/S7 | `fixtures/` | 数据、注入语料、失败剧本、SSE 字节流 | `fixtures/failures/scenarios.yaml` | 离线验收 |

---

## 3. 模块清单（模块 → 职责 → 入口 → 调用方 → 时相）

### 3.1 应用与公共

| 模块 | 路径 | 职责 | 关键入口 | 被谁调用 | 时相 |
|---|---|---|---|---|---|
| 应用工厂 | `backend/app/main.py` | 声明 5 个 HTTP 端点、SSE 编码、线程/队列桥接、取消注册表 | `create_app()`、`app = create_app(default_runner_factory)` | uvicorn、`scenarios.app` | 查询时 |
| CLI 公共 | `backend/app/cli.py` | UTF-8 stdio 兜底 | `enable_utf8_stdio()` | 全部 CLI、`schema_contract`、`contracts_gen` | 构建/阶段 |
| Schema 契约 | `backend/app/schema_contract.py` | 加载/校验 `schema.contract.yaml` + DDL，生成文档 | `load_contract()`、`check_contract()`、`load_ddl()` | `build.plan`、`recall.catalog` | S1/S2 |
| SQL 词法 | `backend/app/sqllex.py` | 可执行注释检测、关键词扫描 | `has_executable_comment()`、`scan_keywords()` | `generate.guard`、`security.policy` | 查询时 |

### 3.2 构建层 S2（`backend/app/build/`）

| 模块 | 路径 | 职责 | 关键入口 | 被谁调用 | 时相 |
|---|---|---|---|---|---|
| 构建 CLI | `backend/app/build_meta_knowledge.py` | 解析 `--dry-run/--fresh/--verify/--assert-idempotent`，打印计划与 manifest | `main()` | `Makefile stage2`、`scripts/docker_init.py` | 构建时 |
| 构建配置 | `backend/app/build/config.py` | 从环境读三存储连接、目标名、embedding 参数 | `BuildConfig.from_env()` | build / recall / docker_init | 构建时 |
| 计划 | `backend/app/build/plan.py` | 纯内存生成 `BuildPlan`（不连存储） | `build_plan()`、`BuildPlan.counts()` | `build.pipeline`、CLI | 构建时 |
| 主流程 | `backend/app/build/pipeline.py` | noop/增量/全量、verify、幂等断言、manifest | `build()`、`verify()`、`assert_idempotent()` | 构建 CLI、docker_init | 构建时 |
| Meta 存储 | `backend/app/build/meta_store.py` | MySQL `meta_rebuild` 建表 / 写入 / 计数 | `MetaStore` | `build.pipeline` | 构建时 |
| ES 存储 | `backend/app/build/es_store.py` | `value_index_rebuild` 索引与 bulk | `ESValueStore` | `build.pipeline` | 构建时 |
| Qdrant 存储 | `backend/app/build/qdrant_store.py` | 列/指标两个 collection 的建库与 upsert | `QdrantVectorStore` | `build.pipeline` | 构建时 |
| Embedding | `backend/app/build/embedding.py` | 默认确定性 `hash-ngram-v1` | `make_embedding_provider()` | `build.plan`、`recall.clients` | 构建时 |
| 构建错误 | `backend/app/build/errors.py` | `BuildError` / `VerifyError` | 异常类型 | build 全层 | 构建时 |

### 3.3 召回层 S3（`backend/app/recall/`）

| 模块 | 路径 | 职责 | 关键入口 | 被谁调用 | 时相 |
|---|---|---|---|---|---|
| 目录 | `backend/app/recall/catalog.py` | 从契约构建内存 `Catalog`（表/列/指标/别名） | `default_catalog()` | recall、generate.context、security.policy | 查询/阶段 |
| 关键词 | `backend/app/recall/keywords.py` | 中文关键词与别名命中 | `extract_keywords()`、`term_matches()` | recall.nodes、generate.context | 查询 |
| 客户端 | `backend/app/recall/clients.py` | ES `_msearch`、Qdrant 批量、Meta 一次快照 | `RecallStack` | recall.nodes/pipeline | 阶段 S3 |
| 节点 | `backend/app/recall/nodes.py` | 4 路召回 + merge + filter + extra context | `recall_column()` 等 | recall.pipeline | 阶段 S3 |
| 编排 | `backend/app/recall/pipeline.py` | `query → RecallState`，不生成 SQL、不调 LLM | `recall()` | `scripts/recall.py`、集成测试 | 阶段 S3 |
| 渲染 | `backend/app/recall/render.py` | `RecallState` → 稳定 YAML | `render()` | S3 CLI | 阶段 S3 |

### 3.4 生成层 S4（`backend/app/generate/`）

| 模块 | 路径 | 职责 | 关键入口 | 被谁调用 | 时相 |
|---|---|---|---|---|---|
| 上下文 | `backend/app/generate/context.py` | `OfflineContextBuilder` 的 8 个真实阶段 | `phases()` / `result()` | `agent.orchestrator`、`generate.pipeline` | 查询时 |
| 意图 | `backend/app/generate/intent.py` | 排名/时间序列等意图判定 | `has_ranking_intent()` 等 | context、guard、deterministic | 查询时 |
| 模型 | `backend/app/generate/models.py` | `GenerateContext` / `GuardReport` 等数据类 | 数据类 | generate / agent 全层 | 查询时 |
| 提示词 | `backend/app/generate/prompts.py` | 渲染提示词、校验 7 个槽位 | `render_prompt()`、`build_slots()` | pipeline、correct | 查询时 |
| 生成器 | `backend/app/generate/provider.py` | 确定性生成器 + OpenAI 兼容 HTTP 生成器 | `DeterministicGenerator` / `HttpLlmGenerator.from_env()` | main、pipeline | 查询时 |
| 确定性实现 | `backend/app/generate/deterministic.py` | 无 LLM 时可复现的 SQL 生成 | `DeterministicGenerator` | provider | 查询时 |
| 输出形状 | `backend/app/generate/output_schema.py` | `sql` 或 `refusal` 两种形状校验 | `validate_payload()` | pipeline、correct | 查询时 |
| 静态校验 | `backend/app/generate/guard.py` | sqlglot AST 静态规则（表/列/常量/ORDER BY/LIMIT） | `check_sql()` | agent.validate、pipeline | 查询时 |
| 编排 | `backend/app/generate/pipeline.py` | `draft_sql` / `validate_draft` / `generate` | `draft_sql()` | agent.orchestrator、security.pipeline | 查询时 |

### 3.5 安全层 S5（`backend/app/security/`）

| 模块 | 路径 | 职责 | 关键入口 | 被谁调用 | 时相 |
|---|---|---|---|---|---|
| 策略配置 | `backend/app/security/config.py` | 读 `sql.policy.yaml` | `load_policy_config()` | policy / executor / corpus | 查询时 |
| AST 策略 | `backend/app/security/policy.py` | 6 步判定：注释→单语句→只读→白名单→词法→LIMIT | `enforce()` | agent.validate、executor、scenarios | 查询时 |
| 执行器 | `backend/app/security/executor.py` | 策略先行 + 只读账号 + 超时 + 禁多语句 | `ReadOnlyExecutor.execute()` | agent.orchestrator | 查询时 |
| 只读账号 | `backend/app/security/account.py` | 开通 / 验证 `dw_reader` | `verify_account()` | `scripts/security.py` | S5 实战 |
| 注入语料 | `backend/app/security/corpus.py` | 加载 36 拒绝 + 11 允许语料 | `load_corpus()` | S5 CLI | 离线验收 |
| 两屏演示 | `backend/app/security/demo.py` | 旧系统执行 / 新系统拒绝对比 | `run_demo()` | S5 CLI | S5 实战 |
| 安全编排 | `backend/app/security/pipeline.py` | question → generate → enforce → execute | `run_question()` | S5 CLI / 示例 | 阶段 S5 |

### 3.6 失败通道 S6（`backend/app/agent/`）

| 模块 | 路径 | 职责 | 关键入口 | 被谁调用 | 时相 |
|---|---|---|---|---|---|
| 错误表 | `backend/app/agent/errors.py` | 加载 16 码、构造 `ChannelError`、事件形状 | `load_error_table()`、`build_error()` | main、orchestrator、scenarios | 查询时 |
| 取消 | `backend/app/agent/cancel.py` | `request_id → CancelToken` 注册表 | `CancelRegistry` | main、orchestrator | 查询时 |
| 校验闸门 | `backend/app/agent/validate.py` | `guard`（S4） + `policy`（S5）组合 | `validate_sql()`、`DEFAULT_GATES` | orchestrator | 查询时 |
| 校正 | `backend/app/agent/correct.py` | 仅可重试错误；最多 1 次；改后重新校验 | `propose_correction()` | orchestrator | 查询时 |
| 值归一化 | `backend/app/agent/values.py` | Decimal 保数字、date → ISO 字符串 | `normalize_cell()` | orchestrator | 查询时 |
| 编排器 | `backend/app/agent/orchestrator.py` | 发 12 步事件、判定、执行、收尾 | `AgentRunner.events()` | main、scenarios | 查询时 |

### 3.7 场景、脚本与前端

| 模块 | 路径 | 职责 | 关键入口 | 被谁调用 | 时相 |
|---|---|---|---|---|---|
| 场景加载 | `backend/app/scenarios/loader.py` | 严格加载 `scenarios.yaml`（9 个场景） | `load_scenarios()` | `scripts/failures.py`、`scenarios.app` | 离线验收 |
| 场景应用 | `backend/app/scenarios/app.py` | 同一 `create_app`，只替换模型/数据库 | `scenario_runner_factory()` | `--port 8102` | 验收 |
| 契约生成 | `backend/app/scripts/contracts_gen.py` | 契约 → `frontend/src/generated/*` | `--check` | `make stage7` | 构建时 |
| Docker 初始化 | `backend/app/scripts/docker_init.py` | 等健康、开只读账号、校验/重建 S2 | `main()` | compose `init` | 部署时 |
| S3 CLI | `backend/app/scripts/recall.py` | 打印召回 YAML 与统计 | `main()` | `make stage3` | 阶段 |
| S4 CLI | `backend/app/scripts/generate.py` | 打印生成 YAML / 基线表 | `main()` | `make stage4`、`baseline` | 阶段 |
| S5 CLI | `backend/app/scripts/security.py` | 注入门禁、策略判定、账号验证 | `main()` | `make stage5` | 阶段 |
| S6 CLI | `backend/app/scripts/failures.py` | 6 类失败离线回放 | `--check` | `make stage6` | 阶段 |
| SSE 录制 | `backend/app/scripts/record_sse.py` | 录制/对账 14 条字节流夹具 | `--check` | `make stage7` | 阶段 |
| 前端入口 | `frontend/src/App.tsx` | 状态机、事件分流、取消 | `ask()` / `stop()` | `main.tsx` | 查询时 |
| 前端组件 | `frontend/src/components/` | `Composer`、`StepRail`、`ResultTable`、`ErrorCard`、`PseudoErrorCard` | 默认导出 | `App.tsx` | 查询时 |
| 前端库 | `frontend/src/lib/` | `api.ts`（含 SSE 解析）、`json-schema.ts`、`result.ts` | `streamQuery()`、`parseAgentEvent()` | App / ResultTable | 查询时 |
| 生成物 | `frontend/src/generated/` | 契约的类型/校验副本/回放数据（**不要手改**） | `sse.ts`、`sse.schema.json` | `lib/api`、`types.ts` | 查询时 |

---

## 4. HTTP API（5 个端点）

证据：`backend/app/main.py`（应用工厂 `create_app` 内逐条注册）。

| # | 方法 | 路径 | 作用 | 响应 | 行号 |
|---:|---|---|---|---|---|
| 1 | GET | `/api/health` | 健康检查，返回 `stage` | `{"status":"ok","stage":"S7"}` | L170–L172 |
| 2 | GET | `/api/steps` | 下发 `steps.yaml` 的 12 步与版本 | `StepsResponse` | L174–L181 |
| 3 | GET | `/api/errors` | 下发 16 错误码表 | `load_error_table().to_dict()` | L183–L191 |
| 4 | POST | `/api/query` | 单轮问数，SSE 流；请求体 `{query}` | `text/event-stream` + `X-Request-Id` | L193–L224 |
| 5 | POST | `/api/cancel` | 取消一次问数；请求体 `{request_id}` | `{"request_id","cancelled"}` | L226–L237 |

补充：`POST /api/query` 的空问题在进入流之前返回 **422**（L208–L209）；
CORS 只放行 `127.0.0.1:5273` / `localhost:5273`（L160–L168）。

---

## 5. 12 个步骤

证据：`contracts/steps.yaml`（YAML 解析 ✅，`version: 1`）。

| # | id | label | conditional | 谁发事件 |
|---:|---|---|:---:|---|
| 1 | `extract_keywords` | 抽取关键词 | 否 | `OfflineContextBuilder.phases()` |
| 2 | `recall_column` | 召回字段信息 | 否 | 同上 |
| 3 | `recall_value` | 召回字段取值 | 否 | 同上 |
| 4 | `recall_metric` | 召回指标信息 | 否 | 同上 |
| 5 | `merge_retrieved_info` | 合并召回信息 | 否 | 同上 |
| 6 | `filter_table` | 过滤表信息 | 否 | 同上 |
| 7 | `filter_metric` | 过滤指标信息 | 否 | 同上 |
| 8 | `add_extra_context` | 添加额外上下文 | 否 | 同上 |
| 9 | `generate_sql` | 生成SQL | 否 | `AgentRunner._run()` |
| 10 | `validate_sql` | 校验SQL | 否 | `AgentRunner._run()` |
| 11 | `correct_sql` | 校正SQL | **是** | `AgentRunner._correct()` / 显式 `skipped` |
| 12 | `run_sql` | 执行SQL | 否 | `AgentRunner._run()` |

不变式：条件步骤要么 `running → success/error`，要么**显式** `skipped`，
不允许永远停在 `pending`（`agent/orchestrator.py` L168–L179）。

---

## 6. 错误码（16 个 / 3 类）

证据：`contracts/errors.yaml`（YAML 解析 ✅）。`class` 决定 UI，不决定码。

| # | code | class | retryable | label |
|---:|---|---|:---:|---|
| 1 | `SQL_REJECTED` | failure | 否 | SQL 被安全策略拒绝 |
| 2 | `SQL_SYNTAX` | failure | 是 | SQL 语法错误 |
| 3 | `SQL_UNKNOWN_COLUMN` | failure | 是 | 引用了不存在的列 |
| 4 | `EMPTY_RESULT` | **empty** | 否 | 查询成功但没有数据 |
| 5 | `LLM_REFUSAL` | failure | 否 | 模型明确拒答 |
| 6 | `TIMEOUT` | failure | 否 | 执行超时 |
| 7 | `CANCELLED` | **cancelled** | 否 | 用户取消 |
| 8 | `SQL_UNKNOWN_TABLE` | failure | 是 | 引用了不存在的表 |
| 9 | `SQL_NOT_READ_ONLY` | failure | 否 | 不是只读查询 |
| 10 | `SQL_MULTIPLE_STATEMENTS` | failure | 否 | 不是单条语句 |
| 11 | `SQL_CONSTANT_PROJECTION` | failure | 是 | 投影了常量 |
| 12 | `SQL_MISSING_ORDER_BY` | failure | 是 | 缺 ORDER BY |
| 13 | `SQL_MISSING_LIMIT` | failure | 是 | 缺 LIMIT |
| 14 | `SQL_EMPTY` | failure | 否 | SQL 为空 |
| 15 | `SQL_EXECUTION_ERROR` | failure | 否 | 数据库执行出错 |
| 16 | `INTERNAL_ERROR` | failure | 否 | 系统内部错误 |

| class | 含义 | UI | 步骤条 |
|---|---|---|---|
| `failure` | 真失败 | 红框 + 错误码 + 可复制详情 | 失败步骤红叉 |
| `empty` | 合法但无数据 | 虚线空态卡，不标红 | 执行步骤保持绿色 |
| `cancelled` | 用户取消 | 中性卡 | 正在跑的步骤标「已取消」 |

校正策略同文件声明：`max_attempts: 1`、`revalidate: true`，
重新过 `guard` + `policy`。`SQL_REJECTED` **永不重试**。

---

## 7. SSE 事件（3 种）

证据：`contracts/sse.schema.json`（`oneOf` 3 个 `$defs` ✅）。

| type | 必填字段 | 语义 | 终态 |
|---|---|---|:---:|
| `progress` | `step`、`status`、`duration_ms` | 步骤推进；`status ∈ {running, success, error, skipped}` | 否 |
| `result` | `data.columns[]`、`data.rows[][]` | 成功结果；列类型 `string/number/boolean/null/date` | 是 |
| `error` | `code`、`class`、`message`、`step`、可选 `detail` | 失败/空/取消；`code` 必须来自 `errors.yaml` | 是 |

不变式：流**一定**以 `result` 或 `error` 收尾（`main.py` L14–L18、
`AgentRunner.events()` L199–L209）；未知 `type` 前端忽略并留痕，不当失败。

---

## 8. 数据模型（5 表 / 24 列 / 6 指标 / 9 条列—指标关系）

证据：`contracts/schema.contract.yaml`；用 PyYAML 解析计数 ✅。

| 表 | 列数 | 列 | grain |
|---|---:|---|---|
| `dim_region` | 4 | `region_id` `province` `region_name` `country` | 一行一个 `region_id` |
| `dim_customer` | 4 | `customer_id` `customer_name` `gender` `member_level` | 一行一个 `customer_id` |
| `dim_product` | 4 | `product_id` `product_name` `category` `brand` | 一行一个 `product_id`（无 `price`） |
| `dim_date` | 5 | `date_id` `year` `quarter` `month` `day` | 一行一个 `date_id`（一天） |
| `fact_order` | 7 | `order_id` `customer_id` `product_id` `date_id` `region_id` `order_quantity` `order_amount` | 一行一个 `order_id`（一单） |
| **合计** | **24** | | |

逻辑外键 4 条（`fact_order` → 四张维表），见 `foreign_keys`。

| # | 指标 | 口径 | 关联列（→ 列—指标关系） |
|---:|---|---|---|
| 1 | `GMV` | `SUM(order_amount)` | `fact_order.order_amount` |
| 2 | `AOV` | `SUM(order_amount) / COUNT(DISTINCT order_id)` | `fact_order.order_amount`、`fact_order.order_id` |
| 3 | `订单量` | `COUNT(DISTINCT order_id)` | `fact_order.order_id` |
| 4 | `销量` | `SUM(order_quantity)` | `fact_order.order_quantity` |
| 5 | `平均件单价` | `SUM(order_amount) / SUM(order_quantity)` | `fact_order.order_amount`、`fact_order.order_quantity` |
| 6 | `平均每单件数` | `SUM(order_quantity) / COUNT(DISTINCT order_id)` | `fact_order.order_quantity`、`fact_order.order_id` |
| **合计** | **6** | | **9 条关系** |

期望值（契约内声明）：GMV `279159.5`、AOV `2427.47`、订单量 `115`、
销量 `622`、平均件单价 `448.81`、平均每单件数 `5.41`。

---

## 9. 端口表

证据：`compose.yaml`、`Makefile`、`docs/SETUP-FROM-SCRATCH.md` §1.3。

| 端口 | 服务 | 绑定 | 说明 | 状态 |
|---:|---|---|---|---|
| `8100` | FastAPI（后端） | `127.0.0.1:8100` | 本地 `make dev-backend`；容器也映射这里 | ✅ |
| `5273` | Vite（前端开发） | localhost | 刻意避开旧栈 `5173`；未配 `strictPort` | ✅ |
| `8080` | 前端容器（nginx → 80） | `0.0.0.0:8080` 默认 | 全量部署唯一对外入口 | ✅ |
| `3306` | MySQL | `127.0.0.1:3306` | 数仓 + Meta | ✅ |
| `9200` | Elasticsearch | `127.0.0.1:9200` | 取值索引 | ✅ |
| `6333` | Qdrant REST | `127.0.0.1:6333` | 向量索引（`6334` gRPC 未用） | ✅ |

临时验收端口（与主端口隔离）：`8101/5274`（S0）、`8102/5275`（S6）、
`8103/5276`（S7）。旧系统 `8000/5173` **不启动**。

---

## 10. 测试

| 项 | 值 | 证据 | 状态 |
|---|---|---|---|
| 后端测试文件 | 45 | `find backend/tests -name 'test_*.py'` | ✅ |
| 后端通过数 | 782 passed / 31 skipped | `README.md` | 🟡 本机未跑 |
| 前端单测 | 2 个文件（README 声称 40 passed） | `frontend/src/lib/*.test.ts` | 🟡 |
| 场景数 | 9（6 类失败 + happy + slow + corrected） | `fixtures/failures/scenarios.yaml` | ✅ |
| SSE 夹具 | 14 条 | `fixtures/sse/*.json` | ✅ |
| 注入语料 | 36 拒绝 + 11 允许 | `fixtures/injection/sql-injection.yaml`（YAML 解析） | ✅ |
| 黄金集 | 20 题 | `README.md` §当前进度、`docs/SETUP-FROM-SCRATCH.md` §2.6 | 🟡 |

45 个后端测试文件按层归类：

| 层 | 测试文件（去掉 `test_` 前缀） | 数量 |
|---|---|---:|
| 契约对齐 / S0–S1 | `s0_contract` `s1_schema_contract` `contract_alignment` `error_alignment` `policy_alignment` `contract_gen` | 6 |
| S2 构建 | `s2_build` `build_config` `meta_store` `pipeline` | 4 |
| S3 召回 | `clients` `keywords` `render` `golden` | 4 |
| S4 生成 | `generate` `guard` `prompts` `baseline` `sqllex` | 5 |
| S5 安全 | `policy` `executor` `injection_corpus` `zero_false_positive` `account` `demo` `config` `security_cli` | 8 |
| S6 失败 / 编排 | `errors` `correct` `orchestrator` `scenarios` `values` `type_fidelity` `api` | 7 |
| S7 前端契约 / SSE | `sse_fixtures` | 1 |
| 部署 / 脚本 / 环境 | `docker_env_script` `docker_init` `docker_reset_script` `docker_smoke_script` `export_docker_env_script` `line_endings` `makefile_portability` `python_interpreter` `recall_demo_script` `smoke_checks` | 10 |
| **合计** | | **45** |

---

## 11. 模块 → 文件 → 证据

| 结论 | 文件 | 证据 | 状态 |
|---|---|---|---|
| 5 个 HTTP 端点 | `backend/app/main.py` | `@application.get/post` L170/L174/L183/L193/L226 | ✅ |
| SSE 一定以 result/error 收尾 | `backend/app/main.py`、`backend/app/agent/orchestrator.py` | 兜底 `except` 发 `INTERNAL_ERROR`，L199–L209 | ✅ |
| 12 步契约 | `contracts/steps.yaml`、`GET /api/steps` | YAML 12 条 + `conditional` 1 条 | ✅ |
| 16 错误码 / 3 class | `contracts/errors.yaml`、`GET /api/errors` | YAML 解析 16 / 3 | ✅ |
| 3 种 SSE 事件 | `contracts/sse.schema.json` | `oneOf` 3 个 `$defs` | ✅ |
| 5 表 / 24 列 / 6 指标 | `contracts/schema.contract.yaml` | PyYAML 计数 | ✅ |
| 9 条列—指标关系 | 同上 | `relevant_columns` 求和 1+2+1+1+2+2 | ✅ |
| S2 写入 44/76/98/22/241 | `backend/app/build/plan.py`、`build_meta_knowledge.py --dry-run` | `facts.md` §5；`counts()` 打印 | 🟡 按公式推导 |
| 上下文 8 阶段真实执行 | `backend/app/generate/context.py` | `phases()` L363–L376 | ✅ |
| 校正最多 1 次且重新校验 | `contracts/errors.yaml`、`agent/orchestrator.py` | `correction.max_attempts: 1`；`continue` 回校验 | ✅ |
| 策略先于连库 | `backend/app/security/executor.py` | `execute()` 先 `enforce()`，L226 起 | ✅ |
| 前端不硬编码步骤/错误码 | `frontend/src/App.tsx`、`lib/api.ts` | `fetchSteps()` / `fetchErrorCodes()` | ✅ |
| 未知事件类型被忽略 | `frontend/src/lib/api.ts` | `parseAgentEvent()` 返回 `unknown_type` | ✅ |
| 契约生成前端类型 | `backend/app/scripts/contracts_gen.py` | 生成 `generated/sse.ts` 等 3 个文件 | ✅ |
| 失败场景 9 条 | `fixtures/failures/scenarios.yaml` | 9 个 `- id:` | ✅ |

---

## 12. 不一致与未决

| # | 现象 | 影响 | 处理 |
|---:|---|---|---|
| 1 | `README.md` 写 **782 passed**；`docs/SETUP-FROM-SCRATCH.md` §3 写 **665 passed / 31 skipped** | 测试计数无单一事实源 | 按 `facts.md` 采用 782，标 🟡；建议协调者以本机一次全量跑数为准回写 |
| 2 | 任务书写前端有 `lib/sse`；仓库里**没有** `lib/sse.ts` | 组件树图若照抄会画出不存在的文件 | SSE 解析器实际在 `lib/api.ts` 的 `SseParser`；`generated/sse.ts` 只提供类型与 `EVENT_TYPES`。图 04 按真实文件画，并在说明中标注 |
| 3 | `README.md` 目录树写 `frontend/tests/`「无头浏览器 + SSE 回放服务器」，实际确有 5 个 `.mjs`；但单测在 `src/lib/*.test.ts` | 前端测试口径容易混 | 本文件把「单测 2 个」与「浏览器/回放 5 个」分开 |
| 4 | `facts.md` 说「前端测试文件 2 个」 | 只数了 `*.test.*`，不含 `frontend/tests/*.mjs` | 本文件沿用 2（单测）并另列 5（脚本） |
| 5 | `--fresh` 写三存储、真实 LLM、浏览器验收、Compose 全栈均未在本机执行 | 只能给 🟡 / ⚪ | 见 `facts.md` §9 |
| 6 | 生产问数主链路**不读** S3 的 ES/Qdrant 召回 | 容易误以为查询时依赖三存储 | 生产用 `OfflineContextBuilder`（契约离线裁剪）；S3 只在 `stage3` 与集成测试中使用（`README.md` §数据与存储） |

---

## 13. 复核命令

```bash
cd /home/zhensirong/VM-Share/DSWS-design

# 规模
find backend/app -name '*.py' | wc -l                       # 60
find backend/tests -name 'test_*.py' | wc -l                # 45
find frontend/src -type f | wc -l                           # 17
find contracts -type f | wc -l                              # 13
find fixtures -type f | wc -l                               # 19

# 契约计数
python3 - <<'PY'
import yaml, json
s = yaml.safe_load(open('contracts/schema.contract.yaml'))
print(len(s['tables']), sum(len(t['columns']) for t in s['tables']), len(s['metrics']),
      sum(len(m['relevant_columns']) for m in s['metrics']))
print(len(yaml.safe_load(open('contracts/steps.yaml'))['steps']))
print(len(yaml.safe_load(open('contracts/errors.yaml'))['codes']))
print(len(json.load(open('contracts/sse.schema.json'))['oneOf']))
PY
```
