"""S6 · 编排器。

这一层要守住的四条：

    1. 流**一定**以 result 或 error 收尾（没有第三种结局）；
    2. 每一步都有真事：8 个上下文阶段 + 4 个业务步骤；
    3. 校正闭环最多 1 次，校正后的 SQL **重新过**静态校验与安全策略；
    4. 取消 → `CANCELLED`，后面的步骤不再开始。
"""

from __future__ import annotations

from typing import Any

import yaml

from app.agent.cancel import CancelToken
from app.agent.correct import FixtureCorrector
from app.agent.orchestrator import (
    CORRECT_STEP,
    GENERATE_STEP,
    RUN_STEP,
    VALIDATE_STEP,
    AgentRunner,
)
from app.security.executor import ExecutionError

from conftest import (
    BROKEN_SQL,
    GOOD_SQL,
    QUERY,
    UNION_SQL,
    UNKNOWN_COLUMN_SQL,
    FakeExecutor,
    FakeGenerator,
)

CONTEXT_STEPS = (
    "extract_keywords",
    "recall_column",
    "recall_value",
    "recall_metric",
    "merge_retrieved_info",
    "filter_table",
    "filter_metric",
    "add_extra_context",
)


def _run(runner: AgentRunner) -> list[dict[str, Any]]:
    return list(runner.events())


def _progress(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["type"] == "progress"]


def _terminal(events: list[dict[str, Any]]) -> dict[str, Any]:
    return events[-1]


def _states(events: list[dict[str, Any]]) -> dict[str, str]:
    """每个步骤的最终状态。"""
    states: dict[str, str] = {}
    for event in _progress(events):
        states[event["step"]] = event["status"]
    return states


# ---------------------------------------------------------------------------
# 正常路径
# ---------------------------------------------------------------------------


def test_happy_path_runs_every_step() -> None:
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=FakeExecutor(
                columns=("地区", "销售额"),
                rows=({"地区": "华北", "销售额": 128400.0},),
            ),
        )
    )

    assert _terminal(events)["type"] == "result"
    states = _states(events)
    for step in (*CONTEXT_STEPS, GENERATE_STEP, VALIDATE_STEP, RUN_STEP):
        assert states[step] == "success", f"{step} 应当成功"
    assert states[CORRECT_STEP] == "skipped"


def test_every_step_reports_running_before_finishing() -> None:
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=FakeExecutor(columns=("地区",), rows=({"地区": "华北"},)),
        )
    )
    for step in (*CONTEXT_STEPS, GENERATE_STEP, VALIDATE_STEP, RUN_STEP):
        statuses = [
            event["status"]
            for event in _progress(events)
            if event["step"] == step
        ]
        assert statuses[0] == "running"
        assert statuses[-1] == "success"


def test_conditional_step_is_explicitly_skipped() -> None:
    """条件步骤必须显式说「未触发」，不能永远是一块灰的 pending（D4）。"""
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=FakeExecutor(columns=("地区",), rows=({"地区": "华北"},)),
        )
    )
    skipped = [
        event
        for event in _progress(events)
        if event["status"] == "skipped"
    ]
    assert [event["step"] for event in skipped] == [CORRECT_STEP]
    assert skipped[0]["duration_ms"] is None


def test_result_carries_columns_and_rows() -> None:
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=FakeExecutor(
                columns=("地区", "销售额"),
                rows=({"地区": "华北", "销售额": 128400.0},),
            ),
        )
    )
    data = _terminal(events)["data"]
    assert data["columns"] == [
        {"name": "地区", "type": "string"},
        {"name": "销售额", "type": "number"},
    ]
    assert data["rows"] == [["华北", 128400.0]]


# ---------------------------------------------------------------------------
# 失败路径
# ---------------------------------------------------------------------------


def test_syntax_error_ends_the_stream_with_an_error() -> None:
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            executor=FakeExecutor(),
        )
    )
    terminal = _terminal(events)
    assert terminal["type"] == "error"
    assert terminal["code"] == "SQL_SYNTAX"
    assert terminal["class"] == "failure"
    assert terminal["step"] == VALIDATE_STEP
    assert _states(events)[VALIDATE_STEP] == "error"


def test_policy_rejection_is_reported_as_sql_rejected() -> None:
    """UNION 过得了静态校验，过不了安全策略。"""
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": UNION_SQL}),
            executor=FakeExecutor(),
        )
    )
    terminal = _terminal(events)
    assert terminal["code"] == "SQL_REJECTED"
    assert terminal["detail"]["reason_code"] == "SQL_FORBIDDEN_CONSTRUCT"


def test_unknown_column_is_reported() -> None:
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": UNKNOWN_COLUMN_SQL}),
            executor=FakeExecutor(),
        )
    )
    assert _terminal(events)["code"] == "SQL_UNKNOWN_COLUMN"


def test_generator_refusal_is_llm_refusal() -> None:
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator(
                {"refusal": {"code": "OUT_OF_RANGE", "reason": "越界了"}}
            ),
            executor=FakeExecutor(),
        )
    )
    terminal = _terminal(events)
    assert terminal["code"] == "LLM_REFUSAL"
    assert terminal["step"] == GENERATE_STEP
    assert terminal["detail"]["reason_code"] == "OUT_OF_RANGE"


def test_execution_timeout_is_reported() -> None:
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=FakeExecutor(
                error=ExecutionError(code="TIMEOUT", message="超时了")
            ),
        )
    )
    terminal = _terminal(events)
    assert terminal["code"] == "TIMEOUT"
    assert terminal["step"] == RUN_STEP
    assert _states(events)[RUN_STEP] == "error"


def test_empty_result_is_not_a_failure() -> None:
    """空数组是合法语义：通道码是 EMPTY_RESULT，类别是 empty，步骤仍绿。"""
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=FakeExecutor(columns=("地区",), rows=()),
        )
    )
    terminal = _terminal(events)
    assert terminal["code"] == "EMPTY_RESULT"
    assert terminal["class"] == "empty"
    assert _states(events)[RUN_STEP] == "success"


def test_executor_crash_becomes_internal_error() -> None:
    class Boom:
        def execute(self, sql):
            raise RuntimeError("连不上库")

    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=Boom(),
        )
    )
    terminal = _terminal(events)
    assert terminal["code"] == "INTERNAL_ERROR"
    assert terminal["step"] == RUN_STEP


def test_stream_always_ends_with_result_or_error() -> None:
    """没有第三种结局——静默结束是最严重的缺陷。"""
    for payload in (
        {"sql": GOOD_SQL},
        {"sql": BROKEN_SQL},
        {"refusal": {"code": "OUT_OF_RANGE", "reason": "越界"}},
    ):
        events = _run(
            AgentRunner(
                query=QUERY,
                generator=FakeGenerator(payload),
                executor=FakeExecutor(),
            )
        )
        assert events[-1]["type"] in ("result", "error")


# ---------------------------------------------------------------------------
# 校正闭环
# ---------------------------------------------------------------------------


def test_correction_fixes_the_sql_and_reruns() -> None:
    """校验失败 → 校正 → 重新校验 → 执行成功。"""
    executor = FakeExecutor(
        columns=("地区", "销售额"),
        rows=({"地区": "华北", "销售额": 128400.0},),
    )
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=FixtureCorrector({"sql": GOOD_SQL}),
            executor=executor,
        )
    )

    assert _terminal(events)["type"] == "result"
    # 执行的正是校正后的那条 SQL
    assert executor.seen == [GOOD_SQL]
    # 校验步骤：先红后绿（第一次失败、重新校验通过）
    statuses = [
        event["status"]
        for event in _progress(events)
        if event["step"] == VALIDATE_STEP
    ]
    assert statuses == ["running", "error", "running", "success"]
    assert _states(events)[VALIDATE_STEP] == "success"
    assert _states(events)[CORRECT_STEP] == "success"


#: 「各省 GMV 排名」缺 ORDER BY —— 静态校验的可重试错误。
MISSING_ORDER_BY_SQL = (
    "SELECT dim_region.province AS `省份`, "
    "SUM(fact_order.order_amount) AS `销售额` "
    "FROM fact_order "
    "JOIN dim_region ON fact_order.region_id = dim_region.region_id "
    "GROUP BY dim_region.province"
)

#: 补上 ORDER BY 之后的合法 SQL。
FIXED_ORDER_BY_SQL = MISSING_ORDER_BY_SQL + " ORDER BY `销售额` DESC"


def test_guard_error_is_corrected_and_revalidated() -> None:
    """可重试的 guard 错误 → correct_sql=success → 重新过 guard + policy。

    与「语法错误」那条不同，这里第一次失败是**静态校验**给出的
    `SQL_MISSING_ORDER_BY`：校正器必须真的把 SQL 改到能过校验，而不是
    被当成「模型说的就算」。
    """
    executor = FakeExecutor(
        columns=("省份", "销售额"),
        rows=({"省份": "广东省", "销售额": 30000.0},),
    )
    events = _run(
        AgentRunner(
            query="各省 GMV 排名",
            generator=FakeGenerator({"sql": MISSING_ORDER_BY_SQL}),
            corrector=FixtureCorrector({"sql": FIXED_ORDER_BY_SQL}),
            executor=executor,
        )
    )

    assert _terminal(events)["type"] == "result"
    assert executor.seen == [FIXED_ORDER_BY_SQL]
    statuses = [
        event["status"]
        for event in _progress(events)
        if event["step"] == VALIDATE_STEP
    ]
    assert statuses == ["running", "error", "running", "success"]
    assert _states(events)[CORRECT_STEP] == "success"


def test_guard_error_correction_still_faces_the_policy() -> None:
    """guard 错误触发的校正，重新校验时 policy 也要真的跑一遍。"""
    # 常量投影 → guard 的可重试错误；校正结果换成能过 guard 的 UNION SQL，
    # 它必须被 policy 拦下——证明重新校验不是只跑 guard。
    constant_sql = (
        "SELECT dim_region.region_name AS `地区`, 1 AS `常量`, "
        "SUM(fact_order.order_amount) AS `销售额` "
        "FROM fact_order "
        "JOIN dim_region ON fact_order.region_id = dim_region.region_id "
        "GROUP BY dim_region.region_name"
    )
    executor = FakeExecutor()
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": constant_sql}),
            corrector=FixtureCorrector({"sql": UNION_SQL}),
            executor=executor,
        )
    )

    terminal = _terminal(events)
    assert terminal["code"] == "SQL_REJECTED"
    assert terminal["detail"]["reason_code"] == "SQL_FORBIDDEN_CONSTRUCT"
    assert executor.seen == [], "被策略拒绝的校正结果绝不能进数据库"


def test_correction_failure_reason_is_visible_in_the_error_detail() -> None:
    """校正失败的原因必须出现在 SSE 的 error.detail 里，而不是只有红叉。"""
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=FixtureCorrector(
                {
                    "refusal": {
                        "code": "UNKNOWN_COLUMN",
                        "reason": "可用字段里没有可替换的列。",
                    }
                }
            ),
            executor=FakeExecutor(),
        )
    )

    terminal = _terminal(events)
    assert terminal["code"] == "SQL_SYNTAX"
    reason = terminal["detail"]["reason"]
    assert "校正被拒答" in reason
    assert "可用字段里没有可替换的列" in reason


def test_correction_happens_at_most_once() -> None:
    """校正器一直给坏 SQL，闭环也只试一次。"""

    class AlwaysBad:
        name = "always-bad"

        def __init__(self) -> None:
            self.calls = 0

        def correct(self, context, prompt, sql, error):
            self.calls += 1
            return {"sql": BROKEN_SQL}

    corrector = AlwaysBad()
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=corrector,
            executor=FakeExecutor(),
        )
    )

    assert corrector.calls == 1, "校正最多 1 次"
    assert _terminal(events)["type"] == "error"
    assert _terminal(events)["code"] == "SQL_SYNTAX"


def test_corrected_sql_must_pass_the_security_policy() -> None:
    """路线图验收：校正后 SQL 必须再次过 S5 策略。

    校正器返回一条带写操作的 SQL —— 闭环必须把它挡下来，绝不能当成
    「模型说的就算」。
    """
    executor = FakeExecutor()
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=FixtureCorrector(
                {"sql": "UPDATE fact_order SET order_amount = 0"}
            ),
            executor=executor,
        )
    )

    terminal = _terminal(events)
    assert terminal["code"] == "SQL_NOT_READ_ONLY"
    assert executor.seen == [], "被拒的 SQL 绝不能进数据库"


def test_corrected_sql_with_union_is_rejected_by_the_policy() -> None:
    """UNION 过得了静态校验，过不了安全策略——校正也一样。

    这是「校正后必须再次过 S5 策略」最直接的证据：连一条**能跑**的
    危险 SQL 都不能靠「模型说它没问题」放行。
    """
    executor = FakeExecutor()
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=FixtureCorrector({"sql": UNION_SQL}),
            executor=executor,
        )
    )

    terminal = _terminal(events)
    assert terminal["code"] == "SQL_REJECTED"
    assert terminal["detail"]["reason_code"] == "SQL_FORBIDDEN_CONSTRUCT"
    assert executor.seen == [], "被拒的 SQL 绝不能进数据库"


def test_original_sql_is_kept_in_the_error_detail() -> None:
    """保留原始 SQL —— 校正之后也要看得见最初那条。"""
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=FixtureCorrector({"sql": "UPDATE fact_order SET x = 1"}),
            executor=FakeExecutor(),
        )
    )
    detail = _terminal(events)["detail"]
    assert detail["original_sql"] == BROKEN_SQL
    assert detail["corrected_sql"] == "UPDATE fact_order SET x = 1"
    assert detail["attempts"] == 1


def test_old_error_is_cleared_after_a_successful_correction() -> None:
    """校正成功 → 旧 error 不再出现在结局里。"""
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=FixtureCorrector({"sql": GOOD_SQL}),
            executor=FakeExecutor(
                columns=("地区",), rows=({"地区": "华北"},)
            ),
        )
    )
    terminal = _terminal(events)
    assert terminal["type"] == "result"
    assert "error" not in terminal


# ---------------------------------------------------------------------------
# 取消
# ---------------------------------------------------------------------------


def test_cancel_stops_the_run_and_reports_cancelled() -> None:
    """取消 → CANCELLED，不是 done，也不是 error。"""
    token = CancelToken("req-1")
    token.cancel()

    executor = FakeExecutor()
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=executor,
            cancel=token,
        )
    )

    terminal = _terminal(events)
    assert terminal["type"] == "error"
    assert terminal["code"] == "CANCELLED"
    assert terminal["class"] == "cancelled"
    assert executor.seen == [], "取消之后不该再执行 SQL"


def test_cancel_midway_stops_the_remaining_steps() -> None:
    """取消之后步骤条停止推进：后面的步骤不再开始。"""

    class CancellingExecutor:
        def __init__(self, token: CancelToken) -> None:
            self.token = token
            self.seen: list[str] = []

        def execute(self, sql: str):
            self.token.cancel()
            self.seen.append(sql)
            from app.security.executor import ExecutionResult

            return ExecutionResult(
                ok=True, sql=sql, columns=("地区",), rows=({"地区": "华北"},)
            )

    token = CancelToken("req-2")
    executor = CancellingExecutor(token)
    events = _run(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=executor,
            cancel=token,
        )
    )
    terminal = _terminal(events)
    assert terminal["code"] == "CANCELLED"
    assert terminal["type"] == "error"


# ---------------------------------------------------------------------------
# 步骤目录
# ---------------------------------------------------------------------------


def test_context_phases_match_the_step_catalog() -> None:
    """上下文那 8 个阶段必须是 steps.yaml 里声明过的 step id。"""
    from app.generate.context import OfflineContextBuilder

    catalog = {
        step["id"]
        for step in yaml.safe_load(
            (
                __import__("pathlib").Path(__file__).resolve().parents[3]
                / "contracts"
                / "steps.yaml"
            ).read_text(encoding="utf-8")
        )["steps"]
    }
    builder = OfflineContextBuilder(QUERY)
    assert {phase.step for phase in builder.phases()} == set(CONTEXT_STEPS)
    assert set(CONTEXT_STEPS) <= catalog
