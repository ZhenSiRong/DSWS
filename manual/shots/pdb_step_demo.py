#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 教师/CI 夹具：不是学生入口；学生工具见 manual/appendix/gui-debugging.md
"""离线 pdb 单步演示（第 21 页补图用）。

只跑**真代码路径**：
    check_sql（guard 静态校验）→ validate_sql（guard + policy 两道关）
    → propose_correction（触发条件 + 校正 + 契约校验）
    → validate_sql（二次校验）→ run_sql 的边界

只替换两样外部依赖（与 `backend/tests/agent/conftest.py` 同一套思路）：
    - 模型：假生成器返回一段固定 JSON **文本**，文本仍走真的
      `parse_model_payload` 解析；
    - 数据库：假执行器返回固定行，不连 MySQL。
不读 .env、不连网络、不启容器、不碰 ES / Qdrant。

跑法（在仓库根目录，用现成的 backend/.venv，Python 3.14）：

    backend/.venv/bin/python -m pdb manual/shots/pdb_step_demo.py

进 pdb 后按 `manual/review/pdb-step-runbook.md` 的断点命令敲，
或直接跑 `python3 manual/shots/render_pdb_step.py` 自动重录 transcript。
想手动随手单步，也可以在 main() 开头取消注释 `breakpoint()`。

脚本会打印 `=== NODE validate_sql ===` 之类的分段标记；
`render_pdb_step.py` 用这些标记驱动左栏 12 节点时间轴高亮。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.agent.correct import (  # noqa: E402
    FixtureCorrector,
    LlmCorrector,
    propose_correction,
)
from app.agent.errors import build_error, load_error_table  # noqa: E402
from app.agent.validate import validate_sql  # noqa: E402
from app.generate.context import build_offline_context  # noqa: E402
from app.generate.guard import check_sql  # noqa: E402
from app.generate.provider import parse_model_payload  # noqa: E402
from app.security.executor import ExecutionResult  # noqa: E402

#: 与 `backend/tests/agent/conftest.py` 的 QUERY / UNKNOWN_COLUMN_SQL /
#: GOOD_SQL 逐字一致——这样图和 pytest 断言的是同一组输入。
QUERY = "华北销售额"

#: 引用了「华北销售额」离线上下文里不存在的列。
SQL_BEFORE = (
    "SELECT dim_region.no_such_column AS `地区` "
    "FROM fact_order "
    "JOIN dim_region ON fact_order.region_id = dim_region.region_id"
)

#: 校正后的合法 SQL（把 no_such_column 换成 region_name）。
SQL_AFTER = (
    "SELECT dim_region.region_name AS `地区`, "
    "SUM(fact_order.order_amount) AS `销售额` "
    "FROM fact_order "
    "JOIN dim_region ON fact_order.region_id = dim_region.region_id "
    "GROUP BY dim_region.region_name"
)

#: 假模型「返回」的原文：故意裹一层 ```json 代码块，让 parse_model_payload
#: 真的走一遍剥壳 + json.loads（模型常这么干，解析器必须兜住）。
MODEL_TEXT = '```json\n{"sql": "' + SQL_AFTER + '"}\n```'

#: 假执行器的固定结果（不连 MySQL）。
ROWS = ({"地区": "华北", "销售额": 128400.0},)


class FakeGenerator:
    """假模型：返回固定文本，但解析走真解析器（不是手写 dict）。"""

    name = "fake-llm"

    def __init__(self, model_text: str) -> None:
        self._model_text = model_text

    def generate(self, context, prompt):  # noqa: ARG002 - 接口形状与真生成器一致
        return parse_model_payload(self._model_text)


class FakeExecutor:
    """假数据库执行器：返回固定行，不连 MySQL。"""

    name = "fake-db"

    def execute(self, sql: str) -> ExecutionResult:
        return ExecutionResult(
            ok=True,
            sql=sql,
            rows=ROWS,
            columns=("地区", "销售额"),
        )


def mark(node: str) -> None:
    """左栏时间轴的分段标记（render_pdb_step.py 靠这一行切换高亮）。"""
    print(f"=== NODE {node} ===", flush=True)


def main() -> None:
    # 想手动单步时取消下面这行注释（自动重录 transcript 时不要开）。
    # breakpoint()

    context = build_offline_context(QUERY)
    sql_before = SQL_BEFORE
    policy = load_error_table().correction
    attempts = 0

    mark("validate_sql")
    report = check_sql(sql_before, context, QUERY)
    print(f"guard.check_sql -> ok={report.ok} 违规={len(report.violations)} 条")
    print(f"  首条违规 = {report.violations[0].code} · {report.violations[0].message}")
    error = validate_sql(sql_before, context, QUERY)
    print(f"validate_sql -> error.code={error.code} retryable={error.retryable}")

    mark("correct_sql")
    print(f"契约 correction -> max_attempts={policy.max_attempts} revalidate={policy.revalidate}")

    no_corrector = propose_correction(context, sql_before, error, corrector=None)
    print(f"触发条件① corrector=None -> attempted={no_corrector.attempted} note={no_corrector.note}")

    rejected = build_error("SQL_REJECTED", "被安全策略拒绝", reason_code="SQL_NOT_READ_ONLY")
    not_retryable = propose_correction(
        context,
        sql_before,
        rejected,
        corrector=FixtureCorrector({"sql": SQL_AFTER}),
    )
    print(f"触发条件② code={rejected.code} -> attempted={not_retryable.attempted} note={not_retryable.note}")

    fake_llm = FakeGenerator(MODEL_TEXT)
    proposal = propose_correction(context, sql_before, error, corrector=LlmCorrector(fake_llm))
    attempts = attempts + 1
    sql_after = proposal.sql
    print(f"触发条件③ 全满足 -> attempted={proposal.attempted} ok={proposal.ok} attempts={attempts}/{policy.max_attempts}")
    print(f"候选 sql_after = {sql_after}")

    mark("validate_sql")
    revalidated = validate_sql(sql_after, context, QUERY)
    print(f"二次 validate_sql -> error={revalidated}")

    mark("run_sql")
    result = FakeExecutor().execute(sql_after)
    print(f"run_sql（假执行器，不连 MySQL）-> ok={result.ok} rows={result.rows}")
    print("=== DONE · 演示结束（真代码路径 / 假模型 + 假数据库）===")


if __name__ == "__main__":
    main()
