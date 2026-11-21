# 附录 · 看执行与调试：VizTracer 时间线（已实测）+ LangGraph Studio / Zed / DevTools

> **附录，不算 24 页。** 主线判据仍是各页命令与 `ACCEPTANCE.md`；本附录只解决「想看清一次问数里谁在跑、跑多久，点开哪个工具，怎么记得住」。

## 1. 这页解决什么

- 三个 GUI 入口，各看一层：**VizTracer** 看函数级时间线（已实测，第 2 节）、**LangGraph Studio / Zed** 看图节点与断点（Studio 已实测、Zed 仅配置，第 3 节）、**Chrome DevTools** 看前端收到的 SSE 帧（第 4 节）。
- 一条 CLI 兜底（第 5 节）：pdb 看变量、`curl | tee` 看帧、`record_sse --check` 把帧当判据。GUI 关了也能复现同一条路径。
- 目标不是「会用一次」，是**记得住**：工具 = 从哪打开 + 看哪一栏；命令 = 不记得 UI 时照样能跑。

## 2. VizTracer（已实测）

装一次（独立 venv，别装进 `backend/.venv`；磁盘紧张，用完删）：

```bash
uv venv /tmp/vizenv --python 3.14
uv pip install --python /tmp/vizenv/bin/python viztracer
```

一条命令生成 trace 和单文件时间线（离线夹具，不连模型、不连 MySQL、不启容器）：

```bash
PYTHONPATH=/tmp/vizenv/lib/python3.14/site-packages \
  backend/.venv/bin/python manual/shots/trace_viztracer.py
```

产物在 `manual/review/viztracer/`：`trace.json`（viztracer 原始 trace，2169 条事件）和 `timeline.html`（2.7 MB 单文件，浏览器直接双击打开，不用起服务）。看什么：

- **横条 = 一次函数调用**，条越宽越久，上下叠着就是「谁调了谁」。
- 顶层 `ask_once`（约 60.6 ms）下面四段：`graph_context_stages` 29.4 ms → `guard_check` 15.8 ms → `correct_retry` 8.9 ms → `second_validate` 6.5 ms；再下一层是 `check_sql` / `validate_sql` / `propose_correction`。
- **点任意条带**，下方给出 Title / Start / Wall Duration / Self Time（实测点 `guard_check`：`15,784,580 ns`）。这就是「跑多久」的精确读数。
- 复现命令与产物尺寸记在 [`review/viztracer/runbook.md`](../review/viztracer/runbook.md)。

![VizTracer 时间线：一次离线问数的函数条带，ask_once 下分上下文 / guard / 校正三段](../images/gui-viztracer.png)

## 3. LangGraph Studio / Zed（实测详情见 review 报告）

### LangGraph Studio（已实测）

- 看什么：把 `backend/app/agent/graph.py` 的 12 节点图可视化，逐节点看 state 与条件边怎么走——这是「节点级」。
- 怎么起：临时 venv 装 `langgraph-cli[inmem]`，在 review 目录起 `langgraph dev --port 2024`，浏览器开 Studio 网页（图、Input、run 时间轴都在一屏）。注意：`langgraph dev` 只发 API，界面在远程 LangSmith Studio（需要联网）；国内代理变量会让本地 API 启动失败，先 `env -u HTTP_PROXY …`。
- 实测截图：12 节点全图 [`images/gui-langgraph-studio-full.png`](../images/gui-langgraph-studio-full.png)、画布裁切 [`images/gui-langgraph-studio-graph.png`](../images/gui-langgraph-studio-graph.png)。
- 步骤与坑见 [review/gui-studio-zed.md](../review/gui-studio-zed.md)（和 VizTracer 的「函数级」不是同一层）。

### Zed 断点

- 看什么：在 `backend/app/agent/correct.py` 打断点，单步看 `sql_before / error / attempts`——这是「源码级」。
- 现状：review 报告交付了项目级 `debug.json` 配置样例（debugpy 可执行已验），但 Zed 里的断点 GUI **未实拍**，别当教程照抄。
- 等价的命令行单步先用第 5 节 pdb 命令；Zed 侧配置见 [review/gui-studio-zed.md](../review/gui-studio-zed.md)。

## 4. Chrome DevTools：前端 SSE 帧

- 起栈一句：`make docker-up`（首次约 8 分钟；栈在跑就跳过），浏览器开 `http://127.0.0.1:8080` 问一句「华北销售额」。
- F12 → **Network** → 过滤 `query` → 点 `query` 请求 → **EventStream** 标签；每行一条 `data: {...}`：`progress` 的 `step` / `status` 逐条到，最后一条 `result` 带 `41099.5`（第 23 页前端 12 节点步骤条的数据来源就是这个流）。
- 点取消会多发一条 `cancel`，EventStream 里能等到 `CANCELLED` 错误事件——和 VizTracer 里「trace 停在半截」是同一件事的两层。

## 5. CLI 兜底（GUI 关了也能复现）

```bash
# 代码级：pdb 里 b app.generate.guard.check_sql，再 c/n/s 看变量
backend/.venv/bin/python -m pdb manual/shots/pdb_step_demo.py

# 帧级：直接收 SSE 字节流，一行一帧（端口按你的栈改）
curl -sN -X POST http://127.0.0.1:8080/api/query \
  -H 'content-type: application/json' -d '{"query":"华北销售额"}' | tee /tmp/sse.txt

# 帧级对账：14 条夹具用今天的代码重录、逐字节比（离线，不起服务）
(cd backend && .venv/bin/python -m app.scripts.record_sse --check)
```

三条各干一件事：pdb 看变量，`curl | tee` 看帧，`record_sse --check` 把帧变成判据。

## 6. 诚实边界

- **VizTracer 是观测，会放大耗时**：每个函数进出都记一笔——同一次问数不追踪约 43 ms，追踪后约 61 ms。看相对比例与层级，别当绝对性能。
- **离线夹具 ≠ 真模型**：假模型返回固定 JSON、假执行器不连 MySQL；trace 说明「路径与层级」，不代表真 LLM 的延迟分布。
- **截图是裁图**：只裁到函数条带（时间轴、工具栏、空白不在图里），完整窗口见 [`review/viztracer/gui-overview.png`](../review/viztracer/gui-overview.png)；第 2 节耗时数字来自同一份 `trace.json` 与点选面板。
- **第 3 节分工**：Studio 已实测（12 节点全图 + run/state 面板）；Zed 只有配置样例、没有 GUI 实拍（本机无窗口自动化工具）；细节以 review 报告为准。
