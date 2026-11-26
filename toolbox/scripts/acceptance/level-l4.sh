#!/usr/bin/env bash
# toolbox/scripts/acceptance/level-l4.sh —— T2 验收线 L4（tutorial/ACCEPTANCE.md §5，page-18 – page-22）。
#
# **离线为主**：不需要栈（p18/p19 只读账号的实库检查是 MANUAL 的前置，不在自动段）。
# 自动（只读/安全）：
#   1. app.scripts.security --check     （S5 PASS + 36/36 拒绝）
#   2. pytest system/backend/tests/agent -k cancel（6 passed）
#   3. app.scripts.record_sse --check   （S7 SSE RECORD PASS）
#   4. cd system/frontend && npm test          （40 passed；缺 node_modules 记可选 SKIP+WARN）
# MANUAL（只打印，不执行）：p22 级考核「抢窗口注入 GRANT ALL」+ 还原。
#
# 用法：bash toolbox/scripts/acceptance/level-l4.sh（任意 cwd；Makefile 目标 accept-l4）。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=common.sh
source "$ROOT/scripts/acceptance/common.sh"

accept_init L4 'page-18 – page-22（「守」事故与越权；离线为主）'
require_root
require_backend_python

manuals() {
  manual_section
  manual 'p18–p21 逐页对账：按 tutorial/ACCEPTANCE.md §5 的「你应该看到」人工判（只读账号 --verify-ro-account、/api/steps = 12、/api/errors = 16 等）；本脚本覆盖 S5 / cancel / S7 / 前端 40 条。'
  manual 'p22 级考核（抢窗口注入 GRANT ALL，破坏性但可还原）：1) 终端 B 先粘 page-22 的 watcher 循环（等 init 退出就注入，实测窗口约 3 秒）；2) 终端 A 跑 make docker-smoke → 1–6 步绿、第 7 步红、fail-fast 停在第 7 步；3) 还原：(cd system/backend && .venv/bin/python -m app.scripts.security --provision-ro-account) → make docker-smoke 回到 DOCKER SMOKE PASS。'
  manual 'p22 的全量 pytest（813 passed, 30 skipped，数字会漂）不在自动段：耗时且与本级判据重复；需要时手动跑 (cd system/backend && .venv/bin/python -m pytest -q)。'
  manual '不要在本机别的栈上做抢窗口注入；并行验收用仓库副本 + 独立 compose 项目名/端口（page-13）。'
}

# --- 1. S5 安全策略门（36/36 拒绝 + S5 PASS）--------------------------------
run_in "$ROOT/backend" .venv/bin/python -m app.scripts.security --check
assert_matches 'S5 安全策略门（S5 PASS；注入语料 36/36 拒绝）' 'S5 PASS' '36/36'

# --- 2. 取消路径（6 passed, 108 deselected）--------------------------------
check_contains '取消测试（system/backend/tests/agent -k cancel：6 passed）' '6 passed' \
  "$BACKEND_PY" -m pytest system/backend/tests/agent -q -k cancel

# --- 3. SSE 夹具对账（S7 SSE RECORD PASS）----------------------------------
run_in "$ROOT/backend" .venv/bin/python -m app.scripts.record_sse --check
assert_matches 'SSE 夹具对账（app.scripts.record_sse --check：S7 SSE RECORD PASS）' 'S7 SSE RECORD PASS'

# --- 4. 前端协议单测（40 passed；缺 node_modules 时可选 SKIP+WARN）---------
frontend_npm_test

manuals
accept_finish
