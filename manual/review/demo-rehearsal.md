# 计时彩排：答辩演示（舞台 dsws-lab-ui）

> **结论**：A 段 **32.8 秒**页面出现 `41099.5`（≤3 分钟，余量 147 秒）；C 段操作链路 **43.3 秒**（含“猜”的 30 秒控场预留），10 分钟版其余时间是口播与追问。彩排后栈已恢复：5 个服务 healthy + init `Exited (0)`，18081 实测出数；主栈 `dsws-trace` 未碰（仍 5/5 healthy）。
> **计时口径**：`date +%s.%N` 取起点；浏览器用 playwright-core 驱动无头 Chrome（`/usr/bin/google-chrome`）真跑；“页面出现 41099.5”= 页面 DOM 文本命中（20ms 轮询）。秒数为实测，轮询误差约 ±0.2s；工作目录 `/home/zhensirong/VM-Share/DSWS-design-lab`。

## 1. A 段：从零起栈 → 页面出现 41099.5（实测 32.8s ≤ 3min）

**实际执行序列**：`down`（保留卷）→ 计时开始并 `up -d`（该命令自身阻塞到依赖 healthy）→ 无头浏览器并行重试打开 18081（等价于“轮询 ps + 开页面”）→ 输入“华北销售额”点「发送」→ DOM 出现 `41099.5` 停表。`up -d` 返回时 backend 已 healthy、ui 已启动，端口已可打开。

**逐条脚本（可复制）**
```bash
# ① 清场，保留卷（实测 5.99s；3 个 lab_* 卷仍在，数据不重建）
docker compose -f compose.lab-ui.yaml -p dsws-lab-ui down
docker volume ls | grep lab_
# ② 计时开始 + 起栈（实测 32.27s；返回时依赖全部就绪）
T0=$(date +%s.%N)
docker compose -f compose.lab-ui.yaml --env-file .env -p dsws-lab-ui up -d
T1=$(date +%s.%N); echo "up=$(echo "$T1-$T0" | bc)s"
# ③ 打开 http://127.0.0.1:18081，输入 华北销售额，点右下角「发送」；看到 41099.5 停表
#    无头复验（可选，打印从打开到出数的耗时；本次实测 0.3～0.5s）：
node -e 'const {chromium}=require("/home/zhensirong/VM-Share/DSWS-design-lab/frontend/node_modules/playwright-core");(async()=>{const b=await chromium.launch({executablePath:"/usr/bin/google-chrome",headless:true,args:["--no-sandbox"]});const p=await b.newPage();const t=Date.now();await p.goto("http://127.0.0.1:18081");await p.fill("textarea","华北销售额");await p.click("button[aria-label=\"发送\"]");await p.waitForFunction(()=>document.body.innerText.includes("41099.5"),{timeout:60000});console.log("出数 "+((Date.now()-t)/1000).toFixed(2)+"s");await b.close()})()'
```

**实测耗时表（A）**

| 步骤 | 实测 | 备注 |
|---|---|---|
| down（不计入 A 总时） | 5.99s | 保留 3 个卷 |
| up -d 返回 | 32.27s | 阻塞到 init 完成 + backend/ui 启动 |
| 存储 healthy | mysql / qdrant 5.8s；ES 21.1s | **ES 是关键路径，占全程 64%** |
| init 运行 | 21.30s → 26.00s（4.70s） | verify 通过，未重建元知识 |
| backend healthy | 32.06s | init 完成后约 6.1s |
| ui 启动 / 首次页面加载 | 31.60s / 32.40s | 页面 JS 就绪 |
| **页面出现 41099.5** | **32.80s** | DOM 命中；3 分钟余量 147s ✅ |

**你应该看到**

- `docker compose ps`：5 行 `Up ... (healthy)`；`docker ps -a` 里 init 为 `Exited (0)`。
- 页面：底部先“正在连接问数智能体...”，查询后“查询完成，已返回结构化结果。”→“执行流程”12 步→“查询结果 / 1 行 / `[[41099.5]]`”。
- 等待期浏览器连续报 `net::ERR_CONNECTION_REFUSED`（本次 31.6s 内 165 次）——栈没起来的正常窗口。

**卡点**：ES 启动 21.1s 是大头（单节点、已有数据卷）；init 只 verify 4.7s 没重建；查询本身 0.5s 内完成。

## 2. C 段：猜→造→对账→恢复（实测 43.3s；10 分钟版口播预算约 6 分钟）

**逐条脚本 + 口播（可复制）**
```bash
# ① 猜（30s，实测 30.007s）口播：“把 nginx/UI 入口删掉，系统还能问数吗？举手。”
#    预设答案 A：入口没了=整个系统都没了；B：只是页面打不开，后端还在。先不揭晓，30 秒后进②。
# ② 造（实测 1.215s）——真删入口
docker rm -f dsws-lab-ui-ui-1                        # 0.23s，回显容器名
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18081/   # 000（curl rc=7）
#    浏览器刷新 18081 → 0.35s 出 net::ERR_CONNECTION_REFUSED
# ③ 对账（实测 0.068s，口播 2 分钟）——入口死了，主干还活
curl -sN -X POST http://127.0.0.1:18100/api/query \
  -H 'Content-Type: application/json' -d '{"query":"华北销售额"}'
#    实测 HTTP 200 / 0.049s / 23 条 progress + 1 条 result，末行 data: {"type":"result","data":{...,"rows":[[41099.5]]}}
# ⚠ 任务书给的 -d '{"question":"华北销售额"}' 实测 422（body 字段名必须是 query）
# ④ 恢复（实测 12.01s，口播 30s）
docker compose -f compose.lab-ui.yaml --env-file .env -p dsws-lab-ui up -d   # 5.53s，只重建 ui
#    init 被再次拉起但只 verify；ui healthy 10.57s；刷新 18081 → 输入 → 发送 → 12.01s 出 41099.5
```

**实测耗时表（C）**

| 段 | 口播预算 | 实测操作 | 关键证据 |
|---|---|---|---|
| 猜 | 30s | 30.01s（控场定时） | 两预设答案见上 |
| 造 | 2–4 min | 1.22s | rm 0.23s；curl rc=7/http=000；Chrome `ERR_CONNECTION_REFUSED` |
| 对账 | 2 min | 0.07s | HTTP 200，23 条 progress + `rows": [[41099.5]]` |
| 恢复 | 30s | 12.01s | up 5.53s、ui healthy 10.57s、页面加载 0.38s、出数 0.69s |
| **合计** | **≈6 min** | **43.30s** | 10 分钟版 = 6 分钟演 + 4 分钟追问缓冲 |

**你应该看到**：rm 回显 `dsws-lab-ui-ui-1`；刷新后 Chrome 错误页 `net::ERR_CONNECTION_REFUSED`，curl 终端 `curl: (7) Failed to connect ... port 18081`；对账终端逐条 `data: {"type": "progress", ...}`，最后 `rows": [[41099.5]]`。
- 恢复后 ps 里 ui 重新 `Up (healthy)`，页面再次出现 `[[41099.5]]`；落点：“入口层（UI/nginx）与主干（FastAPI + MySQL/ES/Qdrant）解耦；删入口不伤数据，重建入口即恢复。”

## 3. 风险清单（一句应对）

| 风险 | 应对 |
|---|---|
| 网络/镜像 | 现场 build/pull 会破 3 分钟 → 上台前确认两镜像在本地；本次 up 无网络动作。 |
| 启动耗时（ES 21.1s / init 重跑 4.7s） | 32.8s 可接受；想更快就演示前 5 分钟先起栈，别 `down -v` 删卷。 |
| 磁盘 98%（剩 4.8G） | 台上别 build、别删卷；ES 已关磁盘水位线，实测起停不写大文件。 |
| 端口被占 | `ss -tlnp \| grep 18081` 先查；主栈在 18080，不冲突。 |
| 浏览器空白/拒绝连接 | 等 ps 全部 healthy 再刷新；A 段前 31.6s 的拒绝是正常窗口。 |
| ui 健康检查有 5s start_period | 恢复后别死等 healthy，18081 能打开就刷新（本次 12.01s 出数）。 |
| 结果在流程图下方 / 按钮不叫“问一句” | 出数后向下滚动；口播说点「发送」（placeholder“问一个电商数据问题...”）。 |
| curl 字段名写错 | `question` 会 422，必须 `query`；上台前先空跑一次对账命令。 |

## 4. 5 个可能追问 + 一句话答法

1. “删掉 UI，数据会丢吗？”→ 不会，数据在 MySQL/ES/Qdrant 三个独立卷里，ui 只是无状态入口。
2. “页面打不开，为什么 curl 还能出数？”→ 入口层（nginx/静态页）与主干（FastAPI+存储）解耦，入口挂了主干照跑。
3. “41099.5 是不是写死的？”→ 不是，23 条 SSE 事件跑完 12 步真实 SQL；换问法结果就变（华东销售额→107373.0）。
4. “3 分钟起栈，时间花在哪？”→ ES 21.1s + init verify 4.7s + backend 6.1s；预热/不 down 可压到秒级。
5. “生产里删了入口也能这样恢复吗？”→ 容器化声明式重建可以，生产再加流量切换/健康检查/多副本即可。

## 5. 收尾确认

`docker compose -f compose.lab-ui.yaml -p dsws-lab-ui ps` → 5 行 `Up (healthy)`；`docker ps -a --filter name=dsws-lab-ui` → init `Exited (0)`；`curl -sN -X POST http://127.0.0.1:18081/api/query -H 'Content-Type: application/json' -d '{"query":"华北销售额"}'` → `"rows": [[41099.5]]`。主栈 `dsws-trace` 未动，5/5 healthy。
