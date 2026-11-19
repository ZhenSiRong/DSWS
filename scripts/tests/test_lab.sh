#!/usr/bin/env bash
# scripts/tests/test_lab.sh —— scripts/lab 的纯 shell 回归测试
#
# 原则：
#   * 不碰真实仓库：在 mktemp 临时目录里造一棵最小树，把真脚本拷进去跑；
#   * 纯 shell + 核心工具（find/diff/cp/sha256sum|shasum），不需要 pytest/venv；
#   * 每条断言自己打印 ✔/✘，最后汇总；失败时保留临时目录供排查。
#
# 用法：bash scripts/tests/test_lab.sh

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LAB_SRC="$REPO/scripts/lab"

PASS=0
FAIL=0
TMP="$(mktemp -d "${TMPDIR:-/tmp}/lab-test.XXXXXX")" || { echo "mktemp 失败" >&2; exit 1; }
TREE="$TMP/repo"
OUT=""
RC=0

cleanup() {
  if [ "$FAIL" -eq 0 ]; then
    rm -rf -- "$TMP"
  else
    printf '\n失败 %s 项，临时目录保留用于排查：%s\n' "$FAIL" "$TMP"
  fi
}
trap cleanup EXIT

section() {
  printf '\n== %s ==\n' "$*"
}

ok() {
  PASS=$((PASS + 1))
  printf '  ✔ %s\n' "$*"
}

ng() {
  FAIL=$((FAIL + 1))
  printf '  ✘ %s\n' "$*"
}

dump_out() {
  printf '%s\n' "$OUT" | sed 's/^/      | /'
}

# 执行一条命令：输出进 OUT，退出码进 RC。
run() {
  OUT="$("$@" 2>&1)"
  RC=$?
}

assert_ok() {
  if [ "$RC" -eq 0 ]; then ok "$1"; else ng "$1（期望成功，实际退出码 $RC）"; dump_out; fi
}

assert_fail() {
  if [ "$RC" -ne 0 ]; then ok "$1"; else ng "$1（期望失败，实际退出码 0）"; dump_out; fi
}

assert_contains() {
  if printf '%s\n' "$OUT" | grep -qF -- "$2"; then
    ok "$1"
  else
    ng "$1（输出里找不到「$2」）"
    dump_out
  fi
}

assert_not_contains() {
  if printf '%s\n' "$OUT" | grep -qF -- "$2"; then
    ng "$1（输出里不应出现「$2」）"
    dump_out
  else
    ok "$1"
  fi
}

assert_file() {
  if [ -f "$2" ]; then ok "$1"; else ng "$1（文件不存在：$2）"; fi
}

assert_no_file() {
  if [ ! -e "$2" ]; then ok "$1"; else ng "$1（不应存在：$2）"; fi
}

assert_dir() {
  if [ -d "$2" ]; then ok "$1"; else ng "$1（目录不存在：$2）"; fi
}

sha_file() {
  "${SHA_BIN[@]}" "$1" | awk '{print $1}'
}

assert_sha_eq() {
  # $1=描述 $2=文件A $3=文件B
  if [ "$(sha_file "$2")" = "$(sha_file "$3")" ]; then
    ok "$1"
  else
    ng "$1（sha 不一致：$2 vs $3）"
  fi
}

assert_snapshot_count() {
  # $1=描述 $2=期望张数
  local n
  n="$(find "$TREE/.lab/snapshots" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d '[:space:]')"
  if [ "$n" -eq "$2" ]; then
    ok "$1"
  else
    ng "$1（期望 $2 张，实际 $n 张）"
  fi
}

# ---------------------------------------------------------------------------
# 0. 准备
# ---------------------------------------------------------------------------
section "0. 准备：最小树 + 拷贝真脚本"

if command -v sha256sum >/dev/null 2>&1; then
  SHA_BIN=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  SHA_BIN=(shasum -a 256)
else
  echo "需要 sha256sum 或 shasum" >&2
  exit 1
fi

assert_file "scripts/lab 存在" "$LAB_SRC"

mkdir -p "$TREE/scripts" "$TREE/contracts" "$TREE/backend/app/__pycache__" \
  "$TREE/backend/app/.venv" "$TREE/backend/app/node_modules" "$TMP/orig"
cp "$LAB_SRC" "$TREE/scripts/lab"
chmod +x "$TREE/scripts/lab"
LAB="$TREE/scripts/lab"

cat > "$TREE/contracts/schema.contract.yaml" <<'YAML'
contract: demo
version: 1
fields:
  - id: int
  - name: string
YAML
cat > "$TREE/compose.yaml" <<'YAML'
services:
  demo:
    image: busybox
YAML
cat > "$TREE/backend/app/x.py" <<'PY'
def add(a, b):
    return a + b
PY
# 这些必须被排除：密钥、缓存、依赖、符号链接式噪音
printf 'SECRET=contracts-dotenv\n' > "$TREE/contracts/.env"
printf 'ROOT_SECRET=root-dotenv\n' > "$TREE/.env"
printf 'cached\n' > "$TREE/backend/app/__pycache__/x.pyc"
printf 'venv\n' > "$TREE/backend/app/.venv/fake.py"
printf 'dep\n' > "$TREE/backend/app/node_modules/index.js"

cp "$TREE/contracts/schema.contract.yaml" "$TMP/orig/schema.contract.yaml"
cp "$TREE/compose.yaml" "$TMP/orig/compose.yaml"
cp "$TREE/backend/app/x.py" "$TMP/orig/x.py"
cp "$TREE/contracts/.env" "$TMP/orig/contracts.env"

# 预期跟踪 3 个文件（schema / compose / x.py），其余都被排除或不在白名单。
printf '  （临时树：%s）\n' "$TREE"

# ---------------------------------------------------------------------------
# 1. 基本命令 + 不创建 .lab
# ---------------------------------------------------------------------------
section "1. help / list / 未知命令（不得顺手创建 .lab/）"

run "$LAB" help
assert_ok "lab help 成功"
assert_contains "help 提到三条主命令" "save <名字>"
assert_contains "help 提到 reset --yes" "reset <名字> --yes"
assert_contains "help 提到安全规则" "安全快照"
assert_contains "help 提到 --no-safety" "--no-safety"
assert_no_file "help 不创建 .lab/" "$TREE/.lab"

run "$LAB" list
assert_ok "lab list 成功"
assert_contains "空仓库提示先 save" "还没有任何快照"
assert_no_file "list 不创建 .lab/" "$TREE/.lab"

run "$LAB" nope
assert_fail "未知命令失败"
assert_contains "未知命令给下一步" "scripts/lab help"

run "$LAB"
assert_ok "lab 不带参数打印帮助"
assert_contains "无参数输出用法" "save <名字>"

# ---------------------------------------------------------------------------
# 2. save：内容、manifest、排除规则、同名拒绝、坏名字
# ---------------------------------------------------------------------------
section "2. save / manifest / 排除规则"

run "$LAB" save s0
assert_ok "save s0 成功"
assert_contains "save 报文件数" "已保存快照 \"s0\"：3 个文件"
assert_contains "save 报跳过的不存在路径" "已跳过"

SNAP="$TREE/.lab/snapshots/s0"
TREE_DIR="$SNAP/tree"
assert_file "快照存了 contracts/schema.contract.yaml" "$TREE_DIR/contracts/schema.contract.yaml"
assert_file "快照存了 compose.yaml" "$TREE_DIR/compose.yaml"
assert_file "快照存了 backend/app/x.py" "$TREE_DIR/backend/app/x.py"
assert_file "manifest.json 存在" "$SNAP/manifest.json"

assert_no_file ".env 未入快照（contracts/）" "$TREE_DIR/contracts/.env"
assert_no_file ".env 未入快照（仓库根）" "$TREE_DIR/.env"
assert_no_file "__pycache__ 未入快照" "$TREE_DIR/backend/app/__pycache__/x.pyc"
assert_no_file ".venv 未入快照" "$TREE_DIR/backend/app/.venv/fake.py"
assert_no_file "node_modules 未入快照" "$TREE_DIR/backend/app/node_modules/index.js"
if [ -z "$(find "$SNAP/tree" \( -name '.env*' -o -name '__pycache__' -o -name '.venv' -o -name 'node_modules' \) -print -quit)" ]; then
  ok "快照树里没有任何排除项"
else
  ng "快照树里混进了排除项"
fi

if grep -qF '"file_count": 3' "$SNAP/manifest.json"; then ok "manifest 记录文件数 3"; else ng "manifest 文件数不对"; fi
if grep -qF '"path": "frontend/src", "kind": "dir", "present": false' "$SNAP/manifest.json"; then
  ok "manifest 记录不存在的白名单路径"
else
  ng "manifest 没记录不存在的白名单路径"
fi
if grep -qF '"git_head"' "$SNAP/manifest.json"; then ok "manifest 记录 git HEAD"; else ng "manifest 缺 git HEAD"; fi
if grep -qF '"sha256"' "$SNAP/manifest.json"; then ok "manifest 记录 sha256"; else ng "manifest 缺 sha256"; fi
if grep -qF '"excludes"' "$SNAP/manifest.json"; then ok "manifest 记录排除名单"; else ng "manifest 缺排除名单"; fi

run "$LAB" list
assert_ok "list 成功"
assert_contains "list 列出 s0" "s0"
assert_contains "list 显示文件数" "3 个文件"
assert_contains "list 显示 git HEAD" "git unknown"

SHA_MANIFEST_BEFORE="$(sha_file "$SNAP/manifest.json")"
run "$LAB" save s0
assert_fail "连续同名 save 被拒绝"
assert_contains "同名拒绝说明不覆盖" "已存在，不能覆盖"
if [ "$(sha_file "$SNAP/manifest.json")" = "$SHA_MANIFEST_BEFORE" ]; then
  ok "同名拒绝没有改动旧快照"
else
  ng "同名拒绝却改动了旧快照"
fi
assert_snapshot_count "同名拒绝后仍只有 1 张快照" 1

run "$LAB" save "../evil"
assert_fail "带斜杠的坏名字被拒绝"
assert_contains "坏名字给规则" "非法字符"
assert_no_file "坏名字没有写出目录" "$TREE/.lab/evil"
assert_snapshot_count "坏名字没有产生快照" 1

run "$LAB" save "a b"
assert_fail "带空格的坏名字被拒绝"
assert_contains "带空格名字给规则" "非法字符"

# ---------------------------------------------------------------------------
# 3. diff：新增 / 修改 / 删除三类变化
# ---------------------------------------------------------------------------
section "3. diff：新增 / 修改 / 删除"

# 修改：契约加一行；删除：backend/app/x.py；新增：contracts/new.contract.yaml
printf '# 拆一刀：删掉 name 字段\n' >> "$TREE/contracts/schema.contract.yaml"
rm -f "$TREE/backend/app/x.py"
printf 'contract: new\n' > "$TREE/contracts/new.contract.yaml"
# 排除项也改动/新增，diff 必须完全无视它们
printf 'SECRET=changed\n' > "$TREE/contracts/.env"
printf 'new-cache\n' > "$TREE/backend/app/__pycache__/new.pyc"
printf 'ROOT_SECRET=changed\n' > "$TREE/.env"
cp "$TREE/contracts/schema.contract.yaml" "$TMP/modified-schema.yaml"

run "$LAB" diff s0
assert_ok "diff 成功"
assert_contains "diff 报新增" "新增（快照里没有，工作区有）"
assert_contains "diff 列出新增文件" "contracts/new.contract.yaml"
assert_contains "diff 报修改" "修改（内容不同）"
assert_contains "diff 列出修改文件" "contracts/schema.contract.yaml"
assert_contains "diff 报删除" "删除（快照里有，工作区没有）"
assert_contains "diff 列出删除文件" "backend/app/x.py"
assert_contains "diff 有统一 diff 头" "+++"
assert_contains "diff 显示新增内容" "+contract: new"
assert_contains "diff 显示删除内容" "-def add(a, b):"
assert_not_contains "diff 无视 .env" ".env"
assert_not_contains "diff 无视 __pycache__" "__pycache__"
assert_contains "diff 末尾给 reset 提示" "scripts/lab reset s0 --yes"

# ---------------------------------------------------------------------------
# 4. reset 无 --yes：拒绝 + 一个文件都不动
# ---------------------------------------------------------------------------
section "4. reset 无 --yes：只打印计划，不动文件"

run "$LAB" reset s0
assert_fail "reset 无 --yes 被拒绝"
assert_contains "拒绝时说明没动文件" "没有 --yes，一个文件都没动"
assert_contains "计划里有删除" "删除（快照里没有"
assert_contains "计划里有写回" "写回"
assert_contains "计划里有覆盖" "覆盖"
assert_contains "拒绝时给确认命令" "scripts/lab reset s0 --yes"
assert_snapshot_count "拒绝时没拍安全快照" 1

assert_sha_eq "拒绝后修改的文件没被还原" "$TMP/modified-schema.yaml" "$TREE/contracts/schema.contract.yaml"
assert_file "拒绝后新增的文件还在" "$TREE/contracts/new.contract.yaml"
assert_no_file "拒绝后被删的文件没被写回" "$TREE/backend/app/x.py"

# ---------------------------------------------------------------------------
# 5. reset --yes：完全还原（sha 对比）+ 排除项不被碰 + 自动安全快照
# ---------------------------------------------------------------------------
section "5. reset --yes：还原 + 安全快照"

run "$LAB" reset s0 --yes
assert_ok "reset --yes 成功"
assert_contains "reset 报已恢复" "已恢复快照 \"s0\""
assert_contains "reset 报自动安全快照" "pre-reset-"
assert_contains "reset 收尾确认一致" "完全一致"

assert_sha_eq "被修改的契约还原到快照 sha" "$TMP/orig/schema.contract.yaml" "$TREE/contracts/schema.contract.yaml"
assert_sha_eq "被删除的 x.py 还原到快照 sha" "$TMP/orig/x.py" "$TREE/backend/app/x.py"
assert_sha_eq "未被改动的 compose.yaml 保持不变" "$TMP/orig/compose.yaml" "$TREE/compose.yaml"
assert_no_file "多余的新增文件被删除" "$TREE/contracts/new.contract.yaml"

assert_file "排除项 contracts/.env 仍在" "$TREE/contracts/.env"
if grep -qF 'SECRET=changed' "$TREE/contracts/.env"; then
  ok "排除项 contracts/.env 内容未被 reset 改回"
else
  ng "排除项 contracts/.env 被 reset 动了"
fi
assert_file "排除项根 .env 仍在" "$TREE/.env"
assert_file "排除项 __pycache__ 未被删除" "$TREE/backend/app/__pycache__/x.pyc"
assert_file "排除项 .venv 未被删除" "$TREE/backend/app/.venv/fake.py"
assert_file "排除项 node_modules 未被删除" "$TREE/backend/app/node_modules/index.js"

SAFETY_DIR="$(find "$TREE/.lab/snapshots" -mindepth 1 -maxdepth 1 -type d -name 'pre-reset-*' | head -n 1)"
if [ -n "$SAFETY_DIR" ]; then
  SAFETY="$(basename -- "$SAFETY_DIR")"
  ok "安全快照目录存在（$SAFETY）"
  assert_file "安全快照拍下了 restore 前的新增文件" "$SAFETY_DIR/tree/contracts/new.contract.yaml"
  if grep -qF '# 拆一刀' "$SAFETY_DIR/tree/contracts/schema.contract.yaml"; then
    ok "安全快照拍下了恢复前的改动"
  else
    ng "安全快照内容不是恢复前的现场"
  fi
  assert_no_file "安全快照同样不含 .env" "$SAFETY_DIR/tree/contracts/.env"
else
  ng "没有找到 pre-reset 安全快照"
  SAFETY=""
fi
assert_snapshot_count "现在共有 2 张快照（s0 + 安全快照）" 2

run "$LAB" diff s0
assert_ok "reset 后 diff 成功"
assert_contains "reset 后 diff 为空" "工作区与快照完全一致"

# ---------------------------------------------------------------------------
# 6. reset 无差异：直接返回，不再拍安全快照
# ---------------------------------------------------------------------------
section "6. 无差异时 reset 不重复拍快照"

run "$LAB" reset s0 --yes
assert_ok "无差异 reset 成功"
assert_contains "无差异 reset 提示不需要恢复" "不需要恢复"
assert_snapshot_count "无差异时不新增快照" 2

# ---------------------------------------------------------------------------
# 7. 事故恢复：从 pre-reset 安全快照回退 + --no-safety
# ---------------------------------------------------------------------------
section "7. 恢复事故处理：回退到安全快照"

if [ -n "${SAFETY:-}" ]; then
  run "$LAB" reset "$SAFETY" --yes --no-safety
  assert_ok "回退到安全快照成功"
  assert_contains "回退后一致" "完全一致"
  assert_file "回退后新增文件回来了" "$TREE/contracts/new.contract.yaml"
  assert_sha_eq "回退后契约是拆过的那版" "$TMP/modified-schema.yaml" "$TREE/contracts/schema.contract.yaml"
  assert_no_file "回退后被删的 x.py 仍缺失" "$TREE/backend/app/x.py"
  assert_snapshot_count "--no-safety 不新增快照" 2

  run "$LAB" reset s0 --yes --no-safety
  assert_ok "再从 s0 恢复成功"
  assert_sha_eq "最终契约回到原版" "$TMP/orig/schema.contract.yaml" "$TREE/contracts/schema.contract.yaml"
  assert_snapshot_count "--no-safety 再恢复仍不新增快照" 2
else
  ng "跳过事故恢复测试（没拿到安全快照名）"
fi

# ---------------------------------------------------------------------------
# 8. 错误路径：不存在/损坏的快照、参数错误
# ---------------------------------------------------------------------------
section "8. 错误信息要能指下一步"

run "$LAB" diff nope
assert_fail "diff 不存在的快照失败"
assert_contains "diff 不存在时提示 list" "scripts/lab list"

run "$LAB" reset nope --yes
assert_fail "reset 不存在的快照失败"
assert_contains "reset 不存在时提示 save" "scripts/lab save nope"

mkdir -p "$TREE/.lab/snapshots/broken"
run "$LAB" diff broken
assert_fail "缺 manifest 的损坏快照被拒绝"
assert_contains "损坏快照给出清理办法" "不完整"
rm -rf "$TREE/.lab/snapshots/broken"

run "$LAB" reset s0 --force
assert_fail "reset 不认识的选项失败"
assert_contains "不认识的选项给出支持列表" "只支持 --yes"

run "$LAB" reset
assert_fail "reset 缺名字失败"
assert_contains "reset 缺名字给例子" "scripts/lab reset"

run "$LAB" diff
assert_fail "diff 缺名字失败"
assert_contains "diff 缺名字给例子" "scripts/lab diff"

# ---------------------------------------------------------------------------
# 9. 空快照（S0「空起点」场景）
# ---------------------------------------------------------------------------
section "9. 空树 save：0 个文件的空起点快照"

mkdir -p "$TMP/blank/scripts"
cp "$LAB_SRC" "$TMP/blank/scripts/lab"
chmod +x "$TMP/blank/scripts/lab"
run "$TMP/blank/scripts/lab" save s-empty
assert_ok "空树 save 成功"
assert_contains "空快照报 0 个文件" "0 个文件"
run "$TMP/blank/scripts/lab" list
assert_contains "空快照可列出" "s-empty"
run "$TMP/blank/scripts/lab" reset s-empty --yes
assert_ok "空快照 reset 成功"
assert_contains "空快照 reset 提示一致" "完全一致"

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
printf '\n=========================================\n'
if [ "$FAIL" -eq 0 ]; then
  printf '全部通过：%s 项检查\n' "$PASS"
  exit 0
else
  printf '失败 %s 项 / 通过 %s 项\n' "$FAIL" "$PASS"
  exit 1
fi
