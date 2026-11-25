# T4 交接 · 部署 / 测试图（25–32）

> 作者：qoder（T4）· 基线 `eea5e75` · 分支 `design/atlas`
> 工作树：`/home/zhensirong/VM-Share/DSWS-design`

## 1. 产出清单

| 类型 | 文件 |
|---|---|
| 图源（Mermaid / Graphviz） | `design/diagrams/05-deployment/25-compose-topology.mmd`、`26-port-exposure.mmd`、`27-startup-order.mmd`、`28-legacy-isolation.mmd`；`design/diagrams/06-testing/29-test-pyramid.mmd`、`30-stage-gates.dot`、`31-failure-injection.mmd`、`32-evidence-ledger.mmd` |
| 渲染（SVG） | 上述 8 个同名 `.svg` |
| 图说明 | 上述 8 个同名 `.md`（按 `STYLEGUIDE.md` §7 模板：一句话 / 回答什么 / 图例 / 关键元素 / 证据 / 边界） |
| 目录草稿 | `design/inventory/catalog-deploy-test.md` |
| 交接 | 本文件 `design/inventory/handoff-T4.md` |

没有修改源码、契约、`docs/`、`Makefile` 或 `design/scripts/`。

## 2. 渲染与验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/05-deployment/*.svg diagrams/06-testing/*.svg
```

本次结果（2026-10-29 本机）：

```text
OK  diagrams/05-deployment/25-compose-topology.mmd -> 25-compose-topology.svg (ok)
OK  diagrams/05-deployment/26-port-exposure.mmd -> 26-port-exposure.svg (ok)
OK  diagrams/05-deployment/27-startup-order.mmd -> 27-startup-order.svg (ok)
OK  diagrams/05-deployment/28-legacy-isolation.mmd -> 28-legacy-isolation.svg (ok)
OK  diagrams/06-testing/29-test-pyramid.mmd -> 29-test-pyramid.svg (ok)
OK  diagrams/06-testing/30-stage-gates.dot -> 30-stage-gates.svg (ok)
OK  diagrams/06-testing/31-failure-injection.mmd -> 31-failure-injection.svg (ok)
OK  diagrams/06-testing/32-evidence-ledger.mmd -> 32-evidence-ledger.svg (ok)
```

覆盖检查：

- 25 / 26 覆盖 `mysql`、`elasticsearch`、`qdrant`、`init`、`backend`、`frontend` 六个服务；端口图里 `init` 明确标为「一次性 · 无端口」。
- 30 覆盖 S0–S7；S8 未实现，按 WBS 不画。
- 29 区分「不需要三存储」「需要三存储」「仅需 MySQL」三档。
- 32 区分 ✅ / 🟡 / ⚪，并写明本工作树的 Docker 边界。

## 3. 未决问题（按优先级）

1. **`render_all.py` 的 SVG 尺寸缺陷（已在本轮修复，无需后处理）**：任务开始时脚本用
   `viewBox="([\d.]+)..."` 取宽高，负坐标（如 `viewBox="0 -2 1604 635"`）匹配不到根节点，
   转而匹配 Mermaid 箭头的 `marker viewBox="0 0 10 10"`，曾把 flowchart 的 SVG 根写成
   `width="10" height="10"`。本任务进行中脚本已被更新（现在只处理根 `<svg>` 标签，坐标允许
   `-?`）；最后一次 `render_all.py` 重渲染后，8 张图的根尺寸全部正确。回归检查一条即可：
   任一 SVG 的开头不应出现 `width="10" height="10"`。

2. **测试计数口径冲突**：`README.md` L25 与 `docs/DOCKER-HANDOFF.md` §5.1 写
   `782 passed / 31 skipped`；`docs/SETUP-FROM-SCRATCH.md` §3 L851 仍写
   `665 passed / 31 skipped`。图里不写死总测试数，只在 29 / 30 / 32 的边界里注明冲突；
   T8 做 QA 报告时需要定一个权威口径。

3. **`SETUP-FROM-SCRATCH.md` §2.4 与 `compose.yaml` 不一致**：文档 L284 说
   “Qdrant 没有 healthcheck，全量 Docker 部署时 `init` 会自己轮询”，但
   `compose.yaml` L67–L81 已给 Qdrant 配了 `/readyz` healthcheck。27 以 `compose.yaml`
   为准并画了 healthcheck；文档同步不在 T4 范围内。

4. **Docker 全栈未在本工作树跑通**：`docker ps` 失败（`DOCKER_DENIED`），25 / 26 / 27
   的运行时结论统一标 ⚪。`docs/DOCKER-HANDOFF.md` §6.1 有他机 `DOCKER SMOKE PASS`
   记录，但没有升级成 ✅。

5. **30 是超宽横图**（约 2144 × 97）：`flowchart LR` 是任务硬要求，8 个阶段必然横排；
   若书稿单页放不下，T8 可在排版时缩放到整页宽或拆成两行（改图源会偏离任务规定的 LR）。

## 4. 读过的文件

- `design/WBS.md`、`design/STYLEGUIDE.md`、`design/inventory/facts.md`
- `compose.yaml`（全部）、`Makefile`（`stage0`–`stage7`、`docker-*`）
- `docs/DOCKER-DEPLOY.md`、`docs/DOCKER-HANDOFF.md`
- `docs/SETUP-FROM-SCRATCH.md` §2.4、§2.9、§2.12、§3、§4、§5、§6、§7
- `scripts/docker-smoke.sh`、`scripts/docker-reset.sh`、`scripts/export-docker-env.sh`、`scripts/stage0-ui.sh`、`scripts/stage6-ui.sh`、`scripts/stage7-ui.sh`
- `backend/app/scripts/docker_init.py`、`backend/app/build/config.py`（默认目标）
- `backend/tests/` 目录结构、`tests/agent/test_scenarios.py`、`tests/recall/test_golden.py`、`tests/recall/test_clients.py`、`tests/test_s2_build.py` 头部
- `contracts/errors.yaml`、`fixtures/failures/scenarios.yaml`
- `docker/nginx.conf`、`README.md`（相关段落）
- `design/scripts/render_all.py`、`design/diagrams/02-runtime/07-end-to-end-request.mmd`

## 5. 给 T8 / 协调者的最短行动

1. 渲染脚本的尺寸缺陷已修复；如需回归，重跑 `render_all.py` 后抽查任一 SVG 根尺寸不为 10×10。
2. 定一个测试计数口径（README 782 或 SETUP 665），写进 QA 报告。
3. 本机有 Chrome（`/usr/bin/google-chrome`）与 Python 3.12.3，渲染链可用；Docker 仍无权限。
