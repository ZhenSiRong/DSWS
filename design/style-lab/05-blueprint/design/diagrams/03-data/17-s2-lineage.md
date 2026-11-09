# 17 · S2 数据 lineage（契约 + 冻结数仓 → 三存储 + manifest）

**一句话**：S2 先把契约与 DDL 校验成一份纯内存 `BuildPlan`，再按 Meta → ES → Qdrant → manifest 的顺序写入；任何一步失败都不会登记成功的 manifest。

**这张图回答**：数据从哪来？在哪一步校验？三存储各写多少？`5/24/6/9/76/98/22` 分别是什么？manifest 为什么是构建成功的唯一凭据？

**图例**：蓝色=输入与契约校验；橙色=BuildPlan 生成；青色=存储；绿色=验收；红色=拒绝构建。

**关键元素**：
- 输入：`contracts/schema.contract.yaml`（语义）+ `fixtures/dw.sql`（物理类型与真实值）。
- `check_contract`：语义与 DDL 不一致时抛 `BuildError`，零写入。
- `build_plan`：生成 5 个 `TablePlan`、24 个 `ColumnPlan`、6 个 `MetricPlan`、76 个 `ValueDoc`、98 个 column point、22 个 metric point。
- Meta：44 行 = `table_info` 5 + `column_info` 24 + `metric_info` 6 + `column_metric` 9。
- ES：76 篇取值文档；Qdrant：98 + 22 个 point。
- `build_manifest`：1 行，记录 `config_hash`、目标名、7 个计数与 `status`。
- 推导写入总数：44 + 76 + 98 + 22 + 1 = **241**。

**证据**：
- `backend/app/build/plan.py` L281–L400：`build_plan` 与重复 ID 检查。
- `backend/app/build/plan.py` L174–L185：`counts()` 的 7 个键。
- `backend/app/build/pipeline.py` L196–L291：构建顺序、`meta.reset_data` → `write_plan` → `bulk_index` → 两个 `upsert` → `write_manifest`。
- `backend/app/build/meta_store.py` L25–L95：5 张 Meta 表 DDL。
- `backend/app/build/es_store.py` L107–L141：bulk 写入 `value_index_rebuild`。
- `backend/app/build/qdrant_store.py` L113–L145：`column_info_rebuild` / `metric_info_rebuild` 写入。
- `backend/app/build_meta_knowledge.py --dry-run`（✅ 2026-10-27 本机）：5/24/6/9/76/98/22。
- `design/inventory/facts.md` L52–L67：计数与 241 的推导。

**边界**：241 是按代码公式推导，不是 `--fresh` 实测（本机 Docker socket 无权限），标 🟡。manifest 的 `status=failed` 也会落一行，用于记录失败；只有 `status=success` 且哈希、计数、维度、样例都一致时 `verify` 才通过。
