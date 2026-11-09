#!/usr/bin/env python3
"""WBS 1.1 · 冻结参考基线。

记录当前 git 状态、关键契约文件哈希、以及线上 5051 的契约快照。
任何一项变化，后续一致性测试的结果就不可比，必须先重新冻结。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "freeze.json"

FILES = [
    "contracts/steps.yaml",
    "contracts/errors.yaml",
    "contracts/sql.policy.yaml",
    "contracts/schema.contract.yaml",
    "contracts/metrics.yaml",
    "backend/app/agent/graph.py",
    "backend/app/agent/validate.py",
    "backend/app/agent/correct.py",
    "backend/app/generate/provider.py",
    "backend/app/security/policy.py",
    "backend/app/security/executor.py",
    "frontend/package.json",
    "deliverable/v2/original-frontend/package.json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def fetch(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            body = r.read()
        return {
            "url": url,
            "status": r.status,
            "sha256": hashlib.sha256(body).hexdigest(),
            "body": json.loads(body) if body[:1] in (b"{", b"[") else body[:200].decode("utf-8", "replace"),
        }
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"url": url, "error": str(exc)}


def main() -> int:
    files = {}
    for rel in FILES:
        p = ROOT / rel
        files[rel] = sha256(p) if p.is_file() else None

    data = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git("rev-parse", "HEAD"),
            "dirty_files": len([x for x in git("status", "--porcelain").splitlines() if x]),
        },
        "files": files,
        "remote": {
            "steps_5051": fetch("http://8.155.135.97:5051/api/steps"),
            "health_5051": fetch("http://8.155.135.97:5051/api/health"),
        },
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "branch": data["git"]["branch"],
        "commit": data["git"]["commit"][:12],
        "dirty_files": data["git"]["dirty_files"],
        "missing_files": [k for k, v in files.items() if v is None],
        "steps_5051": data["remote"]["steps_5051"].get("status"),
        "node_count": len(data["remote"]["steps_5051"].get("body", {}).get("steps", []))
        if isinstance(data["remote"]["steps_5051"].get("body"), dict) else None,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
