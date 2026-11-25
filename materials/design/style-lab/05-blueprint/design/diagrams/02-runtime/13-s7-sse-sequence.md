# 13 · S7 SSE 事件序列

**一句话**：后端只发三种事件（`progress` / `result` / `error`），前端按 `type` 与 `class` 分流到三个组件；`skipped` 和 `cancelled` 在界面上各占一个独立状态，不并入 pending 或失败。

**这张图回答**：一条 `progress` 到哪个组件？`error.class` 三个取值各长什么样？取消为什么不算 done？

**图例**：绿色语义 = 成功路径；红色 = failure；灰色 = cancelled。

## 参与者（真实进程 / 类）

| 图上名字 | 真实实体 | 文件 |
|---|---|---|
| `AgentRunner` | 事件生产者 | `backend/app/agent/orchestrator.py` L199 |
| `SSE` | `_sse()` 帧编码 | `backend/app/main.py` L250 |
| `Browser` | `App` 的 `switch (event.type)` | `frontend/src/App.tsx` L141–L176 |
| `StepRail` | `StepRail` 组件 | `frontend/src/components/StepRail.tsx` L33 |
| `ResultTable` | `ResultTable` 组件 | `frontend/src/components/ResultTable.tsx` L46 |
| `ErrorCard` | `ErrorCard` 组件 | `frontend/src/components/ErrorCard.tsx` L32 |

## 三种事件 → 三个组件

| 事件 | 判定 | UI |
|---|---|---|
| `progress` `running` | `sse.schema.json` `status` 枚举 | 步骤条 spinner |
| `progress` `success` | 同上，`duration_ms` 必须是数字 | ✓ + 耗时 |
| `progress` `skipped` | 条件步骤未触发（`orchestrator.py` L168–L180） | 「未触发 –」 |
| `result` | `{columns:[{name,type}], rows:[[...]]}` | `ResultTable`，按列类型渲染 |
| `error` `class=failure` | 红框 + 失败步骤打 × | `ErrorCard` |
| `error` `class=empty` | 空态卡，**步骤不标红** | `ErrorCard`（虚线） |
| `error` `class=cancelled` | 取消态，running 步骤标 ⊘ | `ErrorCard`（中性） |

`class` 只有三个合法取值（`contracts/sse.schema.json` `error.class` 枚举 = `failure` / `empty` / `cancelled`），由 `contracts/errors.yaml` 的 `class` 字段决定。

## `skipped` 的 UI 语义

条件步骤 `correct_sql` 要么跑（running → success/error），要么**显式** skipped。后端在三条提前收尾路径上补发这一条（`orchestrator.py` L168–L180 的 `_skip_correct()`），前端 `StepRail` 渲染成 `–` + 「未触发」（`StepRail.tsx` L51–L53）。**不允许**永远是一块灰色 pending——那正是审计缺陷 D4。

## `cancelled` 的 UI 语义

- 后端：发 `error` + `CANCELLED`，`class=cancelled`。
- 前端：`event.class === "cancelled"` → `setStatus("cancelled")`，并把所有 running 步骤改成 `cancelled`（`App.tsx` L171–L175）。
- 本地 abort：`isAbortError` 分支同样置 `cancelled`（L210–L217），**不是** done。旧系统 `App.tsx:149` 把 abort 写成 `status: "done"`，那就是被修掉的缺陷。

## 证据

| 结论 | 状态 | 出处 |
|---|---|---|
| 只有 3 种事件、`progress.status` 只有 4 值 | ✅ | `contracts/sse.schema.json` `$defs` |
| `error.class` 三值决定 UI | ✅ | `ErrorCard.tsx` L13–L17、L52 |
| `skipped` 由后端显式补发 | ✅ | `orchestrator.py` L168–L180 |
| 取消 ≠ done | ✅ | `App.tsx` L171–L175、L210–L217 |
| 未知事件类型只记录、不当失败 | ✅ | `App.tsx` L187–L194、`api.ts` L129 |
| 真实浏览器渲染 | ⚪ | 本次未起前端 |

## 边界

- **`ResultTable` 的 `rows.length === 0` 分支在生产路径不可达**：后端在 0 行时发的是 `EMPTY_RESULT`，不是空 `result`（`orchestrator.py` L373–L388）。那段代码是给其它调用方与契约测试用的兜底。
- 前端对未知 `step` 会抛 `UNKNOWN_STEP`（`App.tsx` L141–L144）——步骤 id 必须来自 `/api/steps`。
- 流「静默结束」（没收到 result/error 就断了）被前端判成 `STREAM_INCOMPLETE` 失败（L199–L209），不允许当成功。
