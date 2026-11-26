#!/usr/bin/env bash
# doctor.sh —— 第 0 页的完成判据：一条命令把「工具 / 依赖 / 端口」判成 PASS/FAIL。
#
# 用法（在仓库根目录）：
#
#     make doctor                  # 等价于 bash toolbox/scripts/doctor.sh
#     bash toolbox/scripts/doctor.sh -v    # 每项多一行：实际输出 + 判定依据
#
# 为什么要它：第 0 页原本要人一条条敲 system/docker/uv/node/make/curl/python/端口，
# 敲完还得自己判断「这算不算过了」。判据散在 7 条命令里，第三方没法复核——
# SPEC「体验判据」第 5 条要求「别人照着页面文字能判断对错，不依赖作者在场」，
# 所以把散判据收成一条命令 + 一个总判定；输出里带版本号，别人照图就能对上。
#
# 只用本机已有工具（docker / uv / node / make / curl），不联网、不写文件。
# Windows 用 Git Bash 或 WSL；macOS 先敲 bash（默认 zsh 没有 /dev/tcp）。

set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 2

VERBOSE=0
[ "${1:-}" = "-v" ] && VERBOSE=1

pass=0
fail=0
hints=()

mark() { if [ "$1" -eq 0 ]; then printf '✓'; else printf '✗'; fi; }
tally() { if [ "$1" -eq 0 ]; then pass=$((pass + 1)); else fail=$((fail + 1)); fi; }

# 记一条失败修法：note <状态> <短名> <修法>
note() {
  if [ "$1" -ne 0 ] && [ -n "${3:-}" ]; then
    hints+=("$2：$3")
  fi
}

# 取字符串里第一段版本号：'Docker version 29.1.3, build ...' → 29.1.3
ver() { printf '%s' "$1" | grep -oE '[0-9]+(\.[0-9]+)+' | head -1; }

# ---------------- 工具 ----------------

tools=()

out=$(docker --version 2>&1)
st=$?
tools+=("$(mark $st) docker $(ver "$out")")
tally $st
note $st "docker" "没装。安装页 https://docs.docker.com/get-docker/"

docker version --format '{{.Server.Version}}' >/dev/null 2>&1
st=$?
tools+=("$(mark $st) daemon")
tally $st
note $st "docker daemon" "没跑起来。Docker Desktop 打开窗口；Linux 用 sudo systemctl start docker"

out=$(uv --version 2>&1)
st=$?
tools+=("$(mark $st) uv $(ver "$out")")
tally $st
note $st "uv" "没装。安装页 https://docs.astral.sh/uv/"

out=$(node -v 2>&1)
st=$?
tools+=("$(mark $st) node $out")
tally $st
note $st "node" "没装。安装页 https://nodejs.org/"

out=$(make --version 2>/dev/null | head -1)
st=$?
tools+=("$(mark $st) make $(ver "$out")")
tally $st
note $st "make" "没装 GNU Make。Windows 用 Git Bash 自带的 make"

out=$(curl --version 2>/dev/null | head -1)
st=$?
tools+=("$(mark $st) curl $(ver "$out")")
tally $st
note $st "curl" "没装 curl（多数系统自带）"

# ---------------- 依赖 ----------------

deps=()

PY=""
for cand in system/backend/.venv/bin/python system/backend/.venv/Scripts/python.exe; do
  if [ -x "$cand" ]; then PY="$cand"; break; fi
done

if [ -z "$PY" ]; then
  deps+=("✗ Python")
  tally 1
  note 1 "Python 环境" "system/backend/.venv 不存在。回仓库根目录跑 make install"
else
  pv=$("$PY" -V 2>&1 | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)
  req=$(grep -oE 'requires-python *= *">= *[0-9.]+"' system/backend/pyproject.toml 2>/dev/null |
    grep -oE '[0-9]+(\.[0-9]+)+' | head -1)
  req=${req:-3.12}
  newer=$(printf '%s\n%s\n' "$req" "$pv" | sort -V | tail -1)
  if [ "$newer" = "$pv" ]; then st=0; else st=1; fi
  deps+=("$(mark $st) Python $pv（要求 ≥$req）")
  tally $st
  note $st "Python $pv" "低于 pyproject 要求的 $req，重建 venv：rm -rf system/backend/.venv && make install"

  out=$(uv pip check --python "$PY" 2>&1)
  st=$?
  cnt=$(printf '%s' "$out" | grep -oE 'Checked [0-9]+ packages' | grep -oE '[0-9]+' | head -1)
  deps+=("$(mark $st) uv ${cnt:-?} 个包全兼容")
  tally $st
  note $st "uv 包" "有包装不上或互相冲突。跑 cd system/backend && uv sync --frozen 看第一段红字"

  (cd system/frontend && npm ls --depth=0 >/dev/null 2>&1)
  st=$?
  deps+=("$(mark $st) npm 依赖无缺失")
  tally $st
  note $st "npm 依赖" "缺包。跑 cd system/frontend && npm ci（别用 npm install）"
fi

# ---------------- 端口 ----------------

ports=()
for port in 3307 8000 8081; do
  if (echo >/dev/tcp/127.0.0.1/"$port") 2>/dev/null; then
    ports+=("✗ $port")
    tally 1
    note 1 "$port 被占用" "ss -tlnp | grep :$port 找到 PID，再 kill -15 <PID>"
  else
    ports+=("✓ $port")
    tally 0
  fi
done

# ---------------- 输出 ----------------

printf '工具  '
printf '%s  ' "${tools[@]}"
printf '\n依赖  '
printf '%s  ' "${deps[@]}"
printf '\n端口  '
printf '%s  ' "${ports[@]}"
printf '\n'

if [ "${#hints[@]}" -gt 0 ]; then
  printf '\n'
  for h in "${hints[@]}"; do
    printf '  ✗ %s\n' "$h"
  done
fi

total=$((pass + fail))
if [ "$fail" -eq 0 ]; then
  printf '%d/%d 通过\n' "$pass" "$total"
else
  printf '%d/%d 通过（%d 项没过）\n' "$pass" "$total" "$fail"
fi

if [ "$VERBOSE" -eq 1 ]; then
  printf '\n判定依据（-v）\n'
  printf '  docker  : docker --version / docker version --format {{.Server.Version}}\n'
  printf '  依赖    : %s -V；uv pip check；npm ls --depth=0 退出码\n' "${PY:-backend/.venv/bin/python}"
  printf '  端口    : /dev/tcp 连不上 127.0.0.1:3307|8000|8081 即为空闲\n'
fi

[ "$fail" -eq 0 ] || exit 1
exit 0
