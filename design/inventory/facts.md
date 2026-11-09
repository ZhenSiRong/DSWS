# DSWS 软件普查 · 共享事实底稿

> 基线：`eea5e75`（2026-10-29）。本文件只记录**能指到文件或命令**的事实。
> 任何图、任何章节引用计数时，以本文件为准；发现不一致，先改这里并注明出处。

## 1. 仓库与阶段

| 项 | 值 | 证据 |
|---|---|---|
| 仓库 | `github.com:LucianZoraZephyr/DSWS` | `git remote -v` |
| 基线提交 | `eea5e75 docs: 精简 README 为可操作版本` | `git log -1` |
| 分支 | `design/atlas`（设计工作树） | `git branch --show-current` |
| 阶段 | S0–S7 已实现；S8 为后续/生产化 | `README.md` §当前进度、`docs/SETUP-FROM-SCRATCH.md` |
| 后端测试 | README 声称 **782 passed** | `README.md`；本机未跑全量，标 🟡 |
| 后端 Python 文件 | 60 个 | `find backend/app -name '*.py' | wc -l` |
| 后端测试文件 | 45 个 | `find backend/tests -name 'test_*.py' | wc -l` |
| 前端测试文件 | 2 个 | `find frontend -name '*.test.*' | wc -l` |

## 2. 运行入口与端口

| 入口 | 端口 | 证据 |
|---|---|---|
| FastAPI（本地） | `8100` | `Makefile` dev-backend、`docs/SETUP-FROM-SCRATCH.md` §2.11 |
| Vite（本地） | `5273` | `Makefile` dev-frontend；刻意避开旧栈 5173 |
| 前端容器（nginx） | `8080` → 80 | `compose.yaml` frontend |
| MySQL | `3306` | `compose.yaml` mysql |
| Elasticsearch | `9200` | `compose.yaml` elasticsearch |
| Qdrant | `6333` | `compose.yaml` qdrant |

## 3. HTTP API

| 方法 | 路径 | 作用 | 证据 |
|---|---|---|---|
| GET | `/api/health` | 健康检查，返回 `stage` | `backend/app/main.py` |
| GET | `/api/steps` | 返回 `contracts/steps.yaml` 的 12 步 | `backend/app/main.py` |
| GET | `/api/errors` | 返回错误码表 | `backend/app/main.py` |
| POST | `/api/query` | 单轮问数，SSE 流 | `backend/app/main.py` |
| POST | `/api/cancel` | 取消一次问数 | `backend/app/main.py` |

## 4. 契约

| 契约 | 内容 | 计数 | 证据 |
|---|---|---|---|
| `contracts/schema.contract.yaml` | 5 表 / 24 列 / 6 指标 | 5 / 24 / 6 | YAML 解析 |
| `contracts/steps.yaml` | 12 个步骤，`correct_sql` 条件执行 | 12 | YAML 解析 |
| `contracts/errors.yaml` | 16 个错误码，3 个 class | 16 / 3 | YAML 解析 |
| `contracts/sse.schema.json` | 3 种事件：progress / result / error | 3 | JSON Schema |
| `contracts/sql.policy.yaml` | 只读、单语句、表白名单等策略 | — | 文件 |
| `contracts/sql.output.schema.json` | 生成 SQL 的输出结构 | — | 文件 |
| `contracts/prompts/` | 生成 / 校正提示词 | — | 目录 |

## 5. S2 三存储真实计数

来源：`backend/app/build_meta_knowledge.py --dry-run`（✅ 2026-10-27 本机）与 `plan.counts()`。

| 目标 | 计数 | 含义 |
|---|---|---|
| Meta `table_info` | 5 | 5 张表 |
| Meta `column_info` | 24 | 24 列 |
| Meta `metric_info` | 6 | 6 个指标 |
| Meta `column_metric` | 9 | 9 条列—指标关系 |
| ES `value_index_rebuild` | 76 | 76 条 enum 取值文档 |
| Qdrant `column_info_rebuild` | 98 | 24 列拆成 98 条检索文本 |
| Qdrant `metric_info_rebuild` | 22 | 6 指标拆成 22 条检索文本 |

推导写入总数：44（Meta 行）+ 76（ES）+ 98 + 22 + 1（manifest）= **241**。
这是按代码公式推导，不是 `--fresh` 实测；标 🟡。

## 6. 数据模型

5 张表：

- `dim_region`：一行一个 `region_id`；`region_name` 是省的分组，不是唯一键；无 `city` 列。
- `dim_customer`：一行一个 `customer_id`。
- `dim_product`：一行一个 `product_id`；无 `price` 列。
- `dim_date`：一行一个 `date_id`（一天）。
- `fact_order`：一行一个 `order_id`（一单）；`order_quantity` 是单内件数，`order_amount` 是整单金额。

外键关系（逻辑）：

```text
fact_order.customer_id -> dim_customer.customer_id
fact_order.product_id  -> dim_product.product_id
fact_order.date_id     -> dim_date.date_id
fact_order.region_id   -> dim_region.region_id
```

6 个指标：`GMV`、`AOV`、`订单量`、`销量`、`平均件单价`、`平均每单件数`。

## 7. Docker Compose 服务

`compose.yaml` 定义 6 个服务：

| 服务 | 作用 | 关键依赖 |
|---|---|---|
| `mysql` | 数仓 + Meta 存储 | 健康检查 `mysqladmin ping` |
| `elasticsearch` | 取值索引 | 健康检查 cluster health |
| `qdrant` | 向量索引 | 健康检查 `/readyz` |
| `init` | 一次性初始化：建库、账号、S2 构建 | 依赖三存储 healthy |
| `backend` | FastAPI | 依赖 `init` completed |
| `frontend` | nginx + 静态资源 | 依赖 backend healthy |

## 8. 安全边界

- 应用账号：`didilili`，只读账号：`dw_reader`（密码由 `REBUILD_DW_RO_PASSWORD` 提供）。
- 执行器：`ReadOnlyExecutor`，只允许单条 `SELECT`，带 `max_execution_time`。
- 策略：`contracts/sql.policy.yaml`，拒绝多语句、写操作、非白名单表、常量投影、缺 `ORDER BY` / `LIMIT`。
- 旧系统：只读夹具，不作为参考实现；rebuild 目标一律 `*_rebuild`。

## 9. 已验证 / 未验证（本设计工作树）

| 项 | 状态 | 说明 |
|---|---|---|
| 拉取 `eea5e75` | ✅ | `git pull --ff-only` 成功 |
| `--dry-run` 计数 | ✅ | 2026-10-27 本机 |
| 全量后端测试 782 | 🟡 | README 声称；本机未跑 |
| `--fresh` 写三存储 | ⚪ | Docker socket 无权限 |
| 真实 LLM 生成 | ⚪ | 无端点 / 无 Key |
| 前端构建 / 浏览器验收 | ⚪ | 本次未跑 |
| Docker Compose 全栈 | ⚪ | 本次未跑 |
