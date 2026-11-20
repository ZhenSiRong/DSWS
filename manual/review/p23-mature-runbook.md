# p23 成熟版前端（原版 shopkeeper-agent）真跑 runbook（给写手 / 截图重跑）
> 对照主体：`deliverable/v2/original-frontend/`（react 19 + tailwind 3.4.17 + vite 6；`dist/` 已构建；`nginx.conf` 把 `/api/` 反代 `backend:8100` 并关 SSE 缓冲）。产物：`manual/images/page-23-mature.png`（图 A）+ `page-23-mature.gif`（真跑录屏）；本任务只交付图与本 runbook，页面由写手嵌入。隔离栈 `p23mature`：mysql 13357 / ES 19257 / Qdrant 16357 / backend 18157 / 入口 18097，`FRONTEND_BIND=127.0.0.1`；磁盘 90% 顺序：依赖 → 关 ES watermark → init/backend → 成熟版 nginx。工具：`frontend/node_modules/playwright-core` + `/usr/bin/google-chrome`（headless、`--no-sandbox`、1440×1470、deviceScaleFactor=1；浏览器自动化照 `manual/shots/p23_shots.py` 里 browser_shot / capture_page 两段改选择器）。图内不得出现用户名 / 主机名 / 绝对路径 / 隔离端口；成品 1440 宽 @1x、1px 灰边。
## 1. 起隔离栈（仓库根目录；镜像已缓存 → 一律 `--no-build`，镜像缺了才 `--build`，约 8 分钟，第 13 页）
```bash
export COMPOSE_PROJECT_NAME=p23mature MYSQL_HOST_PORT=13357 ES_HOST_PORT=19257 QDRANT_HOST_PORT=16357 BACKEND_HOST_PORT=18157 FRONTEND_HOST_PORT=18097 FRONTEND_BIND=127.0.0.1
docker compose -p p23mature up -d mysql elasticsearch qdrant        # 等三个 healthy
curl -s -X PUT 'http://127.0.0.1:19257/_cluster/settings' -H 'Content-Type: application/json' -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false}}'
docker compose -p p23mature up -d --no-build init backend           # init Exited (0) → backend healthy；compose 的 frontend 服务不起（省出 18097）
```
## 2. 成熟版 nginx（占 18097；网络名 = compose 项目名 + `_default`）
`compose.yaml` 第 1 行 `name: shopkeeper-rebuild` 被 `-p p23mature` 覆盖，实际网络名看 `docker network ls | grep p23mature` → `p23mature_default`；`nginx.conf` 里 `backend:8100` 只有进这个网络才解析得到：
```bash
NGINX_IMAGE=$(grep '^NGINX_IMAGE=' .env.example | cut -d= -f2)
docker run -d --name p23-mature --network p23mature_default -p 127.0.0.1:18097:80 \
  -v "$PWD/deliverable/v2/original-frontend/dist:/usr/share/nginx/html:ro" \
  -v "$PWD/deliverable/v2/original-frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" "$NGINX_IMAGE"
curl -s http://127.0.0.1:18097/api/health     # {"status":"ok","stage":"S7"}
```
## 3. 问答与期望（图 A → `images/page-23-mature.png`：1440×1472 / 124 KB）
开 `http://127.0.0.1:18097` → 输入框（placeholder「问一个电商数据问题...」）填「华北销售额」→ 点「发送」→ 约 6–9s 出结果（真 LLM；「生成SQL」亮「执行中」约 5–8s，按钮变「停止」，底部「运行中」）。期望：`<title>` = 「电商问数 | Shopkeeper Agent」；侧栏「电商问数 / shopkeeper-agent / 新会话 / 样例（4 条）」+ `API /api` + `完成 1`；顶栏「智能数据分析 Agent / FastAPI SSE / LangGraph」；12 节点流程图 11 个 ✓ + 「校正SQL · 未触发」；「查询结果」表头「销售额」、单元格 `41099.5`（页面无千分位，正文 `41,099.5` 是同一数值）、右上「1 行」；底部「就绪」；OCR 须读到 `41099.5`；1440×1470 一屏放下（scrollHeight = clientHeight = 1271，无滚动）。
## 4. GIF（→ `images/page-23-mature.gif`：1440×1472 / 66 帧 / 7.92s / 255 KB）
同一页面重复 §3：点输入框 → 逐字敲「华北销售额」→ 发送 → 每 180ms 截一帧直到结果 + 1.6s 停留 → 120ms/帧合成 6–8s 循环、≤2.5MB；末帧 OCR 读到 `41099.5`，首/中/末帧 AE 非 0 才算有动画。
## 5. 拆一刀（停成熟版 → 第 9 页 17 行 HTML → 同一后端同一入口）
```bash
docker stop p23-mature
mkdir -p p23-html && sed -n '/^```html$/,/^```$/p' manual/page-23.md | sed '1d;$d' > p23-html/index.html && chmod 644 p23-html/index.html
docker run -d --name p23-html --network p23mature_default -p 127.0.0.1:18097:80 -v "$PWD/p23-html/index.html:/usr/share/nginx/html/index.html:ro" shopkeeper-rebuild/frontend:local
```
刷新 18097 → 点「问一句」→ `#out` 先闪步骤 id、约 6–9s 停 `41099.5`；DOM：`table`=0、`svg.lucide-check`=0、无「执行流程 / 查询结果 / 智能数据分析 Agent」。已有 `images/page-23-html.png`（1100×95）DOM 一致可复用、不必重拍。
## 6. 还原与清理
```bash
docker rm -f p23-html p23-mature && rm -rf p23-html
docker compose -p p23mature down -v --remove-orphans        # 0 容器 / 0 卷 / 0 网络
git checkout -- backend/uv.lock 2>/dev/null; docker ps -a -q | sort | wc -l   # 回到用户 24 容器（18081 的 dsws-lab-ui-ui-1 不动）
```
## 7. DOM 断言清单（写手 / 截图重跑；缺一条就不算「成熟版真跑」）
1) `document.title` = `电商问数 | Shopkeeper Agent`，`<html lang>` = `zh-CN`；2) 无「从零重建 / 教学版 / 契约驱动 / 执行链路 / 12 步 / 1 条件步 / 提问」（重建版标记）；3) `textarea`×1、placeholder「问一个电商数据问题...」，流式中发送按钮 aria-label=`停止`、结束后=`发送`。
4) `div[style]` 12 节点文案：抽取关键词 / 召回字段信息 / 召回指标信息 / 召回字段取值 / 合并召回信息 / 过滤指标信息 / 过滤表信息 / 添加额外上下文 / 生成SQL / 校验SQL / 校正SQL · 未触发 / 执行SQL；`svg.lucide-check`=11、`svg.lucide-minus`=1，结束后 loader=cross=0；流式中 loader 所在卡片文案=`生成SQL`。
5) 表头 `销售额`、单元格 `41099.5`、行标 `1 行`、助手气泡「查询完成，共 1 行结果。」、侧栏「完成」计数 1；6) 流式后 `scrollHeight == clientHeight`（1470 高视口一屏放下）；console error / pageerror / requestfailed 均 0。
7) DOM 文本与 OCR 文本无用户名 / 主机名 / `/home/` / `/tmp/` / 隔离端口（13357 / 19257 / 16357 / 18157 / 18097）。
