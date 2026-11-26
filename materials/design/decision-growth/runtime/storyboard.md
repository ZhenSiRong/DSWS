# 运行链 · Storyboard（CP1 一页 brief）

> 教学编撰声明（D57）：生长时间线 v1→v4 是**教学重构**，不是 commit 历史；终态结论全部由代码/契约/真跑证据锚定。

**链名**：运行链（图 27 · `materials/design/diagrams/05-deployment/`）

**核心问题（一句话）**：服务启动，靠盲等，还是靠健康条件和失败停点？——答案：不是盲等，是条件轮询 + 超时上限；失败停在下游之前。

## Claim 表

| id | 主张 | 类型 | status |
|---|---|---|---|
| RUN1 | 按健康条件依赖，不按启动顺序 | invariant | verified |
| RUN2 | init 一次性，退出 0 才放行 backend | decision | verified |
| RUN3 | 失败停在下游之前（三级停点） | invariant | verified |
| RUN4 | 起得来 ≠ 部署好：smoke 8 步逐条验 | descriptive | verified |
| RUN5 | init 不是纯 sleep：2s 轮询 + 180s 上限 [当前值] | descriptive | verified |
| RUN6 | 失败停点注入已实证（scale=0 → init Exited(1)，下游未启动） | descriptive | verified |

（详见 `claims.yaml` / `claims.md`。RUN2–RUN4 证据为 page-13 重放记录；2026-11-27 真栈 probe 补验失败停点与 180s 超时，RUN5/RUN6 转正。）

## 候选与剪枝（决策空间，[重构] 表示重构的候选，不是真实历史）

| 候选 | 被什么打脸 / 留下 |
|---|---|
| C1 [重构] sleep 30 盲等 | **杀**：慢、假绿——库没起来也可能继续，失败后不知道停在哪（data.yaml v1 fail） |
| C2 [重构] depends_on 顺序就算依赖完成 | **杀**：Started ≠ healthy；init 可能比库快、backend 没初始化就接客（page-13 对账） |
| C3 [重构] healthcheck 有了就算部署好 | **杀**：up 成功 ≠ 部署好；init 失败/一次性没验、端口/SSE 没测（page-13 拆一刀「假象」：全 healthy 也没 init） |
| C4 [当前] 条件化依赖 + 失败停点 + init 一次性 + smoke 8 步灰度验收 | **留**：compose config 通过（本轮实跑）；page-13 记录 init Exited (0)、DOCKER SMOKE PASS；拆一刀删 init 在 3/8 红 |

参数只标 [当前值]：轮询 `interval_s=2.0`、每存储 `timeout_s=180.0`（`docker_init.py:87`）；启动耗时不是设计承诺。

## 未知 / 反悔点

- **[已实证]** 真栈失败停点注入（RUN6，2026-11-27）：--scale mysql=0 → init 等待超时 Exited(1)、backend/frontend 从未启动，恢复后 20s 全绿；nuance——scale=0 时 compose 把 service_healthy 当空满足放行 init，停点由 docker_init 的 180s 超时兜底。
- **[当前值]** 2s 轮询 / 180s 上限可被 `--timeout` 覆盖，慢机器上可能不够——不是原则。
- 反悔点：condition 降级成 service_started（RUN1 倒）；init 改常驻或 restart: always（RUN2 倒）；smoke 裁掉 3/8 的 init 退出码检查（RUN4 倒）。

## 两页布局（D57 版式）

- **左页**：2×2 四格、Z 字阅读 v1→v2→v3→v4。每格「做法 + 被什么打脸 + 补上了什么」：v1 sleep 30 → v2 depends_on 顺序 → v3 healthcheck → v4 失败停点 + 灰度验收（标「当前」）。
- **右页**：终态设计 + 证据 + 可重跑命令。上半：图 27（启动顺序与失败停点，figcap 原文）+ 一行链路「三存储 healthy → init 退出 0 → backend healthy → frontend」；下半：证据 E1 compose config 通过（本轮实跑）、E2 init Exited (0)（page-13 记录）、E3 smoke 8 步（page-13 记录）+ 拆一刀红法（3/8）；右下固定 `[未知]` 框（nuance：compose 空满足 + 启动耗时不是承诺）。

## 请用户决定（CP1）

1. 真栈失败注入已实证（2026-11-27，--scale mysql=0）；RUN3/RUN6 已升级为实证。余下可选：完整 `make docker-smoke` 8 步留档。
2. 左页 v4 格要不要把「拆一刀删 init 的假象」（全 healthy 也没 init）直接画进去？它比正面描述更有打脸感。
3. smoke 8 步在右页是全表还是只挑 3/8、5/8、7/8 三条代表？全表更完整，代表三条更聚焦。
