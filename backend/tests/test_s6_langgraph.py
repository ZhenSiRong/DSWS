"""S6 · LangGraph 接入验收。

这里不测「有没有 import langgraph」，而是测「图是不是真的在跑」：

    1. 编译图的节点集合必须逐字等于 `contracts/steps.yaml` 的 12 个 id；
    2. `validate_sql` 必须有到 `run_sql` / `correct_sql` 的条件分支；
    3. 直接用编译图跑 happy path，12 个节点都要吐出 progress；
    4. `AgentRunner.events()` 跑 happy path，12 个节点都有事件且以 result 收尾；
    5. 校验失败要触发 `correct_sql`（或按 max_attempts 明确 skipped）。

测试只用现有的离线 fake（FakeGenerator / FakeExecutor / FixtureCorrector），
不联网、不依赖 MySQL / ES / Qdrant。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langgraph.graph import END

from app.agent.correct import FixtureCorrector
from app.agent.graph import (
    AGENT_STEP_IDS,
    CORRECT_STEP,
    RUN_STEP,
    VALIDATE_STEP,
    AgentGraphDeps,
    build_agent_graph,
)
from app.agent.orchestrator import AgentRunner
from app.generate.context import OfflineContextBuilder

from tests.agent.conftest import (
    BROKEN_SQL,
    GOOD_SQL,
    QUERY,
    UNION_SQL,
    FakeExecutor,
    FakeGenerator,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_STEPS = [
    step["id"]
    for step in yaml.safe_load(
        (ROOT / "contracts" / "steps.yaml").read_text(encoding="utf-8")
    )["steps"]
]


def _deps(
    *,
    generator: FakeGenerator | None = None,
    corrector: FixtureCorrector | None = None,
    executor: FakeExecutor | None = None,
) -> AgentGraphDeps:
    return AgentGraphDeps(
        query=QUERY,
        builder=OfflineContextBuilder(QUERY),
        executor=executor or FakeExecutor(),
        generator=generator or FakeGenerator({"sql": GOOD_SQL}),
        corrector=corrector,
    )


def _progress(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["type"] == "progress"]


def _states(events: list[dict[str, Any]]) -> dict[str, str]:
    states: dict[str, str] = {}
    for event in _progress(events):
        states[event["step"]] = event["status"]
    return states


# ---------------------------------------------------------------------------
# 图拓扑
# ---------------------------------------------------------------------------


def test_compiled_graph_has_exactly_the_twelve_contract_nodes() -> None:
    graph = build_agent_graph(_deps())
    nodes = {
        name
        for name in graph.get_graph().nodes
        if name not in ("__start__", "__end__")
    }

    assert tuple(CONTRACT_STEPS) == AGENT_STEP_IDS, (
        "graph.py 里的节点 id 与 contracts/steps.yaml 不一致"
    )
    assert nodes == set(CONTRACT_STEPS)
    assert len(nodes) == 12


def test_validate_sql_has_branches_to_run_and_correct() -> None:
    graph = build_agent_graph(_deps())
    edges = [
        edge
        for edge in graph.get_graph().edges
        if edge.source == VALIDATE_STEP and edge.conditional
    ]
    targets = {edge.target for edge in edges}

    assert RUN_STEP in targets, "校验通过必须能走 run_sql"
    assert CORRECT_STEP in targets, "可重试失败必须能走 correct_sql"
    assert END in targets, "不可重试 / 超次时必须能结束（错误路径）"


def test_correct_sql_loops_back_to_validate_and_run_ends() -> None:
    graph = build_agent_graph(_deps())
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}

    assert (CORRECT_STEP, VALIDATE_STEP) in edges, "校正后必须重新校验"
    assert (RUN_STEP, END) in edges, "执行完必须结束"


# ---------------------------------------------------------------------------
# 图本身真的会执行
# ---------------------------------------------------------------------------


def test_compiled_graph_streams_progress_for_all_twelve_nodes() -> None:
    """不经过 AgentRunner，直接跑图：12 个节点都要真的被走到。"""
    graph = build_agent_graph(
        _deps(
            executor=FakeExecutor(
                columns=("地区", "销售额"),
                rows=({"地区": "华北", "销售额": 128400.0},),
            )
        )
    )

    progress: list[dict[str, Any]] = []
    final_state: dict[str, Any] = {}
    for mode, chunk in graph.stream(
        {"query": QUERY},
        stream_mode=["custom", "values"],
    ):
        if mode == "custom":
            progress.append(chunk)
        else:
            final_state = chunk

    assert {event["step"] for event in progress} == set(CONTRACT_STEPS)
    assert final_state["execution"].ok is True
    assert final_state["sql"] == GOOD_SQL


# ---------------------------------------------------------------------------
# AgentRunner：图 → SSE
# ---------------------------------------------------------------------------


def test_happy_path_emits_every_node_and_ends_with_result() -> None:
    events = list(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": GOOD_SQL}),
            executor=FakeExecutor(
                columns=("地区", "销售额"),
                rows=({"地区": "华北", "销售额": 128400.0},),
            ),
        ).events()
    )

    assert events[-1]["type"] == "result"
    steps = {event["step"] for event in _progress(events)}
    assert steps == set(CONTRACT_STEPS)
    # 非条件节点必须有 running；correct_sql 在 happy path 里显式 skipped，
    # 也必须有一条属于它的 progress 事件。
    for step in CONTRACT_STEPS:
        if step == CORRECT_STEP:
            continue
        assert any(
            event["step"] == step and event["status"] == "running"
            for event in _progress(events)
        ), f"{step} 没有 running 事件"
    assert _states(events)[CORRECT_STEP] == "skipped"


def test_validation_failure_triggers_correct_sql_and_result() -> None:
    """校验失败 → correct_sql（running/success）→ 重新校验 → 执行成功。"""
    executor = FakeExecutor(
        columns=("地区", "销售额"),
        rows=({"地区": "华北", "销售额": 128400.0},),
    )
    events = list(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            corrector=FixtureCorrector({"sql": GOOD_SQL}),
            executor=executor,
        ).events()
    )

    assert events[-1]["type"] == "result"
    assert executor.seen == [GOOD_SQL], "执行的必须是重新校验过的校正 SQL"
    correct_statuses = [
        event["status"]
        for event in _progress(events)
        if event["step"] == CORRECT_STEP
    ]
    assert correct_statuses == ["running", "success"]

    validate_statuses = [
        event["status"]
        for event in _progress(events)
        if event["step"] == VALIDATE_STEP
    ]
    assert validate_statuses == ["running", "error", "running", "success"]


def test_non_retryable_failure_skips_correct_sql() -> None:
    """安全策略拒绝不可重试：correct_sql 必须显式 skipped，而不是灰着。"""
    events = list(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": UNION_SQL}),
            executor=FakeExecutor(),
        ).events()
    )

    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "SQL_REJECTED"
    assert _states(events)[VALIDATE_STEP] == "error"
    assert _states(events)[CORRECT_STEP] == "skipped"


def test_retryable_failure_without_corrector_visits_correct_sql() -> None:
    """可重试失败即使没有校正器也会进入 correct_sql，并在那里给出 error。"""
    events = list(
        AgentRunner(
            query=QUERY,
            generator=FakeGenerator({"sql": BROKEN_SQL}),
            executor=FakeExecutor(),
        ).events()
    )

    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "SQL_SYNTAX"
    correct_statuses = [
        event["status"]
        for event in _progress(events)
        if event["step"] == CORRECT_STEP
    ]
    assert correct_statuses == ["running", "error"]
