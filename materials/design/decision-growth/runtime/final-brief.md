# 运行链 · Final brief（CP2）

> 教学编撰声明（D57）：生长时间线是教学重构，非 commit 历史；结论均由代码/契约/真跑证据锚定。

## 结论（3 句）

启动不是「等」，是每一级给出可判定条件（healthy / 退出 0），失败停在下游之前：三存储 healthy → init 退出 0 → backend healthy → frontend。init 是一次性初始化（等存储、开只读账号、校验元知识），`restart: "no"`、非零即失败；它内部是 2s 条件轮询 + 180s 上限 [当前值]，不是纯 sleep。「起得来」不等于「部署好」——smoke 8 步把 health、init 退出码、端口、SSE 缓冲、只读账号逐条单验。

## 产物链接

- 渐进稿：[`spread.png`](spread.png)（固定画布 1540×1120 ×2（跨页 3200×1170）；本目录 spread.* 由视觉步骤产出，产出后此链接直接生效）
- 机器可读 claims：[`claims.yaml`](claims.yaml)；人读版：[`claims.md`](claims.md)；CP1：[`storyboard.md`](storyboard.md)

## 已跑命令 / 结果

| 命令 | 结果 | 何时 |
|---|---|---|
| `docker compose config --quiet` | 退出 0（条件链可解析） | 本轮实跑 |
| `docker compose ps` / `ps -a` | 5 running 全 healthy + init `Exited (0)` | 2026-11-27 真栈实测（另 page-13 有记录） |
| `make docker-smoke` | 8 步全过，`DOCKER SMOKE 8/8 PASS` | 2026-11-27 真栈实测（另 page-13 有记录） |
| page-13 拆一刀（删 init 整段） | smoke 3/8 红「init 没有成功退出（state=缺失）」，`DOCKER SMOKE FAIL` | page-13 重放记录 |
| 真栈失败注入（`docker compose up -d --scale mysql=0`） | init 等待超时 Exited(1)、backend/frontend 从未启动；恢复后 20s 全绿；nuance：compose 空满足放行 init，停点由 docker_init 180s 超时兜底 | 真栈补验 2026-11-27 |

## 已知未知

- 真栈 live up / 失败注入已实证（RUN6 `verified`，2026-11-27）：`--scale mysql=0` → init 等待超时 Exited(1)、backend/frontend 从未启动，恢复后 20s 全绿。**nuance**：scale=0 时 compose 把 service_healthy 当空满足放行 init，「停在 init 前」由 docker_init 的 180s 超时兜底，不是 compose 条件拦截。
- RUN5（2s 轮询 / 180s 上限）`verified`——`docker_init.py:87` 常量 + 注入实测打出「等待超时（180s）」。
- 启动耗时（第一次构建约 8 分钟等）不是设计承诺；180s 是 [当前值]，慢机器可 `--timeout` 覆盖。

## 学生可读性检查（三项复述答案）

1. **N / 参数是什么**：6 个服务（5 长驻 + init 一次性）；smoke 8 步；`/api/steps=12`；轮询 2s、每存储等待上限 180s [当前值]；默认端口 3307/9200/6333/8100/8080（避开本机常见的 3306）。
2. **哪些错误不能重试**：init 失败不重试——`restart: "no"`、非零退出即失败，backend 停在启动前；同理 smoke 红一步就是 `DOCKER SMOKE FAIL`，没有「再跑一次碰运气」的语义（up 幂等 ≠ 失败重试）。
3. **拆掉什么会红**：删掉 compose.yaml 的 init 整段（连同 backend 的三行 depends_on）→ smoke 3/8 红「init 没有成功退出」；只删 init 不删三行 → `depends on undefined service "init"` 直接报错；把 backend 的 condition 降级成 service_started → init 失败时 backend 照样接客（假绿复现）。

## 后续动作

- 有：RUN3/RUN6 已由 2026-11-27 真栈失败注入提级（init Exited(1)、下游未启动）；`make docker-smoke` 8/8 已于 2026-11-27 真栈实测留档；余下可选：其余失败模式（ES/Qdrant 宕机等）注入。
- 合入主 PDF 前按 workflow §9 重跑本链 probe（`docker compose config --quiet`；真栈可用时加 smoke）。
- 无须改教程/契约：page-13 与 compose.yaml / docker_init.py 口径本轮已对上；RUN5 的 2s/180s 已按 [当前值] 标注，不进设计原则。
