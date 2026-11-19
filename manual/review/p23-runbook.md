# p23 截图 / GIF 复现 runbook（供截图 agent）

> 页面 `manual/page-23.md`。隔离栈 `p23l5`：mysql 13327 / ES 19227 / Qdrant 16327 / backend 18127 / frontend 18087，`FRONTEND_BIND=127.0.0.1`；磁盘 90%，顺序见下。工具：`frontend/node_modules/playwright-core` + `/usr/bin/google-chrome`（照 `manual/shots/web_shots.py`，headless、`--no-sandbox`）。图里不得出现用户名 / 主机名 / 绝对路径 / 隔离端口（正文用 8080）。
## 1. 起隔离栈
```bash
export MYSQL_HOST_PORT=13327 ES_HOST_PORT=19227 QDRANT_HOST_PORT=16327 BACKEND_HOST_PORT=18127 FRONTEND_HOST_PORT=18087 FRONTEND_BIND=127.0.0.1
docker compose -p p23l5 up -d mysql elasticsearch qdrant   # 等三个 healthy
curl -s -X PUT 'http://127.0.0.1:19227/_cluster/settings' -H 'Content-Type: application/json' -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false}}'
docker compose -p p23l5 up -d --no-build init backend frontend   # init Exited (0)、backend/frontend healthy
```

## 2. 图 A：真前端 → `images/page-23-frontend.png`（1440×1000）
浏览器开 `http://127.0.0.1:18087` → 填「华北销售额」→ 点「提问」→ 等 `[data-testid="run-status"]` 变「已完成」→ 截图。DOM 期望：`.rail-item` × 12（文案来自 `/api/steps`）、11 `.rail-success` + 1 `.rail-skipped`（`correct_sql`）、表头「销售额 number」、单元格 `41,099.5`、console 0 error；「生成 SQL」亮「执行中」约 6 秒，可抓中途帧。

## 3. 图 B：拆一刀回 17 行页面 → `images/page-23-html.png`
```bash
sed -n '/^```html$/,/^```$/p' manual/page-23.md | sed '1d;$d' > p23-html/index.html && chmod 644 p23-html/index.html
docker compose -p p23l5 stop frontend
docker run -d --name p23-html --network p23l5_default -p 127.0.0.1:18087:80 \
  -v "$PWD/p23-html/index.html:/usr/share/nginx/html/index.html:ro" shopkeeper-rebuild/frontend:local
```
开 `http://127.0.0.1:18087` 强刷 → 点「问一句」→ `#out` 先闪步骤名（`extract_keywords`…`run_sql`）→ 约 6 秒停 `41099.5`；无表格、无步骤轨（GIF 可录这一过程）。可选反例：挂第 9 页原版 `lab/index.html` → `GET /api/stream` 404、结果区一直空。

## 4. 还原与清理
```bash
docker rm -f p23-html && docker compose -p p23l5 up -d --no-build frontend   # healthy 后真前端复测 41,099.5
docker compose -p p23l5 down -v && rm -rf p23-html                           # 0 容器 / 0 卷 / 0 网络残留
```
图补进 `manual/page-23.md`「你应该看到」与「拆一刀」；跑 `python3 manual/shots/audit_book.py`，末行须 `页面：24/24 通过；README 坏链：0`。
