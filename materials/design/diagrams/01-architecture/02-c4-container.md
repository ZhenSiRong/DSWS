# 02 · C4-L2 容器图

**一句话**：一次请求依次穿过浏览器 → nginx :8080 → FastAPI :8100 → AgentRunner → generate/security。S2 构建由 init 一次性容器调用 build CLI，写完三存储后退出。

**这张图回答**：一次请求跨哪些容器或进程？S2 构建与 init 在容器拓扑里处于什么位置？

**图例**：橙=构建时容器/任务；紫=查询时进程；红=安全；蓝=契约；青=存储；灰=外部。

**关键元素**：

- **frontend · nginx :8080**：唯一对外入口，`/api/` 反向代理到 backend，关闭响应缓冲。
- **backend · uvicorn 单 worker :8100**：FastAPI 5 个端点，SSE 线程/队列桥接。
- **AgentRunner**：编排 12 步；生成、校验、校正、执行、取消。
- **generate**：`OfflineContextBuilder` 8 阶段 + 7 槽位提示词；可选 HTTP LLM。
- **security**：AST 策略 + `ReadOnlyExecutor`，只读 MySQL。
- **init · 一次性容器**：执行 S2 构建、开通 `dw_reader`，完成后退出。
- **contracts/**：只读挂载，steps/errors/schema/policy 的唯一事实源。
- **MySQL / ES / Qdrant**：构建写入，查询侧仅 S5 读 MySQL、S3 验收读三者。
- **S3 recall**：画在部署边界外，表示阶段验收/集成测试使用，不在生产请求路径。

**证据**：

- `compose.yaml` L11–L160：mysql/elasticsearch/qdrant/init/backend/frontend 六服务与端口
- `backend/app/main.py` L147–L236：`create_app` 与 5 个端点
- `backend/app/agent/orchestrator.py` L126 `AgentRunner`，L199 `events()`
- `backend/app/generate/context.py` L363–L376：8 个上下文阶段
- `backend/app/security/policy.py` L298 `enforce()`；`security/executor.py` L161、L226
- `backend/app/build_meta_knowledge.py` L87–L109：CLI 入口与 4 个开关
- `README.md` L74–L76：init/backend/frontend 端口与职责

**边界**：

- Compose 是部署形态；本地 `make dev-backend` / `make dev-frontend` 不经 nginx。
- S3 recall 的「边界外」是架构判断（🟡 依据 README 与 orchestrator 导入关系），不是容器缺失。
- LLM 端点可选且未联调（⚪）；确定性 provider 路径可离线验收。
- 图中端口为宿主机映射；容器内端口见 `compose.yaml`。
