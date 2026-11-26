# final-brief.md · 用户旅程设计（journey）· CP2 brief

> 规格：`toolbox/workflows/design-doc-growth.md` §5.6。用户回：`收` / `改 X` / `停`。

## 一条链的结论（3 句）

用户旅程不是「一问一答」，是 12 节点图上的接力：中文提问经 `POST /api/query` 进入 LangGraph（12 节点 / 10 步，id 逐字来自 `contracts/steps.yaml`），`validate_sql` 双关（guard+policy）与 `correct_sql`（≤1 次、校正后重验）夹在生成与执行之间，`dw_reader` 只读执行后由 SSE 流回前端按契约渲染。旅程体验的生长主线是「每一步都有名字」：进度看得见（progress 逐节点）、错误读得懂（errors.yaml 码→人话）、失败收得住（流必以 result/error 收尾）。数字与 prd 对得上：12 节点、10 步（stage 分组口径）、校正 1 次（契约 `[当前值]`）；12 个节点分属 steps.yaml 的 10 个 stage 分组（第 2 阶段「召回」含 3 个节点：列/值/指标），correct_sql（第 9 阶段）是条件节点，界面在 12 步上标「1 条件步」。

## 产物链接

- [spread.png](spread.png) · [spread.pdf](spread.pdf) · [spread.html](spread.html)
- [claims.yaml](claims.yaml) · [claims.md](claims.md) · [storyboard.md](storyboard.md)
- 图源：[journey-map.svg](journey-map.svg)（①–⑪ 每步标注真实文件·符号）

## 已跑命令 / 结果

| 命令 | 结果 |
|---|---|
| `(cd system/backend && .venv/bin/python -m pytest tests/test_steps_stages.py tests/test_s6_langgraph.py -q)` | **9 passed** |
| `(cd system/frontend && npm test)` | **40 passed**（sse 26 + result 14） |
| `(cd system/backend && .venv/bin/python -m pytest tests/security/ -q)` | **179 passed / 2 skipped**（2 skipped = 拒答题 OUT_OF_RANGE/UNSUPPORTED_INTENT 的 runtime skip，非真库用例） |
| `python3 materials/design/scripts/make_decision_growth.py --render journey` | spread.html + spread.png + spread.pdf |
| `python3 materials/design/scripts/check_spread.py journey` | **PASS**（BADGES: v1 → v2 → v3 → v4 · 当前，无溢出/裁切） |

需起栈后验证：`curl -N -X POST http://127.0.0.1:8000/api/query -H 'Content-Type: application/json' -d '{"query":"华北地区销售额是多少？"}'`（前置：起栈；预期：逐节点 progress，以 result/error 收尾——已写进右页「今天怎么验」作为可重跑命令）。

## 已知未知

- [部分实证] 真库侧（2026-11-27）：MySQL 3024→TIMEOUT 真库实测转正，SHOW GRANTS 只读校验已由安全链 S6 真库实证；仍留缺口——1205/1317 未真触发（仅参数化单测）、执行期间取消丢结果的竞态无真并发测试。注意：tests/security 的 2 skipped 是两道拒答题（OUT_OF_RANGE/UNSUPPORTED_INTENT）的 runtime skip，不是真库用例。
- [未知] 执行期间取消丢结果的竞态只有代码路径（`graph.py#_run_node`），未做并发实测。
- v1–v4 生长线是教学编撰（D57），「被打脸」锚定源码注释里的审计记录（D4/D6/B4/F3/F11/FP-8）与旧系统缺陷引用，不是 commit 时间序。

## 学生可读性三问（§5.7，仅看 spread.png 复述）

1. **N / 参数是什么？**——校正次数 N=1（`errors.yaml#correction.max_attempts`，标 `[当前值]` 不是原则）；问题长度 1–500 字（`main.py#QueryRequest`）；12 节点 / 10 步。
2. **哪些错误不能重试？**——`SQL_REJECTED`（安全拒绝）永不进 correction，另有 CANCELLED / EMPTY_RESULT / LLM_REFUSAL 等 retryable: false；retryable 由 `errors.yaml` 契约决定，不是模型决定。
3. **拆掉什么会红？**——改名/删 `steps.yaml` 任一节点 → test_steps_stages 红；去掉流的 result/error 收尾兜底 → test_s6_langgraph 红；去掉 `execute()` 的 enforce 前置或 dw_reader 只读 → tests/security 红。

结论：三问均可从图面+证据栏直接复述，通过。（独立 reviewer：本轮由生产者自测，正式合卷前建议按 §5.8 再过一眼。）

## 后续动作（是否要改 30 页设计文档 / 教程 / 契约）

- 合卷时把本链两页并入主设计文档（§9 装配步骤），目录/页码需复核；合入前重跑本链 probe。
- 契约/源码无需改动；唯一建议：真触发一次 1205/1317 超时映射 + 真并发取消竞态实测，把 J8 的剩余缺口收口。
- 教程侧无必改项；若教程有「问数旅程」章节，可引用 journey-map.svg 的 ①–⑪ 锚点表。
