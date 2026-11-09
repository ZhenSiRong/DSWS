# 25 · Docker Compose 拓扑

**一句话**：`compose.yaml` 用一条默认网络把六个服务连起来，三个命名卷承载状态，`init` 是唯一的一次性任务。

**这张图回答**：哪六个服务？谁依赖谁？数据落在哪？`init` 为什么和另外五个不一样？

**图例**：橙色=`init` 一次性构建任务；青色=三存储与卷；紫色=`backend` / `frontend` 查询时服务；灰色=宿主挂载与命名卷。

**关键元素**：
- 三存储：`mysql`、`elasticsearch`、`qdrant`，各自带 healthcheck。
- `init`：与 `backend` 共用镜像 `shopkeeper-rebuild/backend:local`，但 `restart: "no"`，正常退出后不再启动。
- `backend`：只拿 `dw_reader` 只读凭据；`frontend`：nginx，唯一对外入口。
- 依赖方向：三存储 healthy → `init` 启动；`init` 退出 0 → `backend` 启动；`backend` healthy → `frontend` 启动。
- 默认网络未显式声明，Compose 按项目名生成 `shopkeeper-rebuild_default`；项目名来自 `compose.yaml` 的 `name:`（可被 `COMPOSE_PROJECT_NAME` 覆盖，卷名与网络名随之变化）。
- 命名卷：`mysql_data`、`es_data`、`qdrant_data`；另有一个只读绑定 `./fixtures/dw.sql` → MySQL 初始化目录。

**证据**：
- `compose.yaml` L1（项目名）、L11–L168（六服务）、L98–L104（`init` 依赖三存储 healthy）、L131–L133（`backend` 等 `init` 完成）、L158–L160（`frontend` 等 `backend` healthy）、L170–L173（三个卷）。
- `compose.yaml` L28（`fixtures/dw.sql` 只读挂载到 `docker-entrypoint-initdb.d`）。
- `docs/DOCKER-DEPLOY.md` §5：卷实际名称为 `shopkeeper-rebuild_mysql_data` / `_es_data` / `_qdrant_data`。
- `docs/DOCKER-HANDOFF.md` §1：拓扑与一次性 `init` 的既定事实。

**边界**：本工作树 Docker socket 无权限（`docker ps` 报 `permission denied`），未实际启动该拓扑，标 ⚪；服务名、卷名、依赖条件均逐字取自 `compose.yaml`。图中不画镜像仓库、跨主机网络与高可用——`docs/DOCKER-DEPLOY.md` §7 明确不提供。
