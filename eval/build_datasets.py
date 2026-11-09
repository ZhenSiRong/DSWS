#!/usr/bin/env python3
"""WBS 1.2 / 1.3 · 生成一致性测试数据集。

数据来源全部是仓库里已存在的真相源，不新造期望值：

- `backend/tests/recall/golden.yaml`   → 20 条检索问题（layer=retrieval）
- `backend/tests/generate/baseline.yaml` → 10 条生成基线（layer=sql）
- `contracts/errors.yaml`               → retryable / code 的唯一来源

校正用例按 `errors.yaml` 的 retryable 分成：
- `correctable`：guard 级错误，最多校正 1 次，校正后必须重过 guard + policy；
- `non_correctable`：策略/结构级错误，**不进入校正**，直接拒绝。

用法：
    backend/.venv/bin/python eval/build_datasets.py
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def load_yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def build_golden() -> list[dict]:
    recall = load_yaml("backend/tests/recall/golden.yaml")["questions"]
    baseline = load_yaml("backend/tests/generate/baseline.yaml")["questions"]

    rows: list[dict] = []
    for q in recall:
        rows.append({
            "id": f"r-{q['id']}",
            "layer": "retrieval",
            "question": q["question"],
            "expect": {
                "tables": q.get("expected_tables", []),
                "columns": q.get("expected_columns", []),
                "metrics": q.get("expected_metrics", []),
                "values": q.get("expected_values", []),
                "must_not": q.get("must_not", []),
            },
        })
    for q in baseline:
        rows.append({
            "id": f"b-{q['id']}",
            "layer": "sql",
            "question": q["question"],
            "expect": {
                "outcome": q["expect"],
                "sql_contains": q.get("sql_contains", []),
                "sql_not_contains": q.get("sql_not_contains", []),
                "refusal_code": q.get("refusal_code"),
            },
        })
    return rows


CORRECTION = [
    # -- 可校正：列名 ------------------------------------------------------
    {"id": "c01", "category": "列名", "layer": "guard", "sql": "SELECT fact_order.amount FROM fact_order",
     "expect_code": "SQL_UNKNOWN_COLUMN", "expect": "corrected"},
    {"id": "c02", "category": "列名", "layer": "guard",
     "sql": "SELECT SUM(fact_order.order_amount) AS gmv FROM fact_order WHERE fact_order.amount > 100",
     "expect_code": "SQL_UNKNOWN_COLUMN", "expect": "corrected"},
    # -- 可校正：表名 ------------------------------------------------------
    {"id": "c03", "category": "表名", "layer": "guard",
     "sql": "SELECT SUM(fact_sales.order_amount) FROM fact_sales",
     "expect_code": "SQL_UNKNOWN_TABLE", "expect": "corrected"},
    {"id": "c04", "category": "表名", "layer": "guard",
     "sql": "SELECT COUNT(*) FROM fact_order JOIN dim_city ON fact_order.region_id = dim_city.region_id",
     "expect_code": "SQL_UNKNOWN_TABLE", "expect": "corrected"},
    # -- 可校正：语法 ------------------------------------------------------
    {"id": "c05", "category": "语法", "layer": "guard",
     "sql": "SELECT SUM(fact_order.order_amount FROM fact_order",
     "expect_code": "SQL_SYNTAX", "expect": "corrected"},
    {"id": "c06", "category": "语法", "layer": "guard",
     "sql": "SELEC region_name FROM dim_region",
     "expect_code": "SQL_SYNTAX", "expect": "corrected"},
    # -- 可校正：别名 / 结构 ----------------------------------------------
    {"id": "c07", "category": "别名", "layer": "guard",
     "sql": "SELECT SUM(fact_order.order_amount) AS gmv FROM fact_order ORDER BY total_amount",
     "expect_code": "SQL_UNKNOWN_COLUMN", "expect": "corrected"},
    {"id": "c08", "category": "结构", "layer": "guard",
     "sql": "SELECT dim_region.province, SUM(fact_order.order_amount) FROM fact_order JOIN dim_region ON fact_order.region_id = dim_region.region_id GROUP BY dim_region.province",
     "expect_code": "SQL_MISSING_ORDER_BY", "expect": "corrected", "intent": "排名"},
    {"id": "c09", "category": "结构", "layer": "guard",
     "sql": "SELECT dim_region.province, SUM(fact_order.order_amount) FROM fact_order JOIN dim_region ON fact_order.region_id = dim_region.region_id GROUP BY dim_region.province ORDER BY 2 DESC",
     "expect_code": "SQL_MISSING_LIMIT", "expect": "corrected", "intent": "Top 3"},
    {"id": "c10", "category": "结构", "layer": "guard",
     "sql": "SELECT 'placeholder' AS gmv FROM fact_order",
     "expect_code": "SQL_CONSTANT_PROJECTION", "expect": "corrected"},
    # -- 不可校正：不安全构造 ----------------------------------------------
    {"id": "c11", "category": "不安全构造", "layer": "policy",
     "sql": "SELECT order_amount FROM fact_order UNION SELECT customer_id FROM dim_customer",
     "expect_code": "SQL_REJECTED", "expect_reason": "SQL_FORBIDDEN_CONSTRUCT", "expect": "rejected"},
    {"id": "c12", "category": "不安全构造", "layer": "guard",
     "sql": "SELECT 1 AS a FROM fact_order LIMIT 1; DROP TABLE fact_order",
     "expect_code": "SQL_MULTIPLE_STATEMENTS", "expect": "rejected"},
    {"id": "c13", "category": "不安全构造", "layer": "guard",
     "sql": "DELETE FROM fact_order WHERE order_id = 'O001'",
     "expect_code": "SQL_NOT_READ_ONLY", "expect": "rejected"},
    {"id": "c14", "category": "不安全构造", "layer": "policy",
     "sql": "SELECT LOAD_FILE('/etc/passwd') FROM fact_order",
     "expect_code": "SQL_REJECTED", "expect_reason": "SQL_FORBIDDEN_CONSTRUCT", "expect": "rejected"},
    {"id": "c15", "category": "不安全构造", "layer": "policy",
     "sql": "SELECT * FROM mysql.user",
     "expect_code": "SQL_REJECTED", "expect_reason": "SQL_TABLE_NOT_ALLOWED", "expect": "rejected"},
    {"id": "c16", "category": "不安全构造", "layer": "policy",
     "sql": "SELECT /*!50000 order_amount */ FROM fact_order",
     "expect_code": "SQL_REJECTED", "expect_reason": "SQL_COMMENT_OBFUSCATION", "expect": "rejected"},
    {"id": "c17", "category": "不安全构造", "layer": "policy",
     "sql": "SELECT dim_customer.phone FROM dim_customer",
     "expect_code": "SQL_REJECTED", "expect_reason": "SQL_COLUMN_NOT_ALLOWED", "expect": "rejected"},
    # -- 不可校正：结构 ------------------------------------------------
    {"id": "c18", "category": "结构", "layer": "guard", "sql": "   ",
     "expect_code": "SQL_EMPTY", "expect": "rejected"},
    {"id": "c19", "category": "结构", "layer": "guard",
     "sql": "WITH d AS (DELETE FROM fact_order RETURNING order_id) SELECT * FROM d",
     "expect_code": "SQL_NOT_READ_ONLY", "expect": "rejected"},
    {"id": "c20", "category": "结构", "layer": "guard",
     "sql": "SELECT NULL AS gmv FROM fact_order",
     "expect_code": "SQL_CONSTANT_PROJECTION", "expect": "corrected"},
]

CORRECTION_QUERIES = {
    "c01": "华北销售额",
    "c02": "华北销售额",
    "c03": "各品类销售额",
    "c04": "各地区订单量",
    "c05": "各地区销售额",
    "c06": "各省份",
    "c07": "总销售额",
    "c08": "哪个省销量最高",
    "c09": "品牌销售额 Top 3",
    "c10": "总销售额",
    "c11": "用 UNION 拼接两个品类",
    "c12": "华北销售额",
    "c13": "删除订单",
    "c14": "读取文件",
    "c15": "查询用户",
    "c16": "销售额",
    "c17": "客户手机号",
    "c18": "华北销售额",
    "c19": "删除订单",
    "c20": "总销售额",
}

for _case in CORRECTION:
    _case.setdefault("query", CORRECTION_QUERIES.get(_case["id"], "华北销售额"))

LIVE = [
    {"id": "live-01", "question": "查询销售额大于平均销售额的商品", "why": "自然触发校正并成功（已有 SSE 证据）"},
    {"id": "live-02", "question": "哪个商品品类卖得最好", "why": "曾触发校正失败，用于回归"},
    {"id": "live-03", "question": "统计 2025 年第一季度各大区的 GMV", "why": "不应触发校正"},
    {"id": "live-04", "question": "各省 GMV 排名", "why": "排名意图，缺 ORDER BY 应被拦"},
    {"id": "live-05", "question": "品牌销售额 Top 3", "why": "Top-N，缺 LIMIT 应被拦"},
    {"id": "live-06", "question": "用 UNION 把两个品类的销售额拼起来", "why": "策略拒绝，不校正"},
    {"id": "live-07", "question": "各城市销售额", "why": "无 city 粒度，应正确降级或拒答"},
    {"id": "live-08", "question": "2024 年销售额", "why": "越界时间，应显式提示"},
]


def main() -> int:
    golden = build_golden()
    (OUT / "golden.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in golden) + "\n", encoding="utf-8"
    )

    errors = load_yaml("contracts/errors.yaml")["codes"]
    for case in CORRECTION:
        meta = errors.get(case["expect_code"], {})
        case["retryable"] = meta.get("retryable")
        # 契约要求：不可重试的错误绝不进入校正
        if case["expect"] == "rejected" and meta.get("retryable"):
            raise SystemExit(f"{case['id']}: 期望拒绝但契约标记 retryable=true")
        if case["expect"] == "corrected" and not meta.get("retryable"):
            raise SystemExit(f"{case['id']}: 期望校正但契约标记 retryable=false")

    (OUT / "correction.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in CORRECTION) + "\n", encoding="utf-8"
    )
    (OUT / "correction_live.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in LIVE) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "golden": len(golden),
        "golden_by_layer": {k: sum(1 for x in golden if x["layer"] == k) for k in ("retrieval", "sql")},
        "correction": len(CORRECTION),
        "correction_correctable": sum(1 for x in CORRECTION if x["expect"] == "corrected"),
        "correction_rejected": sum(1 for x in CORRECTION if x["expect"] == "rejected"),
        "live": len(LIVE),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
