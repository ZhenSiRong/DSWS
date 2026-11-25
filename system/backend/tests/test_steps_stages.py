"""契约测试：12 个节点必须完整落进 10 个阶段。

这条测试守的是教材里那句「12 个节点按 10 步分阶段执行」：
- 节点集合逐字等于 `steps`；
- 每个节点恰好属于一个阶段，不重不漏；
- `step.stage` 与 `stages[].nodes` 双向一致；
- 阶段编号连续 1..10。
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
STEPS = ROOT / "contracts" / "steps.yaml"


def _load() -> dict:
    return yaml.safe_load(STEPS.read_text(encoding="utf-8"))


def test_twelve_nodes_in_ten_stages() -> None:
    data = _load()
    steps = data["steps"]
    stages = data["stages"]

    assert len(steps) == 12, f"节点数应为 12，实际 {len(steps)}"
    assert len(stages) == 10, f"阶段数应为 10，实际 {len(stages)}"
    assert [s["id"] for s in stages] == list(range(1, 11)), "阶段编号必须连续 1..10"

    step_ids = [s["id"] for s in steps]
    assert len(set(step_ids)) == 12, "节点 id 不能重复"

    staged: list[str] = []
    for stage in stages:
        assert stage["nodes"], f"阶段 {stage['id']} 没有节点"
        staged.extend(stage["nodes"])

    assert sorted(staged) == sorted(step_ids), "阶段里的节点必须与 steps 完全一致，不重不漏"

    by_id = {s["id"]: s for s in steps}
    for stage in stages:
        for node in stage["nodes"]:
            assert by_id[node]["stage"] == stage["id"], (
                f"{node} 的 stage 字段与所属阶段不一致"
            )
