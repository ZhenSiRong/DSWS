# 第 13 页独立审计报告（学生视角 · L2 换真部署）

> 方式：**文字审计 + 配置级/离线验证，未整栈重跑**（原因见文末）。页面文件未改。现场：HEAD `6dfe66b`（页面）+ 工作区未提交改动（`compose.yaml` 3 行 ES hostname、`scripts/docker-smoke.sh` +20 行第 3 步轮询、`Makefile` doctor）；本机 3306/9200/6333/8100/8080 均已被既有栈/进程占用（20+ 容器，另有 8080 上的 node；`ss` 实测），故只做只读/离线验证。
> 证据：page-13 正文、`compose.yaml`、`Makefile`、`scripts/docker-smoke.sh`、`scripts/smoke_checks.py`、`scripts/lab`、`.env.example`、`docs/DOCKER-HANDOFF.md`、`git show`。

**一句话结论**：骨架和绝大多数判据都对（六服务编排、ps vs ps -a、make 目标、lab 白名单实测真还原；页面输出来自作者 `p13verify` 真跑，非编造），但 smoke 的 SSE 判据写错（合法的 `too-fast` 会被讲成不通过）、前置理由「抢同一份数据」与事实相反、拆一刀的 120 秒失败文案依赖工作区**未提交**的 smoke 改动——这 3 条先修；另有 5 条中低问题。

## 环节表

| # | 环节 | 真结果（学生视角 / 证据） | 问题数 |
|---|---|---|---|
| 前置 | :2/:19–:24 停三个手动件 | 三样都点名了（uvicorn `Ctrl+C` + `docker rm -f lab-mysql lab-nginx`）；漏停不致命（3307/8000/8081 与 compose 五端口在配置上不重叠）。但 :24 理由「抢同一份数据」是错的（两份库独立），且没交代删 `lab-mysql` 会丢第 1–12 页的库、部署库数据来自 `fixtures/dw.sql` | 1 |
| 命令 | :17/:26–:38 | 全页仅 1 处 cwd 说明、无 `cd`（D48 不适用）；`make -n` 核对：`docker-up` = `docker-env` 守卫 + `docker compose up -d --build`，`down/smoke/reset` 均存在，`reset` 要输 yes；`docker-env` 已有 `.env` 时静默跳过、无 `.env` 时末行 `已生成 …` 均实测一致 | 0 |
| smoke | :40–:44/:60–:90 | 9 条 echo 与脚本逐字一致（脚本 :54/:87/:111/:138/:143/:177/:186/:191/:196）；`services:` 成功行/缺 init 报错行用假表实测逐字命中；`health`/`steps=12`/`nginx: …` 与源码、53 条单测一致 | 1 |
| 拆一刀 | :95–:108 | 删 init 段 + backend 三行依赖后 `docker compose config -q` 通过、5 服务；只删 init 保留依赖 → `service "backend" depends on undefined service "init"`（证明两处都得删）；`lab` 白名单含 `compose.yaml`（scripts/lab:31），sandbox 实测 save→改→reset 逐字还原。但 :101/:105 的 120 秒文案只在未提交版脚本成立，失败日志还会多一条 `no such service: init` | 3 |
| 端口 | :30 | 五个变量名/默认值/8081 差异全对（`.env.example` 解析出 3306/9200/6333/8100/8080，前端 0.0.0.0、其余 127.0.0.1）；「改 .env 不改 compose.yaml」「smoke 自问实际端口」准确。缺 `FRONTEND_BIND` 与「先怎么查被占」 | 1 |
| 时长/失败 | :36/:91/:108 | 有「别以为卡死」，smoke 失败会打 FAIL + ps -a + 日志；但 `make docker-up` 自身失败（构建网络/端口占用/Linux ES）无「看哪一行、怎么修」，首次构建无实测基准（作者 commit 记 ~8 分钟，正文只写「几分钟到十几分钟」），smoke 主路径也没提第 2/3 步可能静默等 | 1 |

**四类合计：① 指令/歧义 4（#1、#3、#6、#7）· ② 期望不符 1（#8）· ③ 跨页/口径 2（#2、#5）· ④ 最易卡 1（#4，兼①）**；共 **8** 条。

## 问题清单

| page-13.md:行 | 原文（摘） | 问题 | 建议 |
|---|---|---|---|
| :90（配 :71） | 「`sse_chunks` 会有一两个出入，判据是 `sse_verdict=streamed` 和 `rows=1`」；「你应该看到」只给 `streamed` | **与脚本不符**：响应 <200ms、时间上分不出流式时输出 `sse_verdict=too-fast` 并**判过**（要求 nginx 生效配置显示缓冲已关）；`backend/tests/test_smoke_checks.py:437` 实测返回 0；`docs/DOCKER-HANDOFF.md:242` 的真实记录正是 `too-fast`。学生看到 too-fast 会以为失败 | 「你应该看到」补两档；:90 改成「判据 = rows=1 且（streamed 或 too-fast+nginx 缓冲已关）；too-fast 是正常档，不是失败」 |
| :24 | 「它们占的 3307/8000/8081 和 compose 不冲突，但手动进程不会自己退，留着就是两套系统抢同一份数据」 | 事实相反：`lab-mysql` 无数据卷、数据在容器层（page-00 :97「数据随容器消失」），compose 用 `mysql_data` 卷 + `fixtures/dw.sql` 首灌（compose.yaml:26–28），两者不共享。真正后果是旧入口 8081/8000 继续在线、`make docker-down` 管不到、学生可能对着旧系统验收；且没说删 `lab-mysql` 会丢掉第 1–12 页的库 | 改理由：「不是抢数据，是新旧两套同时在跑、容易验收错对象」；补「删 lab-mysql = 第 1–12 页的库没了；部署库数据来自 fixtures/dw.sql，不受影响」 |
| :101/:105 | 「它会先轮询两分多钟等 init」「DOCKER SMOKE FAIL: 120 秒内服务状态没齐」 | 只在**工作区未提交**的 `scripts/docker-smoke.sh` 里成立；HEAD `6dfe66b` 版本第 3 步一次快照就判，输出是 `DOCKER SMOKE FAIL: 服务状态不满足要求`、无 120 秒轮询。若提交/交付漏了该改动，拆一刀整段对不上 | 提交页面时把 smoke 第 3 步轮询改动一起提交（或页面注明依赖版本） |
| :36（另全页无排障段） | 「第一次要几分钟到十几分钟…别以为卡死；中断了重跑一次就行」 | 有防焦虑但缺可操作失败指引：`make docker-up` 失败（构建网络、端口占用、Linux ES `vm.max_map_count`）时不知道看哪一行、怎么修；也无实测基准（作者 commit 记本机真跑 ~8 分钟） | 加「本机首次约 8 分钟；>20 分钟还在打 `#N` 是构建慢；报错看 `ERROR` 行，起不来先 `docker compose ps -a` / `make docker-logs`；Linux ES 反复退出查 `vm.max_map_count`」 |
| :30 | 「默认宿主机端口：MySQL 3306、ES 9200、Qdrant 6333、backend 8100、frontend 8080…哪个被占，就改 .env…**别改 compose.yaml**」 | 五变量/默认值/8081 差异都对，但漏 `FRONTEND_BIND`：`.env.example:29–31` 默认 `0.0.0.0`（前端对局域网开放，其余四端口只绑 127.0.0.1——L1 的 nginx 是 127.0.0.1，这是行为变化）；且没教「怎么先查被占」，page-00 的 `make doctor` 只查 3307/8000/8081，本机实测这五个 compose 端口全被占 | 补 `FRONTEND_BIND=0.0.0.0` 的含义/收紧法；给一行 `ss -tlnp \| grep -E ':(3306\|9200\|6333\|8100\|8080) '` 自查 |
| :44 vs :99 | :44「**先别停**——"拆一刀"还要用它」；:99「先一键停：`make docker-down`」 | 自相矛盾：拆一刀第一步就是停栈；真正必须保留的是**数据卷**（`down` 不删卷，`reset` 才删） | 改为「先别 `docker-reset`/删卷——拆一刀只 `down`，卷要留着」 |
| :100 | 「把 `init:` 整段删掉（从 `init:` 到它最后一行 `condition: service_healthy`；下一段就是 `backend:`）」 | 全文件 `condition: service_healthy` 出现 4 处（compose.yaml:103/105/107 属 init，:163 属 frontend），仅靠这句话有删错边界的风险 | 锚点写清：「删到 qdrant 那条 `condition: service_healthy` 为止（再下一个空行是 `backend:`）」 |
| :107 | 「后面跟着 5 行 `ps -a` 和日志：五座设施全 healthy…」 | 拆后 `init` 已不在编排里，smoke 的 `fail()` 会先跑 `docker compose logs --tail=60 init backend frontend`，实测（compose 2.40.3）直接报 `no such service: init` 并退出，backend/frontend 日志不会打印 → 学生多看到一条看似报错的 `no such service: init` | 加一句「失败输出里会有一条 `no such service: init`，那是预期内的（编排里已删 init）」 |

## 真实验证记录（无整栈）

- `docker compose -p p13audit -f compose.yaml config -q` → exit 0；`--services` **6** 个。端口覆盖生效：环境变量覆盖 → published `13316/19216/16336/18116/18086`；`--env-file .env.example` → `3306/9200/6333/8100/8080`，frontend `host_ip 0.0.0.0`、其余 `127.0.0.1`——与 :30 五个默认值逐字一致。
- **拆一刀文本推演**（/tmp 副本，未碰仓库文件）：删 `init:` 段（86–107）+ backend 三行依赖 → `config -q` exit 0、服务 **5** 个、backend 无 depends_on；**只删 init 保留依赖** → exit 1 `service "backend" depends on undefined service "init": invalid compose project`。即 :100「删完编排合法」成立，且「两处都删」是必要的。
- `scripts/smoke_checks.py services` 假表实测：六行全好 → `services: backend=running, elasticsearch=running, frontend=running, init=exited, mysql=running, qdrant=running`（:67 逐字，exit 0）；缺 init → stderr `init 没有成功退出（state=缺失, exit=?）`、exit 1（:104 逐字）。
- `health` 子命令吃 `{"status":"ok","stage":"S7"}` → exit 0（`backend/app/main.py:171–172` 就是这两个值）；`contracts/steps.yaml` 实测 **12** 步（:68/:90 对）；`check_nginx` 喂真实 `docker/nginx.conf` → `nginx: /api/query 的代理缓冲已关闭`（:75/:77 逐字）。
- `backend/.venv/bin/python -m pytest tests/test_smoke_checks.py -q` → **53 passed**；其中 `test_the_sse_check_reports_too_fast` 断言 `sse_verdict=too-fast` 时 **check_sse 返回 0（通过）**——问题 #1 的直接证据。
- `docker compose ps` vs `ps -a`：对已在跑的隔离栈 `dsws-lab-ui` 只读执行 → `ps` **5 行**、`ps -a` **6 行**（多 `init exited 0`），容器名 `<project>-<service>-1`，裸 Tab 格式 `{{.Service}}\t{{.State}}\t{{.Health}}\t{{.ExitCode}}` 与脚本消费格式一致 —— :48/:58/:87 的 init 说明成立。
- `scripts/lab` sandbox（/tmp 假仓库，仅 `compose.yaml` + `.env`）：`save p13-before` → 改 compose → `reset --yes` 末行逐字 `现在工作区与快照 "p13-before" 完全一致。`；`.env` 未进快照、reset 后仍在；仓库 `scripts/lab:31` 白名单含 `compose.yaml` → :108 的还原可成立。
- `make -n`：`docker-up` = `docker-env` 守卫 + `docker compose up -d --build`；`docker-down/docker-smoke/docker-reset` 均存在且语义与页面一致；`.env` 已存在时 `make docker-env` exit 0 无输出；`python3 scripts/generate_docker_env.py --output /tmp/...` 末行 `已生成 /tmp/...`（:28/:30 成立）。
- 端口现实性：`ss -tlnp` 本机 3306/9200/6333/8100/8080 **全被别的栈占着**，而 `make doctor` 只查 3307/8000/8081 → :30 的「被占就改」不是假设。
- 真跑证据（非本次）：`git show 6dfe66b` commit body 记「隔离 project p13verify + 五端口覆盖：`make docker-up` ~8 分钟、smoke PASS、拆一刀红在 3/8」→ 页面输出非编造；但 :36 没把「~8 分钟」写进正文。

## 未做与原因

- **整栈重跑：未做。** ① 任务硬约束：不启动任何 compose 栈、不动用户容器/端口；② 本机磁盘 **91%（18G 可用）**，整套 build（backend+frontend 镜像、npm/pip 缓存、镜像层）会再吃数 GB，且作者已真跑并留档（commit body + `docs/DOCKER-HANDOFF.md`）；③ 本机 3306/9200/6333/8100/8080 均被现有用户栈占用，起栈即便改端口也会抢资源。折中做完了上面 10 组配置级/离线验证。
- **另未验证**：① 本机学生环境下 `sse_verdict` 到底是 `streamed` 还是 `too-fast`（取决于机器快慢；作者跑出 streamed，历史记录是 too-fast）；② `sse_chunks` 真值（页面 24 vs handoff 记录 17）；③ `docker compose up -d --build` 的终端实况（init `Started→Exited`、frontend `health: starting` 时长）；④ 拆一刀在真栈上的 120 秒轮询到回 PASS 的全过程；⑤ 前置三件的真实存活状态——本机确有 `lab-mysql`/`lab-nginx` 在跑，但属别的实验栈，**未删除、未停、未碰**（只读过 `docker ps`）。
