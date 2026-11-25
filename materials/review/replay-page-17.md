# 第 17 页独立重放报告（学生视角 · L3 级考核）

- 重放时间 2026-11-19 18:03–18:14；对象 `manual/page-17.md`。环境：`/tmp/replay-p17` = 工作区 rsync 副本（带 `backend/.venv`，剔除 `.env`/`.env.*`，未起任何容器、无模型 key，纯离线）；起点≈学生做完 P16 的回绿工作区（`.lab` 不入本页任何命令）。
- 只按页面文字操作，未读 writer 报告；引用核对直接查仓库源码/证据。
- **一句话结论：本页可整段照做，核心判据全部复现**——169 文件快照、`14 passed`、`S6 PASS`、插 4 行后 `5 failed, 9 passed` + S6 只红 `corrected`、probe `mismatch: 0`、`reset --yes` 回绿。共 6 个问题，仅 1 条高优先：`page-17.md:7`“成功态至今没有稳定复现过”引用真实、但结论与仓库 v2 证据冲突。L3 答案成立：**单元判据 + 失败矩阵抓到了，20 条语料 probe 没抓到**。

## 环节表（按页面顺序）

| # | 环节（页行） | 页面期望 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | `lab save p17-before`（:16-20） | `已保存快照 "p17-before"：169 个文件。`；同名被拒 | 刚好 169；重复 save exit 1，stderr 给“换一个名字：…-2 / 看 list” | ✓ |
| 2 | pytest 校正器层（:24-26, :47） | `14 passed in 0.11s` | `14 passed`（0.10–0.21s，页面已声明秒数变） | ✓ |
| 3 | 失败矩阵 `--check`（:30-32, :49-52） | corrected 期望/实际 result、16 码、`S6 PASS` | 逐字一致（仅行尾空格差异） | ✓ |
| 4 | 语料 grep（:36-40, :54-58） | corrected 行 + `11/9` 两对计数 | 计数正确；**retryable 两行顺序与页面相反**（实际 false 在前） | ⚠ P2 |
| 5 | 拆一刀插 4 行（:72-79） | 在唯一入口 `policy = contract.correction` 后、缩进 4 格 | 全仓该锚点仅 1 处；照抄即生效；4 行全按 4 格缩进也生效（续行在括号内，实测同样 `5 failed, 9 passed`） | ✓ 不卡 |
| 6 | pytest（:84, :90） | `5 failed, 9 passed in 0.14s` | `5 failed, 9 passed`（0.13–0.14s）；5 红=产出候选 2 条 + 拒答/崩溃原因 3 条（“产物不合契约”那条反而照绿） | ✓ |
| 7 | 矩阵 tail（:85, :91-95） | corrected 实际 `SQL_SYNTAX`、`FAIL: 1 项…` | 逐字一致；`PYTHONUNBUFFERED=1` 确为必需（去掉后 `tail -5` 看不到 FAIL 两行，实测） | ✓ |
| 8 | probe（:86, :96） | `{"total": 20, "mismatch": 0}` | 一致；页面 :99 明说“probe 照绿……不量校正做没做”✓，读码也确认只跑 guard/policy | ✓ |
| 9 | `reset` 不带 `--yes`（:101 语境） | 页面未要求（只贴带 --yes 的命令） | 只打印计划、exit 2、一个文件没动，并提示“再执行：… --yes” | ✓ `--yes` 提醒够 |
| 10 | `reset p17-before --yes`（:104, :110） | 末行 `现在工作区与快照 "p17-before" 完全一致。` | 一致；先自动拍 `pre-reset-…`（169 文件） | ✓ |
| 11 | 回绿（:105-112） | `14 passed`、`S6 PASS` | `14 passed in 0.11s`、`S6 PASS` | ✓ |
| 12 | D48 整段连续（:3） | 单终端从仓库根连跑、pwd 不变、无 exit 127 | 单 shell 连跑 12 条命令（+中间 1 次改文件）：pwd 恒为仓库根，无 127/not found；仅拆刀后 pytest 有意 exit 1 | ✓ |
| 13 | 跨页 P16（:3, :65）+“成功”栏（:44, :54-58） | 基线=回绿；统计块无“成功”栏 | P16 末=reset 回绿、`SQL_REJECTED` 不可重试两页同口径 ✓；四行只有 retryable/expect、语料无 success 字段 ✓；**若 P16 拆一刀未还原：step2 `1 failed, 13 passed`、无 S6 PASS、probe `mismatch: 3`** | ⚠ P4 |
| 14 | 引用核对（:7, :64） | PRD:13 / FINDINGS §3.1、§2 不是编造 | 16.31s、触发=true/纠正成功=false、5/5、4 次里 3 次均与原文一致；但“至今没有稳定复现”与 v2 冲突；`deliverable/evidence/` 路径不存在 | ⚠ P1、P3 |

## 问题清单

| page-17.md:行 | 原文（摘） | 问题 | 建议 |
|---|---|---|---|
| :7 | “……为什么‘纠正成功’不能写进判据——真实模型这边，成功态至今没有稳定复现过。” | 引用真实（PRD:13 记 v1“触发=true、纠正成功=false”；FINDINGS:24/28 记 5/5、:37 记“随后 3 次全成功”），但“至今没有稳定复现”强于证据：v2 已写“纠正成功态已复现（自然问数 + 故障注入）”（`deliverable/v2/README-v2.md:172`，证据 `deliverable/v2/evidence/v2-correct-success.sse`、`v2-natural-correct-success.sse`），只是“不能保证每次复现”。拿 v1 记录当“至今”结论已过时。 | 改成“v1 演示未复现；v2 有成功样本但触发依赖模型、不能保证每次复现——判据只能写多次采样+成功率与失败分类，不能写‘已修复’”。 |
| :55-56 | `11 "retryable": true` / `9 "retryable": false` | 逐字不符：`sort` 下 `"…: false"` 恒排在 `"…: true"` 前（f<t），实测先出 false 行、后 true 行；计数 11/9 正确。 | 对调两行（一行修改）。 |
| :64 | “（真实云端模型，视频证据在 `deliverable/evidence/`）” | 仓库无 `deliverable/evidence/`（`deliverable/` 只有 PRD、README、`v2/`；v1 的 `*_browser.sse`/视频未随仓库分发），学生照页面找不到证据。 | 改指 `deliverable/v2/evidence/`，或注明“v1 视频/SSE 不在仓库，离线可核对 `eval/FINDINGS.md`”。 |
| :3（前置） | “前置：本页一条服务都不用……命令都在仓库根目录……” | 没提醒“P16 的拆一刀必须先还原”。实测保留 P16 cut 时本页 step2/3/4 期望值全不成立（见环节 13），此时第 1 步快照还会把坏状态存成 p17-before。 | 前置加一句：“若第 16 页拆一刀还没还原，先 `scripts/lab reset p16-before --yes` 再开工。” |
| :16 + :104 | “（同名快照会被拒，重做本页就换个名字）” / `scripts/lab reset p17-before --yes` | 换名建议没让后面 reset 的名字跟着换：立即重做无害（实测仍回绿）；但若中间有其它白名单改动，照抄旧 reset 会回滚/删掉它们（实测删 2 个新文件、覆盖 2 个改动文件，仅靠 `pre-reset-…` 可救，页面未提恢复路径）。 | :16 补“（并把第 5 步 reset 的名字一起换）”，或 reset 用新名字。 |
| :34 | “前一条命令只打印结局和码，表里没有‘重试了几次’这一列” | 实际 `--scenarios` 打 4 列（场景/名称/期望/类别/失败步骤）；corrected 的“期望”是 `result` 不是码。后半句“无重试次数列”成立。 | 改“只打印期望结局和失败步骤；没有‘重试了几次’列”。 |
最该先修 3 条：**① `:7` 成功态断言（事实/引用，最误导）；② `:16`+`:104` 重做换名与 reset 名字脱节（会误回滚后续改动）；③ `:64` `deliverable/evidence/` 路径不存在（核心引用的证据无法核对）**。另 `:55-56` 只需对调两行，建议顺手修。

## 真输出摘录（原样，仅去行尾空格）
```text
已保存快照 "p17-before"：169 个文件。
lab: 同名快照 "p17-before" 已存在，不能覆盖（快照只读）。
换一个名字：scripts/lab save p17-before-2
---- 基线 ----
14 passed in 0.11s
S6 PASS
| `corrected` | 校正闭环成功 | result | - | - |
      9 "retryable": false      ← 页面把 11 true 写在前面
     11 "retryable": true
     11 "expect": "corrected"
      9 "expect": "rejected"
---- 拆一刀后（核心判据逐字复现）----
5 failed, 9 passed in 0.13s
  corrected            期望 result               实际 SQL_SYNTAX
== 2/2 错误码表（路线图点名的 7 个码必须都在） ==
  错误码表：16 个码，路线图要求的 7 个全在
FAIL: 1 项不符合预期
  - corrected: 应当成功，实际是 SQL_SYNTAX
{"total": 20, "mismatch": 0}
---- reset 回绿 ----
现在工作区与快照 "p17-before" 完全一致。
14 passed in 0.11s
S6 PASS
---- 反证 P4：P16 cut 未还原时 ----
1 failed, 13 passed in 0.14s
{"total": 20, "mismatch": 3}
```

## 核对通过（未列问题）

- 期望块除 :55-56 两行外逐字一致：`169 个文件`、`14 passed in 0.11s`、`S6 PASS`、`corrected` 行、`5 failed, 9 passed in 0.14s`（实测 0.13–0.14s，已声明秒数变）、probe、reset 末行与回绿两行。
- 契约：`contracts/errors.yaml:42-47` `max_attempts: 1` / `revalidate: true` / `revalidate_with: [guard, policy]`；`retryable: true` 恰好 6 个码（:61,67,98,116,122,128）；16 码、`SQL_REJECTED` 不可重试 ✓；`detail.original_sql` 由 `errors.py:344-359`/`graph.py` 落盘 ✓。
- `eval/build_datasets.py:175-184` 用 `retryable` 逐条校验 expect、对不上 `SystemExit` ✓；`test_corrector_refusal_keeps_the_original_error` 存在 ✓；probe 只量 guard/policy ✓。
- L3 口径：`manual/OVERVIEW.md:36` L3=P14–P17，本页确为末页；P14 黄金集 20 条、P15 baseline 10 题、P16 语料 20 条与 :115 对得上 ✓。
- “成功”栏确认没有：语料 20 行字段仅 `category/expect/expect_code/id/layer/query/retryable/sql`；四行统计只有 retryable/expect；`--scenarios` 行的“校正闭环成功”是夹具场景名，不是统计栏 ✓。

## 清理确认

- 已删 `/tmp/replay-p17`、`/tmp/d48.sh`、`/tmp/d48.log`；`/tmp` 无 lab 残留；未碰用户栈（未启停任何容器）。
- 本重放在用户工作区只新增本报告：`manual/page-17.md` 未改（sha `cfbc5474…` 未变）；本重放未创建/修改 `.lab`、`backend/uv.lock`（副本里 `backend/uv.lock` 全程 sha `742c2892…`）。**注意**：重放期间共享工作区出现并发会话产物——`.lab/`（18:12 起，含他人在跑的 `p19-before` 快照）与 `backend/uv.lock`（18:12 起被改写，现 sha `1889b84c…`）不是本重放产生，我未删/未还原它们（避免破坏另一重放/写作任务的现场与安全快照）。
