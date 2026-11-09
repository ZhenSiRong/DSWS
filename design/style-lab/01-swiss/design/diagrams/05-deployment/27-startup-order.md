# 27 · 启动顺序与失败停点

**一句话**：`docker compose up` 是一道四级闸门——三存储 healthy → `init` 退出 0 → `backend` healthy → `frontend` 启动；任何一级不过，后面的服务都不会起来。

**这张图回答**：谁在等谁？每级等多久？失败会停在哪一步？`init` 内部又做了什么？

**图例**：参与者用真实进程名；`init` 内部按 `docker_init.py` 的实际调用顺序展开。

**关键元素**：
- MySQL healthcheck：`mysqladmin ping`，`5s × 60`，`start_period 30s`。
- Elasticsearch healthcheck：`_cluster/health?wait_for_status=yellow`，`10s × 30`，`start_period 30s`。
- Qdrant healthcheck：`/readyz` 返回 200，`10s × 30`，`start_period 10s`（要求 Qdrant ≥ v1.5.0）。
- `init`：`depends_on` 三存储 `service_healthy`；内部再轮询三项（每项最多 180s），随后开通 `dw_reader`、验证只读、`--verify` 元知识；校验失败才 `--fresh` 重建并再次 `--verify`。
- `backend`：`depends_on init: service_completed_successfully`；只有 `init` 退出 0 才启动。
- `frontend`：`depends_on backend: service_healthy`。
- 失败停点：存储不 healthy → 停在 `init` 前；`init` 非 0 → 停在 `backend` 前；`backend` 不 healthy → 停在 `frontend` 前。

**证据**：
- `compose.yaml` L29–L36（MySQL）、L49–L58（ES）、L67–L81（Qdrant）、L98–L104（`init`）、L131–L143（`backend`）、L158–L168（`frontend`）。
- `backend/app/scripts/docker_init.py` L41–L118：`wait_for_services` → `initialize`（开通只读账号 → 验证 → `--verify` → 必要时 `--fresh` → 再 `--verify`）。
- `docs/DOCKER-DEPLOY.md` §2：五步等待顺序与「`init` 退出 0 后 backend 才启动」。
- `docs/DOCKER-DEPLOY.md` §7：backend 固定单 worker（取消注册表是进程内状态）。

**边界**：顺序与超时是 `compose.yaml` / `docker_init.py` 的文件事实（✅）；本工作树没有 Docker socket 权限，未实际观察过一次 `up` 的完整时序（⚪）。`init` 的「跳过重建」路径在 `docs/DOCKER-HANDOFF.md` §6.1 有他机 smoke 记录（🟡，非本工作树复跑）。
