# 部署与测试图目录（25–32）

> 作者：T4（qoder）· 基线 `eea5e75` · 工作树 `/home/zhensirong/VM-Share/DSWS-design`
> 渲染命令：`cd design && python3 scripts/render_all.py`
> 结论状态：✅ 已验证 / 🟡 推断 / ⚪ 未验证（定义见 `STYLEGUIDE.md` §6）

| 编号 | 标题 | 回答的问题 | 图源 | 渲染 | 主要证据 | 结论状态 |
|---|---|---|---|---|---|---|
| 25 | Docker Compose 拓扑 | 六个服务谁依赖谁？数据落在哪？`init` 为什么是一次性？ | `diagrams/05-deployment/25-compose-topology.mmd` | `25-compose-topology.svg` | `compose.yaml` L1、L11–L173；`docs/DOCKER-DEPLOY.md` §5 | ✅ 文件事实；⚪ 未实际启动 |
| 26 | 宿主端口与容器端口暴露面 | 哪个端口对外？哪些只绑 `127.0.0.1`？`init` 有没有端口？ | `diagrams/05-deployment/26-port-exposure.mmd` | `26-port-exposure.svg` | `compose.yaml` L24–L25、L45–L46、L63–L64、L129–L130、L155–L157；`docker/nginx.conf` | ✅ 文件事实；⚪ 未 `docker compose port` 复核 |
| 27 | 启动顺序与失败停点 | `up` 之后谁等谁？每级超时多久？失败停在哪？ | `diagrams/05-deployment/27-startup-order.mmd` | `27-startup-order.svg` | `compose.yaml` L29–L168；`backend/app/scripts/docker_init.py` L41–L118；`docs/DOCKER-DEPLOY.md` §2 | ✅ 文件事实；⚪ 未实际观察 |
| 28 | 旧系统与 rebuild 隔离 | 旧 `meta` / `value_index` / `5173` / `3306` 与新 `*_rebuild` / `5273` / `8100` 怎么分？ | `diagrams/05-deployment/28-legacy-isolation.mmd` | `28-legacy-isolation.svg` | `docs/SETUP-FROM-SCRATCH.md` §4 L918–L962、§5 L966–L980；`README.md` L247–L255 | ✅ 默认值与端口；🟡 旧系统计数未变（未复跑） |
| 29 | 测试金字塔与三存储依赖 | 五层测试各覆盖什么？哪层开始需要三存储？ | `diagrams/06-testing/29-test-pyramid.mmd` | `29-test-pyramid.svg` | `README.md` L28–L29；`Makefile` L38–L106；`backend/tests/recall/test_golden.py` L111–L125；`docs/SETUP-FROM-SCRATCH.md` §3 L835–L847 | ✅ 目录与前置；🟡 计数（README 782 vs SETUP 665） |
| 30 | S0–S7 阶段门禁 | 每阶段跑什么命令？通过判据是什么？ | `diagrams/06-testing/30-stage-gates.dot` | `30-stage-gates.svg` | `Makefile` L14–L157；`docs/SETUP-FROM-SCRATCH.md` §3 L835–L847；`README.md` L15–L25 | ✅ 命令存在；🟡 通过记录为他机；⚪ 本工作树未重跑 |
| 31 | 失败注入矩阵 | 六类失败从哪注入？落到哪个错误码？界面怎么渲染？ | `diagrams/06-testing/31-failure-injection.mmd` | `31-failure-injection.svg` | `fixtures/failures/scenarios.yaml` L51–L191；`contracts/errors.yaml` L42–L92；`backend/tests/agent/test_scenarios.py` L20–L30；`Makefile` L108–L133 | ✅ 夹具与契约；🟡 场景未在本工作树跑；⚪ 浏览器未跑 |
| 32 | 证据台账 | 哪些结论已验证、哪些是推断、哪些未验证？证据去哪？ | `diagrams/06-testing/32-evidence-ledger.mmd` | `32-evidence-ledger.svg` | `design/inventory/facts.md` §9；`README.md` L25–L29；`docs/DOCKER-HANDOFF.md` §5–§6；`docs/SETUP-FROM-SCRATCH.md` §7 | ✅ 本机命令；🟡/⚪ 见图中分桶 |

## 覆盖检查

- 部署图覆盖 `compose.yaml` 全部 6 个服务：`mysql`、`elasticsearch`、`qdrant`、`init`、`backend`、`frontend`（25、26）。
- 端口图覆盖 6 个服务：5 个有宿主映射，`init` 明确「一次性 · 无端口」（26）。
- 阶段门禁覆盖 S0–S7；S8 未实现，不在本任务范围（30）。
- 测试图区分「不需要三存储」「需要三存储」「仅需 MySQL」三档（29），并区分本机已验证与他机记录（32）。

## 合并 / 省略说明

- WBS 中「29 测试金字塔与阶段门禁」与「30 S0–S8 验收链路」拆成两张图：29 回答层次与存储依赖，30 回答每阶段命令与判据；没有合并。
- S8 尚未实现，30 不画 S8 节点；在 `.md` 边界里说明。
