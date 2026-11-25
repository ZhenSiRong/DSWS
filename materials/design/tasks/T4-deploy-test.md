# T4 · 部署 / 测试图（qoder）

## 角色与工作树

你是 DSWS 重建项目的设计图集作者之一。工作树：

```text
/home/zhensirong/VM-Share/DSWS-design
```

先读：

1. `design/WBS.md`
2. `design/STYLEGUIDE.md`
3. `design/inventory/facts.md`
4. `compose.yaml`
5. `Makefile` 的 `stage0`–`stage7`、`docker-*`
6. `docs/DOCKER-DEPLOY.md`、`docs/DOCKER-HANDOFF.md`
7. `docs/SETUP-FROM-SCRATCH.md` §2.4、§2.12、§3、§5、§6、§7
8. `scripts/docker-*.sh`、`scripts/stage*.sh`、`scripts/smoke_checks.py`
9. `backend/tests/` 目录结构

## 目标

产出 8 张部署与测试图，回答「怎么起、怎么隔离、怎么验收、失败怎么注入」。

## 必须产出

目录：`design/diagrams/05-deployment/`（25–28）与 `design/diagrams/06-testing/`（29–32）。

| 编号 | 文件 | 类型 | 内容要求 |
|---|---|---|---|
| 25 | `05-deployment/25-compose-topology.mmd` | flowchart | 6 个服务、网络、卷、依赖方向；标出 `init` 一次性 |
| 26 | `05-deployment/26-port-exposure.mmd` | flowchart | 宿主端口 → 容器端口；哪些只绑 `127.0.0.1`，哪个对外 |
| 27 | `05-deployment/27-startup-order.mmd` | sequenceDiagram | `docker compose up` → 三存储 healthy → init → backend healthy → frontend；失败会停在哪 |
| 28 | `05-deployment/28-legacy-isolation.mmd` | flowchart | 旧系统 `meta` / `value_index` / 5173 / 3306 与 rebuild `*_rebuild` / 5273 / 8100 的隔离边界 |
| 29 | `06-testing/29-test-pyramid.mmd` | flowchart | 单元 / 契约 / 集成 / 场景 / 端到端；标出哪些不需要三存储、哪些需要 |
| 30 | `06-testing/30-stage-gates.dot` | Graphviz neato 4×2 | S0→S7 每阶段的硬验收命令与「通过」判据 |
| 31 | `06-testing/31-failure-injection.mmd` | flowchart | 失败注入矩阵：SQL 拒绝 / 语法错 / 空结果 / 超时 / 取消 / LLM 拒答；对应错误码 |
| 32 | `06-testing/32-evidence-ledger.mmd` | flowchart | 已验证 / 推断 / 未验证 三类证据的来源与去向；标出本机边界 |

每张图配同名 `.md` 说明，按 `STYLEGUIDE.md` §7 模板。

### 目录草稿

`design/inventory/catalog-deploy-test.md`：25–32 的编号、标题、问题、源文件、SVG、证据、状态。

### 交接

`design/inventory/handoff-T4.md`：产出清单、渲染命令、未决问题、读过的文件。

## 约束

- 只写 `design/inventory/`、`design/diagrams/05-deployment/`、`design/diagrams/06-testing/`。
- 不要改源码、契约、文档、Makefile。
- 端口、服务名、卷名必须与 `compose.yaml` 逐字一致。
- 不要声称 Docker 全栈已跑通；本机 Docker socket 无权限，标 ⚪。
- 测试图要区分「本机已验证」与「README 声称」。

## 验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/05-deployment/*.svg diagrams/06-testing/*.svg
```

8 个 SVG 全部生成；端口图覆盖 6 个服务；阶段门禁覆盖 S0–S7。
