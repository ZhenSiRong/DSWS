# AGENTS · 仓库 steering（导航指针，不是教程）

> 四类存放见 `PROJECT-MAP.md`：`tutorial/`（教程正典）/ `toolbox/`（制作工具）/ `system/`（示例系统）/ `materials/`（设计研究证据）。根目录不再保留兼容软链；所有路径直接用四类真实目录。

- 写/改页面：先读 `tutorial/SPEC.md`（六段模板与硬预算）和 `tutorial/TRAPS.md`（重放实测的环境陷阱）。
- 环境回滚：`materials/docs/lab.md`（`lab save/diff/reset` 只回文件）；页面模板与 DoD：`materials/humen-desicions/09-ablation-course.md` D46/D47。
- 验收/回归：`tutorial/ACCEPTANCE.md`（按级判据、级考核、失败时看哪）；结构审计 `python3 toolbox/shots/audit_book.py`。
- 教材生产流程：skill `tutorial-production`（写手 → 独立重放者 → 修复者 → 截图/验收；重放八类必查）；Orca worker（codebuddy/opencode/qoder）读不到 DSH skill，改按 `materials/review/REPLAY-TEMPLATE.md` + `tutorial/SPEC.md` + `materials/humen-desicions/09-ablation-course.md` D46/D47 手工执行同一流程。
- 术语：`GLOSSARY.md`（流程术语）；`L1–L5`/`A0–A9` 口径见 `tutorial/README.md` 与 D44/D50。
- 提交边界：只提交本项目修正——`tutorial/`、`materials/humen-desicions/`、`GLOSSARY.md`、`materials/docs/`、`toolbox/scripts/`、`.github/`；`atlas/`、`mermaid/` 是用户的探索，只留工作区、不提交。
- 硬规则 1：改完页面必须跑 `python3 toolbox/shots/audit_book.py`，末行 `页面：24/24 通过；README 坏链：0` 才算过；**改页面或契约还要跑 `make verify`（T0/T1，页面↔契约同步与离线命令，见 `materials/docs/verify-line.md`）**。
- 硬规则 2：**隔离验证栈**用隔离 project + 端口覆盖，跑完 `docker compose down -v`；教材主栈按 `tutorial/ACCEPTANCE.md` 级考核保留（级考核用 `make docker-down`、不删卷，整座城留着跑下一级）；同一时间只留一套栈。`lab` 只回白名单文件——数据库、容器卷、`uv.lock` 回不来，且别照 `record_sse` 提示重录（见 `tutorial/TRAPS.md` 6/7）。
- 硬规则 3：先落盘再收尾——结论先写回文件，再跑下一项或结束会话。**任务状态变更只经 `toolbox/scripts/task.py`**（台账 `toolbox/workflows/ledger.yaml` 为唯一真相源）；任务在 worktree 内推进；done 必过 review（或 `--force --reason` 留痕）；收尾跑 `task.py check` + `task.py render`。规格见 `toolbox/workflows/task-lifecycle.md`。
- 派单：同构重复 / 同工作区写文件 → 内置 subagent；跨模型独立评审、独立 worktree 长任务、需用户旁观 → Orca worker（`orca-ide orchestration worker-start`，免费 agent：opencode2/codebuddy/qoder）。
