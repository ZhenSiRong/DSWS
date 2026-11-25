#!/usr/bin/env python3
"""task.py —— 任务生命周期 chokepoint CLI（台账唯一合法写入口）

真相源：workflows/ledger.yaml。规格见 workflows/task-lifecycle.md。
门禁与 git 解耦：每次 start/done 都触发，不依赖 commit。

命令：
    add <id> --title T [--group G] [--deps a,b]   注册 todo（拒环/拒重复）
    start <id> [--agent A]                        依赖闸 → 建 worktree → doing
    done <id> [--force --reason R]                review 门禁；--force 留痕越过
    verdict <id> [--report PATH]                  读报告末行 VERDICT 定 done/打回
    block <id> --reason R / unblock <id>          卡住/解卡（旁注）
    fail <id> --reason R                          失败 → todo（保留 worktree）
    reopen <id> --reason R                        done → doing
    evidence <id> --kind file|cmd (--path P|--run R) [--criterion C] | --clear   钉/清证据
    list [--ready] [--status S] / show <id>       台账视图
    board [--out PATH] [--no-check]               台账 → 单文件浏览器看板（离线 HTML + meta）
    check [--quick]                               一致性校验（漂移退码 1）
    render [--width N]                            从 ledger 投影甘特 mermaid+PNG+meta
    migrate-from-gantt                            一次性从 14 文档灌入现有任务

退出码：0 成功；1 门禁拒绝/漂移/blocker；2 review 待派（done 后需 verdict）。
依赖：PyYAML（唯一第三方依赖）；渲染甘特另需 google-chrome + ImageMagick + 本地 mermaid.min.js；
board 只写静态 HTML（无需 chrome/网络）。
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "workflows" / "ledger.yaml"
REVIEWS = REPO / "workflows" / "reviews"
DEFAULT_DOC = REPO / "workflows" / "gantt.md"
DEFAULT_PNG = REPO / "workflows" / "gantt.png"
AGENTS = ["opencode2", "codebuddy", "qoder"]
TAGS = {"done", "active", "crit", "milestone"}


# --------------------------------------------------------------------------- #
# 基础 IO
# --------------------------------------------------------------------------- #
def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="minutes")


def host() -> str:
    return platform.node()


def load_ledger() -> dict:
    if not LEDGER.exists():
        return {"meta": {"host": host(), "repo": str(REPO), "updated_at": now()}, "tasks": []}
    data = yaml.safe_load(LEDGER.read_text(encoding="utf-8")) or {}
    data.setdefault("meta", {})
    data.setdefault("tasks", [])
    return data


def save_ledger(data: dict) -> None:
    data["meta"]["updated_at"] = now()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def tmap(data: dict) -> dict:
    return {t["id"]: t for t in data["tasks"]}


def get_task(data: dict, tid: str) -> dict:
    t = tmap(data).get(tid)
    if t is None:
        raise SystemExit(f"未知任务 id：{tid}（先 add，或 list 查看）")
    return t


def ledger_sha() -> str:
    return hashlib.sha256(LEDGER.read_bytes()).hexdigest()


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def git_time(path: Path) -> str | None:
    p = git("log", "-1", "--format=%cI", "--", str(path))
    s = p.stdout.strip()
    return s or None


# --------------------------------------------------------------------------- #
# 依赖闸 / 环检测
# --------------------------------------------------------------------------- #
def missing_deps(data: dict, task: dict) -> list[str]:
    tm = tmap(data)
    out = []
    for d in task.get("depends_on") or []:
        dt = tm.get(d)
        if dt is None or dt.get("status") != "done":
            out.append(d)
    return out


def has_cycle(tasks: list[dict]) -> bool:
    graph = {t["id"]: list(t.get("depends_on") or []) for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph}

    def dfs(u: str) -> bool:
        color[u] = GRAY
        for v in graph.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False

    return any(color[k] == WHITE and dfs(k) for k in graph)


# --------------------------------------------------------------------------- #
# worktree 绑定（Orca 优先，git 降级）
# --------------------------------------------------------------------------- #
def orca_available() -> bool:
    try:
        p = subprocess.run(
            ["orca-ide", "orchestration", "run-current", "--json"],
            capture_output=True, text=True, timeout=20,
        )
        return bool(p.stdout.strip()) and yaml.safe_load(p.stdout).get("ok") is True
    except Exception:
        return False


def current_branch() -> str:
    return git("branch", "--show-current").stdout.strip() or "main"


def bind_worktree(task: dict, agent: str | None) -> None:
    tid = task["id"]
    branch = f"task/{tid}"
    path = REPO.parent / f"{REPO.name}-{tid}"
    use_orca = orca_available()
    session_id = None
    if use_orca:
        chosen = agent or AGENTS[0]
        p = subprocess.run(
            ["orca-ide", "orchestration", "worker-start", "--task", tid,
             "--worktree", "new-child", "--agent", chosen,
             "--base-branch", current_branch(), "--json"],
            capture_output=True, text=True, timeout=120,
        )
        try:
            rec = yaml.safe_load(p.stdout) or {}
            wt = rec.get("worktree") or rec.get("worktreePath") or rec.get("path")
            if isinstance(wt, dict):
                wt = wt.get("path")
            path = Path(wt) if wt else path
            session_id = rec.get("dispatchId") or rec.get("sessionId") or rec.get("id")
            agent = chosen
        except Exception:
            use_orca = False  # 解析失败 → 降级 git
    if not use_orca:
        agent = agent or "manual"
        session_id = f"manual-{tid}"
        if not path.exists():
            br = git("branch", "--list", branch)
            if br.stdout.strip():
                p = git("worktree", "add", str(path), branch)
            else:
                p = git("worktree", "add", str(path), "-b", branch)
            if p.returncode != 0:
                raise SystemExit(f"git worktree 创建失败：{p.stderr.strip() or p.stdout.strip()}")
    task["worktree"] = str(path)
    task["branch"] = branch
    task["agent"] = agent
    task["session_id"] = str(session_id)
    task["provenance"] = f"{host()}@{path}&{agent} -s {session_id}"


# --------------------------------------------------------------------------- #
# review 门禁（两段式：done 备 brief → verdict 定案）
# --------------------------------------------------------------------------- #
def pick_reviewer(task: dict, orca: bool) -> str:
    if not orca:
        return "builtin-codereview"
    for a in AGENTS:
        if a != task.get("agent"):
            return a
    return AGENTS[0]


def write_review_request(task: dict, reviewer: str) -> Path:
    REVIEWS.mkdir(parents=True, exist_ok=True)
    req = REVIEWS / f"{task['id']}.request.md"
    ev = "\n".join(
        f"- [{e.get('kind')}] {e.get('path') or e.get('run')} — 判据：{e.get('criterion') or '存在/exit 0'}"
        for e in task.get("evidence") or []
    ) or "- （无声明证据，审实际产物）"
    req.write_text(
        f"# Review 请求 · {task['id']} {task.get('title', '')}\n\n"
        f"- worktree: `{task.get('worktree')}`\n- branch: `{task.get('branch')}`\n"
        f"- 干活 agent: {task.get('agent')}\n- reviewer: {reviewer}\n\n"
        f"## 声明证据（先核这些是否真成立）\n{ev}\n\n"
        f"## 审查顺序（丙→乙→甲）\n"
        f"1. 丙：上面每条证据/判据是否真成立（声明→现场）。\n"
        f"2. 乙：页面/文档改动是否正确（练本页、规划文档）。\n"
        f"3. 甲：代码改动是否有严重错误（按需）。\n\n"
        f"## 产出\n把结论写进 `workflows/reviews/{task['id']}.md`，"
        f"**最后一非空行**必须是 `VERDICT: pass` 或 `VERDICT: blocker`（blocker 时上文列具体问题）。\n",
        encoding="utf-8",
    )
    return req


def parse_verdict(report: Path) -> str | None:
    if not report.exists():
        return None
    for line in reversed(report.read_text(encoding="utf-8").splitlines()):
        m = re.match(r"\s*VERDICT:\s*(pass|blocker)\s*$", line, re.I)
        if m:
            return m.group(1).lower()
    return None


# --------------------------------------------------------------------------- #
# 命令实现
# --------------------------------------------------------------------------- #
def cmd_add(args) -> int:
    data = load_ledger()
    if args.id in tmap(data):
        raise SystemExit(f"任务已存在：{args.id}")
    deps = [d.strip() for d in (args.deps or "").split(",") if d.strip()]
    task = {
        "id": args.id, "title": args.title, "group": args.group or "default",
        "depends_on": deps, "status": "todo",
        "blocked_reason": None, "failed_reason": None,
        "started_at": None, "ended_at": None, "approx": False,
        "worktree": None, "branch": None, "agent": None, "session_id": None,
        "provenance": None, "evidence": [],
        "review": {"verdict": None, "reviewer": None, "report": None, "at": None,
                   "overridden": False, "override_reason": None},
    }
    data["tasks"].append(task)
    if has_cycle(data["tasks"]):
        raise SystemExit(f"依赖成环，拒绝添加：{args.id} deps={deps}")
    save_ledger(data)
    print(f"已添加 {args.id}（todo，deps={deps or '无'}）")
    return 0


def cmd_start(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    if task["status"] != "todo":
        raise SystemExit(f"{args.id} 状态={task['status']}，只有 todo 可 start")
    miss = missing_deps(data, task)
    if miss:
        raise SystemExit(f"依赖闸拒绝：{args.id} 的前驱未 done → blocked-by: {miss}")
    bind_worktree(task, args.agent)
    task["status"] = "doing"
    task["started_at"] = now()
    task["blocked_reason"] = None
    task["failed_reason"] = None
    save_ledger(data)
    print(f"▶ {args.id} doing | worktree={task['worktree']} | {task['provenance']}")
    return 0


def cmd_done(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    if task["status"] != "doing":
        raise SystemExit(f"{args.id} 状态={task['status']}，只有 doing 可 done")
    if args.force:
        if not args.reason:
            raise SystemExit("--force 必须配 --reason（留痕）")
        task["status"] = "done"
        task["ended_at"] = now()
        task["review"].update({"verdict": None, "overridden": True,
                               "override_reason": args.reason, "at": now()})
        save_ledger(data)
        print(f"✔ {args.id} done（--force 越过 review，已留痕：{args.reason}）")
        return 0
    orca = orca_available()
    reviewer = pick_reviewer(task, orca)
    req = write_review_request(task, reviewer)
    task["review"].update({"verdict": "pending", "reviewer": reviewer,
                           "report": str(REVIEWS / f"{args.id}.md"), "at": None})
    save_ledger(data)
    if orca:
        subprocess.run(
            ["orca-ide", "orchestration", "worker-start", "--spec-file", str(req),
             "--agent", reviewer, "--worktree", task["worktree"], "--json"],
            capture_output=True, text=True, timeout=120,
        )
        print(f"… {args.id} review 已派 Orca worker（{reviewer}）")
    print(f"⏸ {args.id} REVIEW REQUIRED（reviewer={reviewer}）")
    print(f"  brief: {req}")
    print(f"  审完写报告 workflows/reviews/{args.id}.md（末行 VERDICT: pass|blocker），再跑：")
    print(f"    python3 scripts/task.py verdict {args.id}")
    return 2


def cmd_verdict(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    report = Path(args.report) if args.report else REVIEWS / f"{args.id}.md"
    v = parse_verdict(report)
    if v is None:
        raise SystemExit(f"报告缺失或无 VERDICT 行：{report}")
    task["review"].update({"verdict": v, "report": str(report), "at": now()})
    if v == "pass":
        task["status"] = "done"
        task["ended_at"] = now()
        save_ledger(data)
        print(f"✔ {args.id} done（review pass）")
        return 0
    task["status"] = "doing"
    save_ledger(data)
    print(f"✘ {args.id} review blocker → 留 doing。报告：{report}")
    return 1


def cmd_block(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    task["blocked_reason"] = args.reason
    save_ledger(data)
    print(f"⚠ {args.id} blocked：{args.reason}")
    return 0


def cmd_unblock(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    task["blocked_reason"] = None
    save_ledger(data)
    print(f"{args.id} 解卡")
    return 0


def cmd_fail(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    task["status"] = "todo"
    task["failed_reason"] = args.reason
    save_ledger(data)
    print(f"✘ {args.id} fail → todo（保留 worktree 供重试）：{args.reason}")
    return 0


def cmd_reopen(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    if task["status"] != "done":
        raise SystemExit(f"{args.id} 非 done，无需 reopen")
    task["status"] = "doing"
    task["ended_at"] = None
    task["reopen_reason"] = args.reason
    save_ledger(data)
    print(f"↺ {args.id} reopen → doing：{args.reason}")
    return 0


def cmd_evidence(args) -> int:
    data = load_ledger()
    task = get_task(data, args.id)
    if args.clear:
        task["evidence"] = []
        save_ledger(data)
        print(f"{args.id} 证据已清空")
        return 0
    if task["status"] == "done":
        raise SystemExit(f"{args.id} 已 done（证据已钉）；改证据请先 reopen")
    if args.kind == "file":
        if not args.path:
            raise SystemExit("--kind file 必须配 --path")
        ev = {"kind": "file", "path": args.path, "criterion": args.criterion or ""}
    elif args.kind == "cmd":
        if not args.run:
            raise SystemExit("--kind cmd 必须配 --run")
        ev = {"kind": "cmd", "run": args.run, "criterion": args.criterion or ""}
    else:
        raise SystemExit("必须指定 --kind file|cmd（或 --clear）")
    task.setdefault("evidence", []).append(ev)
    save_ledger(data)
    print(f"＋ {args.id} 证据[{args.kind}] {args.path or args.run}（判据：{args.criterion or '存在/exit 0'}）")
    return 0


def cmd_list(args) -> int:
    data = load_ledger()
    tm = tmap(data)
    rows = data["tasks"]
    if args.ready:
        rows = [t for t in rows if t["status"] == "todo" and not missing_deps(data, t)]
    elif args.status:
        rows = [t for t in rows if t["status"] == args.status]
    print(f"{'ID':<6}{'状态':<8}{'组':<18}标题 / blocked-by")
    print("-" * 72)
    for t in rows:
        miss = missing_deps(data, t)
        extra = ""
        if t["status"] == "todo" and miss:
            extra = f"  [blocked-by: {','.join(miss)}]"
        if t.get("blocked_reason"):
            extra += f"  ⚠{t['blocked_reason']}"
        print(f"{t['id']:<6}{t['status']:<8}{t.get('group', ''):<18}{t.get('title', '')}{extra}")
    print("-" * 72)
    print(f"共 {len(rows)} 项；台账 {LEDGER.relative_to(REPO)}")
    return 0


def cmd_show(args) -> int:
    data = load_ledger()
    print(yaml.safe_dump(get_task(data, args.id), allow_unicode=True, sort_keys=False))
    return 0


# --------------------------------------------------------------------------- #
# board（ledger → 单文件静态 HTML + meta；人类入口，与甘特并列投影）
# --------------------------------------------------------------------------- #
BOARD_DEFAULT = "workflows/board.html"
STATUS_LABEL = ("todo", "doing", "done")

BOARD_CSS = """
:root{
  --bg:#f2f5fb; --panel:#fff; --ink:#182033; --muted:#6b7280; --line:#e5e9f2;
  --blue:#2563eb; --green:#15803d; --gray:#6b7280; --red:#dc2626; --amber:#b45309;
}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  background:radial-gradient(1100px 420px at 8% -8%,#dbe4ff 0%,transparent 60%),
             radial-gradient(900px 380px at 100% 0%,#e6fbf2 0%,transparent 55%),var(--bg)}
a{color:var(--blue);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace}
[hidden]{display:none!important}
.hero{position:relative;overflow:hidden;padding:30px 40px 26px;color:#e8eefc;
  background:linear-gradient(135deg,#0f172a 0%,#172554 55%,#1e3a8a 100%)}
.hero:after{content:"";position:absolute;right:-80px;top:-120px;width:360px;height:360px;border-radius:50%;
  background:radial-gradient(circle,rgba(96,165,250,.28),transparent 68%)}
.kicker{font-size:11px;letter-spacing:.18em;color:#93c5fd;font-weight:700}
.hero-main{position:relative;z-index:1;display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-top:10px}
h1{margin:0;font-size:34px;line-height:1.15;letter-spacing:-.02em}
.sub{margin:8px 0 0;color:#b6c4e6;font-size:13px}
.hero-badge{border:1px solid rgba(147,197,253,.45);background:rgba(59,130,246,.16);color:#bfdbfe;
  border-radius:999px;padding:7px 14px;font-size:12px;font-weight:700;white-space:nowrap}
.facts{position:relative;z-index:1;display:flex;flex-wrap:wrap;gap:10px 26px;margin-top:22px;font-size:12.5px;color:#cbd5e1}
.facts b{color:#93c5fd;font-weight:600;margin-right:8px}
.facts code{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:2px 7px;color:#e0e7ff}
main{max-width:1720px;margin:0 auto;padding:24px 40px 8px}
.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-bottom:22px}
.stat{display:flex;align-items:baseline;gap:10px;background:var(--panel);border:1px solid var(--line);
  border-radius:14px;padding:15px 18px;box-shadow:0 8px 22px rgba(20,32,70,.05)}
.stat .n{font-size:27px;font-weight:800;line-height:1;letter-spacing:-.02em}
.stat .l{font-size:12.5px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.06em}
.stat .zh{font-size:12px;color:var(--muted)}
.stat-todo{border-top:3px solid #94a3b8}.stat-todo .n{color:#475569}
.stat-doing{border-top:3px solid var(--blue)}.stat-doing .n{color:var(--blue)}
.stat-done{border-top:3px solid #16a34a}.stat-done .n{color:var(--green)}
.stat-block{border-top:3px solid var(--red)}.stat-block .n{color:var(--red)}
.stat-ms{border-top:3px solid #7c3aed}.stat-ms .n{color:#6d28d9}
.controls{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:var(--panel);border:1px solid var(--line);
  border-radius:14px;padding:12px 14px;margin-bottom:18px;box-shadow:0 6px 18px rgba(20,32,70,.04)}
.filters{display:flex;gap:7px;flex-wrap:wrap}
.chip{border:1px solid #dbe2ef;background:#f8fafc;color:#475569;border-radius:999px;padding:6px 13px;
  font:inherit;font-size:12.5px;cursor:pointer}
.chip span{color:#94a3b8;margin-left:5px;font-size:11.5px}
.chip:hover{border-color:#c7d2fe;background:#eef2ff}
.chip.on{background:#1e3a8a;border-color:#1e3a8a;color:#fff}
.chip.on span{color:#bfdbfe}
.search{display:flex;align-items:center;gap:8px;margin-left:auto}
.search input{width:260px;border:1px solid #d7dfec;border-radius:10px;padding:8px 12px;background:#fbfcff;
  color:var(--ink);font:inherit;font-size:13px;outline:none}
.search input:focus{border-color:#818cf8;box-shadow:0 0 0 3px rgba(99,102,241,.13)}
.hint{color:#94a3b8;font-size:12px}
.group{background:var(--panel);border:1px solid var(--line);border-radius:16px;margin-bottom:20px;overflow:hidden;
  box-shadow:0 10px 26px rgba(20,32,70,.05)}
.group-head{display:flex;align-items:baseline;gap:10px;padding:15px 20px;border-bottom:1px solid var(--line);
  background:linear-gradient(180deg,#fbfcff,#f7f9ff)}
.group-head h2{margin:0;font-size:16px;letter-spacing:-.01em}
.gcount{background:#eef2ff;color:#4338ca;border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:700}
.gstats{color:var(--muted);font-size:12px}
.table-wrap{overflow-x:auto}
table{width:100%;min-width:1080px;border-collapse:collapse}
thead th{background:#fbfcff;border-bottom:1px solid var(--line);padding:9px 14px;color:#94a3b8;
  font-size:11px;font-weight:700;letter-spacing:.08em;text-align:left;text-transform:uppercase;white-space:nowrap}
tbody td{border-bottom:1px solid #eef1f7;padding:11px 14px;font-size:13px;vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:#f9fbff}
tbody tr.row-ready{background:#f4fdf8;box-shadow:inset 3px 0 0 #22c55e}
tbody tr.row-ready:hover{background:#ecfdf3}
.c-id{width:78px}.c-status{width:104px}.c-deps{width:190px}.c-ev{width:170px}.c-review{width:150px}.c-time{width:150px}
.c-id code{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:2px 7px;color:#334155;font-size:12.5px;font-weight:700}
.badge{display:inline-block;border-radius:999px;padding:3px 10px;font-size:11.5px;font-weight:800;letter-spacing:.02em}
.st-todo{background:#f1f5f9;border:1px solid #e2e8f0;color:#475569}
.st-doing{background:#dbeafe;border:1px solid #bfdbfe;color:#1d4ed8}
.st-done{background:#dcfce7;border:1px solid #bbf7d0;color:var(--green)}
.bdot{display:inline-block;width:8px;height:8px;margin-left:7px;border-radius:50%;background:var(--red);
  vertical-align:1px;box-shadow:0 0 0 3px rgba(220,38,38,.13)}
.tt{font-weight:600;color:#1e293b}
.ms{display:inline-block;margin-left:8px;border:1px solid #ddd6fe;border-radius:999px;padding:1px 8px;
  background:#f5f3ff;color:#6d28d9;font-size:11px;font-weight:700}
.ready-chip{display:inline-block;margin-left:8px;border-radius:999px;padding:2px 9px;background:#16a34a;color:#fff;
  font-size:11px;font-weight:800;box-shadow:0 2px 6px rgba(22,163,74,.25)}
.dep{display:inline-flex;align-items:center;gap:5px;margin:1px 4px 1px 0;border:1px solid;border-radius:7px;
  padding:2px 7px;font-size:11.5px;font-weight:700}
.dep-dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.dep-ok{background:#f0fdf4;border-color:#bbf7d0;color:var(--green)}
.dep-miss{background:#fef2f2;border-color:#fecaca;color:#b91c1c}
.byline{font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.byline-bad{color:var(--red)}
.evcount{display:block;color:#334155;font-size:12.5px;font-weight:700}
.evkinds{display:block;margin-top:1px;color:#64748b;font-size:11.5px}
.review{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.vbadge{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800}
.v-ok{background:#dcfce7;color:var(--green)}
.v-bad{background:#fee2e2;color:#b91c1c}
.v-wait{background:#fef3c7;color:var(--amber)}
.v-warn{background:#ede9fe;color:#6d28d9}
.v-mute{background:#f1f5f9;color:#94a3b8}
.rlink,.rfile{max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11.5px;color:#475569}
.rlink{color:var(--blue)}
.c-time span{display:block;color:#64748b;font-size:11.5px;font-variant-numeric:tabular-nums}
.c-time .arrow{color:#cbd5e1;font-size:10px;line-height:1.2}
.muted{color:#cbd5e1}
.empty{margin-bottom:20px;border:1px dashed #cbd5e1;border-radius:14px;padding:36px;background:var(--panel);
  color:var(--muted);text-align:center}
footer{display:flex;flex-wrap:wrap;gap:8px 22px;max-width:1720px;margin:0 auto;padding:6px 40px 30px;
  color:#94a3b8;font-size:11.5px}
footer code{background:#eef2ff;border-radius:5px;padding:1px 6px;color:#4338ca}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.hero,main,footer{padding-left:18px;padding-right:18px}
  .search{width:100%;margin-left:0}.search input{width:100%}}
@media print{body{background:#fff}.controls{display:none}footer{color:#64748b}}
"""

BOARD_JS = """
(function () {
  var controls = document.getElementById("controls");
  if (!controls) return;
  controls.hidden = false;
  var input = document.getElementById("q");
  var empty = document.getElementById("empty");
  var rows = Array.prototype.slice.call(document.querySelectorAll("tr.task-row"));
  var groups = Array.prototype.slice.call(document.querySelectorAll(".group"));
  var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-filter]"));
  var filter = "all";
  function apply() {
    var q = (input.value || "").trim().toLowerCase();
    var shown = 0;
    rows.forEach(function (row) {
      var hit = (filter === "all" || row.dataset.status === filter) &&
                (!q || (row.dataset.title || "").toLowerCase().indexOf(q) !== -1);
      row.hidden = !hit;
      if (hit) shown += 1;
    });
    groups.forEach(function (group) {
      group.hidden = group.querySelectorAll("tr.task-row:not([hidden])").length === 0;
    });
    buttons.forEach(function (button) {
      button.classList.toggle("on", button.dataset.filter === filter);
    });
    empty.hidden = shown !== 0;
  }
  buttons.forEach(function (button) {
    button.addEventListener("click", function () { filter = button.dataset.filter; apply(); });
  });
  input.addEventListener("input", apply);
})();
"""


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def board_path(data: dict, override: str | None = None) -> Path:
    """看板路径：--out > meta.render.board > workflows/board.html。

    相对路径一律相对仓库根（与 meta.render.doc/png 同口径），不写进产物。
    """
    if override:
        p = Path(override).expanduser()
        return p if p.is_absolute() else REPO / p
    configured = ((data.get("meta") or {}).get("render") or {}).get("board")
    if configured:
        p = Path(str(configured)).expanduser()
        return p if p.is_absolute() else REPO / p
    return REPO / BOARD_DEFAULT


def board_meta_path(board: Path) -> Path:
    return board.with_name(board.name + ".meta")


def display_path(path: Path) -> str:
    """人类可读的相对路径；绝不打印绝对路径。"""
    for base in (REPO, Path.cwd()):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.name


def fmt_time(value: object, full: bool = False) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return esc(text[:16])
    return dt.strftime("%Y-%m-%d %H:%M" if full else "%m-%d %H:%M")


def board_branch() -> str:
    """git rev-parse 尽力取分支；无 git/无仓库不阻断看板。"""
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO, capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return "（未知）"
    name = p.stdout.strip()
    if not name:
        return "（未知）"
    return "detached HEAD" if name == "HEAD" else name


def review_link(report: object, board: Path) -> tuple[str | None, str]:
    """报告链接：仓库内才给相对 href；仓库外只显示文件名（绝不写绝对路径）。"""
    if not report:
        return None, ""
    p = Path(str(report))
    if not p.is_absolute():
        p = REPO / p
    try:
        p = p.resolve()
        p.relative_to(REPO.resolve())
        # 看板本身在仓库外时，relpath 会带出 ../home/<user>/… 这类路径片段：
        # 宁可只显示文件名，也不泄露绝对路径。
        board.parent.resolve().relative_to(REPO.resolve())
    except (OSError, ValueError):
        return None, p.name
    if not p.exists():
        return None, p.name
    rel = Path(os.path.relpath(p, board.parent.resolve())).as_posix()
    if os.path.isabs(rel):
        return None, p.name
    return rel, p.name


def review_cell(task: dict, board: Path) -> str:
    review = task.get("review") or {}
    verdict = review.get("verdict")
    label, cls = {
        "pass": ("pass", "ok"), "blocker": ("blocker", "bad"), "pending": ("pending", "wait"),
    }.get(verdict, ("—", "mute"))
    if verdict is None and review.get("overridden"):
        label, cls = "override", "warn"
    title = ""
    if review.get("overridden") and review.get("override_reason"):
        title = f' title="越过 review：{esc(review["override_reason"])}"'
    parts = [f'<span class="vbadge v-{cls}"{title}>{esc(label)}</span>']
    href, name = review_link(review.get("report"), board)
    if href:
        parts.append(f'<a class="rlink" href="{esc(href)}">{esc(name)}</a>')
    elif name:
        parts.append(f'<span class="rfile" title="报告文件不存在或不在仓库内">{esc(name)}</span>')
    return '<div class="review">' + "".join(parts) + "</div>"


def deps_cell(data: dict, task: dict) -> str:
    deps = task.get("depends_on") or []
    if not deps:
        return '<span class="muted">—</span>'
    tm = tmap(data)
    miss = [d for d in deps if (tm.get(d) or {}).get("status") != "done"]
    pills = []
    for dep in deps:
        ok = (tm.get(dep) or {}).get("status") == "done"
        pills.append(
            f'<span class="dep {"dep-ok" if ok else "dep-miss"}">'
            f'<span class="dep-dot"></span>{esc(dep)}</span>'
        )
    prefix = '<span class="byline byline-bad">blocked-by</span> ' if miss else ""
    return prefix + "".join(pills)


def evidence_cell(task: dict) -> str:
    evs = task.get("evidence") or []
    if not evs:
        return '<span class="muted">—</span>'
    labels = {"file": "文件", "cmd": "命令"}
    counts: dict[str, int] = {}
    for e in evs:
        raw = str(e.get("kind") or "?")
        label = labels.get(raw, raw[:12])
        counts[label] = counts.get(label, 0) + 1
    bits = " · ".join(f"{esc(k)}×{v}" for k, v in counts.items())
    return f'<span class="evcount">{len(evs)} 项</span><span class="evkinds">{bits}</span>'


def status_cell(task: dict) -> str:
    status = task.get("status") if task.get("status") in STATUS_LABEL else "todo"
    badge = f'<span class="badge st-{status}">{status}</span>'
    reason = task.get("blocked_reason")
    if reason:
        badge += f'<span class="bdot" title="卡住：{esc(reason)}" aria-label="卡住"></span>'
    return badge


def title_cell(data: dict, task: dict) -> str:
    title = esc(task.get("title") or task.get("id") or "（无标题）")
    extra = ""
    if task.get("milestone"):
        extra += '<span class="ms">◆ 里程碑</span>'
    if task.get("status") == "todo" and not missing_deps(data, task):
        extra += '<span class="ready-chip">可开始</span>'
    return f'<span class="tt">{title}</span>{extra}'


def board_row(data: dict, task: dict, board: Path) -> str:
    status = task.get("status") if task.get("status") in STATUS_LABEL else "todo"
    ready = status == "todo" and not missing_deps(data, task)
    text = " ".join(str(task.get("title") or task.get("id") or "").split())
    row_cls = f"task-row st-row-{status}" + (" row-ready" if ready else "")
    return (
        f'<tr class="{row_cls}" data-status="{status}" data-title="{esc(text)}">'
        f'<td class="c-id"><code>{esc(task.get("id"))}</code></td>'
        f'<td class="c-status">{status_cell(task)}</td>'
        f'<td class="c-title">{title_cell(data, task)}</td>'
        f'<td class="c-deps">{deps_cell(data, task)}</td>'
        f'<td class="c-ev">{evidence_cell(task)}</td>'
        f'<td class="c-review">{review_cell(task, board)}</td>'
        f'<td class="c-time"><span>{fmt_time(task.get("started_at"))}</span>'
        f'<span class="arrow">→</span><span>{fmt_time(task.get("ended_at"))}</span></td>'
        f'</tr>'
    )


def group_section(data: dict, group: str, tasks: list[dict], board: Path) -> str:
    counts = {s: sum(1 for t in tasks if t.get("status") == s) for s in STATUS_LABEL}
    stats = " · ".join(f"{s} {counts[s]}" for s in ("doing", "todo", "done") if counts[s])
    rows = "".join(board_row(data, t, board) for t in tasks)
    return f'''
<section class="group" data-group="{esc(group)}">
  <div class="group-head">
    <h2>{esc(group)}</h2>
    <span class="gcount">{len(tasks)} 项</span>
    <span class="gstats">{stats}</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th class="c-id">ID</th><th class="c-status">状态</th><th class="c-title">标题</th>
        <th class="c-deps">依赖 / blocked-by</th><th class="c-ev">证据</th><th class="c-review">review</th>
        <th class="c-time">开始 / 结束</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>'''


def summary_html(data: dict, tasks: list[dict]) -> str:
    n = {s: sum(1 for t in tasks if t.get("status") == s) for s in STATUS_LABEL}
    blocked = sum(1 for t in tasks if missing_deps(data, t))
    milestones = sum(1 for t in tasks if t.get("milestone"))
    return f'''
<section class="stats" aria-label="任务汇总">
  <div class="stat stat-todo"><span class="n">{n["todo"]}</span><span class="l">todo</span><span class="zh">待办</span></div>
  <div class="stat stat-doing"><span class="n">{n["doing"]}</span><span class="l">doing</span><span class="zh">进行中</span></div>
  <div class="stat stat-done"><span class="n">{n["done"]}</span><span class="l">done</span><span class="zh">已完成</span></div>
  <div class="stat stat-block"><span class="n">{blocked}</span><span class="l">blocked-by</span><span class="zh">依赖未满足</span></div>
  <div class="stat stat-ms"><span class="n">{milestones}</span><span class="l">milestone</span><span class="zh">里程碑</span></div>
</section>'''


def gen_board_html(data: dict, board: Path, generated_iso: str) -> str:
    tasks = data["tasks"]
    generated = datetime.fromisoformat(generated_iso).strftime("%Y-%m-%d %H:%M")
    sha = ledger_sha()
    updated = (data.get("meta") or {}).get("updated_at")
    groups: dict[str, list[dict]] = {}
    for t in tasks:
        groups.setdefault(str(t.get("group") or "未分组"), []).append(t)
    sections = "".join(group_section(data, g, ts, board) for g, ts in groups.items())
    if not sections:
        sections = '<div class="empty">台账暂无任务。</div>'
    n = {s: sum(1 for t in tasks if t.get("status") == s) for s in STATUS_LABEL}
    ledger_rel = display_path(LEDGER)
    footer_meta = esc(board.name + ".meta")
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="task.py board">
<title>任务看板 · {esc(REPO.name)} · {esc(generated)}</title>
<style>{BOARD_CSS}</style>
</head>
<body>
<header class="hero">
  <div class="kicker">TASK LEDGER · 人类入口</div>
  <div class="hero-main">
    <div>
      <h1>{esc(REPO.name)}</h1>
      <p class="sub">任务台账浏览器看板 · 单文件离线可读 · 台账是唯一真相源</p>
    </div>
    <div class="hero-badge">只读投影</div>
  </div>
  <div class="facts">
    <span><b>分支</b><code>{esc(board_branch())}</code></span>
    <span><b>生成</b>{esc(generated)}</span>
    <span><b>台账 sha256</b><code>{esc(sha[:12])}</code></span>
    <span><b>账本更新</b>{fmt_time(updated, full=True)}</span>
  </div>
</header>
<main>
{summary_html(data, tasks)}
<div class="controls" id="controls" hidden>
  <div class="filters" role="group" aria-label="按状态筛选">
    <button type="button" class="chip on" data-filter="all">全部 <span>{len(tasks)}</span></button>
    <button type="button" class="chip" data-filter="todo">todo <span>{n["todo"]}</span></button>
    <button type="button" class="chip" data-filter="doing">doing <span>{n["doing"]}</span></button>
    <button type="button" class="chip" data-filter="done">done <span>{n["done"]}</span></button>
  </div>
  <label class="search"><input id="q" type="search" placeholder="搜索标题…" aria-label="搜索标题" autocomplete="off"></label>
  <span class="hint">纯静态 · 无需联网</span>
</div>
{sections}
<div class="empty" id="empty" hidden>没有匹配的任务。</div>
</main>
<footer>
  <span>由 <code>scripts/task.py board</code> 生成</span>
  <span>数据源 <code>{esc(ledger_rel)}</code></span>
  <span>身份指纹 <code>{footer_meta}</code></span>
  <span>台账是唯一真相源，手改本页无效</span>
</footer>
<script>{BOARD_JS}</script>
</body>
</html>
'''


def read_board_meta(board: Path) -> dict | None:
    mp = board_meta_path(board)
    if not mp.exists():
        return None
    try:
        meta = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def board_identity(data: dict, board: Path | None = None) -> tuple[bool, str]:
    """看板身份对账：board.html.meta.ledger_sha256 == sha256(ledger.yaml)。"""
    board = board or board_path(data)
    mp = board_meta_path(board)
    meta = read_board_meta(board)
    if meta is None:
        return False, f"{mp.name} 缺失/不可读；请重跑 task.py board"
    recorded = str(meta.get("ledger_sha256") or "")
    if not recorded:
        return False, f"{mp.name} 无 ledger_sha256；请重跑 task.py board"
    current = ledger_sha()
    if recorded != current:
        return False, (
            f"sha 漂移 {recorded[:12]}… → {current[:12]}…；请重跑 task.py board"
        )
    return True, f"sha256(ledger)=={mp.name}"


def cmd_board(args) -> int:
    data = load_ledger()
    board = board_path(data, getattr(args, "out", None))
    generated = now()
    board.parent.mkdir(parents=True, exist_ok=True)
    board.write_text(gen_board_html(data, board, generated), encoding="utf-8")
    meta = {
        "ledger_sha256": ledger_sha(),
        "generated_at": generated,
        "task_count": len(data["tasks"]),
    }
    board_meta_path(board).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已生成 {display_path(board)}（{len(data['tasks'])} 项）")
    if not getattr(args, "no_check", False):
        ok, msg = board_identity(data, board)
        print(f"check 自检（board 身份）：{'OK' if ok else 'FAIL'} · {msg}")
    return 0


# --------------------------------------------------------------------------- #
# check（吸收 check_progress.py）
# --------------------------------------------------------------------------- #
def check_evidence(task: dict) -> tuple[bool, str]:
    for e in task.get("evidence") or []:
        crit = e.get("criterion") or ""
        if e.get("kind") == "file":
            p = REPO / e["path"]
            if not p.exists():
                return False, f"证据文件缺：{e['path']}"
            if crit and crit not in p.read_text(encoding="utf-8"):
                return False, f"{e['path']} 未命中判据「{crit}」"
        elif e.get("kind") == "cmd":
            try:
                p = subprocess.run(e["run"], shell=True, cwd=REPO,
                                   capture_output=True, text=True, timeout=120)
            except Exception as ex:
                return False, f"证据命令异常：{ex}"
            if p.returncode != 0:
                return False, f"证据命令非 0：{e['run']}"
            if crit and crit not in (p.stdout + p.stderr):
                return False, f"命令输出未命中判据「{crit}」：{e['run']}"
    return True, "证据成立"


def cmd_check(args) -> int:
    data = load_ledger()
    tm = tmap(data)
    rows: list[tuple[str, bool, str]] = []

    rows.append(("依赖无环", not has_cycle(data["tasks"]), "depends_on 图无环"))
    for t in data["tasks"]:
        if t["status"] in ("doing", "done"):
            miss = missing_deps(data, t)
            rows.append((f"{t['id']} 依赖满足", not miss,
                         "前驱全 done" if not miss else f"未 done: {miss}"))
        if t["status"] == "done":
            ok, msg = check_evidence(t)
            rows.append((f"{t['id']} 证据", ok, msg))
            rv = t.get("review") or {}
            rok = rv.get("verdict") == "pass" or rv.get("overridden") is True
            rows.append((f"{t['id']} review", rok,
                         "pass/override" if rok else "done 但无 review pass/override"))
            sa, ea = t.get("started_at"), t.get("ended_at")
            tok = bool(sa and ea and sa <= ea)
            rows.append((f"{t['id']} 时间戳", tok, "started≤ended" if tok else "时间戳缺失/倒挂"))

    # 甘特身份对账：meta == sha256(ledger.yaml)
    png = render_paths(data)[1]
    meta = png.with_suffix(".png.meta")
    mok = meta.exists() and meta.read_text(encoding="utf-8").strip() == ledger_sha()
    rows.append(("甘特身份对账", mok, "sha256(ledger)==png.meta（否则 render）"))

    # 看板身份对账：board 存在才查；没有 board 不引入新失败
    board = board_path(data)
    if board.exists():
        bok, bmsg = board_identity(data, board)
        rows.append(("board 身份对账", bok, bmsg))

    if not args.quick:
        audit = REPO / "manual" / "shots" / "audit_book.py"
        if audit.exists():
            try:
                p = subprocess.run([sys.executable, str(audit)],
                                   cwd=REPO, capture_output=True, text=True, timeout=120)
                aok = p.returncode == 0 and "24/24 通过" in p.stdout and "坏链：0" in p.stdout
            except Exception:
                aok = False
            rows.append(("全局闸门 audit_book", aok, "24/24 且 README 坏链 0"))
        else:
            rows.append(("全局闸门 audit_book", True, "未配置 audit_book，跳过（可移植）"))

    print(f"{'状态':<8}{'检查项':<24}说明")
    print("-" * 72)
    drift = sum(1 for _, ok, _ in rows if not ok)
    for name, ok, msg in rows:
        print(f"{'OK' if ok else 'DRIFT':<8}{name:<24}{msg}")
    print("-" * 72)
    print(f"核对：{len(rows) - drift}/{len(rows)} 通过；漂移 {drift} 项")
    return 1 if drift else 0


# --------------------------------------------------------------------------- #
# render（ledger → 甘特 mermaid → PNG → meta）
# --------------------------------------------------------------------------- #
def render_paths(data: dict) -> tuple[Path, Path]:
    r = (data.get("meta") or {}).get("render") or {}
    doc = REPO / r["doc"] if r.get("doc") else DEFAULT_DOC
    png = REPO / r["png"] if r.get("png") else DEFAULT_PNG
    return doc, png


def gen_mermaid(data: dict) -> str:
    lines = [
        "gantt",
        f"    title 进度看板 · {datetime.now():%Y-%m-%d}（橙线 = 今天）",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %m-%d",
        "    todayMarker stroke-width:3px,stroke:#e65100",
    ]
    groups: dict[str, list[dict]] = {}
    for t in data["tasks"]:
        groups.setdefault(t.get("group") or "default", []).append(t)
    for g, ts in groups.items():
        lines.append(f"\n    section {g}")
        for t in ts:
            tag = {"done": "done", "doing": "active"}.get(t["status"], "")
            deps = t.get("depends_on") or []
            start = f"after {deps[0]}" if deps else f"{datetime.now():%Y-%m-%d}"
            if t.get("milestone"):
                tag = "milestone"
            parts = [p for p in [tag, t["id"], start, "1d"] if p]
            # mermaid gantt 用 ASCII 冒号/分号分隔「标签 :tag, id, start, 1d」，
            # 标题里带 ASCII ':' ';' 会把标签截断（渲染报 mermaid 解析错），换成全角。
            title = (t.get("title") or t["id"]).replace(":", "：").replace(";", "；")
            lines.append(f"    {title}        :{', '.join(parts)}")
    return "\n".join(lines)


def find_mermaid_js() -> Path:
    import os
    env = os.environ.get("MERMAID_JS")
    cands = [Path(env)] if env else []
    cands += [REPO / "design" / "assets" / "mermaid.min.js",
              REPO / "assets" / "mermaid.min.js"]
    for c in cands:
        if c.exists():
            return c
    raise SystemExit("缺本地 mermaid.min.js（设 MERMAID_JS 或放 assets/mermaid.min.js）")


def cmd_render(args) -> int:
    sys.path.insert(0, str(REPO / "scripts"))
    import render_progress_gantt as rpg
    data = load_ledger()
    mmd = gen_mermaid(data)
    doc, png = render_paths(data)
    # 把生成的 mermaid 写回 doc 的 ```mermaid 块（生成物）
    block = f"```mermaid\n{mmd}\n```"
    if doc.exists():
        text = doc.read_text(encoding="utf-8")
        if re.search(r"```mermaid\n.*?```", text, re.S):
            text = re.sub(r"```mermaid\n.*?```", lambda _: block, text, count=1, flags=re.S)
        else:
            text += "\n\n## 甘特源（由 task.py render 生成，勿手改）\n\n" + block + "\n"
        doc.write_text(text, encoding="utf-8")
    else:
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(f"# 进度甘特（生成物）\n\n![甘特]({png.name})\n\n{block}\n", encoding="utf-8")
    js = find_mermaid_js().read_text(encoding="utf-8")
    rpg.render_to_png(mmd, png, args.width, mermaid_js=js)
    png.with_suffix(".png.meta").write_text(ledger_sha() + "\n", encoding="utf-8")
    print(f"源哈希（ledger）{ledger_sha()[:12]}… → {png.with_suffix('.png.meta').name}")
    return 0


# --------------------------------------------------------------------------- #
# migrate-from-gantt（一次性）
# --------------------------------------------------------------------------- #
SECTION_GROUP = {
    "已收口": "closed",
    "12 · MarkText 复核编辑器": "marktext",
    "13 · CSS 迭代链": "css-iteration",
    "13 · GrapesJS 试点": "grapesjs-pilot",
    "阅读层（暂停待恢复）": "reading-layer",
}
DONE_EVIDENCE = {
    "s1": [{"kind": "file", "path": "humen-desicions/12-md-editor.md", "criterion": "落定"},
           {"kind": "file", "path": "humen-desicions/13-html-rebuild.md", "criterion": "落定"}],
    "s2": [{"kind": "file", "path": "GLOSSARY.md", "criterion": "复核编辑器"},
           {"kind": "file", "path": "GLOSSARY.md", "criterion": "重构版"},
           {"kind": "file", "path": "docs/adr/0001-dual-canon.md", "criterion": ""}],
    "s3": [{"kind": "file", "path": "humen-desicions/progress-gantt.png", "criterion": ""}],
    "s4": [{"kind": "cmd", "run": "git config core.hooksPath", "criterion": ".githooks"}],
}


def cmd_migrate(args) -> int:
    doc = REPO / "humen-desicions" / "14-progress-gantt.md"
    if not doc.exists():
        raise SystemExit(f"缺 {doc}")
    m = re.search(r"```mermaid\n(.*?)```", doc.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit("14 文档无 mermaid 块")
    tasks: list[dict] = []
    group = "default"
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if line.startswith("section "):
            name = line[len("section "):].strip()
            group = SECTION_GROUP.get(name, re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "default")
            continue
        if ":" not in line or line.startswith(("gantt", "title", "dateFormat", "axisFormat", "todayMarker")):
            continue
        title, meta = line.split(":", 1)
        toks = [x.strip() for x in meta.split(",")]
        tags = [x for x in toks if x in TAGS]
        ids = [x for x in toks if re.fullmatch(r"[a-z]\d+", x)]
        if not ids:
            continue
        tid = ids[0]
        deps = [x[len("after "):].strip() for x in toks if x.startswith("after ")]
        status = "done" if "done" in tags else "doing" if "active" in tags else "todo"
        ev = DONE_EVIDENCE.get(tid, [])
        ended = git_time(REPO / ev[0]["path"]) if (status == "done" and ev and ev[0].get("kind") == "file") else None
        ended = ended or (now() if status == "done" else None)
        t = {
            "id": tid, "title": title.strip(), "group": group,
            "depends_on": deps, "status": status,
            "blocked_reason": None, "failed_reason": None,
            "started_at": ended if status == "done" else (now() if status == "doing" else None),
            "ended_at": ended, "approx": status == "done",
            "worktree": None, "branch": None, "agent": None, "session_id": None,
            "provenance": None, "evidence": ev,
            "milestone": "milestone" in tags,
            "review": {"verdict": "pass" if status == "done" else None,
                       "reviewer": "migrated" if status == "done" else None,
                       "report": None, "at": ended, "overridden": False, "override_reason": None},
        }
        if tid == "m1":  # 甘特标 active 但实测 flatpak 下载已死 → 纠为卡住
            t["blocked_reason"] = "flatpak 下载中断（实测 count=0、无进程），需重下"
        if "crit" in tags:
            t["blocked_reason"] = "等用户裁决（原 crit）"
        tasks.append(t)
    data = {"meta": {"host": host(), "repo": str(REPO), "updated_at": now(),
                     "render": {"doc": "humen-desicions/14-progress-gantt.md",
                                "png": "humen-desicions/progress-gantt.png"}},
            "tasks": tasks}
    if has_cycle(tasks):
        raise SystemExit("迁移检测到依赖环，请检查 14 文档")
    save_ledger(data)
    print(f"已迁移 {len(tasks)} 项 → {LEDGER.relative_to(REPO)}")
    print("  注意：m1 已纠为 blocked（下载中断）；历史 done 时间戳 approx=true")
    return 0


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="任务生命周期 chokepoint CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add"); p.add_argument("id"); p.add_argument("--title", required=True)
    p.add_argument("--group"); p.add_argument("--deps"); p.set_defaults(fn=cmd_add)

    p = sub.add_parser("start"); p.add_argument("id"); p.add_argument("--agent"); p.set_defaults(fn=cmd_start)
    p = sub.add_parser("done"); p.add_argument("id"); p.add_argument("--force", action="store_true")
    p.add_argument("--reason"); p.set_defaults(fn=cmd_done)
    p = sub.add_parser("verdict"); p.add_argument("id"); p.add_argument("--report"); p.set_defaults(fn=cmd_verdict)
    p = sub.add_parser("block"); p.add_argument("id"); p.add_argument("--reason", required=True); p.set_defaults(fn=cmd_block)
    p = sub.add_parser("unblock"); p.add_argument("id"); p.set_defaults(fn=cmd_unblock)
    p = sub.add_parser("fail"); p.add_argument("id"); p.add_argument("--reason", required=True); p.set_defaults(fn=cmd_fail)
    p = sub.add_parser("reopen"); p.add_argument("id"); p.add_argument("--reason", required=True); p.set_defaults(fn=cmd_reopen)
    p = sub.add_parser("evidence"); p.add_argument("id")
    p.add_argument("--kind", choices=["file", "cmd"]); p.add_argument("--path"); p.add_argument("--run")
    p.add_argument("--criterion"); p.add_argument("--clear", action="store_true"); p.set_defaults(fn=cmd_evidence)
    p = sub.add_parser("list"); p.add_argument("--ready", action="store_true"); p.add_argument("--status"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("show"); p.add_argument("id"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("board"); p.add_argument("--out")
    p.add_argument("--no-check", action="store_true"); p.set_defaults(fn=cmd_board)
    p = sub.add_parser("check"); p.add_argument("--quick", action="store_true"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("render"); p.add_argument("--width", type=int, default=1800); p.set_defaults(fn=cmd_render)
    p = sub.add_parser("migrate-from-gantt"); p.set_defaults(fn=cmd_migrate)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())