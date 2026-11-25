"""LangGraph Studio 的离线图入口（实测用，不进正文）。

把仓库里**真的** `build_agent_graph`（12 节点）暴露给 Studio：
    OfflineContextBuilder（8 个上下文阶段，真代码，不连存储）
    + DeterministicGenerator（离线确定性生成器，不调模型）
    + FakeExecutor（固定行，不连 MySQL）
    + FixtureCorrector（预设产物，仅为演示校正分支）

不读 .env、不连网络、不启容器；与 `manual/shots/pdb_step_demo.py`
同一套离线替身思路（真代码路径 / 假模型 + 假数据库）。

跑法（在 `manual/review/langgraph-studio/` 目录下，见 gui-studio-zed.md）：
    /tmp/lgs/env/bin/langgraph dev --no-browser --port 2024
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.agent.correct import FixtureCorrector  # noqa: E402
from app.agent.graph import AgentGraphDeps, build_agent_graph  # noqa: E402
from app.generate.context import OfflineContextBuilder  # noqa: E402
from app.generate.provider import DeterministicGenerator  # noqa: E402
from app.security.executor import ExecutionResult  # noqa: E402

QUERY = "华北销售额"

GOOD_SQL = (
    "SELECT dim_region.region_name AS `地区`, "
    "SUM(fact_order.order_amount) AS `销售额` "
    "FROM fact_order "
    "JOIN dim_region ON fact_order.region_id = dim_region.region_id "
    "GROUP BY dim_region.region_name"
)


class _FakeExecutor:
    """离线执行器：固定行，不连 MySQL。"""

    name = "fake-db"

    def execute(self, sql: str) -> ExecutionResult:
        return ExecutionResult(
            ok=True,
            sql=sql,
            rows=({"地区": "华北", "销售额": 128400.0},),
            columns=("地区", "销售额"),
        )


def _build(query: str = QUERY):
    return build_agent_graph(
        AgentGraphDeps(
            query=query,
            builder=OfflineContextBuilder(query),
            executor=_FakeExecutor(),
            generator=DeterministicGenerator(),
            corrector=FixtureCorrector({"sql": GOOD_SQL}),
            request_id="studio-offline",
        )
    )


#: langgraph.json 里 `graphs` 指向的对象；Studio 读它画 12 节点图。
graph = _build()


def reset_graph(query: str = QUERY):
    """换一个问题时重新编译（Studio 里一般不需要）。"""
    global graph
    graph = _build(query)
    return graph
