# 第 23 页 · 装前端：从 17 行 HTML 到真前端

> 前置：L5 只一页，接第 13–22 页那套整栈——Docker 可用、`.env` 已由 `make docker-env` 生成、`make docker-up` 起过栈（栈停过/机器重启过就先 `docker compose up -d`，别 `--build`，本页不改镜像）。本页不动后端、契约、数据，只换浏览器入口；命令都在仓库根目录、同一终端里整段连续执行，括号是子 shell，跑完你还在仓库根目录。

## 这一页构建什么

不是从零写 React：是把第 9 页那 17 行 HTML 入口，换成 `compose.yaml` 里 `frontend` 服务提供的真前端（React 构建产物）。
契约、SSE 协议、查询链路、`41099.5` 判据全不动——换的只是**体验层**：谁渲染进度、谁画结果表。
规模事实：`frontend/src` 17 个文件、2861 行，其中光是界面（7 个 tsx + `styles.css`）就 1143 行；第 9 页那页是 17 行。

## 猜一猜

动手前写下答案（都允许猜错）：
1. 把第 9 页的 17 行页面一个字不改、直接接到真后端：还能出 `41099.5` 吗？真前端和它是不是两套接口？
2. `(cd frontend && npm test)` 的 40 条测试里，有几条真的打开浏览器？换前端后，第 13 页那 8 步 `docker-smoke` 要不要跟着改？

## 动手

**第 1 步：起整栈。** 已经起着就跳过；起栈、等健康、init 退出 0 的判据全在第 13 页。本页只要求 `docker compose ps` 里五个长驻服务 `healthy`（`frontend` 在）——端口默认 `8080`，改过 `.env` 就用你的 `FRONTEND_HOST_PORT`：

```bash
make docker-up
```

**第 2 步：用浏览器问一句。** 打开 `http://127.0.0.1:8080`，输入框填 `华北销售额`，点「提问」。这就是第 9 页那个页面换掉之后的样子：左边步骤轨、右边对话与结果表。

**第 3 步：跑前端自己的判据。** 40 条离线测试（协议解析 + 结果渲染），前提是第 0 页 `make install` 装好了 `frontend/node_modules`：

```bash
(cd frontend && npm test)
```

## 你应该看到

浏览器里 12 条步骤轨来自 `/api/steps`；「生成 SQL」会亮「执行中」约 6 秒，然后结果表出现。表里 `41,099.5` 是千分位写法，数值就是第 7 页那个 `41099.5`；「未触发」那条是条件步骤 `correct_sql`，不是失败。最后一行是第 3 步的末行（秒数随机器变）：

```text
41,099.5
12 步 · 11 完成 + 1 未触发
# (cd frontend && npm test) 末行：
     Tests  40 passed (40)
```

## 对账

- **猜 1：不能，而且它们不是两套接口。** 实测把第 9 页页面原样接真后端：浏览器问一句，结果区一直空——页面调的 `GET /api/stream` 回 **404**；真后端的入口是 `POST /api/query`，结果行也从对象 `rows[0].sales` 变成二维数组 `rows[0][0]`（`contracts/sse.schema.json` 规定 `result.data` 只有 `columns` + `rows`）。也就是说，「同一套契约」指 **SSE 事件**：23 条 `progress`（`step` + `status` + `duration_ms`）+ 1 条 `result`（`columns` + `rows`），每条都是 `data: <json>` 加一个空行。入口方法、结果行形状属于**接线**——下一段把接线补上，页面就能接上同一个后端；真前端和 17 行页面只是同一个后端的两个消费者。
- **猜 2：0 条；`docker-smoke` 一行不用改。** 40 条全是 vitest 纯函数测试（`src/lib/sse.test.ts` 26 条 + `src/lib/result.test.ts` 14 条）：切 SSE 帧、按契约校验事件、按列类型渲染结果，不开浏览器、不连后端。`docker-smoke` 的 8 步也只发 API 请求、看容器和 nginx 配置，没有一步打开页面（第 13/22 页）——它的第 3/8 步只要求 `frontend` 容器 `healthy`。所以两层判据各管一头：**`npm test` 管协议与渲染，`docker-smoke` 管部署与 API，谁也替代不了谁。**
- **装修与承重墙。** 承重墙 = 后端查询链路 + SSE 事件契约 + `/api/steps` 步骤目录；装修 = 谁渲染（`<pre>` 里一行一个数，还是 1143 行界面：步骤轨、结果表、失败卡、空态、取消态、响应式）。换装修，`41099.5` 这个数不变。
- **卡住了看这里。**
  - 打 `8080` 连不上：端口被占或改过 `.env`，改用 `FRONTEND_HOST_PORT` 那个端口；**别改 `compose.yaml`**（第 13 页）。
  - 首次 `make docker-up` 约 8 分钟（网络慢更久）：`frontend` 镜像要 `npm ci` + `tsc` + `vite build`，看到 `Container ... Started` 才算完，别中断（第 13 页）。
  - `npm test` 报找不到 `vitest`：`frontend/node_modules` 缺，先 `(cd frontend && npm ci)`（要联网）。
  - 结果不是 `41099.5`：数据库不是 `fixtures/dw.sql` 的演示集——第 10 页换真数据后没还原，`华北销售额` 会变成 35 行 / `61890.00`；按第 10 页收尾重灌回 115 行演示态。
  - 拆一刀回 `502`：新 nginx 没进 compose 网络（用了默认 bridge，或 proxy 写 `host.docker.internal:8100`）——`backend` 只绑宿主机 `127.0.0.1`，容器从外面进不来；按下一段加 `--network`。
  - 拆一刀回 `403`：`p23-html/index.html` 权限太严（`-rw-------`），`chmod 644 p23-html/index.html` 再刷新（第 9 页同款坑）。

> **你现在拥有**：同一套契约的两个入口——17 行页面和真前端都能问出 `41099.5`；「界面有 1143 行」不等于「多了一套接口」。

## 拆一刀

L5 的级考核：把装修换回简陋版，看承重墙倒不倒。

**第 1 步：停真前端。** 8080 让出来，compose 网络与后端都还在：

```bash
docker compose stop frontend
```

**第 2 步：写回第 9 页的页面，只补接线。** 在仓库根目录建 `p23-html/index.html`，内容如下——`form + pre + 事件处理`的骨架没变，只改 3 处接线（注释标出）：入口换成 `POST /api/query`、`EventSource` 换成 `fetch` 读流、结果行取 `rows[0][0]`；渲染那一行还是「收到 progress 显示 step，收到 result 显示数」。

```html
<!doctype html>
<meta charset="utf-8">
<form onsubmit="ask(q.value); return false">
  <input id="q" name="q" value="华北销售额" size="30"> <button>问一句</button>
</form>
<pre id="out"></pre>
<script>
function ask(question) {
  out.textContent = '';
  // 接线1：真后端入口是 POST /api/query（第 9 页是 GET /api/stream）
  fetch('/api/query', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query: question})}).then(async (resp) => {
    // 接线2：EventSource 换成 fetch 读流；帧还是 data: <json> 加空行
    const reader = resp.body.getReader(), decoder = new TextDecoder();
    let buf = '';
    for (;;) {
      const {value, done} = await reader.read(); if (done) break;
      const frames = (buf += decoder.decode(value, {stream: true})).split('\n\n');
      buf = frames.pop();
      for (const frame of frames) {
        const line = frame.split('\n').find((s) => s.startsWith('data: ')); if (!line) continue;
        const msg = JSON.parse(line.slice(6));
        // 接线3：真契约的结果行是二维数组，不是对象 rows[0].sales
        out.textContent = msg.type === 'result' ? msg.data.rows[0][0] : msg.step;
      }
    }
  });
}
</script>
```

**第 3 步：用真前端的镜像起 nginx 占 8080。** 反代配置（`docker/nginx.conf`）和端口沿用镜像里那一套，只把静态页换成刚写的 `index.html`；必须进 compose 网络，`backend` 这个名字才解析得到：

```bash
docker run -d --name p23-html --network shopkeeper-rebuild_default -p 127.0.0.1:8080:80 \
  -v "$PWD/p23-html/index.html:/usr/share/nginx/html/index.html:ro" \
  shopkeeper-rebuild/frontend:local
```

**第 4 步：再问一次。** 浏览器打开 `http://127.0.0.1:8080`（强刷），点「问一句」：`<pre>` 里先闪过 `extract_keywords`、`generate_sql` 这些步骤名，约 6 秒后停在 `41099.5`。没有步骤轨、没有结果表——那 1143 行就是用来干这个的。

**第 5 步：还原。** 删掉简陋入口、把真前端起回来，等它 `healthy` 再刷新 8080：

```bash
docker rm -f p23-html && docker compose up -d frontend
```

结论：两次结果相同（`41099.5`），契约相同（23 条 `progress` + 1 条 `result`），差的只是「谁负责渲染」。**拆掉体验层，系统照跑。**

> L5 只一页：装修不改变承重墙，所以它不是新造一座城。
