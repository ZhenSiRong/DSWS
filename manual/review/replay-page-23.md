# 第 23 页独立重放报告（学生视角 · L5 装：从 17 行 HTML 到真前端）

## 结论
能独立跟做：五项判据全部复现——`(cd frontend && npm test)` 40 passed、`/api/steps` 12 步、23 progress+1 result、真前端出 `41,099.5`、拆一刀骨架出 `41099.5` 且还原后仍 `41,099.5`。先修 3 条：拆一刀 `docker run` 写死 8080 与网络名（照抄会失败、失败后残留同名容器）、:53「数据不对」的修法指向 lab-mysql（本页 compose 栈上照做无解）、:39「你应该看到」有一行真前端不存在的文本。

## 范围声明
- 真跑：起隔离栈 → 真前端浏览器（步骤轨/执行中/结果表）→ `npm test` → 拆一刀（17 行骨架换回）→ 还原；另真跑 404/502/403 三条「卡住」反例。浏览器 = `frontend/node_modules/playwright-core` + `/usr/bin/google-chrome`（headless）。
- 隔离与方式：`-p p23replay` + 环境变量覆盖端口（mysql 13337 / ES 19237 / Qdrant 16337 / backend 18137 / frontend 18097、`FRONTEND_BIND=127.0.0.1`）；盘 90% → 先起三依赖 → 关 ES watermark → init/backend/frontend；单 shell 从仓库根按页序连续执行（拆一刀与还原同 shell），每步 `pwd` 在仓库根、无 exit 127。
- 替换：页面 8080→18097、`shopkeeper-rebuild_default`→`p23replay_default`；页面默认值已静态核对（`compose.yaml` 第 1 行 `name: shopkeeper-rebuild`、镜像 `shopkeeper-rebuild/frontend:local`）；随机容器 ID 以 `<id>` 省略。
- 静态核对与时点：ACCEPTANCE §6、page-09/10/12/13/21/22 口径、`compose.yaml`、`contracts/sse.schema.json`、`docker/nginx.conf`、`docker/frontend.Dockerfile`、Makefile、frontend 行数；2026-11-20 07:33–07:43（+08:00），`page-23.md` sha `be8d5fd…`；未重跑首次 8 分钟构建（本页不改镜像）；不重灌真数据（跨页静态判断）；页面尚无截图引用（待截图 agent 按 `p23-runbook` 出，不在本次范围）。

## 环节表
| 环节（page-23.md:行） | 可执行? | 期望一致? | 问题数 |
|:--|:--:|:--|:--:|
| 前置（:3） | 否 | 否：`make docker-up`=`up -d --build`，与「别 `--build`」相反 | 1 |
| 第 1 步 起整栈（:19-23） | —（栈已起，按页跳过） | 是：五个长驻 healthy、init `Exited (0)` | 0 |
| 第 2 步 浏览器问一句（:25） | 是 | 是：12 条轨、执行中约 6 秒、表 `41,099.5`；地址写死 8080 | 1 |
| 第 3 步 `npm test`（:29-31） | 是 | 是：exit 0、`Tests  40 passed (40)` | 0 |
| 「你应该看到」（:37-42） | — | 否：`41,099.5` 对；:39 无此文本、:40「末行」非末行 | 2 |
| 对账（:46-47） | — | 是：23 progress+1 result、`GET /api/stream`→404、26+14=40、smoke 无开页面步骤 | 0 |
| 卡住了（:50-55） | — | 部分：502/403 实测成立；:53 修法指错库 | 1 |
| 拆一刀 第 1–3 步（:63-108） | 是 | 是：骨架闪 `generate_sql`→6.1 s 停 `41099.5`、无轨无表；命令照抄失败见问题 1 | 2 |
| 拆一刀 第 4–5 步+还原（:111-117） | 是 | 是：`up -d frontend` 后 healthy、再问仍 `41,099.5`；还原未清 `p23-html/` | 1 |
| 预算（:21-31、:37-42、:71-101） | — | 是：命令 3≤3、输出 4≤5；HTML 29 行（SPEC 只管 L1，若套 ≤25 超 4 行） | 1 |
| **合计**（跨页：ACCEPTANCE §6 与正文一致；与 page-09/13/21/22 一致，唯 :53 与 page-10/12 冲突，已计在「卡住了」） | | | **9** |

## 问题清单
| page-23.md:行 | 原文摘录 | 问题（类型） | 建议改法 | 严重度 |
|:--|:--|:--|:--|:--:|
| :106-108 | `docker run -d --name p23-html --network shopkeeper-rebuild_default -p 127.0.0.1:8080:80 …` | 易卡：8080 与网络名写死。本工作区 `.env` 为 18080（第 19 行自己说「改过 `.env` 就用 `FRONTEND_HOST_PORT`」），照抄实测 `failed to bind host port 127.0.0.1:8080/tcp: address already in use`；失败还留下 Created 容器，重跑报 `Conflict. The container name "/p23-html" is already in use` | 改 `-p 127.0.0.1:${FRONTEND_HOST_PORT:-8080}:80`（或加一句「8080 换成你 `.env` 的 `FRONTEND_HOST_PORT`，第 4/5 步同；网络名 = `compose.yaml` 的 name + `_default`」）；补「失败先 `docker rm -f p23-html` 再重跑」 | 高 |
| :53 | 「第 10 页换真数据后没还原…按第 10 页收尾重灌回 115 行演示态」 | 跨页：`dw-real` 只灌进第 10/12 页的 `lab-mysql:3307`（第 13 页第 2 步已 `docker rm -f lab-mysql`）；本页 compose 栈的库是 `mysql:3306`、由 `fixtures/dw.sql` 首次 init 灌入，第 10 页收尾命令（`docker exec -i lab-mysql …`）在本页栈上无处可跑，照它修不回来 | 改成「`docker compose exec -T mysql mysql … -e 'SELECT COUNT(*) FROM fact_order'` 应=115；不是就 `make docker-reset` 后 `make docker-up` 重灌 `fixtures/dw.sql`（第 13 页）」 | 高 |
| :39 | 「12 步 · 11 完成 + 1 未触发」 | 事实：真前端无此行文本。浏览器 body 只有 badge `12 步`/`1 条件步`/`已完成`，步骤轨逐条 `完成`×11 + `未触发`×1；「你应该看到」逐行对不上 | 换成界面真有的 `12 步` `1 条件步` `已完成`；「11 完成 + 1 未触发」移到正文说明（不进输出块） | 中 |
| :3、:22 | 「别 `--build`」 vs 第 1 步「`make docker-up`」 | 歧义：`make docker-up` = `docker compose up -d --build`；栈停过的读者按第 1 步会重建，与前置相反 | 第 1 步改 `docker compose up -d`（等五 healthy），或明说「栈停过只 `docker compose up -d`，别 `make docker-up`」 | 中 |
| :25、:111、:114 | 「打开 `http://127.0.0.1:8080`」 | 歧义：:19 与 :50 都给了「改过 `.env` 用你的端口」，但三个浏览器地址仍写死 8080；改过 `.env` 的读者第一步就问不出（本工作区 `.env` 是 18080） | 三处统一「`8080`（或你 `.env` 的 `FRONTEND_HOST_PORT`）」 | 中 |
| :40 | 「# (cd frontend && npm test) 末行：」 | 事实：真正末行是 `Duration …`（输出顺序 Test Files/Tests/Start at/Duration），`Tests 40 passed (40)` 不是末行 | 改「关键行」或把 `Duration` 行也列出 | 低 |
| :69、:71-100 | 「只补接线」+ 29 行 HTML | 歧义：第 9 页是 17 行，接线 2 把 `EventSource` 换成 12 行 `fetch` 读流样板，行数近翻倍；若按 SPEC 片段预算 ≤25 行则超 4 行（L5 不在 SPEC 范围，仅提示） | 注明「接线 2 会让页面从 17 行涨到 29 行，多的是读流样板」 | 低 |
| :69 | 「在仓库根目录建 `p23-html/index.html`」 | 易卡：没有 `mkdir -p p23-html`；用编辑器存能建目录，用终端 `> p23-html/index.html` 直接 `No such file or directory` | 代码块前加 `mkdir -p p23-html`（或注明必须用编辑器保存） | 低 |
| :116 | `docker rm -f p23-html && docker compose up -d frontend` | 易卡：只删容器不删目录，还原后仓库根多一个未跟踪 `p23-html/`；页面却说「删掉简陋入口」 | 还原命令补 `rm -rf p23-html`，或说明留着无害 | 低 |

## 真输出摘录
```text
$ docker compose -p p23replay ps --format '{{.Name}}\t{{.Status}}'
五个长驻 healthy：mysql / elasticsearch / qdrant / backend / frontend；init Exited (0)
$ (cd frontend && npm test)          # exit=0，秒数随机器变
     Tests  40 passed (40)
$ curl -sN -X POST http://127.0.0.1:18097/api/query -d '{"query":"华北销售额"}'
frames=24 {'progress': 23, 'result': 1}  data.keys=['columns','rows']  rows=[[41099.5]]
$ curl -s -o /dev/null -w '%{http_code}' -G http://127.0.0.1:18097/api/stream --data-urlencode 'q=华北销售额'  → 404
真前端：run-status=已完成；.rail-item=12（success 11 / skipped 1）；td=41,099.5；console error=0；5.9–6.3 s
拆一刀：#out 先 generate_sql → 6.1 s 停在 41099.5；rail=0、table=0
照抄 8080：failed to bind host port 127.0.0.1:8080/tcp: address already in use；重跑：Conflict … "/p23-html" is already in use
卡住反例：chmod 600→403 / chmod 644→200；默认 bridge→/api/steps 502
```

## 清理确认
- [x] 容器 / compose 项目：`docker compose -p p23replay down -v` → 卷/网络/容器全删；`ps -a`、`volume ls`、`network ls` 过滤 `p23replay` 均空；临时容器 `p23-html`/`p23-html-src`/`p23-html-bridge` 已 `rm -f`。
- [x] 临时目录：仓库根 `p23-html/` 与 `/tmp` 下 4 个临时脚本/日志已删。
- [x] `backend/uv.lock` / `.lab/`：uv.lock sha `742c28…` 前后一致并 `git checkout --` 兜底；未新建 `.lab`（本页不用 lab），未碰并发会话快照。
- [x] 用户栈：全容器 ID 集合 sha 前后均为 `57a647…`（24 个，含已停容器），未重启/未改端口；隔离端口已释放。
- [x] 只新增本报告 + 更新 `review/README.md` 索引 1 行；`manual/page-23.md` sha `be8d5fd…` 前后一致。

## 8 类必查清单（逐条打勾再交）
- [x] **uv.lock 改写**：→ 通过：本页主机侧只跑 `npm test`，未跑 uv；`backend/uv.lock` sha 前后一致，另 `git checkout --` 兜底。
- [x] **cwd 子 shell**：→ 通过：唯一 `(cd frontend && npm test)` 是子 shell，跑完 `pwd`=仓库根；拆一刀三命令都在仓库根，全页 pwd 不变、无 exit 127。
- [x] **管道退出码**：→ 不适用：页内命令无管道；`npm test` 直跑 exit 0（若接 `| tail` 须看 `${PIPESTATUS[0]}`）。
- [x] **端口与 `.env`**：→ 未过：:25/:111/:114 写死 8080、:106 写死网络名；`.env` 为 18080 且 8080 被占，实测照抄 bind 失败并残留同名容器（问题 :106 与 :25）。
- [x] **lab 快照边界**：→ 不适用：本页不用 `lab save/reset`、无快照；但 :53 让人照第 10 页走 lab-mysql 重灌（问题 2）。
- [x] **重录假绿**：→ 不适用：本页无 `record_sse`/夹具重录。
- [x] **精确行号与同名代码**：→ 通过：不动仓库源码；拆一刀是独立新建文件、3 处接线有注释；`frontend/src` 17 文件 / 2861 行 / 1143 行实测逐字对上。
- [x] **跨页前置回绿**：→ 通过（有缺口）：第 22 页终态 `DOCKER SMOKE PASS`/栈在，第 1 步 `docker compose ps` 五 healthy 是可执行前置；实测第 22 页拆刀残留（GRANT）不红本页判据；缺「先确认第 22 页已还原」一句（低，未单列）。
