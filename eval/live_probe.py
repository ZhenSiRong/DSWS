#!/usr/bin/env python3
"""WBS 4.1 · 实模型层：对运行中的服务发真实问数，按“多次采样”统计校正成功率。

单次结果不能当结论：同一问题可能一次失败、一次成功。默认每条跑 3 次。

判据：
- correction_opportunity：出现过 validate_sql error
- correction_success：correct_sql success 之后 validate_sql success 且 run_sql success
- correction_fail：触发校正但最终仍 error
- no_correction_needed：一次校验就过

用法：
    python3 eval/live_probe.py --target http://8.155.135.97:5051 --trials 3
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CASES = Path(__file__).resolve().parent / "correction_live.jsonl"


def ask(target: str, query: str, timeout: int = 150) -> list[dict]:
    req = urllib.request.Request(
        f"{target}/api/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    events: list[dict] = []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                events.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                continue
    return events


def summarize(events: list[dict]) -> dict:
    seq = [(e.get("step"), e.get("status")) for e in events if e.get("type") == "progress"]
    result = next((e for e in events if e.get("type") == "result"), None)
    error = next((e for e in events if e.get("type") == "error"), None)

    validate_errors = sum(1 for s, st in seq if s == "validate_sql" and st == "error")
    correct = [st for s, st in seq if s == "correct_sql"]
    run_ok = any(s == "run_sql" and st == "success" for s, st in seq)
    # 校正之后是否还有一次成功的 validate
    corrected_ok = False
    if "success" in correct:
        idx = max(i for i, (s, st) in enumerate(seq) if s == "correct_sql")
        corrected_ok = any(s == "validate_sql" and st == "success" for s, st in seq[idx:])

    data = (result or {}).get("data") or {}
    rows = data.get("rows") or []
    return {
        "node_count": len({s for s, _ in seq}),
        "validate_errors": validate_errors,
        "correct_sql": correct[-1] if correct else None,
        "corrected_ok": corrected_ok,
        "run_sql_ok": run_ok,
        "outcome": "result" if result else ("error" if error else "unknown"),
        "error_code": (error or {}).get("code"),
        "row_count": len(rows),
        "columns": [c.get("name") for c in data.get("columns", [])],
    }


def classify(t: dict) -> str:
    if t["validate_errors"] == 0:
        return "no_correction_needed"
    if t["corrected_ok"] and t["run_sql_ok"]:
        return "correction_success"
    if t["correct_sql"]:
        return "correction_fail"
    return "validate_fail_no_correction"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="http://8.155.135.97:5051")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    cases = [json.loads(x) for x in CASES.read_text(encoding="utf-8").splitlines() if x.strip()]
    out = []
    for c in cases:
        trials = []
        for _ in range(args.trials):
            try:
                t = summarize(ask(args.target, c["question"]))
            except Exception as exc:
                t = {"error": str(exc), "outcome": "transport_error"}
            t["class"] = classify(t) if "validate_errors" in t else "transport_error"
            trials.append(t)
        out.append({"id": c["id"], "question": c["question"], "why": c["why"], "trials": trials})
        print(json.dumps({
            "id": c["id"],
            "classes": [t["class"] for t in trials],
            "errors": [t.get("error_code") for t in trials],
        }, ensure_ascii=False))

    flat = [t for c in out for t in c["trials"]]
    counters = Counter(t["class"] for t in flat)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "trials_per_case": args.trials,
        "cases": out,
        "totals": dict(counters),
        "correction_opportunities": sum(t.get("validate_errors", 0) > 0 for t in flat),
        "correction_success_rate": (
            counters["correction_success"] / max(1, counters["correction_success"] + counters["correction_fail"])
        ),
    }
    (Path(__file__).resolve().parent / "live-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"totals": report["totals"], "success_rate": round(report["correction_success_rate"], 3)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
