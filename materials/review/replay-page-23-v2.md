# 第 23 页独立重放报告（学生视角 · L5 装：成熟版前端真跑 + 拆一刀）

## 结论
能独立跟做，五项判据全复现：成熟版 18097 标题「电商问数 | Shopkeeper Agent」+「样例」4 条 + 12 节点（11 ✓ + 1 未触发）+ 结果表 `41099.5`；教学版 18087 同问同数 `41,099.5`；`(cd frontend && npm test)` 40 passed；拆一刀 29 行 HTML 5.6 s 停 `41099.5`、无表无流程图；还原干净。先修 3 条：:128/:52 把成熟版数值写成 `41,099.5`（实为 `41099.5`，与 :42 自相矛盾）、:23 第 1 步 `make docker-up` 恒带 `--build`（与 :3「镜像已缓存」相反）、:35 从 `.env.example` 取 `NGINX_IMAGE` 未读 `.env`。

## 范围声明
- 真跑：`-p p23replay` 隔离栈（mysql 13377 / ES 19277 / Qdrant 16377 / backend 18177 / frontend(教学版) 18087，`FRONTEND_BIND=127.0.0.1`；盘 90% → 先起三依赖 → 关 ES watermark → `--no-build` 起 init/backend/frontend）→ 成熟版 nginx 进 `p23replay_default` 占 18097 → Playwright-core + `/usr/bin/google-chrome` 双界面问答 → `npm test` → 拆一刀（删 `p23-mature`、页面 :79-107 的 29 行 HTML 落成 `lab-mature/index.html`、`shopkeeper-rebuild/frontend:local` 占 18097）→ 还原。
- 方式：单 shell 从仓库根按页顺序连续执行（拆一刀与还原同 shell）；全程 `pwd`=仓库根、无 exit 127。
- 静态核对：`compose.yaml`（第 1 行 `name:`）、`deliverable/v2/original-frontend/{nginx.conf,src/lib/agentApi.ts,src/components/StepRail.tsx}`、`docker/nginx.conf`、`docker/frontend.Dockerfile`、`fixtures/dw.sql`、`scripts/docker-reset.sh`、Makefile `docker-up`、page-13/22 判据、三图 OCR。
- 替换：页面 8088→18097、8080→18087（本工作区 `.env` 的 `FRONTEND_HOST_PORT=18080`，默认 8080 被别的进程占）、`shopkeeper-rebuild_default`→`p23replay_default`；容器名沿用 `p23-mature`/`lab-mature`。
- 时点与版本：2026-11-20 10:06–10:11（+08:00）；`page-23.md` sha `7b82b95…`、HEAD `47e9b6f`、`backend/uv.lock` sha `742c28…`。
- 未做与原因：首次 `make docker-up`（`--build`，约 8 分钟；本页不改镜像，故用 `--no-build`，未验构建时长）；真 LLM 分支（本工作区未配 key，走确定性生成器）；502 反例（未故意退出网络，按 `nginx.conf` 的 `backend:8100` + resolver 静态推演）。

## 环节表
| 环节（page-23.md:行） | 可执行? | 期望一致? | 问题数 |
|:--|:--:|:--|:--:|
| 前置（:3） | — | 部分：第 22 页终态成立（page-22:117 `DOCKER SMOKE PASS`）、`.env`/镜像在；"第一次才构建"与 :23 命令相反（计入第 1 步） | 0 |
| 第 1 步 起整栈（:23-27） | 是 | 是：五长驻 healthy + init `Exited (0)`（判据同 page-13:51-58）；`make docker-up` 恒 `--build` 见问题 | 1 |
| 第 2 步 起成熟版（:29-36） | 是 | 是：网络名测到 `p23replay_default`、挂 dist 后 `/api/health {"status":"ok","stage":"S7"}`；镜像来源见问题 | 1 |
| 第 3 步 对照提问（:38） | 是 | 是：`/api/query` 24 帧（23 progress + 1 result）、两界面同数；判据块端口写死见问题 4 | 1 |
| 「你应该看到」（:40-54） | — | 部分：标题/样例 4 条/12 节点/11 ✓+1 未触发/表 `41099.5` 全对；:52 图注数值与图不符 | 1 |
| `npm test`（:48-49） | 是 | 是：exit 0、`Tests 40 passed (40)`、末行 `Duration`；但无独立命令块 | 1 |
| 对账（:56-64） | — | 部分：成熟版 `src/` 无 `/api/steps`、`STEP_LABELS` 映 12 个中文名、教学版轨来自 `/api/steps`、:64 修法正确；:61 端口修法兜不住"别的进程占" | 1 |
| 拆一刀 1–2 步（:66-108） | 是 | 是：删容器后 `sed` 抽块=29 行落盘 | 0 |
| 拆一刀 3–4 步（:110-120） | 是 | 是：镜像 nginx 反代通，5.56 s 停 `41099.5`，`table=0`、`svg.lucide-check=0` | 0 |
| 还原（:122-126） | 是 | 是：容器与目录都删净、18097 关闭、教学版不受影响 | 0 |
| 跨页（:3、page-22） | — | 是：第 22 页拆一刀还原判据与 page-22:109-117 一致 | 0 |
| **合计** | | | **6** |

## 问题清单
| page-23.md:行 | 原文摘录 | 问题（事实/歧义/跨页/易卡） | 建议改法 | 严重度 |
|:--|:--|:--|:--|:--:|
| :128、:52 | 「成熟版 `41,099.5`」「结果表 41,099.5」 | 事实：成熟版单元格实测 `41099.5`（无千分位），:42 自己也写「原样显示 `41099.5`」；图 A 的 OCR 也只有 `41099.5`，:52 图注与图不符、:128 与 :42 互相矛盾 | 两处成熟版都写 `41099.5`（要提千分位就注明"数值即 `41,099.5`"） | 中 |
| :3、:23-27 | 「第一次或代码真改过才构建」+「`make docker-up`」（=`up -d --build`） | 歧义：栈停过但镜像已缓存（本页前置就是这状态）时，照第 1 步会重建约 8 分钟，与页面前置和「别把 8 分钟当必做」相反；页内没给"只 `up` 不 build"的命令 | 第 1 步补一行「栈停过：`docker compose up -d`（约 1 分钟）；真改了代码/首次才 `make docker-up`」 | 中 |
| :31-35 | `"$(grep '^NGINX_IMAGE=' .env.example \| cut -d= -f2)"` | 易卡：容器镜像取自 `.env.example` 而非学生实际生效的 `.env`；换过镜像源/离线环境时拉错镜像，而教学版镜像可能按 `.env` 建 | 改 `grep '^NGINX_IMAGE=' .env`（缺项时回退 `.env.example`） | 低 |
| :42、:45-47 | 「8080：教学版…」 | 歧义：判据块写死 8080/8088，只有 :38/:63 提「改过 `.env` 用你的」；本工作区 `.env` 是 18080，照判据对不上端口（数值判据不受影响） | 判据块改写「8088/8080（或你 `.env` 的 `FRONTEND_HOST_PORT`）」 | 低 |
| :61 | 「8088 打不开 / `Conflict`：端口被占或同名容器残留，`docker rm -f lab-mature` 后重跑」 | 易卡：别的进程占 8088 时 `rm` 无效，重跑仍 bind 失败；应给换端口的退路 | 补「若是别的进程占 8088，把 `-p` 端口换成空的（如 8089）并同步 :38/:45 的地址」 | 低 |
| :48-49 | 「# (cd frontend && npm test) 汇总行」 | 歧义：`npm test` 命令只以注释埋在「你应该看到」里，动手段没有可复制命令，学生容易漏跑这条判据 | 动手段补一条 `(cd frontend && npm test)` 命令块（括号子 shell 与 :3 呼应） | 低 |

## 真输出摘录
```text
$ docker compose -p p23replay ps --format '{{.Service}} {{.Health}}'
mysql/elasticsearch/qdrant/backend/frontend healthy 五个；init exited 0
$ curl -sN -X POST http://127.0.0.1:18097/api/query -d '{"query":"华北销售额"}'
frames=24 {'progress': 23, 'result': 1}；rows=[[41099.5]]；time≈7.7s（随机器变）
成熟版 18097：title=电商问数 | Shopkeeper Agent；样例=是；12 节点；lucide-check=11 + lucide-minus=1；table=销售额/41099.5；console/pageerror/requestfailed=0
教学版 18087：rail-item=12（rail-success 11 + rail-skipped 1）；td=41,099.5；title=电商问数智能体 · 重建 S0
$ (cd frontend && npm test)   # exit=0
     Tests  40 passed (40)
$ 拆一刀（18097 换 29 行 HTML）：tableCount=0、rail=0、svg.lucide-check=0；#out=41099.5，elapsed 5563ms
```

## 清理确认
- [x] 容器 / compose 项目：`docker compose -p p23replay down -v --remove-orphans` → 0 容器 / 0 卷 / 0 网络；`p23-mature`、`lab-mature` 已 `rm -f`。
- [x] 临时目录：仓库根 `lab-mature/` 已删；`/tmp/p23v2` 探针脚本/截图已删。
- [x] `backend/uv.lock`：sha `742c28…` 前后一致；`git status` 仅 `atlas/`、`mermaid/`（用户探索，未碰）。
- [x] `.lab/`：未新建（本页不用 lab 快照）。
- [x] 用户栈：24 个容器名集合与开工前逐名 diff 为空，ID 集合 sha `57a647af…`（与 v1 报告同值），未重启/改端口。
- [x] 只新增本报告 + `review/README.md` 索引 1 行；`manual/page-23.md` sha `7b82b95…` 前后一致。

## 8 类必查清单（逐条打勾再交）
- [x] **uv.lock 改写**：→ 通过：主机侧只跑 `npm test` 与 docker，未跑 `uv`；sha 前后一致（`742c28…`）。
- [x] **cwd 子 shell**：→ 通过：`(cd frontend && npm test)` 后 `pwd`=仓库根；拆一刀 `$PWD` 挂载在仓库根，全页 pwd 不变、无 127。
- [x] **管道退出码**：→ 通过：`( cd frontend && npm test 2>&1 | tail )` 用 `${PIPESTATUS[0]}` 取到 exit 0；页面本体命令无管道。
- [x] **端口与 `.env`**：→ 未过：:42/:45-47 判据块写死 8080/8088（问题 4），:31 取 `.env.example` 而非 `.env`（问题 3）；隔离运行用 18087/18097 替换，未改 `compose.yaml`。
- [x] **lab 快照边界（DB、uv.lock）**：→ 不适用：本页不用 `lab save/reset`；:64 引 `make docker-reset`（`down -v` 真删卷）与 `scripts/docker-reset.sh:100` 一致。
- [x] **重录假绿**：→ 不适用：本页无 `record_sse`/夹具重录。
- [x] **精确行号与同名代码**：→ 通过：:31 `compose.yaml` 第 1 行 `name: shopkeeper-rebuild`、:58 `src/lib/agentApi.ts`、:59 `src/components/StepRail.tsx` 均实测存在且语义对得上（`fetch('/api/query')`、STEP_LABELS 12 条）。
- [x] **跨页前置回绿**：→ 通过：page-22:109-117 的 `DOCKER SMOKE PASS` 与本页 :3 前置一致。
