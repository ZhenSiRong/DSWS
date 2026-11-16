#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""term_render.py —— 真跑练本第 1–8 页的命令，把「提示符 + 真实输出」渲染成终端截图。

一条命令重跑全部图（在仓库根目录）：

    python3 manual/shots/term_render.py

它做四件事：

1. 在 /tmp 建一个**临时工作区**：软链 `backend/`（用仓库里现成的 venv），
   拷入 `fixtures/dw.sql` 和 `.env.example`，写入每页 `lab/app.py`。
   页面命令里全是相对路径，在临时工作区里逐字执行，所以图里不会出现
   `/home/...` 这类绝对路径。
2. 按**页序**在真 shell 里跑每页「动手」的命令：第 1 页起 MySQL（3307）并复用，
   第 3 页起每页用新代码重启 uvicorn（8000），curl 的输出逐条捕获（不手抄）。
3. 把捕获到的「命令 + 输出」拼成深色终端版式的 HTML，用
   `google-chrome --headless --screenshot` 截 1100px 宽、1:1 像素的图，
   再用 ImageMagick `convert -trim` 把高度裁到内容。
4. 把每页真跑输出与本页「## 你应该看到」的样例逐行对账（PID、耗时这类
   每次不同的数字按通配处理），并检查内容里没有用户名/主机名/绝对路径。

输出：`manual/images/page-0X-*.png`。跑完自动 `docker rm -f lab-mysql`、
杀掉 uvicorn、删掉临时工作区，不留残余。

依赖（本机已装，不新装）：docker、google-chrome、ImageMagick convert/identify、
仓库自带的 `backend/.venv`。端口：MySQL 3307、API 8000。
"""

from __future__ import annotations

import getpass
import html
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------- 常量

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"

WINDOW_W = 1100          # 窗口宽度固定 1100px（SPEC：窗宽固定）
WINDOW_H = 10000         # 先渲染得足够高，再用 -trim 裁到内容
FONT_PX = 14             # 等宽字号；-force-device-scale-factor=1，1:1 不缩放

MYSQL_PORT = 3307        # 与第 1 页 -p 127.0.0.1:3307:3306 一致
API_PORT = 8000          # 与第 3 页 uvicorn --port 8000 一致
CONTAINER = "lab-mysql"  # 第 1 页 --name lab-mysql（页面命令写死，必须一致）

MYSQL_WARN = "mysql: [Warning] Using a password on the command line interface can be insecure."

UVICORN = "backend/.venv/bin/python -m uvicorn lab.app:app --port 8000"
PY_APP = "backend/.venv/bin/python -m lab.app"

DOCKER_RUN = "\n".join(
    [
        "docker run -d --name lab-mysql \\",
        "  -p 127.0.0.1:3307:3306 \\",
        "  -e LANG=C.UTF-8 \\",
        "  -e MYSQL_ROOT_PASSWORD=labpass \\",
        "  -e MYSQL_USER=didilili \\",
        "  -e MYSQL_PASSWORD=labpass \\",
        '  -v "$PWD/fixtures/dw.sql:/docker-entrypoint-initdb.d/10-dw.sql:ro" \\',
        '  "$(grep \'^MYSQL_IMAGE=\' .env.example | cut -d= -f2)"',
    ]
)

WAIT_MYSQL = "until docker logs lab-mysql 2>&1 | grep -q 'port: 3306'; do sleep 2; done"

EXEC_TABLES = (
    'docker exec lab-mysql mysql -uroot -plabpass -N -B dw -e "SHOW TABLES;"'
)

EXEC_COUNT = (
    'docker exec lab-mysql mysql -uroot -plabpass -N -B dw '
    '-e "SELECT COUNT(*) FROM fact_order;"'
)

EXEC_COUNT_JOIN = (
    'docker exec lab-mysql mysql -uroot -plabpass -N -B dw -e '
    '"SELECT COUNT(*) FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id '
    'WHERE r.region_name = \'华北\';"'
)

EXEC_SAMPLE = "\n".join(
    [
        'docker exec lab-mysql mysql -uroot -plabpass -N -B dw -e "',
        "SELECT f.order_id, r.province, r.region_name, f.order_amount",
        "FROM fact_order f",
        "JOIN dim_region r ON f.region_id = r.region_id",
        "WHERE r.region_name = '华北'",
        'LIMIT 3;"',
    ]
)

CURL_HEALTH = "curl -s http://127.0.0.1:8000/health"

CURL_QUERY_1 = (
    "curl -s -X POST http://127.0.0.1:8000/api/query "
    "-H 'Content-Type: application/json' -d '{\"question\":\"华北销售额\"}'"
)
CURL_QUERY_2 = (
    "curl -s -X POST http://127.0.0.1:8000/api/query "
    "-H 'Content-Type: application/json' -d '{\"question\":\"华南订单量\"}'"
)
CURL_QUERY_3 = (
    "curl -s -X POST http://127.0.0.1:8000/api/query "
    "-H 'Content-Type: application/json' -d '{\"question\":\"华东的销售额是多少\"}'"
)

CURL_STREAM = "curl -sN -G 'http://127.0.0.1:8000/api/stream' --data-urlencode 'q=华北销售额'"

# ---------------------------------------------------------------- 每页 lab/app.py
# 与 manual/page-03.md … page-08.md 的代码逐字一致；第 6–8 页是按页面说明
# 在上一页文件上插入/替换后的完整文件（跑的是页面最终形态）。

APP_PAGE_03 = '''\
# lab/app.py —— 你的第一个 HTTP 服务
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}
'''

APP_PAGE_04 = '''\
# lab/app.py —— 加一个能“收问题”的接口
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Query(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/query")
def query(q: Query):
    return {
        "question": "华北销售额",
        "keywords": [],
        "sql": None,
        "rows": [],
    }
'''

APP_PAGE_05 = '''\
# lab/app.py —— 从问题里抽关键词（纯字符串规则，不用 AI）
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

REGIONS = ["华北", "华东", "华南", "西南", "华中"]
METRICS = ["销售额", "订单量"]


class Query(BaseModel):
    question: str


def extract_keywords(question: str) -> list[str]:
    keywords = []
    for word in REGIONS + METRICS:
        if word in question:
            keywords.append(word)
    return keywords


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/query")
def query(q: Query):
    keywords = extract_keywords(q.question)
    return {
        "question": q.question,
        "keywords": keywords,
        "sql": None,
        "rows": [],
    }
'''

APP_PAGE_06 = '''\
# lab/app.py —— 从问题里抽关键词（纯字符串规则，不用 AI）
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

REGIONS = ["华北", "华东", "华南", "西南", "华中"]
METRICS = ["销售额", "订单量"]


class Query(BaseModel):
    question: str


def extract_keywords(question: str) -> list[str]:
    keywords = []
    for word in REGIONS + METRICS:
        if word in question:
            keywords.append(word)
    return keywords


CONTRACT = {
    "tables": {
        "fact_order": ["region_id", "order_amount", "order_id"],
        "dim_region": ["region_id", "region_name"],
    },
    "metrics": {"销售额": "SUM(fact_order.order_amount)",
                "订单量": "COUNT(DISTINCT fact_order.order_id)"},
    "region_values": ["华北", "华东", "华南", "西南", "华中"],
}


def build_sql(keywords: list[str]) -> str:
    region = next(k for k in keywords if k in CONTRACT["region_values"])
    metric = next(k for k in keywords if k in CONTRACT["metrics"])
    sql = f"""SELECT dim_region.region_name, {CONTRACT['metrics'][metric]} AS sales
FROM fact_order
JOIN dim_region ON fact_order.region_id = dim_region.region_id
WHERE dim_region.region_name = '{region}'
GROUP BY dim_region.region_name"""
    return sql


if __name__ == "__main__":
    print(build_sql(extract_keywords("华北销售额")))


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/query")
def query(q: Query):
    keywords = extract_keywords(q.question)
    return {
        "question": q.question,
        "keywords": keywords,
        "sql": None,
        "rows": [],
    }
'''

APP_PAGE_07 = '''\
# lab/app.py —— 从问题里抽关键词（纯字符串规则，不用 AI）
import pymysql

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

REGIONS = ["华北", "华东", "华南", "西南", "华中"]
METRICS = ["销售额", "订单量"]


class Query(BaseModel):
    question: str


def extract_keywords(question: str) -> list[str]:
    keywords = []
    for word in REGIONS + METRICS:
        if word in question:
            keywords.append(word)
    return keywords


CONTRACT = {
    "tables": {
        "fact_order": ["region_id", "order_amount", "order_id"],
        "dim_region": ["region_id", "region_name"],
    },
    "metrics": {"销售额": "SUM(fact_order.order_amount)",
                "订单量": "COUNT(DISTINCT fact_order.order_id)"},
    "region_values": ["华北", "华东", "华南", "西南", "华中"],
}


def build_sql(keywords: list[str]) -> str:
    region = next(k for k in keywords if k in CONTRACT["region_values"])
    metric = next(k for k in keywords if k in CONTRACT["metrics"])
    sql = f"""SELECT dim_region.region_name, {CONTRACT['metrics'][metric]} AS sales
FROM fact_order
JOIN dim_region ON fact_order.region_id = dim_region.region_id
WHERE dim_region.region_name = '{region}'
GROUP BY dim_region.region_name"""
    return sql


def run_sql(sql: str) -> list[dict]:
    conn = pymysql.connect(host="127.0.0.1", port=3307, user="root",
                           password="labpass", database="dw",
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/query")
def query(q: Query):
    keywords = extract_keywords(q.question)
    sql = build_sql(keywords)
    return {"question": q.question, "keywords": keywords,
            "sql": sql, "rows": run_sql(sql)}
'''

APP_PAGE_08 = '''\
# lab/app.py —— 从问题里抽关键词（纯字符串规则，不用 AI）
import json
import pymysql
import time

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

REGIONS = ["华北", "华东", "华南", "西南", "华中"]
METRICS = ["销售额", "订单量"]


class Query(BaseModel):
    question: str


def extract_keywords(question: str) -> list[str]:
    keywords = []
    for word in REGIONS + METRICS:
        if word in question:
            keywords.append(word)
    return keywords


CONTRACT = {
    "tables": {
        "fact_order": ["region_id", "order_amount", "order_id"],
        "dim_region": ["region_id", "region_name"],
    },
    "metrics": {"销售额": "SUM(fact_order.order_amount)",
                "订单量": "COUNT(DISTINCT fact_order.order_id)"},
    "region_values": ["华北", "华东", "华南", "西南", "华中"],
}


def build_sql(keywords: list[str]) -> str:
    region = next(k for k in keywords if k in CONTRACT["region_values"])
    metric = next(k for k in keywords if k in CONTRACT["metrics"])
    sql = f"""SELECT dim_region.region_name, {CONTRACT['metrics'][metric]} AS sales
FROM fact_order
JOIN dim_region ON fact_order.region_id = dim_region.region_id
WHERE dim_region.region_name = '{region}'
GROUP BY dim_region.region_name"""
    return sql


def run_sql(sql: str) -> list[dict]:
    conn = pymysql.connect(host="127.0.0.1", port=3307, user="root",
                           password="labpass", database="dw",
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/query")
def query(q: Query):
    keywords = extract_keywords(q.question)
    sql = build_sql(keywords)
    return {"question": q.question, "keywords": keywords,
            "sql": sql, "rows": run_sql(sql)}


STEPS = ["extract_keywords", "recall_column", "recall_value", "recall_metric",
         "merge_retrieved_info", "filter_table", "filter_metric", "add_extra_context",
         "generate_sql", "validate_sql", "correct_sql", "run_sql"]


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\\n\\n"


@app.get("/api/stream")
def stream(q: str):
    def gen():
        for step in STEPS:
            t0 = time.perf_counter()
            time.sleep(0.15)  # 假装在干活，让你肉眼看到一条条到
            yield sse({"type": "progress", "step": step, "status": "success",
                       "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})
        rows = run_sql(build_sql(extract_keywords(q)))
        yield sse({"type": "result", "data": {"rows": rows}})

    return StreamingResponse(gen(), media_type="text/event-stream")
'''

# ---------------------------------------------------------------- 页面规格
# steps 里每一项按顺序执行；kind：
#   cmd     跑一条命令，捕获合并后的 stdout+stderr
#   server  起 uvicorn（后台），捕获到 "Uvicorn running on" 为止的启动日志
#   stop    给 uvicorn 发 SIGINT（相当于 Ctrl+C），不产生截图内容
#   stream  curl -sN 流式请求：逐行捕获并记录每行到达时间
#
# shots[].panes[].items 里 step 指上面 steps 的下标，part 取 cmd / out；
# out 的 pick：
#   all              全部输出行（默认）
#   first_events:N   前 N 个 SSE 事件（含事件之间真实存在的空行）
#   last_events:N    最后 N 个 SSE 事件
#
# checks 把某几步的真跑输出与页面「## 你应该看到」的第 block 个代码块对账。

PAGES = [
    {
        "id": "page-01",
        "code": None,
        "steps": [
            {"kind": "cmd", "cmd": DOCKER_RUN, "timeout": 180},
            {"kind": "cmd", "cmd": WAIT_MYSQL, "timeout": 180},
            {"kind": "cmd", "cmd": EXEC_TABLES, "timeout": 60},
        ],
        "checks": [{"block": 0, "steps": [2]}],
        "shots": [
            {
                "file": "page-01-mysql-tables.png",
                "panes": [
                    {
                        "title": "终端",
                        "items": [
                            {"step": 0, "part": "cmd"},
                            {"step": 0, "part": "out"},
                            {"step": 1, "part": "cmd"},
                            {"step": 2, "part": "cmd"},
                            {"step": 2, "part": "out"},
                        ],
                    }
                ],
            }
        ],
    },
    {
        "id": "page-02",
        "code": None,
        "steps": [
            {"kind": "cmd", "cmd": EXEC_COUNT, "timeout": 60},
            {"kind": "cmd", "cmd": EXEC_COUNT_JOIN, "timeout": 60},
            {"kind": "cmd", "cmd": EXEC_SAMPLE, "timeout": 60},
        ],
        "checks": [{"block": 0, "steps": [0, 1, 2]}],
        "shots": [
            {
                "file": "page-02-data-check.png",
                "panes": [
                    {
                        "title": "终端",
                        "items": [
                            {"step": 0, "part": "cmd"},
                            {"step": 0, "part": "out"},
                            {"step": 1, "part": "cmd"},
                            {"step": 1, "part": "out"},
                            {"step": 2, "part": "cmd"},
                            {"step": 2, "part": "out"},
                        ],
                    }
                ],
            }
        ],
    },
    {
        "id": "page-03",
        "code": APP_PAGE_03,
        "steps": [
            {"kind": "server", "cmd": UVICORN, "timeout": 30},
            {"kind": "cmd", "cmd": CURL_HEALTH, "timeout": 30},
            {"kind": "stop"},
        ],
        "checks": [{"block": 0, "steps": [0]}, {"block": 1, "steps": [1]}],
        "shots": [
            {
                "file": "page-03-health.png",
                "panes": [
                    {
                        "title": "终端 1",
                        "items": [
                            {"step": 0, "part": "cmd"},
                            {"step": 0, "part": "out"},
                        ],
                    },
                    {
                        "title": "终端 2",
                        "items": [
                            {"step": 1, "part": "cmd"},
                            {"step": 1, "part": "out"},
                        ],
                    },
                ],
            }
        ],
    },
    {
        "id": "page-04",
        "code": APP_PAGE_04,
        "steps": [
            {"kind": "server", "cmd": UVICORN, "timeout": 30},
            {"kind": "cmd", "cmd": CURL_QUERY_1, "timeout": 30},
            {"kind": "cmd", "cmd": CURL_QUERY_2, "timeout": 30},
            {"kind": "stop"},
        ],
        "checks": [{"block": 0, "steps": [1, 2]}],
        "shots": [
            {
                "file": "page-04-query-json.png",
                "panes": [
                    {
                        "title": "终端 2",
                        "items": [
                            {"step": 1, "part": "cmd"},
                            {"step": 1, "part": "out"},
                            {"step": 2, "part": "cmd"},
                            {"step": 2, "part": "out"},
                        ],
                    }
                ],
            }
        ],
    },
    {
        "id": "page-05",
        "code": APP_PAGE_05,
        "steps": [
            {"kind": "server", "cmd": UVICORN, "timeout": 30},
            {"kind": "cmd", "cmd": CURL_QUERY_1, "timeout": 30},
            {"kind": "cmd", "cmd": CURL_QUERY_3, "timeout": 30},
            {"kind": "stop"},
        ],
        "checks": [{"block": 0, "steps": [1, 2]}],
        "shots": [
            {
                "file": "page-05-keywords.png",
                "panes": [
                    {
                        "title": "终端 2",
                        "items": [
                            {"step": 1, "part": "cmd"},
                            {"step": 1, "part": "out"},
                            {"step": 2, "part": "cmd"},
                            {"step": 2, "part": "out"},
                        ],
                    }
                ],
            }
        ],
    },
    {
        "id": "page-06",
        "code": APP_PAGE_06,
        "steps": [{"kind": "cmd", "cmd": PY_APP, "timeout": 60}],
        "checks": [{"block": 0, "steps": [0]}],
        "shots": [
            {
                "file": "page-06-build-sql.png",
                "panes": [
                    {
                        "title": "终端",
                        "items": [
                            {"step": 0, "part": "cmd"},
                            {"step": 0, "part": "out"},
                        ],
                    }
                ],
            }
        ],
    },
    {
        "id": "page-07",
        "code": APP_PAGE_07,
        "steps": [
            {"kind": "server", "cmd": UVICORN, "timeout": 30},
            {"kind": "cmd", "cmd": CURL_QUERY_1, "timeout": 30},
            {"kind": "stop"},
        ],
        "checks": [{"block": 0, "steps": [1]}],
        "shots": [
            {
                "file": "page-07-rows.png",
                "panes": [
                    {
                        "title": "终端 2",
                        "items": [
                            {"step": 1, "part": "cmd"},
                            {"step": 1, "part": "out"},
                        ],
                    }
                ],
            }
        ],
    },
    {
        "id": "page-08",
        "code": APP_PAGE_08,
        "steps": [
            {"kind": "server", "cmd": UVICORN, "timeout": 30},
            {"kind": "stream", "cmd": CURL_STREAM, "timeout": 60},
            {"kind": "stop"},
        ],
        "checks": [{"block": 0, "steps": [1]}],
        "shots": [
            {
                "file": "page-08-stream.png",
                "panes": [
                    {
                        "title": "终端 2",
                        "items": [
                            {"step": 1, "part": "cmd"},
                            {"step": 1, "part": "out", "pick": "first_events:6"},
                        ],
                    }
                ],
            },
            {
                "file": "page-08-result.png",
                "panes": [
                    {
                        "title": "终端 2",
                        "items": [
                            {"step": 1, "part": "cmd"},
                            {"step": 1, "part": "out", "pick": "last_events:2"},
                        ],
                    }
                ],
            },
        ],
    },
]

# ---------------------------------------------------------------- 小工具


def say(msg: str = "") -> None:
    print(msg, flush=True)


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_port_closed(port: int, timeout: float = 15.0) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if not port_open(port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"端口 {port} 一直没释放")


def docker_names() -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


# ---------------------------------------------------------------- shell 执行


class Shell:
    """在临时工作区里跑命令；合并 stdout/stderr 以保证输出顺序是真终端顺序。"""

    def __init__(self, work: Path):
        self.work = work
        self.server: subprocess.Popen | None = None
        self.server_lines: list[str] = []
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    # -- 普通命令 ---------------------------------------------------------
    def run(self, cmd: str, timeout: float) -> list[str]:
        proc = subprocess.run(
            cmd, shell=True, cwd=self.work,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
        out = proc.stdout or ""
        if proc.returncode != 0:
            raise RuntimeError(
                f"命令失败（exit={proc.returncode}）：{cmd}\n--- 输出 ---\n{out}"
            )
        return out.splitlines()

    # -- 长跑服务 ---------------------------------------------------------
    def start_server(self, cmd: str, timeout: float) -> list[str]:
        wait_port_closed(API_PORT)
        self.server_lines = []
        self.server = subprocess.Popen(
            cmd, shell=True, cwd=self.work, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1, start_new_session=True,
        )

        def _pump() -> None:
            assert self.server is not None and self.server.stdout is not None
            for line in self.server.stdout:
                with self._lock:
                    self.server_lines.append(line.rstrip("\n"))

        self._reader = threading.Thread(target=_pump, daemon=True)
        self._reader.start()

        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.server.poll() is not None:
                raise RuntimeError(
                    "uvicorn 没起来就退出了：\n" + "\n".join(self.log_snapshot())
                )
            lines = self.log_snapshot()
            for i, line in enumerate(lines):
                if "Uvicorn running on" in line:
                    time.sleep(0.2)                    # 等最后一行日志落盘
                    return self.log_snapshot()[: i + 1]
            time.sleep(0.05)
        raise RuntimeError("等 uvicorn 启动超时：\n" + "\n".join(self.log_snapshot()))

    def stop_server(self) -> list[str]:
        proc = self.server
        if proc is None:
            return []
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=5)
        finally:
            if self._reader is not None:
                self._reader.join(timeout=5)
            self.server = None
        wait_port_closed(API_PORT)
        return self.log_snapshot()

    def log_snapshot(self) -> list[str]:
        with self._lock:
            return list(self.server_lines)

    # -- 流式请求 ---------------------------------------------------------
    def stream(self, cmd: str, timeout: float) -> tuple[list[str], list[tuple[float, str]]]:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=self.work, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1,
        )
        assert proc.stdout is not None
        timed: list[tuple[float, str]] = []
        t0 = time.monotonic()

        def _pump() -> None:
            for line in proc.stdout:  # type: ignore[union-attr]
                timed.append((time.monotonic() - t0, line.rstrip("\n")))

        reader = threading.Thread(target=_pump, daemon=True)
        reader.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(f"流式请求超时：{cmd}")
        reader.join(timeout=5)
        if proc.returncode != 0:
            raise RuntimeError(f"curl 失败（exit={proc.returncode}）：{cmd}")
        return [line for _, line in timed], timed

    def shutdown(self) -> None:
        if self.server is not None:
            try:
                self.stop_server()
            except Exception:
                pass


# ---------------------------------------------------------------- 输出选择


def select_lines(lines: list[str], pick: str | None) -> list[str]:
    """从一个步骤的原始输出里挑要上图的几行。"""
    if not pick or pick == "all":
        return list(lines)

    m = re.fullmatch(r"(first|last)_events:(\d+)", pick)
    if not m:
        raise ValueError(f"不认识的 pick：{pick}")
    where, n = m.group(1), int(m.group(2))

    # SSE 输出里「事件」= 非空行；事件之间真实存在一个空行，要一起保留。
    idx = [i for i, line in enumerate(lines) if line.strip()]
    if len(idx) < n:
        raise RuntimeError(f"只捕获到 {len(idx)} 个事件，不够 {n} 个")
    if where == "first":
        start = 0
        end = idx[n] if n < len(idx) else len(lines)
    else:
        start = idx[-n]
        end = len(lines)
    picked = lines[start:end]
    while picked and not picked[-1].strip():
        picked.pop()
    return picked


# ---------------------------------------------------------------- HTML 渲染

CSS = """
:root {
  --page-bg: #04070b;   /* 页面底色：与终端底色不同，-trim 靠它找边界 */
  --term-bg: #0d1117;
  --bar-bg:  #161b22;
  --border:  #21262d;
  --fg:      #e6edf3;
  --dim:     #8b949e;
  --green:   #3fb950;
  --purple:  #d2a8ff;
  --yellow:  #d29922;
  --blue:    #79c0ff;
}
html, body { margin: 0; padding: 0; background: var(--page-bg); }
.wrap { width: 1100px; padding: 18px 0; }
.pane { background: var(--term-bg); border: 1px solid var(--border);
        border-radius: 10px; overflow: hidden; }
.pane + .pane { margin-top: 14px; }
.titlebar { background: var(--bar-bg); color: var(--dim);
            padding: 8px 16px; border-bottom: 1px solid var(--border);
            font: 12px/1 "JetBrains Mono", "Noto Sans CJK SC", monospace;
            letter-spacing: 0.02em; }
pre { margin: 0; padding: 16px 22px; color: var(--fg);
      font-family: "JetBrains Mono", "DejaVu Sans Mono", "Noto Sans CJK SC", monospace;
      font-size: 14px; line-height: 1.62; font-variant-ligatures: none;
      white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 8; }
.p  { color: var(--green); font-weight: 700; }   /* 一级提示符 $ */
.p2 { color: var(--green); opacity: 0.6; }       /* 续行提示符 > */
.c  { color: var(--purple); }                    /* 敲进去的命令 */
.w  { color: var(--yellow); }                    /* 已知无害的 Warning */
.k  { color: var(--blue); }                      /* INFO: / data: 前缀 */
"""


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def html_out_line(line: str) -> str:
    if not line.strip():
        return ""  # 保留真实的空行（SSE 事件之间的分隔）
    if line == MYSQL_WARN:
        return f'<span class="w">{esc(line)}</span>'
    m = re.match(r"^(INFO:)(.*)$", line)
    if m:
        return f'<span class="k">INFO:</span>{esc(m.group(2))}'
    m = re.match(r"^(data:)(.*)$", line)
    if m:
        return f'<span class="k">data:</span>{esc(m.group(2))}'
    return esc(line)


def html_cmd_lines(cmd: str) -> list[str]:
    out = []
    for i, line in enumerate(cmd.split("\n")):
        prompt = '<span class="p">$ </span>' if i == 0 else '<span class="p2">&gt; </span>'
        out.append(prompt + f'<span class="c">{esc(line)}</span>')
    return out


def build_html(panes: list[dict], records: dict[int, list[str]]) -> str:
    chunks = []
    for pane in panes:
        rows: list[str] = []
        for item in pane["items"]:
            rec = records[item["step"]]
            if item["part"] == "cmd":
                rows.extend(html_cmd_lines(rec["cmd"]))
            elif item["part"] == "out":
                rows.extend(html_out_line(line) for line in select_lines(rec["lines"], item.get("pick")))
            else:
                raise ValueError(item["part"])
        chunks.append(
            f'<div class="pane"><div class="titlebar">{esc(pane["title"])}</div>'
            f'<pre>{"\n".join(rows)}</pre></div>'
        )
    body = "\n".join(chunks)
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f"<style>{CSS}</style></head><body>"
        f'<div class="wrap">{body}</div></body></html>\n'
    )


# ---------------------------------------------------------------- 截图


def chrome_screenshot(html_path: Path, png_path: Path, profile_dir: Path) -> None:
    png_path.unlink(missing_ok=True)
    cmd = [
        "google-chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size={WINDOW_W},{WINDOW_H}",
        f"--user-data-dir={profile_dir}",
        f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError(
            "chrome 截图失败：\n" + (proc.stderr or proc.stdout or "")[-4000:]
        )


def trim_png(raw: Path, out: Path) -> tuple[int, int]:
    subprocess.run(
        ["convert", str(raw), "-trim", "+repage", str(out)],
        check=True, capture_output=True, timeout=120,
    )
    ident = subprocess.run(
        ["identify", "-format", "%w %h", str(out)],
        check=True, capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    w, h = (int(x) for x in ident.split())
    if w != WINDOW_W:
        raise RuntimeError(f"{out.name} 宽度是 {w}px，不是约定的 {WINDOW_W}px")
    return w, h


def render_shot(shot: dict, records: dict[int, list[str]], work: Path) -> Path:
    html_text = build_html(shot["panes"], records)
    stem = Path(shot["file"]).stem
    html_path = work / f"{stem}.html"
    html_path.write_text(html_text, encoding="utf-8")
    raw = work / f"{stem}.raw.png"
    target = IMAGES / shot["file"]
    chrome_screenshot(html_path, raw, work / "chrome-profile")
    w, h = trim_png(raw, target)
    say(f"    🖼  {target.relative_to(REPO)}  {w}x{h}")
    return target


# ---------------------------------------------------------------- 页面样例对账

_PID_RE = re.compile(r"\[\d+\]")
_MS_RE = re.compile(r'"duration_ms": \d+(?:\.\d+)?')


def normalize(line: str) -> str:
    line = _PID_RE.sub("[<pid>]", line)
    line = _MS_RE.sub('"duration_ms": <ms>', line)
    return line.rstrip()


def clean_output(lines: list[str]) -> list[str]:
    """去掉页面上已说明过的已知噪声行和空行，便于逐行对账。"""
    cleaned = []
    for line in lines:
        if not line.strip():
            continue
        if line == MYSQL_WARN:
            continue
        cleaned.append(normalize(line))
    return cleaned


def page_expected_blocks(page_id: str) -> list[list[str]]:
    text = (REPO / "manual" / f"{page_id}.md").read_text(encoding="utf-8")
    m = re.search(r"^## 你应该看到[ \t]*\n(.*?)^## 对账", text, re.S | re.M)
    if not m:
        return []
    section = m.group(1)
    blocks = re.findall(r"^```[A-Za-z]*[ \t]*\n(.*?)^```[ \t]*$", section, re.S | re.M)
    return [[normalize(line) for line in block.rstrip("\n").split("\n")] for block in blocks]


def compare_block(real: list[str], expected: list[str]) -> tuple[bool, str]:
    """真跑输出 vs 页面样例；含「…」的块按 头/省略/尾 三段对。"""
    ell = next((i for i, line in enumerate(expected) if "…" in line), None)
    if ell is None:
        head, tail, mid_ok = expected, [], 0
    else:
        head, tail = expected[:ell], expected[ell + 1:]
        mid_ok = len(real) - len(head) - len(tail)
        if mid_ok < 0:
            mid_ok = -1

    problems = []
    for i, (exp, got) in enumerate(zip(head, real)):
        if exp != got:
            problems.append(f"第 {i + 1} 行：页面 {exp!r} ≠ 真跑 {got!r}")
    if len(real) < len(head) + len(tail):
        problems.append(f"真跑只有 {len(real)} 行，页面样例至少 {len(head) + len(tail)} 行")
    else:
        for i, exp in enumerate(tail):
            got = real[len(real) - len(tail) + i]
            if exp != got:
                problems.append(f"尾部第 {i + 1} 行：页面 {exp!r} ≠ 真跑 {got!r}")
    if ell is None:
        if len(real) > len(expected):
            problems.append(f"真跑多出 {len(real) - len(expected)} 行：" + " / ".join(real[len(expected):]))
        elif len(real) < len(expected) and not problems:
            problems.append(f"真跑少 {len(expected) - len(real)} 行")
    if problems:
        return False, "；".join(problems)
    if ell is None:
        return True, f"{len(real)} 行逐行一致"
    return True, f"首 {len(head)} 行 + 末 {len(tail)} 行一致（中间 {mid_ok} 行页面用 … 省略）"


def run_checks(page: dict, records: dict[int, list[str]]) -> bool:
    blocks = page_expected_blocks(page["id"])
    ok_all = True
    for check in page.get("checks", []):
        real: list[str] = []
        for step in check["steps"]:
            real.extend(clean_output(records[step]["lines"]))
        idx = check["block"]
        if idx >= len(blocks):
            say(f"  ⚠️  {page['id']}：页面里找不到第 {idx + 1} 个样例块")
            ok_all = False
            continue
        ok, detail = compare_block(real, blocks[idx])
        ok_all = ok_all and ok
        mark = "✅" if ok else "⚠️ "
        say(f"  {mark} 样例块 {idx + 1}（step {check['steps']}）：{detail}")
    return ok_all


# ---------------------------------------------------------------- 工作区准备


def prepare_workdir() -> Path:
    work = Path(tempfile.mkdtemp(prefix="manual-shots-"))
    os.symlink(REPO / "backend", work / "backend", target_is_directory=True)
    (work / "fixtures").mkdir()
    shutil.copy2(REPO / "fixtures" / "dw.sql", work / "fixtures" / "dw.sql")
    shutil.copy2(REPO / ".env.example", work / ".env.example")
    (work / "lab").mkdir()
    return work


def preflight() -> None:
    missing = [tool for tool in ("docker", "google-chrome", "convert", "identify")
               if shutil.which(tool) is None]
    if missing:
        sys.exit(f"缺少依赖：{', '.join(missing)}（本脚本不装新依赖）")
    for port in (MYSQL_PORT, API_PORT):
        if port_open(port):
            sys.exit(
                f"端口 {port} 已被占用；本脚本不杀别人的进程。"
                f"先停掉占用它的服务再重跑。"
            )
    if CONTAINER in docker_names():
        say(f"发现上一轮残留的容器 {CONTAINER}，先删除（脚本会自己清理，正常不应出现）")
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, timeout=60)
    IMAGES.mkdir(parents=True, exist_ok=True)


def cleanup(work: Path | None) -> None:
    try:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, timeout=60)
    except Exception:
        pass
    if work is not None:
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- 主流程


def main() -> int:
    t_start = time.monotonic()
    say("=" * 78)
    say("term_render.py —— 真跑第 1–8 页命令，生成终端运行截图")
    say(f"仓库：{REPO}")
    say(f"输出：{IMAGES.relative_to(REPO)}/page-0X-*.png   （窗口宽 {WINDOW_W}px，字号 {FONT_PX}px）")
    say("=" * 78)

    preflight()
    work: Path | None = None
    sh = None
    checks: dict[str, bool] = {}
    try:
        work = prepare_workdir()
        say(f"临时工作区：{work}（命令里的相对路径都在这里，图里不出现绝对路径）")
        sh = Shell(work)

        for page in PAGES:
            say("")
            say(f"── {page['id']} ──")
            if page["code"] is not None:
                (work / "lab" / "app.py").write_text(page["code"], encoding="utf-8")
                say("    写入 lab/app.py（与页面代码一致）")

            records: dict[int, list[str]] = {}
            for i, step in enumerate(page["steps"]):
                kind = step["kind"]
                t0 = time.monotonic()
                if kind == "cmd":
                    shown = step["cmd"].split("\n")[0]
                    say(f"    $ {shown}")
                    lines = sh.run(step["cmd"], step["timeout"])
                    records[i] = {"cmd": step["cmd"], "lines": lines}
                    say(f"      → exit 0，{len(lines)} 行输出（{time.monotonic() - t0:.1f}s）")
                elif kind == "server":
                    say(f"    $ {step['cmd']}   （后台服务，等它就绪）")
                    startup = sh.start_server(step["cmd"], step["timeout"])
                    records[i] = {"cmd": step["cmd"], "lines": startup}
                    say(f"      → 启动日志 {len(startup)} 行（{time.monotonic() - t0:.1f}s）")
                elif kind == "stream":
                    say(f"    $ {step['cmd']}   （流式：逐行捕获并记录到达时间）")
                    lines, timed = sh.stream(step["cmd"], step["timeout"])
                    records[i] = {"cmd": step["cmd"], "lines": lines, "timed": timed}
                    say(f"      → {len(lines)} 行（{time.monotonic() - t0:.1f}s）")
                elif kind == "stop":
                    stop_lines = sh.stop_server()
                    say(f"    Ctrl+C 停服务（收尾日志 {len(stop_lines)} 行，不上图）")
                else:
                    raise ValueError(kind)

            # 真跑 vs 页面样例
            say("    —— 与页面「你应该看到」对账 ——")
            checks[page["id"]] = run_checks(page, records)

            # 第 8 页额外量一下流式节奏（页面对账里说「约 0.15 秒一条」）
            for i, step in enumerate(page["steps"]):
                if step["kind"] == "stream":
                    timed = records[i].get("timed", [])
                    events = [t for t, line in timed if line.strip()]
                    if len(events) >= 2:
                        gaps = [(b - a) * 1000 for a, b in zip(events, events[1:])]
                        say(
                            f"    ⏱  流式节奏：{len(events)} 个事件，相邻间隔 "
                            f"{min(gaps):.0f}/{sorted(gaps)[len(gaps) // 2]:.0f}/{max(gaps):.0f} ms"
                            f"（min/中位/max），首末总时长 {events[-1] - events[0]:.2f}s"
                        )

            # 渲染截图
            say("    —— 渲染终端截图 ——")
            all_lines: list[str] = []
            for shot in page["shots"]:
                for pane in shot["panes"]:
                    for item in pane["items"]:
                        rec = records[item["step"]]
                        if item["part"] == "cmd":
                            all_lines.extend(rec["cmd"].split("\n"))
                        else:
                            all_lines.extend(select_lines(rec["lines"], item.get("pick")))
                render_shot(shot, records, work)

            # 硬约束：图里的文字不能有用户名 / 主机名 / 绝对路径
            forbidden = ["/home/", "/root/", getpass.getuser(), socket.gethostname()]
            hit = [needle for needle in forbidden if needle and any(needle in line for line in all_lines)]
            if hit:
                raise RuntimeError(f"{page['id']} 的截图内容出现禁止字符串 {hit}，已中止")
            say("    ✅ 内容检查：无用户名 / 主机名 / 绝对路径")

        say("")
        say("=" * 78)
        say("汇总")
        say("=" * 78)
        for page in PAGES:
            mark = "✅" if checks.get(page["id"], False) else "⚠️ "
            files = ", ".join(shot["file"] for shot in page["shots"])
            say(f"  {mark} {page['id']}：{files}")
        say("")
        say("截图（identify）：")
        for page in PAGES:
            for shot in page["shots"]:
                path = IMAGES / shot["file"]
                ident = subprocess.run(
                    ["identify", "-format", "%f  %wx%h", str(path)],
                    capture_output=True, text=True, timeout=60,
                ).stdout.strip()
                say(f"  {ident}")
        say("")
        if not all(checks.values()):
            say("⚠️  有页面样例与真跑输出不完全一致（见上面每个 ⚠️ 行）。")
            say("    截图内容仍是真跑输出；页面文字未改动，差异请人工决定是否修订页面。")
        say(f"完成，用时 {time.monotonic() - t_start:.1f}s。")
        return 0
    except KeyboardInterrupt:
        say("\n被 Ctrl+C 中断，开始清理……")
        return 130
    except Exception as exc:  # noqa: BLE001
        say(f"\n❌ 出错：{exc}")
        return 1
    finally:
        if sh is not None:
            sh.shutdown()
        cleanup(work)


if __name__ == "__main__":
    sys.exit(main())
