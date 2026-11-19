# fixtures/dw-real — 第二数据集（L2 / P10「换真数据」用）

## 这是什么
- 与 `fixtures/dw.sql` **同结构**的「甲方真实数据」：5 张表 / 24 列 / 同列名同类型；
  规模 `dim_region 7 · dim_customer 20 · dim_product 15 · dim_date 1461 · fact_order 410`。
- 比演示集「真」在：日期跨 **2023–2026**、金额带分（两位小数）、日期维是连续日历，
  且故意内置 **5 类脏数据（D1–D5）+ 2 项附加异常（D6/D7）**。
- AS-OF = **2026-11-19（20261119）**：未来日期判定与清洗窗口上界都用这个冻结值，
  SQL 不写 `CURDATE()`，保证任何一天重跑都能复算。
- 导入：`mysql --default-character-set=utf8mb4 < fixtures/dw-real.sql`（文件内含 `CREATE DATABASE dw`）。
  建议导进独立实例（验证用端口 3310 的临时容器），别覆盖项目演示库。
- 配套文件：`dw-real.expected.json`（42 项对账真值，每项自带可重跑的 `sql`）、
  `dw-real.checks.sql`（一键输出 5 类计数 + 清洗后对账表）、本 README。

## 5 类脏数据 + 2 项附加异常（行内以 `-- [Dx]` 标注）
- **D1** `fact_order.order_amount` 为 NULL，2 行 → `SUM` 漏、`COUNT(*)` 多（`COUNT(order_amount)` 只有 408）。
- **D2** `order_id` 重复 1 对（`ORD20261119001`，2 行逐列相同，多 1 行）→ naive SUM 多算 5197.40；去重会少。
- **D3** `dim_region.region_name` 带「区」后缀各 1 行（R002=华东区、R004=华北区）→
  按契约枚举过滤只剩 279 行 / 789027.50（少了 129 行）。
- **D4** 1 行 `region_id=R099` 孤儿行（dim_region 无此 id，金额 1798.00）→ 内连接静默丢。
- **D5** 日期跨 2023–2026，且有 1 行未来日期 2026-12-15（金额 1399.00）→ 时间过滤会变。
- **D6**（附加）`dim_region` 同名 province=北京市 两行（R004、R007）→ 按 province 连接放大：
  496 行 / 1359154.30（正确 405 行 / 1136341.10）。
- **D7**（附加）金额带分：191 行非整数金额 → 必须按 `DECIMAL(16,2)` 语义处理。
> 注：题面「5 类脏数据」= D1–D5；D6/D7 是同批要求里的附加异常，对账时必须一起处理。

## 清洗规则（可执行成 SQL，见 checks.sql / expected.json 的 cleaning_rules）
- R1 去重：`SELECT DISTINCT` 7 列（同一 order_id 留 1 行）
- R2 剔金额缺失：`WHERE order_amount IS NOT NULL`
- R3 时间上界：`WHERE date_id <= 20261119`
- R4 剔孤儿：`INNER JOIN dim_region r ON r.region_id = order.region_id`
- R5 地区名归一：`TRIM(TRAILING '区' FROM r.region_name)`（华北区→华北、华东区→华东）
- R6 维度只按 `region_id` 关联（不要按 province/region_name，否则 D6 放大）
- R7 金额逐值 `CAST(order_amount AS DECIMAL(16,2))` 后再 `SUM`
- R8 单数用 `COUNT(DISTINCT order_id)`（清洗后应与行数相等，都是 405）

## 对账真值摘要（expected.json 由真实导入 MySQL 8.0 后实跑 SQL 生成，非手算）
- 原始装数：dim_region 7 / dim_customer 20 / dim_product 15 / dim_date 1461 / fact_order 410；
  naive SUM（不洗不筛）= **1144735.50**（重复 +1 份、孤儿、未来单都在里面，NULL 被跳过）。
- 清洗后：**405 行 / 405 单 / 1136341.10**；华北 **91 单 / 222813.20**。
- 按 region（orders/sales）：华东 130/325179.80 · 华中 45/174373.40 · 华北 91/222813.20 ·
  华南 87/261231.60 · 西南 52/152743.10。
- 自检：`mysql --default-character-set=utf8mb4 < fixtures/dw-real.checks.sql`；输出应与 expected.json 一致。

## 与 fixtures/dw.sql 的差异
- 数据：115 → 410 行；2025Q1 → 2023–2026；整数金额 → 带分；日期维 90 → 1461 行。
- 结构：5 个 `CREATE TABLE` 块与 dw.sql **逐字相同**（24 列、主外键语义不变）。唯一差异是装载期一句
  `ALTER TABLE fact_order DROP PRIMARY KEY, ADD KEY ...`：重复 order_id（D2）在 PRIMARY KEY 下装不进，
  模拟「源系统导出不保证约束」；不装载重复行就没法演示 D2。
- 去掉了 dw.sql 里那条 `GRANT ... TO '<账号>'`（数据集文件内不出现账号/密码）。

## 教学用途（P10）
- 「找到替身」：dw.sql = 115 行干净替身；dw-real.sql = 甲方脏数据。
- 「换真件」：替换数据源 → 同一句 `SELECT SUM(order_amount) FROM fact_order` 立刻从真值变错数；
  再按 R1–R8 清洗回 1136341.10，体会「同一判据仍绿」。
- 判据：`dw-real.checks.sql` 的 5 类计数 + 对账表；`expected.json` 是机器可复算真值（42 项，
  每项 `sql` 可单独重跑，金额按 DECIMAL 比）。实测 mysql:8.0.46 临时容器 **42/42 PASS**。
