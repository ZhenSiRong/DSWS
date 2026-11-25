# PRD 技术栈差异补齐对照（v1 → v2）

> 对照对象：`deliverable/PRD-对照表.md` 中项目五的三处「措辞级差距」。
> v2 实例：`http://8.155.135.97:5051`；v1 旧实例：`http://8.155.135.97:5050`（未改动）。
> 原则：只写有证据的结论；未复现的仍然标 ⚠️。

| # | PRD 要求 | v1（旧实例） | v2（新实例） | v2 证据 | 结论 |
|---|---|---|---|---|---|
| 2 | LangGraph 多节点工作流（12 节点 / 10 步） | ❌ 未使用 LangGraph；自研 12 步编排 | ✅ 真实 `langgraph.graph.StateGraph` 执行 12 个契约节点；`validate_sql` 条件边到 `run_sql` / `correct_sql` / `END`；`correct_sql → validate_sql` | 容器内 `langgraph 1.2.19`；`AGENT_STEP_IDS` 打印 12 节点；真实 SSE 12 节点全部出现；`evidence/v2-query.sse`、`evidence/v2-correct-path.sse`；单测 `backend/tests/test_s6_langgraph.py` | **已补齐**（框架选型 + 运行时真实执行） |
| 5 | React 19 + Tailwind 现代化前端 | ⚠️ React 19 ✅；Tailwind ❌（757 行手写 CSS） | ✅ 恢复原版 `shopkeeper-agent` 界面：React 19 + Tailwind 3.4（`tailwindcss ^3.4.17`），Vite 6 构建；只加 SSE 展示适配，不改契约 | `original-frontend/package.json`；`dist/assets/index-DqE4c5df.css` 16.55 kB；`:5051` 标题 `电商问数 \| Shopkeeper Agent`；`screenshots/v2-idle-1920x1080.png`、`v2-query-result-1920x1080.png` | **已补齐**（原版界面 + Tailwind 3.4 真实进构建产物） |
| 3 | SQL 自校验 validate_sql + 自纠错 correct_sql（失败自动重试） | ⚠️ 触发=true、纠正成功=false（v1 真跑一次校正 16.31s，重写后列名仍不在契约，最终 `SQL_UNKNOWN_COLUMN`） | ✅ 条件边真实执行；根因修复后原问题直接成功（`correct_sql skipped`）；自然问数 `查询销售额大于平均销售额的商品` 已触发 `validate_sql error → correct_sql success → validate_sql success → run_sql success`（真实 LLM + MySQL）；故障注入样本仍保留用于稳定回归 | `evidence/v2-fixed-query.sse`；`evidence/v2-natural-correct-success.sse`；`evidence/v2-correct-success.sse`；`evidence/v2-product-ranking-metric.sse`；新增回归测试 `test_implicit_ranking_question_exposes_fact_measures` 等 | **已补齐**（自然问数已出现校正成功样本；是否触发取决于模型是否生成可重试错误，不保证每次复现） |

## 补充说明

1. **v2 没有改 SSE 契约**：`contracts/sse.schema.json`、错误码、12 步 id、`correct_sql` 的 `skipped` 语义均未变；界面适配只在前端展示层（步骤 id → 中文节点名、`{columns,rows}` → 行对象、`skipped` 状态）；v1 的 12 节点契约测试与 v2 的 LangGraph 测试同时通过。
2. **v2 复用 v1 的数据与只读账号**：MySQL / Elasticsearch / Qdrant 未重建；v2 backend 只连 `shopkeeper-rebuild_default` 外部网络，frontend 只连 v2 默认网络，避免 `backend` 解析到旧容器。
3. **旧实例未受影响**：`http://8.155.135.97:5050/api/health` 仍返回 `{"status":"ok","stage":"S7"}`；v1 容器未重启。
4. **纠正成功态的修复**：原问题失败有两层根因——(a) `卖得最好` 没命中指标，`filter_table` 把事实表的 measure 列裁掉了，生成器只能猜列名；(b) `correct_sql.prompt` 没有 `column_infos`，校正器看不到可用字段。已修复：排名意图 + 无指标时补事实表 measure；商品级问法补 `dim_product.product_name`；校正提示词增加 `column_infos`。原问题与商品级问法现在都直接成功；校正成功态用故障注入 + 真实 LLM/MySQL 复现（`evidence/v2-correct-success.sse`），没有制造假证据。
5. **界面切换（2026-11-06）**：v2 前端从教学重建版换回原版 `shopkeeper-agent` 界面，页面不再出现「教学版」「从零重建」；旧重建镜像 `dsws-v2/frontend:local` 保留，可随时回滚。视频与截图均为切换后重新录制/截取。
6. **第二次校正修复（`ac4985e`）**：第一次修复只覆盖「没有命中指标」的排名问题；命中指标时 `implicit_ranking=False`，实体粒度维度/外键仍不会进上下文。已把实体粒度补齐与 `metric_candidates` 解耦，并让 `correct_sql` 在 `SQL_UNKNOWN_COLUMN/TABLE` 且存在语义等价字段时替换/补 JOIN；`graph.py` 同时把校正失败原因写入 `error.detail.reason`。线上自然问数已出现一次 `validate_sql error → correct_sql success → validate_sql success`（`evidence/v2-natural-correct-success.sse`）。
