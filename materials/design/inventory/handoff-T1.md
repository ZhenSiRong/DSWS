# 交接 · T1 架构图与软件普查（Qoder）

> 基线 `eea5e75` · 2026-10-29 · 工作树 `/home/zhensirong/VM-Share/DSWS-design`

## 1. 产出清单

`design/inventory/`：

- `software-census.md` —— 代码规模、分层、模块表、端点/步骤/错误/SSE、数据模型、端口、测试与夹具、模块→文件→证据、不一致项
- `catalog-architecture.md` —— 01–06 的编号 / 标题 / 问题 / 源文件 / SVG / 证据 / 状态
- `handoff-T1.md` —— 本文件

`design/diagrams/01-architecture/`（6 组，共 18 个文件）：

| 编号 | 源 | `.svg` | `.md` |
|---|---|---|---|
| 01 | `01-c4-context.mmd` | ✅ | ✅ |
| 02 | `02-c4-container.mmd` | ✅ | ✅ |
| 03 | `03-backend-modules.dot` | ✅ | ✅ |
| 04 | `04-frontend-tree.mmd` | ✅ | ✅ |
| 05 | `05-stage-evolution.mmd` | ✅ | ✅ |
| 06 | `06-build-vs-query.mmd` | ✅ | ✅ |

## 2. 渲染与验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/01-architecture/*.svg
```

本机结果（2026-10-29）：

```text
OK  diagrams/01-architecture/01-c4-context.mmd -> 01-c4-context.svg (ok)
OK  diagrams/01-architecture/02-c4-container.mmd -> 02-c4-container.svg (ok)
OK  diagrams/01-architecture/03-backend-modules.dot -> 03-backend-modules.svg (ok)
OK  diagrams/01-architecture/04-frontend-tree.mmd -> 04-frontend-tree.svg (ok)
OK  diagrams/01-architecture/05-stage-evolution.mmd -> 05-stage-evolution.svg (ok)
OK  diagrams/01-architecture/06-build-vs-query.mmd -> 06-build-vs-query.svg (ok)
27 mermaid, 1 graphviz, 0 failure(s)
```

渲染环境：Mermaid 11.17.2（`design/assets/mermaid.min.js`）、Chrome headless、Graphviz 2.43。

## 3. 需要协调者知道的结论

1. **生产问数主链路不读 ES/Qdrant**。`AgentRunner` 默认注入 `OfflineContextBuilder`（`generate/context.py` L94、L392），只读契约内存目录；S3 的 `recall()` 只在阶段验收、S3 CLI 和 `generate_with_recall()` 里用。01/02/06 都按这个事实画。
2. **仓库没有 `frontend/src/lib/sse.ts`**。SSE 解析器是 `lib/api.ts` 的 `SseParser`（L78），`generated/sse.ts` 只有类型与 `EVENT_TYPES`（L69）。04 按真实文件画，未虚构文件。
3. **测试数存在文档不一致**：`README.md` L25 写 782 passed / 31 skipped，`docs/SETUP-FROM-SCRATCH.md` §3 写 665 passed。census 采用 782 并标 🟡（本机未跑全量）。
4. **S8 未实现**：`README.md` L24 标「待做」，05 用灰框表示。
5. **03 聚合成文件组**：为可读性把同层文件合并成节点；逐文件职责、入口、调用方在 `software-census.md` §3。

## 4. 未决问题

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | 782 vs 665 的测试数不一致 | 书稿数字 | 有环境时跑一次 `make stage7` 并回填 `facts.md` |
| 2 | 06 的 SVG 为 1656×998px，A4 满宽时偏矮 | 印刷可读性 | 单页横排，或拆成「构建」「查询」两页 |
| 3 | 03 的 Graphviz 宽约 2072px | 印刷宽度 | A4 横排缩小字号，或按「构建时 / 查询时」拆两张 |
| 4 | 01 的旧系统只有夹具、无运行实例 | “旧系统只读”只能标 🟡 | 书稿注明夹具来源 |
| 5 | LLM 未联调 | 01/06 的「可选」分支 | 配 `REBUILD_LLM_*` 后跑 `make stage6` |

## 5. 读过的文件

规范与事实：

- `design/WBS.md`、`design/STYLEGUIDE.md`、`design/inventory/facts.md`
- `README.md`、`docs/SETUP-FROM-SCRATCH.md`
- `design/scripts/render_all.py`

契约：

- `contracts/steps.yaml`、`errors.yaml`、`sse.schema.json`、`schema.contract.yaml`、`sql.policy.yaml`、`sql.output.schema.json`、`contracts/prompts/`

后端（节选）：

- `backend/app/main.py`（全文）
- `backend/app/agent/orchestrator.py`、`validate.py`、`correct.py`、`errors.py`、`cancel.py`
- `backend/app/generate/context.py`、`pipeline.py`、`guard.py`、`provider.py`、`prompts.py`
- `backend/app/security/policy.py`、`executor.py`、`config.py`
- `backend/app/recall/pipeline.py`、`nodes.py`、`clients.py`、`catalog.py`、`keywords.py`
- `backend/app/build_meta_knowledge.py`、`build/pipeline.py`、`build/plan.py`、`build/*_store.py`、`build/embedding.py`
- `backend/app/schema_contract.py`、`sqllex.py`、`cli.py`

前端：

- `frontend/src/App.tsx`、`main.tsx`、`types.ts`
- `frontend/src/components/` 5 个组件
- `frontend/src/lib/api.ts`、`result.ts`、`json-schema.ts`
- `frontend/src/generated/sse.ts`、`sse.schema.json`、`contract.json`

部署与测试：

- `compose.yaml`、`Makefile`
- `fixtures/failures/scenarios.yaml`、`fixtures/injection/sql-injection.yaml`

## 6. 未改动的部分

未修改 `backend/`、`frontend/`、`contracts/`、`docs/`、`Makefile`；`design/` 下只新增 `diagrams/01-architecture/` 三件套与本目录三个 `.md`。
