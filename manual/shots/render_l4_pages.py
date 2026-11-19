#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_l4_pages.py —— 真跑练本第 13 页与 L4 第 18–22 页的命令，渲染 8 张终端运行截图。

一条命令重跑全部图（在仓库根目录）：

    python3 manual/shots/render_l4_pages.py

做五件事：

1. 在 `/tmp/shots-l4` 建一个**临时副本**（rsync 仓库，排除 `.git` / `.lab` /
   `node_modules` / 缓存，再把 `frontend/node_modules` 复制进来给 npm test 用）。
   - 副本 `.env` 的 5 个 host 端口改成隔离端口：mysql 13347 / ES 19247 /
     Qdrant 16367 / backend 18147 / frontend 18087，`FRONTEND_BIND=127.0.0.1`；
   - 副本 `compose.yaml` 只加两类**隔离运行所需**的行：`container_name:
     shopkeeper-rebuild-<svc>-1`（让截图里的 NAME 列与页面原文一致，项目名仍
     由 `-p shotsl4` 隔离）和 `mem_limit`（防单容器把宿主内存吃穿）。
   - **仓库文件一个字都不改**：所有改动都只发生在 /tmp 副本里。
2. 页面命令按原文执行，执行侧只做两处替换（与 `render_l2_pages.py` /
   `render_l3_pages.py` 约定一致）：`docker compose` 加 `-p shotsl4`，页面默认
   端口 8080 换成隔离端口 18087。**渲染进图的仍是页面原文**：执行时出现的隔离
   端口在渲染前换回页面默认端口（`18087→8080`、`13347→3306`…），所以图里不会
   出现隔离端口。
3. 按页真跑命令（PTY 捕获，保留学生终端里的真实输出顺序）：
   - 第 13 页：`docker compose ps` / `ps -a` → `make docker-smoke` 8 步 PASS；
   - 第 22 页：全量 pytest（813 passed, 30 skipped）+ npm test（40 passed）+
     第二次 `make docker-smoke`；再按页里的「终端 B 自动等待循环」在 init
     退出窗口内注入 `GRANT ALL`，让同一条 smoke 在第 7 步精确变红；
   - 第 18 页：开通只读账号 → `--verify-ro-account` PASS（写操作被拒 1142）→
     `GRANT ALL` → 同一条判据变红 `FAIL: 3 项问题`（两段对照）；
   - 第 19/20/21 页：纯离线判据（`security --check` / 语料表 / 取消测试 +
     `record_sse --check` / `/api/steps` + `/api/errors` + 夹具 + npm test）。
4. 渲染 8 张 3200×…（宽 3200 = 1600 CSS px @2x，高 ≥1800）深色终端图，并做图文
   一致性自检：页面「## 你应该看到」/「## 拆一刀」的样例块逐行对账（`…` 当通配
   符；`sse_chunks` / `sse_verdict` / 秒数 / ps 的 Up 时长按通配）、OCR 关键字
   抽检、禁止字符串（用户名 / 主机名 / 绝对路径 / 隔离端口 / 口令）、PNG 尺寸。
5. 跑完 `docker compose -p shotsl4 down -v`（容器 / 卷 / 网络一起删），删临时副本，
   并核对用户栈（`dsws-*` / `lab-*` / `downloads-*` 等）前后一致。

输出（只写这 8 个文件）：

    manual/images/page-13-ps.png         第 13 页 `docker compose ps` / `ps -a`（5 healthy + init Exited(0)）
    manual/images/page-13-smoke.png      第 13 页 `make docker-smoke` 8 步 PASS
    manual/images/page-18-account.png    第 18 页 开通→PASS(1142)；GRANT ALL→FAIL: 3 项问题
    manual/images/page-19-policy.png     第 19 页 36/36 + 11/11 + 8/8 + S5 PASS
    manual/images/page-20-cancel.png     第 20 页 6 passed + 114 passed + S7 SSE RECORD PASS
    manual/images/page-21-observe.png    第 21 页 12 步 / 16 码 / S7 PASS / 30 passed + 40 passed
    manual/images/page-22-smoke.png      第 22 页 813 passed, 30 skipped + 40 passed + DOCKER SMOKE PASS
    manual/images/page-22-ablation.png   第 22 页 L4 级考核：窗口内 GRANT ALL → 第 7 步红

依赖（本机已有，不新装）：docker（compose v2）、rsync、google-chrome、ImageMagick
convert/identify、仓库自带 `backend/.venv`；OCR 自检可选依赖 tesseract + Pillow
（没装就跳过，主对账用渲染前原文完成）。

调试用（不参与正常流程）：

    python3 manual/shots/render_l4_pages.py --keep                 # 留 /tmp/shots-l4 与隔离栈
    python3 manual/shots/render_l4_pages.py --keep-captures        # 保留 /tmp/shots-l4-captures.json
    python3 manual/shots/render_l4_pages.py --render-only FILE     # 用捕获缓存只重渲染 + 自检
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- 常量

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"
PAGE_MD = {
    13: REPO / "manual" / "page-13.md",
    18: REPO / "manual" / "page-18.md",
    19: REPO / "manual" / "page-19.md",
    20: REPO / "manual" / "page-20.md",
    21: REPO / "manual" / "page-21.md",
    22: REPO / "manual" / "page-22.md",
}

WORK = Path("/tmp/shots-l4")                     # 临时副本（隔离，跑完删）
PROJECT = "shotsl4"                              # compose project（专用，不碰用户栈）
CAPTURES = Path("/tmp/shots-l4-captures.json")   # 捕获缓存（调试；正常跑完删）
CONTAINER_PREFIX = "shopkeeper-rebuild"          # 页面里的容器名前缀
INIT_CONTAINER = f"{CONTAINER_PREFIX}-init-1"
SERVICES = ("mysql", "elasticsearch", "qdrant", "backend", "frontend")

# 隔离端口（任务约定；页面默认值 3306/9200/6333/8100/8080 一个都不占）
HOST_PORTS = {
    "MYSQL_HOST_PORT": 13347,
    "ES_HOST_PORT": 19247,
    "QDRANT_HOST_PORT": 16367,
    "BACKEND_HOST_PORT": 18147,
    "FRONTEND_HOST_PORT": 18087,
}
# 执行侧端口 → 页面默认端口（渲染时换回，图里只出现页面原文端口）
DISPLAY_PORTS = {
    HOST_PORTS["MYSQL_HOST_PORT"]: 3306,
    HOST_PORTS["ES_HOST_PORT"]: 9200,
    HOST_PORTS["QDRANT_HOST_PORT"]: 6333,
    HOST_PORTS["BACKEND_HOST_PORT"]: 8100,
    HOST_PORTS["FRONTEND_HOST_PORT"]: 8080,
}
DISPLAY_FRONTEND_PORT = 8080

WINDOW_W_CSS = 1600                              # 窗宽 1600 CSS px
DEVICE_SCALE = 2                                 # @2x：PNG 宽 3200 px
WINDOW_H_CSS = 3600                              # 先渲高一点，再 -trim 到内容
MIN_PNG_H = 1800                                 # 与 L2/L3 一致：高至少 1800 px
PAGE_BG = "#04070b"                              # 与 term_render.CSS 的 --page-bg 一致

# 每次运行都会变、或只属于隔离环境、不该出现在图里的东西
FORBIDDEN = [
    "/home/", "/root/", "/Users/", "/tmp/", "/var/", "zhensirong", ".dsh",
    "shots-l4", "shotsl4", "uv.lock", "MSYS",
    *[str(port) for port in HOST_PORTS.values()],
]

# 每张图的 OCR 关键字（tesseract 只有 eng 语言包：英文/数字可信；中文关键行
# 用渲染前的捕获原文逐字对账，见 run_checks）
OCR_KEYWORDS = {
    "page-13-ps.png": ["shopkeeper-rebuild-backend-1", "healthy", "Exited (0)",
                       "shopkeeper-rebuild-init-1"],
    "page-13-smoke.png": ["DOCKER SMOKE PASS", "DOCKER INIT PASS",
                          "S2 VERIFY PASS", "8/8", "PASS: 该账号"],
    "page-18-account.png": ["1142", "FAIL: 3", "PASS: 该账号",
                            "GRANT ALL PRIVILEGES", "dw_reader"],
    "page-19-policy.png": ["36/36", "11/11", "8/8", "S5 PASS", "47"],
    "page-20-cancel.png": ["6 passed", "114 passed", "S7 SSE RECORD PASS",
                           "CANCELLED"],
    "page-21-observe.png": ["/api/steps", "/api/errors", "S7 SSE RECORD PASS",
                            "30 passed", "40 passed"],
    "page-22-smoke.png": ["813 passed", "30 skipped", "40 passed",
                          "DOCKER SMOKE PASS", "S2 VERIFY PASS"],
    "page-22-ablation.png": ["FAIL: 3", "DOCKER SMOKE FAIL", "GRANT GRANT ALL",
                             "GRANT USAGE"],
}

# 页面里必须存在的图片嵌入行（脚本不写页面，只核对；图与页对不上就报红）
EMBED_LINES = {
    13: [
        "![第 13 页 · `docker compose ps`：五个长驻服务全 healthy；`ps -a` 里 init `Exited (0)`](images/page-13-ps.png)",
        "![第 13 页 · `make docker-smoke`：8 步逐条验，末行 DOCKER SMOKE PASS](images/page-13-smoke.png)",
    ],
    18: [
        "![第 18 页 · 开通只读账号 → `PASS`（写操作被拒 1142）→ `GRANT ALL` 后变红 `FAIL: 3 项问题`](images/page-18-account.png)",
    ],
    19: [
        "![第 19 页 · `security --check`：36/36 拒 + 11/11 放行 + 8/8 基线，S5 PASS](images/page-19-policy.png)",
    ],
    20: [
        "![第 20 页 · `pytest -k cancel` 6 passed + `record_sse --check` S7 SSE RECORD PASS](images/page-20-cancel.png)",
    ],
    21: [
        "![第 21 页 · `/api/steps = 12`、`/api/errors = 16`、S7 SSE RECORD PASS、30 passed + 40 passed](images/page-21-observe.png)",
    ],
    22: [
        "![第 22 页 · 全量 pytest 813 passed, 30 skipped + npm 40 passed + DOCKER SMOKE PASS](images/page-22-smoke.png)",
        "![第 22 页 · L4 级考核：init 退出窗口内 GRANT ALL，smoke 第 7 步红 FAIL: 3 项问题](images/page-22-ablation.png)",
    ],
}

# ---------------------------------------------------------------- 复用 term_render

sys.dont_write_bytecode = True                   # 不在 manual/shots 里写 __pycache__
sys.path.insert(0, str(HERE))
import term_render as tr  # noqa: E402

# term_render 的 CSS 按窗宽 1100 写死，这里只把窗宽换成 1600，字体/配色/版式不变；
# 另加 .dim（「…（省略）」标注）与 .compact（ps 全表用 11.5px 才放得下）。
tr.CSS = tr.CSS.replace("1100px", f"{WINDOW_W_CSS}px")
if "1100px" in tr.CSS:
    raise RuntimeError("term_render.CSS 的窗宽没替换干净")
CSS = tr.CSS + (
    "\n.dim { color: var(--dim); }  /* …（省略）标注 */\n"
    ".compact pre { font-size: 11.5px; line-height: 1.5; }  /* ps 宽表 */\n"
)

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>]")

# ---------------------------------------------------------------- 小工具


def say(msg: str = "") -> None:
    print(msg, flush=True)


def section(title: str) -> None:
    say("")
    say("─" * 78)
    say(title)
    say("─" * 78)


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def mem_available_mb() -> int:
    """宿主可用内存（MemAvailable）。Windows VM 占 6GB 的机器上要盯这个。"""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except Exception:  # noqa: BLE001
        pass
    return -1


def docker_rows() -> list[tuple[str, str]]:
    """(容器名, compose project 标签) —— 用来核对没碰用户栈。"""
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format",
             "{{.Names}}\t{{.Label \"com.docker.compose.project\"}}"],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    rows = []
    for line in out.splitlines():
        if "\t" in line:
            name, proj = line.split("\t", 1)
            rows.append((name.strip(), proj.strip()))
    return rows


def user_stack_snapshot() -> list[str]:
    """用户栈快照：排除本项目（shotsl4）的容器，前后对比证明没碰别人的东西。"""
    return sorted(name for name, proj in docker_rows() if proj != PROJECT)


def project_containers() -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def decode(raw: bytes) -> str:
    return strip_ansi(raw.decode("utf-8", "replace")).replace("\r\n", "\n")


def base_env() -> dict:
    env = os.environ.copy()
    env.update({
        "UV_OFFLINE": "1",
        "TERM": "dumb",
        "NO_COLOR": "1",
    })
    return env


def run_pipe(cmd: str, cwd: Path, timeout: float,
             allowed: tuple[int, ...] = (0,),
             env_extra: dict | None = None) -> tuple[list[str], int]:
    """非交互命令：合并 stdout/stderr，按退出码校验。"""
    env = base_env()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["bash", "-c", cmd], cwd=cwd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, env=env,
    )
    lines = (proc.stdout or "").splitlines()
    if proc.returncode not in allowed:
        raise RuntimeError(
            f"命令失败（exit={proc.returncode}，允许 {allowed}）：{cmd}\n"
            "--- 输出末 30 行 ---\n" + "\n".join(lines[-30:])
        )
    return lines, proc.returncode


def run_pty(cmd: str, cwd: Path, timeout: float,
            allowed: tuple[int, ...] = (0,),
            env_extra: dict | None = None) -> tuple[list[str], int]:
    """交互式命令：用 PTY 捕获，保留学生终端里的真实输出顺序。

    stdout/stderr 交织的顺序（比如门禁的明细 + 末行 FAIL 摘要）只有 PTY 能原样保留；
    管道捕获会因缓冲把顺序打乱。
    """
    master, slave = pty.openpty()
    import fcntl
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 200, 240, 0, 0))
    env = base_env()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen(
        ["bash", "-c", cmd], cwd=cwd, stdin=slave, stdout=slave,
        stderr=slave, close_fds=True, env=env, start_new_session=True,
    )
    os.close(slave)
    chunks: list[bytes] = []
    deadline = time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=10)
                raise RuntimeError(f"命令超时（{timeout}s）：{cmd}")
            try:
                ready, _, _ = select.select([master], [], [], 0.5)
            except OSError:
                break
            if not ready:
                if proc.poll() is not None:
                    try:
                        while True:
                            data = os.read(master, 65536)
                            if not data:
                                break
                            chunks.append(data)
                    except OSError:
                        pass
                    break
                continue
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
    finally:
        try:
            os.close(master)
        except OSError:
            pass
    code = proc.wait(timeout=timeout)
    lines = decode(b"".join(chunks)).split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if code not in allowed:
        raise RuntimeError(
            f"命令失败（exit={code}，允许 {allowed}）：{cmd}\n"
            "--- 输出末 30 行 ---\n" + "\n".join(lines[-30:])
        )
    return lines, code


def exec_cmd(display_cmd: str) -> str:
    """页面命令 → 隔离环境执行命令：compose 加 `-p shotsl4`，8080 换隔离端口。"""
    out = re.sub(r"\bdocker compose\b", f"docker compose -p {PROJECT}", display_cmd)
    out = out.replace(f"127.0.0.1:{DISPLAY_FRONTEND_PORT}",
                      f"127.0.0.1:{HOST_PORTS['FRONTEND_HOST_PORT']}")
    return out


def display_line(line: str) -> str:
    """渲染前把执行侧的隔离端口换回页面默认端口（图里不出现隔离端口）。"""
    for exec_port, page_port in DISPLAY_PORTS.items():
        line = line.replace(f":{exec_port}", f":{page_port}")
    return line


def capture(records: dict, key: str, display_cmd: str, cwd: Path,
            timeout: float, allowed: tuple[int, ...] = (0,),
            with_env: bool = False,
            smoke: bool = False) -> list[str]:
    """真跑一条命令：记录「页面原文命令 + 真实输出」，供渲染和自检。"""
    cmd = exec_cmd(display_cmd)
    if with_env and not display_cmd.lstrip().startswith("source "):
        cmd = f"source scripts/export-docker-env.sh\n{cmd}"
    env_extra = {"COMPOSE_PROJECT_NAME": PROJECT} if smoke else None
    t0 = time.monotonic()
    lines, code = run_pty(cmd, cwd, timeout, allowed, env_extra)
    records[key] = {"cmd": display_cmd, "lines": lines, "exit": code}
    say(f"    $ {display_cmd}")
    say(f"      → exit {code}，{len(lines)} 行输出（{time.monotonic() - t0:.1f}s）")
    return lines


def capture_quiet(records: dict, key: str, display_cmd: str, cwd: Path,
                  timeout: float, allowed: tuple[int, ...] = (0,),
                  with_env: bool = False) -> list[str]:
    """上不了图的辅助命令（快照 / reset / 还原账号），用管道捕获。"""
    cmd = exec_cmd(display_cmd)
    if with_env and not display_cmd.lstrip().startswith("source "):
        cmd = f"source scripts/export-docker-env.sh\n{cmd}"
    lines, code = run_pipe(cmd, cwd, timeout, allowed)
    records[key] = {"cmd": display_cmd, "lines": lines, "exit": code}
    say(f"    $ {display_cmd}  → exit {code}，{len(lines)} 行")
    return lines


# ---------------------------------------------------------------- 工作区 / 隔离栈


def preflight() -> None:
    missing = [tool for tool in ("docker", "rsync", "google-chrome", "convert", "identify")
               if shutil.which(tool) is None]
    if missing:
        sys.exit(f"缺少依赖：{', '.join(missing)}（本脚本不装新依赖）")
    if not (REPO / "backend" / ".venv" / "bin" / "python").exists():
        sys.exit("backend/.venv 不存在；先按第 0 页准备好环境")
    if not (REPO / ".env").is_file():
        sys.exit("缺少 .env；先按第 13 页 `make docker-env` 生成")
    free = mem_available_mb()
    if 0 <= free < 1200:
        sys.exit(f"宿主可用内存只有 {free}MB，起不动隔离栈（任务约定：≥1200MB 才跑）")
    for port in HOST_PORTS.values():
        if port_open(port):
            sys.exit(f"端口 {port} 被占用；本脚本不杀别人的进程，先停掉占用者再重跑")


def patch_env(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for var, port in HOST_PORTS.items():
        text, n = re.subn(rf"^{var}=.*$", f"{var}={port}", text, flags=re.M)
        if n != 1:
            raise RuntimeError(f"副本 .env 里找不到 {var}= 这一行")
    text, n = re.subn(r"^FRONTEND_BIND=.*$", "FRONTEND_BIND=127.0.0.1",
                      text, flags=re.M)
    if n != 1:
        raise RuntimeError("副本 .env 里找不到 FRONTEND_BIND= 这一行")
    path.write_text(text, encoding="utf-8")


def patch_compose(path: Path) -> None:
    """副本 compose 只加隔离运行需要的两类键；仓库文件不动。"""
    limits = {"mysql": "1024m", "elasticsearch": "1280m", "qdrant": "768m",
              "init": "1024m", "backend": "1024m", "frontend": "256m"}
    text = path.read_text(encoding="utf-8")
    for svc, limit in limits.items():
        anchor = f"\n  {svc}:\n"
        if text.count(anchor) != 1:
            raise RuntimeError(f"副本 compose.yaml 里找不到唯一的 `  {svc}:`")
        text = text.replace(
            anchor,
            anchor
            + f"    container_name: {CONTAINER_PREFIX}-{svc}-1\n"
            + f"    mem_limit: {limit}\n",
        )
    path.write_text(text, encoding="utf-8")


def prepare_workdir() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    excludes = [".git", ".lab", "node_modules", "__pycache__", ".pytest_cache",
                ".mypy_cache", ".ruff_cache", "*.pyc", "neg1.pid"]
    cmd = ["rsync", "-a"]
    for item in excludes:
        cmd += ["--exclude", item]
    cmd += [str(REPO) + "/", str(WORK) + "/"]
    subprocess.run(cmd, check=True, timeout=900)
    patch_env(WORK / ".env")
    patch_compose(WORK / "compose.yaml")
    src_nm = REPO / "frontend" / "node_modules"
    dst_nm = WORK / "frontend" / "node_modules"
    if dst_nm.exists():
        shutil.rmtree(dst_nm)
    shutil.copytree(src_nm, dst_nm, symlinks=True)
    say(f"临时副本：{WORK}（.env 改隔离端口；compose 副本加 container_name / "
        f"mem_limit；node_modules 已复制）")
    return WORK


def compose(work: Path, args: str, timeout: float,
            allowed: tuple[int, ...] = (0,)) -> tuple[list[str], int]:
    cmd = f"docker compose -p {PROJECT} {args}"
    proc = subprocess.run(
        ["bash", "-c", cmd], cwd=work, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, env=base_env(),
    )
    lines = (proc.stdout or "").splitlines()
    if proc.returncode not in allowed:
        raise RuntimeError(
            f"compose 命令失败（exit={proc.returncode}）：{cmd}\n"
            + "\n".join(lines[-40:])
        )
    return lines, proc.returncode


def container_state(name: str) -> tuple[str, str]:
    """(Status, ExitCode)；daemon 忙时 inspect 会偶发超时，重试几次。"""
    for _ in range(3):
        try:
            out = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{.State.Status}} {{.State.ExitCode}}", name],
                capture_output=True, text=True, timeout=60,
            )
            if out.returncode == 0:
                parts = out.stdout.strip().split()
                if parts:
                    return parts[0], parts[1] if len(parts) > 1 else "?"
        except subprocess.TimeoutExpired:
            pass
        time.sleep(1)
    return "missing", "?"


def container_health(name: str) -> str:
    for _ in range(3):
        try:
            out = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{if .State.Health}}{{.State.Health.Status}}"
                 "{{else}}{{.State.Status}}{{end}}", name],
                capture_output=True, text=True, timeout=60,
            )
            return out.stdout.strip()
        except subprocess.TimeoutExpired:
            time.sleep(1)
    return "unknown"


def wait_healthy(names: tuple[str, ...], timeout: float = 300.0) -> None:
    t0 = time.monotonic()
    last = ""
    while time.monotonic() - t0 < timeout:
        states = {name: container_health(name) for name in names}
        last = " ".join(
            f"{name.replace(CONTAINER_PREFIX + '-', '').replace('-1', '')}={s}"
            for name, s in states.items()
        )
        if all(state == "healthy" for state in states.values()):
            say(f"      → 全部 healthy（{time.monotonic() - t0:.0f}s）")
            return
        time.sleep(2)
    raise RuntimeError(f"{timeout}s 内没有全部 healthy：{last}")


def es_disk_percent() -> int | None:
    try:
        url = f"http://127.0.0.1:{HOST_PORTS['ES_HOST_PORT']}/_cat/allocation?format=json"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(float(data[0]["disk.percent"]))
    except Exception:  # noqa: BLE001
        return None


def es_disable_watermark() -> None:
    url = f"http://127.0.0.1:{HOST_PORTS['ES_HOST_PORT']}/_cluster/settings"
    body = json.dumps({"persistent": {
        "cluster.routing.allocation.disk.threshold_enabled": False}}).encode()
    req = urllib.request.Request(url, data=body, method="PUT",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def cleanup_project(work: Path | None) -> list[str]:
    """把 project=shotsl4 的容器 / 卷 / 网络清干净（只碰这一个 project）。"""
    lines: list[str] = []
    if work is not None and work.exists():
        try:
            out, _ = compose(work, "down -v --remove-orphans", timeout=600)
            lines = out
        except Exception as exc:  # noqa: BLE001
            lines = [f"down -v 失败：{exc}"]
    ids = project_containers()
    if ids:
        subprocess.run(["docker", "rm", "-f", *ids], capture_output=True,
                       text=True, timeout=300)
        lines.append(f"补删 {len(ids)} 个 project={PROJECT} 容器")
    vols = subprocess.run(
        ["docker", "volume", "ls", "-q",
         "--filter", f"label=com.docker.compose.project={PROJECT}"],
        capture_output=True, text=True, timeout=120).stdout.split()
    if vols:
        subprocess.run(["docker", "volume", "rm", *vols], capture_output=True,
                       text=True, timeout=300)
        lines.append(f"补删 {len(vols)} 个 project={PROJECT} 卷")
    nets = subprocess.run(
        ["docker", "network", "ls", "-q",
         "--filter", f"label=com.docker.compose.project={PROJECT}"],
        capture_output=True, text=True, timeout=120).stdout.split()
    if nets:
        subprocess.run(["docker", "network", "rm", *nets], capture_output=True,
                       text=True, timeout=300)
        lines.append(f"补删 {len(nets)} 个 project={PROJECT} 网络")
    return lines


def start_isolated_stack(work: Path, extra: list[str]) -> list[str]:
    """:先三存储（可按需关 ES disk watermark），再 init / backend / frontend。"""
    say("起隔离栈（project=shotsl4；页面命令执行时才替换 -p 与端口）")
    say("   预构建镜像（--build 缓存；第一次可能几分钟）……")
    compose(work, "build", timeout=1800)
    say("   起三座存储（--no-build，复用刚构建的镜像）")
    compose(work, "up -d --no-build mysql elasticsearch qdrant", timeout=600)
    wait_healthy(tuple(f"{CONTAINER_PREFIX}-{s}-1"
                       for s in ("mysql", "elasticsearch", "qdrant")))
    pct = es_disk_percent()
    if pct is not None and pct >= 85:
        es_disable_watermark()
        extra.append(
            f"隔离 ES 磁盘 {pct}% 触发 disk watermark（ES 默认 low=85%）→ 在 "
            f"shotsl4 的 cluster settings 里临时关闭 disk threshold（只影响隔离卷，"
            f"down -v 后随卷消失）"
        )
        say(f"      磁盘 {pct}%：已临时关闭隔离 ES 的 disk watermark（只影响 shotsl4）")
    else:
        say(f"      ES 磁盘 {pct}%：未触发水位，不动 cluster settings")
    say("   起 init / backend / frontend")
    compose(work, "up -d --no-build", timeout=900)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 600:
        status, code = container_state(INIT_CONTAINER)
        if status == "exited":
            if code != "0":
                raise RuntimeError(f"init 退出码 {code}（不是 0）")
            log = subprocess.run(
                ["docker", "logs", INIT_CONTAINER],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
            text = (log.stdout or "") + (log.stderr or "")
            if "S2 VERIFY PASS" not in text:
                raise RuntimeError("init 退出 0 但日志里没有 S2 VERIFY PASS")
            say(f"      → init Exited (0)，S2 VERIFY PASS（{time.monotonic() - t0:.0f}s）")
            break
        time.sleep(1)
    else:
        raise RuntimeError("init 10 分钟内没有正常退出")
    wait_healthy(tuple(f"{CONTAINER_PREFIX}-{s}-1" for s in SERVICES))
    return []


def stop_isolated_stack(work: Path | None, records: dict) -> list[str]:
    lines = cleanup_project(work)
    records["cleanup"] = {"cmd": f"docker compose -p {PROJECT} down -v",
                          "lines": lines[-8:], "exit": 0}
    say(f"  ✅ down -v：{len(lines)} 行输出（容器 / 卷 / 网络一起删）")
    leftovers = project_containers()
    say(f"  {'✅' if not leftovers else '⚠️ '} project={PROJECT} 容器残留：{leftovers or '无'}")
    return lines


# ---------------------------------------------------------------- 页面解析 / 自检

def page_text(page: int) -> str:
    return PAGE_MD[page].read_text(encoding="utf-8")


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    return re.findall(
        r"^```([A-Za-z]*)[ \t]*\n(.*?)^```[ \t]*$", text, re.S | re.M
    )


def section_text(page: int, heading: str) -> str:
    text = page_text(page)
    m = re.search(rf"^{re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise RuntimeError(f"page-{page}.md 里找不到「{heading}」段")
    return m.group(1)


def blocks_of(page: int, heading: str) -> list[list[str]]:
    blocks = fenced_blocks(section_text(page, heading))
    return [[line.rstrip() for line in body.rstrip("\n").split("\n")]
            for _, body in blocks]


def find_block(blocks: list[list[str]], needle: str) -> list[str]:
    for block in blocks:
        if any(needle in line for line in block):
            return block
    raise RuntimeError(f"找不到含 {needle!r} 的代码块")


def truncate_block(block: list[str], marker: str) -> list[str]:
    """去掉页面样例块里「可选步骤」的部分（如 `# 第 5 步` 之后）。"""
    out: list[str] = []
    for line in block:
        if marker in line:
            break
        out.append(line)
    return out


def norm_line(line: str) -> str:
    return re.sub(r"[ \t\u00a0]+", " ", strip_ansi(line)).strip()


def block_segments(block: list[str]) -> list[list[str]]:
    segments: list[list[str]] = []
    current: list[str] = []
    for line in block:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text in ("...", "…", "……"):
            if current:
                segments.append(current)
                current = []
            continue
        current.append(line)
    if current:
        segments.append(current)
    return segments


def wildcard_regex(expected: str) -> re.Pattern:
    text = norm_line(expected)
    # 每次运行都会变、或页面自己说明「随机器变」的量，统一当通配符
    text = re.sub(r"in \d+\.\d+s", "in …", text)
    text = re.sub(r"sse_chunks=\d+", "sse_chunks=…", text)
    text = re.sub(r"sse_verdict=\w+", "sse_verdict=…", text)
    text = re.sub(r"Up .*?\(healthy\)", "Up … (healthy)", text)
    text = re.sub(r"Exited \(0\) .*", "Exited (0) …", text)
    # 1142 后面的客户端 IP 因机器而异（page-18 明说）
    text = re.sub(r"@'\d+\.\d+\.\d+\.\d+'", "@'…'", text)
    pattern = re.escape(text)
    pattern = pattern.replace(re.escape("…"), ".+?")
    return re.compile(pattern)


def check_expected(block: list[str], actual_lines: list[str]) -> tuple[bool, str]:
    """页面样例块 ↔ 真跑输出：每段里的行按顺序出现（可跳过真跑里的无关行）。"""
    actual = [norm_line(line) for line in actual_lines if norm_line(line)]
    pos = 0
    checked = 0
    for segment in block_segments(block):
        for line in segment:
            regex = wildcard_regex(line)
            found = False
            while pos < len(actual):
                if regex.search(actual[pos]):
                    found = True
                    pos += 1
                    break
                pos += 1
            if not found:
                return False, f"真跑输出里找不到：{line!r}"
            checked += 1
    return True, f"{checked} 行按顺序命中真跑输出（{len(actual)} 行）"


def check_presence(block: list[str], actual_lines: list[str]) -> tuple[bool, str]:
    """页面样例块 ↔ 真跑输出：每行都出现即可，**不要求顺序**。"""
    actual = [norm_line(line) for line in actual_lines if norm_line(line)]
    missing: list[str] = []
    checked = 0
    for segment in block_segments(block):
        for line in segment:
            regex = wildcard_regex(line)
            if not any(regex.search(item) for item in actual):
                missing.append(line)
            checked += 1
    if missing:
        return False, "真跑输出里找不到：" + " / ".join(repr(x) for x in missing[:3])
    return True, f"{checked} 行全部命中真跑输出（{len(actual)} 行；顺序不参与对账）"


def check_key_lines(keys: list[str], actual_lines: list[str]) -> tuple[bool, str]:
    actual = [norm_line(line) for line in actual_lines if norm_line(line)]
    missing = []
    for key in keys:
        regex = wildcard_regex(key)
        if not any(regex.search(line) for line in actual):
            missing.append(key)
    if missing:
        return False, "未命中：" + " / ".join(repr(x) for x in missing)
    return True, f"{len(keys)} 个关键字全部命中"


def check_ps_block(block: list[str], actual_lines: list[str]) -> tuple[bool, str]:
    """page-13 的 ps 样例块：只对「服务名 + (healthy)」，时长按通配。"""
    actual = [norm_line(line) for line in actual_lines if norm_line(line)]
    missing = []
    for line in block:
        text = norm_line(line)
        if not text or text.startswith("#"):
            continue
        name = text.split()[0]
        ok = any(name in item and "(healthy)" in item for item in actual)
        if not ok:
            missing.append(name)
    if missing:
        return False, f"ps 输出里没有 healthy 的服务：{missing}"
    return True, f"{len([l for l in block if norm_line(l) and not norm_line(l).startswith('#')])} 个服务行都 healthy"


def find_line(lines: list[str], needle: str) -> str:
    for line in lines:
        if needle in line:
            return line
    raise RuntimeError(f"输出里找不到 {needle!r}；末 10 行：\n" + "\n".join(lines[-10:]))


def find_line_regex(lines: list[str], regex: str) -> str:
    pattern = re.compile(regex)
    for line in lines:
        if pattern.search(line):
            return line
    raise RuntimeError(f"输出里找不到 /{regex}/；末 10 行：\n" + "\n".join(lines[-10:]))


def pick_forward(lines: list[str], needles: list[str]) -> list[str]:
    """按顺序从真跑输出里挑行（每行命中后从下一行继续找）。"""
    picked: list[str] = []
    pos = 0
    for needle in needles:
        found = None
        for idx in range(pos, len(lines)):
            if needle in lines[idx]:
                found = lines[idx]
                pos = idx + 1
                break
        if found is None:
            raise RuntimeError(f"输出里找不到 {needle!r}（从第 {pos} 行往后找）")
        picked.append(found)
    return picked


def pick_matching(lines: list[str], needles: list[str]) -> list[str]:
    """每条 needle 取真跑输出里的第一次出现，按**捕获顺序**输出（不假设跨行顺序）。

    第 22 页级考核里 `docker compose exec -T` 的容器进程 stdout 有缓冲、stderr 无缓冲：
    门禁的 FAIL 摘要（stderr）会先到，账号 / GRANT 明细（stdout）在进程退出时才刷出来。
    这是真实终端的顺序，不是判据错（页面正文对 tee/重定向解释过同一件事）。
    """
    picked: list[tuple[int, str]] = []
    for needle in needles:
        for idx, line in enumerate(lines):
            if needle in line:
                picked.append((idx, line))
                break
        else:
            raise RuntimeError(f"输出里找不到 {needle!r}")
    picked.sort(key=lambda pair: pair[0])
    return [line for _, line in picked]


def find_index(lines: list[str], needle: str) -> int:
    for idx, line in enumerate(lines):
        if needle in line:
            return idx
    raise RuntimeError(f"输出里找不到 {needle!r}")


# ---------------------------------------------------------------- 截图 / 渲染


def chrome_screenshot(html_path: Path, png_path: Path, profile_dir: Path) -> None:
    png_path.unlink(missing_ok=True)
    cmd = [
        "google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
        "--hide-scrollbars", f"--force-device-scale-factor={DEVICE_SCALE}",
        f"--window-size={WINDOW_W_CSS},{WINDOW_H_CSS}",
        f"--user-data-dir={profile_dir}", f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError("chrome 截图失败：\n"
                           + (proc.stderr or proc.stdout or "")[-4000:])


def identify_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["identify", "-format", "%w %h", str(path)],
        check=True, capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    w, h = (int(x) for x in out.split())
    return w, h


def build_html(panes: list[dict]) -> str:
    chunks = []
    for pane in panes:
        rows: list[str] = []
        for item in pane["items"]:
            kind = item["kind"]
            if kind == "cmd":
                rows.extend(tr.html_cmd_lines(item["text"]))
            elif kind == "out":
                rows.extend(tr.html_out_line(display_line(line))
                            for line in item["lines"])
            elif kind == "note":
                rows.append(f'<span class="dim">{tr.esc(item["text"])}</span>')
            else:
                raise ValueError(kind)
        classes = "pane compact" if pane.get("compact") else "pane"
        chunks.append(
            f'<div class="{classes}"><div class="titlebar">{tr.esc(pane["title"])}</div>'
            f'<pre>{"\n".join(rows)}</pre></div>'
        )
    body = "\n".join(chunks)
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f"<style>{CSS}</style></head><body>"
        f'<div class="wrap">{body}</div></body></html>\n'
    )


def render_shot(shot: dict, tmpdir: Path) -> Path:
    html_text = build_html(shot["panes"])
    stem = Path(shot["file"]).stem
    html_path = tmpdir / f"{stem}.html"
    html_path.write_text(html_text, encoding="utf-8")

    raw = tmpdir / f"{stem}.raw.png"
    chrome_screenshot(html_path, raw, tmpdir / f"chrome-{stem}")
    raw_w, _ = identify_size(raw)
    if raw_w != WINDOW_W_CSS * DEVICE_SCALE:
        raise RuntimeError(f"截图宽 {raw_w}px，不是 {WINDOW_W_CSS * DEVICE_SCALE}px")

    trimmed = tmpdir / f"{stem}.trim.png"
    subprocess.run(["convert", str(raw), "-trim", "+repage", str(trimmed)],
                   check=True, capture_output=True, timeout=120)
    _, h = identify_size(trimmed)
    target_h = max(h, MIN_PNG_H)
    target = IMAGES / shot["file"]
    subprocess.run(
        ["convert", str(trimmed), "-gravity", "center",
         "-background", PAGE_BG, "-extent",
         f"{WINDOW_W_CSS * DEVICE_SCALE}x{target_h}", str(target)],
        check=True, capture_output=True, timeout=120,
    )
    final_w, final_h = identify_size(target)
    if final_w != WINDOW_W_CSS * DEVICE_SCALE or final_h < MIN_PNG_H:
        raise RuntimeError(f"{target.name} 尺寸 {final_w}x{final_h} 不符合 @2x 约定")
    say(f"    🖼  {target.relative_to(REPO)}  {final_w}x{final_h}")
    return target


# ---------------------------------------------------------------- 页面命令原文

CMD13_PS = "docker compose ps"
CMD13_PSA = "docker compose ps -a"
CMD13_CURL = (
    "curl -s -N -X POST http://127.0.0.1:8080/api/query "
    "-H 'Content-Type: application/json' -d '{\"query\":\"华北销售额\"}'"
)
CMD13_SMOKE = "make docker-smoke"

CMD18_PROVISION = "(cd backend && .venv/bin/python -m app.scripts.security --provision-ro-account)"
CMD18_VERIFY = "(cd backend && .venv/bin/python -m app.scripts.security --verify-ro-account)"
CMD18_GRANT = (
    'docker compose exec -T mysql mysql -uroot -p"$REBUILD_MYSQL_ROOT_PASSWORD" '
    "-e \"GRANT ALL ON dw.* TO 'dw_reader'@'%'\""
)

CMD19_CHECK = "(cd backend && .venv/bin/python -m app.scripts.security --check)"
CMD19_CORPUS = (
    '(cd backend && PYTHONUNBUFFERED=1 .venv/bin/python -m app.scripts.security --corpus) '
    '2>&1 | grep -E "multi_statement|executable_comment|union|语料："'
)

CMD20_SAVE = "scripts/lab save p20-before"
CMD20_CANCEL = "(cd backend && .venv/bin/python -m pytest tests/agent -q -k cancel)"
CMD20_AGENT = "(cd backend && .venv/bin/python -m pytest tests/agent -q)"
CMD20_FRAMES = (
    '(cd backend && .venv/bin/python -c "import json;[print(f) for f in '
    "json.load(open('../fixtures/sse/cancelled.json'))['frames']]\")"
)
CMD20_RECORD = "(cd backend && .venv/bin/python -m app.scripts.record_sse --check)"

CMD21_SAVE = "scripts/lab save p21-before"
CMD21_COUNTS = """(cd backend && .venv/bin/python -c "
import json
from fastapi.testclient import TestClient
from app.scenarios.app import create_scenario_app
c = TestClient(create_scenario_app())
s = c.get('/api/steps').json()['steps']; e = c.get('/api/errors').json()
print('/api/steps =', len(s), '条件步骤 =', [x['id'] for x in s if x['conditional']])
print('/api/errors =', len(e['codes']), '类别 =', e['classes'])
for sid in ('happy', 'llm_refusal'):
    steps = [json.loads(f[6:])['step'] for f in json.load(open(f'../fixtures/sse/{sid}.json'))['frames'] if json.loads(f[6:])['type'] == 'progress']
    print(f'{sid}: {len(steps)} 条 progress 帧 / {len(set(steps))} 个步骤名；只出现一次 ' + '/'.join(x for x in dict.fromkeys(steps) if steps.count(x) == 1))
")"""
CMD21_FIXTURES = "(cd backend && .venv/bin/python -m pytest tests/frontend/test_sse_fixtures.py -q)"
CMD21_NPM = "(cd frontend && npm test)"

CMD22_SAVE = "scripts/lab save p22-before"
CMD22_PYTEST = "(cd backend && .venv/bin/python -m pytest -q)"
CMD22_SMOKE = "make docker-smoke"
CMD22_TERMINAL_B = """source scripts/export-docker-env.sh
seen=0; end=$((SECONDS+60)); while [ "$SECONDS" -lt "$end" ]; do
  id="$(docker compose ps -aq init 2>/dev/null)"; [ -z "$id" ] && { sleep 0.1; continue; }
  s="$(docker inspect -f '{{.State.Status}}' "$id" 2>/dev/null)"; [ "$s" = running ] && seen=1
  [ "$seen" = 1 ] && [ "$s" = exited ] && { echo "watcher: 捕捉到 init 退出，立刻注入 GRANT ALL"; break; }
  sleep 0.1; done
[ "$seen" = 1 ] || { echo "没等到 init 跑起来（60 秒）：先确认栈已起、A 的 smoke 已开跑（docker compose ps -a），再重跑本步" >&2; exit 1; }
docker compose exec -T mysql mysql -uroot -p"$REBUILD_MYSQL_ROOT_PASSWORD" -e "GRANT ALL ON dw.* TO 'dw_reader'@'%'\""""


# ---------------------------------------------------------------- 捕获流程（离线）

def capture_offline(work: Path) -> dict:
    records: dict = {}
    section("第 19 页 · 守策略（page-19.md，离线）")
    capture(records, "19_check", CMD19_CHECK, work, timeout=180)
    capture(records, "19_corpus", CMD19_CORPUS, work, timeout=180)

    section("第 20 页 · 守取消（page-20.md，离线）")
    capture(records, "20_save", CMD20_SAVE, work, timeout=180)
    capture(records, "20_cancel", CMD20_CANCEL, work, timeout=180)
    capture(records, "20_agent", CMD20_AGENT, work, timeout=300)
    capture(records, "20_frames", CMD20_FRAMES, work, timeout=120)
    capture(records, "20_record", CMD20_RECORD, work, timeout=300)

    section("第 21 页 · 守可观测（page-21.md，离线）")
    capture(records, "21_save", CMD21_SAVE, work, timeout=180)
    capture(records, "21_counts", CMD21_COUNTS, work, timeout=180)
    capture(records, "21_fixtures", CMD21_FIXTURES, work, timeout=300)
    capture(records, "21_npm", CMD21_NPM, work, timeout=300)

    section("第 22 页 · 守回归（page-22.md，离线两段）")
    capture(records, "22_save", CMD22_SAVE, work, timeout=180)
    capture(records, "22_pytest", CMD22_PYTEST, work, timeout=600)

    # 关键数字先在捕获阶段核对一遍（页面样例块的逐行对账在 run_checks 里做）
    checks = [
        ("19_check", ["36/36 条按预期拒绝", "11/11 条放行",
                      "8/8 条 SQL 通过策略", "S5 PASS"]),
        ("19_corpus", ["语料：47 条，失败 0 条"]),
        ("20_cancel", ["6 passed"]),
        ("20_agent", ["114 passed"]),
        ("20_record", ["S7 SSE RECORD PASS（14 个夹具与真实输出一致）"]),
        ("21_counts", ["/api/steps = 12", "/api/errors = 16"]),
        ("21_fixtures", ["30 passed"]),
        ("21_npm", ["40 passed"]),
        ("22_pytest", ["813 passed, 30 skipped"]),
    ]
    for key, needles in checks:
        ok, detail = check_key_lines(
            needles, [display_line(line) for line in records[key]["lines"]])
        if not ok:
            raise RuntimeError(f"{key} 关键行没命中：{detail}")
        say(f"      ✅ {key}：{detail}")
    return records


# ---------------------------------------------------------------- 捕获流程（栈）

def capture_stack(work: Path, records: dict, extra: list[str]) -> None:
    section("第 13 页 · 换真部署（page-13.md，栈）")
    capture(records, "13_ps", CMD13_PS, work, timeout=120)
    capture(records, "13_psa", CMD13_PSA, work, timeout=120)
    # ps 输出必须能证明「5 长驻 healthy + init Exited(0)」
    services = ("backend", "elasticsearch", "frontend", "mysql", "qdrant")
    for svc in services:
        name = f"{CONTAINER_PREFIX}-{svc}-1"
        row = find_line(records["13_ps"]["lines"], name)
        if "(healthy)" not in row:
            raise RuntimeError(f"docker compose ps 里 {svc} 不是 healthy：{row}")
    init_rows = [line for line in records["13_psa"]["lines"]
                 if INIT_CONTAINER in line and "Exited (0)" in line]
    if not init_rows:
        raise RuntimeError("docker compose ps -a 里找不到 init Exited (0)")
    say(f"      ✅ ps：5 个长驻服务 healthy；ps -a：init Exited (0)")

    say("   跑 make docker-smoke（第 1 次：8 步逐条验）……")
    capture(records, "13_smoke", CMD13_SMOKE, work, timeout=1200, smoke=True)
    for needle in ("DOCKER SMOKE PASS", "DOCKER INIT PASS", "S2 VERIFY PASS"):
        find_line(records["13_smoke"]["lines"], needle)
    say("      ✅ 第 1 次 smoke：DOCKER SMOKE PASS")

    section("第 22 页 · 守回归（page-22.md，栈）")
    say("   跑 make docker-smoke（第 2 次：给第 3 张图取「回归网全绿」）……")
    capture(records, "22_smoke", CMD22_SMOKE, work, timeout=1200, smoke=True)
    find_line(records["22_smoke"]["lines"], "DOCKER SMOKE PASS")
    say("      ✅ 第 2 次 smoke：DOCKER SMOKE PASS")

    section("第 18 页 · 守账号（page-18.md，只需 MySQL）")
    capture(records, "18_prov", CMD18_PROVISION, work, timeout=300, with_env=True)
    find_line(records["18_prov"]["lines"], "只读账号就绪")
    capture(records, "18_verify_green", CMD18_VERIFY, work, timeout=300,
            with_env=True)
    ok = [line for line in records["18_verify_green"]["lines"]
          if "写操作被拒绝" in line and "1142" in line]
    if not ok:
        raise RuntimeError("只读账号验证没有出现 1142 拒绝")
    find_line(records["18_verify_green"]["lines"], "PASS: 该账号在 dw 上只有 SELECT")
    say("      ✅ 开通 → 验证 PASS（写操作被拒 1142）")
    capture(records, "18_grant", CMD18_GRANT, work, timeout=300, with_env=True)
    capture(records, "18_verify_red", CMD18_VERIFY, work, timeout=300,
            with_env=True, allowed=(1,))
    for needle in ("写操作被放行", "FAIL: 3 项问题", "GRANT ALL PRIVILEGES"):
        find_line(records["18_verify_red"]["lines"], needle)
    say("      ✅ GRANT ALL 后变红：FAIL: 3 项问题（两段对照齐了）")
    capture_quiet(records, "18_restore", CMD18_PROVISION, work, timeout=300,
                  with_env=True)
    capture_quiet(records, "18_restore_verify", CMD18_VERIFY, work, timeout=300,
                  with_env=True)
    say("      ✅ 已用 --provision-ro-account 还原账号（权限集合回到 SELECT）")

    section("第 22 页级考核 · init 退出窗口内注入 GRANT ALL")
    ablate_ok = capture_ablation_with_retry(work, records, extra)
    if not ablate_ok:
        raise RuntimeError("级考核没拿到「第 7 步红」的证据（页面图的最后一帧做不出来）")
    # 还原账号并确认回绿（页面第 5 步）
    capture_quiet(records, "22_restore", CMD18_PROVISION, work, timeout=300,
                  with_env=True)
    green = capture_quiet(records, "22_restore_verify", CMD18_VERIFY, work,
                          timeout=300, with_env=True)
    find_line(green, "PASS: 该账号在 dw 上只有 SELECT")
    say("      ✅ 已还原账号，单步判据回到 PASS")


def _watcher_script() -> str:
    """终端 B：与 page-22「拆一刀」同一份 8 行命令（图里照抄页面原文）。

    执行侧不改写命令本身：调用处用 COMPOSE_PROJECT_NAME 把 `docker compose`
    指到隔离 project（本脚本全程只碰 project=shotsl4；因为命令与页面逐字
    一致，图里显示的终端 B 不需要任何执行侧替换）。
    """
    return CMD22_TERMINAL_B


def capture_ablation_with_retry(work: Path, records: dict, extra: list[str],
                                attempts: int = 2) -> bool:
    for attempt in range(1, attempts + 1):
        say(f"   第 {attempt} 次尝试（终端 B 自动等 init 窗口 → 终端 A 跑 smoke）")
        t0 = time.monotonic()
        watcher = subprocess.Popen(
            ["bash", "-c", _watcher_script()], cwd=work,
            env={**base_env(), "COMPOSE_PROJECT_NAME": PROJECT},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
        )
        time.sleep(0.3)
        try:
            lines = capture(records, "22_ablation", CMD22_SMOKE, work,
                            timeout=1200, allowed=(0, 2), smoke=True)
        finally:
            try:
                watcher.wait(timeout=20)
            except subprocess.TimeoutExpired:
                watcher.kill()
        watcher_lines = (watcher.stdout.read() or "").splitlines() if watcher.stdout else []
        watcher_lines = [line for line in watcher_lines if line.strip()]
        records["22_ablation_watcher"] = {"cmd": CMD22_TERMINAL_B,
                                          "lines": watcher_lines, "exit": 0}
        Path("/tmp/shots-l4-watch.log").write_text(
            "\n".join(watcher_lines) + "\n", encoding="utf-8")
        code = records["22_ablation"]["exit"]
        say(f"      watcher：{watcher_lines}")
        red = all(any(needle in line for line in lines) for needle in
                  ("写操作被放行", "FAIL: 3 项问题",
                   "DOCKER SMOKE FAIL: 只读账号验证未通过"))
        green_pass = any("DOCKER SMOKE PASS" in line for line in lines)
        steps_1_6 = all(any(needle in line for line in lines) for needle in
                        ("steps=12", "sse_verdict=", "result rows="))
        if red and not green_pass and steps_1_6:
            extra.append(
                f"第 22 页级考核：终端 B 在 init 退出窗口内注入 GRANT ALL（watch 输出："
                f"{' / '.join(watcher_lines)}），同一条 make docker-smoke 第 7 步变红"
                f"（FAIL: 3 项问题），1–6 步绿；attempt={attempt}，"
                f"smoke 用时 {time.monotonic() - t0:.1f}s"
            )
            say(f"      ✅ 窗口命中：第 7 步红，1–6 步绿（exit={code}）")
            return True
        say(f"      ⚠️  没命中窗口（red={red} green_pass={green_pass} "
            f"steps_1_6={steps_1_6}），还原账号后重试")
        capture_quiet(records, f"22_abl_restore_{attempt}", CMD18_PROVISION,
                      work, timeout=300, with_env=True)
        time.sleep(2)
    return False


# ---------------------------------------------------------------- 渲染数据（节选真实输出）


def note(text: str) -> dict:
    return {"kind": "note", "text": text}


def out(lines: list[str]) -> dict:
    return {"kind": "out", "lines": lines}


def cmd(text: str) -> dict:
    return {"kind": "cmd", "text": text}


def shot_13_ps(records: dict) -> dict:
    return {
        "file": "page-13-ps.png",
        "panes": [
            {
                "title": "终端 · 第 5 步：docker compose ps——五个长驻服务全 healthy"
                         "（11.5px：整张 7 列表格；时长随机器变）",
                "compact": True,
                "items": [cmd(CMD13_PS), out(records["13_ps"]["lines"])],
            },
            {
                "title": "第 5 步：docker compose ps -a——第六行只跑一次的 init："
                         "Exited (0)（默认 ps 看不到它）",
                "compact": True,
                "items": [cmd(CMD13_PSA), out(records["13_psa"]["lines"])],
            },
        ],
    }


def shot_13_smoke(records: dict) -> dict:
    lines = records["13_smoke"]["lines"]
    start1 = find_index(lines, "== 1/8")
    start2 = find_index(lines, "== 2/8")
    start8 = find_index(lines, "== 8/8")
    tail = lines[start8:]
    s2 = find_line(tail, "S2 VERIFY PASS")
    idem = find_line(tail, "== init 幂等（必须跳过重建） ==")
    return {
        "file": "page-13-smoke.png",
        "panes": [{
            "title": "终端 · 第 6 步：make docker-smoke——8 步逐条验，末行 "
                     "DOCKER SMOKE PASS（第 1 步构建日志与 8/8 明细从略）",
            "items": [
                cmd(CMD13_SMOKE),
                out([lines[start1]]),
                note("…（docker compose up 的构建/启动日志省略）"),
                out(lines[start2:start8 + 1]),
                note("…（8/8 的 S2 对账明细与 init 幂等的完整日志省略）"),
                out([s2, idem, "DOCKER INIT PASS", "DOCKER SMOKE PASS"]),
            ],
        }],
    }


def shot_18_account(records: dict) -> dict:
    green = records["18_verify_green"]["lines"]
    red = records["18_verify_red"]["lines"]
    return {
        "file": "page-18-account.png",
        "panes": [
            {
                "title": "终端 · 第 3、4 步：开通只读账号 → 门禁 PASS"
                         "（读 SHOW GRANTS + 真写一次被拒 1142）",
                "items": [
                    cmd(CMD18_PROVISION),
                    out(records["18_prov"]["lines"]),
                    cmd(CMD18_VERIFY),
                    out(green),
                ],
            },
            {
                "title": "拆一刀 · 同一终端：GRANT ALL ON dw.* 之后，同一条门禁变红"
                         "——静态、动态两条判据都抓到",
                "items": [
                    cmd(CMD18_GRANT),
                    out(records["18_grant"]["lines"]),
                    cmd(CMD18_VERIFY),
                    out(red),
                ],
            },
        ],
    }


def shot_19_policy(records: dict) -> dict:
    return {
        "file": "page-19-policy.png",
        "panes": [
            {
                "title": "终端 · 第 2 步：security --check——36/36 全拒 + 11/11 放行 "
                         "+ 8/8 基线，末行 S5 PASS（纯离线）",
                "items": [cmd(CMD19_CHECK), out(records["19_check"]["lines"])],
            },
            {
                "title": "第 3 步：语料判定表（节选三类构造）——末行统计走 stderr，"
                         "PYTHONUNBUFFERED=1 保证它落在表尾",
                "items": [cmd(CMD19_CORPUS), out(records["19_corpus"]["lines"])],
            },
        ],
    }


def shot_20_cancel(records: dict) -> dict:
    save_first = records["20_save"]["lines"][:1]
    cancel_last = records["20_cancel"]["lines"][-1:]
    agent_last = records["20_agent"]["lines"][-1:]
    frames = records["20_frames"]["lines"][:2]
    return {
        "file": "page-20-cancel.png",
        "panes": [
            {
                "title": "终端 · 第 1、2 步：先拍快照 → 只跑名字带 cancel 的 6 条；"
                         "再整跑 tests/agent 确认没碰坏别的",
                "items": [
                    cmd(CMD20_SAVE), out(save_first),
                    cmd(CMD20_CANCEL), out(cancel_last),
                    cmd(CMD20_AGENT), out(agent_last),
                ],
            },
            {
                "title": "第 3 步：取消夹具回放——恰好两帧（skipped → CANCELLED）；"
                         "record_sse --check 逐字节对账 14 条夹具",
                "items": [
                    cmd(CMD20_FRAMES), out(frames),
                    cmd(CMD20_RECORD),
                    out([find_line(records["20_record"]["lines"],
                                   "S7 SSE RECORD PASS")]),
                ],
            },
        ],
    }


def shot_21_observe(records: dict) -> dict:
    save_first = records["21_save"]["lines"][:1]
    counts = records["21_counts"]["lines"]
    npm_all = [line for line in records["21_npm"]["lines"]
               if norm_line(line).startswith(("Test Files", "Tests"))]
    npm_lines = npm_all[-2:]
    return {
        "file": "page-21-observe.png",
        "panes": [
            {
                "title": "终端 · 第 1 步：拍快照，数观测面的两半——目录端点给名字与码，"
                         "夹具流给实例（不启服务、不联网）",
                "items": [
                    cmd(CMD21_SAVE), out(save_first),
                    cmd(CMD21_COUNTS), out(counts),
                ],
            },
            {
                "title": "第 2、3 步：14 条夹具逐字节对账 PASS；夹具每帧合契约 "
                         "30 passed；前端协议 40 passed",
                "items": [
                    cmd(CMD20_RECORD),
                    out([find_line(records["20_record"]["lines"],
                                   "S7 SSE RECORD PASS")]),
                    cmd(CMD21_FIXTURES),
                    out([find_line(records["21_fixtures"]["lines"], "30 passed")]),
                    cmd(CMD21_NPM),
                    out(npm_lines),
                ],
            },
        ],
    }


def shot_22_smoke(records: dict) -> dict:
    pytest_last = [find_line_regex(records["22_pytest"]["lines"],
                                   r"\d+ passed, \d+ skipped in ")]
    npm_all = [line for line in records["21_npm"]["lines"]
               if norm_line(line).startswith(("Test Files", "Tests"))]
    npm_lines = npm_all[-2:]
    smoke = records["22_smoke"]["lines"]
    picked = pick_forward(smoke, [
        "health: {", "services: ", "steps=", "sse_verdict=", "result rows=",
        "nginx: ", "PASS: 该账号在 dw 上只有 SELECT", "S2 VERIFY PASS",
        "meta: verify passed; skip rebuild", "DOCKER INIT PASS",
        "DOCKER SMOKE PASS",
    ])
    return {
        "file": "page-22-smoke.png",
        "panes": [
            {
                "title": "终端 · 第 2 步：全量后端测试 843 条——813 passed, 30 skipped"
                         "（判据是「没有失败」，不是记死这个数）",
                "items": [
                    cmd(CMD22_PYTEST),
                    note("…（pytest 进度点省略）"),
                    out(pytest_last),
                ],
            },
            {
                "title": "第 3 步：前端 40 条离线协议与渲染测试",
                "items": [cmd(CMD21_NPM), out(npm_lines)],
            },
            {
                "title": "第 4 步：make docker-smoke——8 步跨层验收全绿，"
                         "末行 DOCKER SMOKE PASS（节选关键行）",
                "items": [
                    cmd(CMD22_SMOKE),
                    note("…（第 1 步 up 的启动日志与 2/8、4/8 的标题行省略）"),
                    out(picked),
                ],
            },
        ],
    }


def shot_22_ablation(records: dict) -> dict:
    lines = records["22_ablation"]["lines"]
    picked = pick_matching(lines, [
        "== 2/8", "health: {",
        "== 3/8", "services: ",
        "== 4/8", "steps=",
        "== 5/8", "sse_verdict=", "result rows=", "nginx: ",
        "== 6/8",
        "== 7/8", "FAIL: 3 项问题",
        "  - 账号持有不该有的权限", "  - 账号没有 SELECT 权限",
        "  - 写操作被放行（权限配置有误）",
        "账号：", "  GRANT GRANT USAGE", "  GRANT GRANT ALL PRIVILEGES",
        "写操作尝试：写操作被放行",
        "DOCKER SMOKE FAIL: 只读账号验证未通过",
    ])
    watcher = records.get("22_ablation_watcher", {"lines": []})["lines"]
    watcher_evidence = [line for line in watcher
                        if line.startswith("watcher:") or "mysql: [Warning]" in line]
    return {
        "file": "page-22-ablation.png",
        "panes": [
            {
                "title": "终端 B（先粘、回车）：自动等这次 init 真跑过"
                         "（running → exited）就立刻越权——窗口实测只有几秒",
                "items": [
                    cmd(CMD22_TERMINAL_B),
                    out(watcher_evidence),
                    note("…（自动循环不等手速；GRANT ALL 落在 init 退出之后、"
                         "smoke 第 7 步之前）"),
                ],
            },
            {
                "title": "终端 A（后跑）：make docker-smoke——1–6 步全绿，第 7 步红、"
                         "fail-fast 停住，第 8 步不跑",
                "items": [
                    cmd(CMD22_SMOKE),
                    note("…（第 1 步 up 的启动日志省略；2–6 步标题与检查行如下）"),
                    out(picked),
                    note("…（7/8 的明细来自容器进程：FAIL 摘要走 stderr 先到，"
                         "账号/GRANT 行走 stdout 随后——缓冲顺序，不是判据错）"),
                ],
            },
        ],
    }


def build_shots(records: dict) -> list[dict]:
    return [
        shot_13_ps(records),
        shot_13_smoke(records),
        shot_18_account(records),
        shot_19_policy(records),
        shot_20_cancel(records),
        shot_21_observe(records),
        shot_22_smoke(records),
        shot_22_ablation(records),
    ]


def collect_display_text(shots: list[dict]) -> dict[str, list[str]]:
    out_map: dict[str, list[str]] = {}
    for shot in shots:
        lines: list[str] = []
        for pane in shot["panes"]:
            lines.append(pane["title"])
            for item in pane["items"]:
                if item["kind"] == "cmd":
                    lines.extend(item["text"].split("\n"))
                elif item["kind"] == "out":
                    lines.extend(display_line(line) for line in item["lines"])
                elif item["kind"] == "note":
                    lines.append(item["text"])
        out_map[shot["file"]] = lines
    return out_map


# ---------------------------------------------------------------- OCR / 自检


def ocr_text(png: Path, tmpdir: Path) -> str:
    """把深色终端图反色后 OCR；没装 tesseract / Pillow 就返回空串。"""
    if shutil.which("tesseract") is None:
        return ""
    try:
        from PIL import Image, ImageOps
    except Exception:  # noqa: BLE001
        return ""
    tmp = tmpdir / f"{png.stem}.ocr.png"
    with Image.open(png) as im:
        gray = ImageOps.invert(im.convert("L"))
        ImageOps.expand(gray, border=24, fill=255).save(tmp)
    try:
        chunks = []
        for psm in ("6", "11"):
            proc = subprocess.run(
                ["tesseract", str(tmp), "stdout", "--psm", psm],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300,
            )
            chunks.append(proc.stdout or "")
        return "\n".join(chunks)
    finally:
        tmp.unlink(missing_ok=True)


def squash(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z.]", "", text)


def run_checks(records: dict, shots: list[dict], tmpdir: Path,
               extra: list[str]) -> bool:
    section("图文一致性自检（页面「你应该看到」↔ 真跑输出）")
    all_ok = True

    def lines_of(*keys: str) -> list[str]:
        merged: list[str] = []
        for key in keys:
            merged.extend(display_line(line) for line in records[key]["lines"])
        return merged

    page_blocks = {
        "13_ps": (13, "你应该看到", "shopkeeper-rebuild-backend-1"),
        "13_smoke": (13, "你应该看到", "DOCKER SMOKE PASS"),
        "18_green": (18, "你应该看到", "# 第 3 步"),
        "18_abl": (18, "拆一刀", "FAIL: 3 项问题"),
        "19_all": (19, "你应该看到", "# 第 2 步"),
        "20_all": (20, "你应该看到", "# 第 1 步"),
        "21_all": (21, "你应该看到", "# 第 1 步"),
        "22_all": (22, "你应该看到", "# 第 1 步"),
        "22_abl": (22, "拆一刀（L4 级考核）", "FAIL: 3 项问题"),
    }
    blocks: dict[str, list[str]] = {}
    for key, (page, heading, needle) in page_blocks.items():
        blocks[key] = find_block(blocks_of(page, f"## {heading}"), needle)
    # 页面样例块里的「可选步骤」不跑，对账时去掉
    blocks["18_green"] = truncate_block(blocks["18_green"], "# 第 5 步")
    blocks["19_all"] = truncate_block(blocks["19_all"], "# 第 4 步")
    blocks["20_all"] = truncate_block(blocks["20_all"], "# 第 4 步")
    # 13_ps 的 ps -a 那行在正文里（不在样例块里），单独用关键行核对

    ok, detail = check_ps_block(blocks["13_ps"],
                                lines_of("13_ps", "13_psa"))
    all_ok = all_ok and ok
    say(f"  {'✅' if ok else '⚠️ '} page-13-ps.png ← page-13.md（ps 块）：{detail}")

    block_checks = [
        ("page-13-smoke.png", "13_smoke", lines_of("13_smoke")),
        ("page-18-account.png", "18_green", lines_of("18_prov", "18_verify_green")),
        ("page-18-account.png", "18_abl",
         lines_of("18_grant", "18_verify_red")),
        ("page-19-policy.png", "19_all", lines_of("19_check", "19_corpus")),
        ("page-20-cancel.png", "20_all",
         lines_of("20_save", "20_cancel", "20_agent", "20_frames", "20_record")),
        ("page-21-observe.png", "21_all",
         lines_of("21_save", "21_counts", "20_record", "21_fixtures", "21_npm")),
        ("page-22-smoke.png", "22_all",
         lines_of("22_save", "22_pytest", "21_npm", "22_smoke")),
        ("page-22-ablation.png", "22_abl", lines_of("22_ablation")),
    ]
    presence_only = {"22_abl"}
    for shot_name, key, actual in block_checks:
        if key in presence_only:
            # 拆一刀样例块把「账号/GRANT 明细」写在 FAIL 摘要前面，而真跑捕获里
            # FAIL（stderr）先到；这里只验每行都在真跑输出里，顺序交给图去看。
            ok, detail = check_presence(blocks[key], actual)
        else:
            ok, detail = check_expected(blocks[key], actual)
        all_ok = all_ok and ok
        page = page_blocks[key][0]
        say(f"  {'✅' if ok else '⚠️ '} {shot_name} ← page-{page}.md（{key}）：{detail}")

    # 任务点名的关键行：逐条命中（防止样例块里被 `…` 放宽掉）
    section("关键行逐条核对（任务点名的判据）")
    key_checks = [
        ("page-13-ps.png", "13_psa",
         [f"{INIT_CONTAINER}", "Exited (0)"]),
        ("page-13-smoke.png", "13_smoke",
         ["DOCKER SMOKE PASS", "DOCKER INIT PASS", "S2 VERIFY PASS"]),
        ("page-18-account.png", "18_verify_green",
         ["PASS: 该账号在 dw 上只有 SELECT", "1142"]),
        ("page-18-account.png", "18_verify_red",
         ["FAIL: 3 项问题", "写操作被放行", "GRANT ALL PRIVILEGES"]),
        ("page-19-policy.png", "19_check",
         ["36/36", "11/11", "8/8", "S5 PASS"]),
        ("page-20-cancel.png", "20_cancel", ["6 passed"]),
        ("page-20-cancel.png", "20_record",
         ["S7 SSE RECORD PASS（14 个夹具与真实输出一致）"]),
        ("page-21-observe.png", "21_counts",
         ["/api/steps = 12", "/api/errors = 16"]),
        ("page-21-observe.png", "21_fixtures", ["30 passed"]),
        ("page-21-observe.png", "21_npm", ["40 passed"]),
        ("page-22-smoke.png", "22_pytest", ["813 passed, 30 skipped"]),
        ("page-22-smoke.png", "21_npm", ["40 passed"]),
        ("page-22-smoke.png", "22_smoke", ["DOCKER SMOKE PASS"]),
        ("page-22-ablation.png", "22_ablation",
         ["FAIL: 3 项问题", "写操作被放行（权限配置有误）",
          "DOCKER SMOKE FAIL: 只读账号验证未通过", "steps=12",
          "sse_verdict="]),
    ]
    for shot_name, key, needles in key_checks:
        ok, detail = check_key_lines(
            needles, [display_line(line) for line in records[key]["lines"]])
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} {shot_name} ← {key}：{detail}")

    # 级考核必须真的红：不能出现 DOCKER SMOKE PASS
    ablate = records["22_ablation"]["lines"]
    no_pass = not any("DOCKER SMOKE PASS" in line for line in ablate)
    all_ok = all_ok and no_pass
    say(f"  {'✅' if no_pass else '⚠️ '} page-22-ablation.png "
        f"← 22_ablation：同一条 smoke 里没有 DOCKER SMOKE PASS（窗口命中，"
        f"第 7 步红、第 8 步不跑）")

    # 页面命令逐字核对：图里显示的命令必须真的出现在页面正文里
    section("页面命令逐字核对（图里显示的命令 = 页面原文）")
    command_pairs = [
        (13, CMD13_PS), (13, CMD13_PSA), (13, CMD13_SMOKE),
        (18, CMD18_PROVISION), (18, CMD18_VERIFY), (18, CMD18_GRANT),
        (19, CMD19_CHECK), (19, CMD19_CORPUS),
        (20, CMD20_SAVE), (20, CMD20_CANCEL), (20, CMD20_AGENT),
        (20, CMD20_FRAMES), (20, CMD20_RECORD),
        (21, CMD21_SAVE), (21, CMD21_COUNTS), (21, CMD21_FIXTURES),
        (21, CMD21_NPM),
        (22, CMD22_SAVE), (22, CMD22_PYTEST), (22, CMD22_SMOKE),
        (22, CMD22_TERMINAL_B),
    ]
    for page, display in command_pairs:
        text = page_text(page)
        ok = all(line.strip() in text for line in display.split("\n") if line.strip())
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} page-{page}.md 含：{display.splitlines()[0][:60]}…")

    # 图片嵌入行：脚本不写页面，只核对页面里已经有了
    section("页面图片嵌入行核对（脚本不写页面）")
    for page, lines in EMBED_LINES.items():
        text = page_text(page)
        for line in lines:
            ok = line in text
            all_ok = all_ok and ok
            say(f"  {'✅' if ok else '⚠️ '} page-{page}.md 嵌入行：{line[:56]}…")

    # OCR：图里英文/数字关键字能不能真扫出来
    section("OCR 关键字抽检（对 PNG 反色后 tesseract）")
    for name, keywords in OCR_KEYWORDS.items():
        png = IMAGES / name
        text = ocr_text(png, tmpdir)
        if not text:
            say(f"  ⚠️  {name}：没有 tesseract/Pillow，跳过 OCR（主对账已用渲染前原文完成）")
            continue
        flat = squash(text)
        miss = [kw for kw in keywords if squash(kw) not in flat]
        ok = not miss
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} {name}：{len(keywords) - len(miss)}/"
            f"{len(keywords)} 命中" + (f"，未命中 {miss}" if miss else ""))

    # 尺寸
    section("PNG 尺寸")
    for name in OCR_KEYWORDS:
        png = IMAGES / name
        w, h = identify_size(png)
        ok = w == WINDOW_W_CSS * DEVICE_SCALE and h >= MIN_PNG_H
        all_ok = all_ok and ok
        say(f"  {'✅' if ok else '⚠️ '} {name}  {w}x{h}（@2x，宽 "
            f"{WINDOW_W_CSS * DEVICE_SCALE}）")

    # 禁止字符串：渲染前文本（与渲染同一份数据）里不能有用户名/路径/隔离端口/口令
    section("禁止字符串（用户名 / 主机名 / 绝对路径 / 隔离端口 / 口令）")
    passwords = []
    env_text = (REPO / ".env").read_text(encoding="utf-8")
    for line in env_text.splitlines():
        m = re.match(r"^(MYSQL_ROOT_PASSWORD|MYSQL_PASSWORD|REBUILD_DW_RO_PASSWORD)=(.*)$",
                     line.strip())
        if m and m.group(2):
            passwords.append(m.group(2))
    hits = []
    display_map = records["__display__"]
    for name, lines in display_map.items():
        for needle in FORBIDDEN + passwords:
            if needle and any(needle in line for line in lines):
                hits.append(f"{name}: {needle!r}")
    if hits:
        all_ok = False
        say(f"  ❌ 图内出现禁止字符串：{hits}")
    else:
        say(f"  ✅ {len(display_map)} 张图内容无用户名 / 主机名 / 绝对路径 / "
            f"隔离端口 / 口令（检查了 {', '.join(sorted(display_map))}）")
    for line in extra:
        say(f"  ℹ️  {line}")
    return all_ok


# ---------------------------------------------------------------- 主流程


def save_captures(records: dict) -> None:
    data = {k: v for k, v in records.items() if not k.startswith("__")}
    CAPTURES.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    say(f"  捕获缓存：{CAPTURES}（调试用；正常跑完会删）")


def render_all(shots: list[dict], records: dict, tmpdir: Path) -> list[Path]:
    section("渲染终端截图（真跑输出 → 深色终端版式）")
    targets = []
    for shot in shots:
        targets.append(render_shot(shot, tmpdir))
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="渲染练本第 13 页与 L4 第 18–22 页的真跑截图")
    parser.add_argument("--render-only", metavar="CAPTURES_JSON",
                        help="不跑命令，用上次的捕获缓存只重渲染 + 自检（调试用）")
    parser.add_argument("--keep", action="store_true",
                        help="跑完保留 /tmp/shots-l4 与隔离栈（调试用；正常会清）")
    parser.add_argument("--keep-captures", action="store_true",
                        help="保留捕获缓存 JSON（供 --render-only 用）")
    args = parser.parse_args(argv)

    t_start = time.monotonic()
    say("=" * 78)
    say("render_l4_pages.py —— 真跑第 13 页与 L4 第 18–22 页命令，生成 8 张终端截图")
    say(f"仓库：{REPO}")
    say(f"输出：{IMAGES.relative_to(REPO)}/page-1[38]-*.png / page-2[0-2]-*.png 共 8 张"
        f"（宽 {WINDOW_W_CSS * DEVICE_SCALE}px，@2x，高 ≥{MIN_PNG_H}px）")
    say(f"隔离：project={PROJECT}，端口 {HOST_PORTS}；跑完 down -v")
    say(f"内存：可用 {mem_available_mb()}MB（同一时间只跑这一个隔离栈）")
    say("=" * 78)
    IMAGES.mkdir(parents=True, exist_ok=True)

    if args.render_only:
        path = Path(args.render_only)
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = {k: {"cmd": v["cmd"], "lines": v["lines"],
                       "exit": v.get("exit", 0)} for k, v in raw.items()}
        shots = build_shots(records)
        records["__display__"] = collect_display_text(shots)
        with tempfile.TemporaryDirectory(prefix="shots-l4-render-") as tmp:
            render_all(shots, records, Path(tmp))
            ok = run_checks(records, shots, Path(tmp),
                            ["--render-only：未跑命令，仅用捕获缓存重渲染"])
        say("")
        say(f"完成（render-only），用时 {time.monotonic() - t_start:.1f}s。")
        return 0 if ok else 2

    preflight()
    work: Path | None = None
    stack_started = False
    user_before = user_stack_snapshot()
    records: dict = {}
    extra: list[str] = []
    min_mem = mem_available_mb()
    try:
        # 上一轮残留（本项目）先清掉，否则占着隔离端口
        if project_containers():
            say(f"发现上一轮残留的 project={PROJECT} 容器，先 down -v 清掉")
            cleanup_project(WORK if (WORK / "compose.yaml").exists() else None)
        work = prepare_workdir()

        # ---------------- 离线判据（不需要栈，先把不占内存的跑完）
        records.update(capture_offline(work))
        min_mem = min(min_mem, mem_available_mb())
        save_captures(records)

        # ---------------- 起隔离栈，跑需要栈的判据
        start_isolated_stack(work, extra)
        stack_started = True
        min_mem = min(min_mem, mem_available_mb())
        capture_stack(work, records, extra)
        min_mem = min(min_mem, mem_available_mb())
        save_captures(records)
        extra.append(
            f"内存：本脚本全程最低可用 {min_mem}MB（Windows VM 已关闭；"
            f"未出现 OOM，栈 5 个长驻服务全程 healthy）"
        )
    except KeyboardInterrupt:
        say("\n被 Ctrl+C 中断，开始清理……")
        return 130
    except Exception as exc:  # noqa: BLE001
        say(f"\n❌ 出错：{exc}")
        if records:
            save_captures(records)
        return 1
    finally:
        if not args.keep:
            section("清理")
            if stack_started or project_containers():
                stop_isolated_stack(
                    work if (work and (work / "compose.yaml").exists()) else None,
                    records)
            else:
                say("  隔离栈未启动，无需 down")
            if work is not None and work.exists():
                shutil.rmtree(work, ignore_errors=True)
            if WORK.exists():
                say(f"  ⚠️  {WORK} 没删掉，请手动检查")
            else:
                say(f"  ✅ 临时副本已删：{WORK}")
            user_after = user_stack_snapshot()
            if user_before == user_after:
                say(f"  ✅ 用户栈未变（{len(user_before)} 个非 {PROJECT} 容器前后一致）")
            else:
                say("  ⚠️  用户容器前后不一致（下面只影响本项目，请人工确认）：")
                say(f"      before-only: {sorted(set(user_before) - set(user_after))}")
                say(f"      after-only : {sorted(set(user_after) - set(user_before))}")
            # 仓库 uv.lock 若被改（uv 会按镜像配置静默重写），还原掉
            tracked = subprocess.run(
                ["git", "-C", str(REPO), "status", "--porcelain", "--",
                 "backend/uv.lock"],
                capture_output=True, text=True, timeout=60,
            ).stdout.strip()
            if tracked:
                subprocess.run(["git", "-C", str(REPO), "checkout", "--",
                                "backend/uv.lock"], timeout=60)
                say("  ✅ backend/uv.lock 被改过，已 git checkout -- 还原（命令都在 /tmp 副本里跑）")
            else:
                say("  ✅ backend/uv.lock 未被改动（命令都在 /tmp 副本里跑）")
        else:
            say(f"\n--keep：保留 {WORK} 与隔离栈（project={PROJECT}）。")

    if not args.keep:
        # 栈已 down，渲染（Chrome 不占着栈的内存）
        with tempfile.TemporaryDirectory(prefix="shots-l4-render-") as tmp:
            shots = build_shots(records)
            records["__display__"] = collect_display_text(shots)
            render_all(shots, records, Path(tmp))
            ok = run_checks(records, shots, Path(tmp), extra)
        if not args.keep_captures:
            CAPTURES.unlink(missing_ok=True)
            say(f"  ✅ 捕获缓存已删：{CAPTURES}")
        else:
            save_captures(records)
        section("汇总")
        for shot in shots:
            target = IMAGES / shot["file"]
            w, h = identify_size(target)
            say(f"  🖼  {target.relative_to(REPO)}  {w}x{h}  "
                f"（{target.stat().st_size / 1024:.0f} KB）")
        say("")
        say(f"完成，用时 {time.monotonic() - t_start:.1f}s。")
        return 0 if ok else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
