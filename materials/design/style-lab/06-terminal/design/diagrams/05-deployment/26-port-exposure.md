# 26 · 宿主端口与容器端口暴露面

**一句话**：默认只有 `frontend` 的 `8080 → 80` 监听所有网卡，其余四个发布端口全部锁在 `127.0.0.1`，`init` 没有宿主端口。

**这张图回答**：谁能从局域网进来？哪些端口只能本机访问？容器之间走什么端口？

**图例**：紫色=查询时服务；青色=三存储；橙色=一次性 `init`；灰色=访问面边界。

**关键元素**：
- `frontend`：`${FRONTEND_BIND:-0.0.0.0}:${FRONTEND_HOST_PORT:-8080}:80`，默认 `0.0.0.0`，是唯一对外入口；要收紧就设 `FRONTEND_BIND=127.0.0.1`。
- `backend`：`127.0.0.1:${BACKEND_HOST_PORT:-8100}:8100`。
- `mysql`：`127.0.0.1:${MYSQL_HOST_PORT:-3306}:3306`。
- `elasticsearch`：`127.0.0.1:${ES_HOST_PORT:-9200}:9200`。
- `qdrant`：`127.0.0.1:${QDRANT_HOST_PORT:-6333}:6333`。
- `init`：无 `ports:`；只能 `docker compose run --rm --no-deps init` 进入，或由 `up` 自动执行一次。
- 容器内：`frontend` 通过 `backend:8100` 反向代理 `/api/`；`backend` 通过容器 DNS 访问三存储。

**证据**：
- `compose.yaml` L24–L25（MySQL）、L45–L46（ES）、L63–L64（Qdrant）、L129–L130（backend）、L155–L157（frontend，含 `FRONTEND_BIND` 注释）、L83–L104（`init` 无 `ports`）。
- `docker/nginx.conf`：`listen 80`、`location /api/` 代理到 `http://backend:8100`。
- `docs/DOCKER-DEPLOY.md` §1：「只有前端 `8080` 监听所有网卡，其余端口都只绑定 `127.0.0.1`」。
- `docs/DOCKER-DEPLOY.md` §2.1：容器 `backend` 与本机 `make dev-backend` 都占 `8100`，不能同时跑。

**边界**：端口映射是文件事实（✅），但本工作树无 Docker 权限，未用 `docker compose port` 复核实际发布结果（⚪）。`FRONTEND_BIND` 默认 `0.0.0.0` 且无鉴权，是文档写明的取舍（`docs/DOCKER-HANDOFF.md` §3 B11）。
