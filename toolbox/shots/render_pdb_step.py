#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 教师/CI 夹具：不是学生入口；学生工具见 manual/appendix/gui-debugging.md
"""render_pdb_step.py —— 第 21 页补图：pdb 终端单步 + 前端 12 节点左右对照 GIF。

一条命令重跑（在仓库根目录）：

    python3 manual/shots/render_pdb_step.py

它做四件事：

1. **真 pdb 会话**：用 Python 标准库 pty 驱动
   `backend/.venv/bin/python -m pdb manual/shots/pdb_step_demo.py`，
   按固定命令序列在 6 个断点单步（断点行号见下），捕获完整会话
   （提示符 `(Pdb)` + 命令 + 源码行 + 变量值）。仓库绝对前缀归一成相对
   路径，去掉 ANSI；命令/输出本身不改。落盘
   `manual/review/pdb-step-transcript.txt`，并断言必含关键证据。
2. **左栏 12 节点时间轴**：12 个节点 id 来自 `contracts/steps.yaml`；
   脚本打印的 `=== NODE validate_sql ===` 等标记驱动高亮，左栏还有
   本次 4 步路径、触发条件、关键变量、当前断点、断点命令。
3. **右栏 pdb 终端**：transcript 从第一行开始逐行出现（每帧 1–2 行，
   等宽字体深色终端风），前半屏的命令/输出/源码行原样上屏。
4. **合成 GIF 并自检**：无头 Chrome 按 @2x 逐帧截图（1600px 宽），
   ffmpeg（palettegen + transdiff）合成 6–10s 循环；自检帧数/尺寸/大小/
   首中末帧差异/末帧 OCR/敏感串。ImageMagick 只用在 trim / compare / OCR 前处理。

断点行号（真实代码行，runbook 里有同样的命令序列）：

    backend/app/generate/guard.py:306          if violations:——拒绝分支
    backend/app/agent/correct.py:169           if corrector is None:（触发条件①）
    backend/app/agent/correct.py:176           if not error.retryable:（触发条件②）
    backend/app/agent/correct.py:183           if policy.max_attempts < 1:（触发条件③）
    backend/app/generate/provider.py:257       parse_model_payload 的 return
    backend/app/agent/validate.py:71           validate_sql 的 return None（二次校验通过）

常用参数：

    --capture-only   只重录 transcript，不渲染
    --render-only    用现有 transcript 只渲染
    --keep-frames    把全部帧留在 manual/review/pdb-step-frames/（默认只留首/中/末）

依赖（本机已装，不新装）：仓库 backend/.venv（Python 3.14）、google-chrome、
ffmpeg、ImageMagick convert/identify/compare、tesseract（只用了英文包）。
不启容器、不连 MySQL / ES / Qdrant / LLM、不读 .env。
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
from pathlib import Path

# ---------------------------------------------------------------- 常量

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"
REVIEW = REPO / "manual" / "review"
FRAMES = REVIEW / "pdb-step-frames"
TRANSCRIPT = REVIEW / "pdb-step-transcript.txt"
GIF = IMAGES / "page-21-pdb-step.gif"
DEMO = HERE / "pdb_step_demo.py"

PY = REPO / "backend" / ".venv" / "bin" / "python"

CSS_W = 800              # CSS 宽；@2x 截图 → 1600px（要求 1100–1600）
SCALE = 2
PAD = 10
LEFT_W = 272
GAP = 10
RIGHT_W = CSS_W - 2 * PAD - LEFT_W - GAP      # 498
TERM_FONT = 9.0          # 右栏等宽字号（CSS px；@2x = 18px 物理像素）
TERM_LH = 12.8           # 右栏行高（CSS px）
BASE_DELAY = 14          # GIF 每帧 14/100s
MIN_SECONDS = 6.0
MAX_SECONDS = 10.0
GIF_MAX_BYTES = 3_000_000

#: 12 个节点，id 与顺序逐字取自 `contracts/steps.yaml`。
NODES = [
    ("extract_keywords", "抽取关键词", "离线跳过"),
    ("recall_column", "召回字段信息", "离线跳过"),
    ("recall_value", "召回字段取值", "离线跳过"),
    ("recall_metric", "召回指标信息", "离线跳过"),
    ("merge_retrieved_info", "合并召回信息", "离线跳过"),
    ("filter_table", "过滤表信息", "离线跳过"),
    ("filter_metric", "过滤指标信息", "离线跳过"),
    ("add_extra_context", "添加额外上下文", "离线跳过"),
    ("generate_sql", "生成SQL", "假模型 → sql_before"),
    ("validate_sql", "校验SQL", "本次执行"),
    ("correct_sql", "校正SQL", "本次执行"),
    ("run_sql", "执行SQL", "本次执行"),
]

#: pdb 命令序列：每块对应一个断点停下的位置（真实会话，逐条敲）。
CAPTURE_BLOCKS = [
    # 0. 插断点 + 开跑（PYTHONPATH=backend，断点用 app/... 相对 sys.path 的路径）
    ["b app/generate/guard.py:306",
     "b app/agent/correct.py:169",
     "b app/agent/correct.py:176",
     "b app/agent/correct.py:183",
     "b app/generate/provider.py:257",
     "b app/agent/validate.py:71",
     "c"],
    # 1. guard.py:306 —— 拒绝分支（错误码/原因）
    ["p violations[0].code", "p violations[0].message",
     "up", "p sql_before", "down", "disable 1", "c"],
    # 2. correct.py:169 —— 有校正器吗？（第一次：None）
    ["p corrector", "c"],
    # 3. correct.py:169 —— fixture（不可重试错误只到 176 就被挡）
    ["p corrector.name", "n"],
    # 4. correct.py:176 —— error.retryable=False
    ["p error.code", "p error.retryable", "c"],
    # 5. correct.py:169 —— llm
    ["p corrector.name", "n"],
    # 6. correct.py:176 —— error.retryable=True
    ["p error.code", "p error.retryable", "n"],
    # 7. correct.py:183 —— 契约 max_attempts
    ["p policy.max_attempts", "p policy.revalidate",
     "up", "p attempts", "down", "n", "c"],
    # 8. provider.py:257 —— 假模型 JSON 文本经 parse_model_payload 后的 payload
    ["p list(payload)", "p payload['sql'][:48]", "c"],
    # 9. validate.py:71 —— 二次校验通过
    ["p report.ok", "up", "p attempts", "p sql_after", "down", "c"],
]

#: transcript 必须包含的证据（少一条就退出码 1）。
TRANSCRIPT_MUST = [
    "=== NODE validate_sql ===",
    "=== NODE correct_sql ===",
    "=== NODE run_sql ===",
    "(Pdb) p sql_before",
    "(Pdb) p violations[0].code",
    "(Pdb) p violations[0].message",
    "(Pdb) p corrector",
    "(Pdb) p error.code",
    "(Pdb) p error.retryable",
    "(Pdb) p policy.max_attempts",
    "(Pdb) p attempts",
    "(Pdb) p sql_after",
    "guard.py(306)check_sql()",
    "correct.py(169)propose_correction()",
    "correct.py(176)propose_correction()",
    "correct.py(183)propose_correction()",
    "provider.py(257)parse_model_payload()",
    "validate.py(71)validate_sql()",
    "SQL_UNKNOWN_COLUMN",
    "SQL_REJECTED 不可重试",
    "没有配置校正器",
    "attempted=False",
    "attempted=True",
    "max_attempts",
    "二次 validate_sql -> error=None",
]

# ---------------------------------------------------------------- 小工具


def say(msg: str = "") -> None:
    print(msg, flush=True)


def section(title: str) -> None:
    say("")
    say("=" * 68)
    say(title)
    say("=" * 68)


def run(cmd: list[str], timeout: float = 300.0, **kw) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    if proc.returncode != 0:
        raise RuntimeError(
            f"命令失败（{proc.returncode}）：{' '.join(cmd[:4])} …\n"
            f"{(proc.stderr or proc.stdout or '')[-3000:]}"
        )
    return proc


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- 1. 真 pdb 会话

PROMPT = b"(Pdb) "


def capture_pdb() -> str:
    """用 pty 真跑 `python -m pdb`，按命令序列捕获完整会话。"""
    section("1/5 真 pdb 会话：PTY 驱动 python -m pdb（6 个断点 / 固定命令序列）")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 120, 0, 0))
    env = dict(os.environ)
    env.update({
        "TERM": "dumb",
        "PYTHON_COLORS": "0",
        "NO_COLOR": "1",
        "COLUMNS": "120",
        "PYTHONPATH": str(REPO / "backend"),
    })
    proc = subprocess.Popen(
        [str(PY), "-m", "pdb", str(DEMO.relative_to(REPO))],
        stdin=slave, stdout=slave, stderr=slave,
        cwd=str(REPO), env=env, close_fds=True,
    )
    os.close(slave)
    raw = bytearray()

    def pump(timeout: float) -> None:
        ready, _, _ = select.select([master], [], [], timeout)
        if not ready:
            return
        try:
            chunk = os.read(master, 65536)
        except OSError:
            return
        if chunk:
            raw.extend(chunk)

    def wait_prompts(count: int, timeout: float = 120.0) -> None:
        deadline = time.time() + timeout
        while bytes(raw).count(PROMPT) < count:
            if time.time() > deadline:
                raise RuntimeError(
                    "pdb 会话超时（命令序列与断点对不上？）\n"
                    f"tail={bytes(raw)[-1200:]!r}"
                )
            pump(0.2)

    wait_prompts(1)
    total = 1
    for index, block in enumerate(CAPTURE_BLOCKS):
        for command in block:
            total += 1
            os.write(master, (command + "\n").encode())
            wait_prompts(total)
        say(f"    块 {index}：{len(block)} 条命令 OK")
    os.write(master, b"q\n")
    for _ in range(60):
        pump(0.1)
        if proc.poll() is not None:
            break
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError("pdb 退出超时")

    text = bytes(raw).decode("utf-8", "replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 仓库绝对前缀归一为相对路径；pdb 自己的 --Return--/traceback 里没有别的绝对路径。
    text = text.replace(str(REPO) + "/", "")
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip("\n") + "\n"
    say(f"    捕获 {len(text)} 字节 / {len(text.splitlines())} 行")
    return text


def check_transcript(text: str) -> None:
    section("2/5 校验 transcript：关键证据 / 相对路径 / 无敏感串")
    missing = [needle for needle in TRANSCRIPT_MUST if needle not in text]
    if missing:
        raise RuntimeError(f"transcript 缺证据：{missing}")
    say(f"    关键证据 {len(TRANSCRIPT_MUST)}/{len(TRANSCRIPT_MUST)} 全在")
    for bad in ("zhensirong", "/home/", "/Users/", "api_key", "API_KEY", "sk-"):
        if bad in text:
            raise RuntimeError(f"transcript 出现敏感串：{bad!r}")
    say("    无用户名 / 家目录 / key 串")
    if not text.splitlines()[0].startswith("> manual/shots/pdb_step_demo.py("):
        raise RuntimeError(f"首行不是相对路径的启动 banner：{text.splitlines()[0]!r}")
    say("    启动 banner 是相对路径（manual/shots/pdb_step_demo.py）")


def write_transcript(text: str) -> None:
    TRANSCRIPT.parent.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT.write_text(text, encoding="utf-8")
    say(f"    -> {TRANSCRIPT.relative_to(REPO)}  {len(text)} 字节")


# ---------------------------------------------------------------- 3. 帧状态机


def display_lines(text: str) -> list[str]:
    """上屏的行：从开跑的 `(Pdb) c` 到 `=== DONE`（启动 banner / 断点设置 /
    跑完的 restart 尾巴只在 transcript 里，不占 GIF 高度；断点在左栏列出）。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line == "=== NODE validate_sql ===":
            start = i - 1 if i > 0 and lines[i - 1].startswith("(Pdb) c") else i
            break
    if start is None:
        raise RuntimeError("transcript 里找不到 NODE 标记")
    end = None
    for j in range(start, len(lines)):
        if lines[j].startswith("=== DONE"):
            end = j
            break
    if end is None:
        raise RuntimeError("transcript 里找不到 DONE 标记")
    return lines[start:end + 1]


class State:
    """左栏状态：由“已上屏的前缀行”重算，保证每帧可复现。"""

    def __init__(self) -> None:
        self.validate = "pending"          # pending / active / err / ok
        self.correct = "pending"
        self.run = "pending"
        self.chips = ["pending"] * 4       # ①校验#1 ②校正 ③校验#2 ④执行
        self.validate_pass = 0
        self.corrector_names: list[str] = []
        self.error_pairs: list[tuple[str, str]] = []   # (code, retryable)
        self.max_attempts = ""
        self.revalidate = ""
        self.vars = {
            "sql_before": "",
            "error_code": "",
            "max_attempts": "",
            "attempts": "",
            "sql_after": "",
        }
        self.location = ""
        self.last_cmd = ""
        self.done = False
        self.reason = ""
        self.phase = ""                     # validate1 / correct / validate2 / run
        self.occurrence = 0
        self.last_error_code = ""           # 最近一次 p error.code（分支探针，不覆盖主错误码）

    def explain(self) -> tuple[str, list[str]]:
        """左栏「当前这一步在判什么」：随 NODE 标记切换。"""
        return {
            "": ("还没开始", [
                "敲 c 后 pdb 会停在第一个断点：guard 的拒绝分支。",
            ]),
            "validate1": ("validate_sql · guard 拒绝分支", [
                "<b>guard.check_sql</b> 逐条查：表/列在不在上下文、是否只读、投影是否常量。",
                "列不在上下文 → 返回带名字的违规（不抛异常），码 = SQL_UNKNOWN_COLUMN。",
                "<b>validate_sql</b> 把第一条违规变成 error：码 + 原因，交给校正。",
            ]),
            "correct": ("correct_sql · 三个触发条件", [
                "① 有没有校正器；② 错误是否 retryable；③ 契约 max_attempts ≥ 1。",
                "三条都满足才调用一次模型；假模型返回文本，仍走真 parse_model_payload。",
                "校正产物还要过 sql_or_refusal 契约校验，才交给二次校验。",
            ]),
            "validate2": ("validate_sql · 二次校验", [
                "校正后的 SQL 重新过 guard + policy（回边 correct_sql → validate_sql）。",
                "策略这一关不许写、不许多语句、不许出白名单——校正不是绕过检查的后门。",
                "返回 None = 通过，才允许进入 run_sql。",
            ]),
            "run": ("run_sql · 执行（边界）", [
                "本演示到此为止用假执行器，不连 MySQL；只证明代码路径走到这里。",
                "真实触发与真实结果见 review/correction-live-trigger.sse。",
            ]),
        }[self.phase]

    # -- 供左栏渲染 -------------------------------------------------------
    def vars_text(self) -> list[tuple[str, str]]:
        def short(value: str, limit: int = 44) -> str:
            value = value.strip("'")
            return value if len(value) <= limit else value[:limit] + "…"

        return [
            ("sql_before", short(self.vars["sql_before"])),
            ("error.code", self.vars["error_code"] or "—"),
            ("max_attempts", self.vars["max_attempts"] or "—"),
            ("attempts", self.vars["attempts"] or "—"),
            ("sql_after", short(self.vars["sql_after"])),
        ]

    def trigger_text(self) -> list[tuple[str, str, str]]:
        """(样式, 条件, 细节)；样式取 ok / err / dim。"""
        rows: list[tuple[str, str, str]] = []
        if self.corrector_names:
            rows.append(("ok", "① 有校正器", " / ".join(self.corrector_names)))
        else:
            rows.append(("err", "① 有校正器", "corrector=None"))
        if self.error_pairs:
            for code, retryable in self.error_pairs[-2:]:
                ok = retryable == "True"
                rows.append(("ok" if ok else "err", "② 错误可重试",
                             f"{code} → retryable={retryable}"))
        else:
            rows.append(("dim", "② 错误可重试", "—"))
        if self.max_attempts:
            rows.append(("ok" if self.max_attempts == "1" else "err",
                         "③ 契约允许", f"max_attempts={self.max_attempts}"))
        else:
            rows.append(("dim", "③ 契约允许", "—"))
        return rows


def advance(state: State, lines: list[str]) -> State:
    pending: str | None = None
    node_count = 0
    for line in lines:
        if line.startswith("(Pdb) "):
            cmd = line[len("(Pdb) "):].strip()
            state.last_cmd = cmd
            if cmd.startswith("p "):
                pending = cmd[2:].strip()
            else:
                pending = None
            continue
        if pending is not None:
            value = line.strip()
            expr = pending
            pending = None
            if expr == "violations[0].code":
                state.vars["error_code"] = value.strip("'")
                state.validate = "err"
                state.chips[0] = "err"
            elif expr == "violations[0].message":
                state.reason = value.strip("'")
            elif expr == "sql_before":
                state.vars["sql_before"] = value
            elif expr == "corrector":
                state.vars["error_code"] = state.vars["error_code"] or ""
            elif expr == "corrector.name":
                name = value.strip("'")
                if name and name not in state.corrector_names:
                    state.corrector_names.append(name)
            elif expr == "error.code":
                state.last_error_code = value.strip("'")
            elif expr == "error.retryable":
                code = state.last_error_code or state.vars["error_code"] or "?"
                pair = (code, value)
                if not state.error_pairs or state.error_pairs[-1] != pair:
                    state.error_pairs.append(pair)
            elif expr == "policy.max_attempts":
                state.max_attempts = value
                state.vars["max_attempts"] = value
            elif expr == "policy.revalidate":
                state.revalidate = value
            elif expr == "attempts":
                state.vars["attempts"] = value
            elif expr == "report.ok":
                if value == "True":
                    state.validate = "ok"
                    state.chips[2] = "ok"
            elif expr == "sql_after":
                state.vars["sql_after"] = value
            continue
        # -- 非 p 输出行 --------------------------------------------------
        if line.startswith("> "):
            state.location = line[2:].strip()
        elif line.startswith("=== NODE validate_sql ==="):
            node_count += 1
            state.occurrence += 1
            state.phase = "validate1" if state.occurrence == 1 else "validate2"
            state.validate = "active"
            state.chips[0] = "err" if state.vars["error_code"] else "active"
            if state.vars["error_code"]:
                state.chips[2] = "active" if state.correct == "ok" else "pending"
        elif line.startswith("=== NODE correct_sql ==="):
            state.phase = "correct"
            state.correct = "active"
            state.chips[1] = "active"
        elif line.startswith("=== NODE run_sql ==="):
            state.phase = "run"
            state.run = "active"
            state.chips[3] = "active"
        elif line.startswith("=== DONE"):
            state.done = True
            state.run = "ok"
            state.chips[3] = "ok"
            if state.validate == "ok":
                state.chips[2] = "ok"
        elif "触发条件①" in line:
            pass
        elif "触发条件②" in line:
            pass
        elif "触发条件③" in line:
            state.correct = "ok"
            state.chips[1] = "ok"
        elif line.startswith("契约 correction"):
            match = re.search(r"max_attempts=(\d+)", line)
            if match:
                state.max_attempts = match.group(1)
                state.vars["max_attempts"] = match.group(1)
        elif "二次 validate_sql -> error=None" in line:
            state.validate = "ok"
            state.chips[2] = "ok"
    return state


# 状态 -> 左栏展示
STATUS_STYLE = {
    "pending": ("○", "dim", "待执行"),
    "active": ("◉", "blue", "执行中"),
    "err": ("✗", "red", "拒绝"),
    "ok": ("✓", "green", "通过"),
}


#: 断点：(显示名, 真实源文件, 行号)。源码行在渲染时从仓库真文件里读，
#: 所以左栏的「行号 ↔ 源码行」永远和代码一致，不会手抄漂移。
BREAKPOINTS = [
    ("guard.py", "backend/app/generate/guard.py", 306),
    ("correct.py", "backend/app/agent/correct.py", 169),
    ("correct.py", "backend/app/agent/correct.py", 176),
    ("correct.py", "backend/app/agent/correct.py", 183),
    ("provider.py", "backend/app/generate/provider.py", 257),
    ("validate.py", "backend/app/agent/validate.py", 71),
]


def breakpoint_rows() -> list[tuple[str, int, str]]:
    rows = []
    for name, rel, lineno in BREAKPOINTS:
        path = REPO / rel
        try:
            code = path.read_text(encoding="utf-8").splitlines()[lineno - 1].strip()
        except (OSError, IndexError):
            code = "（源文件缺失）"
        rows.append((name, lineno, code))
    return rows


_SSE_CACHE: list[tuple[str, int, str] | None] | None = None


def sse_evidence() -> list[str]:
    """从真模型现场 SSE 里抽「四节点序列 + 关键耗时」，作为离线演示的诚实旁证。"""
    global _SSE_CACHE
    if _SSE_CACHE is None:
        import json
        path = REVIEW / "correction-live-trigger.sse"
        sequence: list[str] = []
        durations: dict[str, float] = {}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("data: "):
                    continue
                try:
                    payload = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if payload.get("type") != "progress":
                    continue
                step = str(payload.get("step"))
                status = str(payload.get("status"))
                if step in ("validate_sql", "correct_sql", "run_sql"):
                    sequence.append(f"{step}:{status}")
                    if status == "success" and payload.get("duration_ms") is not None:
                        durations[step] = float(payload["duration_ms"])
        except OSError:
            _SSE_CACHE = None
            return ["（缺 review/correction-live-trigger.sse）"]
        text = " → ".join(sequence) if sequence else "（SSE 里没有 SQL 节点事件）"
        detail = "correct_sql " + f"{durations.get('correct_sql', 0):.0f}ms"
        if "validate_sql" in durations:
            detail += f" · 二次 validate {durations['validate_sql']:.1f}ms"
        if "run_sql" in durations:
            detail += f" · run_sql {durations['run_sql']:.1f}ms"
        _SSE_CACHE = [text, detail, "真模型 deepseek-flash · 原版前端 · 隔离栈"]
    return [item for item in _SSE_CACHE if item is not None]


# ---------------------------------------------------------------- 4. HTML


def _load_term_render():
    """加载同目录的 term_render.py（只取它的 CSS 与 esc），保持深色终端风一致。"""
    import importlib.util
    path = HERE / "term_render.py"
    spec = importlib.util.spec_from_file_location("manual_term_render", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


try:
    _TR = _load_term_render()
    BASE_CSS = _TR.CSS            # term_render.py 的深色终端 CSS（颜色/字体/等宽）
    _tr_esc = _TR.esc
except Exception:                 # 单独搬运本文件时仍能跑（只少了基础配色）
    BASE_CSS = ""
    _tr_esc = None


LAYOUT_CSS = """
:root {
  --page: #04070b; --term: #0d1117; --bar: #161b22; --border: #21262d;
  --fg: #e6edf3; --dim: #8b949e; --green: #3fb950; --red: #f85149;
  --yellow: #d29922; --blue: #79c0ff; --purple: #d2a8ff; --cyan: #39c5cf;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--page); }
body { width: 800px; padding: 10px; }
.cols { display: flex; gap: 10px; align-items: stretch; }
.pane { border: 1px solid var(--border); border-radius: 10px;
        background: var(--term); overflow: hidden;
        display: flex; flex-direction: column; }
.left { width: 272px; flex: none; background: #0b0f14; }
.right { width: 498px; flex: none; }
.titlebar { background: var(--bar); color: var(--dim);
            padding: 6px 10px; border-bottom: 1px solid var(--border);
            font: 10.5px/1.35 "JetBrains Mono", "Noto Sans CJK SC", monospace;
            letter-spacing: 0.02em; flex: none; }
.titlebar b { color: var(--fg); font-weight: 700; }
.titlebar .tag { float: right; color: var(--blue); font-size: 8.6px; }

/* ---------------- 左栏 ---------------- */
.lbody { padding: 8px 9px; display: flex; flex-direction: column;
         gap: 6px; flex: 1;
         font-family: "JetBrains Mono", "Noto Sans CJK SC", monospace; }
.spacer { flex: 1; }
.sect { border: 1px solid #1c232b; border-radius: 6px; padding: 5px 7px 6px;
        background: #0d1218; }
.sect h4 { margin: 0 0 4px; color: var(--dim); font-size: 8.1px; font-weight: 700;
           letter-spacing: 0.06em; text-transform: uppercase; }
.tl { position: relative; padding-left: 11px; }
.tl:before { content: ""; position: absolute; left: 3px; top: 6px; bottom: 6px;
             width: 1px; background: #30363d; }
.tl-row { position: relative; display: flex; align-items: baseline; gap: 4px;
          font-size: 8.4px; line-height: 15.5px; color: var(--fg); white-space: nowrap; }
.tl-row .dot { position: absolute; left: -11px; width: 7px; text-align: center;
               font-size: 7px; color: #484f58; background: #0d1218; }
.tl-row .label { flex: none; }
.tl-row .id { flex: 1; color: #586069; font-size: 7.2px; overflow: hidden;
              text-overflow: ellipsis; }
.tl-row .st { flex: none; font-size: 7.4px; color: var(--dim); }
.tl-row.dim .label { color: #6e7681; }
.tl-row.active .label { color: var(--blue); }
.tl-row.err .label { color: var(--red); }
.tl-row.ok .label { color: var(--green); }
.st-red { color: var(--red) !important; }
.st-green { color: var(--green) !important; }
.st-blue { color: var(--blue) !important; }
.st-yellow { color: var(--yellow) !important; }
.st-dim { color: var(--dim) !important; }
.st-purple { color: var(--purple) !important; }

.path { display: flex; flex-direction: column; gap: 2px; }
.pbox { display: flex; align-items: center; gap: 6px; padding: 3px 5px;
        border: 1px solid #1c232b; border-radius: 5px; line-height: 1.25; }
.pbox .num { font-size: 10px; color: var(--dim); flex: none; }
.pbox .ptext { min-width: 0; }
.pbox .plabel { font-size: 8.4px; color: var(--fg); white-space: nowrap; }
.pbox .pnote { font-size: 7.4px; color: var(--dim); white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; }
.pbox.active { border-color: #2a4a6b; background: #101b28; }
.pbox.active .plabel { color: var(--blue); }
.pbox.ok { border-color: #1d3a26; }
.pbox.ok .pnote { color: var(--green); }
.pbox.err { border-color: #4a2222; }
.pbox.err .pnote { color: var(--red); }
.parrow { text-align: center; color: #30363d; font-size: 7px; line-height: 8px; }

.explain { font-size: 8px; line-height: 12.2px; color: var(--fg); }
.explain b { color: var(--cyan); font-weight: 700; }
.explain .dimline { color: var(--dim); }

.trig { font-size: 7.8px; line-height: 12.4px; color: var(--fg);
        overflow-wrap: anywhere; }
.trig .mk { display: inline-block; width: 8px; }
.trig .det { color: var(--dim); }
.kv { display: flex; gap: 5px; font-size: 7.7px; line-height: 12.2px; }
.kv .k { color: var(--dim); flex: none; width: 66px; }
.kv .v { color: var(--yellow); overflow-wrap: anywhere; }
.cur-box { font-size: 7.7px; line-height: 12.2px; }
.cur-box .loc { color: var(--blue); overflow-wrap: anywhere; }
.cur-box .cmd { color: var(--purple); white-space: nowrap; overflow: hidden;
                text-overflow: ellipsis; }
.bp { font-size: 7.4px; line-height: 12px; color: var(--dim); white-space: nowrap; }
.bp b { color: var(--fg); font-weight: 400; }
.srcbox { font-size: 7.2px; line-height: 12.4px; color: var(--dim); white-space: nowrap; }
.srcbox .file { color: var(--blue); }
.srcbox .ln { color: var(--yellow); }
.srcbox .code { color: var(--fg); }
.sseq { font-size: 7.2px; line-height: 12px; color: var(--fg); overflow-wrap: anywhere; }
.sseq .err { color: var(--red); }
.sseq .ok { color: var(--green); }
.ssed { font-size: 7.1px; line-height: 11.6px; color: var(--dim); }
.legend { font-size: 7.6px; line-height: 12px; color: var(--dim); }
.legend b { color: var(--purple); font-weight: 400; }
.legend .k2 { color: var(--fg); }
.proof { font-size: 7.6px; line-height: 12px; color: var(--fg); }
.proof .yes { color: var(--green); }
.proof .no { color: var(--dim); }
.foot { font-size: 7.2px; line-height: 10.8px; color: #6e7681; }
.foot b { color: var(--green); font-weight: 700; }

/* ---------------- 右栏终端 ---------------- */
.termbody { flex: 1; padding: 7px 10px; overflow: hidden; }
.ln { font-family: "JetBrains Mono", "DejaVu Sans Mono", "Noto Sans CJK SC", monospace;
      font-size: 9px; line-height: 12.7px; color: var(--fg);
      white-space: pre-wrap; overflow-wrap: anywhere; font-variant-ligatures: none; }
.ln.hl { background: #16202b; box-shadow: -6px 0 0 #16202b; }
.cursor { color: var(--green); }
.pr { color: var(--green); font-weight: 700; }
.cmd { color: var(--purple); }
.stop { color: var(--blue); }
.src { color: var(--cyan); }
.node { color: var(--yellow); font-weight: 700; }
.done { color: var(--green); font-weight: 700; }
.val { color: var(--yellow); }
.dim { color: var(--dim); }
.say { color: var(--green); }
"""
CSS = BASE_CSS + "\n/* ---- page-21-pdb-step：在本图追加 800px 两栏版式 ---- */\n" + LAYOUT_CSS


def esc(text: str) -> str:
    if _tr_esc is not None:
        return _tr_esc(text)
    return html.escape(text, quote=False)


def render_term_line(line: str, last: bool) -> str:
    cls = "ln hl" if last else "ln"
    if line.startswith("(Pdb) "):
        inner = f'<span class="pr">(Pdb)</span> <span class="cmd">{esc(line[6:])}</span>'
    elif line.startswith("> "):
        inner = f'<span class="stop">{esc(line)}</span>'
    elif line.startswith("-> "):
        inner = f'<span class="src">{esc(line)}</span>'
    elif line.startswith("=== NODE "):
        inner = f'<span class="node">{esc(line)}</span>'
    elif line.startswith("=== DONE"):
        inner = f'<span class="done">{esc(line)}</span>'
    elif line.startswith("Disabled breakpoint"):
        inner = f'<span class="dim">{esc(line)}</span>'
    elif line.startswith("'") or line.startswith("['"):
        inner = f'<span class="val">{esc(line)}</span>'
    elif line.startswith(("guard.check_sql", "首条违规", "validate_sql ->",
                          "契约 correction", "触发条件", "候选 sql_after",
                          "二次 validate_sql", "run_sql")):
        inner = f'<span class="say">{esc(line)}</span>'
    else:
        inner = esc(line)
    if last:
        inner += '<span class="cursor">▌</span>'
    return f'<div class="{cls}">{inner}</div>'


NODE_EXEC = {"validate_sql", "correct_sql", "run_sql"}


def node_status(state: State, node_id: str) -> tuple[str, str, str]:
    """(样式 class, 状态文本, 额外行内标记)"""
    status = {"validate_sql": state.validate,
              "correct_sql": state.correct,
              "run_sql": state.run}[node_id]
    if status == "pending":
        return "dim", "待执行", ""
    if status == "active":
        extra = ""
        if node_id == "validate_sql":
            extra = f"第{state.occurrence}次 "
        return "active", extra + "执行中", "◉"
    if status == "err":
        extra = "第1次 " if node_id == "validate_sql" else ""
        return "err", extra + "拒绝", "✗"
    extra = "第2次 " if node_id == "validate_sql" else ""
    return "ok", extra + "通过", "✓"


def status_icon(status: str) -> str:
    return {"pending": "○", "active": "◉", "err": "✗", "ok": "✓"}[status]


def path_note(index: int, state: State) -> str:
    status = state.chips[index]
    if status == "pending":
        return ["第一步校验：拒绝时才有校正", "最多一次：attempts 1/1",
                "校正后重跑 guard + policy", "策略过了才执行"][index]
    if status == "active":
        return "执行中…"
    if status == "err":
        if index == 0:
            return f"拒绝（{state.vars['error_code']}）"
        return "失败"
    if index == 0:
        return "通过"
    if index == 1:
        return "候选已给出（attempts 1/1）"
    if index == 2:
        return "error=None"
    return "假执行器返回 1 行"


def build_html(lines: list[str], state: State, height_css: int | None) -> str:
    body_height = f"height:{height_css}px;" if height_css else ""
    cols_height = f"height:{height_css - 2 * PAD}px;" if height_css else ""

    # -------- 12 节点时间轴
    tl_rows = []
    for node_id, label, note in NODES:
        if node_id in NODE_EXEC:
            cls, text, icon = node_status(state, node_id)
            row_cls = cls
            icon_cls = {"dim": "st-dim", "active": "st-blue", "err": "st-red",
                        "ok": "st-green"}[cls]
            st = (f'<span class="st {icon_cls}">{icon} {esc(text)}</span>')
            label_cls = ""
        else:
            row_cls = "dim"
            icon_cls = "st-dim"
            icon = "○" if node_id != "generate_sql" else "◇"
            st = f'<span class="st st-dim">{esc(note)}</span>'
            label_cls = ""
        tl_rows.append(
            f'<div class="tl-row {row_cls}">'
            f'<span class="dot {icon_cls}">{icon}</span>'
            f'<span class="label">{esc(label)}</span>'
            f'<span class="id">{esc(node_id)}</span>{st}</div>'
        )

    # -------- 本次 4 步路径
    chip_defs = [
        ("①", "validate_sql #1"),
        ("②", "correct_sql"),
        ("③", "validate_sql #2"),
        ("④", "run_sql"),
    ]
    chips = []
    for idx, (num, label) in enumerate(chip_defs):
        status = state.chips[idx]
        cls = {"pending": "", "active": "active", "err": "err", "ok": "ok"}[status]
        icon_cls = {"pending": "st-dim", "active": "st-blue", "err": "st-red",
                    "ok": "st-green"}[status]
        chips.append(
            f'<div class="pbox {cls}"><span class="num {icon_cls}">'
            f'{status_icon(status)}</span><span class="ptext">'
            f'<span class="plabel">{num} {esc(label)}</span><br>'
            f'<span class="pnote">{esc(path_note(idx, state))}</span>'
            f'</span></div>'
        )

    # -------- 当前步骤说明
    title, explain_lines = state.explain()
    explain_html = f'<div class="explain"><b>{esc(title)}</b><br>' + "<br>".join(
        line.replace("<b>", '<b>') for line in explain_lines) + "</div>"

    # -------- 触发条件
    trig_rows = []
    for klass, cond, detail in state.trigger_text():
        icon = {"ok": "✓", "err": "✗", "dim": "—"}[klass]
        trig_rows.append(
            f'<div class="trig"><span class="mk st-{klass}">{icon}</span>'
            f'{esc(cond)} <span class="det">{esc(detail)}</span></div>'
        )

    # -------- 真模型现场 SSE（如实显示真跑序列，用作离线演示的旁证）
    sse_seq = sse_evidence()[0]
    sse_parts = []
    for token in sse_seq.split(" → "):
        if ":error" in token:
            sse_parts.append(f'<span class="err">{esc(token)}</span>')
        elif ":success" in token:
            sse_parts.append(f'<span class="ok">{esc(token)}</span>')
        else:
            sse_parts.append(f'<span class="dim">{esc(token)}</span>')
    sse_html = ('<span class="dim"> → </span>').join(sse_parts)

    # -------- 关键变量
    kvs = [f'<div class="kv"><span class="k">{esc(k)}</span>'
           f'<span class="v">{esc(v)}</span></div>' for k, v in state.vars_text()]

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body style="{body_height}">
<div class="cols" style="{cols_height}">
  <div class="pane left">
    <div class="titlebar"><b>左栏 · 12 节点时间轴</b><span class="tag">NODE 标记驱动</span></div>
    <div class="lbody">
      <div class="sect"><h4>12 节点时间轴（contracts/steps.yaml）</h4>
        <div class="tl">{''.join(tl_rows)}</div></div>
      <div class="sect"><h4>本次 pdb 路径（校正回边 4 步）</h4>
        <div class="path">{'<div class="parrow">↓</div>'.join(chips)}</div></div>
      <div class="sect"><h4>当前这一步在判什么</h4>{explain_html}</div>
      <div class="sect"><h4>校正触发条件（correct.py:169 / 176 / 183）</h4>
        {''.join(trig_rows)}</div>
      <div class="sect"><h4>关键变量（transcript 里的 p 命令）</h4>{''.join(kvs)}</div>
      <div class="sect"><h4>当前断点 / 上一条命令</h4>
        <div class="cur-box"><div class="loc">{esc(state.location or '（还没停下）')}</div>
        <div class="cmd">(Pdb) {esc(state.last_cmd or '—')}</div></div></div>
      <div class="sect"><h4>断点行号 ↔ 真实源码行</h4>
        {''.join(f'<div class="srcbox"><span class="file">{esc(name)}</span>:'
                 f'<span class="ln">{lineno}</span>  <span class="code">{esc(code)}</span></div>'
                 for name, lineno, code in breakpoint_rows())}</div>
      <div class="sect"><h4>怎么读右栏</h4>
        <div class="legend"><b>(Pdb) p x</b> 打印变量 · <b>n</b> 下一行 · <b>c</b> 到下个断点<br>
        <b>up / down</b> 切栈帧看调用方变量 · <b>&gt;</b> 停在哪 · <b>-&gt;</b> 下一行源码</div></div>
      <div class="sect"><h4>这段演示证明什么 / 不能证明什么</h4>
        <div class="proof"><span class="yes">✓</span> guard 拒绝给出错误码与原因<br>
        <span class="yes">✓</span> 三个触发条件都满足才 attempt 一次（attempts 1/1）<br>
        <span class="yes">✓</span> 候选 SQL 过真解析器 + 二次校验才执行<br>
        <span class="no">✗ 假模型 / 假数据库：不证明真模型一定会改对；真实触发证据见 SSE</span></div></div>
      <div class="sect"><h4>真模型现场（SSE 旁证）</h4>
        <div class="sseq">{sse_html}</div>
        <div class="ssed">{esc(sse_evidence()[1])}<br>{esc(sse_evidence()[2])}<br>
        见 review/correction-live-trigger.sse</div></div>
      <div class="spacer"></div>
      <div class="foot"><b>✓ 真代码路径</b> guard → validate_sql → correct_sql → validate_sql → run_sql；
        离线、不读 .env。<br>review/correction-live-trigger.sse 是真模型现场 27 帧</div>
    </div>
  </div>
  <div class="pane right">
    <div class="titlebar"><b>右栏 · pdb 单步终端</b><span class="tag">python -m pdb · 真实会话</span></div>
    <div class="termbody">{''.join(render_term_line(line, i == len(lines) - 1) for i, line in enumerate(lines))}</div>
  </div>
</div>
</body></html>
"""
    return html_doc


def chrome_shot(html_path: Path, png_path: Path, height_css: int,
                profile_dir: Path) -> None:
    png_path.unlink(missing_ok=True)
    cmd = [
        "google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
        "--hide-scrollbars", f"--force-device-scale-factor={SCALE}",
        f"--window-size={CSS_W},{height_css}",
        f"--user-data-dir={profile_dir}", f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError("chrome 截图失败：\n" + (proc.stderr or proc.stdout or "")[-3000:])


def image_size(path: Path) -> tuple[int, int]:
    out = run(["identify", "-format", "%w %h\n", str(path)]).stdout.strip()
    first = out.splitlines()[0].split()
    return int(first[0]), int(first[1])


# ---------------------------------------------------------------- 5. 渲染


def render_frames(work: Path, lines: list[str]) -> tuple[list[Path], list[int], int]:
    section("3/5 逐帧渲染：左栏 12 节点 + 右栏 pdb 终端（无头 Chrome @2x）")
    profile = work / "chrome-profile"
    profile.mkdir(exist_ok=True)

    # 3.1 先渲末帧量出总高（所有行都上屏），后续每帧同一画布尺寸
    final_html = work / "frame-final.html"
    trimmed = work / "final-trim.png"
    if trimmed.exists():
        say("    复用已测量的末帧高度")
    else:
        final_html.write_text(build_html(lines, advance(State(), lines), None),
                              encoding="utf-8")
        final_raw = work / "final-raw.png"
        chrome_shot(final_html, final_raw, 4200, profile)
        run(["convert", str(final_raw), "-trim", "+repage", str(trimmed)])
    _, content_h = image_size(trimmed)
    frame_h = content_h // SCALE + 2 * PAD + 2
    say(f"    末帧内容高 {content_h}px（@2x）→ 画布 {CSS_W}×{frame_h} CSS "
        f"= {CSS_W * SCALE}×{frame_h * SCALE}px")

    # 3.2 逐帧：每帧多 1–2 行；NODE 标记帧加长停顿
    frame_dir = work / "frames"
    frame_dir.mkdir(exist_ok=True)
    reveal = list(range(2, len(lines) + 2, 2))
    if reveal[-1] > len(lines):
        reveal[-1] = len(lines)
    paths: list[Path] = []
    delays: list[int] = []
    for index, count in enumerate(reveal):
        visible = lines[:count]
        state = advance(State(), visible)
        png_path = frame_dir / f"f{index:03d}.png"
        if not png_path.exists():
            html_path = frame_dir / f"f{index:03d}.html"
            html_path.write_text(build_html(visible, state, frame_h), encoding="utf-8")
            chrome_shot(html_path, png_path, frame_h, profile)
        paths.append(png_path)
        delay = BASE_DELAY
        new_lines = lines[max(0, count - 2):count]
        if any(line.startswith("=== NODE ") or line.startswith("=== DONE")
               for line in new_lines):
            delay = 27
        if index == 0:
            delay = 40
        delays.append(delay)
    # 末帧停留
    hold_frames = max(1, int(round(1.2 / (BASE_DELAY / 100.0))))
    for _ in range(hold_frames):
        paths.append(paths[-1])
        delays.append(BASE_DELAY)
    total = sum(delays) / 100.0
    say(f"    {len(reveal)} 帧 + 末帧停留 {hold_frames} 帧 → {len(paths)} 帧 / "
        f"{total:.2f}s")
    if not (MIN_SECONDS <= total <= MAX_SECONDS):
        raise RuntimeError(f"GIF 时长 {total:.2f}s 不在 {MIN_SECONDS}–{MAX_SECONDS}s")
    return paths, delays, frame_h


def compose_gif(work: Path, paths: list[Path], delays: list[int]) -> None:
    """用 ffmpeg（palettegen / transdiff）合成 GIF。

    为什么不用 ImageMagick 一条 convert 收尾：本图 60+ 帧 × 1600×2874 像素，
    Q16 像素缓存约 4.6MB/帧，叠起来会撞 IM 的 1GiB 内存/2GiB 磁盘配额
    （实测 convert 报 "cache resources exhausted"）；ffmpeg 逐帧流式处理，
    且 transdiff 只编码帧间差异，5 万像素级改动就能出 1MB 内的 GIF。
    """
    section("4/5 合成 GIF（ffmpeg palettegen + transdiff）+ 自检")
    seq_dir = work / "gifseq"
    shutil.rmtree(seq_dir, ignore_errors=True)
    seq_dir.mkdir()
    index = 0
    for path, delay in zip(paths, delays):
        repeat = max(1, int(round(delay / BASE_DELAY)))
        for _ in range(repeat):
            target = seq_dir / f"g{index:04d}.png"
            if not target.exists():
                try:
                    os.link(path, target)
                except OSError:
                    shutil.copyfile(path, target)
            index += 1
    fps = 100.0 / BASE_DELAY
    duration = index * BASE_DELAY / 100.0
    say(f"    帧序列 {index} 帧 × {BASE_DELAY}/100s（常量帧率 {fps:.3f}fps）"
        f" = {duration:.2f}s")
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", f"{fps:.6f}", "-i", str(seq_dir / "g%04d.png"),
        "-vf", "split[s0][s1];[s0]palettegen=max_colors=96:stats_mode=diff[p];"
               "[s1][p]paletteuse=dither=none",
        "-gifflags", "+transdiff", "-loop", "0", str(GIF),
    ], timeout=900)
    width, height = image_size(GIF)
    frames = int(run(["identify", "-format", "%n\n", str(GIF)]).stdout.splitlines()[0])
    size = GIF.stat().st_size
    delays_out = run(["identify", "-format", "%T\n", str(GIF)]).stdout.split()
    unique_delays = sorted({int(x) for x in delays_out if x.strip()})
    say(f"    -> {GIF.relative_to(REPO)}  {width}x{height}  {frames} 帧  "
        f"{size / 1024:.0f} KB  delay={unique_delays} (1/100s)")
    if not (1100 <= width <= 1600):
        raise RuntimeError(f"GIF 宽 {width}px 不在 1100–1600")
    if width != CSS_W * SCALE:
        raise RuntimeError(f"GIF 宽 {width}px ≠ 约定 {CSS_W * SCALE}px")
    if not (20 <= frames <= 120):
        raise RuntimeError(f"帧数 {frames} 不在 20–120")
    if size > GIF_MAX_BYTES:
        raise RuntimeError(f"GIF {size} 字节 > 上限 {GIF_MAX_BYTES}")
    if not (MIN_SECONDS <= duration <= MAX_SECONDS):
        raise RuntimeError(f"GIF 时长 {duration:.2f}s 不在 {MIN_SECONDS}–{MAX_SECONDS}s")
    if unique_delays != [BASE_DELAY]:
        raise RuntimeError(f"GIF 每帧 delay 不是常量 {BASE_DELAY}：{unique_delays}")


def verify(work: Path) -> None:
    section("5/5 证据自检：首/中/末帧差异 + OCR 关键词 + 敏感串")
    check_dir = work / "check"
    shutil.rmtree(check_dir, ignore_errors=True)
    check_dir.mkdir()
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(GIF),
         str(check_dir / "f%04d.png")], timeout=600)
    frames = sorted(check_dir.glob("f*.png"))
    if len(frames) < 5:
        raise RuntimeError("GIF 抽帧失败")
    first, mid, last = frames[0], frames[len(frames) // 3], frames[-1]

    def ae(a: Path, b: Path) -> int:
        proc = subprocess.run(["compare", "-metric", "AE", str(a), str(b), "null:"],
                              capture_output=True, text=True, timeout=180)
        raw = (proc.stderr or proc.stdout or "").strip().split()
        return int(float(raw[0])) if raw else -1

    ae_fl, ae_fm, ae_ml = ae(first, last), ae(first, mid), ae(mid, last)
    say(f"    compare -metric AE：首↔末 {ae_fl}  首↔中 {ae_fm}  中↔末 {ae_ml}")
    if min(ae_fl, ae_fm, ae_ml) <= 0:
        raise RuntimeError("首/中/末帧没有差异，GIF 没有动画")
    hashes = {sha256(path) for path in frames}
    say(f"    唯一画面数 {len(hashes)} / {len(frames)}")
    if len(hashes) < 5:
        raise RuntimeError("唯一画面不足 5 种")

    # 末帧 OCR：先放大 2 倍再识别（tesseract 只有英文包，按英文关键词验）
    ocr_src = work / "ocr-last.png"
    run(["convert", str(last), "-resize", "200%", "-colorspace", "Gray",
         "-contrast-stretch", "1%x1%", str(ocr_src)])
    ocr = run(["tesseract", str(ocr_src), "stdout", "--psm", "6"]).stdout
    (work / "ocr-last.txt").write_text(ocr, encoding="utf-8")
    flat = re.sub(r"\s+", " ", ocr)
    must = ["correct_sql", "SQL_UNKNOWN_COLUMN", "max_attempts", "validate_sql",
            "run_sql"]
    missing = [word for word in must if word not in flat]
    say(f"    末帧 OCR 关键词 {len(must) - len(missing)}/{len(must)} 命中"
        + (f"（缺 {missing}）" if missing else ""))
    if missing:
        raise RuntimeError(f"末帧 OCR 缺关键词 {missing}；OCR 全文见 {work / 'ocr-last.txt'}")
    for bad in ("zhensirong", "/home/"):
        if bad in ocr:
            raise RuntimeError(f"末帧 OCR 出现敏感串 {bad!r}")
    for tag, frame in (("首帧", first), ("中帧", mid)):
        extra_ocr = run(["tesseract", str(frame), "stdout", "--psm", "6"]).stdout
        for bad in ("zhensirong", "/home/"):
            if bad in extra_ocr:
                raise RuntimeError(f"{tag} OCR 出现敏感串 {bad!r}")

    FRAMES.mkdir(parents=True, exist_ok=True)
    for tag, frame in (("first", first), ("mid", mid), ("last", last)):
        shutil.copyfile(frame, FRAMES / f"{tag}.png")
        say(f"    -> {FRAMES.relative_to(REPO)}/{tag}.png  sha256={sha256(frame)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="pdb 终端单步 + 12 节点对照 GIF")
    parser.add_argument("--capture-only", action="store_true", help="只重录 transcript")
    parser.add_argument("--render-only", action="store_true", help="用现有 transcript 只渲染")
    parser.add_argument("--keep-frames", action="store_true", help="保留全部中间帧")
    parser.add_argument("--workdir", type=Path, default=None,
                        help="复用临时工作目录（调样式时省掉重渲染）")
    args = parser.parse_args()
    if not PY.exists():
        raise SystemExit(f"缺 {PY}（先按第 0 页 make install 生成 backend/.venv）")

    if args.workdir is not None:
        work = args.workdir
        work.mkdir(parents=True, exist_ok=True)
    else:
        work = Path(tempfile.mkdtemp(prefix="pdb-step-"))
    try:
        if args.render_only:
            if not TRANSCRIPT.exists():
                raise SystemExit(f"缺 {TRANSCRIPT}（先不带 --render-only 跑一次）")
            text = TRANSCRIPT.read_text(encoding="utf-8")
            check_transcript(text)
        else:
            text = capture_pdb()
            check_transcript(text)
            write_transcript(text)
            if args.capture_only:
                say("")
                say("--capture-only：只更新 transcript，未渲染 GIF")
                return 0
        lines = display_lines(text)
        say(f"    上屏 {len(lines)} 行（启动/断点设置/restart 尾巴不上屏）")
        paths, delays, _ = render_frames(work, lines)
        if args.keep_frames:
            FRAMES.mkdir(parents=True, exist_ok=True)
            for path in paths:
                if path == paths[-1] and (FRAMES / path.name).exists():
                    continue
                shutil.copyfile(path, FRAMES / path.name)
            say(f"    -> {FRAMES.relative_to(REPO)}/ 保留全部 {len(set(paths))} 帧")
        compose_gif(work, paths, delays)
        verify(work)
        section("完成")
        say(f"    transcript: manual/review/pdb-step-transcript.txt")
        say(f"    GIF:        {GIF.relative_to(REPO)}")
        return 0
    finally:
        if args.workdir is None:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
