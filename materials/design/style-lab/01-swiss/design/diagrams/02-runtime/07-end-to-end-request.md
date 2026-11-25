# 07 · 端到端请求生命周期

**一句话**：一次 `POST /api/query` 由 FastAPI 建 `request_id` 与取消开关，交给 `AgentRunner` 在工作线程里跑「上下文 → 生成 → 校验 → 执行」，中间状态逐帧写成 SSE `progress`，最后**必**以 `result` 或 `error` 收尾。

**这张图回答**：一次问数里谁把什么交给谁？失败、空结果、取消分别在哪一步分叉？为什么这条流一定会结束？

**图例**：紫色块 = 查询时服务（8 阶段上下文）；`alt` = 分叉；`opt` = 可选路径（用户取消）。

## 参与者（真实进程 / 类）

| 图上名字 | 真实实体 | 文件 |
|---|---|---|
| `Browser` | React `App` + `streamQuery` | `frontend/src/App.tsx`、`frontend/src/lib/api.ts` L232 |
| `FastAPI` | `create_app()` → `query()` → `_stream()` | `backend/app/main.py` L147 / L207 / L262 |
| `SSE` | `_sse()`，一行一帧 `data: {...}\n\n` | `backend/app/main.py` L250 |
| `AgentRunner` | `AgentRunner.events()` → `_run()` | `backend/app/agent/orchestrator.py` L126 / L199 / L211 |
| `ContextBuilder` | `OfflineContextBuilder`（8 个阶段） | `backend/app/generate/context.py` L94 / L363 |
| `Generator` | `DeterministicGenerator` 或 `HttpLlmGenerator` | `backend/app/generate/provider.py` L138 |
| `Guard` | `validate_sql()` = `check_sql()` + `enforce()` | `backend/app/agent/validate.py` L31 |
| `ReadOnlyExecutor` | `ReadOnlyExecutor.execute()` | `backend/app/security/executor.py` L161 / L226 |
| `MySQL` | 只读账号连接（密码来自 `REBUILD_DW_RO_PASSWORD`） | `backend/app/security/executor.py` L32 / L187 |

## 主线（谁在什么时候把什么交给谁）

1. `query()` 生成 `request_id`，在 `CANCEL_REGISTRY` 登记取消开关，把 `X-Request-Id` 放进响应头（`main.py` L211–L226）。前端靠这个头调 `/api/cancel`。
2. `_stream()` 把**同步**的 `runner.events()` 放进工作线程，事件经 `asyncio.Queue` 回到协程，再逐帧 `_sse()`（`main.py` L262–L295）。
3. `AgentRunner._run()` 先跑 8 个上下文阶段，每个阶段**先发 running、再真跑、再发 success + duration_ms**（`orchestrator.py` L222–L237）。
4. `draft_sql()` 拿 `GenerateContext` 生成 SQL 或拒答；`validate_sql()` 过 guard + policy；`_execute()` 走只读执行器。
5. `to_result_payload()` 把 `ExecutionResult` 摊成 `{columns:[{name,type}], rows:[[...]]}`（`orchestrator.py` L86）。

## 分叉点

| 结局 | 分叉位置 | 产出 |
|---|---|---|
| **成功** | 执行 `ok` 且 `rows` 非空（L365–L389） | `result` 事件 |
| **空结果** | 执行 `ok` 但 `rows == []`（L373–L388） | `error` + `EMPTY_RESULT`，`class=empty`，**步骤仍是绿的** |
| **失败** | 校验失败 L304–L306 / 生成拒答 L261–L273 / 执行抛异常 L352–L363 / 执行返回错误 L392–L415 | `error`，码取自 `contracts/errors.yaml` |
| **取消** | `/api/cancel` → `CancelRegistry.cancel()`（`main.py` L236），或客户端 abort → `_stream` 的 `finally`（L298–L299） | `error` + `CANCELLED`，`class=cancelled` |

取消只在**步骤边界**生效：`_cancelled()` 在每个阶段/生成/校验/执行前后各查一次（L219、L286、L342、L367）。已经跑完的步骤不会回滚，后面的步骤不再开始。

## 证据

| 结论 | 状态 | 出处 |
|---|---|---|
| 流以 `result` 或 `error` 收尾，异常被兜成 `INTERNAL_ERROR` | ✅ | `orchestrator.py` L199–L209 |
| 8 阶段与 `contracts/steps.yaml` 前 8 项一一对应 | ✅ | `context.py` L363–L376 对照 `steps.yaml` |
| 同步生成器跑在工作线程、经队列回传 | ✅ | `main.py` L272–L294 |
| 空结果是 `EMPTY_RESULT` 而不是空 `result` | ✅ | `orchestrator.py` L373–L388 |
| 取消是独立状态、不是 done | ✅ | `main.py` L227–L237、`orchestrator.py` L181–L187 |
| 真实 LLM 生成 | ⚪ | 无端点 / 无 Key，本机未跑 |
| 浏览器端到端（真实点击 + SSE） | ⚪ | 本次未起前端 |

## 边界与已知偏差

- **生产请求路径的 8 阶段是 `OfflineContextBuilder`，不是 `RecallPipeline`**。前者只读内存里的契约目录（`default_catalog()`），**不访问 ES / Qdrant / Meta**；后者（`backend/app/recall/pipeline.py`）才连三存储，只在 S3 CLI 与 `generate_with_recall()` 里用。所以本图没有画 ES / Qdrant。三存储召回见 09。
- `_stream()` 的 `finally` 无条件 `cancel + release`，所以客户端断开时即使工作线程还在跑，也会在下一个边界停下。
- 图中 `error(code, step=validate_sql)` 只画了终止分支；`retryable=true` 时会先插入一次 `correct_sql`，见 12。
