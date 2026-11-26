#!/usr/bin/env bash
# toolbox/scripts/acceptance/level-l2.sh —— T2 验收线 L2（tutorial/ACCEPTANCE.md §3，page-10 – page-13）。
#
# 自动（只读/安全）：
#   1. preflight_stack：5 个长驻服务 running/healthy（只读 docker compose ps）
#   2. make docker-smoke（≤240 秒）：p13 的 8 步部署判据
#   3. python3 tutorial/shots/audit_book.py（24/24 通过）
# MANUAL（只打印，不执行）：p13 级考核「拆编排」——down / 删 init / 改 compose / lab reset。
#
# 栈没起时直接 SKIP（退出码 2）：不会跑到 docker-smoke（它内部第 1 步会 compose up）。
# 用法：bash toolbox/scripts/acceptance/level-l2.sh（任意 cwd；Makefile 目标 accept-l2）。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=common.sh
source "$ROOT/scripts/acceptance/common.sh"

accept_init L2 'page-10 – page-13（「换」真件 + p13 级考核：拆编排）'
require_root
require_python

manuals() {
  manual_section
  manual 'p10–p12 逐页对账：按 tutorial/ACCEPTANCE.md §3 的「你应该看到」人工判（405 行 / 1136341.10；S1 PASS；Decimal(1144735.50) 等）。'
  manual 'p13 级考核（拆编排，破坏性）：1) make docker-down（保留数据卷）；2) 打开 compose.yaml 删 init: 整段（全文件 4 处 condition: service_healthy 别瞎删），再删 backend 的 depends_on 里指向 init 的三行；docker compose config -q 应通过、只剩 5 个服务。'
  manual 'p13 级考核 3)：make docker-smoke → 第 3/8 步红（先轮询约 120 秒，别以为卡死）；no such service: init 是预期。'
  manual 'p13 级考核 4) 还原：toolbox/scripts/lab reset p13-before --yes → make docker-up → make docker-smoke 回到 DOCKER SMOKE PASS；整座城留着跑 L3。'
  manual '级考核期间不要同时跑本脚本的自动部分（栈会被拆）。'
}

if ! preflight_stack; then
  skip 'T2 教学栈预检（docker-smoke 前置）' "$STACK_PREFLIGHT_REASON"
  manuals
  accept_finish
fi

# --- 1. make docker-smoke（p13 判据；≤240s）--------------------------------
# 说明：docker-smoke 第 1 步是幂等的 `docker compose up -d --build`（p13 判据的一部分）；
# 上面 preflight 已经把「栈没起」拦成 SKIP，所以这里不会由脚本自己去起一套栈。
run_bounded 240 make -C "$ROOT" docker-smoke
case "$CAPTURE_RC" in
  0)
    assert_matches 'make docker-smoke（p13：DOCKER SMOKE PASS）' 'DOCKER SMOKE PASS'
    ;;
  124)
    fail 'make docker-smoke（≤240 秒）' \
      '超过 240 秒未结束；先看 docker compose ps -a / logs（page-13），别以为卡死'
    ;;
  *)
    fail 'make docker-smoke（≤240 秒）' \
      "退出码 ${CAPTURE_RC}，真实输出见上（对照 page-13「你应该看到」）"
    ;;
esac

# --- 2. 结构审计（离线只读）-------------------------------------------------
audit_gate

manuals
accept_finish
