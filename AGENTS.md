# AGENTS · 仓库 steering（导航指针，不是教程）

- 写/改页面：先读 `manual/SPEC.md`（六段模板与硬预算）和 `manual/TRAPS.md`（重放实测的环境陷阱）。
- 环境回滚：`docs/lab.md`（`lab save/diff/reset` 只回文件）；页面模板与 DoD：`humen-desicions/09-ablation-course.md` D46/D47。
- 验收/回归：`manual/ACCEPTANCE.md`（按级判据、级考核、失败时看哪）；结构审计 `python3 manual/shots/audit_book.py`。
- 教材生产流程：skill `tutorial-production`（写手 → 独立重放者 → 修复者 → 截图/验收；重放八类必查）。
- 术语：`GLOSSARY.md`（流程术语）；`L1–L4`/`A0–A9` 口径见 `manual/README.md` 与 D44。
- 提交边界：只提交本项目修正——`manual/`、`humen-desicions/`、`GLOSSARY.md`、`docs/`、`scripts/`；`atlas/`、`mermaid/` 是用户的探索，只留工作区、不提交。
- 硬规则 1：改完页面必须跑 `python3 manual/shots/audit_book.py`，末行 `页面：23/23 通过；README 坏链：0` 才算过。
- 硬规则 2：整栈验证用隔离 project + 端口覆盖，跑完 `docker compose down -v`；同一时间只留一套栈。
- 硬规则 3：先落盘再收尾——结论先写回文件，再跑下一项或结束会话。
