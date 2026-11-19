# 第 21 页重放报告（学生视角 · 独立重放）

> 环境：`/tmp/replay-p21` 全量 rsync 副本（无 `.lab`；保留 `backend/.venv` 与 `frontend/node_modules`），离线、无 MySQL/ES/栈/`.env`/模型 key，未启服务或容器；命令从仓库根单 shell 连续执行（D48）。只按页面文字操作，未读 writer 报告，未碰用户栈。重放期间页面被并行追加 1 行截图引用（L71，非本会话写入），本报告按该版本行号。

**一句话结论**：第 1–3 步基线与拆一刀逐字复现，`lab reset` 回绿、D48 连续执行通过，页面可重放；最该先修的是第 4 步 `make stage7` 的 `uv run` 按本机镜像重写 `backend/uv.lock`（1250 行）而 `lab reset` 救不回、却仍回显"完全一致"，以及拆一刀两处归一化的位置按字面搜不到、前置未写"承接第 20 页需已回绿"。共 7 条问题（高 1 / 中 2 / 低 4）。

## 环节表

| # | 环节 | 页面命令/判据 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | 第 1 步 快照+数两半（L16-32） | `scripts/lab save p21-before` + 内嵌 python | `已保存快照 "p21-before"：169 个文件。`；`/api/steps = 12 条件步骤 = ['correct_sql']`；`/api/errors = 16 类别 = ['failure', 'empty', 'cancelled']`；happy 23/12、llm_refusal 19/10；exit 0 | ✅ 逐字一致 |
| 2 | 第 2 步 对账（L34-38） | `record_sse --check`（`.venv/bin/python`，不经过 uv） | `S7 SSE RECORD PASS（14 个夹具与真实输出一致）`，exit 0 | ✅ 逐字一致 |
| 3 | 第 3 步 两组测试（L40-45） | `pytest tests/frontend/test_sse_fixtures.py -q` + `npm test` | `30 passed in 2.69s`；`Tests  40 passed (40)`；exit 0；`frontend/node_modules` 在，npm 离线可跑 | ✅ 计数逐字（耗时变） |
| 4 | 第 4 步（可选）stage7（L47-51） | `make stage7` | 6 段全绿：`45 passed`、`40 passed (40)`、`813 passed, 30 skipped in 33.12s`、末行 `S7 PASS`；wall 47.0s | ⚠️ 通过，有副作用（问题 1） |
| 5 | 拆一刀（L83-99） | 删 `_normalize` 两处 → `--check`（L88） | exit 1；10 条录制全红、4 条手写不红；happy 失配明细见摘录 | ⚠️ 结果对，定位描述不符（问题 2）；"别重录"陷阱与 4 条手写不红均有解释（L76/L94/L99） |
| 6 | 还原回绿（L101-110） | `reset p21-before --yes` + `--check`（`tail -1`） | `覆盖 1 个文件`；record_sse.py sha 复原；末行 S7 PASS；exit 0 | ⚠️ 回绿正确，期望输出为节选（问题 4） |
| 7 | D48 连续执行（L3） | 单 shell 从仓库根按页顺序连跑全页（含编辑/拆刀/还原） | PWD 恒 `/tmp/replay-p21`、无 exit 127/not found；save=0、step1=0、pytest=0、npm=0、ablated=1、reset=0、recheck=0 | ✅ D48 满足 |
| 8 | 跨页 + 栈（L3） | 承接第 20 页；本页应不需要栈 | 全部判据在进程内 TestClient/vitest 完成，无端口/容器/DB，离线通过；但第 20 页拆刀未还原时本页第 2 步单红 `cancelled.json` | ⚠️ 无栈 ✅；跨页前置未写（问题 3） |
| 9 | 运维边界（L79） | "应用层可观测 ≠ 运维可观测" | 核对：`/api/health` 在、`duration_ms` 只在 SSE 生成不落盘、后端无 metrics/tracing/结构化请求日志/告警依赖（grep 空）；QPS/P99/慢在哪 明确说不能答 | ✅ 边界写清 |

## 问题清单

| page-21.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| 47-51 | "前提：本机装了 `uv` 且 `backend/.venv` 依赖已同步" | **高**：`make stage7` 的 `uv run` 按本机 `~/.config/uv/uv.toml` 默认镜像重写 `backend/uv.lock`（pypi.org→清华镜像，1250 行、diff 3024 行）；`scripts/lab` 白名单不含它，跑完再 `reset p21-before` 回显"工作区已经和快照完全一致"，实际 uv.lock 仍脏（第 19 页报告问题 1 同源，仍未修） | Makefile 用 `uv run --frozen`，或页面注明跑完 `git checkout -- backend/uv.lock`；reset 说明写明"只覆盖白名单" |
| 85 | "把 `duration_ms` 改成 12.5 的那段、`detail.pop("request_id")` 的那段" | **中**：按字面搜不到——源码 L201 是 `payload["duration_ms"] = FIXED_DURATION_MS`（12.5 在 L39 常量），L205 是 `detail.pop("request_id", None)`；删错（删整段函数）会变成"录制失败"而非 10 条红 | 给 `record_sse.py:195-206` 行号或直接贴这两行原文 |
| 3 | "第 18–20 页分别守账号、策略、取消" | **中**：未写"承接第 20 页需已回绿"。实测把第 20 页拆刀（`CancelToken.cancel` 删 `_event.set()`）留在工作区，本页第 2 步 exit 1、只红 `cancelled.json` 一条，与本节 10 条红形态不同，学生会误判 | 前置加一句 `record_sse --check` 先 PASS 再开始本页 |
| 57-69、106-110 | 两处期望输出块 | **低**：实为节选但未标"（节选）"：save 少 2 行提示（位置/下一步）；reset 少 8 行非空输出（`已先拍安全快照 pre-reset-…`、`安全快照…`、`现在工作区…` 等）；第 20 页同类块有标注 | 两处补"（节选）" |
| 99 | "今天录出来是 `duration_ms`: 2.9"；`"request_id": "ed13…"` | **低**：单次观测写成定值：实测同机第一个 duration 帧 3.3、happy 的 11 个 duration 帧全与 12.5 不同（0.0–24.6）；request_id 每次随机 32-hex（本次 `9d5221…`） | 标"示例值，每次不同"，不给 2.9/ed13 |
| 47 | "全后端 813 条" | **低**：实际收集 843（813 passed + 30 skipped）；第 22 页 L11 写「全量后端测试共 843 条」 | 改"843 条（813 passed / 30 skipped）" |
| 3、40 | "没有就先 `npm install`，要联网" | **低**：与第 0/22 页统一用的 `npm ci` 不一致；缺 node_modules 时 `npm install` 会重解析并可能改写 `frontend/package-lock.json`（不在 lab 白名单）；且 `.venv` 来源（第 0 页 make install）未列 | 统一 `npm ci`，前置补 `backend/.venv` 来源 |

## 真输出摘录

基线（第 1–3 步，逐字）：
```text
/api/steps = 12 条件步骤 = ['correct_sql']
/api/errors = 16 类别 = ['failure', 'empty', 'cancelled']
happy: 23 条 progress 帧 / 12 个步骤名；只出现一次 correct_sql
llm_refusal: 19 条 progress 帧 / 10 个步骤名；只出现一次 correct_sql
S7 SSE RECORD PASS（14 个夹具与真实输出一致）
30 passed in 2.69s
     Tests  40 passed (40)
```
拆一刀（exit 1；10 条录制全红、4 条手写未出现在红名单）：
```text
FAIL: SSE 夹具与真实输出不同步：
  - happy.json 与今天的真实输出不同步
  - corrected.json …（共 10 条，含 cancelled.json）
请运行：cd backend && uv run python -m app.scripts.record_sse
```
失配明细（happy 24 帧不变，11 个带 duration 的 progress 帧全不同；cancelled 第 2 帧多 request_id）：
```text
frame[1]  step=extract_keywords  fixture.duration_ms=12.5  today.duration_ms=3.3
frame[19] step=validate_sql      fixture.duration_ms=12.5  today.duration_ms=24.6
cancelled[1] fixture detail={}   today detail={"request_id":"9d5221054ff34ac2ab847a10a70dd7fb"}
```
还原（`reset p21-before --yes` 节选 4 行；exit 0）：
```text
已恢复快照 "p21-before"：
  覆盖 1 个文件（内容不同）
安全快照："pre-reset-20261119-204502"（169 个文件）
现在工作区与快照 "p21-before" 完全一致。
```

## 清理确认

- `rm -rf /tmp/replay-p21` 及 `/tmp/p21_*`、`/tmp/uvlock.diff` 已删：副本 `.lab`（p21-before + 2 张 pre-reset）、`frontend/dist`、副本 uv.lock 改动随之清除。
- 源仓库只新增本报告；未写 `manual/page-21.md`（重放期间被并行追加 L71 截图引用，git diff 仅 +2 行，非本会话写入）、未改 `backend/uv.lock`（sha `742c28…` 前后一致）、未新建 `.lab`（用户 `.lab` 仍只有 p22-before）。
- 全程未起容器/栈、未连 MySQL/ES、未碰用户服务；未读 writer 报告。
