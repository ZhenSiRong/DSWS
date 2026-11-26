#!/usr/bin/env python3
"""check_progress.py —— 兼容转发壳（已并入 toolbox/scripts/task.py check）。

进度护栏升级为任务生命周期台账（toolbox/workflows/ledger.yaml），权威执行者是 task.py：
done 钉证据 + 依赖闸 + review 门禁 + 甘特身份对账。本壳保留旧入口
`python3 toolbox/scripts/check_progress.py [--quick]`，原样转发到 task.py check。
规格见 toolbox/workflows/task-lifecycle.md。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    cmd = [sys.executable, str(REPO / "scripts" / "task.py"), "check"]
    if "--quick" in sys.argv[1:]:
        cmd.append("--quick")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())