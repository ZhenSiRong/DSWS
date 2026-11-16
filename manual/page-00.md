# 第 0 页 · 开课前准备

## 这一页构建什么

把克隆下来的仓库变成「能开始第 1 页」的状态：工具装齐、依赖装好、三个端口空着。这一页没有代码，也不讲业务概念，只补克隆后缺的东西。

## 提前说明

先确认你已经克隆好仓库，终端停在**仓库根目录**（`ls` 能看到 `Makefile`、`backend/`、`fixtures/` 的那一层），并且用的是 **bash**（Windows 用 Git Bash 或 WSL；macOS 默认是 zsh，先敲一下 `bash`）。以下命令都在这一层敲。

**安装**好五样（安装方法见官方安装页）：**Docker**（https://docs.docker.com/get-docker/ ；装完要让它**运行**起来，口语常说“跑起来”）、**uv**（https://docs.astral.sh/uv/ ）、**Node.js LTS + npm**（https://nodejs.org/ ）、**GNU Make**（装好就是 `make` 命令）、**curl**（第 3–9 页全靠它，多数系统自带）。

`.env`、`backend/.venv`、`frontend/node_modules` 都被 `.gitignore` 忽略，克隆下来没有：`.env` 不用你建（第 1 页会从 `.env.example` 读），后两个由 `make install` 生成，**别手动 pip 装**。

## 动手

**第 1 条 · 确认 Docker 装好了（装完先让它跑起来：Docker Desktop 打开窗口，Linux 启动 docker 服务）。**

```bash
docker --version
```

**第 2 条 · 确认 uv、Node 和 curl 装好了（第 3–9 页全靠 curl）。**

```bash
uv --version
node -v
curl --version | head -1
```

**第 3 条 · 装依赖（必须在仓库根目录；第一次下载，再跑只要几秒，能重复跑）。**

```bash
make install
```

**第 4 条 · 确认 Python 环境被造出来了。**

```bash
backend/.venv/bin/python -V
```

**第 5 条 · 确认三个端口空着。**

```bash
for p in 3307 8000 8081; do (echo >/dev/tcp/127.0.0.1/$p) 2>/dev/null && echo "$p 被占用" || echo "$p 空闲"; done
```

## 你应该看到

第 3 条最长，真跑输出是（中间 62 行 `+ 包名==版本` 太长，只留两行）：

```text
cd backend && uv sync --frozen
Using CPython 3.14.8
Creating virtual environment at: .venv
Prepared 62 packages in 12ms
Installed 62 packages in 41ms
 + annotated-doc==0.0.5
 + annotated-types==0.8.0
…（其余安装清单略）
cd frontend && npm ci
added 118 packages, and audited 125 packages in 3s
```

其余四条按顺序（`/` 分隔同一命令的多行输出）：

| 第几条 | 真实输出 |
|---|---|
| 1 | `Docker version 29.1.3, build 29.1.3-0ubuntu3~24.04.2` |
| 2 | `uv 0.13.1 (x86_64-unknown-linux-gnu)` / `v24.21.0` / `curl 8.5.0`（后面还有一长串编译信息，不用管） |
| 4 | `Python 3.14.8` |
| 5 | `3307 空闲` / `8000 空闲` / `8081 空闲` |

![第 0 页 · 开课前准备命令的真实输出](images/page-00-prep.png)

版本号、包数量、耗时每次不同，看到同类的行就算对上。尾部出现 `npm warn ...`、`vulnerabilities` 是提醒不是失败；再跑一遍 `make install` 会变成 `Checked 62 packages in 0.55ms` 这种一行，照样算成功。
（上面这张图只覆盖第 1–5 条准备命令；文末「重来一遍」是删容器和文件的破坏性操作，故不进图。）

## 卡住了看这里

- 报 `command not found`：对应的工具没装好，回「提前说明」装完，重开一个终端再试。
- `make install` 中途失败，或 `backend/.venv/bin/python: No such file or directory`：先修第 3 条（多半是网络，重跑一次；还不行就分开跑 `cd backend && uv sync --frozen` 和 `cd frontend && npm ci`，看哪段先红）。
- `docker --version` 有输出不代表 daemon 在跑：`docker info` 会报 `Cannot connect to the Docker daemon`；第 1 页报这句就是服务没启动，启动 Docker Desktop / `sudo systemctl start docker` 后重跑。
- Linux 报 `permission denied ... docker.sock`：当前用户不在 docker 组，`sudo usermod -aG docker $USER` 后**重新登录**再试。
- `uv sync` 卡在下载 Python：机器上没有 3.12+ 时 uv 会联网拉解释器，网络受限就会卡；先 `uv python list` 看本机有没有可用的 3.12+。
- 端口显示「被占用」：`ss -tlnp | grep -E ':(3307|8000|8081) '` 列出占用者，把 PID 那列找出来停掉；看不到 PID 说明是 root 的进程（比如系统自带的 MySQL），加 `sudo` 再看：`sudo ss -tlnp | grep -E ':(3307|8000|8081) '`。第 1 页写死 3307、第 3 页写死 8000、第 9 页写死 8081，改端口要连带改后面命令。

## 自己改一下

把第 5 条里的 `3307` 改成 `3306` 再跑：多半显示「被占用」——那是本机自带的 MySQL，也是第 1 页偏要用 3307 的原因。

## 重来一遍（回到起点）
一轮做完会留下 `lab-mysql`、`lab-nginx` 两个容器、仓库根目录的 `lab/`、终端 1 里的 uvicorn；先按 `Ctrl+C` 停终端 1，再敲（别用 `docker system prune`——会误删本机别的栈）：

```bash
docker rm -f lab-nginx lab-mysql   # 数据随容器消失；重跑第 1 页会重新执行 fixtures/dw.sql
rm -rf lab
docker ps -a --format '{{.Names}}' | grep '^lab-' || echo "容器干净"   # 验证 1
ss -tln | grep -E ':(3307|8000|8081) ' || echo "端口全空"              # 验证 2
```

你应该看到最后两条的真实输出：`容器干净`、`端口全空`；`docker rm` 会先打印 `lab-nginx`、`lab-mysql` 两个名字。

| 想回到 | 删掉 | 保留 |
|---|---|---|
| 第 3 页 | `lab-nginx`、整个 `lab/` | `lab-mysql`（数据不用重新导入） |
| 第 7 页 | `lab-nginx`，并把 `lab/app.py` 退回第 6 页的版本 | `lab-mysql`、`lab/` |
| 只重第 9 页 | 只删 `lab-nginx` | `lab-mysql`、`lab/`（配置和页面直接重用） |
