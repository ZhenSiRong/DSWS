#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 教师/CI 夹具：不是学生入口；学生工具见 tutorial/appendix/gui-debugging.md
"""附录 · VizTracer 实测：把一次离线问数录成浏览器可看的时间线。

只跑**真代码路径**（与第 21 页 pdb 演示同一批函数）：
    OfflineContextBuilder 的 8 个上下文阶段
    → check_sql（guard 静态校验）+ validate_sql（第一道判据）
    → propose_correction 的三个触发条件（无校正器 / 不可重试 / 全满足）
    → 二次 validate_sql → FakeExecutor 的边界

只替换两样外部依赖，**复用 `tutorial/shots/pdb_step_demo.py` 的夹具**：
    - 模型：pdb_step_demo.FakeGenerator，返回固定 JSON 文本，文本仍走真的
      `parse_model_payload` 解析；
    - 数据库：pdb_step_demo.FakeExecutor 返回固定行，不连 MySQL。
不读 .env、不连网络、不启容器、不碰 ES / Qdrant。

跑法（在仓库根目录；viztracer 只装进一次性 venv，别装进仓库 venv）：
    uv venv /tmp/vizenv --python 3.14
    uv pip install --python /tmp/vizenv/bin/python viztracer
    PYTHONPATH=/tmp/vizenv/lib/python3.14/site-packages \\
        system/backend/.venv/bin/python tutorial/shots/trace_viztracer.py

产物（证据留痕，不提交）：
    tutorial/review/viztracer/trace.json     viztracer 原始 trace
    tutorial/review/viztracer/timeline.html  单文件离线时间线（浏览器直接打开）

timeline.html 用 viztracer 自带的 ReportBuilder 把 trace.json 内联进 HTML；
本版 vizviewer 只有本地服务器模式（`vizviewer trace.json`），没有 --output，
所以单文件产物走 Python API（见本文件末尾 build_timeline_html）。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHOTS = Path(__file__).resolve().parent
for path in (str(REPO), str(SHOTS), str(REPO / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

try:  # viztracer 只存在于一次性 venv，通过 PYTHONPATH 注入
    from viztracer import VizTracer
    from viztracer.report_builder import ReportBuilder
except ImportError:  # pragma: no cover - 给学生的报错提示
    raise SystemExit(
        "缺少 viztracer：它只装在一次性 venv 里，不进仓库 venv。\n"
        "  uv venv /tmp/vizenv --python 3.14\n"
        "  uv pip install --python /tmp/vizenv/bin/python viztracer\n"
        "  PYTHONPATH=/tmp/vizenv/lib/python3.14/site-packages \\\n"
        "      system/backend/.venv/bin/python tutorial/shots/trace_viztracer.py"
    )

# 夹具就在 pdb_step_demo.py 里：同一组输入、同一个假模型、同一个假执行器。
import pdb_step_demo as demo  # noqa: E402

from app.agent.correct import (  # noqa: E402
    FixtureCorrector,
    LlmCorrector,
    propose_correction,
)
from app.agent.errors import build_error, load_error_table  # noqa: E402
from app.agent.validate import validate_sql  # noqa: E402
from app.generate.context import OfflineContextBuilder  # noqa: E402
from app.generate.guard import check_sql  # noqa: E402

TRACE_PATH = REPO / "manual" / "review" / "viztracer" / "trace.json"
HTML_PATH = REPO / "manual" / "review" / "viztracer" / "timeline.html"

#: 每个阶段在 trace 里的条带名要能一眼认出来，所以包一层有语义的壳。
TIMINGS: list[tuple[str, float]] = []


def _timed(stage: str, fn, *args, **kwargs):
    """跑一个阶段并记录真实墙钟耗时（含 VizTracer 采样开销）。"""
    started = time.perf_counter()
    value = fn(*args, **kwargs)
    TIMINGS.append((stage, time.perf_counter() - started))
    return value


def graph_context_stages(query: str):
    """8 个上下文阶段——`app/agent/graph.py` 的 `_context_node` 逐个跑的就是它们。"""
    builder = OfflineContextBuilder(query)
    for phase in builder.phases():
        phase.run()
    return builder.result()


def guard_check(sql: str, context, query: str):
    """`validate_sql` 节点里真正做事的两层：AST 静态校验 + 判据聚合。"""
    report = check_sql(sql, context, query)
    error = validate_sql(sql, context, query)
    print(f"guard.check_sql -> ok={report.ok} 违规={len(report.violations)} 条")
    print(f"validate_sql -> error.code={error.code} retryable={error.retryable}")
    return report, error


def correct_retry(context, sql_before: str, error):
    """`correct_sql` 节点：与 pdb_step_demo 同一组触发条件，全满足才真的校正。"""
    policy = load_error_table().correction
    print(f"契约 correction -> max_attempts={policy.max_attempts} revalidate={policy.revalidate}")

    no_corrector = propose_correction(context, sql_before, error, corrector=None)
    print(f"触发条件① corrector=None -> attempted={no_corrector.attempted}")

    rejected = build_error("SQL_REJECTED", "被安全策略拒绝", reason_code="SQL_NOT_READ_ONLY")
    not_retryable = propose_correction(
        context, sql_before, rejected, corrector=FixtureCorrector({"sql": demo.SQL_AFTER})
    )
    print(f"触发条件② code={rejected.code} -> attempted={not_retryable.attempted}")

    fake_llm = demo.FakeGenerator(demo.MODEL_TEXT)
    proposal = propose_correction(context, sql_before, error, corrector=LlmCorrector(fake_llm))
    print(f"触发条件③ 全满足 -> attempted={proposal.attempted} ok={proposal.ok} attempts=1/{policy.max_attempts}")
    return proposal


def second_validate(proposal, context, query: str):
    """`correct_sql` 之后回到 `validate_sql` 重新校验——图里那条回边。"""
    revalidated = validate_sql(proposal.sql, context, query)
    print(f"二次 validate_sql -> error={revalidated}")
    return revalidated


def run_fake_sql(sql: str):
    """`run_sql` 节点：真执行器接口 + 假数据库（不连 MySQL）。"""
    result = demo.FakeExecutor().execute(sql)
    print(f"run_sql（假执行器）-> ok={result.ok} rows={result.rows}")
    return result


def ask_once(query: str = demo.QUERY) -> dict:
    """一次的完整问数：上下文 → guard → 校正 → 二次校验 → 假执行。"""
    context = _timed("graph_context_stages", graph_context_stages, query)
    report, error = _timed("guard_check", guard_check, demo.SQL_BEFORE, context, query)
    proposal = _timed("correct_retry", correct_retry, context, demo.SQL_BEFORE, error)
    revalidated = _timed("second_validate", second_validate, proposal, context, query)
    result = _timed("run_fake_sql", run_fake_sql, proposal.sql)
    return {
        "query": query,
        "violations": len(report.violations),
        "error_code": error.code,
        "sql_after": proposal.sql,
        "revalidated": revalidated,
        "rows": result.rows,
    }


def strip_event_locations(trace: dict) -> dict:
    """把事件名从 `func (绝对路径:行号)` 剥成 `func`。

    viztracer 原始事件名带 `co_filename`，那是本机绝对路径；直接把 raw trace
    交给浏览器会在时间线标签里显示家目录。这里只在生成 HTML 时剥掉定位后缀，
    `trace.json` 保持 viztracer 原始产物不动。
    """
    for event in trace.get("traceEvents", ()):
        name = event.get("name", "")
        if name.endswith(")") and " (" in name:
            head, _, tail = name.rpartition(" (")
            if tail.endswith(")") and ":" in tail:
                event["name"] = head
    return trace


def build_timeline_html(trace_path: Path, html_path: Path) -> int:
    """把 raw trace 变成单文件离线 HTML；返回内联的 trace 事件条数。"""
    trace = strip_event_locations(json.loads(trace_path.read_text(encoding="utf-8")))
    builder = ReportBuilder(trace, verbose=0)
    builder.save(str(html_path), file_info=False)  # 不内联源码，避免绝对路径
    return len(trace.get("traceEvents", []))


def main() -> int:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("=== 开始追踪：一次离线问数（真代码路径 / 假模型 + 假数据库）===")

    tracer = VizTracer(
        output_file=str(TRACE_PATH),
        verbose=0,
        tracer_entries=1000_000,
        # 只录本仓库的代码：stdlib / sqlglot 内部调用会淹没时间线，
        # 而且会把 trace 撑到几十 MB（file_info 还会内联源码）。
        include_files=[str(REPO / "backend" / "app"), str(SHOTS)],
        file_info=False,
        ignore_c_function=True,
        ignore_frozen=True,
    )
    started = time.perf_counter()
    tracer.start()
    try:
        outcome = ask_once()
    finally:
        tracer.stop()
        tracer.save()
    wall = time.perf_counter() - started
    print(f"=== 追踪结束：墙钟 {wall * 1000:.1f} ms（含 VizTracer 开销）===")

    print("\n各阶段耗时（墙钟，含追踪开销）：")
    for stage, seconds in TIMINGS:
        print(f"  {stage:<24}{seconds * 1000:8.2f} ms")

    entries = build_timeline_html(TRACE_PATH, HTML_PATH)
    print(f"\ntrace.json   -> {TRACE_PATH.relative_to(REPO)}  "
          f"{TRACE_PATH.stat().st_size / 1024:.0f} KB / {entries} 条事件")
    print(f"timeline.html -> {HTML_PATH.relative_to(REPO)}  "
          f"{HTML_PATH.stat().st_size / 1024 / 1024:.2f} MB（单文件，可直接打开）")
    print(f"\n结果自检：违规 {outcome['violations']} 条 · 首错 {outcome['error_code']} · "
          f"行数 {len(outcome['rows'])} · 二次校验 {outcome['revalidated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
