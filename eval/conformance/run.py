#!/usr/bin/env python3
"""一致性测试 C1–C6：参考实现与学生产物跑同一套。

用法（仓库根目录）：
    backend/.venv/bin/python eval/conformance/run.py
    backend/.venv/bin/python eval/conformance/run.py --target http://8.155.135.97:5051

产物：
    eval/conformance/report.json   逐项证据
退出码：0 = 全过；1 = 有失败。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "report.json"


def run(cmd: list[str], cwd: Path, timeout: int = 600, extra_env: dict | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(
        cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout, env=env,
    )
    return p.returncode, p.stdout


def fetch(url: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.status, r.read()


def expected_steps() -> list[str]:
    text = (ROOT / "contracts/steps.yaml").read_text(encoding="utf-8")
    return re.findall(r"^\s*-\s*id:\s*(\w+)", text, re.M)


def check_contract(target: str) -> dict:
    want = expected_steps()
    status, body = fetch(f"{target}/api/steps")
    data = json.loads(body)
    got = [s["id"] for s in data.get("steps", [])]
    ok = status == 200 and got == want and len(got) == 12
    return {"gate": "C1_contract", "pass": ok, "evidence": f"{len(got)} nodes; match={got == want}"}


def check_health(target: str) -> dict:
    status, _ = fetch(f"{target}/api/health")
    return {"gate": "C6_health", "pass": status == 200, "evidence": f"HTTP {status}"}


def check_frontend(target: str) -> dict:
    status, body = fetch(f"{target}/")
    html = body.decode("utf-8", "replace")
    m = re.search(r'src="(/assets/[^"]+\.js)"', html)
    asset_ok = False
    if m:
        a_status, _ = fetch(f"{target}{m.group(1)}")
        asset_ok = a_status == 200
    ok = status == 200 and "电商问数" in html and asset_ok
    return {"gate": "C5_frontend", "pass": ok, "evidence": f"title_ok={'电商问数' in html} asset_ok={asset_ok}"}


def check_baseline() -> dict:
    code, out = run(["uv", "run", "--offline", "python", "-m", "app.scripts.generate", "--baseline"], ROOT / "backend")
    ok = code == 0 and "10/10" in out
    tail = [ln for ln in out.splitlines() if "基线：" in ln]
    return {"gate": "C2b_baseline", "pass": ok, "evidence": tail[0] if tail else out[-200:]}


def check_pytest(name: str, args: list[str]) -> dict:
    code, out = run(["uv", "run", "--offline", "pytest", "-q", *args], ROOT / "backend")
    tail = [ln for ln in out.splitlines() if "passed" in ln or "failed" in ln]
    return {"gate": name, "pass": code == 0, "evidence": tail[-1] if tail else out[-200:]}


def check_detection() -> dict:
    code, out = run(
        ["uv", "run", "--offline", "python", str(Path(__file__).resolve().parents[1] / "probe_correction.py")],
        ROOT / "backend",
        timeout=300,
        extra_env={"PYTHONPATH": str(ROOT / "backend")},
    )
    return {"gate": "C3d_detection", "pass": code == 0, "evidence": out.strip().splitlines()[-1]}


def main() -> int:
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="http://8.155.135.97:5051")
    ap.add_argument("--skip-heavy", action="store_true", help="跳过 pytest 与 make stage5")
    ap.add_argument("--root", default=str(ROOT), help="被测仓库根目录（默认当前仓库）")
    args = ap.parse_args()

    ROOT = Path(args.root).resolve()

    checks: list[dict] = []
    checks.append(check_contract(args.target))
    checks.append(check_health(args.target))
    checks.append(check_frontend(args.target))
    checks.append(check_baseline())
    checks.append(check_detection())
    if not args.skip_heavy:
        checks.append(check_pytest("C2r_recall", ["tests/recall/test_golden.py"]))
        checks.append(check_pytest("C3a_loop", ["tests/agent/test_correct.py", "tests/agent/test_scenarios.py"]))
        code, out = run(["make", "stage5"], ROOT, timeout=900)
        checks.append({
            "gate": "C4_stage5",
            "pass": code == 0 and "S5 PASS" in out,
            "evidence": "S5 PASS" if "S5 PASS" in out else out[-200:],
        })

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks),
        "thresholds": {"C1": "100%", "C2": "baseline 10/10 + recall golden", "C3": "detection 20/20 + loop", "C4": "100%", "C5": "title+asset", "C6": "health 200"},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for c in checks:
        print(("PASS" if c["pass"] else "FAIL"), c["gate"], "-", c["evidence"])
    print("ALL PASS" if result["all_pass"] else "GATES FAILED")
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
