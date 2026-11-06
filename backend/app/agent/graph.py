"""S6 · LangGraph 图编排。

这里把一次问数做成一张**真的会被执行的图**，而不是「顺手画一张图」：

    START
      -> extract_keywords -> recall_column -> recall_value -> recall_metric
      -> merge_retrieved_info -> filter_table -> filter_metric
      -> add_extra_context -> generate_sql -> validate_sql
                                              |-- 通过 -----------> run_sql -> END
                                              |-- 可重试且未超次 --> correct_sql
                                              |                     |
                                              |                     v
                                              |                 validate_sql（重新校验）
                                              `-- 否则 -----------> END（错误路径）

节点 id 逐字来自 `contracts/steps.yaml`。8 个上下文节点调用
`OfflineContextBuilder.phases()` 的**同一个阶段对象**；`generate_sql`
调用 S4 的 `draft_sql`；`validate_sql` 调用 S6 的 `validate_sql`；
`correct_sql` 调用 `propose_correction`；`run_sql` 调用注入的执行器。

事件怎么来：节点里用 LangGraph 的 `get_stream_writer()` 发 progress，
`AgentRunner` 只负责把图吐出来的事件转成 SSE。因此屏幕上的每一步都对应
图里真的跑过的一个节点，**没有「先发事件、再假装做事」的节点**。

图只在「正常结束」时把状态交回编排器（`run_sql` 之后，或 `validate_sql`
不可重试/超过重试次数时走 END）。取消、上下文阶段异常、生成阶段异常、
生成拒答、校正失败这些**提前终止**，用异常把图停下来，由编排器统一补上
`correct_sql` 的显式 skipped 和最终的 error 事件——语义与手写循环时一致。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.agent.cancel import CancelToken
from app.agent.correct import (
    CorrectionProposal,
    SqlCorrector,
    propose_correction,
)
from app.agent.errors import (
    INTERNAL_ERROR,
    LLM_REFUSAL,
    ChannelError,
    ErrorTable,
    build_error,
    decorate_error,
    load_error_table,
)
from app.agent.validate import DEFAULT_GATES, validate_sql
from app.generate.context import OfflineContextBuilder
from app.generate.models import GenerateContext
from app.generate.pipeline import draft_sql
from app.generate.provider import SqlGenerator
from app.security.executor import ExecutionResult

# 步骤 id（逐字来自 contracts/steps.yaml）
EXTRACT_KEYWORDS_STEP = "extract_keywords"
RECALL_COLUMN_STEP = "recall_column"
RECALL_VALUE_STEP = "recall_value"
RECALL_METRIC_STEP = "recall_metric"
MERGE_RETRIEVED_INFO_STEP = "merge_retrieved_info"
FILTER_TABLE_STEP = "filter_table"
FILTER_METRIC_STEP = "filter_metric"
ADD_EXTRA_CONTEXT_STEP = "add_extra_context"
GENERATE_STEP = "generate_sql"
VALIDATE_STEP = "validate_sql"
CORRECT_STEP = "correct_sql"
RUN_STEP = "run_sql"

#: 8 个上下文阶段的顺序（与 steps.yaml 一致）。
CONTEXT_STEPS: tuple[str, ...] = (
    EXTRACT_KEYWORDS_STEP,
    RECALL_COLUMN_STEP,
    RECALL_VALUE_STEP,
    RECALL_METRIC_STEP,
    MERGE_RETRIEVED_INFO_STEP,
    FILTER_TABLE_STEP,
    FILTER_METRIC_STEP,
    ADD_EXTRA_CONTEXT_STEP,
)

#: 12 个节点 id（与 contracts/steps.yaml 完全一致）。
AGENT_STEP_IDS: tuple[str, ...] = (
    *CONTEXT_STEPS,
    GENERATE_STEP,
    VALIDATE_STEP,
    CORRECT_STEP,
    RUN_STEP,
)


class SqlExecutor(Protocol):
    """执行器接口。S5 的 `ReadOnlyExecutor` 就是它。"""

    def execute(self, sql: str) -> ExecutionResult:
        ...


class AgentState(TypedDict, total=False):
    """图里流动的状态。

    `failure` 是最近一次校验失败；`execution` 是执行器的原始结果。
    最终是 `result` 还是 `error` 由编排器根据这两个字段决定——图只负责
    把「事情真的做完」。
    """

    query: str
    context: GenerateContext
    sql: str
    original_sql: str
    corrected_sql: str | None
    attempts: int
    correction_attempted: bool
    failure: ChannelError | None
    execution: ExecutionResult


class GraphHalt(Exception):
    """节点主动终止图，并带上最终的通道错误。

    用于那些「不该再往下走」的路径：上下文阶段异常、生成异常/拒答、
    校正失败。图会立刻停下，编排器负责补上收尾事件。
    """

    def __init__(self, error: ChannelError) -> None:
        super().__init__(error.message)
        self.error = error


class GraphCancelled(Exception):
    """用户取消：图在下一个节点边界停下。"""


@dataclass(frozen=True)
class AgentGraphDeps:
    """构建图所需的全部依赖。

    依赖全部注入，所以整张图可以离线跑：只把 LLM 与 MySQL 换成 fake，
    图、校验、策略、事件一行都不改。
    """

    query: str
    builder: OfflineContextBuilder
    executor: SqlExecutor
    generator: SqlGenerator | None = None
    corrector: SqlCorrector | None = None
    now: datetime | None = None
    table: ErrorTable = field(default_factory=load_error_table)
    cancel: CancelToken | None = None
    request_id: str | None = None

    @property
    def max_attempts(self) -> int:
        """校正次数上限只从错误码表里读，不在代码里写死。"""
        return self.table.correction.max_attempts


# ---------------------------------------------------------------------------
# 事件工具
# ---------------------------------------------------------------------------


def _progress(
    step: str,
    status: str,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "type": "progress",
        "step": step,
        "status": status,
        "duration_ms": duration_ms,
    }


def _emit(event: dict[str, Any]) -> None:
    """把事件写进 LangGraph 的 custom 流。

    `AgentRunner` 用 `stream_mode=["custom", "values"]` 消费它，所以事件是
    节点执行**当时**发出来的，不是图跑完之后补出来的。
    """
    get_stream_writer()(event)


def _elapsed(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _ensure_not_cancelled(deps: AgentGraphDeps) -> None:
    if deps.cancel is not None and deps.cancel.cancelled:
        raise GraphCancelled


# ---------------------------------------------------------------------------
# 节点
# ---------------------------------------------------------------------------


def _context_node(step: str, phase: Any, deps: AgentGraphDeps):
    """8 个上下文节点：每个节点跑 `phases()` 里对应的那一件真事。"""

    def node(state: AgentState) -> dict[str, Any]:
        _ensure_not_cancelled(deps)
        _emit(_progress(step, "running"))
        started = time.perf_counter()
        try:
            phase.run()
        except Exception as exc:  # noqa: BLE001 - 失败必须有名字
            _emit(_progress(step, "error", _elapsed(started)))
            raise GraphHalt(
                build_error(
                    INTERNAL_ERROR,
                    f"步骤「{step}」执行失败：{exc}",
                    step=step,
                    request_id=deps.request_id,
                )
            ) from exc
        _emit(_progress(step, "success", _elapsed(started)))
        return {}

    node.__name__ = f"node_{step}"
    return node


def _generate_node(deps: AgentGraphDeps):
    def node(state: AgentState) -> dict[str, Any]:
        # 取消检查点与手写编排保持一致：上下文阶段之后、生成之前不查；
        # 取消发生在生成期间时，由下一步 validate_sql 的检查拦住。
        _emit(_progress(GENERATE_STEP, "running"))
        started = time.perf_counter()
        try:
            draft = draft_sql(
                deps.query,
                context=deps.builder.result(),
                generator=deps.generator,
                now=deps.now,
            )
        except Exception as exc:  # noqa: BLE001 - 生成失败也是一种有名字的失败
            _emit(_progress(GENERATE_STEP, "error", _elapsed(started)))
            raise GraphHalt(
                build_error(
                    INTERNAL_ERROR,
                    f"生成阶段失败：{exc}",
                    step=GENERATE_STEP,
                )
            ) from exc

        if draft.refusal is not None:
            _emit(_progress(GENERATE_STEP, "error", _elapsed(started)))
            raise GraphHalt(
                build_error(
                    LLM_REFUSAL,
                    draft.refusal.reason,
                    step=GENERATE_STEP,
                    reason_code=draft.refusal.code,
                    request_id=deps.request_id,
                )
            )

        _emit(_progress(GENERATE_STEP, "success", _elapsed(started)))
        sql = draft.sql or ""
        return {
            "context": draft.context,
            "sql": sql,
            "original_sql": sql,
            "corrected_sql": None,
            "attempts": 0,
            "correction_attempted": False,
            "failure": None,
        }

    return node


def _validate_node(deps: AgentGraphDeps):
    def node(state: AgentState) -> dict[str, Any]:
        _ensure_not_cancelled(deps)
        _emit(_progress(VALIDATE_STEP, "running"))
        started = time.perf_counter()
        failure = validate_sql(
            state["sql"],
            state["context"],
            deps.query,
            gates=DEFAULT_GATES,
        )
        elapsed = _elapsed(started)

        if failure is None:
            _emit(_progress(VALIDATE_STEP, "success", elapsed))
            if not state.get("correction_attempted"):
                # 条件步骤必须**显式**说「未触发」，不能永远是一块灰的
                # pending（审计 D4）。
                _emit(_progress(CORRECT_STEP, "skipped"))
            return {"failure": None}

        _emit(_progress(VALIDATE_STEP, "error", elapsed))
        return {"failure": failure}

    return node


def _route_after_validate(deps: AgentGraphDeps):
    """`validate_sql` 的条件边：通过 → 执行；可重试且未超次 → 校正；否则结束。"""

    def route(state: AgentState) -> str:
        failure = state.get("failure")
        if failure is None:
            return RUN_STEP
        if failure.retryable and state.get("attempts", 0) < deps.max_attempts:
            return CORRECT_STEP
        return END

    return route


def _correct_node(deps: AgentGraphDeps):
    def node(state: AgentState) -> dict[str, Any]:
        # 与手写编排一致：进入 correct_sql 之前不再单独查取消——循环顶部的
        # 检查刚在 validate_sql 之前做过；校正后的重新校验会再查一次。
        _emit(_progress(CORRECT_STEP, "running"))
        started = time.perf_counter()
        proposal: CorrectionProposal = propose_correction(
            state["context"],
            state["sql"],
            state["failure"],  # type: ignore[arg-type]
            corrector=deps.corrector,
            table=deps.table,
        )
        elapsed = _elapsed(started)

        if proposal.ok:
            _emit(_progress(CORRECT_STEP, "success", elapsed))
        else:
            _emit(_progress(CORRECT_STEP, "error", elapsed))
            failure = proposal.error or state["failure"]  # type: ignore[assignment]
            if proposal.note:
                # 校正失败的原因（被拒答 / 崩溃 / 产物不合契约）必须能被
                # 看到，否则 SSE 上只有一块红色 correct_sql。`reason` 是
                # sse.schema.json 里已有的 detail 字段，不改契约。
                failure = ChannelError(
                    code=failure.code,
                    message=failure.message,
                    step=failure.step,
                    detail={**failure.detail, "reason": proposal.note},
                )
            raise GraphHalt(
                decorate_error(
                    failure,
                    step=VALIDATE_STEP,
                    original_sql=state.get("original_sql"),
                    corrected_sql=state.get("corrected_sql"),
                    attempts=state.get("attempts", 0),
                    request_id=deps.request_id,
                )
            )

        return {
            "sql": proposal.sql or state["sql"],
            "corrected_sql": proposal.sql,
            "attempts": state.get("attempts", 0) + 1,
            "correction_attempted": True,
            "failure": None,
        }

    return node


def _run_node(deps: AgentGraphDeps):
    def node(state: AgentState) -> dict[str, Any]:
        _ensure_not_cancelled(deps)
        _emit(_progress(RUN_STEP, "running"))
        started = time.perf_counter()
        try:
            execution = deps.executor.execute(state["sql"])
        except Exception as exc:  # noqa: BLE001 - 连不上库也算一种失败
            _emit(_progress(RUN_STEP, "error", _elapsed(started)))
            raise GraphHalt(
                decorate_error(
                    build_error(
                        INTERNAL_ERROR,
                        f"执行阶段失败：{exc}",
                        step=RUN_STEP,
                    ),
                    step=RUN_STEP,
                    original_sql=state.get("original_sql"),
                    corrected_sql=state.get("corrected_sql"),
                    attempts=state.get("attempts", 0),
                    request_id=deps.request_id,
                )
            ) from exc
        elapsed = _elapsed(started)

        if execution.ok:
            if deps.cancel is not None and deps.cancel.cancelled:
                # 取消发生在执行期间：结果照常丢弃，换成一条 CANCELLED。
                raise GraphCancelled
            _emit(_progress(RUN_STEP, "success", elapsed))
        else:
            _emit(_progress(RUN_STEP, "error", elapsed))
        return {"execution": execution}

    return node


# ---------------------------------------------------------------------------
# 构图
# ---------------------------------------------------------------------------


def build_agent_graph(deps: AgentGraphDeps):
    """构建并编译 12 节点图。

    每次问数编译一张图：节点闭包持有这一次的 builder / fake LLM / 执行器，
    不共享可变状态。编译本身很轻，换来的是「一次问数 = 一张图」的清晰边界。
    """
    phases = {phase.step: phase for phase in deps.builder.phases()}
    missing = [step for step in CONTEXT_STEPS if step not in phases]
    if missing:
        raise ValueError(f"OfflineContextBuilder 缺少上下文阶段：{missing}")

    graph: StateGraph = StateGraph(AgentState)

    for step in CONTEXT_STEPS:
        graph.add_node(step, _context_node(step, phases[step], deps))

    graph.add_node(GENERATE_STEP, _generate_node(deps))
    graph.add_node(VALIDATE_STEP, _validate_node(deps))
    graph.add_node(CORRECT_STEP, _correct_node(deps))
    graph.add_node(RUN_STEP, _run_node(deps))

    graph.add_edge(START, CONTEXT_STEPS[0])
    for previous, following in zip(CONTEXT_STEPS, CONTEXT_STEPS[1:]):
        graph.add_edge(previous, following)
    graph.add_edge(CONTEXT_STEPS[-1], GENERATE_STEP)
    graph.add_edge(GENERATE_STEP, VALIDATE_STEP)

    graph.add_conditional_edges(
        VALIDATE_STEP,
        _route_after_validate(deps),
        {
            RUN_STEP: RUN_STEP,
            CORRECT_STEP: CORRECT_STEP,
            END: END,
        },
    )
    graph.add_edge(CORRECT_STEP, VALIDATE_STEP)
    graph.add_edge(RUN_STEP, END)

    return graph.compile()
