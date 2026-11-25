# 16 · 一份契约如何落到三存储（region_name / order_amount）

**一句话**：同一份契约列，Meta 得到 1 行结构描述，ES 按值域决定是否展开取值文档，Qdrant 把名称、描述、每个别名各变成一个可检索 point。

**这张图回答**：`region_name` 和 `order_amount` 分别变成什么？为什么一个进 ES、一个不进？Qdrant 的 98 个 point 是怎么来的？Meta 的 `examples` 能不能当全集？

**图例**：蓝色=契约；橙色=BuildPlan；青色=三存储；灰色=口径说明。

**关键元素**：
- `dim_region.region_name`：`kind=enum`，5 个值（华南/华东/西南/华北/华中），`role=dimension`，`sync_values=true`。
  - Meta：`column_info` 1 行，`examples` 只取排序后前 10 条（本列共 5 条）。
  - ES：5 篇文档，`id=dim_region.region_name.华南` 这类，`value` + `column_id`。
  - Qdrant：`region_name`、描述、`地区`、`区域`、`大区` 共 5 个 point。
- `fact_order.order_amount`：`kind=range`（30.0–9499.0），`role=measure`，`sync_values=false`。
  - Meta：`column_info` 1 行，`value_domain` 原样存 JSON，`sync_values=0`。
  - ES：0 篇文档；range 不进入取值索引。
  - Qdrant：`order_amount`、描述、`订单金额`、`收入`、`成交金额` 共 5 个 point。
- 24 列合计 98 个 column point；6 指标另有 22 个 metric point。

**证据**：
- `contracts/schema.contract.yaml` L53–L61（`region_name`）、L288–L309（`order_amount`）。
- `backend/app/build/plan.py` L209–L225：`_should_sync` 只放行 dimension + enum/open + 基数阈值。
- `backend/app/build/plan.py` L235–L243：点文本 = 名称 + 描述 + 别名，去重。
- `backend/app/build/plan.py` L34：`EXAMPLES_LIMIT = 10`，Meta 的 `examples` 是显式截断。
- `backend/app/build/meta_store.py` L36–L48：`column_info` 字段；L254–L272 写入。
- `backend/app/build/es_store.py` L21–L33：`value` / `column_id` / `id` 三个字段。
- `backend/app/build/qdrant_store.py` L113–L145：按 batch upsert point 与向量。
- `backend/app/build_meta_knowledge.py --dry-run`（✅ 2026-10-27）：76 / 98 / 22。

**边界**：图中箭头表示「由 BuildPlan 写往存储」的构建方向；查询时三个存储之间没有数据流动。`region_name` 的 5 篇 ES 文档是按本数据集 6 行 `dim_region` 去重后的结果；换数据集计数会变，但规则不变。
