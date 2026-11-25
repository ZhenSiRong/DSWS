#!/usr/bin/env bash
# scripts/acceptance/level-l5.sh —— T2 验收线 L5（manual/ACCEPTANCE.md §6，page-23）。
#
# 自动（只读/安全）：
#   1. preflight_stack：5 个长驻服务 running/healthy（只读 docker compose ps）
#   2. cd frontend && npm test（40 passed；缺 node_modules 记可选 SKIP+WARN）
#   3. 成熟版入口 8088 只读探活（没起 = 可选 SKIP，不阻塞）
#   4. 教学版 POST /api/query（只读查询，≤30 秒）结果含 41099.5 / 41,099.5
# MANUAL（只打印，不执行）：浏览器判据；p23 级考核「把 8088 换回 17 行 HTML」+ 还原。
#
# 用法：bash scripts/acceptance/level-l5.sh（任意 cwd；Makefile 目标 accept-l5）。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=common.sh
source "$ROOT/scripts/acceptance/common.sh"

accept_init L5 'page-23（「装」体验层：成熟版 / 教学版同一判据）'
require_root
require_python

manuals() {
  manual_section
  manual '浏览器判据（page-23「动手」）：8088 成熟版问「华北销售额」→ 结果表 41099.5（无千分位）；8080 教学版同一问题 → 41,099.5（改过 .env 的 FRONTEND_HOST_PORT 就用你的端口）。'
  manual 'p23 级考核（拆一刀，破坏性）：1) docker rm -f lab-mature；2) mkdir -p lab-mature，写 29 行 index.html（照 page-23「拆一刀」第 2 步抄：form+pre 骨架不变，只补 POST /api/query、fetch 读流、rows[0][0] 三处接线）；3) 用教学版镜像的 nginx 占 8088 并进 compose 网络：docker run -d --name lab-mature --network shopkeeper-rebuild_default -p 127.0.0.1:8088:80 -v "$PWD/lab-mature/index.html:/usr/share/nginx/html/index.html:ro" shopkeeper-rebuild/frontend:local；4) 强刷 8088 问一句 → pre 里闪过步骤 id，约 6 秒停在 41099.5。'
  manual 'p23 还原：docker rm -f lab-mature && rm -rf lab-mature；8088 打不开属预期，8080 教学版不受影响（重问一句 → 41,099.5）。'
  manual '本脚本的 8080 API 检查等价于「同一问题同一个数」；成熟版标题/结果表/12 节点流程图与 17 行页面渲染必须人工看。'
}

if ! preflight_stack; then
  skip 'T2 教学栈预检' "$STACK_PREFLIGHT_REASON"
  manuals
  accept_finish
fi

require_curl

# --- 1. 前端协议单测（40 passed）-------------------------------------------
frontend_npm_test

# --- 2. 成熟版入口 8088（可选：没起就 SKIP 子项，不阻塞）--------------------
mature_frontend_probe() {
  local code='' rc=0
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8088 2>/dev/null)" || rc=$?
  if [ "$rc" -ne 0 ] || [ -z "$code" ] || [ "$code" = '000' ]; then
    skip_optional '成熟版入口 8088（curl）' \
      '8088 没起（page-23 用 docker run lab-mature 提供）；未起 = 可选 SKIP，不阻塞'
    return 0
  fi
  case "$code" in
    2*)
      ok "成熟版入口 8088（HTTP ${code}）"
      ;;
    *)
      fail '成熟版入口 8088' \
        "有响应但 HTTP ${code}：502 常见于容器没进 compose 网络、或 nginx 反代配错（page-23 排查）"
      ;;
  esac
  return 0
}
mature_frontend_probe

# --- 3. 教学版 POST /api/query（只读查询，≤30 秒；结果含 41099.5）----------
run curl -fsS --max-time 30 -X POST "${STACK_BASE_URL}/api/query" \
  -H 'Content-Type: application/json' --data '{"query":"华北销售额"}'
case "$CAPTURE_RC" in
  0)
    assert_matches '教学版 POST /api/query（结果含 41099.5 或 41,099.5）' '41099\.5|41,099\.5'
    ;;
  28)
    fail '教学版 POST /api/query（≤30 秒）' \
      '30 秒内没拿到结果：先看栈健康、数据库是否为 fixtures/dw.sql 演示集（page-13/page-23）'
    ;;
  *)
    fail '教学版 POST /api/query（≤30 秒）' \
      "退出码 ${CAPTURE_RC}（-f 遇 HTTP ≥400 会非 0）：真实输出见上；排查见 page-23「失败时看哪」"
    ;;
esac

manuals
accept_finish
