# GUI 调试路径实测：LangGraph Studio × Zed 调试器

实测 2026-11-21，工作目录 = 仓库根。只新增本报告、`manual/images/` 截图与两个证据目录；
未改 24 页正文、未碰 page-23、未改用户全局 Zed 配置（`~/.config/zed/` 只读）。

## 1. LangGraph Studio（官方图执行 GUI）——成功，已截图

- **装什么**：`backend/.venv` 已有 `langgraph 1.2.19`（无 `langgraph` CLI）；Studio 侧
  `langgraph-cli[inmem] 0.4.43`（含 `langgraph-api 0.18.4`）装进**临时 venv** `/tmp/lgs/env`，
  `backend/.venv` 未动；临时 venv 另补 `pyyaml sqlglot pymysql jsonschema`（被复用的图会真 import 它们）。
- **图入口**：`manual/review/langgraph-studio/studio_graph.py` 暴露仓库真的 `build_agent_graph`
  编译出的 **12 节点图**（`OfflineContextBuilder` 8 段 + `DeterministicGenerator` + `FakeExecutor`
  + `FixtureCorrector`），不读 .env、不连网络/MySQL；`langgraph.json` 指向 `./studio_graph.py:graph`，图名 `agent12`。
- **怎么启动**：在 `manual/review/langgraph-studio/` 起 `langgraph dev --no-browser --port 2024`。
  当前 shell 的代理变量会让 `langgraph-api` 的 httpx 启动时报 `Invalid port: ':1]'`，启动前需去掉代理变量（见下）。
- **看到什么**：Studio 前端（远程 `smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024` + 本地
  Agent Server）画出 12 节点图与 Input（状态）面板；API 建 thread+run 后，线程视图右栏列出
  `__start__ → 12 节点 → __end__` 全时间轴，展开 `run_sql.execution` 可见 SQL，`thread/state` 显示执行成功。
- **实测状态**：成功（一次完整 run 跑通，不是只画图）；缺 `LANGSMITH_API_KEY` 只影响 trace 上报到 LangSmith。
- **截图**：`gui-langgraph-studio-full.png`（2560×1800 视口 ×1.5 DPR＝3840×2700，**12 节点全在一屏** + 右栏
  run/state）、`gui-langgraph-studio-graph.png`（画布区裁切 1926×1740，附录小图）、
  `gui-langgraph-studio.png`（旧局部图，保留）；headless 下 Studio 的 fit view 按钮偶发不生效，改用画布滚轮缩小到 12 节点全可见。

```bash
uv venv /tmp/lgs/env --python /usr/bin/python3
uv pip install --python /tmp/lgs/env/bin/python "langgraph-cli[inmem]" pyyaml sqlglot pymysql jsonschema
cd manual/review/langgraph-studio
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy -u http_proxy -u https_proxy -u NO_PROXY -u no_proxy \
  /tmp/lgs/env/bin/langgraph dev --no-browser --port 2024
# 另开 shell：建线程 + 跑一跳，再用浏览器打开 dev 打印的 Studio URL（URL 后加 &threadId=<thread_id>）
curl -s -X POST http://127.0.0.1:2024/threads -H 'content-type: application/json' -d '{}'
curl -s -X POST "http://127.0.0.1:2024/threads/<thread_id>/runs" -H 'content-type: application/json' \
  -d '{"assistant_id":"agent12","input":{"query":"华北销售额"}}'
```

## 2. Zed 调试器（DAP/debugpy）——配置交付；GUI 实拍未成
- **环境**：Zed preview **1.30.2**（任务写 1.30.1，实测高一个补丁）；`~/.local/share/zed/debug_adapters/`
  为空——依据 Zed 文档，Python 用**内置 adapter 名 `Debugpy`**，不需要装扩展；`debugpy 1.8.22` 已
  `uv pip install --python backend/.venv/bin/python debugpy` 装进 `backend/.venv`（venv 已 gitignore），`import debugpy` 通过。
- **配置样例**：`manual/review/zed-debug/debug.json`（**项目级**，非全局）：`adapter: Debugpy` /
  `request: launch` / `program: $ZED_WORKTREE_ROOT/manual/shots/pdb_step_demo.py` / `cwd: $ZED_WORKTREE_ROOT` /
  `python` 指 venv / `stopOnEntry`。按 Zed 文档复制到项目根 `.zed/debug.json`，不要写进 `~/.config/zed/`。
- **验证到什么**：debugpy 版本/import 通过；`python -m debugpy --listen 127.0.0.1:5679 --wait-for-client
  manual/shots/pdb_step_demo.py` 能起 adapter 并监听端口；最小 DAP 客户端 `initialize` 成功、`launch` 被拒
  （手写 DAP 参数不全，不能算配置失败）。
- **看到什么**：**未实拍**。本机无 `xdotool/wmctrl`；Zed(GPUI) 窗口用 python-xlib XTEST 注入 F4/Ctrl+P 后
  画面不变，打不开「新建调试会话」弹窗，也就截不到断点/调用栈；按纪律不截整个桌面，故不出
  `gui-zed-debug.png`（Zed 窗口本身能正常打开项目 `zed "$PWD"`）。
- **手动复现**：`cp manual/review/zed-debug/debug.json .zed/debug.json` → Zed 打开仓库根 → F4（或命令面板
  `debugger: start`）选 `pdb_step_demo: 离线单步（debugpy）` → 入口停住，可单步/看变量；断点用 gutter 点
  `manual/shots/pdb_step_demo.py` 的 `mark(...)` 行。

## 3. 诚实边界
- Studio 一行用的是**离线夹具**（`pdb_step_demo.py` 同款假模型+假库），12 节点图与校验/事件是真代码，
  但≠真 LLM/MySQL 栈；Studio 前端是 LangSmith 远程网页（需联网），本地 Agent Server 只提供 API。
- Zed 只交付**项目级配置样例 + debugpy 可执行性**，**没有 GUI 实拍**；DAP 端到端「断点-单步」未在 Zed
  里实测，读者自测前请先对齐 Zed 版本。

## 4. 证据文件
`manual/review/langgraph-studio/`（studio_graph.py、langgraph.json、dev-startup.log、thread*.json、PROGRESS.md）与 `manual/review/zed-debug/`（debug.json、debugpy-adapter-smoke.log、environment.txt、PROGRESS.md）。
