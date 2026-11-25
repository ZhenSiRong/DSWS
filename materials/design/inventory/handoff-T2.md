# 交接 · T2 运行时 / 时序图（codebuddy）

> 基线 `eea5e75` · 2026-10-29 · 工作树 `/home/zhensirong/VM-Share/DSWS-design`

## 1. 产出清单

`design/diagrams/02-runtime/`（7 组，共 21 个文件）：

| 编号 | `.mmd` | `.svg` | `.md` |
|---|---|---|---|
| 07 | `07-end-to-end-request.mmd` | ✅ | ✅ |
| 08 | `08-s2-build-sequence.mmd` | ✅ | ✅ |
| 09 | `09-s3-recall-sequence.mmd` | ✅ | ✅ |
| 10 | `10-s4-generate-sequence.mmd` | ✅ | ✅ |
| 11 | `11-s5-security-sequence.mmd` | ✅ | ✅ |
| 12 | `12-s6-correction-state.mmd` | ✅ | ✅ |
| 13 | `13-s7-sse-sequence.mmd` | ✅ | ✅ |

`design/inventory/`：

- `catalog-runtime.md` —— 07–13 的编号 / 标题 / 问题 / 源文件 / SVG / 证据 / 状态
- `handoff-T2.md` —— 本文件

## 2. 渲染与验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/02-runtime/*.svg
```

本机结果（2026-10-29）：

```text
OK  diagrams/02-runtime/07-end-to-end-request.mmd -> 07-end-to-end-request.svg (ok)
OK  diagrams/02-runtime/08-s2-build-sequence.mmd  -> 08-s2-build-sequence.svg  (ok)
OK  diagrams/02-runtime/09-s3-recall-sequence.mmd -> 09-s3-recall-sequence.svg (ok)
OK  diagrams/02-runtime/10-s4-generate-sequence.mmd -> 10-s4-generate-sequence.svg (ok)
OK  diagrams/02-runtime/11-s5-security-sequence.mmd -> 11-s5-security-sequence.svg (ok)
OK  diagrams/02-runtime/12-s6-correction-state.mmd -> 12-s6-correction-state.svg (ok)
OK  diagrams/02-runtime/13-s7-sse-sequence.mmd    -> 13-s7-sse-sequence.svg    (ok)
```

计数复核命令（只读，不写存储）：

```bash
cd backend && uv run --frozen python -m app.build_meta_knowledge --dry-run
# Meta tables=5 columns=24 metrics=6 column_metrics=9
# ES   values=76
# Qdrant column_points=98 metric_points=22
```

## 3. 三个需要协调者知道的结论

1. **生产请求路径不碰 ES/Qdrant**。`AgentRunner` 默认 `context_factory` 是 `OfflineContextBuilder`（`generate/context.py` L94），它只读内存里的契约目录；`RecallPipeline` 只在 S3 CLI 与 `generate_with_recall()` 里用。07 因此没画三存储，09 才是三存储。若书稿要写「请求时查 ES」，那是错的。
2. **`ResultTable` 的 0 行分支不可达**。后端 0 行时发 `EMPTY_RESULT`（`orchestrator.py` L373–L388），不发空 `result`。前端那段代码是兜底，不要当成主路径讲。
3. **S3 实际顺序是「列 → 取值 → 指标」**，且 `meta.load_snapshot()` 在最前面（`recall/pipeline.py` L66–L78），不是「先 ES 后 Qdrant、最后去 Meta 取详情」。

## 4. 未决问题

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | 07 的 SVG 宽 2038px、高 2202px，A4 满宽时正文约 3pt | 印刷可读性 | 书稿里给 07 单页横排，或拆成「请求建立 / 流水线 / 收尾」两页 |
| 2 | `--fresh` 与真实三存储写入未验证（241 是推导值） | 08 的写入计数 | 有 Docker 权限的机器上跑一次 `make stage2`，把 `writes=` 回填到 `facts.md` |
| 3 | 真实 LLM 校正往返未跑 | 10、12 的可重试分支 | 配 `REBUILD_LLM_*` 后跑 `make stage6` |
| 4 | 13 的前端渲染未在浏览器验收 | UI 语义 | `make dev-frontend` + 手动点一次取消 |
| 5 | 07 与 13 都画了 `SSE` 参与者；若 T1 的容器图另有命名，需要统一 | 图集一致性 | 统一叫 `SSE`（`main._sse`） |

## 5. 读过的文件

契约与规范：

- `design/WBS.md`、`design/STYLEGUIDE.md`、`design/inventory/facts.md`
- `contracts/steps.yaml`、`contracts/errors.yaml`、`contracts/sse.schema.json`

后端：

- `backend/app/main.py`（全文 299 行）
- `backend/app/agent/orchestrator.py`（L1–L500）
- `backend/app/agent/validate.py`、`backend/app/agent/errors.py`、`backend/app/agent/correct.py`、`backend/app/agent/cancel.py`
- `backend/app/build_meta_knowledge.py`、`backend/app/build/pipeline.py`、`backend/app/build/plan.py`
- `backend/app/recall/pipeline.py`、`backend/app/recall/nodes.py`、`backend/app/recall/clients.py`、`backend/app/recall/catalog.py`、`backend/app/recall/render.py`
- `backend/app/generate/pipeline.py`、`backend/app/generate/context.py`、`backend/app/generate/guard.py`、`backend/app/generate/provider.py`、`backend/app/generate/prompts.py`、`backend/app/generate/output_schema.py`
- `backend/app/security/pipeline.py`、`backend/app/security/executor.py`、`backend/app/security/policy.py`

前端：

- `frontend/src/App.tsx`、`frontend/src/components/StepRail.tsx`、`frontend/src/components/ResultTable.tsx`、`frontend/src/components/ErrorCard.tsx`、`frontend/src/lib/api.ts`

构建与脚本：

- `Makefile`（stage2 / stage3 / stage4 段）
- `design/scripts/render_all.py`

## 6. 未改动的部分

未修改 `backend/`、`frontend/`、`contracts/`、`docs/` 下任何文件；`design/` 下只新增 `diagrams/02-runtime/` 与本目录两个 `.md`。
