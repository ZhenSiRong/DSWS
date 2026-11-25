#!/usr/bin/env bash
# scripts/acceptance/common.sh —— T2 级考核脚本（scripts/acceptance/level-lN.sh）公共库。
#
# 用法（在每个 level-lN.sh 里）：
#
#   ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
#   source "$ROOT/scripts/acceptance/common.sh"
#   accept_init L3 "page-14 – page-17（离线）"
#   require_root
#   require_backend_python
#   check_contains "生成层 pytest（122 passed）" '122 passed' \
#       "$BACKEND_PY" -m pytest backend/tests/generate -q
#   accept_finish
#
# 设计约束（对应 docs/acceptance-line.md）：
#   * 脚本可在任意 cwd 调用：自己算 ROOT，不依赖调用者。
#   * 只做只读/安全动作：不启动/停止 stack、不 down、不删卷、不改代码、
#     不写数据库。破坏性步骤只打印 MANUAL，绝不执行。
#   * 统一三态：PASS = exit 0，FAIL = exit 1，SKIP = exit 2（栈没起/前置缺失，
#     SKIP 不是通过）。最后一行固定 `LEVEL <级> PASS|FAIL|SKIP`。
#   * 检查 helper 一律返回 0 并自己记账（ok/fail/skip/warn），脚本可以顺序
#     调用，不会因为预期内的失败被 set -e 提前打断；set -e 只用来抓脚本
#     自身的意外错误（ERR trap 会兜底打印最终判定）。
#
# 本文件只定义函数与变量，不执行任何检查、不 cd、不碰 docker。
#
# 兼容性：不依赖 bash 4 的关联数组/大小写转换；细节列表用换行分隔字符串，
# 为了 macOS 自带 bash 3.2 也能跑（`set -u` 下空数组展开在 3.2 会报错）。

# --- 常量 -------------------------------------------------------------------

ACCEPT_AUDIT_EXPECT='页面：24/24 通过；README 坏链：0'
# 第 13 页 compose 的 5 个长驻服务（init 是一次性任务，不在此列）。
ACCEPT_STACK_SERVICES='mysql elasticsearch qdrant backend frontend'

# --- 状态（由 accept_init 初始化，检查 helper 维护）-------------------------

ACCEPT_LEVEL=''
ACCEPT_TITLE=''
ACCEPT_PASSED=0
ACCEPT_FAILED=0
ACCEPT_SKIPPED=0
ACCEPT_WARNED=0
ACCEPT_FAIL_DETAILS=''
ACCEPT_SKIP_DETAILS=''
ACCEPT_WARN_DETAILS=''
PYTHON=''
BACKEND_PY=''
CAPTURE_OUT=''
CAPTURE_RC=0
STACK_BASE_URL=''
STACK_PREFLIGHT_REASON=''

# --- 基础输出 ---------------------------------------------------------------

# log <文本>：进度/说明行（不是判定）。
log() {
  printf '[%s] %s\n' "${ACCEPT_LEVEL:-accept}" "$*"
}

# ok <名称> [细节]：一条自动检查通过。
ok() {
  local name="$1" detail="${2:-}"
  ACCEPT_PASSED=$((ACCEPT_PASSED + 1))
  if [ -n "$detail" ]; then
    printf '[%s]   OK    %s — %s\n' "$ACCEPT_LEVEL" "$name" "$detail"
  else
    printf '[%s]   OK    %s\n' "$ACCEPT_LEVEL" "$name"
  fi
  return 0
}

# fail <名称> [细节]：一条自动检查失败（本级最终 FAIL）。
fail() {
  local name="$1" detail="${2:-}"
  ACCEPT_FAILED=$((ACCEPT_FAILED + 1))
  _accept_append_detail ACCEPT_FAIL_DETAILS "$name${detail:+ — $detail}"
  if [ -n "$detail" ]; then
    printf '[%s]  FAIL   %s — %s\n' "$ACCEPT_LEVEL" "$name" "$detail"
  else
    printf '[%s]  FAIL   %s\n' "$ACCEPT_LEVEL" "$name"
  fi
  return 0
}

# skip <名称> [原因]：必须的前置没就绪（栈没起/缺 venv），本级最终 SKIP。
# 输出里保留字面量 `SKIP:`，便于 CI 和负责人一眼区分「没过」和「没判」。
skip() {
  local name="$1" reason="${2:-}"
  ACCEPT_SKIPPED=$((ACCEPT_SKIPPED + 1))
  _accept_append_detail ACCEPT_SKIP_DETAILS "$name${reason:+ — $reason}"
  if [ -n "$reason" ]; then
    printf '[%s] SKIP: %s — %s\n' "$ACCEPT_LEVEL" "$name" "$reason"
  else
    printf '[%s] SKIP: %s\n' "$ACCEPT_LEVEL" "$name"
  fi
  return 0
}

# skip_optional <名称> [原因]：可选子项没条件跑（8088 成熟版没起、缺 node_modules）。
# 计 WARN，不阻塞本级判定，但会在汇总里列出来，不假装跑过。
skip_optional() {
  local name="$1" reason="${2:-}"
  ACCEPT_WARNED=$((ACCEPT_WARNED + 1))
  _accept_append_detail ACCEPT_WARN_DETAILS "$name${reason:+ — $reason}"
  printf '[%s] SKIP(可选): %s%s（记 WARN，不阻塞本级判定）\n' \
    "$ACCEPT_LEVEL" "$name" "${reason:+ — $reason}"
  return 0
}

# warn <文本>：不影响判定的提醒。
warn() {
  ACCEPT_WARNED=$((ACCEPT_WARNED + 1))
  _accept_append_detail ACCEPT_WARN_DETAILS "$*"
  printf '[%s] WARN   %s\n' "$ACCEPT_LEVEL" "$*"
  return 0
}

# manual <步骤>：只打印必须人工/有破坏性的步骤，脚本绝不执行。
manual() {
  printf '[%s] MANUAL %s\n' "${ACCEPT_LEVEL}" "$*"
  return 0
}

# manual_section：MANUAL 段落标题。
manual_section() {
  log 'MANUAL（必须人工/有破坏性；脚本只打印，不执行）：'
  return 0
}

# --- 生命周期 ---------------------------------------------------------------

# accept_init <级> [标题]：初始化本级状态并打印表头。
accept_init() {
  ACCEPT_LEVEL="$1"
  ACCEPT_TITLE="${2:-}"
  printf '\n== T2 验收线 · LEVEL %s：%s ==\n' "$ACCEPT_LEVEL" "$ACCEPT_TITLE"
  log '只读/安全步骤自动跑；破坏性步骤只打印 MANUAL；栈没起 = SKIP（退出码 2），不是通过。'
  trap '_accept_unexpected_error' ERR
  return 0
}

# accept_finish：打印失败/跳过明细 + 汇总，最后一行 `LEVEL <级> <状态>`，按状态退出。
# PASS=0 / FAIL=1 / SKIP=2；FAIL 优先于 SKIP（有红就是红）。
accept_finish() {
  local status reason
  trap - ERR
  printf '\n'
  _accept_print_details '失败明细：' "$ACCEPT_FAIL_DETAILS"
  _accept_print_details '跳过明细（不计为通过）：' "$ACCEPT_SKIP_DETAILS"
  _accept_print_details '可选子项（SKIP/WARN，不影响判定）：' "$ACCEPT_WARN_DETAILS"
  if [ "$ACCEPT_FAILED" -gt 0 ]; then
    status='FAIL'
    reason='自动检查有 FAIL；先按上方失败明细修，再看 manual/ACCEPTANCE.md「失败时看哪」'
  elif [ "$ACCEPT_SKIPPED" -gt 0 ]; then
    status='SKIP'
    reason='必须的前置/环境未就绪；SKIP 不是通过（栈没起先按第 13 页起栈）'
  else
    status='PASS'
    reason='自动检查通过；MANUAL 步骤仍需人做，本行不代表整级验收完成'
  fi
  printf '汇总：%s passed / %s failed / %s skipped / %s optional-skipped\n' \
    "$ACCEPT_PASSED" "$ACCEPT_FAILED" "$ACCEPT_SKIPPED" "$ACCEPT_WARNED"
  printf '判定：%s — %s\n' "$status" "$reason"
  printf 'LEVEL %s %s\n' "$ACCEPT_LEVEL" "$status"
  case "$status" in
    PASS) exit 0 ;;
    SKIP) exit 2 ;;
    *) exit 1 ;;
  esac
}

# --- 前置检查 ---------------------------------------------------------------

# require_root：确认 ROOT 是本仓库根并切到仓库根。失败属于调用方式错误，直接退 2。
require_root() {
  if [ -z "${ROOT:-}" ]; then
    printf 'ERROR: require_root 之前脚本必须先设置 ROOT（仓库根）\n' >&2
    printf 'LEVEL %s SKIP\n' "${ACCEPT_LEVEL:-?}"
    exit 2
  fi
  if [ ! -f "$ROOT/Makefile" ] || [ ! -d "$ROOT/backend" ] || [ ! -d "$ROOT/manual" ]; then
    printf 'ERROR: %s 不是本仓库根（缺 Makefile / backend/ / manual/）\n' "$ROOT" >&2
    printf 'LEVEL %s SKIP\n' "${ACCEPT_LEVEL:-?}"
    exit 2
  fi
  if ! cd "$ROOT"; then
    printf 'ERROR: 无法进入仓库根 %s\n' "$ROOT" >&2
    printf 'LEVEL %s SKIP\n' "${ACCEPT_LEVEL:-?}"
    exit 2
  fi
  log "仓库根：$ROOT（已切到仓库根执行）"
  return 0
}

# require_python：宿主机可用的 Python 3.8+（audit / compose JSON 解析要用）。
# 找不到时记 SKIP 并结束本级（退出码 2）：不是产品红，是 page-00 前置缺。
require_python() {
  if [ -n "${PYTHON:-}" ] && [ -x "$PYTHON" ] \
    && "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
    return 0
  fi
  local candidate=''
  candidate="$(cd "$ROOT" && sh scripts/find-python.sh 2>/dev/null)" || candidate=''
  if [ -z "$candidate" ]; then
    candidate="$(command -v python3 2>/dev/null || true)"
  fi
  if [ -n "$candidate" ] \
    && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
    PYTHON="$candidate"
    log "Python：$PYTHON（$("$PYTHON" -V 2>&1)）"
    return 0
  fi
  skip 'Python 前置' '宿主机找不到可用的 Python 3.8+（page-00 前置，见 docs/SETUP-FROM-SCRATCH.md）'
  accept_finish
  return 1
}

# require_backend_python：离线判据都跑在 backend/.venv 里；缺了记 SKIP 并结束本级。
require_backend_python() {
  if [ -x "$ROOT/backend/.venv/bin/python" ]; then
    BACKEND_PY="$ROOT/backend/.venv/bin/python"
  elif [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
    BACKEND_PY="$ROOT/backend/.venv/Scripts/python.exe"
  else
    skip 'backend/.venv 前置' '缺少 backend/.venv：先按 page-00 跑 make install'
    accept_finish
    return 1
  fi
  log "后端解释器：${BACKEND_PY#"$ROOT/"}"
  return 0
}

# require_curl：只读 HTTP 检查要用；缺了记 SKIP 并结束本级。
require_curl() {
  if command -v curl >/dev/null 2>&1; then
    return 0
  fi
  skip 'curl 前置' '找不到 curl（page-00 前置）；无法做只读 HTTP 检查'
  accept_finish
  return 1
}

# --- 执行与断言 -------------------------------------------------------------
#
# run / run_in 只负责「回显命令 + 执行 + 把真实输出打到屏幕上」并存入
# CAPTURE_OUT / CAPTURE_RC，本身永远返回 0（不让 set -e 误伤）；
# 判定交给 assert_* / check_*。

# run <命令...>
run() {
  log "\$ $*"
  local rc=0
  CAPTURE_OUT="$("$@" 2>&1)" || rc=$?
  CAPTURE_RC=$rc
  _accept_print_output "$CAPTURE_OUT"
  return 0
}

# run_in <目录> <命令...>
run_in() {
  local dir="$1"
  shift
  log "\$ (cd $(_accept_short_dir "$dir") && $*)"
  local rc=0
  CAPTURE_OUT="$( cd "$dir" && "$@" 2>&1 )" || rc=$?
  CAPTURE_RC=$rc
  _accept_print_output "$CAPTURE_OUT"
  return 0
}

# run_bounded <秒> <命令...>：有 timeout/gtimeout 就带上，没有就直跑（会提示）。
run_bounded() {
  local limit="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    run timeout "$limit" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    run gtimeout "$limit" "$@"
  else
    log "注意：本机没有 timeout/gtimeout，以下命令不做超时限制"
    run "$@"
  fi
  return 0
}

# assert_ok <名称>：对上一次 run 的退出码做断言。
assert_ok() {
  local label="$1"
  if [ "$CAPTURE_RC" -eq 0 ]; then
    ok "$label"
  else
    fail "$label" "命令退出码 ${CAPTURE_RC}（真实输出见上）"
  fi
  return 0
}

# assert_matches <名称> <正则...>：要求退出码 0 且输出同时匹配所有正则。
assert_matches() {
  local label="$1"
  shift
  local regex missing='' joined=''
  if [ "$CAPTURE_RC" -ne 0 ]; then
    fail "$label" "命令退出码 ${CAPTURE_RC}（真实输出见上）"
    return 0
  fi
  for regex in "$@"; do
    if ! printf '%s' "$CAPTURE_OUT" | grep -Eq -- "$regex"; then
      missing="${missing} /${regex}/"
    fi
  done
  if [ -n "$missing" ]; then
    fail "$label" "输出里缺少：${missing# }"
  else
    ok "$label"
  fi
  return 0
}

# assert_last_contains <名称> <正则>：要求退出码 0 且最后一个非空行匹配正则。
assert_last_contains() {
  local label="$1" regex="$2" last=''
  if [ "$CAPTURE_RC" -ne 0 ]; then
    fail "$label" "命令退出码 ${CAPTURE_RC}（真实输出见上）"
    return 0
  fi
  last="$(printf '%s\n' "$CAPTURE_OUT" | sed -n '/[^[:space:]]/p' | tail -n 1)" || last=''
  if printf '%s' "$last" | grep -Eq -- "$regex"; then
    ok "$label"
  else
    fail "$label" "末行应匹配 /${regex}/，实际「${last}」"
  fi
  return 0
}

# check_ok <名称> <命令...>：run + 断言退出码 0。
check_ok() {
  local label="$1"
  shift
  run "$@"
  assert_ok "$label"
}

# check_contains <名称> <正则> <命令...>
check_contains() {
  local label="$1" regex="$2"
  shift 2
  run "$@"
  assert_matches "$label" "$regex"
}

# check_last_contains <名称> <正则> <命令...>
check_last_contains() {
  local label="$1" regex="$2"
  shift 2
  run "$@"
  assert_last_contains "$label" "$regex"
}

# check_ok_in <目录> <名称> <命令...>
check_ok_in() {
  local dir="$1" label="$2"
  shift 2
  run_in "$dir" "$@"
  assert_ok "$label"
}

# check_contains_in <目录> <名称> <正则> <命令...>
check_contains_in() {
  local dir="$1" label="$2" regex="$3"
  shift 3
  run_in "$dir" "$@"
  assert_matches "$label" "$regex"
}

# check_last_contains_in <目录> <名称> <正则> <命令...>
check_last_contains_in() {
  local dir="$1" label="$2" regex="$3"
  shift 3
  run_in "$dir" "$@"
  assert_last_contains "$label" "$regex"
}

# --- 共用检查 ---------------------------------------------------------------

# audit_gate：结构审计（离线只读）。失败即 LEVEL FAIL（记一条 fail）。
audit_gate() {
  local last=''
  run_in "$ROOT" "$PYTHON" manual/shots/audit_book.py
  last="$(printf '%s\n' "$CAPTURE_OUT" | sed -n '/[^[:space:]]/p' | tail -n 1)" || last=''
  if [ "$CAPTURE_RC" -eq 0 ] && [ "$last" = "$ACCEPT_AUDIT_EXPECT" ]; then
    ok "结构审计（${ACCEPT_AUDIT_EXPECT}）"
  else
    fail '结构审计（manual/shots/audit_book.py）' \
      "退出码 ${CAPTURE_RC}；期望末行「${ACCEPT_AUDIT_EXPECT}」，实际「${last}」"
  fi
  return 0
}

# frontend_npm_test：前端协议单测（40 passed）。缺 npm/node_modules 只记可选 SKIP+WARN。
frontend_npm_test() {
  if ! command -v npm >/dev/null 2>&1; then
    skip_optional '前端协议单测（cd frontend && npm test）' \
      '找不到 npm（page-00 前置）；本子项 SKIP'
    return 0
  fi
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    skip_optional '前端协议单测（cd frontend && npm test）' \
      '缺少 frontend/node_modules：先 cd frontend && npm ci；本子项 SKIP'
    return 0
  fi
  check_contains_in "$ROOT/frontend" '前端协议单测（40 passed）' '40 passed' npm test
  return 0
}

# --- Docker 栈预检（只读）---------------------------------------------------
#
# preflight_stack：确认第 13 页 compose 的 5 个长驻服务都在 running/healthy，
# 并把前端入口写进 STACK_BASE_URL。只跑 `docker compose ps`，绝不 up/down/build。
# 返回 0 = 栈就绪；返回 1 = 没就绪（原因在 STACK_PREFLIGHT_REASON，调用方记 skip）。
preflight_stack() {
  STACK_PREFLIGHT_REASON=''
  STACK_BASE_URL=''
  if [ -z "${PYTHON:-}" ]; then
    STACK_PREFLIGHT_REASON='内部错误：preflight_stack 之前必须先 require_python'
    log "$STACK_PREFLIGHT_REASON"
    return 1
  fi
  log '栈预检（只读）：docker compose ps；不启动/不停止/不删除任何东西'
  if ! command -v docker >/dev/null 2>&1; then
    STACK_PREFLIGHT_REASON='docker 不可用（page-00 前置）；需要先按第 13 页起栈（make docker-up）'
    log "$STACK_PREFLIGHT_REASON"
    return 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    STACK_PREFLIGHT_REASON='docker compose 不可用（需要 Docker Compose v2）；需要先按第 13 页起栈（make docker-up）'
    log "$STACK_PREFLIGHT_REASON"
    return 1
  fi
  if [ ! -f "$ROOT/.env" ]; then
    STACK_PREFLIGHT_REASON='缺少 .env：先 make docker-env，再按第 13 页起栈（make docker-up）'
    log "$STACK_PREFLIGHT_REASON"
    return 1
  fi
  # 与 compose / docker-smoke 同一份凭据：只读校验 .env 可解析（不改 .env）。
  if ! ( cd "$ROOT" && source scripts/export-docker-env.sh ); then
    STACK_PREFLIGHT_REASON='读取 .env 失败（scripts/export-docker-env.sh 退出非 0）：先 make docker-env，再按第 13 页起栈'
    log "$STACK_PREFLIGHT_REASON"
    return 1
  fi

  local raw='' rc=0
  log '$ docker compose ps -a --format json（只读）'
  raw="$( cd "$ROOT" && docker compose ps -a --format json 2>&1 )" || rc=$?
  if [ "$rc" -ne 0 ]; then
    _accept_print_output "$raw"
    STACK_PREFLIGHT_REASON="docker compose ps 失败（退出码 ${rc}）：需要先按第 13 页起栈（make docker-up）"
    log "$STACK_PREFLIGHT_REASON"
    return 1
  fi

  local verdict='' vrc=0
  # shellcheck disable=SC2086  # 服务名列表按空格拆分传给 python
  verdict="$( printf '%s' "$raw" | _accept_stack_verdict $ACCEPT_STACK_SERVICES )" || vrc=$?
  case "$vrc" in
    0) ;;
    2)
      STACK_PREFLIGHT_REASON="栈在跑但未全部 healthy（${verdict}）：等 10–30 秒重跑；需要先按第 13 页起栈（make docker-up）"
      log "$STACK_PREFLIGHT_REASON"
      return 1
      ;;
    *)
      STACK_PREFLIGHT_REASON="5 个长驻服务没有全部 running（${verdict}）：需要先按第 13 页起栈（make docker-up）"
      log "$STACK_PREFLIGHT_REASON"
      return 1
      ;;
  esac

  local base=''
  base="$(frontend_base_url || true)"
  if [ -z "$base" ]; then
    STACK_PREFLIGHT_REASON='栈在跑，但问不到 frontend 的宿主机端口（docker compose port frontend 80）：见第 13 页端口排查'
    log "$STACK_PREFLIGHT_REASON"
    return 1
  fi
  STACK_BASE_URL="$base"
  log "栈预检通过：${verdict}；前端入口 ${STACK_BASE_URL}"
  return 0
}

# frontend_base_url：前端入口的权威来源。
#   1. DOCKER_BASE_URL（显式覆盖，docker-smoke 同款）；
#   2. `docker compose port frontend 80`（Compose 实际发布端口，最准）；
#   3. .env 的 FRONTEND_HOST_PORT（shell 已导出的值优先，最后默认 8080）。
frontend_base_url() {
  if [ -n "${DOCKER_BASE_URL:-}" ]; then
    printf '%s\n' "${DOCKER_BASE_URL%/}"
    return 0
  fi
  local mapping='' port='' candidate='' from_env=''
  if command -v docker >/dev/null 2>&1; then
    mapping="$( cd "$ROOT" && docker compose port frontend 80 2>/dev/null )" || mapping=''
    mapping="${mapping%%$'\n'*}"
    port="${mapping##*:}"
    case "$port" in
      ''|*[!0-9]*) ;;
      *)
        printf 'http://127.0.0.1:%s\n' "$port"
        return 0
        ;;
    esac
  fi
  if [ -n "${FRONTEND_HOST_PORT:-}" ]; then
    from_env="$FRONTEND_HOST_PORT"
  elif [ -f "$ROOT/.env" ]; then
    from_env="$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}FRONTEND_HOST_PORT[[:space:]]*=[[:space:]]*//p' "$ROOT/.env" | tail -n 1)" || from_env=''
    from_env="${from_env%$'\r'}"
    from_env="${from_env%%[[:space:]]#*}"
    from_env="${from_env%"${from_env##*[![:space:]]}"}"
    from_env="${from_env#\"}"
    from_env="${from_env%\"}"
    from_env="${from_env#\'}"
    from_env="${from_env%\'}"
  fi
  candidate="${from_env:-8080}"
  case "$candidate" in
    ''|*[!0-9]*) return 1 ;;
    *)
      printf 'http://127.0.0.1:%s\n' "$candidate"
      return 0
      ;;
  esac
}

# --- 内部工具 ---------------------------------------------------------------

# _accept_append_detail <变量名> <一行>：换行分隔追加明细。
# 不用间接展开 `${!1}` / 数组：macOS 自带 bash 3.2 在 `set -u` 下对空数组
# 展开会报 unbound variable。这里只接受内部约定的三个变量名。
_accept_append_detail() {
  local name="$1" line="$2"
  case "$name" in
    ACCEPT_FAIL_DETAILS) ACCEPT_FAIL_DETAILS="${ACCEPT_FAIL_DETAILS}${line}"$'\n' ;;
    ACCEPT_SKIP_DETAILS) ACCEPT_SKIP_DETAILS="${ACCEPT_SKIP_DETAILS}${line}"$'\n' ;;
    ACCEPT_WARN_DETAILS) ACCEPT_WARN_DETAILS="${ACCEPT_WARN_DETAILS}${line}"$'\n' ;;
    *)
      printf 'ERROR: _accept_append_detail 未知明细变量：%s\n' "$name" >&2
      return 0
      ;;
  esac
  return 0
}

# _accept_print_details <标题> <换行分隔明细>
_accept_print_details() {
  local title="$1" text="${2:-}"
  [ -n "$text" ] || return 0
  printf '%s\n' "$title"
  printf '%s' "$text" | sed 's/^/  - /'
  return 0
}

# _accept_print_output <文本>：把子命令真实输出缩进显示；超长只留末尾 80 行。
_accept_print_output() {
  local out="$1" total=''
  [ -n "$out" ] || return 0
  total="$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
  case "$total" in
    ''|*[!0-9]*) total=0 ;;
  esac
  if [ "$total" -gt 80 ]; then
    printf '%s\n' "$out" | tail -n 80 | sed 's/^/    /'
    printf '    …（只显示末尾 80 行，共 %s 行）\n' "$total"
  else
    printf '%s\n' "$out" | sed 's/^/    /'
  fi
  return 0
}

# _accept_short_dir <绝对路径>：日志里把仓库根缩成 `.`。
_accept_short_dir() {
  local dir="$1"
  case "$dir" in
    "$ROOT") printf '.' ;;
    "$ROOT"/*) printf '%s' "${dir#"$ROOT/"}" ;;
    *) printf '%s' "$dir" ;;
  esac
}

# _accept_unexpected_error：ERR trap 兜底——脚本自身意外失败也要给最终判定行。
_accept_unexpected_error() {
  local rc=$?
  trap - ERR
  printf '[%s] INTERNAL ERROR：脚本意外失败（exit %s），见上方 stderr\n' \
    "${ACCEPT_LEVEL:-?}" "$rc" >&2
  ACCEPT_FAILED=$((ACCEPT_FAILED + 1))
  _accept_append_detail ACCEPT_FAIL_DETAILS "内部错误：脚本意外失败（exit ${rc}）"
  accept_finish
}

# _accept_stack_verdict：从 stdin 读 compose ps JSON，参数是必须 running 的服务名。
# 退出码 0 = 全部 running 且（有 healthcheck 的）healthy；1 = 缺/未 running；2 = 未 healthy。
_accept_stack_verdict() {
  "$PYTHON" -c '
import json
import sys

required = sys.argv[1:]
raw = sys.stdin.read().strip()
rows = []
if raw:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                data.append(json.loads(line))
    if isinstance(data, dict):
        data = [data]
    rows = data

state = {}
health = {}
for row in rows:
    name = row.get("Service") or row.get("Name") or ""
    if not name:
        continue
    state[name] = row.get("State") or ""
    health[name] = row.get("Health") or ""

missing = [name for name in required if state.get(name) != "running"]
unhealthy = [
    name
    for name in required
    if state.get(name) == "running"
    and health.get(name)
    and health.get(name) != "healthy"
]
if missing:
    present = ", ".join(name + "=" + state[name] for name in sorted(state) if state[name])
    print("缺少/未运行：" + ", ".join(missing) + "；当前容器：" + (present or "（无）"))
    sys.exit(1)
if unhealthy:
    print("未 healthy：" + ", ".join(unhealthy))
    sys.exit(2)
print(str(len(required)) + "/" + str(len(required)) + " 长驻服务 running/healthy")
sys.exit(0)
' "$@"
}
