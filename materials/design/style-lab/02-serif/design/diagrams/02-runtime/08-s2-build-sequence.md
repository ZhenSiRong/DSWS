# 08 · S2 构建流水线时序

**一句话**：S2 是一条**一次性 CLI 任务**：解析四个互斥开关 → 在内存里生成 `BuildPlan` → 按 Meta → ES → Qdrant → manifest 的顺序写入 → 打印计数并退出，查询时不再运行。

**这张图回答**：谁在读契约？谁在写三个存储？写序为什么是这个顺序？四个开关各改变了什么？

**图例**：橙色语义 = 构建时任务（Make / CLI）；青色 = 三个存储；蓝色 = 契约派生的计划。

## 参与者（真实进程 / 类）

| 图上名字 | 真实实体 | 文件 |
|---|---|---|
| `Make` | `make stage2`，连续调 CLI 三次 | `Makefile` L39–L45 |
| `CLI` | `app.build_meta_knowledge.main()` | `backend/app/build_meta_knowledge.py` L87 |
| `Plan` | `load_plan()` → `BuildPlan.counts()` | `backend/app/build/plan.py` L174 |
| `Embedder` | `hash-ngram-v1:256`（确定性，不调外部服务） | `backend/app/build/embedding.py` |
| `Meta` | `MetaStore`（MySQL `meta_rebuild`） | `backend/app/build/meta_store.py` |
| `ES` | `ESValueStore`（`value_index_rebuild`） | `backend/app/build/es_store.py` |
| `Qdrant` | `QdrantVectorStore` ×2（`column_info_rebuild` / `metric_info_rebuild`） | `backend/app/build/qdrant_store.py` |

## 四个开关

| 开关 | 行为 | 是否连存储 |
|---|---|---|
| `--dry-run` | `load_plan()` 后立刻返回，只打印 `counts()` | 否 |
| `--fresh` | `drop_database()` + 重建 schema，再全量写 | 是 |
| `--verify` | 只读：manifest、计数、向量维度、样例文档 | 只读 |
| `--assert-idempotent` | 连跑两次 `build()`，断言第二次是 `noop` 且 manifest 不变 | 是 |

四者互斥（`argparse` 的 `add_mutually_exclusive_group`，`build_meta_knowledge.py` L92–L113）。

## 写序（为什么不能换）

1. `load_plan()` 纯内存，不连任何存储 —— 失败最快、最便宜。
2. 非 `--fresh` 时先比对 `read_manifest()` 的 `config_hash` + 三存储计数 + 样例；全一致直接 `noop`（0 写入）。
3. 先删后建 ES / Qdrant 索引：配置变了不能残留旧值文档或旧向量。
4. **Meta 先写**（事实表），ES / Qdrant 后写（可重建索引）。
5. manifest 最后写：它记的是「这次构建成功了」这件事，所以必须最后落地（`pipeline.py` L284）。

## 计数（与 `facts.md` §5 一致）

| 目标 | 计数 |
|---|---|
| Meta `table_info` / `column_info` / `metric_info` / `column_metric` | 5 / 24 / 6 / 9 = 44 行 |
| ES `value_index_rebuild` | 76 |
| Qdrant `column_info_rebuild` | 98 |
| Qdrant `metric_info_rebuild` | 22 |
| manifest | 1 |
| **合计** | **241** |

## 证据

| 结论 | 状态 | 出处 |
|---|---|---|
| `make stage2` = dry-run → fresh → verify 三次调用 | ✅ | `Makefile` L39–L45 |
| 计数 5/24/6/9、76、98、22 | ✅ | `uv run --frozen python -m app.build_meta_knowledge --dry-run`（2026-10-29 本机） |
| 写序 Meta → ES → Qdrant → manifest | ✅ | `pipeline.py` L263–L284 |
| `noop` 判定条件（哈希 + 计数 + 健康 + 样例） | ✅ | `pipeline.py` L216–L236 |
| 失败也会写一条 failed manifest | ✅ | `pipeline.py` L174–L194、L298 |
| 写入总数 241 | 🟡 | 由 `counts()` 公式相加推导，非 `--fresh` 实测 |
| `--fresh` 真实写三存储 | ⚪ | 本机 Docker socket 无权限 |

## 边界

- `--dry-run` 不验证存储连通性：它只能说明计划与计数，说明不了索引健康。
- `--verify` 与 `build()` 各自 `load_plan()` 一次，所以两次调用的 `config_hash` 必须一致，否则 verify 会报不一致。
- 图中 `--assert-idempotent` 与默认构建合并画在同一个分支里；区别只在它断言第二次必须 `noop`。
