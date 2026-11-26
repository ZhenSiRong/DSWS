#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_l2_pages.py —— 真跑练本 L2 第 10 / 11 / 12 页的命令，渲染 4 张终端运行截图。

一条命令重跑全部图（在仓库根目录）：

    python3 tutorial/shots/render_l2_pages.py

做四件事：

1. 在 `/tmp/shots-l2` 建一个**临时工作区**：拷入 `system/fixtures/`、`system/contracts/`、
   `toolbox/scripts/lab`、`system/backend/app`、`system/backend/.venv`、`materials/docs/SCHEMA-CONTRACT.md`、
   `compose.yaml`、`lab/`。页面命令全是相对路径，在临时工作区里逐字执行，
   所以图里不会出现 `/home/...` 这类绝对路径。
2. 起一个临时 MySQL 容器 `shots-l2-mysql`（端口 3310；被占就顺延 3311 / 3312），
   灌入 `system/fixtures/dw-real.sql`。**不碰**学生已有的 `lab-mysql` 容器和 3307 端口。
3. 按三页正文真跑命令：
   - 第 10 页：`toolbox/scripts/lab save` → 灌 `dw-real.sql` → `dw-real.checks.sql` 对账
     → `--check`（绿）→ 把副本里契约的 `expected_fact_rows` 改成 410 → `--check`（红）
     → `toolbox/scripts/lab reset` 还原 → 重灌 `dw.sql`；
   - 第 11 页：写第 11 页版 `lab/app.py` → `python -m lab.app` → `--check`；
   - 第 12 页：写 `lab/db.py` + 第 12 页版 `lab/app.py` → 灌回 `dw-real.sql`
     → 接管验证（回 1000）→ `python -m lab.db` 七行自检（超时那行真等 5 秒）。
4. 把真跑输出渲染成 4 张 3200×1800（@2x）深色终端图，并做图文一致性自检：
   页面「## 你应该看到」的样例块逐行与真跑输出对账、OCR 抽关键字、检查图里
   没有用户名 / 主机名 / 绝对路径。

输出（只写这四个文件）：

    tutorial/images/page-10-checks.png     第 10 页 `dw-real.checks.sql` 对账输出
    tutorial/images/page-10-gate.png       第 10 页 `--check` 绿 / 红两次运行
    tutorial/images/page-11-contract.png   第 11 页 5 行 SQL + `S1 PASS`
    tutorial/images/page-12-executor.png   第 12 页执行器自检 7 行（+ 接管验证）

两条约定：

- 页面命令里的容器名 `lab-mysql` 是学生环境的名字。本脚本执行时**只把这一处**
  换成临时容器 `shots-l2-mysql`，截图里仍显示页面原文的 `lab-mysql`——学生照着
  页面敲的就是这个名字，图与页面才对得上。临时容器跑完 `docker rm -f`。
- 第 10 页的 `expected_fact_rows: 115 → 410` 只改 `/tmp/shots-l2` 副本里的
  `system/contracts/schema.contract.yaml`，仓库文件一个都不动。

依赖（本机已装，不新装）：docker、google-chrome、ImageMagick convert/identify、
仓库自带的 `system/backend/.venv`；OCR 自检可选依赖 tesseract（没装就跳过，主对账照做）。
"""

from __future__ import annotations

import getpass
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------- 常量

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"
PAGE_MD = {
    10: REPO / "manual" / "page-10.md",
    11: REPO / "manual" / "page-11.md",
    12: REPO / "manual" / "page-12.md",
}

WORK = Path("/tmp/shots-l2")                    # 临时工作区（隔离，跑完删）
CONTAINER = "shots-l2-mysql"                    # 临时容器名（不碰 lab-mysql）
MYSQL_IMAGE = "mysql:8.0"
PORT_CANDIDATES = (3310, 3311, 3312)

WINDOW_W_CSS = 1600                             # 窗宽 1600 CSS px
DEVICE_SCALE = 2                                # @2x：PNG 宽 3200 px
WINDOW_H_CSS = 3000                             # 先渲高一点，再 -trim 到内容
MIN_PNG_H = 1800                                # 不足 1800 的图上下补背景到 1800
PAGE_BG = "#04070b"                             # 与 term_render.CSS 的 --page-bg 一致
MYSQL_WARN = "mysql: [Warning] Using a password on the command line interface can be insecure."

# 与页面「## 动手」逐字一致（改页面时这里要同步；脚本会断言它们真出现在页面里）
CMD10_SAVE = "toolbox/scripts/lab save p10-before"
CMD10_IMPORT_REAL = (
    "docker exec -i lab-mysql mysql -uroot -plabpass "
    "--default-character-set=utf8mb4 < system/fixtures/dw-real.sql"
)
CMD10_CHECKS = (
    "docker exec -i lab-mysql mysql -uroot -plabpass "
    "--default-character-set=utf8mb4 < system/fixtures/dw-real.checks.sql"
)
CMD_CHECK = "(cd system/backend && .venv/bin/python -m app.schema_contract --check)"
CMD10_RESET = "toolbox/scripts/lab reset p10-before --yes"
CMD10_IMPORT_DEMO = "docker exec -i lab-mysql mysql -uroot -plabpass < system/fixtures/dw.sql"
CMD10_COUNT = (
    'docker exec lab-mysql mysql -uroot -plabpass -N -B dw '
    '-e "SELECT COUNT(*) FROM fact_order;"'
)
CMD11_APP = "system/backend/.venv/bin/python -m lab.app"
CMD11_SAVE = "toolbox/scripts/lab save p11-before"
CMD11_RESET = "toolbox/scripts/lab reset p11-before --yes"
CMD12_IMPORT_REAL = CMD10_IMPORT_REAL
CMD12_STEP3 = (
    'system/backend/.venv/bin/python -c "from lab.app import run_sql; '
    "print(len(run_sql('SELECT * FROM dim_date')))\""
)
CMD12_SELFTEST = "system/backend/.venv/bin/python -m lab.db"

EXPECTED_CONTRACT_ROWS = "  expected_fact_rows: 115"
REGION_VALUES_LINE = "          values: [华南, 华东, 西南, 华北, 华中]"
REGION_VALUES_BROKEN = "          values: [华南, 华东, 西南, 华中]"

FORBIDDEN = [
    "/home/", "/root/", "/tmp/", "/Users/", "/var/", "zhensirong", ".dsh",
    CONTAINER, WORK.name,
]

# 每次运行都会变、但对账时要当相同的数字：第 11 页 traceback 的行号、路径不参与精确比对
OCR_KEYWORDS = {
    "page-10-checks.png": ["1136341.10", "1144735.50", "405", "D1", "D7", "410"],
    "page-10-gate.png": ["S1 PASS", "DATASET_ROW_COUNT", "FAIL: 1", "410"],
    "page-11-contract.png": [
        "S1 PASS", "SELECT dim_region.region_name",
        "SUM(fact_order.order_amount)", "279159.5",
    ],
    "page-12-executor.png": [
        "Decimal", "1144735.50", "PermissionError", "OperationalError", "1000",
    ],
}

# ---------------------------------------------------------------- 复用 term_render

sys.dont_write_bytecode = True                  # 不在 tutorial/shots 里写 __pycache__
sys.path.insert(0, str(HERE))
import term_render as tr  # noqa: E402

# term_render 的 CSS 按窗宽 1100 写死，这里只把窗宽换成 1600，字体/配色/版式不变。
tr.CSS = tr.CSS.replace("1100px", f"{WINDOW_W_CSS}px")
if "1100px" in tr.CSS:
    raise RuntimeError("term_render.CSS 的窗宽没替换干净")


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


def docker_names() -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def run_shell(cmd: str, cwd: Path, timeout: float,
              allowed_codes: tuple[int, ...] = (0,)) -> tuple[list[str], int]:
    """跑一条 shell 命令，合并 stdout/stderr；返回 (输出行, 退出码)。"""
    proc = subprocess.run(
        cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", timeout=timeout,
    )
    lines = (proc.stdout or "").splitlines()
    if proc.returncode not in allowed_codes:
        raise RuntimeError(
            f"命令失败（exit={proc.returncode}，允许 {allowed_codes}）：{cmd}\n"
            "--- 输出 ---\n" + "\n".join(lines[-40:])
        )
    return lines, proc.returncode


def exec_command(display_cmd: str) -> str:
    """把页面命令里学生环境的容器名换成临时容器名（只改执行，不改截图文字）。"""
    if "docker exec" in display_cmd:
        return display_cmd.replace("lab-mysql", CONTAINER)
    return display_cmd


def capture(work: Path, records: dict, key: str, cmd: str, timeout: float,
            allowed_codes: tuple[int, ...] = (0,)) -> tuple[list[str], int]:
    """真跑一条命令并记下「页面原文命令 + 真实输出」，供后面渲染。"""
    exec_cmd = exec_command(cmd)
    t0 = time.monotonic()
    say(f"    $ {cmd}")
    if exec_cmd != cmd:
        say(f"      （执行时容器名换成 {CONTAINER}：{exec_cmd}）")
    lines, code = run_shell(exec_cmd, work, timeout, allowed_codes)
    records[key] = {"cmd": cmd, "lines": lines}
    say(f"      → exit {code}，{len(lines)} 行输出（{time.monotonic() - t0:.1f}s）")
    return lines, code


def run_quiet(work: Path, cmd: str, timeout: float,
              allowed_codes: tuple[int, ...] = (0,)) -> tuple[list[str], int]:
    """跑一条不上图的命令（快照 / 重灌 / 计数等），只记日志。"""
    exec_cmd = exec_command(cmd)
    say(f"    $ {cmd}" + ("" if exec_cmd == cmd else f"   （执行时容器名换成 {CONTAINER}）"))
    lines, code = run_shell(exec_cmd, work, timeout, allowed_codes)
    say(f"      → exit {code}，{len(lines)} 行输出")
    return lines, code


# ---------------------------------------------------------------- 页面解析


def page_text(page: int) -> str:
    return PAGE_MD[page].read_text(encoding="utf-8")


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """返回 markdown 里所有 ``` 块 [(语言, 内容), ...]。"""
    return re.findall(
        r"^```([A-Za-z]*)[ \t]*\n(.*?)^```[ \t]*$", text, re.S | re.M
    )


def expected_blocks(page: int) -> list[list[str]]:
    """页面「## 你应该看到」里的代码块，每块一行一个字符串（保留 Tab）。"""
    text = page_text(page)
    m = re.search(r"^## 你应该看到[ \t]*\n(.*?)^## 对账", text, re.S | re.M)
    if not m:
        raise RuntimeError(f"page-{page}.md 里找不到「## 你应该看到」段")
    blocks = fenced_blocks(m.group(1))
    if not blocks:
        raise RuntimeError(f"page-{page}.md 的「你应该看到」里没有代码块")
    return [[line.rstrip() for line in body.rstrip("\n").split("\n")]
            for _, body in blocks]


def instruction_blocks(page: int) -> list[str]:
    """页面「## 动手」里的代码块内容。"""
    text = page_text(page)
    m = re.search(r"^## 动手[ \t]*\n(.*?)^## 你应该看到", text, re.S | re.M)
    if not m:
        raise RuntimeError(f"page-{page}.md 里找不到「## 动手」段")
    return [body for _, body in fenced_blocks(m.group(1))]


def build_app_page11() -> str:
    """第 8 页的 lab/app.py + 第 11 页的三处改动 = 第 11 页最终形态。

    第 2 步的加载块、第 3 步的 build_sql 前 3 行直接从 page-11.md 的代码块里取，
    保证和页面逐字一致；第 1 步的两行 import 在页面里是行内代码，这里按正文插入。
    """
    p11 = page_text(11)
    if "`import yaml`" not in p11 or "`from pathlib import Path`" not in p11:
        raise RuntimeError("page-11.md 第 1 步的 import 说明变了，脚本要同步")

    blocks = instruction_blocks(11)
    load_block = next(
        b for b in blocks
        if b.startswith("ROOT = Path(__file__).resolve().parents[1]")
    )
    build_block = next(
        b for b in blocks if 'sql = f"""SELECT dim_region.region_name' in b
    )

    app = tr.APP_PAGE_08
    import_anchor = "import time\n\nfrom fastapi import FastAPI"
    if app.count(import_anchor) != 1:
        raise RuntimeError("第 8 页 app.py 的 import 段与预期不一致")
    app = app.replace(
        import_anchor,
        "import time\nimport yaml\nfrom pathlib import Path\n\nfrom fastapi import FastAPI",
    )

    old_contract = '''CONTRACT = {
    "tables": {
        "fact_order": ["region_id", "order_amount", "order_id"],
        "dim_region": ["region_id", "region_name"],
    },
    "metrics": {"销售额": "SUM(fact_order.order_amount)",
                "订单量": "COUNT(DISTINCT fact_order.order_id)"},
    "region_values": ["华北", "华东", "华南", "西南", "华中"],
}
'''
    if app.count(old_contract) != 1:
        raise RuntimeError("第 8 页 app.py 里没找到要删的 CONTRACT 字典")
    app = app.replace(old_contract, load_block)

    old_build = (
        '    region = next(k for k in keywords if k in CONTRACT["region_values"])\n'
        '    metric = next(k for k in keywords if k in CONTRACT["metrics"])\n'
        '    sql = f"""SELECT dim_region.region_name, '
        "{CONTRACT['metrics'][metric]} AS sales\n"
    )
    if app.count(old_build) != 1:
        raise RuntimeError("第 8 页 app.py 里没找到要换的 build_sql 前 3 行")
    app = app.replace(old_build, build_block)

    lines = app.splitlines()
    # 第 11 页「拆一刀」里 traceback 写的是 lab/app.py 第 48 行，这里对一下。
    if len(lines) < 48 or "region = next(k for k in keywords if k in _region_values())" not in lines[47]:
        raise RuntimeError(
            "第 11 页 app.py 的 region 那行没落在第 48 行，"
            f"实际第 {next((i + 1 for i, l in enumerate(lines) if 'region = next(' in l), '?')} 行"
        )
    return app


def build_app_page12(app11: str) -> str:
    """第 11 页的 lab/app.py + 第 12 页第 3 步的两处改动。"""
    blocks = instruction_blocks(12)
    run_block = next(b for b in blocks if b.startswith("def run_sql(sql: str) -> list[dict]:"))
    app = app11.replace(
        "from pathlib import Path\n",
        "from pathlib import Path\nfrom lab import db\n", 1,
    )
    old_run = '''def run_sql(sql: str) -> list[dict]:
    conn = pymysql.connect(host="127.0.0.1", port=3307, user="root",
                           password="labpass", database="dw",
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    finally:
        conn.close()
'''
    if app.count(old_run) != 1:
        raise RuntimeError("第 11 页 app.py 里没找到要换的 run_sql")
    return app.replace(old_run, run_block)


def build_db_py(port: int) -> str:
    """第 12 页的 lab/db.py：整段从页面代码块取，只把端口换成临时容器端口。"""
    blocks = instruction_blocks(12)
    src = next(b for b in blocks if "def query(sql: str)" in b)
    if "port=3307" not in src:
        raise RuntimeError("page-12.md 的 lab/db.py 里没找到约定端口 3307")
    src = src.replace("port=3307", f"port={port}")
    if "port=3307" in src:
        raise RuntimeError("lab/db.py 的端口没替换干净")
    return src


# ---------------------------------------------------------------- 镜像 / 容器 / 工作区


def preflight() -> tuple[int, Path]:
    missing = [tool for tool in ("docker", "google-chrome", "convert", "identify")
               if shutil.which(tool) is None]
    if missing:
        sys.exit(f"缺少依赖：{', '.join(missing)}（本脚本不装新依赖）")
    if not (REPO / "backend" / ".venv" / "bin" / "python").exists():
        sys.exit("system/backend/.venv 不存在；先按第 0 页准备好环境")

    inspect = subprocess.run(
        ["docker", "image", "inspect", MYSQL_IMAGE],
        capture_output=True, timeout=60,
    )
    if inspect.returncode != 0:
        sys.exit(f"本机没有 {MYSQL_IMAGE} 镜像；先 docker pull {MYSQL_IMAGE}")

    if CONTAINER in docker_names():
        say(f"发现上一轮残留的临时容器 {CONTAINER}，先删掉（脚本自己会清理，正常不应出现）")
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, timeout=60)

    port = next((p for p in PORT_CANDIDATES if not port_open(p)), None)
    if port is None:
        sys.exit(
            f"端口 {'/'.join(map(str, PORT_CANDIDATES))} 都被占用；"
            "本脚本不杀别人的进程，先停掉占用者再重跑。"
        )

    contract = (REPO / "contracts" / "schema.contract.yaml").read_text(encoding="utf-8")
    if EXPECTED_CONTRACT_ROWS not in contract:
        sys.exit("仓库契约不是 expected_fact_rows: 115，第 10 页对账的前提变了，先确认再重跑")
    for path in ("system/fixtures/dw.sql", "system/fixtures/dw-real.sql",
                 "system/fixtures/dw-real.checks.sql"):
        if not (REPO / path).is_file():
            sys.exit(f"缺少 {path}")

    IMAGES.mkdir(parents=True, exist_ok=True)
    return port, WORK


def prepare_workdir() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    ignore_pycache = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(REPO / "fixtures", WORK / "fixtures", ignore=ignore_pycache)
    shutil.copytree(REPO / "contracts", WORK / "contracts", ignore=ignore_pycache)
    shutil.copytree(REPO / "lab", WORK / "lab", ignore=ignore_pycache)

    (WORK / "scripts").mkdir()
    shutil.copy2(REPO / "scripts" / "lab", WORK / "scripts" / "lab")

    shutil.copytree(REPO / "backend" / "app", WORK / "backend" / "app",
                    ignore=ignore_pycache)
    shutil.copytree(REPO / "backend" / ".venv", WORK / "backend" / ".venv",
                    symlinks=True, ignore=ignore_pycache)

    (WORK / "docs").mkdir()
    shutil.copy2(REPO / "docs" / "SCHEMA-CONTRACT.md",
                 WORK / "docs" / "SCHEMA-CONTRACT.md")
    shutil.copy2(REPO / "compose.yaml", WORK / "compose.yaml")

    # 模拟学生进第 10 页时的状态：lab/app.py 是第 8 页那份。
    (WORK / "lab" / "app.py").write_text(tr.APP_PAGE_08, encoding="utf-8")
    (WORK / "lab" / "db.py").unlink(missing_ok=True)
    return WORK


def start_mysql(port: int) -> None:
    say(f"起临时 MySQL：容器 {CONTAINER}，127.0.0.1:{port} -> 3306（不碰 lab-mysql / 3307）")
    subprocess.run(
        ["docker", "run", "-d", "--name", CONTAINER,
         "-p", f"127.0.0.1:{port}:3306",
         "-e", "LANG=C.UTF-8",
         "-e", "MYSQL_ROOT_PASSWORD=labpass",
         # 第 1 页的 docker run 还建了 didilili 账号：system/fixtures/dw.sql 末尾有一句
         # GRANT 给这个账号，没有它就灌不进演示库（第 10 页拆一刀 3 要用）。
         "-e", "MYSQL_USER=didilili",
         "-e", "MYSQL_PASSWORD=labpass",
         MYSQL_IMAGE],
        check=True, capture_output=True, timeout=180,
    )
    t0 = time.monotonic()
    while time.monotonic() - t0 < 180:
        logs = subprocess.run(
            ["docker", "logs", CONTAINER], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        if "port: 3306" in (logs.stdout + logs.stderr):
            say(f"      → 就绪（{time.monotonic() - t0:.1f}s）")
            return
        time.sleep(2)
    raise RuntimeError("临时 MySQL 180 秒还没就绪")


# ---------------------------------------------------------------- 渲染


def chrome_screenshot(html_path: Path, png_path: Path, profile_dir: Path) -> None:
    png_path.unlink(missing_ok=True)
    cmd = [
        "google-chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--force-device-scale-factor={DEVICE_SCALE}",
        f"--window-size={WINDOW_W_CSS},{WINDOW_H_CSS}",
        f"--user-data-dir={profile_dir}",
        f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError(
            "chrome 截图失败：\n" + (proc.stderr or proc.stdout or "")[-4000:]
        )


def identify_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["identify", "-format", "%w %h", str(path)],
        check=True, capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    w, h = (int(x) for x in out.split())
    return w, h


def render_shot(work: Path, shot: dict, records: dict) -> Path:
    html_text = tr.build_html(shot["panes"], records)
    stem = Path(shot["file"]).stem
    html_path = work / f"{stem}.html"
    html_path.write_text(html_text, encoding="utf-8")

    raw = work / f"{stem}.raw.png"
    chrome_screenshot(html_path, raw, work / f"chrome-{stem}")
    raw_w, _ = identify_size(raw)
    if raw_w != WINDOW_W_CSS * DEVICE_SCALE:
        raise RuntimeError(f"截图宽 {raw_w}px，不是 {WINDOW_W_CSS * DEVICE_SCALE}px")

    trimmed = work / f"{stem}.trim.png"
    subprocess.run(
        ["convert", str(raw), "-trim", "+repage", str(trimmed)],
        check=True, capture_output=True, timeout=120,
    )
    w, h = identify_size(trimmed)
    target_h = max(h, MIN_PNG_H)
    target = IMAGES / shot["file"]
    subprocess.run(
        ["convert", str(trimmed), "-gravity", "center",
         "-background", PAGE_BG, "-extent", f"{WINDOW_W_CSS * DEVICE_SCALE}x{target_h}",
         str(target)],
        check=True, capture_output=True, timeout=120,
    )
    final_w, final_h = identify_size(target)
    if final_w != WINDOW_W_CSS * DEVICE_SCALE or final_h < MIN_PNG_H:
        raise RuntimeError(f"{target.name} 尺寸 {final_w}x{final_h} 不符合 @2x 约定")
    say(f"    🖼  {target.relative_to(REPO)}  {final_w}x{final_h}")
    return target


# ---------------------------------------------------------------- 图文一致性自检


def clean_lines(lines: list[str]) -> list[str]:
    """去掉空行，只保留有内容的行（页面样例块里也没有空行）。"""
    return [line.rstrip() for line in lines if line.strip()]


def compare_subsequence(expected: list[str], actual: list[str]) -> tuple[bool, str]:
    """页面块是真跑输出的节选：要求每行按顺序出现（中间可以省略真跑的行）。"""
    pos = 0
    missing = []
    for line in expected:
        try:
            pos = actual.index(line, pos) + 1
        except ValueError:
            missing.append(line)
    if missing:
        return False, "页面有、真跑里找不到：" + " / ".join(repr(x) for x in missing)
    return True, f"{len(expected)} 行按顺序都能在真跑输出（{len(actual)} 行）里找到"


def compare_ellipsis(expected: list[str], actual: list[str]) -> tuple[bool, str]:
    """页面块里有「…」：首段逐行相等 + 尾段逐行相等，中间省略。"""
    idx = next((i for i, line in enumerate(expected) if "…" in line), None)
    if idx is None:
        return compare_subsequence(expected, actual)
    head, tail = expected[:idx], expected[idx + 1:]
    problems = []
    if actual[:len(head)] != head:
        for i, (exp, got) in enumerate(zip(head, actual)):
            if exp != got:
                problems.append(f"首段第 {i + 1} 行：页面 {exp!r} ≠ 真跑 {got!r}")
    if tail and actual[-len(tail):] != tail:
        for i, exp in enumerate(tail):
            got = actual[len(actual) - len(tail) + i] if len(actual) >= len(tail) else None
            if exp != got:
                problems.append(f"尾段第 {i + 1} 行：页面 {exp!r} ≠ 真跑 {got!r}")
    if problems:
        return False, "；".join(problems)
    return True, f"首 {len(head)} 行 + 末 {len(tail)} 行一致（中间 {max(0, len(actual) - len(head) - len(tail))} 行页面用 … 省略）"


def compare_exact(expected: list[str], actual: list[str]) -> tuple[bool, str]:
    if actual == expected:
        return True, f"{len(expected)} 行逐行一致"
    problems = []
    for i in range(max(len(expected), len(actual))):
        exp = expected[i] if i < len(expected) else "<缺>"
        got = actual[i] if i < len(actual) else "<缺>"
        if exp != got:
            problems.append(f"第 {i + 1} 行：页面 {exp!r} ≠ 真跑 {got!r}")
            if len(problems) >= 5:
                problems.append("……")
                break
    return False, "；".join(problems)


def ocr_text(png: Path, work: Path) -> str:
    """把深色终端图反色后 OCR；没装 tesseract / PIL 就返回空串。

    tesseract 只有 eng 语言包：数字 / 英文关键字能扫出来，中文会变成乱码——
    中文部分靠渲染前的原文对账，OCR 只当独立抽检。`--psm 6`（统一文本块）和
    `--psm 11`（稀疏文本）各跑一次再合并：实测同一行 `S1 PASS` 在 psm 6 会被读成
    `$1 PASS`，psm 11 能读对，合并后抽检最稳。
    """
    if shutil.which("tesseract") is None:
        return ""
    try:
        from PIL import Image, ImageOps
    except Exception:  # noqa: BLE001
        return ""
    tmp = work / f"{png.stem}.ocr.png"
    with Image.open(png) as im:
        gray = ImageOps.invert(im.convert("L"))
        ImageOps.expand(gray, border=24, fill=255).save(tmp)
    try:
        chunks = []
        for psm in ("6", "11"):
            proc = subprocess.run(
                ["tesseract", str(tmp), "stdout", "--psm", psm],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180,
            )
            chunks.append(proc.stdout or "")
        return "\n".join(chunks)
    finally:
        tmp.unlink(missing_ok=True)


def squash(text: str) -> str:
    """OCR 对账用：只留字母/数字/点，避免空格和标点差异。"""
    return re.sub(r"[^0-9A-Za-z.]", "", text)


def check_forbidden(shot_texts: dict[str, list[str]]) -> list[str]:
    hits = []
    for name, lines in shot_texts.items():
        for needle in FORBIDDEN:
            if needle and any(needle in line for line in lines):
                hits.append(f"{name}: {needle!r}")
    return hits


# ---------------------------------------------------------------- 主流程


def main() -> int:
    t_start = time.monotonic()
    say("=" * 78)
    say("render_l2_pages.py —— 真跑 L2 第 10/11/12 页命令，生成 4 张终端运行截图")
    say(f"仓库：{REPO}")
    say(f"输出：{IMAGES.relative_to(REPO)}/page-10-checks.png 等 4 张"
        f"（宽 {WINDOW_W_CSS * DEVICE_SCALE}px，@2x，高 ≥{MIN_PNG_H}px）")
    say("=" * 78)

    port, _ = preflight()
    work: Path | None = None
    container_started = False
    records: dict[str, dict] = {}
    page11_trace: list[str] = []
    page11_restored: list[str] = []
    checks: list[dict] = []
    shot_texts: dict[str, list[str]] = {}
    ocr_results: dict[str, dict[str, bool]] = {}
    ocr_available = True
    extra_checks: list[str] = []

    try:
        work = prepare_workdir()
        say(f"临时工作区：{work}（页面相对路径都在这里跑，图里不出现绝对路径）")

        start_mysql(port)
        container_started = True

        # ================================================== 第 10 页
        section("第 10 页 · 换真数据（page-10.md）")
        run_quiet(work, CMD10_SAVE, timeout=180)
        run_quiet(work, CMD10_IMPORT_REAL, timeout=120)
        capture(work, records, "10_checks", CMD10_CHECKS, timeout=120)
        capture(work, records, "10_green", CMD_CHECK, timeout=120)

        contract_path = work / "contracts" / "schema.contract.yaml"
        contract_text = contract_path.read_text(encoding="utf-8")
        if contract_text.count(EXPECTED_CONTRACT_ROWS) != 1:
            raise RuntimeError("副本契约里 expected_fact_rows: 115 的写法与预期不一致")
        contract_path.write_text(
            contract_text.replace(EXPECTED_CONTRACT_ROWS, "  expected_fact_rows: 410"),
            encoding="utf-8",
        )
        say("    改副本契约：expected_fact_rows: 115 → 410（只改 /tmp 副本，仓库不动）")
        capture(work, records, "10_red", CMD_CHECK, timeout=120, allowed_codes=(1,))

        # 「拆一刀 2」：reset 把文件和契约还原，再跑 --check 回到绿。
        run_quiet(work, CMD10_RESET, timeout=180)
        restored_contract = contract_path.read_text(encoding="utf-8")
        if EXPECTED_CONTRACT_ROWS not in restored_contract:
            raise RuntimeError("reset 后契约没有回到 expected_fact_rows: 115")
        capture(work, records, "10_green_after_reset", CMD_CHECK, timeout=120)

        # 「拆一刀 3」：数据库不跟着 reset，确认还是 410，再重灌 dw.sql 回 115 行。
        count_lines, _ = run_quiet(work, CMD10_COUNT, timeout=60)
        if count_lines and count_lines[-1].strip() == "410":
            extra_checks.append("第 10 页拆一刀 3：reset 后 DB 仍是 410 行（与页面一致）")
        else:
            extra_checks.append(
                f"⚠️ 第 10 页拆一刀 3：reset 后 DB 行数不是 410：{count_lines!r}"
            )
        run_quiet(work, CMD10_IMPORT_DEMO, timeout=120)

        # ================================================== 第 11 页
        section("第 11 页 · 换真契约（page-11.md）")
        app11 = build_app_page11()
        (work / "lab" / "app.py").write_text(app11, encoding="utf-8")
        capture(work, records, "11_app", CMD11_APP, timeout=60)
        capture(work, records, "11_check", CMD_CHECK, timeout=120)

        # 「拆一刀」：改坏契约 → StopIteration 真报错 → reset 还原。只验日志，不上图。
        run_quiet(work, CMD11_SAVE, timeout=180)
        contract_path.write_text(
            contract_path.read_text(encoding="utf-8").replace(
                REGION_VALUES_LINE, REGION_VALUES_BROKEN, 1
            ),
            encoding="utf-8",
        )
        if REGION_VALUES_LINE in contract_path.read_text(encoding="utf-8"):
            raise RuntimeError("副本契约里 region_name 的 values 没改坏")
        page11_trace, trace_code = run_shell(
            exec_command(CMD11_APP), work, timeout=60, allowed_codes=(1,)
        )
        if trace_code != 1 or not page11_trace:
            extra_checks.append(f"⚠️ 第 11 页拆一刀：退出码 {trace_code}，与页面说的 1 不同")
        elif page11_trace[-1].strip() == "StopIteration":
            has_line48 = any(
                "line 48" in line and "build_sql" in line for line in page11_trace
            )
            extra_checks.append(
                "第 11 页拆一刀：真报 StopIteration、退出码 1"
                + ("，build_sql 行号 48 与页面一致" if has_line48
                   else "，但 traceback 行号不是 48")
            )
        else:
            extra_checks.append(
                f"⚠️ 第 11 页拆一刀：末行是 {page11_trace[-1]!r}，不是 StopIteration"
            )
        run_quiet(work, CMD11_RESET, timeout=180)
        page11_restored, _ = run_shell(exec_command(CMD11_APP), work, timeout=60)
        if page11_restored == records["11_app"]["lines"]:
            extra_checks.append("第 11 页拆一刀 3：reset 后 5 行 SQL 原样回来（与页面一致）")
        else:
            extra_checks.append("⚠️ 第 11 页拆一刀 3：reset 后 5 行 SQL 与改坏前不一致")

        # ================================================== 第 12 页
        section("第 12 页 · 换真执行器（page-12.md）")
        run_quiet(work, CMD12_IMPORT_REAL, timeout=120)
        (work / "lab" / "db.py").write_text(build_db_py(port), encoding="utf-8")
        say(f"    写入 lab/db.py（端口换成临时容器 {port}）")
        (work / "lab" / "app.py").write_text(build_app_page12(app11), encoding="utf-8")
        say("    写入第 12 页版 lab/app.py（run_sql 改走 db.query）")
        capture(work, records, "12_step3", CMD12_STEP3, timeout=60)
        capture(work, records, "12_selftest", CMD12_SELFTEST, timeout=120)

        if records["12_step3"]["lines"] != ["1000"]:
            extra_checks.append(
                f"⚠️ 第 12 页第 3 步接管验证回的是 {records['12_step3']['lines']!r}，页面说回 1000"
            )
        else:
            extra_checks.append("第 12 页第 3 步：执行器接管 app，回 1000（与页面一致）")

        # ================================================== 渲染
        section("渲染终端截图（真跑输出 → 深色终端版式）")
        shots = [
            {
                "file": "page-10-checks.png",
                "panes": [{
                    "title": "终端 · 第 10 页第 3 步：真数据对账"
                             "（system/fixtures/dw-real.checks.sql 的真跑输出）",
                    "items": [
                        {"step": "10_checks", "part": "cmd"},
                        {"step": "10_checks", "part": "out"},
                    ],
                }],
            },
            {
                "file": "page-10-gate.png",
                "panes": [
                    {
                        "title": "终端 · 第 4 步：换完真数据，门禁还是绿的"
                                 "（核对的仍是 system/fixtures/dw.sql 旧快照）",
                        "items": [
                            {"step": "10_green", "part": "cmd"},
                            {"step": "10_green", "part": "out"},
                        ],
                    },
                    {
                        "title": "终端 · 第 5 步：expected_fact_rows 改成 410 后，门禁红了",
                        "items": [
                            {"step": "10_red", "part": "cmd"},
                            {"step": "10_red", "part": "out"},
                        ],
                    },
                ],
            },
            {
                "file": "page-11-contract.png",
                "panes": [
                    {
                        "title": "终端 · 第 11 页：python -m lab.app 打出的 5 行 SQL"
                                 "（与第 6 页逐字一致）",
                        "items": [
                            {"step": "11_app", "part": "cmd"},
                            {"step": "11_app", "part": "out"},
                        ],
                    },
                    {
                        "title": "终端 · 契约门禁：S1 PASS"
                                 "（负向夹具、文档新鲜度两段都 PASS）",
                        "items": [
                            {"step": "11_check", "part": "cmd"},
                            {"step": "11_check", "part": "out"},
                        ],
                    },
                ],
            },
            {
                "file": "page-12-executor.png",
                "panes": [
                    {
                        "title": "终端 · 第 12 页第 3 步：执行器接管 app（回 1000 才算接上）",
                        "items": [
                            {"step": "12_step3", "part": "cmd"},
                            {"step": "12_step3", "part": "out"},
                        ],
                    },
                    {
                        "title": "终端 · 第 12 页第 4 步：python -m lab.db 自检"
                                 "（最后一项要等 5 秒）",
                        "items": [
                            {"step": "12_selftest", "part": "cmd"},
                            {"step": "12_selftest", "part": "out"},
                        ],
                    },
                ],
            },
        ]

        targets: list[Path] = []
        for shot in shots:
            targets.append(render_shot(work, shot, records))
            lines: list[str] = []
            for pane in shot["panes"]:
                for item in pane["items"]:
                    rec = records[item["step"]]
                    if item["part"] == "cmd":
                        lines.extend(rec["cmd"].split("\n"))
                    else:
                        lines.extend(rec["lines"])
            shot_texts[shot["file"]] = lines

        # ================================================== 图文一致性自检
        section("图文一致性自检（页面「你应该看到」↔ 真跑输出）")
        exp10 = expected_blocks(10)
        exp11 = expected_blocks(11)
        exp12 = expected_blocks(12)
        checks = [
            {"page": 10, "block": 2, "shot": "page-10-checks.png",
             "key": "10_checks", "mode": "subsequence"},
            {"page": 10, "block": 0, "shot": "page-10-gate.png",
             "key": "10_green", "mode": "subsequence"},
            {"page": 10, "block": 1, "shot": "page-10-gate.png",
             "key": "10_red", "mode": "exact"},
            {"page": 11, "block": 0, "shot": "page-11-contract.png",
             "key": "11_app", "mode": "exact"},
            {"page": 11, "block": 1, "shot": "page-11-contract.png",
             "key": "11_check", "mode": "ellipsis"},
            {"page": 12, "block": 0, "shot": "page-12-executor.png",
             "key": "12_selftest", "mode": "exact"},
        ]
        expected_by_page = {10: exp10, 11: exp11, 12: exp12}
        all_ok = True
        for item in checks:
            blocks = expected_by_page[item["page"]]
            if item["block"] >= len(blocks):
                say(f"  ⚠️  page-{item['page']}.md 找不到第 {item['block'] + 1} 个样例块")
                all_ok = False
                continue
            expected = blocks[item["block"]]
            actual = clean_lines(records[item["key"]]["lines"])
            if item["mode"] == "exact":
                ok, detail = compare_exact(expected, actual)
            elif item["mode"] == "ellipsis":
                ok, detail = compare_ellipsis(expected, actual)
            else:
                ok, detail = compare_subsequence(expected, actual)
            all_ok = all_ok and ok
            say(f"  {'✅' if ok else '⚠️ '} {item['shot']} ← page-{item['page']} 样例块 "
                f"{item['block'] + 1}（{item['mode']}）：{detail}")

        # 页面命令逐字检查：图里显示的命令必须真的出现在页面正文里
        say("")
        say("  页面命令逐字核对：")
        command_pairs = [
            (10, CMD10_SAVE), (10, CMD10_IMPORT_REAL), (10, CMD10_CHECKS),
            (10, CMD_CHECK), (10, CMD10_RESET), (10, CMD10_IMPORT_DEMO),
            (10, CMD10_COUNT), (11, CMD11_APP), (11, CMD_CHECK),
            (11, CMD11_SAVE), (11, CMD11_RESET),
            (12, CMD12_IMPORT_REAL), (12, CMD12_STEP3), (12, CMD12_SELFTEST),
        ]
        for page, cmd in command_pairs:
            if cmd in page_text(page):
                say(f"    ✅ page-{page}.md 含 {cmd}")
            else:
                say(f"    ⚠️  page-{page}.md 不含：{cmd}")
                all_ok = False

        # OCR：图里关键字（英文/数字）能不能真扫出来
        say("")
        say("  OCR 关键字抽检（对 PNG 反色后 tesseract）：")
        for name in (s["file"] for s in shots):
            png = IMAGES / name
            text = ocr_text(png, work)
            if not text:
                ocr_available = False
                say(f"    ⚠️  {name}：没有 tesseract/PIL，跳过 OCR（主对账已用渲染前原文完成）")
                continue
            flat = squash(text)
            result = {}
            for kw in OCR_KEYWORDS.get(name, []):
                result[kw] = squash(kw) in flat
            ocr_results[name] = result
            bad = [kw for kw, hit in result.items() if not hit]
            mark = "✅" if not bad else "⚠️ "
            say(f"    {mark} {name}：{len(result) - len(bad)}/{len(result)} 命中"
                + (f"，未命中 {bad}" if bad else ""))

        # 不许出现用户名 / 主机名 / 绝对路径
        say("")
        hits = check_forbidden(shot_texts)
        if hits:
            all_ok = False
            say(f"  ❌ 图内出现禁止字符串：{hits}")
        else:
            say(f"  ✅ 4 张图内容无用户名 / 主机名 / 绝对路径"
                f"（检查了 {', '.join(sorted(shot_texts))}）")

        # 输出汇总
        section("汇总")
        for page in (10, 11, 12):
            files = [s["file"] for s in shots if s["file"].startswith(f"page-{page}")]
            say(f"  page-{page}：{', '.join(files)}")
        say("")
        for target in targets:
            w, h = identify_size(target)
            say(f"  🖼  {target.relative_to(REPO)}  {w}x{h}  "
                f"（{target.stat().st_size / 1024:.0f} KB）")
        say("")
        say("  附加核对（只写日志，不上图）：")
        for line in extra_checks:
            say(f"    {line}")
        if page11_trace:
            say("    第 11 页拆一刀 traceback 末 3 行：")
            for line in page11_trace[-3:]:
                say(f"      {line}")
        say("")
        if not all_ok:
            say("⚠️  有页面样例与真跑输出不完全一致（见上面 ⚠️ 行）。")
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
        section("清理")
        if container_started or CONTAINER in docker_names():
            subprocess.run(["docker", "rm", "-f", CONTAINER],
                           capture_output=True, timeout=120)
        if work is not None and WORK.exists():
            shutil.rmtree(WORK, ignore_errors=True)
        if WORK.exists():
            say(f"  ⚠️  {WORK} 没删掉，请手动检查")
        else:
            say(f"  ✅ 临时工作区已删：{WORK}")
        if CONTAINER in docker_names():
            say(f"  ⚠️  容器 {CONTAINER} 还在，请手动检查")
        else:
            say(f"  ✅ 临时容器已删：{CONTAINER}（lab-mysql / 3307 未动）")


if __name__ == "__main__":
    sys.exit(main())
