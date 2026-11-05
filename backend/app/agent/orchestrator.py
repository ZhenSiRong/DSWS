"""S6 · 编排器。

把 S4 的生成、S5 的策略与执行、S6 的校正接成一条**会发事件**的流水线：

    上下文 8 阶段  -> generate_sql -> validate_sql -> [correct_sql] -> run_sql
                                                                   -> result / error

工作流本身由 `app.agent.graph` 里的 12 节点 LangGraph 执行；这个模块只
负责「图 → SSE 事件」的翻译。三条不变式不变：

    1. **每一步都有真事**。8 个上下文节点跑的是 `OfflineContextBuilder`
       的真实阶段，`generate/validate/correct/run` 跑的是各层的真实函数。
    2. **每一种失败都有名字**。所有失败都变成 `ChannelError`，码来自
       `contracts/errors.yaml`；没有「失败但没人知道」。
    3. **流必须以 result 或 error 收尾**。任何异常都被兜住并变成
       `INTERNAL_ERROR`——绝不静默结束（旧系统最大的缺陷）。

取消也是一条路径：图在上下文阶段、校验、执行这些与旧编排器相同的步骤
边界检查取消开关，被取消时停下并发一条 `CANCELLED` 错误事件收尾，
**后面的步骤不再开始**。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Iterator

from app.agent.cancel import CancelToken
from app.agent.correct import SqlCorrector
from app.agent.errors import (
    CANCELLED_CODE,
    EMPTY_RESULT,
    INTERNAL_ERROR,
    ChannelError,
    ErrorTable,
    build_error,
    decorate_error,
    load_error_table,
)
from app.agent.graph import (
    CORRECT_STEP,
    GENERATE_STEP,
    RUN_STEP,
    VALIDATE_STEP,
    AgentGraphDeps,
    GraphCancelled,
    GraphHalt,
    SqlExecutor,
    build_agent_graph,
)
from app.agent.values import normalize_cell
from app.generate.context import OfflineContextBuilder
from app.generate.provider import SqlGenerator
from app.security.executor import ExecutionResult, ReadOnlyExecutor


# ---------------------------------------------------------------------------
# 结果负载
# ---------------------------------------------------------------------------


def _cell_type(value: Any) -> str:
    """单元格类型 → `contracts/sse.schema.json` 里的枚举。

    类型是**从原始值**推出来的（不是从归一化后的值）：`Decimal` 推出来
    是 `number`，`date` 推出来是 `date`——哪怕归一化之后它变成了字符串。
    前端照着这个类型渲染，所以类型必须说的是「这个值本来是什么」。
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        return "number"
    if isinstance(value, (datetime, date)):
        return "date"
    return "string"


def to_result_payload(execution: ExecutionResult) -> dict[str, Any]:
    """执行结果 → SSE `result` 事件的数据部分。

    列名来自执行器，行按列顺序摊成数组——`contracts/sse.schema.json`
    里的 `rows` 是二维数组，不是对象数组。

    列类型从**这一列第一个非空值**推断：整列都是 NULL 时才是 `null`。

    值在进 JSON 之前**归一化**（`app.agent.values`）：`Decimal` 保持数字，
    `date` 变成 ISO 8601 字符串。旧系统在这里用 `default=str` 把两者
    都降级成字符串，数字与字符串在同一行里混列——那正是审计 B4 记的
    「类型被悄悄改写」。
    """
    columns = list(execution.columns)
    raw_rows: list[list[Any]] = []
    for row in execution.rows:
        raw_rows.append([row.get(name) for name in columns])

    def column_type(index: int) -> str:
        for row in raw_rows:
            value = row[index]
            if value is not None:
                return _cell_type(value)
        return "null"

    return {
        "columns": [
            {"name": name, "type": column_type(index)}
            for index, name in enumerate(columns)
        ],
        "rows": [[normalize_cell(value) for value in row] for row in raw_rows],
    }


# ---------------------------------------------------------------------------
# 编排器
# ---------------------------------------------------------------------------


@dataclass
class AgentRunner:
    """一次问数的编排器。

    依赖全部是**注入**的：生成器、校正器、执行器、上下文构建器。这样
    整条链路（生成 → 校验 → 校正 → 执行 → 事件）都能离线测：只把 LLM
    和 MySQL 换掉，别的一行都不改。
    """

    query: str
    generator: SqlGenerator | None = None
    corrector: SqlCorrector | None = None
    executor: SqlExecutor | None = None
    context_factory: Callable[[str], OfflineContextBuilder] | None = None
    cancel: CancelToken | None = None
    now: datetime | None = None
    request_id: str | None = None
    table: ErrorTable = field(default_factory=load_error_table)

    #: 条件步骤 `correct_sql` 是否已经有了结论（跑过 或 显式 skipped）。
    _correct_resolved: bool = False

    # -- 事件构造 ---------------------------------------------------------

    def _progress(
        self,
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

    def _error_event(self, error: ChannelError) -> dict[str, Any]:
        return error.to_event()

    def _skip_correct(self) -> Iterator[dict[str, Any]]:
        """条件步骤必须**显式**说「未触发」。

        旧前端硬编码 12 个节点，`correct_sql` 永远灰着（审计 D4）。规则是：
        条件步骤要么跑（running → success/error），要么显式 skipped——
        **不能永远是一块灰的 pending**。所以流在中途结束（生成失败、
        取消）时，这里补上那一条 skipped。
        """
        if self._correct_resolved:
            return
        self._correct_resolved = True
        yield self._progress(CORRECT_STEP, "skipped")

    def _cancel_error(self) -> ChannelError:
        return build_error(
            CANCELLED_CODE,
            "本次问数已被用户取消。",
            step=None,
            request_id=self.request_id,
        )

    def _internal_error(self, message: str, step: str | None = None) -> ChannelError:
        return build_error(
            INTERNAL_ERROR,
            message,
            step=step,
            request_id=self.request_id,
        )

    # -- 主流程 -----------------------------------------------------------

    def events(self) -> Iterator[dict[str, Any]]:
        """产出这一次问数的全部 SSE 事件。

        真正的工作在 LangGraph 里：`_run_graph()` 编译并执行 12 节点图，
        节点用 `get_stream_writer()` 写出的 progress 事件在这里原样转给
        SSE。流**一定**以 `result` 或 `error` 收尾：任何异常都被兜住。
        """
        # 同一个 runner 可能被重复调用；每次问数都从「correct_sql 未决」开始。
        self._correct_resolved = False
        try:
            yield from self._run_graph()
        except GraphCancelled:
            # 取消：条件步骤还没结论时补一条显式 skipped，再发 CANCELLED。
            yield from self._skip_correct()
            yield self._error_event(self._cancel_error())
        except GraphHalt as halt:
            # 图在某个节点主动停下（上下文异常 / 生成拒答 / 校正失败）：
            # 错误已经是完整的通道错误，补 skipped 后收尾。
            yield from self._skip_correct()
            yield self._error_event(halt.error)
        except Exception as exc:  # noqa: BLE001 - 兜底：绝不静默结束
            yield self._error_event(
                self._internal_error(f"问数过程中发生未预期的错误：{exc}")
            )

    def _run_graph(self) -> Iterator[dict[str, Any]]:
        """执行编译后的 12 节点图，把节点事件映射成 SSE 事件。"""
        factory = self.context_factory or (
            lambda query: OfflineContextBuilder(query, now=self.now)
        )
        builder = factory(self.query)
        executor = self.executor or ReadOnlyExecutor()
        graph = build_agent_graph(
            AgentGraphDeps(
                query=self.query,
                builder=builder,
                executor=executor,
                generator=self.generator,
                corrector=self.corrector,
                now=self.now,
                table=self.table,
                cancel=self.cancel,
                request_id=self.request_id,
            )
        )

        final_state: dict[str, Any] = {}
        # custom：节点执行当时写出的 progress；values：每一步之后的完整状态。
        # 两者一起流式消费，事件顺序与手写循环时完全一致。
        for mode, chunk in graph.stream(
            {"query": self.query},
            stream_mode=["custom", "values"],
        ):
            if mode == "custom":
                event: dict[str, Any] = chunk
                if event.get("step") == CORRECT_STEP:
                    # correct_sql 已经有结论（skipped / running / success /
                    # error），后面的提前终止不需要再补 skipped。
                    self._correct_resolved = True
                yield event
            else:
                final_state = chunk

        yield from self._finish(final_state)

    def _finish(self, state: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """图正常结束后的收尾：把最终状态翻译成 result / error。"""
        execution = state.get("execution")
        if execution is not None:
            yield from self._finish_execution(execution, state)
            return

        failure = state.get("failure")
        if failure is not None:
            # 校验失败且不可重试 / 已用完重试次数：条件边走了 END。
            yield from self._skip_correct()
            yield self._error_event(
                decorate_error(
                    failure,
                    step=VALIDATE_STEP,
                    original_sql=state.get("original_sql"),
                    corrected_sql=state.get("corrected_sql"),
                    attempts=state.get("attempts", 0),
                    request_id=self.request_id,
                )
            )
            return

        # 图结束却没有结果也没有错误：宁可报 INTERNAL_ERROR，也不静默结束。
        yield self._error_event(
            self._internal_error("问数流程结束但没有产生结果。")
        )

    def _finish_execution(
        self,
        execution: ExecutionResult,
        state: dict[str, Any],
    ) -> Iterator[dict[str, Any]]:
        """执行器已经跑完：成功给 result，失败给有名字的 error。"""
        sql = state.get("sql") or ""
        original_sql = state.get("original_sql") or sql
        corrected_sql = state.get("corrected_sql")
        attempts = state.get("attempts", 0)

        if execution.ok:
            if not execution.rows:
                # 空结果**不是失败**：库里真的没这批数据。步骤保持绿色，
                # 界面给一张空态卡（审计 FP-8 的结论）。
                yield self._error_event(
                    build_error(
                        EMPTY_RESULT,
                        "查询执行成功，但没有符合条件的数据。",
                        step=RUN_STEP,
                        sql=sql,
                        rows=0,
                        original_sql=original_sql,
                        corrected_sql=corrected_sql,
                        request_id=self.request_id,
                    )
                )
                return
            yield {"type": "result", "data": to_result_payload(execution)}
            return

        failure = self._execution_error(execution, step=RUN_STEP)
        # 执行阶段的失败**不再校正**。
        #
        # 校正要修的是「生成出来的 SQL」，而能执行到这里说明它已经过了
        # 静态校验与安全策略。此刻的数据库错误（列在库里不存在、超时）
        # 不是「最小必要修正」能可靠修好的东西，再问一次模型只会得到
        # 一个说不准对不对的 SQL。
        #
        # 旧系统是从 `EXPLAIN` 失败触发校正的——在新系统里，`EXPLAIN`
        # 这个位置就是**校验阶段**，触发点并没有变，只是这一关比旧系统
        # 强得多（AST 语义 + 安全策略）。
        yield self._error_event(
            decorate_error(
                failure,
                step=RUN_STEP,
                original_sql=original_sql,
                corrected_sql=corrected_sql,
                attempts=attempts,
                request_id=self.request_id,
            )
        )

    def _execution_error(self, execution: ExecutionResult, *, step: str) -> ChannelError:
        """执行器的错误 → 通道错误。

        执行器给的码如果不在错误码表里（自定义执行器可能给别的码），
        退到 `INTERNAL_ERROR`——**失败必须有名字**，不能因为码不认识就
        悄悄消失。
        """
        error = execution.error
        if error is None:
            return self._internal_error("执行失败但没有给出错误原因", step=step)
        if error.code not in self.table:
            return build_error(
                INTERNAL_ERROR,
                f"执行器返回了未登记的错误码 {error.code}：{error.message}",
                step=step,
                reason_code=error.code,
            )
        return build_error(
            error.code,
            error.message,
            step=step,
            reason_code=error.reason_code or error.code,
        )


