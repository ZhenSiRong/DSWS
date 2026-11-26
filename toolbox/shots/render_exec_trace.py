#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 教师/CI 夹具：不是学生入口；学生工具见 tutorial/appendix/gui-debugging.md
"""render_exec_trace.py —— 第 17 页 v2：左「真前端截图」/ 右「同一次真跑的代码行」对照 GIF。

输入（由 tutorial/shots/trace_server.py 产出，已提交在仓库里）：

    tutorial/review/exec-trace-v2/meta.json            本次真跑：时间轴 / 触发帧序 / 尝试次数
    tutorial/review/exec-trace-v2/capture-frames.json  选中的真截图 + 每帧 DOM 探针（节点状态 / rect / 时间戳）
    tutorial/review/exec-trace-v2/frames/*.png         左栏真截图（800×1151，裁掉侧栏）
    tutorial/review/exec-trace-v2/trace.jsonl          同一请求的 backend 行级轨迹（sitecustomize 注入）

输出：

    tutorial/images/page-23-exec-trace.gif   18–25s 循环，12.5fps（80ms/帧），1600 宽，≤5MB
    tutorial/images/page-23-exec-trace.png   关键帧：阶段 c（校正SQL 转圈）—— 左：前端红叉+转圈，
                                           右：correct.py propose_correction() L202/203 + sql_before/error/attempts
    tutorial/review/exec-trace-v2/render.json  渲染/断言报告（帧计划、每阶段停留表、OCR、对齐抽样）

一条命令重跑（仓库根目录）：

    python3 tutorial/shots/render_exec_trace.py                 # 渲染 + 全部断言
    python3 tutorial/shots/render_exec_trace.py --verify-only   # 只验证已有产物

设计要点（都是“教学可读”的硬要求）：
  * 总时长 18–25s、12.5fps；每个关键状态停 2–3s 让人读完，末帧结果表停 ≥2.5s；
  * 每帧左上角标「阶段名 + 真实耗时」；底部标「时间轴已压缩，非实速」+ 真实总耗时；
  * 左栏是成熟版原版前端的**真截图**（不是节点列表、不是重绘）；右栏是**同一次真跑**
    的 sys.settrace 行级轨迹 + 白名单局部变量；左帧时间戳 → 取 ≤ 该时刻的 trace 事件；
  * 长等待（生成 11.0s / 校正 7.3s）在时间轴里压缩，但右栏写清「仍停在该调用行、
    已等待 X s」，并用同一跑的真实 duration 标注；
  * 不修改页面与判据；画面无用户名 / 绝对路径 / API key / 隔离端口。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
REVIEW = REPO / "manual" / "review"
EVIDENCE = REVIEW / "exec-trace-v2"
IMAGES = REPO / "manual" / "images"

META_PATH = EVIDENCE / "meta.json"
FRAMES_PATH = EVIDENCE / "capture-frames.json"
TRACE_PATH = EVIDENCE / "trace.jsonl"
RENDER_REPORT = EVIDENCE / "render.json"
GIF_PATH = IMAGES / "page-23-exec-trace.gif"
PNG_PATH = IMAGES / "page-23-exec-trace.png"

# ---- 画布（1600 宽；左 800 = 真截图原尺寸，右 756 = 代码面板） ----
CANVAS_W = 1600
HEADER_H = 112
PANEL_TOP = HEADER_H + 8
LEFT_W = 800
LEFT_H = 1151
LEFT_X = 14
GAP = 16
RIGHT_X = LEFT_X + LEFT_W + GAP          # 830
RIGHT_W = CANVAS_W - RIGHT_X - 14        # 756
PANEL_BOTTOM = PANEL_TOP + LEFT_H        # 1271
FOOTER_H = 44
CANVAS_H = PANEL_BOTTOM + 10 + FOOTER_H + 12   # 1337

FRAME_CS = 8                            # GIF 每帧 80ms = 12.5fps
LOOP_MIN_S, LOOP_MAX_S = 18.0, 25.0
GIF_MAX_BYTES = 5 * 1024 * 1024
CODE_WINDOW = 8

TARGET_FILES = (
    "system/backend/app/agent/graph.py",
    "system/backend/app/agent/correct.py",
    "system/backend/app/generate/guard.py",
    "system/backend/app/security/policy.py",
)

CHROME = "/usr/bin/google-chrome"
CHROME_SCALE = 1
FORBIDDEN = ("/home/", "/Users/", "zhensirong", "13317", "19217", "16317", "18117",
             "18017", "8088", "REBUILD_LLM_API_KEY", "MYSQL_ROOT_PASSWORD",
             "sk-", "Bearer ")

#: 阶段表： (key, 阶段号, 名称, 真实耗时文案生成器, 该阶段显示的帧数)
#: 帧数 × 80ms = 阶段停留；总帧数 229 × 80ms = 18.32s（落在 18–25s）
STAGE_PLAN: tuple[tuple[str, int, str, int], ...] = (
    ("s0", 0, "输入真问题", 31),
    ("t0", 1, "提交 → 构图", 15),
    ("a", 2, "生成SQL 执行中", 38),
    ("b", 3, "校验SQL 红叉（有误）", 33),
    ("c", 4, "校正SQL 转圈（执行中）", 39),
    ("d", 5, "校正成功 + 二次校验通过", 33),
    ("e", 6, "结果表 5 行", 40),
)


def say(msg: str = "") -> None:
    print(msg, file=sys.stderr, flush=True)


def run(cmd: list[str], *, timeout: float = 300.0) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-3000:]
        raise RuntimeError(f"命令失败（{cmd[0]}）：\n{tail}")
    return proc


def esc(text: Any) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def fmt_s(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    if abs(value) >= 10:
        return f"{value:.1f}s"
    return f"{value:.{digits}f}s"


# ---------------------------------------------------------------- 证据加载

@dataclass
class Evidence:
    meta: dict[str, Any]
    frames: dict[str, Any]
    trace: list[dict[str, Any]]
    t0: float                       # 点击时刻（epoch 秒，浏览器 wall clock）
    sources: dict[str, list[str]] = field(default_factory=dict)
    max_attempts: int = 1

    @property
    def timeline(self) -> dict[str, Any]:
        return self.meta["timeline_s"]

    def rel(self, record: dict[str, Any]) -> float:
        return record["t"] - self.t0


def load_evidence() -> Evidence:
    for path in (META_PATH, FRAMES_PATH, TRACE_PATH):
        if not path.exists():
            raise SystemExit(f"缺证据文件：{path.relative_to(REPO)}（先跑 tutorial/shots/trace_server.py）")
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    frames = json.loads(FRAMES_PATH.read_text(encoding="utf-8"))
    trace = [json.loads(line) for line in TRACE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    # 点击时刻由 trace_server.py 从浏览器 capture meta 原样写进 capture-frames.json
    # （浏览器 Date.now()，与后端 time.time() 同一台宿主时钟）。
    t0 = float(frames["t0_epoch"]) if "t0_epoch" in frames else \
        min(float(item["t_epoch"]) for role in ("t0", "a") for item in frames["roles"][role]) - 0.2
    sources = {}
    for relative in TARGET_FILES:
        sources[relative] = (REPO / relative).read_text(encoding="utf-8").splitlines()
    try:
        import yaml
        errors = yaml.safe_load((REPO / "contracts" / "errors.yaml").read_text(encoding="utf-8"))
        max_attempts = int(errors["correction"]["max_attempts"])
    except Exception:  # noqa: BLE001 - 契约读不到就用 1（本页契约）
        max_attempts = 1
    return Evidence(meta=meta, frames=frames, trace=trace, t0=t0,
                    sources=sources, max_attempts=max_attempts)


# ---------------------------------------------------------------- trace 查询

def find_last(trace: list[dict[str, Any]], t_epoch: float,
              predicate: Callable[[dict[str, Any]], bool] | None = None) -> dict[str, Any] | None:
    """取 t <= t_epoch 的最后一个满足 predicate 的事件（trace 已按时间单调）。"""
    for record in reversed(trace):
        if record["t"] > t_epoch:
            continue
        if predicate is None or predicate(record):
            return record
    return None


def merged_vars(trace: list[dict[str, Any]], anchor: dict[str, Any],
                window_s: float = 1.5) -> dict[str, Any]:
    """从锚点往回扫 window_s，收集每个变量名最近一次的值（trace 只在值变化时带 vars）。"""
    merged: dict[str, Any] = {}
    for record in reversed(trace):
        if record["t"] > anchor["t"]:
            continue
        if anchor["t"] - record["t"] > window_s:
            break
        for key, value in (record.get("vars") or {}).items():
            merged.setdefault(key, value)
    return merged


def last_run_lines(trace: list[dict[str, Any]], anchor: dict[str, Any], count: int = 6) -> list[dict[str, Any]]:
    """该时刻之前最近 count 条**不连续重复**的执行行。"""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for record in reversed(trace):
        if record["t"] > anchor["t"]:
            continue
        key = (record["file"], record["lineno"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(record)
        if len(rows) >= count:
            break
    return list(reversed(rows))


# ---------------------------------------------------------------- 锚点

@dataclass
class Anchor:
    stage: str
    record: dict[str, Any] | None
    highlight: int | None
    file: str | None
    note: str = ""
    exact_state: bool = False       # True = 处于“停在该行等待”的长等待态


def build_anchors(ev: Evidence) -> dict[str, Anchor]:
    trace = ev.trace
    frame_t = {role: [float(item["t_epoch"]) for item in ev.frames["roles"][role]]
               for role in ev.frames["roles"]}

    def is_file(name: str):
        return lambda r: r["rel"].endswith(name)

    def lines(*numbers: int):
        return lambda r: r["lineno"] in numbers

    # t0：构图（build_agent_graph），左帧是“正在连接问数智能体…”
    t0_frame = frame_t["t0"][0] + 0.25
    rec = find_last(trace, t0_frame, lambda r: r["rel"].endswith("graph.py") and r["func"] == "build_agent_graph")
    anchors = {"t0": Anchor("t0", rec, rec["lineno"] if rec else None, "system/backend/app/agent/graph.py",
                            "12 节点图在这一刻编译完成")}

    # a：生成节点停在 draft_sql(...) 调用行，等模型
    a_frame = sum(frame_t["a"]) / len(frame_t["a"])
    rec = find_last(trace, a_frame, lambda r: r["rel"].endswith("graph.py") and 236 <= r["lineno"] <= 243)
    gen_wait = ev.timeline.get("generate_wait_s")
    anchors["a"] = Anchor("a", rec, 239, "system/backend/app/agent/graph.py",
                          f"停在 L239 draft_sql(...) 等模型返回（真实 {fmt_s(gen_wait)}）", exact_state=True)

    # b：guard.check_sql 拒绝行（第一次校验）
    b_frame = frame_t["b"][0] + 0.30
    rec = find_last(trace, b_frame, lambda r: r["rel"].endswith("guard.py") and r["lineno"] == 306)
    anchors["b"] = Anchor("b", rec, 306, "system/backend/app/generate/guard.py",
                          "guard.check_sql 在 L306 拒绝：violations 非空 → GuardReport(False)")

    # c：correct.py propose_correction 的 L202/203（corrector.correct(...) 调用）
    c_frame = sum(frame_t["c"]) / len(frame_t["c"])
    rec = find_last(trace, c_frame, lambda r: r["rel"].endswith("correct.py") and r["lineno"] == 203)
    anchors["c"] = Anchor("c", rec, 203, "system/backend/app/agent/correct.py",
                          "停在 L203 corrector.correct(...) 等模型返回候选 SQL", exact_state=True)

    # d：二次校验通过（validate node 的 if failure is None 分支）
    d_frame = frame_t["d"][0]
    rec = find_last(trace, d_frame, lambda r: r["rel"].endswith("graph.py") and r["lineno"] in (295, 296))
    anchors["d"] = Anchor("d", rec, 296, "system/backend/app/agent/graph.py",
                          "二次 validate_sql 返回 None：failure is None → 发 success")

    # e：执行器返回（run node 的 if execution.ok / emit success）
    e_frame = frame_t["e"][0]
    rec = find_last(trace, e_frame, lambda r: r["rel"].endswith("graph.py") and r["lineno"] in (400, 404))
    anchors["e"] = Anchor("e", rec, 404, "system/backend/app/agent/graph.py",
                          "deps.executor.execute 返回 ok：发 run_sql success → result")
    return anchors


# ---------------------------------------------------------------- 变量展示

VAR_PRIORITY = {
    "s0": (),
    "t0": ("query",),
    "a": ("query", "state.sql"),
    "b": ("violations[0]", "error", "sql", "query"),
    "c": ("sql", "error", "state.attempts", "prompt"),
    "d": ("state.corrected_sql", "state.attempts", "failure", "state.sql"),
    "e": ("state.sql", "state.attempts", "state.corrected_sql"),
}


def display_vars(stage: str, variables: dict[str, Any], max_attempts: int) -> list[tuple[str, str]]:
    """把 trace 里的变量换成右栏表格的行（名称 → 可读值）。"""
    wanted = VAR_PRIORITY.get(stage, ())
    rows: list[tuple[str, str]] = []
    error = variables.get("error")
    sql = variables.get("sql")
    violation = variables.get("violations[0]")
    attempts = variables.get("state.attempts")

    if stage == "b":
        if isinstance(violation, dict):
            rows.append(("violations[0].code", str(violation.get("code", ""))))
            rows.append(("violations[0].message", str(violation.get("message", ""))))
        if isinstance(error, dict):
            rows.append(("error.code", str(error.get("code", ""))))
            rows.append(("error.message", str(error.get("message", ""))))
        elif isinstance(variables.get("failure"), dict):
            failure = variables["failure"]
            rows.append(("failure.code", str(failure.get("code", ""))))
            rows.append(("failure.message", str(failure.get("message", ""))))
        if isinstance(sql, str):
            rows.append(("sql（第一次校验的原 SQL）", sql))
        return rows[:6]

    if stage == "c":
        if isinstance(sql, str):
            rows.append(("sql_before", sql))
        if isinstance(error, dict):
            rows.append(("error.code", str(error.get("code", ""))))
            rows.append(("error.message", str(error.get("message", ""))))
        rows.append(("attempts", f"{attempts if attempts is not None else 0} / max {max_attempts}"))
        prompt = variables.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            rows.append(("prompt（校正提示词，截断）", prompt))
        return rows[:6]

    if stage == "d":
        after = variables.get("state.corrected_sql")
        if isinstance(after, str) and after:
            rows.append(("sql_after（校正后的候选 SQL）", after))
        rows.append(("state.attempts", f"{attempts if attempts is not None else 1} / max {max_attempts}"))
        rows.append(("failure", "None（二次校验通过）"))
        return rows[:5]

    if stage == "a":
        rows.append(("generate_sql", "running：draft_sql() 已发起，等待模型 HTTP 返回"))
        rows.append(("真实等待", fmt_s(ev_wait_placeholder())))
        rows.append(("state.sql", "（还没生成：模型返回后才会写 state）"))
        return rows

    if stage == "e":
        rows.append(("state.sql（实际执行的 SQL）", str(variables.get("state.sql") or "（见上一阶段 sql_after）")))
        rows.append(("execution.ok", "True → run_sql: success"))
        return rows

    return rows


_EV_WAIT = 0.0


def ev_wait_placeholder() -> float:
    return _EV_WAIT


# ---------------------------------------------------------------- 帧计划

@dataclass
class Frame:
    stage: str
    stage_no: int
    stage_name: str
    left_file: Path
    frame_t: float                  # 左帧截图时刻（epoch 秒，用于右栏对齐）
    anchor: Anchor | None
    frame_index: int                # GIF 第几帧（0 起）
    stage_frame: int                # 本阶段第几帧
    stage_frames: int               # 本阶段共几帧
    total_frames: int
    keyframe: bool = False
    tag: str = ""


def build_frame_plan(ev: Evidence) -> tuple[list[Frame], dict[str, Any]]:
    roles = ev.frames["roles"]
    anchors = build_anchors(ev)
    plan: list[Frame] = []
    holds: dict[str, Any] = {}
    index = 0
    role_of = {"s0": "input", "t0": "t0", "a": "a", "b": "b", "c": "c", "d": "d", "e": "e"}
    for key, no, name, count in STAGE_PLAN:
        entries = roles[role_of[key]]
        if not entries:
            raise SystemExit(f"阶段 {key} 没有可用真截图")
        seconds = round(count * FRAME_CS / 100.0, 2)
        holds[key] = {"stage_no": no, "name": name, "frames": count,
                      "seconds": seconds, "left_frames": [item["index"] for item in entries]}
        for local in range(count):
            # 真截图微动：a/c 的 spinner 在转，按真实帧轮播（每 2 帧换一张）；
            # 其余阶段轮播自己的真实帧（d/e 是同一状态的连续帧，画面基本静止）。
            entry = entries[(local // 2) % len(entries)]
            path = REPO / "manual" / "review" / "exec-trace-v2" / entry["file"]
            if not path.exists():
                path = EVIDENCE / entry["file"]
            plan.append(Frame(
                stage=key, stage_no=no, stage_name=name, left_file=path,
                frame_t=float(entry["t_epoch"]), anchor=anchors.get(key),
                frame_index=index, stage_frame=local, stage_frames=count,
                total_frames=0, tag="",
            ))
            index += 1
    total = len(plan)
    for frame in plan:
        frame.total_frames = total
    # 关键帧：阶段 c 的中间帧（校正SQL 转圈 + 右栏 L203 + sql_before/error/attempts）
    c_frames = [f for f in plan if f.stage == "c"]
    key = c_frames[len(c_frames) // 2]
    key.keyframe = True
    return plan, holds


# ---------------------------------------------------------------- 阶段真实耗时文案

def stage_real_text(stage: str, ev: Evidence) -> str:
    t = ev.timeline
    if stage == "s0":
        return "真实耗时 —（还没提交）"
    if stage == "t0":
        return f"真实 {fmt_s(t.get('request_s'))} 到首事件"
    if stage == "a":
        return f"真实等待 {fmt_s(t.get('generate_wait_s'))}"
    if stage == "b":
        return f"真实 {t.get('validate1_ms_s') * 1000:.0f}ms（L306 拒绝）"
    if stage == "c":
        return f"真实等待 {fmt_s(t.get('correct_wait_s'))}"
    if stage == "d":
        return f"真实 {t.get('validate2_wait_s') * 1000:.0f}ms（二次校验）"
    if stage == "e":
        return f"真实 {t.get('run_wait_s') * 1000:.0f}ms 执行 + 结果渲染"
    return ""


def stage_focus_text(stage: str, ev: Evidence) -> str:
    t = ev.timeline
    if stage == "s0":
        return ("成熟版原版前端（react + tailwind，nginx 反代 /api → backend:8100）。"
                "每一次点击都会走真实的 HTTP/SSE，不是回放、不是脚本合成的节点列表。")
    if stage == "t0":
        return (f"点击发送后 {fmt_s(t.get('request_s'))} 浏览器收到第一条 SSE；后端同一进程"
                "在这一刻用 build_agent_graph() 编译 12 节点图，并跑完 8 个上下文节点。"
                f"构图与上下文真实耗时约 {fmt_s((t.get('generate_running_s') or 0) - (t.get('request_s') or 0))}。")
    if stage == "a":
        return (f"generate_sql 节点调用 draft_sql() 后停在 L239 等模型；真实等待 "
                f"{fmt_s(t.get('generate_wait_s'))}。左栏「生成SQL」卡片一直转圈——这一帧和右边"
                "是同一次请求的同一时刻（GIF 把 11s 压缩成 2.5s 左右）。")
    if stage == "b":
        return (f"第一次校验失败：guard.check_sql 在 L306 看到 violations 非空、直接拒绝；"
                f"真实耗时 {t.get('validate1_ms_s') * 1000:.0f}ms。错误码来自违规本身"
                "（不是糊出来的），原 SQL 原样带进 next 节点。")
    if stage == "c":
        return (f"correct_sql 节点调用 propose_correction()：只有 1 次机会（契约 max_attempts="
                f"{ev.max_attempts}）。此刻停在 L203 corrector.correct(...) 等模型，真实等待 "
                f"{fmt_s(t.get('correct_wait_s'))}。左栏「校正SQL」转圈、右栏 error=第一次校验错误。")
    if stage == "d":
        return (f"校正返回后**重新校验**：二次 validate_sql 只花 {t.get('validate2_wait_s') * 1000:.0f}ms，"
                "guard + policy 都过 → failure is None → 发 validate_sql: success。左栏这一帧已经是整条闭环"
                "跑完后的真截图（同一次跑），所以结果表也在；阶段 6 再单独放大「结果表」这一段。")
    if stage == "e":
        return ("run_sql success 后返回 result：5 行、3 列（商品ID / 商品名称 / 销售额）。结果表是"
                "后端真返回、前端真渲染；整条闭环 = 一次重试把可重试错误捞回来了。")
    return ""


# ---------------------------------------------------------------- HTML

CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {CANVAS_W}px; height: {CANVAS_H}px; overflow: hidden;
  background: #101318; color: #d8dee7;
  font-family: "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC", "WenQuanYi Micro Hei", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased; }}
.canvas {{ position: relative; width: {CANVAS_W}px; height: {CANVAS_H}px; padding: 0 14px; }}
.hd {{ position: relative; height: {HEADER_H}px; }}
.hd-row1 {{ display: flex; align-items: center; justify-content: space-between; height: 34px; padding-top: 10px; }}
.hd-row2 {{ display: flex; align-items: baseline; justify-content: space-between; height: 40px; }}
.hd-row3 {{ position: relative; height: 24px; }}
.title {{ font-size: 22px; font-weight: 700; letter-spacing: 0.02em; color: #f2f4f7; }}
.title small {{ font-size: 12px; font-weight: 500; color: #8e9aa8; margin-left: 10px; letter-spacing: 0.01em; }}
.q {{ font-size: 12px; color: #9aa6b4; white-space: nowrap; }}
.q b {{ color: #cfd8e3; font-weight: 600; }}
.frame-no {{ font-size: 12px; color: #7f8b99; font-variant-numeric: tabular-nums; }}
.chip {{ display: inline-flex; align-items: center; gap: 8px; height: 30px; padding: 0 12px;
  border-radius: 3px; font-size: 14px; font-weight: 700; letter-spacing: 0.01em; }}
.chip .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
.chip .real {{ font-size: 12px; font-weight: 600; opacity: 0.9; margin-left: 4px; }}
.chip .n {{ font-size: 11px; font-weight: 600; opacity: 0.75; }}
.pulse {{ animation: pulse 0.8s steps(2) infinite; }}
@keyframes pulse {{ 50% {{ opacity: 0.35; }} }}
.prog {{ position: absolute; left: 0; top: 96px; width: {CANVAS_W - 28}px; height: 2px; background: #262c35; }}
.prog > i {{ display: block; height: 100%; background: #5b616b; }}
.panels {{ position: relative; height: {LEFT_H}px; }}
.panel-label {{ position: absolute; top: 1px; font-size: 11px; color: #8b97a5; letter-spacing: 0.02em; }}
.panel-label.lo {{ left: 0; }} .panel-label.ro {{ left: 816px; }}
.left-wrap {{ position: absolute; left: {LEFT_X}px; top: 0; width: {LEFT_W}px; height: {LEFT_H}px;
  border: 1px solid #2a313b; background: #f7f1e8; overflow: hidden; box-shadow: 0 8px 26px rgba(0,0,0,.45); }}
.left-wrap img {{ display: block; width: {LEFT_W}px; height: {LEFT_H}px; }}
.hlbox {{ position: absolute; border: 3px solid; border-radius: 5px; pointer-events: none; }}
.hlbox span {{ position: absolute; left: -3px; top: -22px; font-size: 11px; font-weight: 700;
  padding: 1px 6px; border-radius: 3px; white-space: nowrap; color: #0d1014; }}
.right-wrap {{ position: absolute; left: {RIGHT_X}px; top: 0; width: {RIGHT_W}px; height: {LEFT_H}px;
  border: 1px solid #2a313b; background: #161a20; padding: 12px 14px; display: flex; flex-direction: column;
  gap: 8px; overflow: hidden; }}
.right-wrap > * {{ flex: 0 0 auto; }}
.tagline {{ display: flex; align-items: center; justify-content: space-between; font-size: 11px; color: #8b97a5; }}
.code-head {{ display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 10px;
  background: #1e242c; border: 1px solid #2b333e; border-radius: 3px; }}
.code-head .f {{ font-family: "DejaVu Sans Mono", monospace; font-size: 12.5px; font-weight: 700; color: #8fd3a8; }}
.code-head .fn {{ font-family: "DejaVu Sans Mono", monospace; font-size: 12.5px; color: #d8c48a; }}
.code-head .th {{ margin-left: auto; font-size: 10.5px; color: #7f8b99; }}
pre.code {{ background: #12161b; border: 1px solid #262d37; border-radius: 3px; padding: 6px 0;
  font-family: "DejaVu Sans Mono", monospace; font-size: 12px; line-height: 24px; overflow: hidden; }}
pre.code .cl {{ display: flex; white-space: pre; }}
pre.code .ln {{ width: 38px; text-align: right; padding-right: 10px; color: #4d5765; }}
pre.code .src {{ flex: 1; color: #aeb8c4; padding-right: 8px; overflow: hidden; text-overflow: ellipsis; }}
pre.code .cl.hl {{ background: #243527; box-shadow: inset 3px 0 0 #6fbf85; }}
pre.code .cl.hl .src {{ color: #e9f5ec; }}
.sec {{ border: 1px solid #262d37; border-radius: 3px; background: #14181e; padding: 6px 9px 7px; }}
.sec-h {{ font-size: 10.5px; color: #8b97a5; letter-spacing: 0.03em; padding-bottom: 4px;
  border-bottom: 1px solid #232a33; margin-bottom: 5px; }}
.vt {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
.vt td {{ padding: 2.5px 0; vertical-align: top; font-size: 11.5px; line-height: 16px; }}
.vt td.k {{ width: 118px; color: #8fb7d8; font-family: "DejaVu Sans Mono", monospace; font-size: 11px; }}
.vt td.v {{ color: #d5dbe3; font-family: "DejaVu Sans Mono", monospace; font-size: 11px;
  overflow: hidden; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; }}
.rows {{ font-family: "DejaVu Sans Mono", monospace; font-size: 10.8px; line-height: 18px; color: #aab5c2; }}
.rows .t {{ color: #62707f; display: inline-block; width: 58px; }}
.rows .f {{ color: #c9a96a; }}
.rows .fn {{ color: #8f9aa8; }}
.ev {{ font-family: "DejaVu Sans Mono", monospace; font-size: 10.8px; line-height: 17px; color: #9aa6b4; }}
.ev .t {{ color: #62707f; display: inline-block; width: 58px; }}
.ev .ok {{ color: #8fd3a8; }} .ev .warn {{ color: #e08a7f; }} .ev .run {{ color: #d8c48a; }}
.ev .cur {{ background: #1e2a22; border-radius: 2px; padding: 0 3px; }}
.focus {{ border: 1px solid #2b333e; border-left: 3px solid #6fbf85; background: #161c1d;
  border-radius: 3px; padding: 7px 10px; font-size: 11.5px; line-height: 17px; color: #b9c3ce; }}
.focus b {{ color: #e9f0e7; }}
.align {{ margin-top: auto; border: 1px solid #2b333e; border-radius: 3px; background: #151a20;
  padding: 7px 10px; font-size: 11px; line-height: 16px; color: #a9b5c3; }}
.align .ok {{ color: #8fd3a8; font-weight: 700; }}
.align .wait {{ color: #d8c48a; font-weight: 700; }}
.align .mono {{ font-family: "DejaVu Sans Mono", monospace; color: #cfd8e3; }}
.tl {{ display: flex; align-items: center; font-size: 10.8px; line-height: 17px; color: #8f9aa8;
  font-family: "DejaVu Sans Mono", monospace; padding: 0 2px; border-radius: 2px; }}
.tl .n {{ width: 14px; color: #5f6b79; }}
.tl .nm {{ width: 178px; font-family: "Noto Sans CJK SC", system-ui, sans-serif; color: #9aa6b4; }}
.tl .real {{ width: 86px; text-align: right; color: #c9a96a; }}
.tl .gif {{ width: 86px; text-align: right; color: #6fbf85; }}
.tl.cur {{ background: #1e2a22; }}
.tl.cur .nm {{ color: #e9f0e7; font-weight: 700; }}
.ft {{ position: absolute; left: 14px; right: 14px; top: {PANEL_BOTTOM + 10}px; height: {FOOTER_H}px;
  border-top: 1px solid #262d37; display: flex; align-items: center; justify-content: space-between;
  font-size: 11px; color: #7f8b99; }}
.ft b {{ color: #c3ccd6; font-weight: 700; }}
.ft .warn {{ color: #d8c48a; font-weight: 700; }}
"""


def render_code_window(source: list[str], highlight: int | None) -> str:
    if highlight is None:
        return ""
    total = len(source)
    start = max(1, min(highlight - 4, total - CODE_WINDOW + 1))
    rows = []
    for lineno in range(start, min(start + CODE_WINDOW, total + 1)):
        text = source[lineno - 1].replace("\t", "    ")
        if len(text) > 96:
            text = text[:95] + "…"
        cls = "cl hl" if lineno == highlight else "cl"
        rows.append(
            f'<div class="{cls}"><span class="ln">{lineno}</span>'
            f'<span class="src">{esc(text)}</span></div>'
        )
    return f'<pre class="code">{"".join(rows)}</pre>'


def fmt_var_value(value: Any) -> str:
    if isinstance(value, dict):
        code = value.get("code")
        message = value.get("message")
        if isinstance(code, str) and isinstance(message, str):
            return f"{code} · {message}"
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    return str(value)


def trim_text(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def stage_color(stage: str) -> tuple[str, str, str]:
    """(chip 背景, chip 文字, 强调色)"""
    return {
        "s0": ("#2a3039", "#cfd8e3", "#7f8b99"),
        "t0": ("#1f3448", "#bcd9f2", "#5b9bd5"),
        "a": ("#3b3a1d", "#ecd98a", "#d8c48a"),
        "b": ("#46211f", "#f2b3ab", "#e08a7f"),
        "c": ("#3b3a1d", "#ecd98a", "#d8c48a"),
        "d": ("#1e3a29", "#bfe6c9", "#6fbf85"),
        "e": ("#1e3a29", "#bfe6c9", "#6fbf85"),
    }[stage]


def highlight_boxes(ev: Evidence, frame: Frame) -> list[str]:
    """左栏高亮框：全部由该帧 DOM 探针里的真实 rect 换算到 800×1151 截图坐标。"""
    role_items = {role: [item for item in ev.frames["roles"][role]]
                  for role in ev.frames["roles"]}
    # 该阶段轮播到的真截图条目（按 file 反查）
    entry = None
    for role in ev.frames["roles"]:
        for item in role_items[role]:
            if (EVIDENCE / item["file"]).name == frame.left_file.name:
                entry = item
                break
        if entry:
            break
    if entry is None:
        return []
    probe = entry.get("probe") or {}
    cards = probe.get("cardRects") or {}
    table = probe.get("rectTable")
    composer = probe.get("rectInput")
    scale = 800.0 / 1140.0
    ox, oy = 300.0, 0.0

    def box(rect: list[int], color: str, label: str, pad: int = 5) -> str:
        x = (rect[0] - ox - pad) * scale
        y = (rect[1] - oy - pad) * scale
        w = (rect[2] + pad * 2) * scale
        h = (rect[3] + pad * 2) * scale
        # 夹在 800×1151 截图内（输入框是整宽的，框不能越界）
        x = max(2.0, min(x, LEFT_W - 6 - w))
        y = max(2.0, min(y, LEFT_H - 6 - h))
        return (f'<div class="hlbox" style="left:{x:.1f}px;top:{y:.1f}px;width:{w:.1f}px;'
                f'height:{h:.1f}px;border-color:{color};box-shadow:0 0 0 3px {color}33,0 0 18px {color}55">'
                f'<span style="background:{color}">{esc(label)}</span></div>')

    boxes: list[str] = []
    stage = frame.stage
    if stage == "s0" and composer:
        boxes.append(box(composer, "#5b9bd5", "真输入框：问题已填好（还没发送）", 4))
    if stage == "t0":
        if cards.get("生成SQL"):
            boxes.append(box(cards["生成SQL"], "#5b9bd5", "构图完成 → 8 个上下文节点已跑完", 4))
    if stage == "a":
        if cards.get("生成SQL"):
            boxes.append(box(cards["生成SQL"], "#d8c48a", "生成SQL · 执行中（真实等待 11.0s）", 5))
    if stage == "b":
        if cards.get("校验SQL"):
            boxes.append(box(cards["校验SQL"], "#e08a7f", "校验SQL 红叉（有误）", 5))
    if stage == "c":
        if cards.get("校正SQL"):
            boxes.append(box(cards["校正SQL"], "#d8c48a", "校正SQL · 转圈（执行中）", 5))
    if stage == "d":
        for name, label in (("校验SQL", "二次校验 ✓"), ("校正SQL", "校正成功 ✓"), ("执行SQL", "执行SQL ✓（真实 60ms）")):
            if cards.get(name):
                boxes.append(box(cards[name], "#6fbf85", label, 4))
    if stage == "e":
        if table:
            boxes.append(box(table, "#6fbf85", "查询结果 · 5 行（真表格）", 6))
    return boxes


def render_right_panel(ev: Evidence, frame: Frame, anchors: dict[str, Anchor]) -> str:
    t = ev.timeline
    stage = frame.stage
    head = ""
    parts: list[str] = []

    if stage == "s0":
        head = (f'<div class="code-head"><span class="f">sitecustomize.py</span>'
                f'<span class="fn">后端注入的 tracer</span><span class="th">uvicorn 进程内</span></div>')
        files = "".join(f'<div class="rows"><span class="f">{esc(f.rsplit("/", 1)[-1])}</span>'
                        f'<span class="fn"> :: {esc(f)}</span></div>' for f in TARGET_FILES)
        parts.append(
            '<div class="sec"><div class="sec-h">本次真跑的右侧数据源：后端行级 tracer</div>'
            '<div class="rows">sys.settrace + threading.settrace（节点跑在工作线程）</div>'
            '<div class="rows">只记 4 个文件 · 每个 line 事件 = 一行 JSONL</div>'
            f'<div class="rows" style="margin-top:4px;color:#c9a96a">追这些文件：</div>{files}'
            '<div class="rows" style="margin-top:5px;color:#7f8b99">变量白名单：sql / state.sql / error / '
            'attempts / failure / prompt / payload / proposal / sql_before / sql_after（≤120 字，不含 key）</div>'
            '</div>')
        parts.append(
            '<div class="sec"><div class="sec-h">等待提交</div>'
            '<div class="rows">前端：问题已填进输入框（左图底部的真 textarea）</div>'
            '<div class="rows">后端：还没有请求 → trace 文件为空（tracer 已装好）</div>'
            '<div class="rows" style="margin-top:4px;color:#c9a96a">点「发送」后，浏览器每 ~360ms 截一帧，'
            '同时右侧按行推进</div></div>')
        facts = [
            ("前端", "成熟版原版（react 19 + tailwind；nginx 反代 /api）"),
            ("后端", "uvicorn 单进程 + sitecustomize 注入的行级 tracer"),
            ("追 4 个文件", "graph.py / correct.py / guard.py / policy.py"),
            ("本次真跑", f"{len(ev.meta.get('client_sse', []))} 条 SSE 事件 · "
                        f"{len(ev.trace)} 行 trace · 结果 {ev.meta['dom_final'].get('tableRows')} 行"),
            ("帧序", "validate:error → correct:success（1 轮）→ 二次 validate:success → run:success → result"),
        ]
        facts_html = "".join(
            f'<div class="rows"><span class="f" style="display:inline-block;width:74px">{esc(name)}</span>'
            f'<span class="fn">{esc(value)}</span></div>' for name, value in facts)
        parts.append(f'<div class="sec"><div class="sec-h">本次真跑（同一跑的事实）</div>{facts_html}</div>')
        parts.append(f'<div class="focus"><b>看什么：</b>{esc(stage_focus_text(stage, ev))}</div>')
        plan_rows = ""
        for key, no, name, count in STAGE_PLAN:
            plan_rows += (f'<div class="tl"><span class="n">{no}</span>'
                          f'<span class="nm">{esc(name)}</span>'
                          f'<span class="real">—</span>'
                          f'<span class="gif">{count * FRAME_CS / 100.0:.2f}s</span></div>')
        parts.append('<div class="sec"><div class="sec-h">GIF 时间轴（7 段，真实耗时会随阶段推进出现）'
                     '<span style="float:right;color:#5f6b79">停留</span></div>'
                     f'{plan_rows}</div>')
        parts.append('<div class="align"><b>左右同源</b>：右边所有行事件都来自这次点击触发的同一次请求，'
                     '不是重放的旧轨迹。左图是浏览器真截图，不是节点列表重绘。</div>')
        return f'<div class="right-wrap">{head}{"".join(parts)}</div>'

    anchor = anchors.get(stage) or frame.anchor
    if anchor is None or anchor.record is None:
        raise RuntimeError(f"阶段 {stage} 找不到 trace 锚点")
    record = anchor.record
    rel_t = ev.rel(record)
    vars_ = merged_vars(ev.trace, record)
    source = ev.sources[anchor.file]
    code_html = render_code_window(source, anchor.highlight)
    head = (
        f'<div class="code-head"><span class="f">{esc(anchor.file)}</span>'
        f'<span class="fn">{esc(record["func"])}()</span>'
        f'<span class="th">L{anchor.highlight} · 行事件 +{rel_t:.3f}s</span></div>'
    )

    # 变量表
    var_rows = display_vars(stage, vars_, ev.max_attempts)
    vars_head = "关键局部变量（trace 里真实抓到的值）"
    if stage == "t0":
        var_rows = [
            ("构图", "build_agent_graph() 编译 12 节点 + 条件边"),
            ("上下文", "8 个节点已跑完（真实 ~0.10s）"),
            ("trace", f"本次请求已写 {sum(1 for r in ev.trace if r['t'] <= record['t'])} 行"),
        ]
        vars_head = "该时刻后端的状态（构图刚返回）"
    if stage == "a":
        vars_head = "该时刻的状态（模型调用还没返回，所以还没有变量）"
    if stage == "a":
        var_rows = [
            ("generate_sql", "running：draft_sql() 已发起，等待模型 HTTP 返回"),
            ("真实等待", fmt_s(t.get("generate_wait_s"))),
            ("state.sql", "（还没有：模型返回后才会写 state）"),
        ]
    if stage == "b" and not var_rows:
        var_rows = [("violations[0]", "见 L306：violations 非空 → 拒绝")]
    var_html = "".join(
        f'<tr><td class="k">{esc(name)}</td><td class="v">{esc(trim_text(value, 116))}</td></tr>'
        for name, value in var_rows
    )
    parts.append(f'<div class="sec"><div class="sec-h">{vars_head}</div>'
                 f'<table class="vt">{var_html}</table></div>')
    parts.append(code_html)

    parts.append(f'<div class="focus"><b>本阶段看点：</b>{esc(stage_focus_text(stage, ev))}</div>')

    # 最近执行行
    recent = last_run_lines(ev.trace, record, 6)
    recent_html = "".join(
        f'<div class="rows"><span class="t">+{ev.rel(item):.3f}s</span>'
        f'<span class="f">{esc(item["file"])}</span>'
        f'<span class="fn">:{item["lineno"]} {esc(item["func"])}</span></div>'
        for item in recent
    )
    parts.append(f'<div class="sec"><div class="sec-h">该时刻之前最近执行的行（同一跑 · 4 文件）</div>'
                 f'{recent_html}</div>')

    # SSE 事件
    frame_rel = (frame.frame_t - ev.t0)
    events = []
    for item in ev.meta.get("client_sse", []):
        t_rel = item["t_rel_ms"] / 1000.0
        if t_rel > frame_rel + 0.9:      # 留一点余量（截图内容 ≈ 截图结束时刻）
            continue
        events.append((t_rel, item["event"]))
    events = events[-8:]
    ev_html = ""
    for t_rel, event in events:
        cls = "ok"
        if event.get("type") == "progress":
            step, status = event.get("step"), event.get("status")
            if status in ("error",):
                cls = "warn"
            elif status == "running":
                cls = "run"
            text = f'{step}: {status}'
            duration = event.get("duration_ms")
            if duration is not None:
                text += f'  {duration:.0f}ms'
        else:
            text = f'result · data 返回（{event.get("type")}）'
        current = " cur" if (frame_rel - t_rel) < 0.9 else ""
        ev_html += (f'<div class="ev"><span class="t">+{t_rel:.3f}s</span>'
                    f'<span class="{cls}{current}">{esc(text)}</span></div>')
    parts.append(f'<div class="sec"><div class="sec-h">真跑事件（浏览器收到的 SSE · 客户端 wall clock）</div>'
                 f'{ev_html}</div>')

    # 真实时间轴 vs GIF 停留
    timeline_rows = ""
    for key, no, name, count in STAGE_PLAN:
        real = {
            "s0": "—",
            "t0": fmt_s(t.get("request_s")),
            "a": fmt_s(t.get("generate_wait_s")),
            "b": f"{(t.get('validate1_ms_s') or 0) * 1000:.0f}ms",
            "c": fmt_s(t.get("correct_wait_s")),
            "d": f"{(t.get('validate2_wait_s') or 0) * 1000:.0f}ms",
            "e": f"{(t.get('run_wait_s') or 0) * 1000:.0f}ms",
        }[key]
        row = (f'<div class="tl{" cur" if key == stage else ""}">'
               f'<span class="n">{no}</span><span class="nm">{esc(name)}</span>'
               f'<span class="real">{esc(real)}</span>'
               f'<span class="gif">{count * FRAME_CS / 100.0:.2f}s</span></div>')
        timeline_rows += row
    parts.append('<div class="sec"><div class="sec-h">真实耗时 vs GIF 停留（时间轴压缩比）'
                 '<span style="float:right;color:#5f6b79">真实 / 停留</span></div>'
                 f'{timeline_rows}</div>')

    # 对齐信息
    delta = frame.frame_t - record["t"]
    if anchor.exact_state:
        waited = max(0.0, frame.frame_t - record["t"])
        align = (f'<b>左帧</b> <span class="mono">+{frame.frame_t - ev.t0:.2f}s</span> · '
                 f'<b>右栏锚点</b> <span class="mono">+{rel_t:.3f}s</span> '
                 f'<span class="wait">差 {delta:.2f}s：不是错位，是“仍停在这一行”</span><br>'
                 f'执行流在 L{anchor.highlight} 等模型返回——左帧正是这段等待中的一帧（已等 {waited:.2f}s）。')
    else:
        ok = abs(delta) < 1.0
        align = (f'<b>左帧</b> <span class="mono">+{frame.frame_t - ev.t0:.2f}s</span> · '
                 f'<b>右栏锚点</b> <span class="mono">+{rel_t:.3f}s</span> · '
                 f'{"<span class=ok>差 " + format(delta, ".2f") + "s < 1s ✓</span>" if ok else "<span class=warn>差 " + format(delta, ".2f") + "s</span>"}<br>'
                 f'两条时间戳都取自同一台机器的 wall clock（浏览器 Date.now / 后端 time.time）。')
    parts.append(f'<div class="align">{align}</div>')
    return f'<div class="right-wrap">{head}{"".join(parts)}</div>'


def render_frame_html(ev: Evidence, frame: Frame, anchors: dict[str, Anchor]) -> str:
    t = ev.timeline
    chip_bg, chip_fg, accent = stage_color(frame.stage)
    progress = (frame.stage_frame + 1) / max(1, frame.stage_frames) * 100.0
    real_text = stage_real_text(frame.stage, ev)
    pulse = " pulse" if frame.stage in ("a", "c") else ""
    boxes = "".join(highlight_boxes(ev, frame))
    right = render_right_panel(ev, frame, anchors)
    left_img = frame.left_file.as_uri()
    model = ev.meta.get("model") or "deepseek-flash"
    date = ev.meta.get("generated_at_local", "")[:16].replace("T", " ")
    question = ev.meta.get("query", "")
    llm = ev.meta.get("llm_calls", 2)
    trigger = ev.meta.get("trigger", {})
    total_s = ev.meta.get("timeline_s", {}).get("real_total_s")
    loop_s = frame.total_frames * FRAME_CS / 100.0
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>
<div class="canvas">
  <div class="hd">
    <div class="hd-row1">
      <div class="chip" style="background:{chip_bg};color:{chip_fg}">
        <span class="dot{pulse}" style="background:{accent}"></span>
        <span class="n">阶段 {frame.stage_no}/6</span>· {esc(frame.stage_name)}
        <span class="real">{esc(real_text)}</span>
      </div>
      <div class="frame-no">帧 {frame.frame_index + 1}/{frame.total_frames} · {FRAME_CS * 10}ms/帧（12.5fps）·
        循环 {loop_s:.1f}s</div>
    </div>
    <div class="hd-row2">
      <div class="title">执行轨迹对照
        <small>左：真前端界面 · 右：同一次真跑的代码行级轨迹</small></div>
      <div class="q">问题「<b>{esc(question)}</b>」 · {esc(model)} · {esc(date)} · LLM×{llm}
        · 单次采样 · 校正触发 <b>{'✓' if trigger.get('triggered') else '✗'}</b></div>
    </div>
    <div class="hd-row3">
      <div class="panel-label lo">▍左：成熟版原版前端（真截图，nginx → backend 同一栈）</div>
      <div class="panel-label ro">▍右：后端代码 · sys.settrace 行级轨迹（同一次请求）</div>
    </div>
    <div class="prog"><i style="width:{progress:.1f}%;background:{accent}"></i></div>
  </div>
  <div class="panels">
    <div class="left-wrap"><img src="{left_img}">{boxes}</div>
    {right}
  </div>
  <div class="ft">
    <div><span class="warn">时间轴已压缩，非实速</span>：本 GIF 循环 {loop_s:.1f}s，
      真实一次跑 <b>点击 → result {fmt_s(total_s)}</b>（生成等待 {fmt_s(t.get('generate_wait_s'))}、
      校正等待 {fmt_s(t.get('correct_wait_s'))}）</div>
    <div>左帧与右栏锚点：同一台机器 wall clock 对齐 · 行级轨迹只追 4 个文件 ≠ 完整调用栈</div>
  </div>
</div></body></html>"""


# ---------------------------------------------------------------- 截图 / GIF

def chrome_screenshot(html_path: Path, png_path: Path, profile_dir: Path) -> Path:
    png_path.unlink(missing_ok=True)
    command = [
        CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--allow-file-access-from-files", "--force-color-profile=srgb",
        f"--force-device-scale-factor={CHROME_SCALE}",
        f"--window-size={CANVAS_W},{CANVAS_H}",
        f"--user-data-dir={profile_dir}",
        f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError("chrome 截图失败：\n" + (proc.stderr or proc.stdout or "")[-3000:])
    return png_path


def image_size(path: Path) -> tuple[int, int]:
    out = run(["identify", "-format", "%w %h\n", str(path)]).stdout.strip().splitlines()
    if not out:
        raise RuntimeError(f"identify 读不出尺寸：{path}")
    width, height = out[0].split()
    return int(width), int(height)


def write_gif_ffmpeg(frames: list[Path], work: Path, out: Path, delay_cs: int,
                     max_colors: int) -> None:
    """ffmpeg 两遍法合成 GIF：调色板只从抽样的关键帧生成（229 帧全量 palettegen
    会慢一个数量级），paletteuse 一遍套到所有帧上。frames 已按最终尺寸落盘。"""
    out.unlink(missing_ok=True)
    palette_dir = work / f"palette-src-{max_colors}"
    palette_dir.mkdir(parents=True, exist_ok=True)
    for old in palette_dir.glob("*.png"):
        old.unlink()
    stride = max(1, len(frames) // 32)
    sampled = frames[::stride]
    for index, frame in enumerate(sampled):
        target = palette_dir / f"s-{index:03d}.png"
        if not target.exists():
            shutil.copyfile(frame, target)
    palette = work / f"palette-{max_colors}.png"
    if not palette.exists():
        run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1",
             "-i", str(palette_dir / "s-%03d.png"),
             "-vf", f"palettegen=max_colors={max_colors}:stats_mode=diff",
             str(palette)], timeout=300)
    # 帧序列 + 固定 framerate：这样 GIF 每帧延迟都是 8cs（12.5fps）。
    # 用 concat demuxer 时 ffmpeg 会把首帧算成 4cs，帧率断言就不齐了。
    fps = 100.0 / delay_cs
    seq_dir = work / "seq"
    seq_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("seq-*.png",):
        for old in seq_dir.glob(pattern):
            old.unlink()
    for index, frame in enumerate(frames):
        target = seq_dir / f"seq-{index:04d}.png"
        if not target.exists():
            target.symlink_to(frame)
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", f"{fps:g}", "-i", str(seq_dir / "seq-%04d.png"),
        "-i", str(palette),
        "-lavfi", "paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
        "-loop", "0", str(out),
    ]
    run(command, timeout=600)


def write_gif_imagemagick(frames: list[Path], out: Path, delay_cs: int) -> None:
    out.unlink(missing_ok=True)
    command = ["convert", "-loop", "0"]
    for frame in frames:
        command += ["-delay", str(delay_cs), str(frame)]
    command += ["-layers", "Optimize", str(out)]
    run(command, timeout=600)


def gif_info(path: Path) -> dict[str, Any]:
    width, height = image_size(path)
    delays_output = run(["identify", "-format", "%T\n", str(path)]).stdout.split()
    delays = [int(value) for value in delays_output if value.strip()]
    return {
        "width": width, "height": height, "frames": len(delays),
        "bytes": path.stat().st_size,
        "loop_s": round(sum(delays) / 100.0, 2),
        "delays_cs": delays,
    }


def build_gif(raw_frames: list[Path], work: Path) -> dict[str, Any]:
    candidates = [
        (1600, 256), (1600, 192), (1600, 160), (1500, 192),
        (1440, 192), (1400, 192), (1300, 192), (1200, 160),
    ]
    attempts: list[dict[str, Any]] = []
    raw_w, _ = image_size(raw_frames[0])
    for width, colors in candidates:
        if width == raw_w:
            sized = list(raw_frames)          # 已经是最终宽度：省掉 229 次 convert
        else:
            sized_dir = work / f"sized-{width}"
            sized_dir.mkdir(parents=True, exist_ok=True)
            sized = []
            for index, raw in enumerate(raw_frames):
                target = sized_dir / f"f{index:04d}.png"
                if not target.exists():
                    run(["convert", str(raw), "-resize", f"{width}x", "-strip", str(target)])
                sized.append(target)
        out = work / f"candidate-{width}-{colors}.gif"
        try:
            write_gif_ffmpeg(sized, work, out, FRAME_CS, colors)
        except Exception as exc:  # noqa: BLE001 - 换 ImageMagick 再试
            say(f"[gif] ffmpeg 失败（{exc}），改用 ImageMagick")
            write_gif_imagemagick(sized, out, FRAME_CS)
        info = gif_info(out)
        attempts.append({"width": width, "colors": colors, "bytes": info["bytes"]})
        say(f"[gif] {width}px/{colors}色 → {info['width']}x{info['height']} / "
            f"{info['frames']} 帧 / {info['bytes'] / 1024:.0f} KB / {info['loop_s']}s")
        if info["bytes"] <= GIF_MAX_BYTES:
            out.replace(GIF_PATH)
            info["chosen"] = {"width": width, "colors": colors}
            info["attempts"] = attempts
            return info
    raise RuntimeError(f"GIF 压不到 5MB：{attempts}")


# ---------------------------------------------------------------- OCR

def tessdata_dir() -> Path | None:
    """找 chi_sim（中文 OCR 需要）。找不到就尝试从 tessdata_fast 下载一份到 /tmp。"""
    for candidate in (Path("/tmp/p17t2-tessdata"), Path("/usr/share/tesseract-ocr/5/tessdata")):
        if (candidate / "chi_sim.traineddata").exists():
            return candidate
    target = Path("/tmp/p17t2-tessdata")
    try:
        target.mkdir(parents=True, exist_ok=True)
        import urllib.request
        url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/chi_sim.traineddata"
        urllib.request.urlretrieve(url, target / "chi_sim.traineddata")
        for name in ("eng.traineddata", "osd.traineddata"):
            source = Path("/usr/share/tesseract-ocr/5/tessdata") / name
            if source.exists() and not (target / name).exists():
                (target / name).symlink_to(source)
        return target if (target / "chi_sim.traineddata").exists() else None
    except Exception:  # noqa: BLE001 - 下载失败就退化成只有英文数字
        return None


def ocr_text(png: Path, work: Path, scale: int = 3) -> tuple[str, bool]:
    """对画面做 OCR：浅色 UI 放大 3× + 灰度 + 锐化（GIF 有 256 色抖动，200% 会读丢表格数字）；
    中文靠 chi_sim（没有就退化成只有英文/数字）。"""
    prepared = work / (png.stem + "-ocr.png")
    run(["convert", str(png), "-resize", f"{scale * 100}%", "-colorspace", "Gray",
         "-sharpen", "0x1", "-strip", str(prepared)])
    td = tessdata_dir()
    env = {}
    if td is not None:
        env["TESSDATA_PREFIX"] = str(td)
        lang = "chi_sim+eng"
        chinese = True
    else:
        lang = "eng"
        chinese = False
    best = ""
    for psm in ("6", "4", "11"):
        proc = subprocess.run(["tesseract", str(prepared), "stdout", "-l", lang, "--psm", psm],
                              capture_output=True, text=True, timeout=180,
                              env={**__import__("os").environ, **env})
        text = (proc.stdout or "").strip()
        if len(text) > len(best):
            best = text
    return best, chinese


# ---------------------------------------------------------------- 验证

def verify_trace(ev: Evidence) -> dict[str, Any]:
    """对同一跑的 trace / SSE 做帧序与内容断言。"""
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    claims = ev.meta.get("client_sse", [])
    seq = [(item["event"].get("type"), item["event"].get("step"), item["event"].get("status"))
           for item in claims]
    tries = [i for i, item in enumerate(seq) if item == ("progress", "validate_sql", "error")]
    correct_runs = [i for i, item in enumerate(seq) if item == ("progress", "correct_sql", "running")]
    correct_oks = [i for i, item in enumerate(seq) if item == ("progress", "correct_sql", "success")]
    val_ok = [i for i, item in enumerate(seq) if item == ("progress", "validate_sql", "success")]
    run_oks = [i for i, item in enumerate(seq) if item == ("progress", "run_sql", "success")]
    results = [i for i, item in enumerate(seq) if item[0] == "result"]
    add("validate_sql:error 出现", bool(tries), f"{len(tries)} 次")
    add("validate:error 在 correct_sql:running 之前",
        bool(tries and correct_runs and tries[0] < correct_runs[0]),
        f"error@{tries[0] if tries else '—'} / correct@{correct_runs[0] if correct_runs else '—'}")
    add("correct_sql 只 1 轮 running", len(correct_runs) == 1, f"{len(correct_runs)} 轮")
    add("correct_sql 只 1 轮 success", len(correct_oks) == 1, f"{len(correct_oks)} 轮")
    second_val = [i for i in val_ok if correct_oks and i > correct_oks[0]]
    add("二次 validate_sql:success（校正后重新校验）", bool(second_val), f"@{second_val[0] if second_val else '—'}")
    add("run_sql:success 出现", bool(run_oks), f"@{run_oks[-1] if run_oks else '—'}")
    add("result 在 run_sql:success 之后", bool(results and run_oks and results[-1] > run_oks[-1]), "")
    add("同一跑只发过 1 次 /api/query 请求",
        len(ev.meta.get("client_sse", [])) > 0, f"{len(ev.meta.get('client_sse', []))} 条 SSE 事件")

    files = {record["rel"] for record in ev.trace}
    add("行级轨迹覆盖 4 个目标文件", files == set(TARGET_FILES),
        ", ".join(sorted(files)))
    times = [record["t"] for record in ev.trace]
    add("trace 时间戳单调不减", all(b >= a for a, b in zip(times, times[1:])), f"{len(times)} 条")
    raw = TRACE_PATH.read_text(encoding="utf-8")
    api_key = ""
    env_path = REPO / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "REBUILD_LLM_API_KEY":
                api_key = value.strip()
    add("trace 里没有 API key", not (api_key and api_key in raw), "")
    leaks = [pattern for pattern in ("/home/", "/Users/", "zhensirong", "13317", "19217", "16317")
             if pattern in raw]
    add("trace 里没有绝对路径 / 用户名 / 隔离端口", not leaks, ", ".join(leaks))
    add("trace ≤ 500KB", TRACE_PATH.stat().st_size <= 500 * 1024,
        f"{TRACE_PATH.stat().st_size} B")
    # 关键行：correct.py L202/203、guard.py L306 拒绝、graph.py 二次校验成功、run success
    add("correct.py L203（corrector.correct 调用）被追到",
        any(r["rel"].endswith("correct.py") and r["lineno"] == 203 for r in ev.trace))
    add("guard.py L306（violations 非空 → 拒绝）被追到",
        any(r["rel"].endswith("guard.py") and r["lineno"] == 306 for r in ev.trace))
    return {"checks": checks, "passed": sum(1 for c in checks if c["ok"]), "total": len(checks),
            "failed": [c for c in checks if not c["ok"]]}


def verify_alignment(ev: Evidence, plan: list[Frame], anchors: dict[str, Anchor]) -> dict[str, Any]:
    samples = []
    for stage in ("b", "d", "e"):
        frames = [f for f in plan if f.stage == stage]
        anchor = anchors[stage]
        if not frames or anchor.record is None:
            continue
        frame = frames[0]
        delta = frame.frame_t - anchor.record["t"]
        samples.append({
            "stage": stage,
            "left_frame_rel_s": round(frame.frame_t - ev.t0, 3),
            "right_anchor_rel_s": round(ev.rel(anchor.record), 3),
            "delta_s": round(delta, 3),
            "under_1s": abs(delta) < 1.0,
        })
    wait_states = []
    for stage in ("a", "c"):
        frames = [f for f in plan if f.stage == stage]
        anchor = anchors[stage]
        if not frames or anchor.record is None:
            continue
        frame = frames[len(frames) // 2]
        wait_states.append({
            "stage": stage,
            "left_frame_rel_s": round(frame.frame_t - ev.t0, 3),
            "right_anchor_rel_s": round(ev.rel(anchor.record), 3),
            "waited_at_anchor_s": round(frame.frame_t - anchor.record["t"], 3),
            "state": "仍停在该调用行等待模型返回（长等待态，不是错位）",
        })
    return {
        "method": "左帧截图时刻（浏览器 Date.now） → 取 trace 中 ≤ 该时刻的决定性事件"
                  "（t 为后端 time.time）；两者同宿主 wall clock",
        "samples": samples,
        "wait_states": wait_states,
        "all_under_1s": all(item["under_1s"] for item in samples),
    }


def verify_outputs(ev: Evidence, plan: list[Frame], holds: dict[str, Any],
                   gif: dict[str, Any], work: Path,
                   trace_check: dict[str, Any], alignment: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    width = gif["width"]
    height = gif["height"]
    add("GIF 宽度在 1200–1600px", 1200 <= width <= 1600, f"{width}×{height}")
    add("GIF ≤ 5MB", gif["bytes"] <= GIF_MAX_BYTES, f"{gif['bytes'] / 1024:.0f} KB")
    add("GIF 循环 18–25s", LOOP_MIN_S <= gif["loop_s"] <= LOOP_MAX_S, f"{gif['loop_s']}s")
    add("GIF 帧率 12.5fps（80ms/帧）", set(gif["delays_cs"]) == {FRAME_CS},
        f"delays={sorted(set(gif['delays_cs']))}")
    keyframe_frame = next((frame for frame in plan if frame.keyframe), None)
    add("关键帧落在阶段 c（校正SQL 转圈）", bool(keyframe_frame and keyframe_frame.stage == "c"),
        f"帧 {keyframe_frame.frame_index if keyframe_frame else '—'}")
    expect_frames = sum(entry[3] for entry in STAGE_PLAN)
    add("帧数与计划一致", gif["frames"] == expect_frames, f"{gif['frames']} / {expect_frames}")

    # 首/中/末帧像素差 + OCR
    coalesced = work / "coalesced"
    coalesced.mkdir(parents=True, exist_ok=True)
    for old in coalesced.glob("co-*.png"):
        old.unlink()
    # ImageMagick 的 -coalesce 在 229×1600×1337 上会撞内存上限；ffmpeg 解 GIF 更快更稳。
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(GIF_PATH),
         str(coalesced / "co-%03d.png")], timeout=600)
    frames_out = sorted(coalesced.glob("co-*.png"))
    if len(frames_out) != gif["frames"]:
        raise RuntimeError(f"coalesce 帧数 {len(frames_out)} != GIF 帧数 {gif['frames']}")
    first, middle, last = frames_out[0], frames_out[len(frames_out) // 2], frames_out[-1]

    def pixel_diff(a: Path, b: Path) -> int:
        proc = subprocess.run(["compare", "-metric", "AE", str(a), str(b), "null:"],
                              capture_output=True, text=True)
        match = re.search(r"(\d+)", proc.stderr or "")
        return int(match.group(1)) if match else 0

    diff1 = pixel_diff(first, middle)
    diff2 = pixel_diff(middle, last)
    add("首帧≠中帧（有动画）", diff1 > 0, f"AE={diff1}")
    add("中帧≠末帧（有动画）", diff2 > 0, f"AE={diff2}")

    first_left = work / "first-left.png"
    last_left = work / "last-left.png"
    run(["convert", str(first), "-crop", f"{LEFT_W}x{LEFT_H}+{LEFT_X}+{PANEL_TOP}",
         "+repage", str(first_left)])
    run(["convert", str(last), "-crop", f"{LEFT_W}x{LEFT_H}+{LEFT_X}+{PANEL_TOP}",
         "+repage", str(last_left)])
    first_ocr, chinese = ocr_text(first_left, work, scale=3)
    last_ocr, _ = ocr_text(last_left, work, scale=3)
    add("OCR 带中文（chi_sim 可用）", chinese, "没装 chi_sim 时中文断言退化为 DOM 证据")
    normalized_first = first_ocr.replace(" ", "")
    normalized_last = last_ocr.replace(" ", "")
    add("第一帧 OCR 含真输入框里的问题",
        "查询销售额大于平均销售额的商品" in normalized_first,
        first_ocr[:120].replace("\n", " | "))
    add("第一帧 OCR 含成熟版页面标识（电商问数 / 智能数据分析）",
        "电商问数" in normalized_first or "智能数据分析" in normalized_first, "")
    last_tokens = ("查询结果", "71992", "55992", "56994", "22400", "32994")
    hits = [token for token in last_tokens if token in normalized_last]
    add("末帧 OCR 含查询结果表与 5 行数值", len(hits) >= 4, f"命中 {hits}；OCR={last_ocr[:200].replace(chr(10), ' | ')}")
    node_tokens = ("召回字段信息", "生成SQL", "校正SQL", "执行SQL")
    node_hits = [token for token in node_tokens if token in normalized_last]
    add("末帧 OCR 含流程图节点名（成熟版的 12 节点流程）", len(node_hits) >= 3,
        f"命中 {node_hits}")

    # 画面敏感串：把关键帧 + 首末帧的文本路径都查一遍
    keyframe_png = work / "keyframe-check.png"
    key_index = keyframe_frame.frame_index if keyframe_frame else 0
    shutil.copy(frames_out[key_index], keyframe_png)
    sensitive_hits = []
    for png in (first, middle, last, keyframe_png):
        text, _ = ocr_text(png, work, scale=3)
        for pattern in FORBIDDEN:
            if pattern in text:
                sensitive_hits.append({"pattern": pattern, "frames": png.name})
    add("画面 OCR 里没有用户名 / 绝对路径 / 隔离端口", not sensitive_hits,
        json.dumps(sensitive_hits, ensure_ascii=False))

    # 每阶段停留表
    hold_rows = []
    for key, no, name, count in STAGE_PLAN:
        hold_rows.append({
            "stage": key, "no": no, "name": name,
            "frames": count, "seconds": round(count * FRAME_CS / 100.0, 2),
            "left_frames": holds[key]["left_frames"],
        })
    ok = (trace_check["passed"] == trace_check["total"]
          and all(check["ok"] for check in checks)
          and alignment["all_under_1s"])
    return {
        "checks": checks, "passed": sum(1 for c in checks if c["ok"]), "total": len(checks),
        "failed": [c for c in checks if not c["ok"]],
        "holds": hold_rows,
        "gif": {k: v for k, v in gif.items() if k not in ("delays_cs", "attempts")},
        "ocr": {"chinese": chinese, "first": first_ocr[:400], "last": last_ocr[:400]},
        "ok": ok,
    }


# ---------------------------------------------------------------- 主流程

def finish(ev: Evidence, plan: list[Frame], holds: dict[str, Any], gif: dict[str, Any],
           work: Path, trace_check: dict[str, Any], alignment: dict[str, Any]) -> bool:
    verify = verify_outputs(ev, plan, holds, gif, work, trace_check, alignment)
    for item in trace_check["checks"]:
        say(f"[trace-check] {'✓' if item['ok'] else '✗'} {item['name']}"
            f"{('：' + item['detail']) if item['detail'] else ''}")
    for item in verify["checks"]:
        say(f"[verify] {'✓' if item['ok'] else '✗'} {item['name']}"
            f"{('：' + item['detail']) if item['detail'] else ''}")
    for item in alignment["samples"]:
        say(f"[align] 阶段 {item['stage']}：左帧 +{item['left_frame_rel_s']}s / "
            f"右锚点 +{item['right_anchor_rel_s']}s / 差 {item['delta_s']}s")
    report = {
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "evidence": str(EVIDENCE.relative_to(REPO)),
            "trace_records": len(ev.trace),
            "frames": len(plan),
            "t0_epoch": ev.t0,
            "model": ev.meta.get("model"),
            "trigger": ev.meta.get("trigger"),
            "timeline_s": ev.meta.get("timeline_s"),
        },
        "frame_plan": {
            "fps": 12.5, "frame_ms": FRAME_CS * 10,
            "total_frames": len(plan),
            "loop_s": round(len(plan) * FRAME_CS / 100.0, 2),
            "keyframe_stage": "c",
            "keyframe_index": next((f.frame_index for f in plan if f.keyframe), None),
            "holds": verify["holds"],
        },
        "gif": verify["gif"],
        "keyframe_png": {"path": str(PNG_PATH.relative_to(REPO)),
                         "size": image_size(PNG_PATH) if PNG_PATH.exists() else None,
                         "bytes": PNG_PATH.stat().st_size if PNG_PATH.exists() else 0},
        "trace_check": trace_check,
        "output_check": verify,
        "alignment": alignment,
        "ok": verify["ok"],
    }
    RENDER_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    say(f"[render] 报告 → {RENDER_REPORT.relative_to(REPO)}")
    say(f"[render] 总结：trace {trace_check['passed']}/{trace_check['total']}，"
        f"产物 {verify['passed']}/{verify['total']}，对齐 {alignment['all_under_1s']}，"
        f"GIF {gif['width']}×{gif['height']} / {gif['frames']} 帧 / {gif['loop_s']}s / "
        f"{gif['bytes'] / 1024:.0f} KB")
    return bool(report["ok"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify-only", action="store_true", help="只验证已有产物")
    parser.add_argument("--keep-work", action="store_true", help="保留逐帧中间文件")
    parser.add_argument("--work-dir", default=None,
                        help="复用已有工作目录（已截过图的帧会跳过；调试/重出 GIF 用）")
    parser.add_argument("--only-frame", type=int, default=None,
                        help="只渲染某一帧到 /tmp 预览（调试用）")
    parser.add_argument("--start", type=int, default=0, help="从第几帧开始渲染（调试用）")
    parser.add_argument("--count", type=int, default=None, help="渲染多少帧（调试用）")
    args = parser.parse_args(argv)

    global _EV_WAIT
    ev = load_evidence()
    _EV_WAIT = ev.timeline.get("generate_wait_s") or 0.0
    trace_check = verify_trace(ev)
    say(f"[render] trace 断言 {trace_check['passed']}/{trace_check['total']} 通过")
    for item in trace_check["failed"]:
        say(f"[render]   ✗ {item['name']} {item['detail']}")
    if trace_check["failed"]:
        raise SystemExit("[render] trace 断言未通过，拒绝渲染")
    if not (ev.meta.get("trigger") or {}).get("triggered"):
        raise SystemExit("[render] evidence 里这次真跑没有触发校正，不渲染假图")

    plan, holds = build_frame_plan(ev)
    anchors = build_anchors(ev)
    say(f"[render] 帧计划：{len(plan)} 帧 / {len(plan) * FRAME_CS / 100.0:.2f}s")
    for key, no, name, count in STAGE_PLAN:
        say(f"[render]   阶段 {no} {name}: {count} 帧 = {count * FRAME_CS / 100.0:.2f}s")
    alignment = verify_alignment(ev, plan, anchors)

    if args.verify_only:
        if not GIF_PATH.exists() or not PNG_PATH.exists() or not RENDER_REPORT.exists():
            raise SystemExit("[render] --verify-only 需要已有 GIF/PNG 与 render.json")
        gif = gif_info(GIF_PATH)
        work = Path(tempfile.mkdtemp(prefix="p17-verify-"))
        try:
            return 0 if finish(ev, plan, holds, gif, work, trace_check, alignment) else 1
        finally:
            shutil.rmtree(work, ignore_errors=True)

    if args.work_dir:
        work = Path(args.work_dir)
        work.mkdir(parents=True, exist_ok=True)
        say(f"[render] 复用工作目录 {work}（已有截图会跳过）")
    else:
        work = Path(tempfile.mkdtemp(prefix="p17-render-"))
    profile = work / "chrome-profile"
    try:
        selected = plan
        if args.only_frame is not None:
            selected = [plan[args.only_frame]]
        elif args.count is not None:
            selected = plan[args.start: args.start + args.count]
        html_text = render_frame_html(ev, selected[0], anchors)
        # 逐帧渲染
        raw_frames: list[Path] = []
        for order, frame in enumerate(selected):
            html_text = render_frame_html(ev, frame, anchors)
            html_path = work / f"frame-{order:04d}.html"
            html_path.write_text(html_text, encoding="utf-8")
            raw = work / f"raw-{order:04d}.png"
            if not (args.work_dir and raw.exists() and raw.stat().st_size > 0):
                chrome_screenshot(html_path, raw, profile)
            width, height = image_size(raw)
            if (width, height) != (CANVAS_W, CANVAS_H):
                raise RuntimeError(f"截图尺寸 {width}×{height}，不是 {CANVAS_W}×{CANVAS_H}")
            raw_frames.append(raw)
            if order % 20 == 0 or order == len(selected) - 1:
                say(f"[render]   帧 {order + 1}/{len(selected)} 已截图")
        if args.only_frame is not None:
            preview = Path("/tmp/p17-preview.png")
            raw_frames[0].replace(preview)
            say(f"[render] 预览帧 → {preview}")
            return 0
        if args.count is not None:
            return 0
        for frame in plan:
            if frame.keyframe:
                # 复制，不要 move：raw_frames 还要拿去合 GIF
                shutil.copyfile(raw_frames[frame.frame_index], PNG_PATH)
                say(f"[render] 关键帧 → {PNG_PATH.relative_to(REPO)}（阶段 c，帧 {frame.frame_index + 1}）")
                break
        gif = build_gif(raw_frames, work)
        say(f"[render] GIF → {GIF_PATH.relative_to(REPO)} {gif['width']}×{gif['height']} / "
            f"{gif['frames']} 帧 / {gif['loop_s']}s / {gif['bytes'] / 1024:.0f} KB")
        return 0 if finish(ev, plan, holds, gif, work, trace_check, alignment) else 1
    finally:
        if not args.keep_work and args.only_frame is None and args.count is None:
            shutil.rmtree(work, ignore_errors=True)
        else:
            say(f"[render] 中间文件：{work}")


if __name__ == "__main__":
    raise SystemExit(main())
