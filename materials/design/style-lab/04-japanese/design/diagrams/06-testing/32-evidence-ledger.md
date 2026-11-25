# 32 · 证据台账：已验证 / 推断 / 未验证

**一句话**：每条结论只允许三种状态——本机跑过（✅）、从结构推导（🟡）、环境不具备（⚪）；三类证据都要写进图说明，缺口也要写出来。

**这张图回答**：图里的结论从哪来？哪些能在本机复现？哪些只是引用他机记录？最终汇到哪里？

**图例**：绿色=已验证；橙色=推断；灰色=未验证 / 本机边界；蓝色=来源与去向。

**关键元素**：
- ✅ 已验证：`--dry-run` 计数（`facts.md`，2026-10-27 本机）；S0–S7 门禁记录（`SETUP-FROM-SCRATCH.md` §7，Windows 2026-10-26 / Linux 2026-10-25）；旧系统计数未变（§5）；契约文件与 `compose.yaml` 的字段。
- 🟡 推断：`782 passed / 31 skipped`（README 与 HANDOFF 声称，本工作树未跑）；241 条写入总数（按 `plan.counts()` 公式推导，非 `--fresh` 实测）；`SETUP-FROM-SCRATCH.md` §3 的 `665 passed`（与 README 冲突，已过期）。
- ⚪ 未验证：Docker 全栈（本工作树 `docker ps` 返回 `permission denied ... /var/run/docker.sock`）；真实 LLM 端点与真实校正通路；本机 `--fresh` 写三存储；本机前端构建与浏览器验收；真实召回接入 `/api/query`。
- 去向：每张图的「证据」段 → `catalog-deploy-test.md` → 书稿 / PDF / QA 报告；未验证项必须在 QA 报告里保留。

**证据**：
- `design/inventory/facts.md` §9：已验证 / 未验证清单（本设计工作树的共享底稿）。
- `README.md` L25–L29：782 passed / 31 skipped、前端 40、SSE 夹具 14；验收前置。
- `docs/DOCKER-HANDOFF.md` §5.1、§6：他机 782 passed / 31 skipped 与 `DOCKER SMOKE PASS` 记录。
- `docs/SETUP-FROM-SCRATCH.md` §7 L1024–L1112：本机已验证 / 未在本 shell 端到端验证 / 明确边界。
- `docs/SETUP-FROM-SCRATCH.md` §2.4 L320–L334：当前审计账户没有 Docker socket 权限。
- 本次命令：`docker ps` → `DOCKER_DENIED`；`google-chrome` 存在；`python3 --version` = 3.12.3（渲染环境可用）。

**边界**：本图只描述本设计工作树的证据强度，不代表项目整体的验证状态。HANDOFF 记录 Docker smoke 在他机通过，但本工作树无法复跑，因此仍归入 ⚪；引用他机结果时必须在文字里写明来源，不能升级成 ✅。
