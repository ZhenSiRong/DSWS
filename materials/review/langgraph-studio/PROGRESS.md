# LangGraph Studio 实测进度（分段落盘）

- [x] 临时 venv `/tmp/lgs/env` + `langgraph-cli[inmem] 0.4.43`（langgraph-api 0.18.4；backend/.venv 未污染）
- [x] 12 节点图入口 `studio_graph.py`（真 build_agent_graph，离线夹具）→ `langgraph.json`
- [x] `langgraph dev --no-browser --port 2024`（headless，API/Studio URL 见 `dev-startup.log`）
- [x] Playwright-core + `/usr/bin/google-chrome` 打开 Studio（远程前端 + baseUrl 指本地），截图见 `manual/images/gui-langgraph-studio.png`
- 坑：shell 代理变量会让 langgraph-api 的 httpx 启动报 `Invalid port: ':1]'`；启动前 unset 代理即可
- 补拍（Lead 要求 12 节点全在一屏）：视口 2560×1800 ×1.5 DPR → `manual/images/gui-langgraph-studio-full.png`（3840×2700，右栏 run/state 保留）；画布区裁切 → `gui-langgraph-studio-graph.png`（1926×1740）
  - headless 下 Studio 的 fit view 按钮点不动，改用画布滚轮 zoom-out（scale 1→0.80）+ 拖拽居中；OCR 校验 12 个节点名全部可读
