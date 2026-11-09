#!/usr/bin/env python3
"""校验 20 条校正用例的期望码是否与真实 guard/policy 一致。

这是「先验证尺子，再量东西」：如果期望码本身错了，后面的通过率没有意义。

用法（必须用 backend venv，确保能 import app）：
    cd backend && .venv/bin/python ../eval/probe_correction.py
"""
from __future__ import annotations

import json
from pathlib import Path

from app.generate.context import build_offline_context
from app.generate.guard import check_sql
from app.security.config import load_policy_config
from app.security.policy import enforce

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).resolve().parent / "correction.jsonl"


def codes_for(sql: str, query: str) -> tuple[list[str], str]:
    ctx = build_offline_context(query)
    guard = check_sql(sql, ctx, query)
    guard_codes = [v.code for v in guard.violations]

    decision = enforce(sql, config=load_policy_config())
    if decision.ok:
        policy_codes = []
    else:
        policy_codes = [decision.reason_code] if decision.reason_code else ["SQL_REJECTED"]
    return guard_codes, policy_codes if isinstance(policy_codes, list) else [policy_codes]


def main() -> int:
    rows = [json.loads(x) for x in CASES.read_text(encoding="utf-8").splitlines() if x.strip()]
    mismatches = []
    for row in rows:
        guard_codes, policy_codes = codes_for(row["sql"], row.get("intent") or row.get("query") or "")
        if row["layer"] == "policy":
            expected = row.get("expect_reason") or row["expect_code"]
            ok = expected in policy_codes and bool(policy_codes)
            actual = policy_codes
        else:
            expected = row["expect_code"]
            ok = expected in guard_codes
            actual = guard_codes
        print(("PASS" if ok else "FAIL"), row["id"], "expected", expected, "actual", actual)
        if not ok:
            mismatches.append({"id": row["id"], "expected": expected, "actual": actual})
    print(json.dumps({"total": len(rows), "mismatch": len(mismatches)}, ensure_ascii=False))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
