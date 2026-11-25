# 04 · 前端文件树

**一句话**：`App.tsx` 是唯一状态机，向下分发到 5 个组件；网络请求与 SSE 解析都在 `lib/api.ts` 的 `SseParser` 里。

**这张图回答**：前端有哪些文件、谁调用谁？SSE 解析与契约类型分别住在哪？

**图例**：紫=页面/组件；蓝=库与契约生成物；青=结果表；灰=入口。

**关键元素**：

- **main.tsx**：挂载 `App`。
- **App.tsx · 状态机**：`switch (event.type)` 处理 progress/result/error；`stop()` 调 `cancelQuery`；判定伪错误后分流。
- **Composer**：输入与停止按钮。
- **StepRail**：按 `steps.yaml` 渲染 12 步状态条。
- **ResultTable**：结果表；列语义与复制载荷来自 `lib/result`。
- **ErrorCard**：按 `class` 展示三类失败。
- **PseudoErrorCard**：把「成功但像错误」的结果单独展示。
- **lib/api.ts**：`fetchSteps` / `fetchErrorCodes` / `streamQuery` / `cancelQuery`，以及 `SseParser` 与 `parseAgentEvent`。
- **lib/result.ts**：`describeColumns` / `buildCopyPayload` / `looksLikePseudoError`。
- **lib/json-schema.ts**：轻量 schema 校验。
- **generated/**：`sse.ts`（类型 + `EVENT_TYPES`）、`sse.schema.json`、`contract.json`。

**证据**：

- `frontend/src/App.tsx` L140–L162 事件 `switch`；L238–L241 `stop()`；L336–L343 伪错误分流
- `frontend/src/lib/api.ts` L47 `parseAgentEvent`；L78 `SseParser`；L169/L197/L211/L232 四个 API 函数
- `frontend/src/lib/result.ts` L41 / L76 / L103 三个导出
- `frontend/src/generated/sse.ts` L69 `EVENT_TYPES = ["progress","result","error"]`
- `frontend/src/components/` 下 5 个组件（✅ 本机 `ls`）
- `frontend/src/generated/` 下 3 个生成物（✅ 本机 `ls`）

**边界**：

- **仓库没有 `frontend/src/lib/sse.ts`**；SSE 解析器实际位于 `lib/api.ts` 的 `SseParser`（✅ 本机 `ls frontend/src/lib`）。本图按真实文件画。
- 前端未做浏览器端到端实跑（⚪）；结构结论来自源码 import 与导出清单。
- 图不展开 `sse.test.ts` / `result.test.ts` 两个测试文件，避免与运行时树混淆。
