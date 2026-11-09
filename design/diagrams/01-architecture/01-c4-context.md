# 01 · C4-L1 系统上下文

**一句话**：DSWS 是契约驱动的问数系统，用户经浏览器提交问题，系统只对 MySQL 做只读取数；ES 与 Qdrant 由 S2 写入、仅由 S3 阶段验收读取，LLM 是可替换的可选项。

**这张图回答**：DSWS 的系统边界在哪？哪些是外部依赖？生产问数主链路到底读哪几个外部系统？

**图例**：灰=人/外部系统；紫=运行时前端；蓝=DSWS 系统边界；青=存储；虚线=可选或只读关系。

**关键元素**：

- **业务用户 → 浏览器 SPA**：输入自然语言问题。
- **浏览器 → DSWS**：`POST /api/query`，接收 3 种 SSE 事件。
- **DSWS → MySQL**：只读 `SELECT` 取业务数据与 Meta。
- **DSWS → ES / Qdrant**：S2 构建时写取值文档与列/指标向量；S3 阶段验收时读取，生产问数主链路不读。
- **DSWS ⇢ LLM**：可选生成/校正；确定性 provider 可完全替代。
- **旧系统 ⇢ DSWS**：`shopkeeper-agent` 冻结为只读负向夹具，不参与运行。

**证据**：

- `backend/app/main.py` L147 `create_app`，L170–L236 共 5 个端点（✅ 文件存在）
- `contracts/` 下 13 个契约文件（`steps.yaml`、`errors.yaml`、`sse.schema.json` 等，✅ 本机 `ls`）
- `README.md` L195：上下文 8 阶段，契约离线裁剪，S3 召回可选
- `README.md` L232–L238：S2 只写 `*_rebuild` 目标；生产问数上下文由 `OfflineContextBuilder` 生成，S3 的 ES/Qdrant 不在主链路
- `backend/app/generate/provider.py`：确定性/HTTP 双实现（✅ 文件存在）
- `fixtures/` 下旧系统相关夹具（✅ 本机 `ls`）

**边界**：

- C4-L1 不展开容器内部；容器职责见 `02-c4-container.md`。
- 图中用一条边概括「S2 写 / S3 读」三存储；构建与查询的时序关系见 `06-build-vs-query.md`。
- 旧系统未运行，只有文件级夹具（🟡 夹具内容已读，运行行为未复现）。
- LLM 外部端点未联调（⚪ 缺少可用端点与凭据）。
