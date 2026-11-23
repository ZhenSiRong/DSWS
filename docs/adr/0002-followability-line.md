# 教材可跟随性验收线：页面契约 + T0/T1/T2 三级校验

**状态**：accepted（2026-11-23）

## 背景

练本 24 页的判据都写在「你应该看到」里，但页面文字与仓库实现/环境之间没有机器核对的绑定：改代码不改页、命令/路径改名、截图/证据过期，学生照做就会断层。现有门禁补不上这一层——结构审计 `audit_book.py` 只查页面结构/格式/图引用/坏链，`make audit` 另查空白/锁文件/敏感串/台账；`manual/ACCEPTANCE.md` 的级考核是人工判据，每次提交跑不了。本决定新增一条「教材可跟随性验收线」：把页面里可机器核对的断言抽成**页面契约**，按 T0/T1/T2 三级触发，先挡断层，再逐步扩覆盖。使用与排查说明见 `docs/verify-line.md`。

与既有「漂移（跑偏）」区分：漂移指工作脱离判据/决策；本文的**断层（drift）**专指页面契约与仓库实现/环境不一致、导致照做失败。

## 决定

- **目标**：防五类断层——① 命令/路径失效；② 预期输出对不上；③ 代码改页面没改；④ 证据/截图过期假绿；⑤ 跨页前置断裂。
- **T0（提交前静态，<2s）**：`python3 scripts/verify.py --fast`；契约解析、页面注解 `<!-- verify: <marker> -->` 与契约双向同步、静态路径/符号、证据存在。由 `.githooks/pre-commit` 调用。
- **T1（离线回归，默认，<2min）**：`python3 scripts/verify.py`（`make verify` 同义）；T0 + 执行 `kind: offline` 命令并断言退出码/关键行；证据过期 warn，`--strict` 升 fail。
- **T2（全栈级考核）**：`scripts/acceptance/level-l{1..5}.sh`（`make accept-l1` … `make accept-l5`）；复用 `manual/ACCEPTANCE.md` 各级「级考核」——安全步骤自动、破坏性步骤标 `MANUAL`；需整栈已起，未起 `SKIP`（退出码 2）。
- **契约载体**：`manual/verify/contracts/page-XX.yaml`（每页一个）；页面内用 `<!-- verify: <marker> -->`（HTML 注释，渲染不可见）标可验块；契约只存关键行/数字，不存全量输出。
- **反假绿**：页面块里的命令与契约命令必须一致；故意改基线时页面、契约、证据同 commit 并说明原因。
- **覆盖顺序**：p17 试点 → p10–p13 → L1/L3/L4 → L5；先接「离线可跑」块，GUI/交互/真模型块标 `manual` 留给 T2。
- **CI**：本地优先（pre-commit + T1）；GitHub Actions 只跑 T0/T1（离线、无 secrets）；T2 本机/夜间。
- **失败策略**：T0/T1 fail-closed；证据过期先 warn，基线稳定后升 fail；失败不自动改任务台账，T2 夜间失败按流程经 `scripts/task.py` 记。
- **实现位置**：`scripts/verify.py`、`manual/verify/README.md`（schema 权威）、`manual/verify/contracts/`、`scripts/acceptance/level-l{1..5}.sh`、`Makefile`（`verify` / `accept-l*`）、`.githooks/pre-commit`、`.github/workflows/`。

## 被否决的选项

- **只靠 `make audit`**：结构审计 `audit_book.py` 只查页面结构/格式/图引用/坏链，`make audit` 另查空白/锁文件/敏感串/台账，都验不到页面里的命令能不能跑、输出对不对。否决。
- **全量 stdout diff**：页面命令输出含秒数、端口、文件数等随机器变化的量，全量比对假红多、维护成本高。否决；改为只断言退出码与关键行/数字。
- **把期望值复制进页面正文**：等于两处维护同一份断言，页面与副本必漂，且学生看到的正文与实际校验脱节。否决；期望值只进契约，页面命令与契约命令强制一致。
- **自动跑页面里所有 bash 块**：24 页上百个块中大量需要整栈、GUI 点选或真模型，无法在 T1 离线跑，全会变成假红。否决；按 `kind` 分层，离线块进 T1，其余留给 T2 人工判据。

## 后果

- 页面仍是内容唯一正典；契约只记录「怎么验」，不承载教学内容，也不成为第二事实源。
- 修订页面命令/输出时须同步改契约与证据（同 commit），否则 T0/T1 红——这是有意成本，用来换「照做不断层」。
- T1 只覆盖离线块，GUI/交互/真模型的假绿风险仍在，靠 T2 人工判据兜底；证据过期在升 fail 前仍有假绿窗口。
- T2 需整栈、未起即 SKIP，绿/红/SKIP 三态必须在报告里分开读，不能把 SKIP 当通过。
- 覆盖按顺序推进中，未接入页面暂不受这条线保护；实现到位前以接口文档为准，落地后以 `manual/verify/README.md` 与脚本实际行为为准。
