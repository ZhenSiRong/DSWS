#!/usr/bin/env bash
# scripts/acceptance/level-l3.sh —— T2 验收线 L3（manual/ACCEPTANCE.md §4，page-14 – page-17）。
#
# **完全离线**：不需要 Docker / 栈，只要求 backend/.venv（page-00 的 make install）。
# 自动（只读/安全）：
#   1. pytest backend/tests/recall         （18 passed, 23 skipped；只断言退出码 0）
#   2. pytest backend/tests/generate       （122 passed）
#   3. pytest backend/tests/agent/test_correct.py（14 passed）
#   4. app.scripts.failures --check        （末行 S6 PASS）
#   5. eval/probe_correction.py            （末行 "mismatch": 0）
# MANUAL（只打印，不执行）：p17 级考核「关纠错」——改代码 + lab reset。
#
# 用法：bash scripts/acceptance/level-l3.sh（任意 cwd；Makefile 目标 accept-l3）。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=common.sh
source "$ROOT/scripts/acceptance/common.sh"

accept_init L3 'page-14 – page-17（「审」不确定输出；离线，不需要栈）'
require_root
require_backend_python

manuals() {
  manual_section
  manual 'p14–p16 逐页对账：按 manual/ACCEPTANCE.md §4 的「你应该看到」人工判（S3 PASS、S4 基线 10/10、S6 PASS 等）；本脚本覆盖 recall / generate / failures / probe。'
  manual 'p17 级考核（关纠错，改代码；可还原）：1) 在 backend/app/agent/correct.py 的 propose_correction 里，于 policy = contract.correction 之后插 4 行立即 return CorrectionProposal(attempted=False, ok=False, error=error, note="拆一刀：校正已关闭")（多行写法照 page-17 抄）。'
  manual 'p17 级考核 2) 重跑三条判据：test_correct.py → 5 failed, 9 passed；failures --check → FAIL: 1 项不符合预期；probe_correction.py 仍 mismatch 0（语料判据抓不到，这正是答案）。'
  manual 'p17 级考核 3) 还原：scripts/lab reset p17-before --yes → test_correct.py 回 14 passed、failures --check 回 S6 PASS。lab reset 只回白名单文件，见 manual/TRAPS.md。'
  manual '本脚本自动段跑的是「拆一刀之前」的状态；拆一刀必须人工做并还原。'
}

# --- 1. 召回层（离线；18 passed / 23 skipped 会漂，只断言退出码）-----------
check_ok '召回层 pytest（backend/tests/recall；只断言退出码 0，计数允许漂）' \
  "$BACKEND_PY" -m pytest backend/tests/recall -q

# --- 2. 生成层（122 passed）-------------------------------------------------
check_contains '生成层 pytest（backend/tests/generate：122 passed）' '122 passed' \
  "$BACKEND_PY" -m pytest backend/tests/generate -q

# --- 3. 纠错单测（14 passed）------------------------------------------------
check_contains '纠错单测（backend/tests/agent/test_correct.py：14 passed）' '14 passed' \
  "$BACKEND_PY" -m pytest backend/tests/agent/test_correct.py -q

# --- 4. 失败矩阵（末行 S6 PASS）---------------------------------------------
run_in "$ROOT/backend" .venv/bin/python -m app.scripts.failures --check
assert_last_contains '失败矩阵（app.scripts.failures --check：末行 S6 PASS）' '^S6 PASS$'

# --- 5. 校正语料的尺子（末行 mismatch 0）-----------------------------------
run env PYTHONPATH="$ROOT/backend" "$BACKEND_PY" "$ROOT/eval/probe_correction.py"
assert_last_contains '校正语料尺子（eval/probe_correction.py：末行 "mismatch": 0）' '"mismatch": 0'

manuals
accept_finish
