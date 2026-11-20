#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trace_query.py —— 【v1 · 已退役，保留作参考】进程内跑 runner 录 SSE + settrace。

> 第 17 页现行方案（左栏=真前端截图 / 右栏=同一跑的行级轨迹）见
> manual/shots/trace_server.py + render_exec_trace.py，runbook 见
> manual/review/exec-trace-runbook.md。本文件只作历史参考，产物已不再被页面引用。

在 backend 容器内**进程内**真跑一次问数，同时录下两侧数据。

左边（SSE）：`AgentRunner.events()` 的原始事件（progress / result / error），
             每一条都自带 wall-clock 时间戳与相对开始时间。
右边（代码）：`sys.settrace` 的行级轨迹，**只追 4 个文件**（其余文件一律放行
             `return None`，不记一行）：

    backend/app/agent/graph.py       12 节点图：谁在跑、条件边往哪走
    backend/app/agent/correct.py     一次校正：提示词槽位、校正器调用、结论
    backend/app/generate/guard.py    S4 静态校验：AST 逐条断言
    backend/app/security/policy.py   S5 安全策略：白名单 / 单语句 / LIMIT

记录内容：`file:lineno`、`function`、时间戳、按名字筛选的关键局部变量
（sql / sql_before / sql_after / error / code / attempts / max_attempts /
prompt / query / text …），一律截断到 ≤120 字符。**API key 永不落盘**：
名字像 key/token/secret/password 的变量直接跳过，值里若出现环境里的
`REBUILD_LLM_API_KEY` 整段替换成 `<redacted>`。

跑法（在仓库根目录；隔离栈 `p17trace` 已起、init 已跑完）：

    mkdir -p /tmp/p17trace-out && chmod 777 /tmp/p17trace-out
    docker compose -p p17trace --env-file .env run --rm --no-deps \
      -v "$PWD/manual/shots/trace_query.py:/tmp/trace_query.py:ro" \
      -v /tmp/p17trace-out:/out \
      backend python /tmp/trace_query.py --out-dir /out

产物（写到 --out-dir）：
    exec-trace.jsonl        行级 + SSE 轨迹（JSONL，一条记录一行）
    exec-trace.meta.json    日期 / 模型 / 问法 / 事件数 / 耗时 / LLM 调用次数

触发问法固定为「查询销售额大于平均销售额的商品」（历史两次真跑都触发
validate:error → correct:success）。这是 LLM 采样，**不保证**每次触发：
最多尝试 3 次，只保留“触发且校正成功”的那一次；都没触发就保留最后一次
现场，并在 meta 里如实写 `triggered: false`。

依赖：backend 镜像里已有的 python 与 app 代码、compose 注入的
REBUILD_* 环境变量（MySQL / ES / Qdrant / LLM）。不改页面、不改判据。
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import platform
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- 常量

DEFAULT_QUERY = "查询销售额大于平均销售额的商品"
DEFAULT_MAX_ATTEMPTS = 3
JSONL_NAME = "exec-trace.jsonl"
META_NAME = "exec-trace.meta.json"
MAX_TRACE_BYTES = 500 * 1024
VAR_MAX_CHARS = 120

#: 只追这四个文件。路径是**仓库相对路径**（容器里根是 /app）。
TARGET_FILES: tuple[str, ...] = (
    "backend/app/agent/graph.py",
    "backend/app/agent/correct.py",
    "backend/app/generate/guard.py",
    "backend/app/security/policy.py",
)

#: 关键局部变量名（按任务口径筛选；不在这里的值一个都不记）。
VAR_NAMES: tuple[str, ...] = (
    "sql",
    "sql_before",
    "sql_after",
    "error",
    "code",
    "attempts",
    "max_attempts",
    "prompt",
    "query",
    "text",
    "failure",
    "state",
    "proposal",
    "decision",
    "report",
    "payload",
    "note",
    "original",
    "final_sql",
    "statements",
    "gates",
)

#: 名字里带这些片段的变量一律不记（API key / 口令 / token 都可能藏在这里）。
SECRET_NAME_HINTS = ("key", "token", "secret", "password", "passwd", "auth")

#: 画面上不想出现的隔离端口（值里万一出现就替换掉）。
ISOLATION_PORTS = ("13397", "19297", "16397", "18197", "18097")

_REPO_ROOT = Path(os.environ.get("TRACE_REPO_ROOT", "/app")).resolve()
_API_KEY = os.environ.get("REBUILD_LLM_API_KEY", "")

#: 脚本本体在 /tmp 下执行时 sys.path[0] 是 /tmp，容器 WORKDIR（/app/backend）
#: 不会自动进 sys.path；把应用目录显式补进去，才能 import 到镜像里的真实代码。
_APP_DIR = Path(os.environ.get("TRACE_APP_DIR", "/app/backend"))
if _APP_DIR.is_dir() and str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def say(msg: str = "") -> None:
    """人看的日志走 stderr，stdout 不掺杂质（若将来改成 stdout 输出也不脏）。"""
    print(msg, file=sys.stderr, flush=True)


def scrub(text: str) -> str:
    """把不该出现在轨迹里的东西抹掉：API key、绝对路径、用户名、隔离端口。"""
    if _API_KEY and _API_KEY in text:
        text = text.replace(_API_KEY, "<redacted>")
    text = text.replace(str(_REPO_ROOT) + "/", "")
    text = text.replace("/app/", "")
    text = re.sub(r"/home/[^/\s]+", "<home>", text)
    text = text.replace("zhensirong", "<user>")
    for port in ISOLATION_PORTS:
        text = text.replace(port, "<port>")
    return text.replace("\r", " ").replace("\n", " ").replace("\t", " ")


def short(value: Any, limit: int = VAR_MAX_CHARS) -> str:
    """值的单行短表示：别让一个变量把一行 JSONL 撑爆。"""
    if isinstance(value, str):
        text = value
    elif hasattr(value, "code") and hasattr(value, "message"):
        # ChannelError / ExecutionError 这类“有名字的失败”
        text = f"{getattr(value, 'code', '')}: {getattr(value, 'message', '')}"
    else:
        try:
            text = repr(value)
        except Exception:  # noqa: BLE001 - repr 失败不该把整个轨迹拖垮
            text = f"<unrepr {type(value).__name__}>"
    text = scrub(text)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def _message_of(value: Any) -> str:
    code = getattr(value, "code", None)
    message = getattr(value, "message", None)
    if code is not None or message is not None:
        return short(f"{code or ''}: {message or ''}")
    return short(value)


def extract_vars(frame: Any) -> dict[str, Any]:
    """按 VAR_NAMES 白名单从当前帧里摘变量；state 字典再挑几个关键字段。"""
    found: dict[str, Any] = {}
    local = frame.f_locals
    for name in VAR_NAMES:
        if name not in local:
            continue
        if any(hint in name.lower() for hint in SECRET_NAME_HINTS):
            continue
        value = local[name]
        lowered = name.lower()
        if lowered == "state" and isinstance(value, dict):
            picked: dict[str, Any] = {}
            for key in (
                "sql",
                "original_sql",
                "corrected_sql",
                "attempts",
                "correction_attempted",
            ):
                if key in value and value[key] is not None:
                    picked[key] = short(value[key])
            failure = value.get("failure")
            if failure is not None:
                picked["failure"] = _message_of(failure)
            if picked:
                found[name] = picked
            continue
        if lowered in ("error", "failure"):
            found[name] = _message_of(value)
            continue
        if lowered == "state":
            continue
        found[name] = short(value)
    return found


# ---------------------------------------------------------------- 记录器


class Recorder:
    """一次尝试的全部记录。时间戳用 wall clock（time.time），单位秒。"""

    def __init__(self, attempt: int, query: str) -> None:
        self.attempt = attempt
        self.query = query
        self.started_epoch = time.time()
        self.started_mono = time.monotonic()
        self.records: list[dict[str, Any]] = []
        self.llm_calls = 0
        self.line_events = 0
        self._seq = itertools.count()
        self._llm_open: dict[str, list[dict[str, Any]]] = {}
        #: (file, func) → 上一次的变量快照；连续相同的变量只记一次，避免
        #: guard/policy 的循环把 500KB 预算吃光（值不变就是没有新信息）。
        self._last_vars: dict[tuple[str, str], str] = {}

    # -- 时间 ------------------------------------------------------------

    def _stamp(self) -> tuple[float, float]:
        now = time.time()
        return now, round((time.monotonic() - self.started_mono) * 1000.0, 2)

    # -- 记录 ------------------------------------------------------------

    def add(self, kind: str, payload: dict[str, Any]) -> None:
        now, elapsed_ms = self._stamp()
        record: dict[str, Any] = {
            "kind": kind,
            "t": round(now, 6),
            "elapsed_ms": elapsed_ms,
            "attempt": self.attempt,
            "seq": next(self._seq),
        }
        record.update(payload)
        self.records.append(record)

    def start(self, model: str) -> None:
        now, elapsed_ms = self._stamp()
        self.add(
            "start",
            {
                "query": self.query,
                "model": model,
                "targets": list(TARGET_FILES),
                "python": platform.python_version(),
                "started_at_local": datetime.fromtimestamp(
                    now, timezone(timedelta(hours=8))
                ).isoformat(timespec="seconds"),
            },
        )

    def sse(self, event: dict[str, Any]) -> None:
        self.add("sse", {"event": event})

    def line(self, file: str, lineno: int, func: str, caller: str, variables: dict[str, Any]) -> None:
        self.line_events += 1
        payload: dict[str, Any] = {
            "file": file,
            "lineno": lineno,
            "func": func,
            "thread": "main"
            if threading.current_thread().name == "MainThread"
            else "worker",
        }
        if caller:
            payload["caller"] = caller
        if variables:
            signature = json.dumps(variables, ensure_ascii=False, sort_keys=True)
            cache_key = (file, func)
            if self._last_vars.get(cache_key) != signature:
                self._last_vars[cache_key] = signature
                payload["vars"] = variables
        self.add("line", payload)

    # -- LLM 调用计数（只包一层计数，不碰真实请求内容） ------------------

    def llm_start(self, role: str, prompt: str) -> int:
        self.llm_calls += 1
        now, elapsed_ms = self._stamp()
        record = {
            "kind": "llm",
            "t": round(now, 6),
            "elapsed_ms": elapsed_ms,
            "attempt": self.attempt,
            "seq": next(self._seq),
            "role": role,
            "call": self.llm_calls,
            "event": "start",
            "prompt_preview": short(prompt),
        }
        self.records.append(record)
        self._llm_open.setdefault(role, []).append(record)
        return self.llm_calls

    def llm_end(self, role: str) -> None:
        now, elapsed_ms = self._stamp()
        started = None
        if self._llm_open.get(role):
            started = self._llm_open[role].pop(0)
        self.records.append(
            {
                "kind": "llm",
                "t": round(now, 6),
                "elapsed_ms": elapsed_ms,
                "attempt": self.attempt,
                "seq": next(self._seq),
                "role": role,
                "event": "end",
                "duration_ms": (
                    round((now - started["t"]) * 1000.0, 1) if started else None
                ),
            }
        )

    def finish(self, outcome: dict[str, Any]) -> None:
        self.add("end", outcome)


# ---------------------------------------------------------------- 行级 tracer


class LineTracer:
    """sys.settrace 的行级轨迹；只对 TARGET_FILES 里的帧记 line 事件。"""

    def __init__(self) -> None:
        #: 同一个 tracer 跨多次尝试复用：LangGraph 的节点跑在线程池里，
        #: 线程在第一次 stream 时才创建；`threading.settrace` 只影响“之后
        #: 创建”的线程，所以钩子必须全程装着，只切换当前记录器。
        self.recorder: Recorder | None = None
        self._cache: dict[str, str | None] = {}
        self.enabled = False

    def set_recorder(self, recorder: Recorder) -> None:
        self.recorder = recorder
        self.enabled = True

    # -- 路径映射 --------------------------------------------------------

    def _relative(self, filename: str) -> str | None:
        cached = self._cache.get(filename, "<miss>")
        if cached != "<miss>":
            return cached
        mapped: str | None = None
        try:
            path = Path(filename)
            if path.is_absolute():
                rel = path.resolve().relative_to(_REPO_ROOT)
                candidate = rel.as_posix()
            else:
                candidate = filename
            if candidate in TARGET_FILES:
                mapped = candidate
        except (ValueError, OSError):
            mapped = None
        self._cache[filename] = mapped
        return mapped

    # -- trace 回调 ------------------------------------------------------

    def global_trace(self, frame: Any, event: str, arg: Any) -> Any:
        if not self.enabled:
            return None
        rel = self._relative(frame.f_code.co_filename)
        if rel is None:
            return None
        if event == "line":
            self._record(frame, rel)
        return self.local_trace

    def local_trace(self, frame: Any, event: str, arg: Any) -> Any:
        if not self.enabled:
            return None
        if event == "line":
            rel = self._relative(frame.f_code.co_filename)
            if rel is not None:
                self._record(frame, rel)
        return self.local_trace

    def _record(self, frame: Any, rel: str) -> None:
        caller = ""
        parent = frame.f_back
        if parent is not None:
            parent_rel = self._relative(parent.f_code.co_filename)
            if parent_rel is not None:
                caller = f"{Path(parent_rel).name}:{parent.f_code.co_name}"
        if self.recorder is None:
            return
        self.recorder.line(
            file=rel,
            lineno=frame.f_lineno,
            func=frame.f_code.co_name,
            caller=caller,
            variables=extract_vars(frame),
        )

    # -- 安装/卸载 -------------------------------------------------------

    def install(self) -> None:
        # 主线程：graph.stream() 的驱动代码；工作线程：LangGraph 的节点。
        sys.settrace(self.global_trace)
        threading.settrace(self.global_trace)

    def uninstall(self) -> None:
        self.enabled = False
        sys.settrace(None)
        threading.settrace(None)


# ---------------------------------------------------------------- 计数包装


class CountingGenerator:
    """只给生成器加一个调用计数/计时，请求与返回原样透传。"""

    def __init__(self, inner: Any, role: str, recorder: Recorder) -> None:
        self._inner = inner
        self._role = role
        self._recorder = recorder
        self.name = getattr(inner, "name", "llm")

    def generate(self, context: Any, prompt: str) -> dict[str, Any]:
        self._recorder.llm_start(self._role, prompt)
        try:
            return self._inner.generate(context, prompt)
        finally:
            self._recorder.llm_end(self._role)


# ---------------------------------------------------------------- 一次尝试


def build_runner(query: str, recorder: Recorder) -> Any:
    """和生产装配（app/main.py 的 default_runner_factory）同一条路径。"""
    from app.agent.correct import LlmCorrector
    from app.agent.orchestrator import AgentRunner
    from app.generate.provider import HttpLlmGenerator

    generator = CountingGenerator(
        HttpLlmGenerator.from_env(), "generate_sql", recorder
    )
    corrector = LlmCorrector(
        CountingGenerator(HttpLlmGenerator.from_env(), "correct_sql", recorder)
    )
    return AgentRunner(
        query=query,
        generator=generator,
        corrector=corrector,
        executor=None,  # 默认 ReadOnlyExecutor：真连 MySQL，只读账号
        cancel=None,
        request_id=None,
    )


def run_attempt(
    query: str, attempt: int, tracer: LineTracer
) -> tuple[Recorder, dict[str, Any]]:
    """跑一次问数，返回（记录器, 判读结果）。"""
    recorder = Recorder(attempt=attempt, query=query)
    tracer.set_recorder(recorder)
    from app.generate.provider import HttpLlmGenerator

    model = os.environ.get("REBUILD_LLM_MODEL", "")
    generator_name = HttpLlmGenerator.from_env().name
    if generator_name != "http-llm":
        raise SystemExit(f"[trace] 环境里不是真模型（generator={generator_name}），拒绝出假证据")
    recorder.start(model)

    say(f"[trace] attempt {attempt}: 开始问数（model={model}, generator={generator_name}）")
    started = time.time()
    error: str | None = None
    try:
        runner = build_runner(query, recorder)
        for event in runner.events():
            recorder.sse(event)
    except Exception as exc:  # noqa: BLE001 - 驱动脚本兜底：异常也要留现场
        error = f"{type(exc).__name__}: {exc}"
        say(f"[trace] attempt {attempt}: 驱动异常 {error}")

    elapsed = round(time.time() - started, 2)
    outcome = classify(recorder.records)
    outcome["error"] = error
    outcome["wall_clock_s"] = elapsed
    outcome["line_events"] = recorder.line_events
    outcome["llm_calls"] = recorder.llm_calls
    recorder.finish(outcome)
    say(
        f"[trace] attempt {attempt}: {outcome['summary']} "
        f"（{elapsed}s / line={recorder.line_events} / llm={recorder.llm_calls}）"
    )
    return recorder, outcome


def classify(records: list[dict[str, Any]]) -> dict[str, Any]:
    """从 SSE 事件判读：校验是否红过、校正是否只跑一轮、是否最终出结果。"""
    events = [r["event"] for r in records if r["kind"] == "sse"]
    progress = [
        (e.get("step"), e.get("status"))
        for e in events
        if e.get("type") == "progress"
    ]
    validate_errors = [
        i for i, (step, status) in enumerate(progress)
        if step == "validate_sql" and status == "error"
    ]
    correct_runs = [
        i for i, (step, status) in enumerate(progress)
        if step == "correct_sql" and status == "running"
    ]
    correct_success = [
        i for i, (step, status) in enumerate(progress)
        if step == "correct_sql" and status == "success"
    ]
    second_validate_success = False
    if correct_runs:
        first_correct = correct_runs[0]
        second_validate_success = any(
            step == "validate_sql" and status == "success"
            for step, status in progress[first_correct:]
        )
    run_success = any(
        step == "run_sql" and status == "success" for step, status in progress
    )
    result = next((e for e in events if e.get("type") == "result"), None)
    error_event = next((e for e in events if e.get("type") == "error"), None)
    triggered = bool(
        validate_errors
        and len(correct_runs) == 1
        and len(correct_success) == 1
        and second_validate_success
        and run_success
        and result is not None
    )
    if triggered:
        summary = "触发校正并成功（validate:error → correct:success → validate:success）"
    elif result is not None and not validate_errors:
        summary = "未触发校正（一次校验就过，模型直接生成了合法 SQL）"
    else:
        code = (error_event or {}).get("code")
        summary = f"未达成目标帧序（final={code or 'result'}, validate_errors={len(validate_errors)}）"
    detail = (result or {}).get("data") or {}
    return {
        "triggered": triggered,
        "summary": summary,
        "validate_errors": len(validate_errors),
        "correct_running": len(correct_runs),
        "correct_success": len(correct_success),
        "second_validate_success": second_validate_success,
        "run_sql_success": run_success,
        "result": result is not None,
        "final_error_code": (error_event or {}).get("code"),
        "row_count": len(detail.get("rows") or []),
        "columns": [column.get("name") for column in detail.get("columns") or []],
        "event_count": len(events),
    }


# ---------------------------------------------------------------- 裁剪/落盘


def serialize(records: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        + "\n"
    ).encode("utf-8")


def crop_records(
    records: list[dict[str, Any]], limit: int = MAX_TRACE_BYTES
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """原始行事件超过 500KB 时裁剪：SSE / LLM / start / end 一条不丢。

    行记录用“关键帧 + 均匀抽样”保住过程可读：
      1. 带 error / failure / attempts / prompt / code 变量的行全留（校正现场）；
      2. 每个目标文件的首末行各留一条（证明文件真的被追到）；
      3. 其余行记录按步长均匀抽样，时间轴不变稀疏。

    返回（裁剪后的记录, 裁剪说明）；没超限时原样返回。
    """
    original_bytes = len(serialize(records))
    info = {
        "original_bytes": original_bytes,
        "cropped": False,
        "dropped_lines": 0,
        "kept_lines": sum(1 for r in records if r["kind"] == "line"),
    }
    if original_bytes <= limit:
        return records, info

    non_lines = [r for r in records if r["kind"] != "line"]
    lines = [r for r in records if r["kind"] == "line"]
    key_var_names = {"error", "failure", "attempts", "prompt", "code", "note"}
    priority = [
        r for r in lines
        if key_var_names & set((r.get("vars") or {}).keys())
    ]
    by_file: dict[str, list[dict[str, Any]]] = {}
    for record in lines:
        by_file.setdefault(record["file"], []).append(record)
    for items in by_file.values():
        priority.append(items[0])
        priority.append(items[-1])
    priority_ids = {id(r) for r in priority}
    rest = [r for r in lines if id(r) not in priority_ids]

    info["cropped"] = True
    info["priority_lines"] = len(priority)
    stride = 2
    while True:
        sampled = rest[::stride]
        keep_ids = priority_ids | {id(r) for r in sampled}
        kept = [r for r in records if r["kind"] != "line" or id(r) in keep_ids]
        payload = serialize(kept)
        if len(payload) <= limit:
            info["dropped_lines"] = len(records) - len(kept)
            info["kept_lines"] = len(kept) - len(non_lines)
            info["sample_stride"] = stride
            return kept, info
        if stride > 8192:
            raise SystemExit(
                f"[trace] 轨迹裁剪后仍超过 500KB（{len(payload)} B），拒绝落盘"
            )
        stride *= 2


def write_outputs(
    out_dir: Path,
    records: list[dict[str, Any]],
    meta: dict[str, Any],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cropped, crop_info = crop_records(records)
    payload = serialize(cropped)
    jsonl_path = out_dir / JSONL_NAME
    jsonl_path.write_bytes(payload)
    meta = dict(meta)
    meta["trace"] = {
        "file": JSONL_NAME,
        "bytes": len(payload),
        "records": len(cropped),
        "cropped": crop_info["cropped"],
        "dropped_lines": crop_info["dropped_lines"],
        "original_bytes": crop_info["original_bytes"],
    }
    for extra in ("sample_stride", "priority_lines", "kept_lines"):
        if extra in crop_info:
            meta["trace"][extra] = crop_info[extra]
    meta_path = out_dir / META_NAME
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for path in (jsonl_path, meta_path):
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
    return {"jsonl": str(jsonl_path), "meta": str(meta_path), "bytes": len(payload)}


# ---------------------------------------------------------------- 主流程


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    args = parser.parse_args(argv)

    say(f"[trace] 目标文件：{', '.join(TARGET_FILES)}")
    say(f"[trace] 问法：{args.query}")
    say(f"[trace] API key 已注入：{'yes' if _API_KEY else 'NO'}（不打印、不落盘）")

    tracer = LineTracer()
    tracer.install()
    attempts: list[dict[str, Any]] = []
    chosen: Recorder | None = None
    try:
        for attempt in range(1, args.max_attempts + 1):
            recorder, outcome = run_attempt(args.query, attempt, tracer)
            attempts.append(outcome)
            chosen = recorder  # 先留着：万一都没触发，保留最后一次现场
            if outcome["triggered"]:
                say(f"[trace] attempt {attempt}: 命中目标帧序，保留这一次")
                break
            say(f"[trace] attempt {attempt}: 未命中，{'重试' if attempt < args.max_attempts else '放弃'}")
            time.sleep(1.0)
    finally:
        tracer.uninstall()

    if chosen is None:
        raise SystemExit("[trace] 一次都没跑成")

    # 节点跑在 LangGraph 的工作线程里，多个线程各写各的时间戳；按
    # (wall-clock, 线程内序号) 稳定排序，落盘的轨迹才是时间单调的。
    chosen.records.sort(key=lambda record: (record["t"], record["seq"]))
    for _record in chosen.records:
        _record.pop("seq", None)

    # 时间戳单调性自检（wall clock 同进程，正常不会倒退）
    stamps = [record["t"] for record in chosen.records]
    monotonic = all(later >= earlier for earlier, later in zip(stamps, stamps[1:]))
    line_files = sorted(
        {record["file"] for record in chosen.records if record["kind"] == "line"}
    )
    line_counts: dict[str, int] = {}
    for record in chosen.records:
        if record["kind"] == "line":
            line_counts[record["file"]] = line_counts.get(record["file"], 0) + 1
    vars_seen: set[str] = set()
    for record in chosen.records:
        for name in (record.get("vars") or {}):
            vars_seen.add(name)

    final = attempts[-1]
    meta = {
        "artifact": JSONL_NAME,
        "generated_at_local": datetime.now(timezone(timedelta(hours=8))).isoformat(
            timespec="seconds"
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "query": args.query,
        "model": os.environ.get("REBUILD_LLM_MODEL", ""),
        "generator": "http-llm",
        "engine": (
            "backend 容器内进程内 AgentRunner.events() + sys.settrace；"
            "LangGraph 节点跑在工作线程，用 threading.settrace 一并追"
        ),
        "triggered": final["triggered"],
        "attempt_kept": chosen.attempt,
        "attempts": attempts,
        "llm_calls": sum(item.get("llm_calls", 0) for item in attempts),
        "llm_calls_kept": chosen.llm_calls,
        "event_count": sum(
            1 for record in chosen.records if record["kind"] == "sse"
        ),
        "progress_count": sum(
            1
            for record in chosen.records
            if record["kind"] == "sse" and record["event"].get("type") == "progress"
        ),
        "result": {
            "columns": final.get("columns"),
            "row_count": final.get("row_count"),
        },
        "wall_clock_s": final.get("wall_clock_s"),
        "trace_files": line_files,
        "trace_file_count": len(line_files),
        "line_events": sum(line_counts.values()),
        "line_events_by_file": line_counts,
        "vars_seen": sorted(vars_seen),
        "timestamps_monotonic": monotonic,
        "api_key_in_trace": bool(_API_KEY) and _API_KEY in serialize(chosen.records).decode("utf-8", "ignore"),
        "note": (
            "单次采样；LLM 温度 0 但不保证每次触发同一路径。"
            "行级轨迹只覆盖 4 个文件，不等于完整调用栈。"
        ),
        "attempts_note": (
            f"共尝试 {len(attempts)} 次，保留第 {chosen.attempt} 次"
            if len(attempts) > 1
            else "第 1 次即命中，未重试"
        ),
    }

    if args.out_dir:
        written = write_outputs(Path(args.out_dir), chosen.records, meta)
        say(f"[trace] 已写入 {written['jsonl']}（{written['bytes']} B）")
        say(f"[trace] 已写入 {written['meta']}")
    else:
        # 没有挂载目录时：JSONL 写 stdout，人看的摘要写 stderr
        sys.stdout.write(serialize(chosen.records).decode("utf-8"))
        sys.stdout.flush()

    say(f"[trace] 触发={final['triggered']} 行记录文件={line_files} 行事件={sum(line_counts.values())} 时间戳单调={monotonic}")
    if not final["triggered"]:
        say("[trace] 注意：这次没有命中 validate:error → correct:success 帧序，现场已保留，报告需如实说明")
    return 0 if final["triggered"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
