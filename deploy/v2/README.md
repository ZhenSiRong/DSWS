# DSWS v2 实例部署（LangGraph + 原版界面）

## 目标

在旧实例（`shopkeeper-rebuild`，前端 `:5050`）之外，再起一套 **v2**：

- 后端：LangGraph `StateGraph` 执行 12 节点（`backend/app/agent/graph.py`）
- 前端：原版 `shopkeeper-agent` 界面（React 19 + Tailwind 3.4），只加 SSE 展示适配
- 复用旧实例的 MySQL / Elasticsearch / Qdrant（数据与只读账号已就绪）
- 对外入口：`http://<host>:5051`，后端只绑 `127.0.0.1:8101`

## 当前部署状态（2026-11-05）

| 项 | 值 |
|---|---|
| v2 前端 | `http://8.155.135.97:5051`（`0.0.0.0:5051->80/tcp`） |
| v2 后端 | `127.0.0.1:8101->8100/tcp` |
| 容器 | `dsws-v2-frontend-1`、`dsws-v2-backend-1`，均 healthy |
| 前端镜像 | `dsws-v2/frontend-original:local`（旧重建镜像 `dsws-v2/frontend:local` 保留可回滚） |
| 旧实例 | `http://8.155.135.97:5050`，未重启、仍 healthy |
| 云端目录 | `/opt/dsws-v2/repo`（源码 + `compose.v2.yaml` + `.env`） |
| 构建日志 | `/opt/dsws-v2/build.log` |

## 云端目录

```
/opt/dsws-v2/repo/
├── backend/ contracts/ fixtures/ docker/
├── original-frontend/   # 原版界面：dist/ + nginx.conf + Dockerfile.original
├── frontend/            # 旧教学重建版源码（compose 已不引用，保留备查）
├── compose.v2.yaml
└── .env                 # 从 /opt/dsws/repo/.env 复制，改两个端口
```

> 前端构建上下文是 `./original-frontend`：在本地 `deliverable/v2/original-frontend/`
> 执行 `npm run build`，把 `dist/`、`nginx.conf`、`Dockerfile.original`、`.dockerignore`
> 上传到 `/opt/dsws-v2/repo/original-frontend/`。`Dockerfile.original` 只做
> 「nginx + 静态 dist」，不在云端跑 npm。

## 部署

```bash
# 0) 在 v2 工作区准备构建上下文（compose 文件来自本仓库 deploy/v2/）
cd <v2-worktree>
cp /path/to/DSWS-design/deploy/v2/compose.v2.yaml ./compose.v2.yaml

# 1) 打包并上传（避免 tar over ssh 在弱网下 gzip 截断）
#    original-frontend/dist 是构建产物，必须一起上传，不要 exclude
tar czf /tmp/opencode/dsws-v2.tgz \
  --exclude='*/.venv' --exclude='*/node_modules' --exclude='*/__pycache__' \
  backend original-frontend contracts fixtures docker compose.v2.yaml
scp -P 2222 -i design/_阿里云10.15.pem /tmp/opencode/dsws-v2.tgz \
  root@8.155.135.97:/opt/dsws-v2.tgz
ssh -p 2222 -i design/_阿里云10.15.pem root@8.155.135.97 '
  rm -rf /opt/dsws-v2/repo && mkdir -p /opt/dsws-v2/repo &&
  tar xzf /opt/dsws-v2.tgz -C /opt/dsws-v2/repo
'

# 2) 生成 .env（复用旧实例的密码与镜像配置，只改端口）
ssh -p 2222 -i design/_阿里云10.15.pem root@8.155.135.97 '
  cd /opt/dsws-v2/repo &&
  cp /opt/dsws/repo/.env .env &&
  sed -i "s/^FRONTEND_HOST_PORT=.*/FRONTEND_HOST_PORT=5051/; s/^BACKEND_HOST_PORT=.*/BACKEND_HOST_PORT=8101/" .env
'

# 3) 国内网络：重写锁文件到腾讯云镜像（版本不变，只换下载 URL）
ssh -p 2222 -i design/_阿里云10.15.pem root@8.155.135.97 '
  cd /opt/dsws-v2/repo/backend &&
  uv lock --index-url https://mirrors.cloud.tencent.com/pypi/simple
'

# 4) 构建并启动
ssh -p 2222 -i design/_阿里云10.15.pem root@8.155.135.97 '
  cd /opt/dsws-v2/repo && docker compose -f compose.v2.yaml up -d --build
'
```

## 国内网络构建注意（本次踩过的坑）

1. **`ghcr.io` 的 uv 镜像极慢**（21.68MB 层约 8KB/s）。把云端 `.env` 的
   `UV_IMAGE` 改成 DaoCloud 的 ghcr 镜像：
   ```text
   UV_IMAGE=ghcr.m.daocloud.io/astral-sh/uv:0.8.22
   ```
   `python` / `node` / `nginx` 继续用 `.env` 里已有的 `docker.m.daocloud.io` 镜像。
2. **`uv.lock` 锁死了 `files.pythonhosted.org` 的下载 URL**。`uv sync --frozen`
   会按锁文件里的 URL 下载，绕过 `UV_INDEX_URL`，在国内服务器上会卡住。
   解决：在云端用国内镜像重写锁文件（本次用腾讯云，版本与仓库锁文件完全一致）：
   ```bash
   cd backend && uv lock --index-url https://mirrors.cloud.tencent.com/pypi/simple
   ```
   仓库内的 `uv.lock` 保持 pypi.org 原始来源，保证可移植；云端锁文件只用于本次部署。
3. **BuildKit cache mount + uv 解包在该服务器上会卡死在 futex**（CPU 0%、无网络连接）。
   `docker/backend.Dockerfile` 已去掉 `--mount=type=cache,target=/root/.cache/uv`，
   并设置 `UV_NO_CACHE=1`、`UV_COMPILE_BYTECODE=0`、`UV_HTTP_TIMEOUT=180`。
4. 如果构建再次卡住，先清理：
   ```bash
   pkill -9 -f '^docker compose'
   pkill -9 -f '^uv sync'
   docker builder prune -af
   ```

## 验证

```bash
curl -s http://8.155.135.97:5051/api/health          # {"status":"ok","stage":"S7"}
curl -sN -X POST http://8.155.135.97:5051/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序"}'
```

- 12 个步骤事件齐全、以 `result` 收尾 → LangGraph 链路真实执行
- 页面标题为 `电商问数 | Shopkeeper Agent`，正文不含「教学版」「从零重建」→ 原版界面生效
- 容器镜像为 `dsws-v2/frontend-original:local`，`/healthz` 返回 `ok` → 前端健康
- 旧实例 `:5050` 不受影响（两套容器、两套端口、共享基础设施）

本次实测结果与证据见 `deliverable/v2/README-v2.md`；v1/v2 三项差距对照见
`deliverable/v2/PRD-差异补齐.md`。
