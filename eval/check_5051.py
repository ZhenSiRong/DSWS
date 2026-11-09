#!/usr/bin/env python3
"""5051 外部冒烟：只读，不改服务。

验证 PRD 四项能力在线上是否成立，并落盘证据。
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TARGET = "http://8.155.135.97:5051"
OUT = Path(__file__).resolve().parent / "5051-smoke.json"


def get(path: str) -> tuple[int, dict]:
    with urllib.request.urlopen(TARGET + path, timeout=15) as r:
        return r.status, json.loads(r.read())


def ask(query: str, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        TARGET + "/api/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    steps, result, error = [], None, None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "progress":
                steps.append([ev.get("step"), ev.get("status")])
            elif ev.get("type") == "result":
                result = ev
            elif ev.get("type") == "error":
                error = ev
    data = (result or {}).get("data") or {}
    return {
        "steps": steps,
        "outcome": "result" if result else ("error" if error else "unknown"),
        "error_code": (error or {}).get("code"),
        "columns": [c.get("name") for c in data.get("columns", [])],
        "rows": data.get("rows", [])[:3],
        "row_count": len(data.get("rows", [])),
    }


def main() -> int:
    health_code, health = get("/api/health")
    steps_code, steps = get("/api/steps")
    gmv = ask("统计 2025 年第一季度各大区的 GMV")
    union = ask("用 UNION 把手机数码和食品饮料两个品类的销售额拼起来给我看")

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "target": TARGET,
        "P1_nl2sql": {
            "health": health_code,
            "question": "统计 2025 年第一季度各大区的 GMV",
            "outcome": gmv["outcome"],
            "columns": gmv["columns"],
            "row_count": gmv["row_count"],
            "first_rows": gmv["rows"],
        },
        "P2_langgraph_12": {
            "steps_status": steps_code,
            "node_count": len(steps.get("steps", [])),
            "ids": [s["id"] for s in steps.get("steps", [])],
        },
        "P3_validate_correct": {
            "note": "校正闭环见 eval/live-report.json 与 .rec/.rec-try1/evidence/seg-06-correct.sse",
        },
        "P4_safety": {
            "question": "用 UNION 把手机数码和食品饮料两个品类的销售额拼起来给我看",
            "outcome": union["outcome"],
            "error_code": union["error_code"],
            "not_executed": union["outcome"] == "error",
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
