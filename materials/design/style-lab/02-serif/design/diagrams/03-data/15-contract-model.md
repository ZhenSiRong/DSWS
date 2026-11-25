# 15 · 契约模型（表 / 列 / 指标 / 值域 / 列—指标）

**一句话**：`schema.contract.yaml` 把「表、列、指标、值域、列—指标关系」建模成五个对象；列—指标关系共 9 条，是 6 个指标 `relevant_columns` 的并集。

**这张图回答**：契约里到底有哪些对象？每个对象带哪些字段？`ValueDomain` 的 `kind` 有哪几种？`ColumnMetric` 为什么是派生表？

**图例**：蓝色=契约对象；菱形箭头=引用；`*--`=组合；黄色便签=口径说明。

**关键元素**：
- `SchemaContract`：顶层 `version`、`dataset`、`tables`、`metrics`。
- `Table`：`name`、`role`（fact/dim）、`grain`、`primary_key`、`columns`、`foreign_keys`、`measures`。
- `Column`：`name`、`type`、`role`、`nullable`、`aliases`、`value_domain`。
- `Metric`：`name`、`label`、`formula`、`aggregation`、`expected_value`、`relevant_columns`、`rejected_values`。
- `ValueDomain.kind`：`enum` / `range` / `id` / `foreign_key` / `open` 五种。
- `ColumnMetric`：`column_id` + `metric_id`；契约里不单独写，由 6 个指标的 `relevant_columns` 展开得到 9 条。

**证据**：
- `contracts/schema.contract.yaml` L15–L399：所有字段与 5 表 / 24 列 / 6 指标。
- `backend/app/build/plan.py` L69–L192：`TablePlan` / `ColumnPlan` / `MetricPlan` / `BuildPlan.column_metric_pairs()`。
- `backend/app/build/meta_store.py` L66–L70：`column_metric` 复合主键 `(column_id, metric_id)`。
- `backend/app/build_meta_knowledge.py --dry-run`（✅ 2026-10-27 本机，计数 5/24/6/9）。

**边界**：`ForeignKey` 与 `Measure` 是契约内的匿名子结构，不是独立数据库表；图中把它们画成类是为了看清字段来源。`ColumnMetric` 是 `BuildPlan` 的派生结果，不来自 YAML 里的独立节点。
