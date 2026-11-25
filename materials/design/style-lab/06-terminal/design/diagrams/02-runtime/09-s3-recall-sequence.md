# 09 · S3 召回流水线时序

**一句话**：S3 用一次 `recall(query)` 把「关键词」变成「候选字段 / 取值 / 指标」，再按确定性规则裁剪成 `RecallState`；它**不生成 SQL、不调 LLM、不写任何存储**。

**这张图回答**：三存储各自被问了几次？候选怎么合并？哪些字段会被丢掉？

**图例**：青色 = 存储；紫色 = 查询时服务。

## 参与者（真实进程 / 类）

| 图上名字 | 真实实体 | 文件 |
|---|---|---|
| `S3 CLI` | `python -m app.scripts.recall`，用 `render()` 输出 YAML | `backend/app/scripts/recall.py`、`backend/app/recall/render.py` |
| `RecallPipeline` | `recall()` | `backend/app/recall/pipeline.py` L35 |
| `Catalog` | `default_catalog()`，契约在内存里的投影 | `backend/app/recall/catalog.py` |
| `Qdrant` | `stack.column_qdrant` / `stack.metric_qdrant` | `backend/app/recall/clients.py` L387 |
| `ES` | `stack.es.msearch()` | `backend/app/recall/clients.py` L269 |
| `Meta` | `stack.meta.load_snapshot()` | `backend/app/recall/clients.py` L91 |

## 实际执行顺序（与直觉不同）

```text
recall()
  ├─ meta.load_snapshot()        ← 全程只读一次，先拿快照
  ├─ extract_keywords            ← 纯内存
  ├─ recall_column   → Qdrant    ← 列向量，limit=12
  ├─ recall_value    → ES        ← 取值检索，size=5
  ├─ recall_metric   → Qdrant    ← 指标向量，limit=8
  ├─ merge_retrieved_info        ← 用前面的快照，不再回库
  ├─ filter_table
  ├─ filter_metric
  └─ add_extra_context
```

代码里 **列召回在取值召回之前**（`pipeline.py` L73–L78），不是「先 ES 再 Qdrant」。`load_snapshot()` 也发生在最前面（L66），不是「合并时再去 Meta 取详情」——合并用的是内存快照。

## 三个计数（与 `facts.md` §5 一致）

| 库 | 计数 | 在这个流程里的角色 |
|---|---|---|
| ES `value_index_rebuild` | 76 条文档 | 取值召回的分母 |
| Qdrant `column_info_rebuild` | 98 个点 | 列召回的分母（24 列拆成 98 条检索文本） |
| Qdrant `metric_info_rebuild` | 22 个点 | 指标召回的分母（6 指标拆成 22 条） |

## 过滤规则（为什么候选会变少）

- `_is_direct_column()`：`lexical_score >= 0.5` 或 `vector_score >= 0.72` 才算直接证据；`metric_dependency` 来源的字段只在 `include_dependency=True` 时保留（`nodes.py` L50–L51、L570–L580）。
- `filter_table()`：只保留「有直接证据列」的表，外加 join 路径上的主外键（`nodes.py` L582）。
- `filter_metric()`：按指标裁剪，再剪掉失去依赖的列（`nodes.py` L651、L751）。

## 证据

| 结论 | 状态 | 出处 |
|---|---|---|
| 8 个节点顺序与 `steps.yaml` 一致 | ✅ | `pipeline.py` L73–L95 |
| 三存储计数 76 / 98 / 22 | ✅ | `--dry-run` 输出（2026-10-29 本机） |
| 召回限额 12 / 8 / 5 / 30 | ✅ | `nodes.py` L44–L47 |
| 词法补偿：Qdrant 未命中也能进候选 | ✅ | `nodes.py` L164–L226（`_aggregate_candidates`） |
| `trace` 记录每库往返次数 | ✅ | `pipeline.py` L95–L118 |
| 真实 Qdrant / ES 命中数（例如 76 条是否全被检索到） | ⚪ | 需要三存储起来；本次只跑 dry-run |

## 边界

- `recall()` 每次把四个 `roundtrips` 计数器清零（`pipeline.py` L59–L63），所以 `trace` 说的是「这道题」的往返，不是进程累计。
- `MAX_VALUE_HITS = 30` 是二次截断：先 `size=5` 取，再按分数排序截 30。
- 本图不画 SQL 生成：S3 的产物是 `RecallState`，交给 S4 的 `context_from_recall_state()`。
