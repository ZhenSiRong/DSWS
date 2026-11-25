# Orca 跨模型独立评审记录 01（codebuddy 只读）

> 来源：Orca worker `codebuddy`，**只读评审**（不改工作区）；对象 = `manual/SPEC.md` 与 `AGENTS.md` 对全书 23 页现状的漂移。
> 时点：2026-11-19；评审时仓库 HEAD `e3ce2c2`。性质：跨模型独立评审（与 DSH 内置 subagent 不同源），4 条发现均经人工复核属实。

## 4 条发现与修复

| # | 发现（评审原文位置） | 核实 | 修复结果 |
|:--:|:--|:--:|:--|
| 1 | `manual/SPEC.md:4,:27-41` 只声明交付 page-01…09 与「九页分工」，但仓库已 23 页（p00 + p10–p22） | 属实 | SPEC 顶部加「范围」行：本文件只约束 L1 九页（page-01…09），p00/p10–p22 见 `manual/ACCEPTANCE.md` 与 D46/D47；标题改「L1 九页分工与技术基线」 |
| 2 | `manual/SPEC.md:22` 要「完整可复制文件（≤40 行）」，与 `:85`「正文只留关键 3–5 行、完整文件放 `manual/appendix/code.md`」冲突，且该附录不存在 | 属实 | `:22` 区分「写文件用完整块（≤40 行）」与「正文讲解只留关键 3–5 行」；`:85` 补「附录尚未生成时，以页面内完整代码块为准」 |
| 3 | `AGENTS.md:6` 指向 skill `tutorial-production`，但 Orca worker（codebuddy/opencode/qoder）读不到 DSH skill | 属实 | 该行补 fallback：skill 不可用时按 `manual/review/REPLAY-TEMPLATE.md` + `manual/SPEC.md` + `humen-desicions/09-ablation-course.md` D46/D47 手工执行同一流程 |
| 4 | `AGENTS.md:10` 要求整栈验证后 `docker compose down -v`，与 `manual/ACCEPTANCE.md:29,39` 级考核「`make docker-down` 保留数据卷、整座城留着跑下一级」冲突 | 属实 | 该行改为：**隔离验证栈**跑完 `down -v`；**教材主栈**按 ACCEPTANCE 级考核保留（级考核用 `make docker-down`、不删卷）；同一时间只留一套栈 |

## 结果与边界

- 只改文档：`manual/SPEC.md`、`AGENTS.md`、`manual/review/`（本记录 + 索引）；未改任何页面正文/图/脚本。
- 验证：`python3 manual/shots/audit_book.py` → `页面：23/23 通过；README 坏链：0`；`make audit` → `AUDIT PASS：4/4`。
- 采纳率：4/4。评审不含页面正文事实核验（本轮只审 L1 规范与仓库 steering 的漂移）。

## Orca worker 用法一句话

- `orca-ide orchestration worker-start --agent codebuddy --spec '<任务：只读评审这些文件，逐条给 文件:行号 + 原文摘录 + 建议改法，不改工作区>'`：起一个跨模型只读评审者，主 agent 逐条复核属实后再改。
