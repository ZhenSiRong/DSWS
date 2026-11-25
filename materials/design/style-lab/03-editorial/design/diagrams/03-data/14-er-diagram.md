# 14 · 数仓 ER 图（5 表）

**一句话**：数仓只有 5 张表；4 张维度表各由主键唯一确定一行，`fact_order` 一行一单，四个 `*_id` 是指向维度的逻辑外键。

**这张图回答**：每张表一行代表什么？主键是什么？事实表如何关联维度？哪些列是真实存在、哪些是常见误问（`city`、`price`）？

**图例**：蓝色=契约与事实源；`PK`=主键，`FK`=逻辑外键；属性后的引号是粒度说明，不是物理约束。

**关键元素**：
- `dim_region`：`region_id` 主键；`region_name` 是大区（省的上级分组），**不是唯一键**；本表没有 `city` 列。
- `dim_customer`：`customer_id` 主键。
- `dim_product`：`product_id` 主键；本表没有 `price` 列，金额只在 `fact_order.order_amount`。
- `dim_date`：`date_id` 主键，一行一天，`yyyyMMdd`。
- `fact_order`：`order_id` 主键，**一行一单**；`order_quantity` 是单内件数，`order_amount` 是整单金额。
- 四条逻辑外键：`customer_id`、`product_id`、`date_id`、`region_id`。

**证据**：
- `contracts/schema.contract.yaml` L26–L399：5 表、主键、`grain`、`foreign_keys`。
- `fixtures/dw.sql` L13–L323：物理 DDL 与 115 行订单数据。
- `design/inventory/facts.md` L69–L88：表粒度与外键清单。

**边界**：外键是**逻辑**关系，DDL 中没有 `FOREIGN KEY` 约束；图中不声称数据库会强制引用完整性。列类型在图中简写为 `varchar/int/float`，精确类型（如 `VARCHAR(20)`、`FLOAT`）以契约与 DDL 为准。
