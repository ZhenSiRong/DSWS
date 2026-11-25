#!/usr/bin/env bash
# Dispatch wave 2 from a clean coordinator terminal (coord3).
# Creates a new Run, then tasks T1b, T4b, T5, T6, T7, T8 and starts workers.
set -uo pipefail

cd /home/zhensirong/VM-Share/DSWS-design/design || exit 1
LOG=/tmp/opencode/wave2.log
: > "$LOG"
say() { echo "$@" | tee -a "$LOG"; }

RUN_JSON=$(orca-ide orchestration run-create \
  --objective "DSWS 设计图集 · 第二批：T1/T4 重试 + T5–T8 手册" --json 2>>"$LOG")
RUN_ID=$(echo "$RUN_JSON" | jq -r '.result.run.id // empty')
if [ -z "$RUN_ID" ]; then
  say "FATAL: run-create failed"
  echo "$RUN_JSON" | tee -a "$LOG"
  exit 1
fi
say "RUN_ID=$RUN_ID"

make_task() {
  local spec="$1" title="$2"
  local out
  out=$(orca-ide orchestration task-create --spec "$(cat "tasks/$spec.md")" \
    --task-title "$title" --display-name "$title" --run "$RUN_ID" --json 2>>"$LOG")
  echo "$out" | jq -r '.result.task.id // empty'
}

T1=$(make_task T1-architecture "T1b 软件普查+架构图")
T4=$(make_task T4-deploy-test "T4b 部署测试图")
T5=$(make_task T5-manual-s0-s4 "T5 手册 S0-S4")
T6=$(make_task T6-manual-s5-s8 "T6 手册 S5-S8")
T7=$(make_task T7-front-atlas "T7 前置+图集叙事")
T8=$(make_task T8-ops-appendix "T8 运维+附录")
say "TASKS T1=$T1 T4=$T4 T5=$T5 T6=$T6 T7=$T7 T8=$T8"

dispatch_terminal() {
  local task="$1" term="$2" name="$3"
  local out
  out=$(orca-ide orchestration worker-start --task "$task" \
    --worktree path:/home/zhensirong/VM-Share/DSWS-design \
    --terminal "$term" --json 2>>"$LOG")
  local ok
  ok=$(echo "$out" | jq -r '.ok')
  say "DISPATCH $name ok=$ok dispatch=$(echo "$out" | jq -r '.result.dispatchId // .error.code')"
}

dispatch_agent() {
  local task="$1" name="$2"
  local out
  out=$(orca-ide orchestration worker-start --task "$task" \
    --worktree path:/home/zhensirong/VM-Share/DSWS-design \
    --agent opencode --json 2>>"$LOG")
  local ok
  ok=$(echo "$out" | jq -r '.ok')
  say "DISPATCH $name ok=$ok dispatch=$(echo "$out" | jq -r '.result.dispatchId // .error.code')"
}

# Existing qoder terminals, already in YOLO mode.
dispatch_terminal "$T1" term_f3618bea-e091-4568-b531-22afd77e2ae2 "T1b-qoder"
dispatch_terminal "$T4" term_3ff89f06-777a-4b3b-ae43-a182e180948d "T4b-qoder"

# New qoder terminal for the atlas narrative.
QOUT=$(orca-ide terminal create --worktree path:/home/zhensirong/VM-Share/DSWS-design \
  --title "qoder-atlas" --command "qoder --dangerously-skip-permissions" --json 2>>"$LOG")
QTERM=$(echo "$QOUT" | jq -r '.result.terminal.handle // empty')
if [ -n "$QTERM" ]; then
  orca-ide terminal wait --terminal "$QTERM" --for tui-idle --timeout-ms 60000 --json >>"$LOG" 2>&1
  dispatch_terminal "$T7" "$QTERM" "T7-qoder"
else
  say "WARN: qoder-atlas terminal not created; T7 falls back to opencode"
  dispatch_agent "$T7" "T7-opencode"
fi

# OpenCode workers.
dispatch_agent "$T5" "T5-opencode"
dispatch_agent "$T6" "T6-opencode"
dispatch_agent "$T8" "T8-opencode"

cat > inventory/orca-dispatch.json <<EOF
{
  "run_id": "$RUN_ID",
  "tasks": {
    "T1b": "$T1",
    "T4b": "$T4",
    "T5": "$T5",
    "T6": "$T6",
    "T7": "$T7",
    "T8": "$T8"
  },
  "qoder_terminal": "$QTERM"
}
EOF
say "DONE"
