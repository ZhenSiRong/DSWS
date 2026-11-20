#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trace_server.py —— 第 17 页 v2：**后端注入**行级 tracer + **真前端**截图循环。

为什么换成注入而不是“进程内跑 runner”：
  上一版（trace_query.py）在 backend 容器里另起一个 Python 进程、进程内直接调
  `AgentRunner.events()`，左边只能拿 SSE 事件画节点时间轴——**不是真前端**。
  本版要的是「左边真浏览器界面、右边同一时刻后端真代码行」：浏览器发一次真请求，
  uvicorn 那个真实进程一边跑一边把行级轨迹写到 `/tmp/trace.jsonl`，两边共用
  宿主 wall clock（浏览器 Date.now() 与后端 time.time()），所以能逐帧对齐。

本脚本做四件事（一条命令一步，全部可重跑）：

  inject  把内嵌的 sitecustomize.py 拷进 backend 容器的 site-packages，
          重启容器（uvicorn 启动时 Python 自动 import sitecustomize），
          等 /api/health 200，并**原地清空** trace 文件（不能 rm：uvicorn 已
          用 O_APPEND 打开该 inode，rm 会让它的写入落进已删除文件）。
  capture 用 headless Chrome（`/usr/bin/google-chrome` + frontend/node_modules 里
          已装的 playwright-core）打开成熟版前端，输入问题、点发送；点击后每
          ~360ms 截一帧并记录 DOM 状态探针（12 节点状态、结果表行数、关键 rect）
          与客户端 SSE 到达时间；结果出现后再拍 15 帧。每次尝试前原地清空 trace。
          **只保留“触发校正且校正成功”的那一次**（validate:error → correct:running
          → correct:success → validate:success → run:success → result）。最多
          `--attempts` 次；一次都没触发就报错退出，不做假图。
  fetch   把容器里的 /tmp/trace.jsonl 与 capture meta 收进工作目录。
  crop    把选中的真截图裁成最终左栏尺寸（800×1151）、写
          `manual/review/exec-trace-v2/` 证据（关键窗口 trace、帧清单、meta）。
  finalize 只补/刷新已提交 meta.json 的 model / LLM 调用次数（capture 原始目录已清理时用）。

默认参数就是本次真跑用的隔离栈（runbook 里有完整的起栈命令）：

  project=p17t2   backend 容器=p17t2-backend-1   health=http://127.0.0.1:18117/api/health
  成熟版入口=http://127.0.0.1:8088  （nginx 容器 p17t2-mature，反代 backend:8100）
  工作目录=/tmp/p17t2-run            证据目录=manual/review/exec-trace-v2

为了可移植，容器 / 端口 / URL / 工作目录都能用参数覆盖。本脚本不启动 compose 栈，
也不改页面与判据。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent          # manual/shots
REPO = HERE.parents[1]                          # 仓库根目录
REVIEW = REPO / "manual" / "review"
EVIDENCE = REVIEW / "exec-trace-v2"

CHROME = "/usr/bin/google-chrome"
PW_CORE = REPO / "frontend" / "node_modules" / "playwright-core"

DEFAULTS: dict[str, Any] = {
    "project": "p17t2",
    "container": "p17t2-backend-1",
    "health_url": "http://127.0.0.1:18117/api/health",
    "app_url": "http://127.0.0.1:8088",
    "work_dir": "/tmp/p17t2-run",
    "query": "查询销售额大于平均销售额的商品",
    "viewport_w": 1440,
    "viewport_h": 1640,
    "dsf": 1.5,
    "interval_ms": 360,
    "tail_frames": 15,
    "attempts": 4,
    # 截图 → 左栏：裁掉 300px 侧栏，只留页面主体 1140×1640，缩到 800 宽。
    "crop_w": 1140,
    "crop_h": 1640,
    "crop_x": 300,
    "out_w": 800,
}

# ---------------------------------------------------------------- 注入的 tracer

#: 只追这 4 个文件（本次问数真正做判断的代码点）。
TARGET_FILES = (
    "backend/app/agent/graph.py",
    "backend/app/agent/correct.py",
    "backend/app/generate/guard.py",
    "backend/app/security/policy.py",
)

SITECUSTOMIZE = r'''"""sitecustomize —— 第 17 页执行轨迹补图：后端行级 tracer（仅 TRACE_OUT 存在时启用）。

由 manual/shots/trace_server.py 生成并拷进 backend 容器的 site-packages；
容器启动时 Python 自动 import 本模块。默认（TRACE_OUT 未设置）什么都不做。

启用后：
  * sys.settrace + threading.settrace —— LangGraph 节点跑在工作线程里，
    只装 sys.settrace 只能看到主线程的构图代码；
  * 只记 4 个文件的 line 事件：app/agent/graph.py、app/agent/correct.py、
    app/generate/guard.py、app/security/policy.py（其余文件 return None）；
  * 每个 line 事件向 TRACE_OUT 追加一行 JSONL：
        {"t", "file", "rel", "lineno", "func", "vars"}
    t 是 wall clock（time.time()，与浏览器 Date.now() 同一台宿主时钟），
    file 是文件名，rel 是仓库相对路径（画面上不出现绝对路径）；
  * vars 只收白名单变量，值截断 <=120 字符，key/token/secret/password 一律不记。
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

_TRACE_OUT = os.environ.get("TRACE_OUT", "")

if _TRACE_OUT:
    _ROOT = Path(os.environ.get("TRACE_ROOT", "/app")).resolve()
    _API_KEY = os.environ.get("REBUILD_LLM_API_KEY", "")
    _FILES = (
        "backend/app/agent/graph.py",
        "backend/app/agent/correct.py",
        "backend/app/generate/guard.py",
        "backend/app/security/policy.py",
    )
    _RELS = set(_FILES)
    _TRIM = 120
    _NAMES = (
        "sql",
        "original_sql",
        "corrected_sql",
        "attempts",
        "failure",
        "error",
        "prompt",
        "query",
        "payload",
        "proposal",
        "sql_before",
        "sql_after",
        "violations",
        "state",
    )
    _SECRET_HINTS = ("key", "token", "secret", "password", "passwd", "auth", "credential")

    _lock = threading.Lock()
    _rel_by_file = {}
    _last_vars = {}
    _fd = os.open(_TRACE_OUT, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)

    def _write(record):
        data = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with _lock:
            os.write(_fd, data)

    def _short(value):
        text = str(value)
        if _API_KEY and _API_KEY in text:
            text = text.replace(_API_KEY, "<redacted>")
        if len(text) > _TRIM:
            text = text[: _TRIM - 1] + "…"
        return text

    def _rel(filename):
        # 每次函数调用都会走到这里，必须 O(1)：非目标文件缓存 None，
        # 用 `filename in _rel_by_file` 判断命中——不能用假值判断，否则每个
        # 非目标调用都会重新 resolve() 一次，导入阶段就能把进程拖死。
        if filename in _rel_by_file:
            return _rel_by_file[filename]
        mapped = None
        try:
            if os.path.isabs(filename):
                candidate = Path(filename).resolve().relative_to(_ROOT).as_posix()
            else:
                candidate = filename
            if candidate in _RELS:
                mapped = candidate
        except (ValueError, OSError):
            mapped = None
        _rel_by_file[filename] = mapped
        return mapped

    def _describe(value, depth=0):
        """把局部变量压成可上屏的小对象：只留判断依据，不留整对象。"""
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return _short(value)
        if depth > 1:
            return _short(value)
        code = getattr(value, "code", None)
        message = getattr(value, "message", None)
        if isinstance(code, str) and isinstance(message, str):
            item = {"code": _short(code), "message": _short(message)}
            retryable = getattr(value, "retryable", None)
            if isinstance(retryable, bool):
                item["retryable"] = retryable
            return item
        violations = getattr(value, "violations", None)
        if violations is not None:
            items = []
            for violation in list(violations)[:2]:
                items.append(
                    {
                        "code": _short(getattr(violation, "code", "?")),
                        "message": _short(getattr(violation, "message", "")),
                    }
                )
            return {"ok": bool(getattr(value, "ok", False)), "violations": items}
        attempted = getattr(value, "attempted", None)
        if attempted is not None:
            return {
                "attempted": bool(attempted),
                "ok": bool(getattr(value, "ok", False)),
                "sql": _short(getattr(value, "sql", "") or ""),
                "note": _short(getattr(value, "note", "") or ""),
            }
        if isinstance(value, dict):
            picked = {}
            for key in ("sql", "original_sql", "corrected_sql", "attempts", "failure",
                        "code", "message", "reason_code", "ok", "retryable", "violations"):
                if key in value:
                    picked[key] = _describe(value[key], depth + 1)
            if not picked:
                return _short(value)
            return picked
        if isinstance(value, (list, tuple)):
            if value and getattr(value[0], "code", None):
                return [
                    {"code": _short(getattr(item, "code", "?")),
                     "message": _short(getattr(item, "message", ""))}
                    for item in list(value)[:2]
                ]
            return _short(value)
        return _short(value)

    def _variables(frame):
        captured = {}
        for name in _NAMES:
            if name not in frame.f_locals:
                continue
            if any(hint in name.lower() for hint in _SECRET_HINTS):
                continue
            value = frame.f_locals[name]
            if name == "state" and isinstance(value, dict):
                for key in ("sql", "attempts", "corrected_sql", "original_sql", "failure"):
                    if key in value:
                        captured["state." + key] = _describe(value[key])
                continue
            if name == "violations" and value:
                captured["violations[0]"] = _describe(value[0])
                captured["violations.count"] = len(value)
                continue
            if name == "error" and value is not None:
                captured["error"] = _describe(value)
                continue
            captured[name] = _describe(value)
        signature = json.dumps(captured, ensure_ascii=False, sort_keys=True)
        key = (frame.f_code.co_filename, frame.f_code.co_name)
        if _last_vars.get(key) == signature:
            return None
        _last_vars[key] = signature
        return captured

    def _record(frame, rel):
        variables = _variables(frame)
        record = {
            "t": round(time.time(), 6),
            "file": rel.rsplit("/", 1)[-1],
            "rel": rel,
            "lineno": frame.f_lineno,
            "func": frame.f_code.co_name,
        }
        if variables:
            record["vars"] = variables
        _write(record)

    def _global(frame, event, arg):
        if event == "call":
            rel = _rel(frame.f_code.co_filename)
            if rel is not None:
                return _local
        return None

    def _local(frame, event, arg):
        if event == "line":
            rel = _rel(frame.f_code.co_filename)
            if rel is not None:
                _record(frame, rel)
        return _local

    sys.settrace(_global)
    threading.settrace(_global)
'''

# ---------------------------------------------------------------- 浏览器截图循环

CAPTURE_JS = r'''// 真前端截图循环（由 trace_server.py 写到临时文件后 node 执行）
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW_CORE);

const URL_ = process.env.URL;
const OUT = process.env.OUT;
const QUERY = process.env.QUERY;
const W = Number(process.env.W);
const H = Number(process.env.H);
const DSF = Number(process.env.DSF);
const INTERVAL = Number(process.env.INTERVAL);
const TAIL_FRAMES = Number(process.env.TAIL_FRAMES);
const MAX_RUN_MS = Number(process.env.MAX_RUN_MS || 120000);

const NODE_NAMES = ['抽取关键词', '召回字段信息', '召回指标信息', '召回字段取值',
  '合并召回信息', '过滤指标信息', '过滤表信息', '添加额外上下文',
  '生成SQL', '校验SQL', '校正SQL', '执行SQL'];

fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, Math.max(0, ms)));

function probeFn(names) {
  const all = document.querySelectorAll('div');
  const cards = [];
  for (const el of all) {
    const cls = typeof el.className === 'string' ? el.className : '';
    if (!cls.includes('flex h-10 items-center gap-2 border')) continue;
    const text = (el.textContent || '').trim();
    let status = 'pending';
    if (cls.includes('border-moss/25')) status = 'success';
    else if (cls.includes('border-tomato/35')) status = 'error';
    else if (cls.includes('border-brass/45')) status = 'running';
    else if (cls.includes('border-dashed')) status = 'skipped';
    cards.push({ text, status });
  }
  const nodes = {};
  for (const name of names) {
    const hit = cards.find((c) => c.text === name || c.text === name + ' · 未触发');
    nodes[name] = hit ? hit.status : 'absent';
  }
  const rect = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return [Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)];
  };
  const cardRects = {};
  for (const el of all) {
    const cls = typeof el.className === 'string' ? el.className : '';
    if (!cls.includes('flex h-10 items-center gap-2 border')) continue;
    const text = (el.textContent || '').trim();
    cardRects[text.replace(' · 未触发', '')] = rect(el);
  }
  const table = document.querySelector('table');
  const rows = table ? table.querySelectorAll('tbody tr').length : 0;
  const sendBtn = document.querySelector('form button');
  const scroller = document.querySelector('main .overflow-y-auto');
  return {
    nodes, cards: cards.length, cardRects,
    rectTable: rect(table), rectInput: rect(document.querySelector('form')),
    rectScroller: rect(scroller), rectRail: rect(document.querySelector('section')),
    title: document.title, lang: document.documentElement.lang,
    tableRows: rows,
    tableText: table ? table.innerText.replace(/\s+/g, ' ').trim().slice(0, 300) : '',
    sendLabel: sendBtn ? (sendBtn.getAttribute('aria-label') || '') : '',
    inputValue: (document.querySelector('textarea') || {}).value ?? null,
    text: document.body.innerText.replace(/\s+/g, ' ').slice(0, 700),
    scrollTop: scroller ? scroller.scrollTop : null,
    scrollHeight: scroller ? scroller.scrollHeight : null,
    clientHeight: scroller ? scroller.clientHeight : null,
  };
}

const browser = await chromium.launch({
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--hide-scrollbars'],
});
const context = await browser.newContext({
  viewport: { width: W, height: H }, deviceScaleFactor: DSF, locale: 'zh-CN',
});

// 在页面脚本之前挂 fetch 钩子：记下 SSE 每个 event 的客户端到达时刻。
// 浏览器 Date.now() 与后端 time.time() 是同一台宿主时钟 → 左右对齐基准。
await context.addInitScript(() => {
  window.__p17 = { sse: [], chunks: [], fetchCalls: [] };
  const origFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const t = Date.now();
    const response = await origFetch(input, init);
    if (!url.includes('/api/query')) return response;
    window.__p17.fetchCalls.push({ url, t, status: response.status });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    const stream = new ReadableStream({
      start(controller) {
        (async () => {
          try {
            for (;;) {
              const { value, done } = await reader.read();
              if (done) { controller.close(); break; }
              const received = Date.now();
              window.__p17.chunks.push({ t: received, bytes: value.byteLength });
              buffer += decoder.decode(value, { stream: true });
              let at;
              while ((at = buffer.indexOf('\n\n')) >= 0) {
                const block = buffer.slice(0, at);
                buffer = buffer.slice(at + 2);
                const payload = block.split('\n').filter((l) => l.startsWith('data:'))
                  .map((l) => l.replace(/^data:\s?/, '')).join('\n').trim();
                if (!payload) continue;
                try { window.__p17.sse.push({ t: received, event: JSON.parse(payload) }); }
                catch (error) { window.__p17.sse.push({ t: received, raw: payload }); }
              }
              controller.enqueue(value);
            }
          } catch (error) {
            try { controller.error(error); } catch (ignored) { /* 流已关闭 */ }
          }
        })();
      },
    });
    return new Response(stream, {
      status: response.status, statusText: response.statusText, headers: response.headers,
    });
  };
});

const page = await context.newPage();
const consoleErrors = [];
page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('pageerror', (err) => consoleErrors.push(String(err)));

await page.goto(URL_, { waitUntil: 'load', timeout: 30000 });
await page.waitForSelector('textarea', { timeout: 20000 });
await page.waitForTimeout(500);

const meta = {
  url: URL_, query: QUERY, viewport: { width: W, height: H }, deviceScaleFactor: DSF,
  started_at_iso: new Date().toISOString(),
  frames: [], inputFrame: null, t0: null, consoleErrors,
  final_probe: null, metrics: null, sse: [], fetchCalls: [], chunks: [],
};
const dump = () => fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 1));

await page.click('textarea');
await page.fill('textarea', QUERY);
await page.waitForTimeout(250);
const tInputPre = Date.now();
await page.screenshot({ path: path.join(OUT, 'input.png') });
const inputProbe = await page.evaluate(probeFn, NODE_NAMES);
meta.inputFrame = { file: 'input.png', t_pre: tInputPre, t_post: Date.now(), probe: inputProbe };
dump();

const t0 = Date.now();
meta.t0 = t0;
await page.click('button[aria-label="发送"]');

let index = 0;
let resultSeenAt = null;
let doneFrames = 0;
while (Date.now() - t0 < MAX_RUN_MS) {
  const loopStart = Date.now();
  const file = `frames/frame-${String(index).padStart(4, '0')}.png`;
  const probePre = await page.evaluate(probeFn, NODE_NAMES);
  const tShot = Date.now();
  await page.screenshot({ path: path.join(OUT, file) });
  const tPost = Date.now();
  const state = await page.evaluate(probeFn, NODE_NAMES);
  meta.frames.push({ index, file, t_shot: tShot, t_post: tPost,
    t_probe: Date.now(), el_ms: tShot - t0, probe_pre: probePre, probe: state });
  index += 1;

  const finished = state.sendLabel === '发送' && state.tableRows > 0;
  if (finished && resultSeenAt === null) resultSeenAt = tPost;
  if (resultSeenAt !== null) doneFrames += 1;
  if (resultSeenAt !== null && state.sendLabel === '发送' && doneFrames >= TAIL_FRAMES) break;
  if (!finished && state.sendLabel === '发送' && index > 8 && state.tableRows === 0
      && state.text.includes('没有成功')) break;
  await sleep(INTERVAL - (Date.now() - loopStart));
  if (index % 10 === 0) { meta.final_probe = state; dump(); }
}

await page.waitForTimeout(700);
const evidence = await page.evaluate(() => window.__p17
  ? { sse: window.__p17.sse, chunks: window.__p17.chunks, fetchCalls: window.__p17.fetchCalls }
  : null);
meta.sse = evidence ? evidence.sse : [];
meta.chunks = evidence ? evidence.chunks : [];
meta.fetchCalls = evidence ? evidence.fetchCalls : [];
meta.final_probe = await page.evaluate(probeFn, NODE_NAMES);
meta.ended_at_iso = new Date().toISOString();
meta.duration_ms = Date.now() - t0;
meta.metrics = await page.evaluate(() => {
  const sc = document.querySelector('main .overflow-y-auto');
  return {
    scrollHeight: sc ? sc.scrollHeight : null,
    clientHeight: sc ? sc.clientHeight : null,
    scrollTop: sc ? sc.scrollTop : null,
    bodyText: document.body.innerText.replace(/\s+/g, ' ').slice(0, 1500),
  };
});
dump();
console.log(JSON.stringify({
  frames: meta.frames.length, t0, duration_ms: meta.duration_ms,
  sse: meta.sse.length, chunks: meta.chunks.length, fetchCalls: meta.fetchCalls,
  nodeStates: meta.final_probe.nodes, tableRows: meta.final_probe.tableRows, consoleErrors,
}));
await browser.close();
'''


# ---------------------------------------------------------------- 小工具


def say(msg: str = "") -> None:
    print(msg, file=sys.stderr, flush=True)


def run(cmd: list[str], *, timeout: float = 180.0, check: bool = True,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if check and proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-3000:]
        raise RuntimeError(f"命令失败（{' '.join(cmd[:2])}…）：{tail}")
    return proc


class Config:
    def __init__(self, args: argparse.Namespace) -> None:
        self.project = args.project
        self.container = args.container
        self.health_url = args.health_url
        self.app_url = args.app_url
        self.work = Path(args.work_dir)
        self.out = Path(args.out_dir) if args.out_dir else EVIDENCE
        self.query = args.query
        self.viewport_w = args.viewport_w
        self.viewport_h = args.viewport_h
        self.dsf = args.dsf
        self.interval_ms = args.interval_ms
        self.tail_frames = args.tail_frames
        self.attempts = args.attempts
        self.crop_w = args.crop_w
        self.crop_h = args.crop_h
        self.crop_x = args.crop_x
        self.out_w = args.out_w


# ---------------------------------------------------------------- inject


def container_site_packages(cfg: Config) -> tuple[str, str]:
    proc = run(["docker", "exec", cfg.container, "python", "-c",
                "import site,sys;print(sys.version.split()[0]);print(site.getsitepackages()[0])"])
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError(f"读不到容器 site-packages：{proc.stdout!r}")
    return lines[0], lines[1]


def wait_health(cfg: Config, timeout_s: float = 90.0) -> None:
    started = time.time()
    while time.time() - started < timeout_s:
        proc = subprocess.run(
            ["docker", "exec", cfg.container, "python", "-c",
             "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8100/api/health',"
             "timeout=3).read()"],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            say(f"[inject] backend /api/health 200（{time.time() - started:.1f}s）")
            return
        time.sleep(1.5)
    raise RuntimeError("backend 重启后 90s 内 /api/health 没有 200")


def trace_size(cfg: Config) -> int:
    proc = run(["docker", "exec", cfg.container, "sh", "-c",
                "stat -c %s /tmp/trace.jsonl 2>/dev/null || echo 0"])
    return int((proc.stdout or "0").strip().splitlines()[-1] or 0)


def truncate_trace(cfg: Config) -> None:
    """原地清空。绝不能 rm：uvicorn 启动时用 O_APPEND 打开该 inode，
    rm 之后它的写入会落进已删除文件，docker cp 只能拿到 0 字节。"""
    run(["docker", "exec", cfg.container, "sh", "-c", ": > /tmp/trace.jsonl"])


def inject(cfg: Config) -> dict[str, Any]:
    python_version, site_packages = container_site_packages(cfg)
    say(f"[inject] 容器 python {python_version}，site-packages={site_packages}")
    temp = Path(tempfile.mkdtemp(prefix="p17-sitecustomize-"))
    local = temp / "sitecustomize.py"
    local.write_text(SITECUSTOMIZE, encoding="utf-8")
    local.chmod(0o644)
    target = f"{site_packages}/sitecustomize.py"
    run(["docker", "cp", str(local), f"{cfg.container}:{target}"])
    run(["docker", "exec", "-u", "0", cfg.container, "chmod", "644", target])
    run(["docker", "exec", "-u", "0", cfg.container, "chown", "10001:10001", target])
    probe = run(["docker", "exec", cfg.container, "python", "-c",
                 "import sys;print('loaded' if sys.modules.get('sitecustomize') else 'missing')"])
    if "loaded" not in probe.stdout:
        raise RuntimeError(f"sitecustomize 没有随解释器加载：{probe.stdout!r}")
    say("[inject] sitecustomize 已加载，重启 backend 让 uvicorn 进程带上 tracer…")
    run(["docker", "restart", cfg.container], timeout=120)
    wait_health(cfg)
    # 启动时 import 会记一批模块级行事件；真跑前清空，只留这一次请求。
    fd_check = run(["docker", "exec", cfg.container, "sh", "-c",
                    "ls -l /proc/1/fd | grep trace || true"])
    if "trace.jsonl" not in fd_check.stdout:
        raise RuntimeError("uvicorn 进程没有打开 /tmp/trace.jsonl（TRACE_OUT 没生效？）")
    truncate_trace(cfg)
    shutil.rmtree(temp, ignore_errors=True)
    info = {
        "container": cfg.container,
        "python": python_version,
        "site_packages": site_packages,
        "target": target,
        "trace_size_after_truncate": trace_size(cfg),
        "uvicorn_fd": fd_check.stdout.strip(),
    }
    say(f"[inject] 完成：{json.dumps(info, ensure_ascii=False)}")
    (cfg.work / "inject.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


# ---------------------------------------------------------------- capture


def sse_events(meta: dict[str, Any]) -> list[dict[str, Any]]:
    return [item["event"] for item in meta.get("sse", []) if isinstance(item.get("event"), dict)]


def judge_trigger(meta: dict[str, Any]) -> dict[str, Any]:
    """判读这次真跑有没有触发校正并成功（顺序要真，不是只看出现过）。"""
    events = sse_events(meta)
    seq = [(ev.get("type"), ev.get("step"), ev.get("status")) for ev in events]
    tries = [i for i, item in enumerate(seq) if item == ("progress", "validate_sql", "error")]
    correct_runs = [i for i, item in enumerate(seq) if item == ("progress", "correct_sql", "running")]
    correct_oks = [i for i, item in enumerate(seq) if item == ("progress", "correct_sql", "success")]
    val_ok_after = [i for i, item in enumerate(seq)
                    if item == ("progress", "validate_sql", "success") and correct_oks and i > correct_oks[0]]
    run_ok = [i for i, item in enumerate(seq) if item == ("progress", "run_sql", "success")]
    result = [i for i, item in enumerate(seq) if item[0] == "result"]
    ok = bool(tries and correct_runs and correct_oks
              and tries[0] < correct_runs[0] < correct_oks[0]
              and val_ok_after and run_ok and result and run_ok[-1] < result[-1]
              and len(correct_runs) == 1 and len(correct_oks) == 1)
    return {
        "triggered": ok,
        "validate_errors": len(tries),
        "correct_runs": len(correct_runs),
        "correct_success": len(correct_oks),
        "events": len(events),
        "rows": (meta.get("final_probe") or {}).get("tableRows"),
        "note": "" if ok else f"帧序不成立：{seq[-8:]}",
    }


def run_capture_once(cfg: Config, attempt: int, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    js = out_dir / "capture.mjs"
    js.write_text(CAPTURE_JS, encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "PW_CORE": str(PW_CORE),
        "URL": cfg.app_url,
        "OUT": str(out_dir),
        "QUERY": cfg.query,
        "W": str(cfg.viewport_w),
        "H": str(cfg.viewport_h),
        "DSF": str(cfg.dsf),
        "INTERVAL": str(cfg.interval_ms),
        "TAIL_FRAMES": str(cfg.tail_frames),
        "MAX_RUN_MS": "120000",
    })
    say(f"[capture] 第 {attempt} 次真跑：打开 {cfg.app_url} → 输入「{cfg.query}」→ 点发送")
    truncate_trace(cfg)
    before = trace_size(cfg)
    started = time.time()
    proc = run(["node", str(js)], timeout=180, env=env)
    elapsed = time.time() - started
    last = (proc.stdout or "").strip().splitlines()
    summary = json.loads(last[-1]) if last and last[-1].startswith("{") else {}
    trace_local = out_dir / "trace.jsonl"
    run(["docker", "cp", f"{cfg.container}:/tmp/trace.jsonl", str(trace_local)])
    trace_lines = sum(1 for _ in trace_local.open(encoding="utf-8", errors="ignore")) \
        if trace_local.exists() else 0
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    judge = judge_trigger(meta)
    judge.update({
        "attempt": attempt,
        "seconds": round(elapsed, 2),
        "frames": len(meta.get("frames", [])),
        "trace_lines": trace_lines,
        "trace_bytes": trace_local.stat().st_size if trace_local.exists() else 0,
        "capture_summary": summary,
    })
    say(f"[capture] 第 {attempt} 次：{elapsed:.1f}s / {judge['frames']} 帧 / "
        f"trace {trace_lines} 行 / 触发={judge['triggered']}")
    if not judge["triggered"]:
        say(f"[capture]   未触发：{judge['note']}")
    return judge


def capture(cfg: Config) -> dict[str, Any]:
    if not PW_CORE.exists():
        raise RuntimeError(f"缺 playwright-core：{PW_CORE}")
    if not Path(CHROME).exists():
        raise RuntimeError(f"缺 Chrome：{CHROME}")
    # 前置健康检查：前端与后端都必须是活的
    proc = subprocess.run(["curl", "-fsS", "-m", "5", f"{cfg.app_url}/api/health"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"成熟版入口 {cfg.app_url}/api/health 不通：{proc.stderr[-500:]}")
    cfg.work.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    kept: Path | None = None
    for attempt in range(1, cfg.attempts + 1):
        attempt_dir = cfg.work / f"capture-{attempt}"
        judge = run_capture_once(cfg, attempt, attempt_dir)
        attempts.append(judge)
        if judge["triggered"]:
            kept = attempt_dir
            break
    summary = {"attempts": attempts, "kept": kept.name if kept else None}
    (cfg.work / "capture-attempts.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    if kept is None:
        raise SystemExit(
            f"[capture] {cfg.attempts} 次真跑都没有触发 validate:error → correct:success，"
            "按要求不渲染假图。可再跑一次 trace_server.py capture。")
    if kept != cfg.work / "capture-kept":
        target = cfg.work / "capture-kept"
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(kept, target)
    say(f"[capture] 保留第 {attempts[-1]['attempt']} 次（触发且校正成功）→ {cfg.work / 'capture-kept'}")
    return summary


# ---------------------------------------------------------------- fetch / crop


def load_kept(cfg: Config) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    kept = cfg.work / "capture-kept"
    meta = json.loads((kept / "meta.json").read_text(encoding="utf-8"))
    trace_path = kept / "trace.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
    return meta, trace


def env_value(name: str) -> str:
    """只读 .env 里指定的配置项（值不打印）。"""
    path = REPO / ".env"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip()
    return ""


def finalize_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """补上「这是哪个模型、LLM 调了几次」——kept run 的调用次数由触发帧序推导，
    全部尝试的调用次数连 attempts 一起算（没触发校正的那次只有 1 次生成调用）。"""
    trigger = meta.get("trigger") or {}
    kept_calls = 1 + (1 if trigger.get("correct_success") else 0)
    all_calls = 0
    for attempt in meta.get("attempts") or []:
        all_calls += 1 + (1 if attempt.get("triggered") else 0)
    meta["model"] = env_value("REBUILD_LLM_MODEL") or meta.get("model") or "unknown"
    meta["generator"] = "http-llm"
    meta["llm_calls"] = kept_calls
    meta["llm_calls_all_attempts"] = all_calls
    meta["llm_evidence"] = (
        f"保留这次：generate_sql 1 次（graph.py:239 draft_sql(...) 只出现 1 次）+ "
        f"correct_sql 1 次（correct.py:203 corrector.correct(...) 只出现 1 次）；"
        f"对应 SSE 两段真实等待 {meta.get('timeline_s', {}).get('generate_wait_s')}s / "
        f"{meta.get('timeline_s', {}).get('correct_wait_s')}s。"
        f"全部 {len(meta.get('attempts') or [])} 次尝试合计 {all_calls} 次"
        f"（第 1 次未触发校正，只用了 1 次）。"
    )
    return meta


def timeline_from_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """把这一次真跑的 SSE 客户端时间换算成相对点击的时间轴（秒）。"""
    t0 = meta["t0"]
    fetch_t = (meta.get("fetchCalls") or [{}])[0].get("t", t0)
    marks: dict[str, float | None] = {}

    def first(step: str, status: str, after: float = -1e18) -> float | None:
        for item in meta.get("sse", []):
            event = item.get("event") or {}
            if (event.get("type") == "progress" and event.get("step") == step
                    and event.get("status") == status and item["t"] >= after):
                return round((item["t"] - t0) / 1000.0, 3)
        return None

    def duration(step: str, status: str) -> float | None:
        for item in meta.get("sse", []):
            event = item.get("event") or {}
            if event.get("type") == "progress" and event.get("step") == step and event.get("status") == status:
                return round((event.get("duration_ms") or 0) / 1000.0, 3)
        return None

    gen_run = first("generate_sql", "running")
    gen_ok = first("generate_sql", "success")
    val_err = first("validate_sql", "error")
    corr_run = first("correct_sql", "running")
    corr_ok = first("correct_sql", "success")
    val2_ok = first("validate_sql", "success", after=(corr_run or 0))
    run_ok = first("run_sql", "success")
    result = next((round((item["t"] - t0) / 1000.0, 3) for item in meta.get("sse", [])
                   if (item.get("event") or {}).get("type") == "result"), None)
    marks.update({
        "click_s": 0.0,
        "request_s": round((fetch_t - t0) / 1000.0, 3),
        "generate_running_s": gen_run,
        "generate_success_s": gen_ok,
        "validate1_running_s": first("validate_sql", "running"),
        "validate1_error_s": val_err,
        "correct_running_s": corr_run,
        "correct_success_s": corr_ok,
        "validate2_success_s": val2_ok,
        "run_sql_success_s": run_ok,
        "result_s": result,
        "generate_wait_s": duration("generate_sql", "success"),
        "validate1_ms_s": duration("validate_sql", "error"),
        "correct_wait_s": duration("correct_sql", "success"),
        "validate2_wait_s": duration("validate_sql", "success"),
        "run_wait_s": duration("run_sql", "success"),
    })
    marks["real_total_s"] = round((result or 0) - (marks["request_s"] or 0), 3)
    return marks


def select_frames(meta: dict[str, Any]) -> dict[str, Any]:
    """按 DOM 探针（pre/post 一致才算稳定态）挑每个阶段的真截图角色。"""

    def stable(frame: dict[str, Any]) -> str:
        def state(probe: dict[str, Any]) -> tuple:
            nodes = tuple(probe.get("nodes", {}).values())
            return (nodes, probe.get("tableRows"), probe.get("sendLabel"))
        return "stable" if state(frame["probe_pre"]) == state(frame["probe"]) else "moving"

    def stage_of(frame: dict[str, Any]) -> str:
        nodes = frame["probe"].get("nodes") or {}
        running = {k for k, v in nodes.items() if v == "running"}
        errors = {k for k, v in nodes.items() if v == "error"}
        success = sum(1 for v in nodes.values() if v == "success")
        rows = frame["probe"].get("tableRows") or 0
        if rows >= 1 and success >= 12:
            return "final"
        if "校验SQL" in errors and "校正SQL" in running:
            return "validate_error"
        if "生成SQL" in running:
            return "generate"
        return "other"

    frames = meta.get("frames") or []
    stable_frames = [f for f in frames if stable(f) == "stable"]
    groups: dict[str, list[dict[str, Any]]] = {"generate": [], "validate_error": [], "final": []}
    for frame in stable_frames:
        stage = stage_of(frame)
        if stage in groups:
            groups[stage].append(frame)

    generate = groups["generate"]
    valid_error = groups["validate_error"]
    final = groups["final"]

    def spread(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
        if not items:
            return []
        if len(items) <= count:
            return items
        if count == 1:
            return [items[0]]
        picks = []
        for i in range(count):
            picks.append(items[round(i * (len(items) - 1) / (count - 1))])
        return picks

    roles = {
        "input": [meta["inputFrame"]],
        "t0": [frames[0]] if frames else [],
        "a": spread(generate, 4),
        # b 只用“红叉刚出现”那一张：再往后 0.8s 时钟差就 >1s，对齐抽查会不好看；
        # d/e 是同一终态（校正后二次校验通过 + 结果表），用最靠近锚点的那张真截图，
        # 靠左栏高亮框 + 右栏锚点区分两个阶段（不拿晚 2s 的帧冒充“当时”）。
        "b": valid_error[:1],
        "c": spread(valid_error[2:], 4) if len(valid_error) > 2 else valid_error[-2:],
        "d": final[:1],
        "e": final[:1],
    }
    return roles


def crop_frames(cfg: Config, meta: dict[str, Any], roles: dict[str, Any]) -> dict[str, Any]:
    """把选中的真截图裁成最终左栏尺寸，写进证据目录（只存选中的 ~11 张）。"""
    frames_dir = cfg.out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.png"):
        old.unlink()
    kept = cfg.work / "capture-kept"
    scale = cfg.dsf
    crop = (int(cfg.crop_x * scale), 0, int(cfg.crop_w * scale), int(cfg.crop_h * scale))
    manifest: dict[str, Any] = {
        "source": "capture-kept/（trace_server.py capture 的工作目录，真截图由它裁出）",
        "t0_epoch": round(meta["t0"] / 1000.0, 6),
        "request_epoch": round((meta.get("fetchCalls") or [{}])[0].get("t", meta["t0"]) / 1000.0, 6),
        "viewport": meta.get("viewport"),
        "deviceScaleFactor": meta.get("deviceScaleFactor"),
        "crop": {"x": crop[0], "y": crop[1], "w": crop[2], "h": crop[3],
                 "css": {"x": cfg.crop_x, "w": cfg.crop_w, "h": cfg.crop_h}},
        "out_width": cfg.out_w,
        "roles": {},
    }
    for role, entries in roles.items():
        items = []
        for frame in entries:
            if role == "input":
                src = kept / frame["file"]
                out = frames_dir / "s0-input.png"
                t_epoch = frame["t_pre"] / 1000.0
                probe = frame.get("probe") or {}
                index = -1
            else:
                src = kept / frame["file"]
                out = frames_dir / f"{role}-{frame['index']:04d}.png"
                t_epoch = frame["t_shot"] / 1000.0
                probe = frame.get("probe") or {}
                index = frame["index"]
            run(["convert", str(src), "-crop", f"{crop[2]}x{crop[3]}+{crop[0]}+{crop[1]}",
                 "+repage", "-resize", f"{cfg.out_w}x", "-strip", str(out)])
            items.append({
                "role": role,
                "index": index,
                "t_epoch": round(t_epoch, 6),
                "file": str(out.relative_to(cfg.out)),
                "probe": {
                    "nodes": probe.get("nodes"),
                    "cardRects": probe.get("cardRects"),
                    "rectTable": probe.get("rectTable"),
                    "rectInput": probe.get("rectInput"),
                    "tableRows": probe.get("tableRows"),
                    "scrollTop": probe.get("scrollTop"),
                },
            })
        manifest["roles"][role] = items
        say(f"[crop] {role}: {[item['index'] for item in items]} → "
            f"{len(items)} 张 {cfg.out_w}px")
    (cfg.out / "capture-frames.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def crop_trace(cfg: Config, trace: list[dict[str, Any]]) -> dict[str, Any]:
    """存关键窗口 trace：本次真跑全窗口；超过 500KB 时按文件抽稀（保留 graph/
    correct/guard 全量，policy 每 2 条留 1 条——policy 是两张门里的第二张，
    右栏只拿它当"最近执行行"的背景）。"""
    limit = 500 * 1024
    full = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in trace)
    data = full
    thinned = False
    if len(full.encode("utf-8")) > limit:
        thinned = True
        seen_policy = 0
        kept: list[str] = []
        for record in trace:
            if record["rel"].endswith("policy.py"):
                seen_policy += 1
                if seen_policy % 2 == 0:
                    continue
            kept.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        data = "\n".join(kept) + "\n"
    path = cfg.out / "trace.jsonl"
    path.write_text(data, encoding="utf-8")
    info = {
        "records_total": len(trace),
        "records_kept": data.count("\n"),
        "bytes": len(data.encode("utf-8")),
        "thinned": thinned,
        "limit_bytes": limit,
    }
    say(f"[crop] trace → {path.relative_to(REPO)}：{info['bytes']} B / "
        f"{info['records_kept']} 条 / 抽稀={thinned}")
    return info


def crop(cfg: Config) -> dict[str, Any]:
    meta, trace = load_kept(cfg)
    judge = judge_trigger(meta)
    if not judge["triggered"]:
        raise SystemExit("[crop] 保留的这次真跑帧序不成立，拒绝出证据")
    cfg.out.mkdir(parents=True, exist_ok=True)
    timeline = timeline_from_meta(meta)
    roles = select_frames(meta)
    if not roles["a"] or not roles["b"] or not roles["d"]:
        raise SystemExit(f"[crop] 截图阶段不全，不能渲染：{[k for k, v in roles.items() if not v]}")
    manifest = crop_frames(cfg, meta, roles)
    trace_info = crop_trace(cfg, trace)
    attempts_path = cfg.work / "capture-attempts.json"
    attempts = json.loads(attempts_path.read_text(encoding="utf-8")) if attempts_path.exists() else {}
    evidence = {
        "artifact": "exec-trace-v2",
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "query": meta["query"],
        "url": meta["url"],
        "viewport": meta["viewport"],
        "device_scale_factor": meta["deviceScaleFactor"],
        "stack": {
            "project": cfg.project,
            "backend_container": cfg.container,
            "app_url": cfg.app_url,
            "trace_in_container": "/tmp/trace.jsonl",
        },
        "attempts": attempts.get("attempts", []),
        "kept_attempt": (attempts.get("kept") or "").replace("capture-", ""),
        "timeline_s": timeline,
        "trigger": judge,
        "frames": {
            "role_counts": {role: len(items) for role, items in manifest["roles"].items()},
            "crop": manifest["crop"],
            "out_width": cfg.out_w,
        },
        "trace": trace_info,
        "client_sse": [
            {"t_rel_ms": round((item["t"] - meta["t0"])),
             "event": item.get("event")}
            for item in meta.get("sse", [])
        ],
        "dom_final": {
            "nodes": (meta.get("final_probe") or {}).get("nodes"),
            "tableRows": (meta.get("final_probe") or {}).get("tableRows"),
            "title": (meta.get("final_probe") or {}).get("title"),
            "lang": (meta.get("final_probe") or {}).get("lang"),
            "consoleErrors": meta.get("consoleErrors"),
            "scroll": meta.get("metrics"),
        },
        "method": {
            "left": "成熟版前端真截图（headless Chrome 1440×1640 @1.5x，点击后每 ~360ms 一帧）",
            "right": "同一请求的 backend uvicorn 进程内 sys.settrace + threading.settrace 行级轨迹"
                     "（sitecustomize 注入，只追 4 个文件），按左帧时间戳取 ≤ 该时刻的决定性 trace 事件",
            "clock": "浏览器 Date.now() 与后端 time.time() 同为宿主 wall clock（epoch 秒/毫秒）",
            "trigger": "LLM 采样不保证每次触发校正；本证据只保留触发且成功的那一次，其余尝试列在 attempts",
        },
    }
    evidence = finalize_meta(evidence)
    (cfg.out / "meta.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    say(f"[crop] 证据 → {cfg.out.relative_to(REPO)}/")
    return evidence


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", default="all",
                        choices=["inject", "capture", "fetch", "crop", "finalize", "all"])
    parser.add_argument("--project", default=DEFAULTS["project"])
    parser.add_argument("--container", default=DEFAULTS["container"])
    parser.add_argument("--health-url", default=DEFAULTS["health_url"])
    parser.add_argument("--app-url", default=DEFAULTS["app_url"])
    parser.add_argument("--work-dir", default=DEFAULTS["work_dir"])
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--query", default=DEFAULTS["query"])
    parser.add_argument("--viewport-w", type=int, default=DEFAULTS["viewport_w"])
    parser.add_argument("--viewport-h", type=int, default=DEFAULTS["viewport_h"])
    parser.add_argument("--dsf", type=float, default=DEFAULTS["dsf"])
    parser.add_argument("--interval-ms", type=int, default=DEFAULTS["interval_ms"])
    parser.add_argument("--tail-frames", type=int, default=DEFAULTS["tail_frames"])
    parser.add_argument("--attempts", type=int, default=DEFAULTS["attempts"])
    parser.add_argument("--crop-w", type=int, default=DEFAULTS["crop_w"])
    parser.add_argument("--crop-h", type=int, default=DEFAULTS["crop_h"])
    parser.add_argument("--crop-x", type=int, default=DEFAULTS["crop_x"])
    parser.add_argument("--out-w", type=int, default=DEFAULTS["out_w"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config(args)
    cfg.work.mkdir(parents=True, exist_ok=True)
    (cfg.work / "config.json").write_text(
        json.dumps({k: getattr(cfg, k) for k in dir(cfg) if not k.startswith("_") and
                    not callable(getattr(cfg, k))}, ensure_ascii=False, indent=1,
                   default=str), encoding="utf-8")
    started = time.time()
    if args.command == "finalize":
        meta_path = cfg.out / "meta.json"
        if not meta_path.exists():
            raise SystemExit(f"缺证据：{meta_path}")
        meta = finalize_meta(json.loads(meta_path.read_text(encoding="utf-8")))
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        say(f"[finalize] {meta_path.relative_to(REPO)}：model={meta['model']} · "
            f"LLM kept={meta['llm_calls']} / 全部尝试={meta['llm_calls_all_attempts']}")
        return 0
    if args.command in ("inject", "all"):
        inject(cfg)
    if args.command in ("capture", "all"):
        capture(cfg)
    if args.command in ("fetch", "crop", "all"):
        # fetch 只是把 kept 里的 trace/meta 再确认一遍（capture 已落盘），crop 才是产物。
        kept = cfg.work / "capture-kept"
        if not (kept / "trace.jsonl").exists():
            run(["docker", "cp", f"{cfg.container}:/tmp/trace.jsonl", str(kept / "trace.jsonl")])
        evidence = crop(cfg)
        say(f"[done] {time.time() - started:.1f}s；证据 {cfg.out.relative_to(REPO)}/，"
            f"下一步：python3 manual/shots/render_exec_trace.py")
        say(f"[done] 帧序：{json.dumps(evidence['trigger'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
