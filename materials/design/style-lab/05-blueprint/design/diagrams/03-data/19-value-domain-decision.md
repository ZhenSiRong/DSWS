# 19 · 值域分类决策树（哪些列写 ES）

**一句话**：只有「维度列 + `enum` 或低基数 `open`」会逐值写 ES 并置 `sync_values=1`；`range`、主键、外键、度量一律 `sync_values=0`，不写 ES。

**这张图回答**：`enum` 和 `range` 分别怎么处理？`open` 文本为什么有的进 ES 有的不进？`sync_values` 到底记什么？Meta 的 `examples` 和 ES 的完整值域是什么关系？

**图例**：蓝色=判断；橙色=生成 ValueDoc；青色=ES / Meta 字段；灰色=不写 ES 的分支。

**关键元素**：
- 第一问 `role = dimension?`：主键、外键、度量直接 `sync_values=false`。
- 第二问 `value_domain.kind`：
  - `enum`：取 distinct 全集，逐值生成 `ValueDoc`。
  - `open`：仅当 `0 < distinct ≤ max_value_docs`（默认 1000）才写；`customer_name`（20 值）、`product_name`（15 值）因此进入 ES。
  - `range` / `id` / `foreign_key`：不写 ES。`date_id`、`month`、`day`、`order_amount` 都在这一类。
- 每个 `ValueDoc.id = column_id.value`，写入 `value_index_rebuild`，字段为 `id` / `value` / `column_id`。
- `sync_values`：写入 `column_info` 的布尔列，记录「这列的完整取值是否已经进了 ES」。
- `examples` 仍只存前 10 条，S3 不能把它当全集。

**证据**：
- `backend/app/build/plan.py` L209–L225：`_should_sync` 的四个条件。
- `backend/app/build/plan.py` L312–L341：逐列计算 `sync_values` 并展开 `ValueDoc`。
- `backend/app/build/plan.py` L34：`EXAMPLES_LIMIT = 10`。
- `backend/app/build/meta_store.py` L36–L48：`sync_values TINYINT(1) NOT NULL DEFAULT 0`。
- `backend/app/build/es_store.py` L21–L33：ES mapping 只有 `id` / `value` / `column_id`。
- `backend/app/recall/models.py` L16、L92–L93：S3 明确把 `examples` 标为截断。
- `backend/app/recall/catalog.py` L187–L192：兜底 payload 里 `examples=[]`、`sync_values=False`。

**边界**：`sync_values` 目前是**元数据记录**，不是 S3 的运行时开关；S3 读 Meta 的 `examples` 并显式带 `examples_truncated=True`。76 篇 ES 文档是本数据集的结果（enum 41 值 + open 35 值），不是固定常量。`range` 列如果将来需要范围检索，必须改契约与 S2 规则，而不是手工往 ES 塞文档。
