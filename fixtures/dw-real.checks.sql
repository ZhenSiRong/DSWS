-- fixtures/dw-real.checks.sql
-- 第二数据集 dw-real 的对账自检：先输出 5 类脏数据计数，再输出清洗后对账表。
--
-- 前置：fixtures/dw-real.sql 已导入（库名 dw）。
-- 运行：mysql --default-character-set=utf8mb4 < fixtures/dw-real.checks.sql
-- 口径：AS-OF = 2026-11-19（20261119，冻结值）；金额 DECIMAL(16,2)；日期 yyyyMMdd 整数。
-- 对照真值：fixtures/dw-real.expected.json（本文件输出应与其中每个 value 一致）。

SET NAMES utf8mb4;
USE dw;
SET @as_of := 20261119;

-- =====================================================================
-- 1. 5 类脏数据计数（D1–D5；判定 SQL 与 expected.json 一致）
-- =====================================================================

-- D1  order_amount 为 NULL（2 行）：SUM 会漏，COUNT 会多
SELECT 'D1' AS id, 'order_amount 为 NULL' AS dirty_class, COUNT(*) AS rows_hit
FROM fact_order
WHERE order_amount IS NULL;

-- D2  order_id 重复（1 对重复行 = 2 行，多 1 行）
SELECT 'D2' AS id, 'order_id 重复' AS dirty_class,
       SUM(c)     AS rows_hit,
       SUM(c) - 1 AS extra_rows
FROM (SELECT COUNT(*) AS c
      FROM fact_order
      GROUP BY order_id
      HAVING COUNT(*) > 1) t;

-- D3  dim_region.region_name 带后缀脏值（华北区 / 华东区，各 1 行）
SELECT 'D3' AS id, 'region_name 带“区”后缀' AS dirty_class,
       COUNT(*) AS rows_hit,
       GROUP_CONCAT(region_name ORDER BY region_id SEPARATOR ',') AS dirty_values
FROM dim_region
WHERE region_name LIKE '%区';

-- D4  region_id 孤儿行（dim_region 中不存在）——内连接会丢
SELECT 'D4' AS id, 'region_id 孤儿行' AS dirty_class, COUNT(*) AS rows_hit
FROM fact_order f
LEFT JOIN dim_region r ON r.region_id = f.region_id
WHERE r.region_id IS NULL;

-- D5  未来日期行（date_id > AS-OF）——时间过滤会变
SELECT 'D5' AS id, '未来日期行' AS dirty_class, COUNT(*) AS rows_hit
FROM fact_order
WHERE date_id > @as_of;

-- D5 附：真实数据的日期跨度（2023–2026，比演示集宽）
SELECT MIN(date_id) AS date_min,
       MAX(date_id) AS date_max,
       COUNT(DISTINCT date_id DIV 10000) AS distinct_years
FROM fact_order;

-- =====================================================================
-- 2. 清洗后对账（R1–R8；规则说明见 fixtures/dw-real.README.md）
-- =====================================================================
DROP TEMPORARY TABLE IF EXISTS tmp_clean_fact;
CREATE TEMPORARY TABLE tmp_clean_fact AS
WITH dedup AS (                                -- R1 同一 order_id 只留 1 行（重复行逐列相同）
    SELECT DISTINCT order_id, customer_id, product_id, date_id,
                    region_id, order_quantity, order_amount
    FROM fact_order
),
clean AS (
    SELECT d.order_id,
           d.date_id,
           d.region_id,
           d.order_quantity,
           CAST(d.order_amount AS DECIMAL(16,2)) AS order_amount,   -- R7 金额按 DECIMAL 聚合
           TRIM(TRAILING '区' FROM r.region_name) AS region_name    -- R5 地区名归一化：华北区→华北
    FROM dedup d
    JOIN dim_region r ON r.region_id = d.region_id                 -- R4 内连接过滤孤儿行；R6 只按 region_id 关联
    WHERE d.order_amount IS NOT NULL                               -- R2 剔除金额缺失
      AND d.date_id <= @as_of                                      -- R3 时间上界 = AS-OF
)
SELECT * FROM clean;

-- 2.1 清洗后总览：有效行数 / 单数 / 总销售额
SELECT COUNT(*)                       AS clean_rows,
       COUNT(DISTINCT order_id)       AS clean_orders,
       CAST(SUM(order_amount) AS DECIMAL(16,2)) AS total_sales
FROM tmp_clean_fact;

-- 2.2 清洗后对账表：region_name, orders, sales
SELECT region_name,
       COUNT(DISTINCT order_id) AS orders,
       CAST(SUM(order_amount) AS DECIMAL(16,2)) AS sales
FROM tmp_clean_fact
GROUP BY region_name
ORDER BY region_name;

-- =====================================================================
-- 3. 附：附加异常 D6/D7、原始装数与 naive 对照（不参与上面的清洗口径）
-- =====================================================================

-- D6  dim_region 同名(province=北京市)两行、不同 id：JOIN 会放大
SELECT 'D6' AS id, 'dim_region 同名(province)重复' AS anomaly,
       COUNT(*)     AS duplicate_groups,
       SUM(c) - 1   AS extra_rows
FROM (SELECT COUNT(*) AS c
      FROM dim_region
      GROUP BY province
      HAVING COUNT(*) > 1) t;

-- D6 放大演示：按 province 自然键连接（错误写法）→ 行数与金额都被放大
SELECT COUNT(*) AS wrong_join_rows,
       CAST(SUM(f.order_amount) AS DECIMAL(16,2)) AS wrong_join_sales
FROM tmp_clean_fact f
JOIN dim_region d1 ON d1.region_id = f.region_id
JOIN dim_region d2 ON d2.province  = d1.province;

-- D7  金额带分（两位小数）：与 dw.sql 的整数金额不同
SELECT 'D7' AS id, '金额带分（非整数金额）' AS anomaly,
       COUNT(*) AS rows_with_nonzero_cents
FROM fact_order
WHERE order_amount IS NOT NULL
  AND order_amount <> ROUND(order_amount, 0);

-- 原始装数 + naive 对照（naive = 不洗不筛直接 SUM，仅跳过 NULL）
SELECT seq, item, n FROM (
    SELECT 1 AS seq, 'dim_region 行数'          AS item, COUNT(*) AS n FROM dim_region
    UNION ALL SELECT 2, 'dim_customer 行数',            COUNT(*) FROM dim_customer
    UNION ALL SELECT 3, 'dim_product 行数',             COUNT(*) FROM dim_product
    UNION ALL SELECT 4, 'dim_date 行数',                COUNT(*) FROM dim_date
    UNION ALL SELECT 5, 'fact_order 原始行数',          COUNT(*) FROM fact_order
    UNION ALL SELECT 6, '不同 order_id 数',             COUNT(DISTINCT order_id) FROM fact_order
    UNION ALL SELECT 7, '非空 order_amount 行数',       COUNT(order_amount) FROM fact_order
) t
ORDER BY seq;

SELECT CAST(SUM(CAST(order_amount AS DECIMAL(16,2))) AS DECIMAL(16,2)) AS naive_sum_amount
FROM fact_order;

DROP TEMPORARY TABLE IF EXISTS tmp_clean_fact;
