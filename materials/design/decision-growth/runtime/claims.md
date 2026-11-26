# 运行链 · claims（人读版）

> 教学编撰声明（D57）：v1→v4 的生长时间线是**教学重构**，不是 commit 历史；每条 claim 的结论由代码/契约/真跑证据锚定。
> status 口径：`verified` = 本轮实跑 probe 或本轮/重放记录里的真跑证据（probe 里写了复核命令）；`inferred` = 只有代码/契约可证；`unknown` = 证据缺口。
> **证据出处声明**：RUN2–RUN4 的证据原出 page-13 重放记录（init Exited (0)、DOCKER SMOKE PASS、拆一刀红法）；2026-11-27 真栈 probe 已复跑升级：live up 时序实测 + `make docker-smoke` 8/8 PASS（RUN2–RUN4）；失败停点注入与 180s 超时实测（RUN5/RUN6 转正）。
> 数字口径：全部来自 `materials/design/decision-growth/runtime/data.yaml` 及其引用的原始出处（page-13、compose.yaml、docker_init.py），不引入新数字。

## Claim 表

| id | 主张 | 类型 | status | 一句话证据 |
|---|---|---|---|---|
| RUN1 | 按健康条件依赖，不按启动顺序（三存储 healthy → init 退出 0 → backend healthy → frontend） | invariant | verified | 本轮实跑 `docker compose config --quiet` → 0；compose.yaml 5 处 condition |
| RUN2 | init 一次性：等存储/开只读账号/校验元知识，退出 0 才放行 backend | decision | verified | page-13 记录 init Exited (0)；compose `restart: "no"` |
| RUN3 | 失败停在下游之前（三级停点） | invariant | verified | page-13 拆一刀记录：删 init → smoke 3/8 红 |
| RUN4 | 起得来 ≠ 部署好：smoke 8 步逐条验 | descriptive | verified | 2026-11-27 真栈 `make docker-smoke` 8/8 PASS（另 page-13 有记录）+ 8 步防什么表 |
| RUN5 | init 不是纯 sleep：2s 条件轮询 + 180s 上限 [当前值] | descriptive | verified | docker_init.py:87 常量 + 注入实测「等待超时（180s）」 |
| RUN6 | 失败停点注入已实证（scale=0 → init Exited(1)，下游未启动）；启动耗时不是设计承诺 | descriptive | verified | 真栈补验 2026-11-27 |

## 每条的证据与反悔点

### RUN1 · 健康条件依赖（verified）

- **证据**：`compose.yaml` 的依赖全是 `condition`，合计 5 处：init 等 mysql/elasticsearch/qdrant 三处 `service_healthy`；backend 等 init 的 `service_completed_successfully`；frontend 等 backend 的 `service_healthy`。**真跑**：本轮 `docker compose config --quiet` 退出 0（配置合法、条件链可解析）。page-13 对账给白话：少了这些条件，compose 只按启动顺序拉，init 可能比库快、backend 可能没初始化就接客。
- **反悔点**：有人把 condition 降级成 `service_started` 或删掉 depends_on——v2 的打脸（Started ≠ healthy）立刻复现；或 compose 换编排工具而条件语义没跟上。

### RUN2 · init 一次性（verified）

- **证据**：`compose.yaml#init` `restart: "no"` + 三处 `service_healthy`；`docker_init.py` 文件头三件事：等待依赖 → 开通只读账号 → 校验/重建 S2 元知识。**真跑记录**（page-13）：`ps -a` 里 init `Exited (0)`，backend 只有拿到退出 0 才启动。失败即非零退出、不重试。
- **反悔点**：init 失败但被设成 `restart: always`（失败被吞、没有停点信号）；或 backend 的 `service_completed_successfully` 条件被拆——「初始化到底成功没有」就没了信号。

### RUN3 · 三级失败停点（verified）

- **证据**：图 27 figcap 原文——存储不 healthy 停 init 前；init 非 0 停 backend 前；backend 不 healthy 停 frontend 前。**实测记录**（page-13 拆一刀）：删掉 init 整段（含 backend 指向 init 的三行），`make docker-smoke` 在 3/8 红「init 没有成功退出（state=缺失）」；只删 init 不删三行则 `depends on undefined service "init"` 直接报错。
- **反悔点**：失败注入实跑若发现某级没有真停（比如 init 失败 backend 还起来）——条件链推得的结论被现实打脸，这条要降级（mysql=0 场景已于 2026-11-27 实测闭环，其余失败模式未注入）。

### RUN4 · 起得来 ≠ 部署好（verified）

- **证据**：`toolbox/scripts/docker-smoke.sh` 的 8 步 + init 幂等段；page-13 的「8 步各防什么」表：3/8 防「只看 running 不看 health 和 init」、4/8 防「契约没进镜像」、5/8 防「接口通但查不出数」、6/8 防「流被攒成整包」、7/8 防「只读只在文档里」、8/8 防「初始化结果不对、一次性脚本不可重跑」。**真跑**（2026-11-27 真栈）：`DOCKER SMOKE 8/8 PASS`；page-13 亦有记录。拆一刀的「假象」段实测：删 init 后五座设施全 healthy、`/api/health` 也 200，但没有 init。
- **反悔点**：smoke 步骤被裁剪（比如去掉 3/8 的 init 退出码检查）；或新增服务没进 8 步覆盖——「部署好」的判据就漏了。

### RUN5 · 2s 轮询 + 180s 上限（verified）

- **证据**：`docker_init.py:87` 默认 `timeout_s=180.0, interval_s=2.0`（每存储各自计时）；`:150` 的 `--timeout` 默认 180。**真栈实证**（2026-11-27）：失败注入下 init 打出「等待超时（180s）」——常量与实测行为一致。
- **反悔点**：慢机器上 180s 不够（timeout 是 [当前值] 不是承诺）；或有人把轮询改成纯 sleep——回到 v1。

### RUN6 · 失败停点注入（verified）

- **证据**：真栈失败停点注入（2026-11-27）：`--scale mysql=0` → init 等待超时 Exited(1)、backend/frontend 从未启动；恢复后 20s 全绿。**nuance**：scale=0 时 compose 把 service_healthy 当空满足放行 init，「停在 init 前」由 docker_init 自身 180s 超时兜底——不是 compose 条件拦截下来的。启动耗时不是设计承诺。
- **反悔点**：换编排工具后「空满足」语义变了（比如 service_healthy 不再空满足），停点位置与耗时都得重测；或 docker_init 的超时被改掉。
