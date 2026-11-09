# 03 · backend/app 模块依赖

**一句话**：`backend/app` 分成构建时与查询时两条依赖链，共享 `schema_contract`、`sqllex` 和运行时内存目录 `recall.catalog + keywords`。

**这张图回答**：谁 import 谁？哪些依赖只发生在构建时，哪些发生在每次请求？安全层和生成层各自依赖什么？

**图例**：实线=import；虚线=运行时调用；橙=构建时；紫=查询时；红=安全；蓝=契约/共享；青=存储。

**关键元素**：

- **构建时**：`build_meta_knowledge` → `build.pipeline` → `build.plan + config` / `build.*_store` / `build.embedding`；写 MySQL、ES、Qdrant 后退出。
- **查询时**：`main` → `agent.orchestrator` → `agent.validate/correct/errors/cancel`；orchestrator 再调用 `generate.context/pipeline` 与 `security.executor`。
- **共享目录**：`recall.catalog + keywords` 被 generate、security、recall 共同 import，是**内存目录**，不是 S3 检索客户端。
- **生成**：`generate.pipeline` → `context` / `guard` / `prompts + provider`。
- **安全**：`security.policy` → `sqllex` + `catalog`；`executor` → `policy`；executor 只读 MySQL。
- **S3 召回**：`recall.pipeline + nodes` → `recall.clients` 读三存储，仅阶段验收使用。

**证据**：

- 本机 AST 提取的 `app.*` import 清单（✅ 2026-10-29，脚本遍历 `backend/app/**/*.py`）
- `backend/app/generate/context.py` L30–L32：import `recall.catalog` / `recall.keywords` / `recall.models`
- `backend/app/generate/pipeline.py` L192–L206：`generate_with_recall` 备用路径（未画入主图）
- `backend/app/agent/orchestrator.py` L43、L126、L199–L214
- `backend/app/security/policy.py` L298；`security/executor.py` L161、L226
- `backend/app/recall/pipeline.py` L35；`recall/nodes.py` L260–L261
- `backend/app/build/pipeline.py`、`build/plan.py`、`build/*_store.py`（✅ 文件存在）

**边界**：

- 图把文件聚合成文件组；逐文件职责与入口见 `inventory/software-census.md` §3。
- `generate_with_recall` 是备用完整召回路径，生产主链路用 `build_offline_context`，因此没有画 `generate.pipeline → recall.pipeline` 的边。
- 实线 import 由 AST 实测（✅）；`validate → guard/policy` 的虚线「调用」由代码阅读推断（🟡）。
- 脚本（`scripts/*`）与 `scenarios/` 未入图，避免外围节点淹没主依赖；其清单见 census §3.7。
