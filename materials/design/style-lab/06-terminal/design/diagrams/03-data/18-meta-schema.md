# 18 · Meta 表结构（5 张元数据表）

**一句话**：Meta 用 5 张表描述「有哪些表、哪些列、什么指标、列和指标怎么关联、这次构建是否成功」；前 4 张是知识，`build_manifest` 是构建凭据。

**这张图回答**：每张 Meta 表的字段和主键是什么？`column_info` 怎么指向表？`column_metric` 的复合主键是什么？manifest 记录哪些计数？

**图例**：蓝色=Meta 表；`PK`=主键，`UK`=唯一键，`FK`=逻辑外键（DDL 未声明物理外键）。

**关键元素**：
- `table_info`：`id` 主键（表名），`name`、`role`、`description`、`grain`。
- `column_info`：`id` 主键（`table.column`），`name`、`type`、`role`、`examples`(JSON)、`description`、`alias`(JSON)、`table_id`、`value_domain`(JSON)、`sync_values`；`table_id` 建了索引。
- `metric_info`：`id` 主键（指标名），`name`、`label`、`description`、`formula`、`relevant_columns`(JSON)、`alias`(JSON)、`aggregation`、`expected_value`、`grain`、`rejected_values`(JSON)。
- `column_metric`：复合主键 `(column_id, metric_id)`，两列分别逻辑指向 `column_info.id` 与 `metric_info.id`。
- `build_manifest`：自增 `seq` 主键；`build_id` 唯一；记录 `manifest_version`、`built_at`、`config_hash`、`contract_version`、嵌入模型/维度、7 个计数、`es_analyzer`、`targets_json`、`status`、`error`。

**证据**：
- `backend/app/build/meta_store.py` L25–L95：建表语句与主键/索引。
- `backend/app/build/meta_store.py` L236–L304：`write_plan` 写入 4 张知识表。
- `backend/app/build/meta_store.py` L306–L341：`write_manifest`。
- `backend/app/build/meta_store.py` L347–L368：`read_manifest` 取最新一行并把 `targets_json` 还原成 `targets`。
- `backend/app/build/plan.py` L174–L192：7 个计数键与 `column_metric_pairs()`。

**边界**：`column_info.table_id`、`column_metric.*` 都只是**逻辑外键**，DDL 中没有 `FOREIGN KEY`。`examples` 是排序后前 10 条，不是完整值域；完整枚举值在 ES。`build_manifest.status` 允许 `success` / `failed`，失败也会留一行用于排查。
