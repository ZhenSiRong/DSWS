#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_exec_trace.py —— 把 trace_query.py 的左右两侧轨迹渲染成 GIF / 关键帧。

输入（由 trace_query.py 在 backend 容器里真跑产出）：

    manual/review/exec-trace.jsonl        SSE 事件 + sys.settrace 行级轨迹
    manual/review/exec-trace.meta.json    日期 / 模型 / 问法 / 耗时 / LLM 调用次数

输出：

    manual/images/page-17-exec-trace.gif  6–10s 循环，左 12 节点时间轴 / 右代码窗口
    manual/images/page-17-exec-trace.png  关键帧：correct_sql 执行行 + sql_before/error/attempts

一条命令重跑（仓库根目录）：

    python3 manual/shots/render_exec_trace.py

只做验证、不重新渲染：

    python3 manual/shots/render_exec_trace.py --verify-only

它做四件事：

1. **先验证原始轨迹**（不通过就不渲染）：`validate_sql:error` 在 `correct_sql`
   之前、`correct_sql` 只有一轮 running/success、其后有二次 `validate_sql:success`、
   `run_sql:success`、`result`；行级轨迹覆盖 ≥3 个文件；时间戳单调。
2. **排帧**：左栏按 SSE wall-clock 推进（12 节点谁 waiting/running/success/error/
   skipped、耗时、第几轮）；右栏按行级轨迹推进（当前文件/函数/行号、6 行代码窗口、
   关键局部变量、LLM 等待窗口）。真实里的 13s/11s 模型调用在 GIF 里按比例压缩，
   整条循环约 8.8s。
3. **渲染**：每帧拼一段深色终端风的 HTML（等宽字体、同 term_render.py 的配色），
   `google-chrome --headless --force-device-scale-factor=2` 截图（1200×800 CSS @2x），
   缩到 1600px 宽（1100–1600 宽 @2x），ImageMagick 合成 GIF（≤3MB，循环）。
4. **验证 GIF**：帧数/尺寸/字节数/循环时长；首/中/末帧像素差非 0；末帧 tesseract
   OCR 必须读出 `correct_sql` 与**本次真实的校验错误码**（从轨迹里读，不写死；
   本次是 `SQL_UNKNOWN_TABLE`——不是任务示例里的 `SQL_UNKNOWN_COLUMN`）；画面
   文本里不得出现用户名、绝对路径、API key、隔离端口；最后写
   `manual/review/exec-trace.render.json`。

不修改页面和判据；只读 contracts/ 与 backend 源码（代码窗口的原文从仓库读，
显示的是仓库相对路径，所以画面上没有 /home/…）。
"""

from __future__ import annotations

import argparse
import bisect
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------- 路径/常量

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
REVIEW = REPO / "manual" / "review"
IMAGES = REPO / "manual" / "images"

TRACE_PATH = REVIEW / "exec-trace.jsonl"
META_PATH = REVIEW / "exec-trace.meta.json"
RENDER_REPORT = REVIEW / "exec-trace.render.json"
GIF_PATH = IMAGES / "page-17-exec-trace.gif"
PNG_PATH = IMAGES / "page-17-exec-trace.png"

CSS_W, CSS_H = 1200, 800        # 页面逻辑尺寸（@2x 截图 → 2400×1600）
DEVICE_SCALE = 2
FINAL_WIDTH = 1600              # 最终 GIF 宽度（任务要求 1100–1600 宽 @2x）
GIF_TARGET_LOOP_CS = 880        # 目标循环 ≈ 8.8s（要求 6–10s）
GIF_MAX_BYTES = 3_000_000

CODE_WINDOW = 6                 # 右栏代码窗口行数
VAR_TRIM = 110                  # 变量表单行最多显示字符数
CODE_TRIM = 96                  # 代码行最多显示字符数

CHROME = "/usr/bin/google-chrome"

TARGET_FILES = (
    "backend/app/agent/graph.py",
    "backend/app/agent/correct.py",
    "backend/app/generate/guard.py",
    "backend/app/security/policy.py",
)

#: 12 个节点（顺序与 contracts/steps.yaml 一致）。
STEPS: list[dict[str, Any]] = []

#: 不想在画面里看到的字符串（验证用）。
FORBIDDEN_PATTERNS = ("/home/", "/Users/", "zhensirong", "13397", "19297",
                      "16397", "18197", "18097", "REBUILD_LLM_API_KEY",
                      "MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD")


def say(msg: str = "") -> None:
    print(msg, file=sys.stderr, flush=True)


def run(cmd: list[str], *, timeout: float = 180.0) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-3000:]
        raise RuntimeError(f"命令失败（{cmd[0]}）：\n{tail}")
    return proc


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- 读契约/源码

def load_steps() -> list[dict[str, Any]]:
    import yaml

    doc = yaml.safe_load((REPO / "contracts" / "steps.yaml").read_text(encoding="utf-8"))
    steps = []
    for index, step in enumerate(doc["steps"]):
        steps.append(
            {
                "index": index,
                "id": step["id"],
                "label": step.get("label", step["id"]),
                "conditional": bool(step.get("conditional", False)),
            }
        )
    if len(steps) != 12:
        raise RuntimeError(f"contracts/steps.yaml 应有 12 个节点，实际 {len(steps)}")
    return steps


def load_max_attempts() -> int:
    import yaml

    doc = yaml.safe_load((REPO / "contracts" / "errors.yaml").read_text(encoding="utf-8"))
    return int(doc["correction"]["max_attempts"])


def load_source(relative: str) -> list[str]:
    path = REPO / relative
    return path.read_text(encoding="utf-8").splitlines()


def read_env_api_key() -> str:
    """只为“轨迹里没有 key”这条断言读 .env；值绝不打印。"""
    env_path = REPO / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "REBUILD_LLM_API_KEY":
            return value.strip()
    return ""


# ---------------------------------------------------------------- 加载轨迹

@dataclass
class Trace:
    records: list[dict[str, Any]]
    meta: dict[str, Any]
    sse: list[dict[str, Any]]
    lines: list[dict[str, Any]]
    llm: list[dict[str, Any]]
    line_times: list[float] = field(default_factory=list)
    index_of: dict[int, int] = field(default_factory=dict)

    @classmethod
    def load(cls, trace_path: Path, meta_path: Path) -> "Trace":
        records = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        sse = [r for r in records if r["kind"] == "sse"]
        lines = [r for r in records if r["kind"] == "line"]
        llm = [r for r in records if r["kind"] == "llm"]
        line_times = [r["t"] for r in lines]
        index_of = {id(r): i for i, r in enumerate(records)}
        return cls(records, meta, sse, lines, llm, line_times, index_of)


def last_line_before(trace: Trace, t: float, predicate=None) -> dict[str, Any] | None:
    index = bisect.bisect_right(trace.line_times, t) - 1
    while index >= 0:
        record = trace.lines[index]
        if predicate is None or predicate(record):
            return record
        index -= 1
    return None


def last_line_between(trace: Trace, start: float, end: float) -> dict[str, Any] | None:
    return last_line_before(trace, end, predicate=lambda r: r["t"] >= start)


# ---------------------------------------------------------------- 验证原始轨迹

def verify_trace(trace: Trace, api_key: str) -> dict[str, Any]:
    records = trace.records
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    progress = [
        (index, r["event"])
        for index, r in enumerate(records)
        if r["kind"] == "sse" and r["event"].get("type") == "progress"
    ]
    sequence = [(event.get("step"), event.get("status")) for _, event in progress]

    def first_index(step: str, status: str, after: int = -1) -> int | None:
        for position, (s, st) in enumerate(sequence):
            if s == step and st == status and position > after:
                return position
        return None

    validate_error = first_index("validate_sql", "error")
    correct_running = first_index("correct_sql", "running")
    correct_success = first_index("correct_sql", "success")
    validate_success = (
        first_index("validate_sql", "success", after=correct_running)
        if correct_running is not None
        else None
    )
    run_success = first_index("run_sql", "success")
    result_index = next(
        (i for i, r in enumerate(records) if r["kind"] == "sse" and r["event"].get("type") == "result"),
        None,
    )

    check("validate_sql:error 出现", validate_error is not None, str(validate_error))
    check(
        "validate_sql:error 在 correct_sql:running 之前",
        validate_error is not None and correct_running is not None and validate_error < correct_running,
        f"error@{validate_error} / correct@{correct_running}",
    )
    check("correct_sql 只 1 轮 running", sequence.count(("correct_sql", "running")) == 1,
          f"{sequence.count(('correct_sql', 'running'))} 轮")
    check("correct_sql 只 1 轮 success", sequence.count(("correct_sql", "success")) == 1,
          f"{sequence.count(('correct_sql', 'success'))} 轮")
    check("correct_sql 没有 error", sequence.count(("correct_sql", "error")) == 0)
    check("二次 validate_sql:success（校正后重新校验）", validate_success is not None,
          f"@{validate_success}")
    check("run_sql:success 出现", run_success is not None, f"@{run_success}")
    check("result 事件出现", result_index is not None,
          f"@{result_index}")
    check(
        "result 在 run_sql:success 之后",
        result_index is not None and run_success is not None and result_index > run_success,
    )

    line_files = sorted({r["file"] for r in trace.lines})
    check("行级轨迹覆盖 ≥3 个文件", len(line_files) >= 3, ", ".join(line_files))
    check(
        "4 个目标文件都被追到",
        set(line_files) == set(TARGET_FILES),
        ", ".join(line_files),
    )
    stamps = [r["t"] for r in records]
    monotonic = all(b >= a for a, b in zip(stamps, stamps[1:]))
    check("时间戳单调不减", monotonic)
    check("JSONL ≤ 500KB", len(TRACE_PATH.read_bytes()) <= 512 * 1024,
          f"{len(TRACE_PATH.read_bytes())} B")

    raw_text = TRACE_PATH.read_text(encoding="utf-8", errors="ignore")
    check("轨迹里没有 API key", not api_key or api_key not in raw_text)
    check("轨迹里没有绝对路径 / 用户名",
          not any(p in raw_text for p in ("/home/", "/Users/", "zhensirong")))

    meta_checks = {
        "meta 有 model": bool(trace.meta.get("model")),
        "meta 有问法": bool(trace.meta.get("query")),
        "meta 有事件数": isinstance(trace.meta.get("event_count"), int),
        "meta 有耗时": trace.meta.get("wall_clock_s") is not None,
        "meta 有 LLM 调用次数": isinstance(trace.meta.get("llm_calls"), int),
    }
    for name, ok in meta_checks.items():
        check(name, ok)

    failed = [item for item in checks if not item["ok"]]
    return {
        "checks": checks,
        "passed": len(checks) - len(failed),
        "total": len(checks),
        "failed": failed,
        "sequence": [f"{s}:{st}" for s, st in sequence],
        "line_files": line_files,
        "line_event_count": len(trace.lines),
    }


# ---------------------------------------------------------------- 帧计划

@dataclass
class Frame:
    #: 右栏代码窗口对应的行记录时间（wall clock）
    real_t: float
    #: 左栏 SSE 时间轴用的时间：节点跑在 LangGraph 工作线程里，SSE 事件由
    #: 主线程消费，两者有毫秒级先后差；左栏必须按 SSE 事件推进，不能拿
    #: 行事件时间反查，否则会出现“右边在跑 correct.py、左边还红着”的错位。
    left_t: float
    right: dict[str, Any] | None
    phase: str
    delay_cs: int = 20
    badge: str = ""
    keyframe: bool = False


def sample(records: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if not records or count <= 0:
        return []
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for record in records:
        key = (record["file"], record["lineno"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    if len(unique) <= count:
        return unique
    if count == 1:
        return [unique[0]]
    picks: list[dict[str, Any]] = []
    used: set[tuple[str, int]] = set()
    for i in range(count):
        position = round(i * (len(unique) - 1) / (count - 1))
        candidate = unique[position]
        key = (candidate["file"], candidate["lineno"])
        if key in used:
            continue
        used.add(key)
        picks.append(candidate)
    return picks


def build_frames(trace: Trace) -> list[Frame]:
    """左侧按 SSE 时间轴排帧，右侧取该阶段的行级轨迹快照。"""
    records = trace.records
    sse = trace.sse
    lines = trace.lines

    def event_time(step: str, status: str, after: float = -1e18) -> float | None:
        for record in sse:
            event = record["event"]
            if (
                event.get("type") == "progress"
                and event.get("step") == step
                and event.get("status") == status
                and record["t"] >= after
            ):
                return record["t"]
        return None

    def llm_window(role: str) -> tuple[float, float] | None:
        start = end = None
        for record in trace.llm:
            if record.get("role") != role:
                continue
            if record.get("event") == "start" and start is None:
                start = record["t"]
            if record.get("event") == "end" and start is not None:
                end = record["t"]
                break
        if start is None:
            return None
        return start, (end if end is not None else start + 1.0)

    context_first = sse[0]["t"] if sse else records[0]["t"]
    start_t = records[0]["t"]
    gen_run = event_time("generate_sql", "running")
    gen_ok = event_time("generate_sql", "success")
    val1_run = event_time("validate_sql", "running")
    val1_err = event_time("validate_sql", "error")
    corr_run = event_time("correct_sql", "running")
    corr_ok = event_time("correct_sql", "success")
    val2_run = event_time("validate_sql", "running", after=corr_run or -1e18)
    val2_ok = event_time("validate_sql", "success", after=corr_run or -1e18)
    run_run = event_time("run_sql", "running")
    run_ok = event_time("run_sql", "success")
    result_t = next(
        (r["t"] for r in records if r["kind"] == "sse" and r["event"].get("type") == "result"),
        records[-1]["t"],
    )
    llm_gen = llm_window("generate_sql")
    llm_corr = llm_window("correct_sql")

    frames: list[Frame] = []
    frames.append(Frame(start_t, start_t, None, "准备：进程内真跑一次问数", 28))

    # 0) 编译 12 节点图（graph.py build_agent_graph 的几行）
    build_lines = [r for r in lines if r["t"] < context_first]
    edge_lines = [r for r in build_lines if 436 <= r["lineno"] <= 456]
    for record in sample(edge_lines or build_lines, 1):
        frames.append(Frame(record["t"], start_t, record, "LangGraph：编译 12 节点图", 34))

    # 1) 8 个上下文节点：每个 success 事件一帧，右栏显示节点里真正执行的那一行
    for step in [s["id"] for s in STEPS[:8]]:
        moment = event_time(step, "success")
        if moment is None:
            continue
        right = last_line_before(
            trace, moment, predicate=lambda r: r.get("func") == "node"
        ) or last_line_before(trace, moment)
        frames.append(Frame(moment, moment, right, f"上下文节点 · {step}", 12))

    # 2) generate_sql：LLM 前的代码帧 + 模型等待帧
    gen_anchor = gen_run or context_first
    if gen_run and llm_gen:
        code_lines = [r for r in lines if gen_run - 0.05 <= r["t"] < llm_gen[0]]
        focus_lines = [
            r for r in code_lines
            if r.get("func") == "node" and 230 <= r["lineno"] <= 280
        ]
        for record in sample(focus_lines or code_lines, 2):
            frames.append(Frame(record["t"], gen_anchor, record,
                                "generate_sql：渲染提示词并调用模型", 26))
        wait_t = (llm_gen[0] + llm_gen[1]) / 2
        right = last_line_before(trace, llm_gen[0])
        frames.append(Frame(wait_t, wait_t, right, "generate_sql：等待模型返回", 80,
                            badge="LLM 调用 #1 进行中"))
    if gen_ok:
        frames.append(Frame(gen_ok, gen_ok, last_line_before(trace, gen_ok),
                            "generate_sql：success", 20))

    # 3) 第一次 validate_sql：guard.py / policy.py 的行级轨迹
    if val1_run and val1_err:
        code_lines = [r for r in lines if val1_run - 0.05 <= r["t"] < val1_err]
        focus_lines = [
            r for r in code_lines
            if r["file"].endswith(("guard.py", "policy.py"))
        ]
        main_flow = [
            r for r in focus_lines
            if r.get("func") in ("check_sql", "enforce", "validate_sql")
        ]
        for record in sample(main_flow or focus_lines or code_lines, 5):
            frames.append(Frame(record["t"], val1_run, record,
                                "validate_sql #1：静态校验 + 安全策略", 16))
        frames.append(Frame(last_line_before(trace, val1_err)["t"] if last_line_before(trace, val1_err) else val1_err,
                            val1_err, last_line_before(trace, val1_err),
                            "validate_sql #1：error（校验红叉）", 70))

    # 4) correct_sql：graph → correct.py → 提示词槽位 → 调模型
    if corr_run and llm_corr:
        code_lines = [r for r in lines if val1_err and val1_err <= r["t"] <= llm_corr[0]]
        focus_lines = [r for r in code_lines if r["file"].endswith("correct.py")]
        picks = sample(focus_lines or code_lines, 4)
        core = [r for r in focus_lines if 186 <= r["lineno"] <= 206]
        for record in core:
            if record["lineno"] in (191, 193) and record not in picks:
                picks.append(record)
        entry = next(
            (
                r for r in code_lines
                if r["file"].endswith("graph.py") and r.get("func") == "node"
            ),
            None,
        )
        if entry is not None and entry not in picks:
            picks.insert(0, entry)
        # 关键帧：correct.py 里 build_correct_slots/render_prompt/corrector.correct 附近
        key_candidates = [
            r for r in code_lines
            if r["file"].endswith("correct.py") and 186 <= r["lineno"] <= 206
        ]
        key_record = key_candidates[-1] if key_candidates else last_line_before(trace, llm_corr[0])
        if key_record is not None and key_record not in picks:
            picks.append(key_record)
            picks.sort(key=lambda r: r["t"])
        for record in picks:
            is_key = record is key_record
            frames.append(
                Frame(record["t"], corr_run, record,
                      "correct_sql：构造 7 个槽位 → 调校正模型", 22, keyframe=is_key)
            )
        wait_t = (llm_corr[0] + llm_corr[1]) / 2
        frames.append(Frame(wait_t, wait_t, last_line_before(trace, llm_corr[0]),
                            "correct_sql：等待模型改写 SQL", 82,
                            badge="LLM 调用 #2 进行中"))
    if corr_ok:
        frames.append(Frame(corr_ok, corr_ok, last_line_before(trace, corr_ok),
                            "correct_sql：success（候选 SQL 还没复查）", 22))
    if llm_corr and val2_run:
        code_lines = [
            r for r in lines
            if llm_corr[1] <= r["t"] < val2_run
            and (
                r["file"].endswith("correct.py")
                or (r["file"].endswith("graph.py") and 320 <= r["lineno"] <= 375)
            )
        ]
        for record in sample(code_lines, 2):
            frames.append(Frame(record["t"], corr_ok or record["t"], record,
                                "correct_sql：写回候选 SQL / attempts+1", 18))

    # 5) 第二次 validate_sql：校正后的候选重新过两道关
    if val2_run and val2_ok:
        code_lines = [r for r in lines if val2_run - 0.05 <= r["t"] < val2_ok]
        focus_lines = [
            r for r in code_lines
            if r["file"].endswith(("guard.py", "policy.py"))
        ]
        main_flow = [
            r for r in focus_lines
            if r.get("func") in ("check_sql", "enforce")
        ]
        for record in sample(main_flow or focus_lines or code_lines, 4):
            frames.append(Frame(record["t"], val2_run, record,
                                "validate_sql #2：候选 SQL 重新过两道关", 15))
        frames.append(Frame(last_line_before(trace, val2_ok)["t"] if last_line_before(trace, val2_ok) else val2_ok,
                            val2_ok, last_line_before(trace, val2_ok),
                            "validate_sql #2：success（候选通过）", 20))

    # 6) run_sql + result
    if run_run and run_ok:
        code_lines = [r for r in lines if run_run - 0.05 <= r["t"] < run_ok]
        focus_lines = [
            r for r in code_lines
            if r.get("func") == "node" and 375 <= r["lineno"] <= 410
        ]
        for record in sample(focus_lines or code_lines, 2):
            frames.append(Frame(record["t"], run_run, record,
                                "run_sql：只读执行器执行策略产物", 20))
        frames.append(Frame(last_line_before(trace, run_ok)["t"] if last_line_before(trace, run_ok) else run_ok,
                            run_ok, last_line_before(trace, run_ok), "run_sql：success", 22))
    frames.append(Frame(result_t, result_t, last_line_before(trace, result_t),
                        "完成：result（本次单次采样结束）", 95))

    # 左栏时间轴必须单调；右栏取的是该阶段的行快照，天然按阶段推进。
    for previous, later in zip(frames, frames[1:]):
        if later.left_t < previous.left_t - 1e-6:
            raise RuntimeError(
                f"帧计划左栏时间轴不单调：{previous.phase} {previous.left_t} > {later.phase} {later.left_t}"
            )
    normalize_delays(frames)
    return frames


def normalize_delays(frames: list[Frame]) -> None:
    total = sum(max(10, frame.delay_cs) for frame in frames)
    if total <= 0:
        return
    scale = GIF_TARGET_LOOP_CS / total
    for frame in frames:
        frame.delay_cs = max(10, int(round(frame.delay_cs * scale / 5.0)) * 5)
    total = sum(frame.delay_cs for frame in frames)
    # 四舍五入后可能偏离目标，逐帧微调回 [6.0s, 10.0s]
    while total > 980:
        for frame in frames:
            if total <= 900:
                break
            if frame.delay_cs > 10:
                frame.delay_cs -= 5
                total -= 5
    while total < 620:
        for frame in frames:
            if total >= 700:
                break
            frame.delay_cs += 5
            total += 5


# ---------------------------------------------------------------- 状态快照

def status_at(trace: Trace, t: float) -> dict[str, Any]:
    status = {step["id"]: "waiting" for step in STEPS}
    runs = {step["id"]: 0 for step in STEPS}
    durations: dict[str, float] = {}
    active: tuple[str, str] | None = None
    count = 0
    for record in trace.sse:
        if record["t"] > t:
            break
        event = record["event"]
        if event.get("type") == "progress":
            count += 1
            step = event.get("step")
            state = event.get("status")
            if step not in status:
                continue
            if state == "running":
                runs[step] += 1
            status[step] = state
            if event.get("duration_ms") is not None:
                durations[step] = float(event["duration_ms"])
            active = (step, state)
        elif event.get("type") in ("result", "error"):
            count += 1
            active = (None, event.get("type"))  # type: ignore[arg-type]
    return {
        "status": status,
        "runs": runs,
        "durations": durations,
        "active": active,
        "count": count,
        "total": len(trace.sse),
    }


PLACEHOLDER_VALUES = {"None", "null", "True", "False", ""}


def _usable(value: str | None) -> bool:
    return bool(value) and value not in PLACEHOLDER_VALUES and not value.startswith("None:")


def merged_vars(trace: Trace, upto_index: int) -> dict[str, str]:
    values: dict[str, str] = {}
    for record in trace.records[: upto_index + 1]:
        if record["kind"] == "llm" and record.get("event") == "start":
            if record.get("prompt_preview"):
                values["prompt"] = record["prompt_preview"]
            continue
        if record["kind"] != "line":
            continue
        for name, value in (record.get("vars") or {}).items():
            if name == "state" and isinstance(value, dict):
                if "sql" in value:
                    values["sql"] = str(value["sql"])
                if "attempts" in value:
                    values["attempts"] = str(value["attempts"])
                if "corrected_sql" in value:
                    values["corrected_sql"] = str(value["corrected_sql"])
                if value.get("failure") is not None and _usable(str(value["failure"])):
                    values["error"] = str(value["failure"])
                continue
            if name == "failure":
                if _usable(str(value)):
                    values["error"] = str(value)
                continue
            if _usable(str(value)):
                values[name] = str(value)
    return values


def evidence_at(trace: Trace, t: float, error_code: str) -> list[dict[str, str]]:
    progress = [
        (record, record["event"]) for record in trace.sse
        if record["event"].get("type") == "progress" and record["t"] <= t
    ]
    sequence = [(event.get("step"), event.get("status")) for _, event in progress]
    chips: list[dict[str, str]] = []
    if ("validate_sql", "error") in sequence:
        chips.append({"text": f"validate#1: {error_code or 'error'}", "tone": "bad"})
    if ("correct_sql", "success") in sequence:
        chips.append({"text": "correct_sql: success ×1", "tone": "good"})
    if ("validate_sql", "success") in sequence:
        chips.append({"text": "validate#2: success", "tone": "good"})
    if ("run_sql", "success") in sequence:
        chips.append({"text": "run_sql: success", "tone": "good"})
    if any(record["event"].get("type") == "result" for record, _ in progress):
        rows = trace.meta.get("result", {}).get("row_count")
        chips.append({"text": f"result: {rows} rows", "tone": "good"})
    return chips


# ---------------------------------------------------------------- HTML 渲染

CSS = """
:root {
  --page-bg: #04070b;
  --term-bg: #0d1117;
  --panel:   #0d1117;
  --bar:     #161b22;
  --border:  #21262d;
  --fg:      #e6edf3;
  --dim:     #8b949e;
  --faint:   #484f58;
  --green:   #3fb950;
  --red:     #f85149;
  --yellow:  #d29922;
  --blue:    #79c0ff;
  --purple:  #d2a8ff;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--page-bg); }
body { width: 1200px; height: 800px; overflow: hidden;
       font-family: "JetBrains Mono", "DejaVu Sans Mono", "Noto Sans CJK SC", monospace;
       color: var(--fg); }
.frame { width: 1200px; height: 800px; padding: 16px 18px 14px 18px; }
.top { display: flex; align-items: baseline; justify-content: space-between;
       border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-bottom: 12px; }
.title { font-size: 21px; font-weight: 700; letter-spacing: 0.02em; }
.title .sub { font-size: 13px; color: var(--dim); font-weight: 400; margin-left: 10px; }
.meta { font-size: 12px; color: var(--dim); text-align: right; line-height: 1.5; }
.cols { display: flex; gap: 14px; height: 686px; }
.panel { background: var(--panel); border: 1px solid var(--border);
         border-radius: 10px; overflow: hidden; }
.left { width: 404px; display: flex; flex-direction: column; }
.right { width: 746px; display: flex; flex-direction: column; }
.panel-head { background: var(--bar); border-bottom: 1px solid var(--border);
              color: var(--dim); font-size: 12px; padding: 7px 12px;
              display: flex; justify-content: space-between; letter-spacing: 0.02em; }
.panel-head b { color: var(--fg); font-weight: 600; }
.nodes { padding: 7px 8px 4px 8px; flex: 1; }
.node { display: flex; align-items: center; gap: 8px; height: 38px;
        padding: 0 8px; border-radius: 7px; border: 1px solid transparent;
        font-size: 12px; color: var(--dim); }
.node.active { border-color: var(--yellow); background: rgba(210,153,34,0.10); }
.node.success .step { color: var(--green); }
.node.error .step { color: var(--red); }
.node.running .step { color: var(--yellow); }
.node.skipped .step { color: var(--faint); }
.node.waiting .step { color: var(--faint); }
.icon { width: 16px; text-align: center; font-size: 13px; }
.node.success .icon { color: var(--green); }
.node.error .icon { color: var(--red); }
.node.running .icon { color: var(--yellow); }
.node.skipped .icon { color: var(--faint); }
.node.waiting .icon { color: var(--faint); }
.step { width: 176px; font-weight: 600; color: #a5b3c9; }
.label { flex: 1; color: var(--dim); font-size: 11px; }
.dur { color: var(--dim); font-size: 11px; min-width: 44px; text-align: right; }
.badge { color: var(--purple); font-size: 10px; border: 1px solid var(--border);
         border-radius: 6px; padding: 1px 4px; }
.left-foot { border-top: 1px solid var(--border); padding: 8px 12px;
             font-size: 11px; color: var(--dim); line-height: 1.6; }
.left-foot b { color: var(--fg); font-weight: 600; }
.caption { color: var(--yellow); }
.tab { display: flex; align-items: center; gap: 10px; background: var(--bar);
       border-bottom: 1px solid var(--border); padding: 7px 12px; font-size: 12px; }
.tab .file { color: var(--blue); }
.tab .fn { color: var(--purple); }
.tab .ln { color: var(--yellow); }
.tab .caller { margin-left: auto; color: var(--dim); font-size: 11px; }
.code { padding: 9px 0 7px 0; background: #0a0e14; }
.cl { display: flex; height: 25px; line-height: 25px; font-size: 13px;
      white-space: pre; overflow: hidden; }
.cl .no { width: 48px; text-align: right; padding-right: 12px; color: var(--faint);
          font-size: 11px; user-select: none; }
.cl .src { flex: 1; overflow: hidden; color: #c9d1d9; }
.cl.cur { background: rgba(210,153,34,0.16); border-left: 3px solid var(--yellow); }
.cl.cur .no { color: var(--yellow); }
.cl.cur .src { color: #ffe9b0; font-weight: 600; }
.placeholder { color: var(--faint); font-size: 12px; padding: 30px 12px; }
.vars { border-top: 1px solid var(--border); padding: 7px 12px 4px 12px; }
.vars-head { color: var(--dim); font-size: 11px; margin-bottom: 4px; letter-spacing: 0.02em; }
table.vt { width: 100%; border-collapse: collapse; table-layout: fixed; }
table.vt td { padding: 2px 0; vertical-align: top; font-size: 12px; line-height: 1.45; }
table.vt td.k { width: 96px; color: var(--purple); }
table.vt td.v { color: #d7e2ef; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
table.vt td.v.missing { color: var(--faint); }
.recent { border-top: 1px solid var(--border); padding: 6px 12px 4px 12px; }
.recent-head { color: var(--dim); font-size: 11px; margin-bottom: 3px; letter-spacing: 0.02em; }
.recent .row { display: flex; gap: 8px; font-size: 11.5px; line-height: 1.62;
               color: var(--faint); white-space: nowrap; overflow: hidden; }
.recent .row.new { color: #b7c5d8; }
.recent .loc { width: 176px; color: var(--blue); }
.recent .fn { width: 128px; color: var(--purple); }
.recent .src { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.evidence { border-top: 1px solid var(--border); padding: 7px 12px 5px 12px;
            display: flex; flex-wrap: wrap; gap: 6px; min-height: 42px; align-content: flex-start; }
.chip { font-size: 12px; border-radius: 999px; padding: 2px 10px; border: 1px solid; }
.chip.good { color: var(--green); border-color: rgba(63,185,80,0.45);
             background: rgba(63,185,80,0.10); }
.chip.bad { color: var(--red); border-color: rgba(248,81,73,0.45);
            background: rgba(248,81,73,0.10); }
.chip.pending { color: var(--faint); border-color: var(--border); }
.right-foot { margin-top: auto; border-top: 1px solid var(--border);
              color: var(--dim); font-size: 11px; padding: 7px 12px; line-height: 1.5;
              display: flex; justify-content: space-between; gap: 10px; }
.right-foot b { color: var(--fg); font-weight: 600; }
.llm { color: var(--yellow); }
"""

STATUS_ICONS = {
    "waiting": "○",
    "running": "◐",
    "success": "✓",
    "error": "✗",
    "skipped": "—",
}


def esc(text: Any) -> str:
    return html.escape(str(text), quote=False)


def trim_code(text: str, limit: int = CODE_TRIM) -> str:
    text = text.expandtabs(4)
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def fmt_duration(ms: float | None) -> str:
    if ms is None:
        return ""
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms:.0f}ms"


def recent_line_records(trace: Trace, upto_index: int, count: int = 6) -> list[dict[str, Any]]:
    """本帧之前最近执行过的 count 行（去重相邻重复），返回从旧到新。"""
    picked: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for record in reversed(trace.records[: upto_index + 1]):
        if record["kind"] != "line":
            continue
        key = (record["file"], record["lineno"])
        if key in seen:
            continue
        seen.add(key)
        picked.append(record)
        if len(picked) >= count:
            break
    picked.reverse()
    return picked


def render_html(
    trace: Trace,
    frame_index: int,
    frame: Frame,
    sources: dict[str, list[str]],
    max_attempts: int,
    error_code: str,
    loop_s: float,
) -> str:
    snapshot = status_at(trace, frame.left_t)
    right_index = trace.index_of.get(id(frame.right), -1) if frame.right else -1
    values = merged_vars(trace, right_index)
    chips = evidence_at(trace, frame.left_t, error_code)

    # ---- 左栏：12 节点
    node_rows: list[str] = []
    active_step = snapshot["active"][0] if snapshot["active"] else None
    for step in STEPS:
        state = snapshot["status"][step["id"]]
        runs = snapshot["runs"][step["id"]]
        duration = snapshot["durations"].get(step["id"])
        classes = ["node", state]
        if step["id"] == active_step:
            classes.append("active")
        badge = ""
        if runs >= 2:
            badge = f'<span class="badge">×{runs}</span>'
        node_rows.append(
            '<div class="%s"><span class="icon">%s</span>'
            '<span class="step">%s</span><span class="label">%s</span>%s'
            '<span class="dur">%s</span></div>'
            % (
                " ".join(classes),
                STATUS_ICONS[state],
                esc(step["id"]),
                esc(step["label"]),
                badge,
                esc(fmt_duration(duration)),
            )
        )

    active_text = "—"
    if snapshot["active"]:
        step, state = snapshot["active"]
        active_text = f"{step} · {state}" if step else f"流结束 · {state}"

    left_foot = (
        f'<div class="left-foot">'
        f'<div class="caption">当前：{esc(frame.phase)}</div>'
        f'<div>{esc(active_text)} ｜ SSE {snapshot["count"]}/{snapshot["total"]}</div>'
        f'<div>真跑 {esc(trace.meta.get("model", ""))} · 单次采样 · {esc(trace.meta.get("wall_clock_s"))}s</div>'
        f'<div>GIF {loop_s:.1f}s 循环（时间压缩）· LLM×{trace.meta.get("llm_calls")}</div>'
        f'</div>'
    )

    # ---- 右栏：代码窗口
    if frame.right is None:
        tab = (
            '<div class="tab"><span class="file">backend/app/agent/graph.py</span>'
            '<span class="fn">build_agent_graph()</span>'
            '<span class="ln">等待第一条行事件</span></div>'
        )
        code_html = '<div class="placeholder">sys.settrace 已安装：等待解释器执行到 4 个目标文件…</div>'
        caller = ""
    else:
        relative = frame.right["file"]
        lineno = int(frame.right["lineno"])
        func = frame.right["func"]
        source = sources.get(relative, [])
        start = max(1, lineno - 2)
        end = min(len(source), start + CODE_WINDOW - 1)
        start = max(1, end - CODE_WINDOW + 1)
        rows = []
        for number in range(start, end + 1):
            text = trim_code(source[number - 1] if number - 1 < len(source) else "")
            css = "cl cur" if number == lineno else "cl"
            rows.append(
                f'<div class="{css}"><span class="no">{number}</span>'
                f'<span class="src">{esc(text)}</span></div>'
            )
        code_html = '<div class="code">' + "".join(rows) + "</div>"
        caller = (
            f'<span class="caller">← 调用自 {esc(frame.right.get("caller"))}</span>'
            if frame.right.get("caller")
            else ""
        )
        tab = (
            f'<div class="tab"><span class="file">{esc(relative)}</span>'
            f'<span class="fn">{esc(func)}()</span>'
            f'<span class="ln">L{lineno}</span>{caller}</div>'
        )

    # ---- 变量表
    sql_before = values.get("sql") or values.get("original_sql") or ""
    sql_after = values.get("corrected_sql") or ""
    error_text = values.get("error") or ""
    attempts = values.get("attempts") or "0"
    prompt_preview = values.get("prompt") or ""
    var_rows = [
        ("sql_before", sql_before, "（还没生成/还没捕获到 SQL）"),
        ("sql_after", sql_after, "（校正成功后才有）"),
        ("error", error_text, "（本帧之前没有 error 局部变量）"),
        ("attempts", f"{attempts} / max {max_attempts}", ""),
        ("prompt", prompt_preview, "（模型调用提示词，截断 ≤120 字符）"),
    ]
    var_html = []
    for name, value, missing in var_rows:
        if value:
            shown = value if len(value) <= VAR_TRIM else value[: VAR_TRIM - 1] + "…"
            var_html.append(
                f'<tr><td class="k">{esc(name)}</td><td class="v">{esc(shown)}</td></tr>'
            )
        else:
            var_html.append(
                f'<tr><td class="k">{esc(name)}</td>'
                f'<td class="v missing">{esc(missing or "—")}</td></tr>'
            )

    # ---- 最近 6 行执行轨迹（settrace 的行事件，越下越新）
    recent = recent_line_records(trace, right_index, 6)
    recent_rows = []
    for position, record in enumerate(recent):
        relative = record["file"]
        basename = relative.rsplit("/", 1)[-1]
        source_line = sources.get(relative, [])
        snippet = ""
        if record["lineno"] - 1 < len(source_line):
            snippet = trim_code(source_line[record["lineno"] - 1].strip(), 64)
        css = "row new" if position == len(recent) - 1 else "row"
        recent_rows.append(
            f'<div class="{css}"><span class="loc">{esc(basename)}:{record["lineno"]}</span>'
            f'<span class="fn">{esc(record["func"])}</span>'
            f'<span class="src">{esc(snippet)}</span></div>'
        )
    recent_html = (
        '<div class="recent"><div class="recent-head">最近执行的 6 行（settrace 行事件，越下越新）</div>'
        + ("".join(recent_rows) if recent_rows else '<div class="row">（等待第一条行事件）</div>')
        + "</div>"
    )

    # ---- 证据链
    chips_html = "".join(
        f'<span class="chip {chip["tone"]}">{esc(chip["text"])}</span>' for chip in chips
    )
    if not chips:
        chips_html = '<span class="chip pending">（等待第一次校验结果）</span>'

    badge_html = (
        f'<span class="llm">● {esc(frame.badge)}</span>' if frame.badge else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="frame">
  <div class="top">
    <div class="title">执行轨迹对照<span class="sub">解释器执行到哪些计算逻辑 · 真跑 · 单次采样</span></div>
    <div class="meta">问法「{esc(trace.meta.get("query", ""))}」<br>
      {esc(trace.meta.get("model", ""))} · {esc(str(trace.meta.get("generated_at_local", ""))[:16])} · 第 {frame_index + 1} 帧
    </div>
  </div>
  <div class="cols">
    <div class="left panel">
      <div class="panel-head"><span>12 节点时间轴 · SSE</span><b>左右同一条 wall-clock</b></div>
      <div class="nodes">{"".join(node_rows)}</div>
      {left_foot}
    </div>
    <div class="right panel">
      {tab}
      {code_html}
      <div class="vars">
        <div class="vars-head">关键局部变量（settrace 按行抓取 · 截断到 ≤120 字符 · 不含 key）{badge_html}</div>
        <table class="vt">{"".join(var_html)}</table>
      </div>
      {recent_html}
      <div class="evidence">{chips_html}</div>
      <div class="right-foot">
        <span>行级轨迹：<b>{len(trace.lines)}</b> 行事件 · 只追 graph.py / correct.py / guard.py / policy.py</span>
        <span>行级轨迹 ≠ 完整调用栈</span>
      </div>
    </div>
  </div>
</div></body></html>"""


# ---------------------------------------------------------------- 截图/GIF

def chrome_screenshot(html_path: Path, png_path: Path, profile_dir: Path) -> Path:
    png_path.unlink(missing_ok=True)
    command = [
        CHROME,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--force-device-scale-factor={DEVICE_SCALE}",
        f"--window-size={CSS_W},{CSS_H}",
        f"--user-data-dir={profile_dir}",
        f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError("chrome 截图失败：\n" + (proc.stderr or proc.stdout or "")[-3000:])
    return png_path


def image_size(path: Path) -> tuple[int, int]:
    # 动图会每帧输出一行，取第一行即可
    out = run(["identify", "-format", "%w %h\n", str(path)]).stdout.strip().splitlines()
    if not out:
        raise RuntimeError(f"identify 读不出尺寸：{path}")
    width, height = out[0].split()
    return int(width), int(height)


def resize_png(source: Path, target: Path, width: int) -> None:
    run(["convert", str(source), "-resize", f"{width}x", "-strip", str(target)])


def write_gif(frames: list[Path], delays: list[int], out: Path) -> None:
    out.unlink(missing_ok=True)
    command = ["convert", "-loop", "0"]
    for frame, delay in zip(frames, delays):
        command += ["-delay", str(delay), str(frame)]
    command += ["-layers", "Optimize", str(out)]
    run(command, timeout=300)


def gif_info(path: Path) -> dict[str, Any]:
    width, height = image_size(path)
    delays_output = run(["identify", "-format", "%T\n", str(path)]).stdout.split()
    delays = [int(value) for value in delays_output if value.strip()]
    frame_count = len(delays)
    return {
        "width": width,
        "height": height,
        "frames": frame_count,
        "bytes": path.stat().st_size,
        "loop_cs": sum(delays),
        "loop_s": round(sum(delays) / 100.0, 2),
        "delays_cs": delays,
    }


def coalesce_gif(gif: Path, work: Path) -> list[Path]:
    """GIF 是逐帧差分存的：必须先 -coalesce 还原完整帧，否则抽出来的是残片。"""
    work.mkdir(parents=True, exist_ok=True)
    pattern = work / "co-%03d.png"
    for old in work.glob("co-*.png"):
        old.unlink()
    run(["convert", str(gif), "-coalesce", str(pattern)], timeout=300)
    frames = sorted(work.glob("co-*.png"))
    if not frames:
        raise RuntimeError("coalesce 后没有帧")
    return frames


def pixel_diff(first: Path, second: Path) -> int:
    proc = subprocess.run(
        ["compare", "-metric", "AE", str(first), str(second), "null:"],
        capture_output=True, text=True,
    )
    match = re.search(r"(\d+)", proc.stderr or "")
    return int(match.group(1)) if match else 0


def ocr_text(png: Path) -> str:
    """深色终端风对 tesseract 不友好：先反色成白底黑字并放大 2×。"""
    prepared = png.with_name(png.stem + "-ocr.png")
    run(
        [
            "convert", str(png),
            "-negate", "-colorspace", "Gray",
            "-resize", "200%",
            str(prepared),
        ]
    )
    lang = "eng"
    try:
        langs = run(["tesseract", "--list-langs"]).stdout
        if "chi_sim" in langs:
            lang = "chi_sim+eng"
    except Exception:  # noqa: BLE001 - 没装 chi_sim 就只认英文 token
        lang = "eng"
    best = ""
    for psm in ("6", "11", "4"):
        proc = subprocess.run(
            ["tesseract", str(prepared), "stdout", "-l", lang, "--psm", psm],
            capture_output=True, text=True, timeout=120,
        )
        text = (proc.stdout or "").strip()
        if len(text) > len(best):
            best = text
    return best


# ---------------------------------------------------------------- 主流程

def build_gif_with_budget(
    raw_frames: list[Path],
    delays: list[int],
    work: Path,
) -> tuple[Path, dict[str, Any]]:
    candidates = [(FINAL_WIDTH, None), (FINAL_WIDTH, 128), (FINAL_WIDTH, 96),
                  (1400, 128), (1400, 96), (1280, 96)]
    attempts: list[dict[str, Any]] = []
    last_error = None
    for width, colors in candidates:
        sized_dir = work / f"sized-{width}-{colors or 256}"
        sized_dir.mkdir(parents=True, exist_ok=True)
        sized = []
        for index, raw in enumerate(raw_frames):
            target = sized_dir / f"f{index:03d}.png"
            if not target.exists():
                resize_png(raw, target, width)
            sized.append(target)
        out = work / f"candidate-{width}-{colors or 256}.gif"
        try:
            write_gif(sized, delays, out)
        except Exception as exc:  # noqa: BLE001 - 换下一档配置
            last_error = str(exc)
            continue
        info = gif_info(out)
        attempts.append({"width": width, "colors": colors or 256, "bytes": info["bytes"]})
        if info["bytes"] <= GIF_MAX_BYTES and 1100 <= info["width"] <= 1600:
            out.replace(GIF_PATH)
            info["chosen"] = {"width": width, "colors": colors or 256}
            info["attempts"] = attempts
            return GIF_PATH, info
        last_error = f"GIF {info['bytes']} B > {GIF_MAX_BYTES} B（{width}px）"
    raise RuntimeError(f"GIF 压不到 3MB：{last_error}（尝试：{attempts}）")


def main(argv: list[str] | None = None) -> int:
    global STEPS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="只验证，不重新渲染")
    parser.add_argument("--keep-work", action="store_true", help="保留中间帧（调试用）")
    args = parser.parse_args(argv)

    STEPS = load_steps()
    max_attempts = load_max_attempts()
    api_key = read_env_api_key()

    if not TRACE_PATH.exists():
        raise SystemExit(f"缺少轨迹文件：{TRACE_PATH.relative_to(REPO)}\n先跑 manual/shots/trace_query.py")
    trace = Trace.load(TRACE_PATH, META_PATH)
    say(f"[render] 轨迹：{len(trace.records)} 条记录 / SSE {len(trace.sse)} / 行 {len(trace.lines)} / LLM {len(trace.llm)}")

    trace_check = verify_trace(trace, api_key)
    say(f"[render] 轨迹断言：{trace_check['passed']}/{trace_check['total']} 通过")
    for item in trace_check["failed"]:
        say(f"[render]   ✗ {item['name']} {item['detail']}")
    if trace_check["failed"]:
        raise SystemExit("[render] 原始轨迹断言未通过，拒绝渲染")
    if not trace.meta.get("triggered"):
        raise SystemExit("[render] meta.triggered=false：这次没触发 validate:error→correct:success，不渲染假图")

    # 从轨迹里拿第一次 validate 的错误码（供证据链/OCR）
    error_code = ""
    for record in trace.records:
        if record["kind"] != "line":
            continue
        for name in ("error", "failure"):
            value = (record.get("vars") or {}).get(name)
            if isinstance(value, str) and value.startswith("SQL_") and ":" in value:
                error_code = value.split(":", 1)[0].strip()
                break
        if error_code:
            break
    if not error_code:
        raise SystemExit("[render] 轨迹里找不到第一次校验的错误码（error/failure 变量）")

    sources = {relative: load_source(relative) for relative in TARGET_FILES}
    frames = build_frames(trace)
    say(f"[render] 帧计划：{len(frames)} 帧 / 循环 {sum(f.delay_cs for f in frames) / 100.0:.1f}s")
    keyframe_index = next((i for i, f in enumerate(frames) if f.keyframe), None)
    if keyframe_index is None:
        raise SystemExit("[render] 帧计划里没有 correct.py 关键帧")

    loop_s = sum(frame.delay_cs for frame in frames) / 100.0
    if args.verify_only:
        if not GIF_PATH.exists() or not PNG_PATH.exists():
            raise SystemExit("[render] --verify-only 需要已有 GIF/PNG")
        report = finish_report(trace, trace_check, gif_info(GIF_PATH), None, error_code, [], api_key)
        return 0 if report else 1

    work = Path(tempfile.mkdtemp(prefix="p17trace-render-"))
    profile_dir = work / "chrome-profile"
    raw_frames: list[Path] = []
    rendered_html: list[str] = []
    try:
        for index, frame in enumerate(frames):
            html_text = render_html(
                trace, index, frame, sources, max_attempts, error_code, loop_s
            )
            rendered_html.append(html_text)
            html_path = work / f"frame-{index:03d}.html"
            html_path.write_text(html_text, encoding="utf-8")
            raw = work / f"raw-{index:03d}.png"
            chrome_screenshot(html_path, raw, profile_dir)
            width, height = image_size(raw)
            if width != CSS_W * DEVICE_SCALE:
                raise RuntimeError(f"截图宽度 {width}px，不是 {CSS_W * DEVICE_SCALE}px（@2x）")
            raw_frames.append(raw)
            if index % 8 == 0 or index == len(frames) - 1:
                say(f"[render]   帧 {index + 1}/{len(frames)} 已截图（{width}x{height}）")
        # 关键帧 PNG（先按最终宽度缩放，保持与 GIF 同版式）
        key_sized = work / "keyframe.png"
        resize_png(raw_frames[keyframe_index], key_sized, FINAL_WIDTH)
        key_sized.replace(PNG_PATH)
        say(f"[render] 关键帧 → {PNG_PATH.relative_to(REPO)}（帧 {keyframe_index + 1}）")

        gif_path, info = build_gif_with_budget(raw_frames, [f.delay_cs for f in frames], work)
        say(f"[render] GIF → {gif_path.relative_to(REPO)} "
            f"{info['width']}x{info['height']} / {info['frames']} 帧 / "
            f"{info['bytes']} B / {info['loop_s']}s / 选型 {info['chosen']}")
        report_ok = finish_report(
            trace, trace_check, info, keyframe_index, error_code, rendered_html, api_key
        )
        return 0 if report_ok else 1
    finally:
        if not args.keep_work:
            shutil.rmtree(work, ignore_errors=True)
        else:
            say(f"[render] 中间文件保留在 {work}")


def finish_report(
    trace: Trace,
    trace_check: dict[str, Any],
    gif: dict[str, Any],
    keyframe_index: int | None,
    error_code: str,
    rendered_html: list[str],
    api_key: str,
) -> bool:
    """GIF/关键帧/画面敏感串/OCR 验证，写 exec-trace.render.json。"""
    width = gif["width"]
    height = gif["height"]
    frames = gif["frames"]
    ok = True

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal ok
        if not condition:
            ok = False
        say(f"[verify] {'✓' if condition else '✗'} {name}{('：' + detail) if detail else ''}")

    check("GIF 宽度 1100–1600px", 1100 <= width <= 1600, f"{width}px")
    check("GIF 帧数 ≥ 12", frames >= 12, f"{frames} 帧")
    check("GIF ≤ 3MB", gif["bytes"] <= GIF_MAX_BYTES, f"{gif['bytes']} B")
    check("GIF 循环 6–10s", 6.0 <= gif["loop_s"] <= 10.0, f"{gif['loop_s']}s")

    work = Path(tempfile.mkdtemp(prefix="p17trace-verify-"))
    try:
        coalesced = coalesce_gif(GIF_PATH, work / "coalesced")
        first = coalesced[0]
        middle = coalesced[len(coalesced) // 2]
        last = coalesced[-1]
        diff_first_middle = pixel_diff(first, middle)
        diff_middle_last = pixel_diff(middle, last)
        check("首帧≠中帧（像素差>0）", diff_first_middle > 0, f"AE={diff_first_middle}")
        check("中帧≠末帧（像素差>0）", diff_middle_last > 0, f"AE={diff_middle_last}")

        ocr_last = ocr_text(last)
        normalized = ocr_last.lower().replace(" ", "").replace("-", "_")
        check("末帧 OCR 含 correct_sql", "correct_sql" in normalized)
        check(
            f"末帧 OCR 含实际校验错误码 {error_code}",
            error_code.lower() in normalized,
            "任务示例写的是 SQL_UNKNOWN_COLUMN，本次真跑是 " + error_code,
        )
        ocr_middle = ocr_text(middle)
        ocr_first = ocr_text(first)
        say(f"[verify] 末帧 OCR 片段：{ocr_last[:260].replace(chr(10), ' | ')}")

        # 画面文本源头的敏感串检查（比 OCR 可靠）：把每帧 HTML 里的可见文本扫一遍
        rendered_text = " ".join(
            re.sub(r"<[^>]+>", " ", html_text) for html_text in rendered_html
        )
        leaked = [pattern for pattern in FORBIDDEN_PATTERNS if pattern in rendered_text]
        check("画面无用户名/绝对路径/API key/隔离端口", not leaked, ", ".join(leaked))
        if api_key:
            check("画面无 API key", api_key not in rendered_text)

        png_info = image_size(PNG_PATH)
        check("关键帧 PNG ≥ 1100px 宽", png_info[0] >= 1100, f"{png_info[0]}x{png_info[1]}")

        report = {
            "generated_at_local": now_text(),
            "source_trace": {
                "file": str(TRACE_PATH.relative_to(REPO)),
                "bytes": TRACE_PATH.stat().st_size,
                "checks": trace_check,
            },
            "gif": {
                "file": str(GIF_PATH.relative_to(REPO)),
                "width": width,
                "height": height,
                "frames": frames,
                "bytes": gif["bytes"],
                "loop_s": gif["loop_s"],
                "chosen": gif.get("chosen"),
                "attempts": gif.get("attempts"),
                "pixel_diff_first_middle": diff_first_middle,
                "pixel_diff_middle_last": diff_middle_last,
            },
            "key_png": {
                "file": str(PNG_PATH.relative_to(REPO)),
                "size": f"{png_info[0]}x{png_info[1]}",
                "bytes": PNG_PATH.stat().st_size,
                "frame_index": keyframe_index,
            },
            "ocr": {
                "last_frame_has_correct_sql": "correct_sql" in normalized,
                "last_frame_has_error_code": error_code.lower() in normalized,
                "error_code": error_code,
                "error_code_note": (
                    "任务示例写的是 SQL_UNKNOWN_COLUMN；本次真跑第一次校验实际报 "
                    + error_code + "，证据按真实错误码验"
                ),
                "last_frame_excerpt": ocr_last[:400],
                "middle_frame_excerpt": ocr_middle[:200],
            },
            "leak_scan": {
                "patterns": list(FORBIDDEN_PATTERNS),
                "leaked": leaked,
                "ok": not leaked,
            },
            "ok": ok,
        }
        RENDER_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        say(f"[verify] 报告 → {RENDER_REPORT.relative_to(REPO)}；总体 {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
