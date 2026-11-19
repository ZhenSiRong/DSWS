# 第 13 页 · 换真部署：一条命令起整座城，一条命令验收
> 前置：第 0 页备好环境（Docker 可用）；本页接第 1 页的 `lab-mysql`、第 3/9 页的 uvicorn、第 9 页的 `lab-nginx`——动手前先把这三个手动起的东西停掉。L2 到此收尾。

## 这一页构建什么

把前九页手动起的三个东西换成 `compose.yaml` 编排的六个服务：`mysql` / `elasticsearch` / `qdrant` / `init` / `backend` / `frontend`。其中 `elasticsearch` / `qdrant` 是前九页没起过的新设施，随编排一起带起来。一条 `make docker-up` 起整座城，一条 `make docker-smoke` 用 8 步自动验收。部署不是“起得来”，是“起得来 + 能被自动验收”。

## 猜一猜

动手前写下答案：

1. 六个服务里哪个只跑一次就退出？`docker compose ps` 里看得到它吗？
2. `make docker-smoke` 会检查哪些事？只检查“进程都在跑”够不够？

## 动手

以下命令都在仓库根目录执行（有 `compose.yaml`、`fixtures/` 的那一层），可整段复制。

**第 1 步：拍快照。** 本页要改 `compose.yaml`，先拍一张（`.env` 不在快照里；同名快照会被拒，重做本页就换个名字）：
```bash
scripts/lab save p13-before
```

**第 2 步：停掉手动起的三个东西。** 终端 1 里第 3/9 页的 uvicorn 按 `Ctrl+C`；两个容器删掉：`docker rm -f lab-mysql lab-nginx`（回显被删的容器名；报 `No such container` 说明早删了）。它们占的 3307 / 8000 / 8081 和 compose 不冲突，但手动进程不会自己退，留着就是两套系统抢同一份数据。

**第 3 步：生成 `.env`。** 密码和宿主机端口都从这里读；`.env` 被忽略、不进快照：
```bash
make docker-env
```
只在没有 `.env` 时生成（已有就什么都不做），末行 `已生成 …`（`…` 是你仓库的位置）。默认宿主机端口：MySQL `3306`、ES `9200`、Qdrant `6333`、backend `8100`、frontend `8080`——frontend 的 `8080` 和第 9 页手动的 `8081` 不是一个（编排重新分了门牌号）；第 1 页绕开 3306 就是因为它常被本机 MySQL 占着。哪个被占，就改 `.env` 里对应那行（`MYSQL_HOST_PORT` / `ES_HOST_PORT` / `QDRANT_HOST_PORT` / `BACKEND_HOST_PORT` / `FRONTEND_HOST_PORT`），**别改 `compose.yaml`**，改完重跑 `make docker-up`；smoke 会自己问 compose 前端实际端口。

**第 4 步：起整座城。**
```bash
make docker-up
```
它等于 `docker compose up -d --build`：先构建 backend / frontend 镜像，再按依赖顺序起六个服务。**第一次要几分钟到十几分钟**（拉镜像、装 Python 依赖、构建前端），屏幕一直在打 `#1 …` 和 `Container ... Started`，别以为卡死；它要等 init 成功、backend / frontend 起来才把提示符还给你，中断了重跑一次就行。

**第 5 步：看状态。** 先 `docker compose ps`，再 `docker compose ps -a`。

**第 6 步：一键验收。**
```bash
make docker-smoke
```
它自己会再 `up` 一次（幂等），然后 8 步逐条验，最后一行 `DOCKER SMOKE PASS`。停整座城用 `make docker-down`（保留数据卷）；`make docker-reset` 连数据卷一起删（破坏性，会让你输入 yes 再动手）。**先别停**——“拆一刀”还要用它。

## 你应该看到

第 4 步末尾你会看到 init 先 `Started` 再 `Exited`，backend `Healthy`，frontend 最后 `Started`；第 5 步 `docker compose ps` 只有 **5 行**（节选 NAME / STATUS 两列，终端里还有 IMAGE / COMMAND / SERVICE / PORTS）：

```text
shopkeeper-rebuild-backend-1        Up 2 minutes (healthy)
shopkeeper-rebuild-elasticsearch-1  Up 4 minutes (healthy)
shopkeeper-rebuild-frontend-1       Up About a minute (healthy)
shopkeeper-rebuild-mysql-1          Up 4 minutes (healthy)
shopkeeper-rebuild-qdrant-1         Up 4 minutes (healthy)
```

`docker compose ps -a` 多出第六行——只跑一次的那个：`shopkeeper-rebuild-init-1   Exited (0) 2 minutes ago`。frontend 的健康检查比 backend 晚几秒，刚起好时可能短暂显示 `health: starting`，等一下再刷就对了。

第 6 步 `make docker-smoke`（节选；第 1 步的构建日志、第 8 步的检查明细从略）：

```text
== 1/8 启动 stack（含一次性 init） ==
== 2/8 等待 http://127.0.0.1:8080/api/health ==
health: {"status":"ok","stage":"S7"}
== 3/8 五个长驻服务 healthy + init 正常退出 ==
services: backend=running, elasticsearch=running, frontend=running, init=exited, mysql=running, qdrant=running
== 4/8 /api/steps = 12 ==
steps=12
== 5/8 经 http://127.0.0.1:8080 发起真实查询（结果非空；是否流式由 nginx 生效配置把关） ==
sse_verdict=streamed
result rows=1 columns=1 sse_chunks=24
nginx: /api/query 的代理缓冲已关闭
== 6/8 nginx 的 /api/ 代理确实关着缓冲 ==
nginx: /api/query 的代理缓冲已关闭
== 7/8 只读账号验证 ==
PASS: 该账号在 dw 上只有 SELECT
== 8/8 S2 元知识对账（init 配置一次性执行） ==
S2 VERIFY PASS
== init 幂等（必须跳过重建） ==
DOCKER INIT PASS
DOCKER SMOKE PASS
```

## 对账

- 猜 1：只跑一次的是 **init**。`docker compose ps` 默认只列 running，所以第一张表里没有它；`ps -a` 才看到 `Exited (0)`。它退出码 0，backend 才被允许启动。
- init 为什么必须一次性：它干三件事再退出——等 mysql / ES / qdrant 健康、开通并验证只读账号、校验元知识（不对就重建）。常驻只会白占资源，还让“初始化到底成功没有”没有信号；`restart: "no"` + 非零退出即失败。
- `depends_on` 的健康检查：init 用 `service_healthy` 等三座存储；backend 用 `service_completed_successfully` 等 init 退出码 0；frontend 用 `service_healthy` 等 backend。少了这些条件，compose 只按启动顺序拉，init 可能比库快、backend 可能没初始化就接客——起得来，但没初始化。
- 8 步各防什么：1/8 起整栈；2/8 打通 nginx→backend 入口链；3/8 五个常驻 healthy 且 init 退出 0（防“只看 running，不看 health 和 init”）；4/8 `/api/steps` 正好 12（防契约没进镜像）；5/8 真查询出结果（防接口通但查不出数；`sse_chunks` 会有一两个出入，判据是 `sse_verdict=streamed` 和 `rows=1`）；6/8 nginx 的 `/api/` 真的 `proxy_buffering off`（防流被攒成整包）；7/8 只读账号真写不了（防“只读只在文档里”）；8/8 元知识对账 + 再跑一次 init 必须跳过重建（防初始化结果不对、一次性脚本不可重跑）。
- 起得来 ≠ 部署好：`docker compose up` 成功只说明容器建起来了——健康可能还在 starting、init 可能已失败退出（默认 `ps` 还看不到）、查询可能 502、流可能被 nginx 攒住。smoke 每一步都是一条判据，红一步就 `DOCKER SMOKE FAIL`，并把 `ps -a` 和相关日志全打出来。

> **你现在拥有**：一套“一条命令重建、一条命令验收”的部署——`compose.yaml` 写清怎么起和依赖顺序，`scripts/docker-smoke.sh` 写清“起对了没有”；换台机器 clone 下来，两条命令复跑同一套判据。

## 拆一刀

L2 的级考核：拆编排。

1. 先一键停：`make docker-down`（容器和网络删掉，数据卷保留）。
2. 打开 `compose.yaml`，把 `init:` 整段删掉（从 `init:` 到它最后一行 `condition: service_healthy`；下一段就是 `backend:`），再把 `backend` 里指向它的三行依赖（`depends_on:` / `init:` / `condition: service_completed_successfully`）一起删掉，Ctrl+S。删完编排合法，`make docker-up` 能起——只是少了一个 init。
3. 跑 `make docker-smoke`。它会在第 **3/8** 步红（它会先轮询两分多钟等 init，别以为卡死）：
```text
== 3/8 五个长驻服务 healthy + init 正常退出 ==
init 没有成功退出（state=缺失, exit=?）
DOCKER SMOKE FAIL: 120 秒内服务状态没齐
```
后面跟着 5 行 `ps -a` 和日志：五座设施全 healthy、`/api/health` 也回 200——只看这些，部署像好的；但没有 init，下一次从零初始化就没人做了。**起得来**，不等于部署好。
4. 还原：`scripts/lab reset p13-before --yes`，末行 `现在工作区与快照 "p13-before" 完全一致。`；再 `make docker-up`（init 回来会重跑一次，backend / frontend 重建，等它健康），最后 `make docker-smoke` 回到 `DOCKER SMOKE PASS`。smoke 第 2 步会重新等 `/api/health`（最多 360 秒），等不到别慌，先看它打出来的日志。整座城先留着跑——L3 的“审”要在它上面做。
