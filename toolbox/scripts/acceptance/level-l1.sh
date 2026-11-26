#!/usr/bin/env bash
# toolbox/scripts/acceptance/level-l1.sh —— T2 验收线 L1（tutorial/ACCEPTANCE.md §2，page-00 – page-09）。
#
# 自动（只读/安全，不需要起停任何东西）：
#   1. make doctor（page-00 的 12/12：工具/依赖/端口；make 不可用则退回关键检查）
#   2. python3 tutorial/shots/audit_book.py（24/24 通过；README 坏链 0）
#   3. T2 教学栈 /api/health 只读探活（栈没起 = SKIP，退出码 2）
# MANUAL（只打印，不执行）：p01–p09 逐页判据 + 建成证明海报；手工 lab 栈。
#
# 用法：bash toolbox/scripts/acceptance/level-l1.sh（任意 cwd；Makefile 目标 accept-l1）。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=common.sh
source "$ROOT/scripts/acceptance/common.sh"

accept_init L1 'page-00 – page-09（「造」：十个零件 + 结构审计）'
require_root
require_python

# make 不可用/超时时的退路：只查关键工具（page-00 前置）存在。
key_tools_gate() {
  local missing='' tool
  for tool in docker uv node curl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing="${missing} ${tool}"
    fi
  done
  if [ -z "$missing" ]; then
    ok '关键工具预检（system/docker/uv/node/curl 都在 PATH 上）'
  else
    fail '关键工具预检' "缺：${missing# }（page-00 前置，装好后重跑）"
  fi
  return 0
}

manuals() {
  manual_section
  manual 'p01–p02 数据底座：容器 running；SELECT VERSION() 有输出且看不到 dw；5 张表、115 行、华北 19。'
  manual 'p03–p06 服务与检索：/health 回 {"ok":true}；两次请求一字不差；["华北","销售额"]；5 行带 JOIN 的 SELECT。'
  manual 'p07–p08 生成与执行：sales = 41099.5；12 条 progress + 1 条 result。'
  manual 'p09 浏览器入口：127.0.0.1:8081 问一句出 41099.5；L1 无「拆一刀」。'
  manual 'L1 另用 tutorial/completeness/poster-answer.png 对账（12 件 × 24 检验点）。'
  manual 'p01/p03/p09 的 lab-mysql / uvicorn / lab-nginx 是手工栈（3307/8000/8081）：T2 脚本不碰它们，做完按 page-00 收尾。'
}

# --- 1. page-00：make doctor（12/12）---------------------------------------
if command -v make >/dev/null 2>&1 && [ -f "$ROOT/Makefile" ]; then
  run_bounded 180 make -C "$ROOT" doctor
  case "$CAPTURE_RC" in
    0)
      assert_matches 'make doctor（page-00：12/12 通过）' '12/12 通过'
      ;;
    124)
      log 'make doctor 超过 180 秒未结束（本机 npm/uv 很慢）；退回关键检查'
      key_tools_gate
      ;;
    *)
      fail 'make doctor（page-00：12/12 通过）' \
        "退出码 ${CAPTURE_RC}；按上方 12 项明细修。若只是 3307/8000/8081 被第 1/9 页手工容器占着，先按 page-00 收尾（Ctrl+C、docker rm -f lab-mysql lab-nginx）再跑"
      ;;
  esac
else
  log '找不到 make / Makefile；退回关键检查（system/docker/uv/node/curl）'
  key_tools_gate
fi

# --- 2. 结构审计（离线只读）-------------------------------------------------
audit_gate

# --- 3. T2 教学栈只读健康检查（栈没起 = SKIP，不是假绿）-------------------
if preflight_stack; then
  require_curl
  run curl -fsS --max-time 10 "${STACK_BASE_URL}/api/health"
  assert_matches 'T2 教学栈 /api/health（只读探活）' '"status"[[:space:]]*:[[:space:]]*"ok"'
else
  skip 'T2 教学栈预检' "$STACK_PREFLIGHT_REASON"
fi

manuals
accept_finish
