# 第 20 页重放报告（学生视角 · 独立重放）

> 环境：`/tmp/replay-p20` 全量副本（删 `.git`/`.env`/`.lab`，保留 `backend/.venv`），无 MySQL/栈、无 `.env`/模型 key，全程离线、未起任何服务；只按页面文字操作，未读 writer 报告，未碰用户栈。行号按 20:43 追加截图行后的 `page-20.md`（112 行）。

**一句话结论**：核心判据全部逐字复现——`6 passed, 108 deselected`、`114 passed`、夹具两帧与 `cancelled.json` 逐字节相等、`S7 SSE RECORD PASS（14 …）`、拆一刀后 `2 failed`（`EMPTY_RESULT` vs `CANCELLED` + `KeyError: 'code'`）与 `record_sse` 红、`reset` 后回绿；拆一刀定位与"删行会 `IndentationError`"提示准确。主要问题是**缺"先还原第 19 页拆一刀"的前置检查**（不还原时本页第 2 步变 `3 failed, 111 passed`、第 3 步红在 `sql_rejected.json`），其次"第 21 页会把对账扩到 14 条"与实测矛盾。共 8 条问题（高 1 / 中 2 / 低 5）。

## 环节表

| # | 环节 | 页面命令/判据 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | 第 1 步快照（L16-20） | `scripts/lab save p20-before` | `已保存快照 "p20-before"：169 个文件。` exit 0（实际还回显"位置/下一步"2 行） | ✅ 数字逐字一致 |
| 2 | 第 2 步离线判据（L22-27） | `pytest tests/agent -q -k cancel`；`-q` 全量 | `6 passed, 108 deselected`；`114 passed`，均 exit 0 | ✅ 逐字一致 |
| 3 | 第 3 步夹具（L29-34） | 逐帧打印 + `record_sse --check` | 两帧逐字节=夹具；`S7 SSE RECORD PASS（14 个夹具与真实输出一致）` exit 0 | ✅ 逐字一致 |
| 4 | 第 4 步 stage6-ui（L36） | `make stage6-ui` | 未跑：可选、离线不自起栈；源码 `frontend/tests/s6_failures.mjs:185-186` 可证 `distinctSignatures`/`cancelled` 两字段与值 | ⏭️ 页面允许跳过 |
| 5 | 拆一刀（L71-92） | `CancelToken.cancel` 的 `set()`→`pass`；重跑第 2/3 步 | `2 failed, 4 passed, 108 deselected`；`EMPTY_RESULT` vs `CANCELLED`；`KeyError: 'code'`；`FAIL: … cancelled.json`，exit 1 | ✅ 逐字一致 |
| 6 | 还原回绿（L96-110） | `reset p20-before --yes` + 两条 | `覆盖 1 个文件（内容不同）`→`完全一致`；`6 passed`；`S7 … PASS`，exit 0 | ✅ 逐字一致 |
| 7 | D48 连续执行（L3/L22/L29） | 同一 shell 按页顺序连续跑第 1–3 步 | pwd 始终 `/tmp/replay-p20`、无 exit 127、全部 exit 0 | ✅ D48 满足 |
| 8 | 跨页衔接（第 19 页→本页） | 不还原第 19 页拆一刀直接跑本页 | 第 2 步 `3 failed, 111 passed`（本页预期 `114 passed`）；第 3 步红 `sql_rejected.json` 并提示重录；本页无前置检查句 | ⚠️ 见问题 1 |

## 问题清单

| page-20.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| 3 | "本页的判据一条服务都不用…" | **高**：缺"先还原第 19 页拆一刀"的检查。实测 `forbid_set_operations: false` 未还原时，本页第 2 步 `3 failed, 111 passed`、第 3 步红 `sql_rejected.json 与今天的真实输出不同步`（提示重录）；若在脏状态拍 `p20-before`，`reset` 也回不去（快照含脏契约） | 照第 17 页:3 加："先确认第 19 页拆一刀已 `scripts/lab reset p19-before --yes`；否则第 2 步会 `3 failed`、第 3 步红在 `sql_rejected.json`" |
| 94 | "**不要照着 `record_sse` 的提示去重录夹具**，那是修好代码后重新生成用的" | **中**：警告在、方向对，但没写后果。实测按提示 `uv run python -m app.scripts.record_sse`：`cancelled.json` 被重录成 **24 帧"正常完成"流**（`source: recorded`），`--check` 立刻**假绿**、判据失效；且 `uv run` 会重写 `backend/uv.lock`（实测 2,812 行 diff，`lab` 白名单不含——第 19 页:40 提过，本页没提） | 补一句"重录=用坏代码覆盖夹具，`--check` 反而变绿、判据失效；还原用 `scripts/lab reset`；提示里的 `uv run` 还会改 `backend/uv.lock`" |
| 29、65 | "用今天的代码重录这条取消路径"；"第 21 页会把这个对账扩到 14 条夹具" | **中**：对账范围说法与实测不符。`--check` 实际重录 9 个场景 + 取消路径、4 条手写只与源码常量比，**本页就已对账 14 条**（L51 输出即 14 条）；第 21 页不"扩"，是逐条拆覆盖/盲区（第 21 页:34 的写法才准确） | L29 改"重录 9 场景 + 取消路径（4 条手写比常量），14 条逐字节对账"；L65 改"第 21 页逐条拆解这 14 条的覆盖与盲区" |
| 44、46-47、78-92 | 各输出块 | **低**：未标"节选"却省略真实行：第 1 步还有"位置/下一步"2 行；pytest 有 `...... [100%]` 进度行；拆一刀有 `E - CANCELLED / E + EMPTY_RESULT` 与 traceback 行，实际顺序也是 FAILURES 在前、`2 failed…` 在末 | 输出块统一标"节选"（像 L103 那样），或补行 |
| 71 | "找到 `CancelToken.cancel`，把 `self._event.set()` 改成 `pass`" | **低**：同文件还有 `CancelRegistry.cancel`（L64），且未给行号，初学者可能改错方法。缩进提示**准确**：实测只删该行→`IndentationError: expected an indented block after function definition on line 36` | 补"`cancel.py:37`（`CancelToken.cancel` 方法体内唯一一行）" |
| 36 | "跑 `make stage6-ui`（…需 `uv`、Node、Chrome/Edge…）" | **低**：前置不全——还缺 `frontend/node_modules`（第 21 页:40 明写"没有就先 npm install，要联网"）；脚本 L68 的 `uv run` 会重写 `backend/uv.lock`，`lab` 救不回 | 补 node_modules 前置，并注"跑完 `git checkout -- backend/uv.lock`" |
| 3 | "只跑 `backend/` 里的离线测试和一条夹具回放" | **低**：未重申 `backend/.venv`（第 18/19 页:3 都写"第 0 页 make install 建好"）；缺 venv 时 `.venv/bin/python` 直接失败（exit 127），无补救指引 | 加"要用第 0 页建好的 `backend/.venv`（缺了先回第 0 页）" |
| 57 | `![第 20 页 …](images/page-20-cancel.png)` | **低（时序）**：落盘时该 PNG 不存在（同批 18/19 页截图也缺，疑似其它任务在补）；交付前若仍缺即断链 | 交付前确认 `manual/images/page-20-cancel.png` 已落盘 |

## 真输出摘录

第 2 步（逐字）：
```text
6 passed, 108 deselected in 0.71s
114 passed in 6.25s
```
第 3 步（逐字；两帧与 `fixtures/sse/cancelled.json` 逐字节相等）：
```text
data: {"type": "progress", "step": "correct_sql", "status": "skipped", "duration_ms": null}
data: {"type": "error", "code": "CANCELLED", "class": "cancelled", "message": "本次问数已被用户取消。", "step": null, "detail": {}}
S7 SSE RECORD PASS（14 个夹具与真实输出一致）
```
拆一刀（节选；末行提示正是 L94 警告所指）：
```text
E       AssertionError: assert 'EMPTY_RESULT' == 'CANCELLED'
FAILED tests/agent/test_orchestrator.py::test_cancel_stops_the_run_and_reports_cancelled
FAILED tests/agent/test_orchestrator.py::test_cancel_midway_stops_the_remaining_steps
E       KeyError: 'code'
2 failed, 4 passed, 108 deselected in 0.62s
FAIL: SSE 夹具与真实输出不同步：
  - cancelled.json 与今天的真实输出不同步
请运行：cd backend && uv run python -m app.scripts.record_sse
```
reset / 回绿（节选）：
```text
已恢复快照 "p20-before"：
  覆盖 1 个文件（内容不同）
现在工作区与快照 "p20-before" 完全一致。
6 passed, 108 deselected in 0.80s
S7 SSE RECORD PASS（14 个夹具与真实输出一致）
```
提示陷阱复测（问题 2 证据）：重录后 `cancelled.json` 变为 24 帧"正常完成"流，`--check` 输出 `S7 SSE RECORD PASS（14 个夹具与真实输出一致）`（假绿）。

## 清理确认

- 已 `rm -rf /tmp/replay-p20`（副本内 `.lab` 快照与 `uv run` 改写的 `backend/uv.lock` 随副本删除）；源仓库 `manual/page-20.md`、`.lab`、`backend/uv.lock` 均未改，未起任何容器/栈。
