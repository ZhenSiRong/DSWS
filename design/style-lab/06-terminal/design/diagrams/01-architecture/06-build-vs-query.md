# 06 · 构建时 vs 查询时

**一句话**：S2 是一次性 CLI，退出后不常驻；查询侧 S4 直接读 contracts、S5 只读 MySQL `dw`，只有阶段验收的 S3 读 ES/Qdrant。

**这张图回答**：S2 退出之后，查询时每个阶段各自直接读什么？有没有常驻构建进程？

**图例**：橙=构建时；紫=查询时；青=存储；蓝=契约；红=安全；虚线=可选路径或只读关系。

**关键元素**：

- **构建时 · S2（无守护进程）**：`fixtures/dw.sql` 做内存 SQLite 校验，`S2 build CLI` 最后写 manifest，进程退出码 0，不常驻。
- **持久化结果 + S3**：Meta/ES/Qdrant 由 S2 写；`S3 recall` 仅阶段验收读取，并可通过 `RecallState` 可选喂给 S4。
- **查询时**：浏览器 → FastAPI → AgentRunner → S4/S5。
- **契约共用**：S2 CLI、S4、S5 都直接读 `contracts/`；S5 另读 `sql.policy`。
- **S5 取数**：`ReadOnlyExecutor` 只读 `dw` 库；S4 不读任何业务存储。
- **S3 位置**：与存储同区，读的是持久化结果；不在生产主链路。

**证据**：

- `backend/app/build_meta_knowledge.py` L4–L7、L87–L109：`--dry-run/--fresh/--verify/--assert-idempotent`
- `backend/app/generate/context.py` L94 `OfflineContextBuilder`、L392 `build_offline_context`
- `backend/app/agent/orchestrator.py` L43、L214：主链路注入 `OfflineContextBuilder`
- `backend/app/security/executor.py` L161、L226：`ReadOnlyExecutor.execute`
- `backend/app/recall/pipeline.py` L35：`recall()` 入口
- `README.md` L195：上下文 8 阶段，可选 S3 召回
- `README.md` L232–L238：S2 只写 `*_rebuild`；生产问数不读 S3 的 ES/Qdrant
- `compose.yaml` L83–L104：init 一次性容器执行 S2 后退出

**边界**：

- 图中「S3 → S4」是可选 `RecallState` 路径（🟡 代码存在 `context_from_recall_state`，生产默认不走）。
- S5 的 `dw` 库连接依赖 `dw_reader` 账号；本图不展开授权细节。
- S2 的实际写入计数（44/76/120）来自契约与 manifest 设计；本机未跑 Docker 构建（⚪，见 census §12）。
