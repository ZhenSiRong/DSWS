#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p23_shots.py —— 真跑第 23 页（L5 装：17 行 HTML → 真前端），隔离栈 `p23shots`，
用本机 Chrome 截两张真浏览器图 + 录一条真操作 GIF。

在仓库根目录一条命令重跑：

    python3 tutorial/shots/p23_shots.py

（栈已经起着、想跳过起停：`python3 tutorial/shots/p23_shots.py --reuse`，
跑完不 down；正常重跑不加参数，脚本自己起栈、自己 `down -v`。）

输出：

    tutorial/images/page-23-frontend.png  真前端：问「华北销售额」→ 步骤轨 12 条（11 完成 + 1 未触发）
                                        + 结果表 41,099.5（浏览器按页面默认 8080 口径截图，图内无隔离端口）
    tutorial/images/page-23-html.png      拆一刀：stop frontend 后换回 page-23.md 里那 17 行 HTML 入口，
                                        同一问题后 #out 停在 41099.5（无轨无表）
    tutorial/images/page-23-demo.gif      真前端操作：输入 → 步骤轨亮起（生成SQL「执行中」约 6s）
                                        → 结果表 41,099.5（约 7s 循环，真实时序录制）

它按 runbook（tutorial/review/p23-runbook.md）与页面命令做五件事：

1. 起隔离栈 `-p p23shots`（隔开用户自己的 dsws-lab-ui / dsws-trace 栈）：
   mysql 13347 / ES 19247 / Qdrant 16347 / backend 18147 / frontend 18097，
   `FRONTEND_BIND=127.0.0.1`；磁盘紧（90%）所以**先起三个依赖 → 关 ES 磁盘 watermark
   → 再起 init/backend/frontend**。镜像已缓存，只 `up -d --no-build`，不重建。
2. 图 A：Chrome 打开 `http://127.0.0.1:18097`，输入框填「华北销售额」→ 点「提问」→
   等 badge 状态变「已完成」、结果表出 `41,099.5`，核对 DOM：`.rail-item` ×12、
   11 `.rail-success` + 1 `.rail-skipped`（校正SQL）、badge `12 步` / `1 条件步`、
   console 0 error；中途还抓一张「生成SQL 执行中」帧。
3. 图 B：`docker compose -p p23shots stop frontend` → 从 page-23.md 的 ```html 块逐字
   抽出 `p23-html/index.html` → 用真前端镜像起临时 nginx `p23-html` 进 `p23shots_default`
   网络占同一个 18097 → 点「问一句」→ 等 `#out` 停在 `41099.5`，核对无 table / 无 rail。
4. GIF：删临时 nginx、把真前端 `up -d` 拉起 → 逐字敲「华北销售额」→ 点「提问」→
   每 180ms 截一帧直到结果出现 + 多录约 1.6s；按 120ms/帧合成 6–8s GIF
   （录制久了就均匀抽帧压缩回放，每一帧仍来自真跑；前 11 步后端各 0–3ms
   是同一批渲染亮的，肉眼可见的「执行中」是生成SQL，LLM 延迟实测 5.6–12.4s），
   首/中/末帧对比证明有动画、末帧 OCR 读出 41,099.5。
5. 收尾：删 `p23-html` 容器与目录、`compose down -v`、删临时工作区；
   `docker ps -a` 前后各拍一次 ID 快照，证明用户 24 个容器一个没动
   （本来就要清那 0 个残留卷/网络）；`system/backend/uv.lock` 被改动就 `git checkout --`。

图里不出现用户名 / 主机名 / 绝对路径 / 隔离端口；两张 PNG 与 page-09 同口径
（窗宽 1100px、1:1 像素、1px 灰边），中文逐字证据取自浏览器 DOM（本机 tesseract
只有英文包，数字用 OCR 复核）。

依赖（本机已装，不新装）：docker、google-chrome、ImageMagick、node、tesseract；
仓库的 `system/frontend/node_modules/playwright-core` 与已缓存的 `shopkeeper-rebuild/*:local` 镜像。
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- 常量

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
IMAGES = REPO / "manual" / "images"
PAGE = REPO / "manual" / "page-23.md"
HTML_DIR = REPO / "p23-html"
PLAYWRIGHT_CORE = REPO / "frontend" / "node_modules" / "playwright-core"
CHROME = "/usr/bin/google-chrome"

PROJECT = "p23shots"
NETWORK = f"{PROJECT}_default"
COMPOSE = ["docker", "compose", "-p", PROJECT]

PORTS = {
    "MYSQL_HOST_PORT": "13347",
    "ES_HOST_PORT": "19247",
    "QDRANT_HOST_PORT": "16347",
    "BACKEND_HOST_PORT": "18147",
    "FRONTEND_HOST_PORT": "18097",
    "FRONTEND_BIND": "127.0.0.1",
}
WEB_URL = f"http://127.0.0.1:{PORTS['FRONTEND_HOST_PORT']}"
API_URL = f"http://127.0.0.1:{PORTS['BACKEND_HOST_PORT']}"
ES_URL = f"http://127.0.0.1:{PORTS['ES_HOST_PORT']}"

WINDOW_W = 1100          # 与 page-09-browser-ok.png 同窗宽 / 成品宽
VIEWPORT_H = 1200        # 页面内容高约 910，留足再按内容裁
CROP_PAD = 32            # 裁掉页面空白后上下各留 32px（与 web_shots.py 一致）
BORDER_PX = 1            # 1px 灰边（与现有 PNG 一致）

SAMPLE_MS = 180          # GIF 录制采帧间隔
GIF_DELAY = 12           # GIF 每帧 12/100s
GIF_MIN_SECONDS = 6.0    # 循环时长下限（真跑录制 → 均匀抽帧压缩，仍每帧都来自真跑）
GIF_MAX_SECONDS = 8.0    # 循环时长上限
FINAL_HOLD_MIN_SECONDS = 1.2
PRE_ROLL_FRAMES = 2
GIF_MAX_BYTES = 2_500_000

FRONTEND_IMAGE = "shopkeeper-rebuild/frontend:local"
BACKEND_IMAGE = "shopkeeper-rebuild/backend:local"

PNG_FRONTEND = IMAGES / "page-23-frontend.png"
PNG_HTML = IMAGES / "page-23-html.png"
GIF_DEMO = IMAGES / "page-23-demo.gif"

QUESTION = "华北销售额"

# ---------------------------------------------------------------- 浏览器脚本
# 由本脚本写进临时工作区再 `node` 执行（playwright-core 在 system/frontend/node_modules，
# 通过 NODE_PATH 找到；本机没有 Playwright 自带浏览器，用系统 Chrome）。

BROWSER_SHOT_JS = r"""'use strict';
// p23_shots.py 临时生成：真浏览器打开隔离真前端 / 拆一刀的 17 行页面，截两张图。
// 用法：node browser_shot.cjs <frontend|html> <out.json> <out.png>
const fs = require('fs');
const { chromium } = require('playwright-core');

const MODE = process.argv[2];
const OUT_JSON = process.argv[3];
const OUT_PNG = process.argv[4];
const URL = 'http://127.0.0.1:18097';
const QUESTION = '华北销售额';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-gpu',
      '--hide-scrollbars',
      '--force-device-scale-factor=1',
      '--lang=zh-CN',
      '--disable-dev-shm-usage',
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1100, height: 1200 },
    deviceScaleFactor: 1,
    locale: 'zh-CN',
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => pageErrors.push(String(e)));
  const result = { mode: MODE, url: URL };

  if (MODE === 'frontend') {
    await page.goto(URL, { waitUntil: 'load', timeout: 30000 });
    // 12 条步骤轨来自 /api/steps；等它真的到了再动手。
    await page.waitForFunction(
      () => document.querySelectorAll('.rail-item').length === 12,
      null, { timeout: 30000 },
    );
    result.title = await page.title();
    result.stepsCount = await page.$$eval('.rail-item', (els) => els.length);
    result.badgesBefore = await page.$$eval('.badges .badge', (els) => els.map((e) => e.innerText.trim()));

    await page.fill('textarea[aria-label="问题"]', QUESTION);
    result.inputValue = await page.inputValue('textarea[aria-label="问题"]');
    result.buttons = await page.$$eval('button', (els) => els.map((e) => e.textContent.trim()));
    await page.click('button[type="submit"]');

    // 中途帧：条件步骤「生成SQL」在跑（约 6s），证明步骤轨是逐条亮的。
    let midSeen = true;
    try {
      await page.waitForFunction(() => {
        const el = document.querySelector('.rail-item.rail-running');
        return el !== null && el.innerText.includes('生成SQL');
      }, null, { timeout: 30000 });
    } catch (err) {
      midSeen = false;
    }
    result.midRunningSeen = midSeen;
    if (midSeen) {
      result.midRunningText = await page.$eval('.rail-item.rail-running', (e) => e.innerText.replace(/\s+/g, ' ').trim());
      result.midBody = (await page.evaluate(() => document.body.innerText)).slice(0, 800);
      await page.screenshot({ path: OUT_PNG.replace(/\.png$/, '.mid.png') });
    }

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="run-status"]');
      return el !== null && el.textContent.trim() === '已完成';
    }, null, { timeout: 90000 });
    await page.waitForTimeout(600);

    result.railItems = await page.$$eval('.rail-item', (els) => els.map((e) => ({
      cls: e.className, text: e.innerText.replace(/\s+/g, ' ').trim(),
    })));
    result.railSuccess = await page.$$eval('.rail-item.rail-success', (els) => els.length);
    result.railSkipped = await page.$$eval('.rail-item.rail-skipped', (els) => els.length);
    result.railLabels = await page.$$eval('.rail-label', (els) => els.map((e) => e.textContent.trim()));
    result.railStatuses = await page.$$eval('.rail-status', (els) => els.map((e) => e.textContent.trim()));
    result.railDurations = await page.$$eval('.rail-duration', (els) => els.map((e) => e.textContent.trim()));
    result.badgesAfter = await page.$$eval('.badges .badge', (els) => els.map((e) => e.innerText.trim()));
    result.runStatus = await page.$eval('[data-testid="run-status"]', (e) => e.textContent.trim());
    result.queryBubbles = await page.$$eval('.query-bubble', (els) => els.map((e) => e.innerText.trim()));
    result.tableHeaders = await page.$$eval('table thead th', (els) => els.map((e) => e.innerText.trim()));
    result.tableCells = await page.$$eval('table tbody td', (els) => els.map((e) => e.innerText.trim()));
    result.bodyText = await page.evaluate(() => document.body.innerText);
    result.crop = await page.evaluate(() => {
      const app = document.querySelector('.app');
      const footer = document.querySelector('.footer');
      const top = app ? app.getBoundingClientRect().top : 0;
      const bottom = footer ? footer.getBoundingClientRect().bottom : document.body.getBoundingClientRect().height;
      return { top, bottom, innerH: innerHeight };
    });
    result.docHeight = await page.evaluate(() => document.body.getBoundingClientRect().height);
    result.consoleErrors = consoleErrors;
    result.pageErrors = pageErrors;
    await page.screenshot({ path: OUT_PNG });
  } else {
    // 拆一刀：page-23.md 里那 17 行页面 + 3 处接线，挂在同一个 18097 上。
    await page.goto(URL, { waitUntil: 'load', timeout: 30000 });
    await page.waitForFunction(() => document.getElementById('out') !== null, null, { timeout: 20000 });
    result.title = await page.title();
    result.defaultQuestion = await page.inputValue('#q');
    result.buttonText = (await page.locator('button').innerText()).trim();
    await page.locator('button').click({ timeout: 10000 });
    await page.waitForFunction(() => {
      const out = document.getElementById('out');
      return out !== null && out.textContent.trim() === '41099.5';
    }, null, { timeout: 60000 });
    await page.waitForTimeout(300);
    result.outText = await page.$eval('#out', (e) => e.textContent.trim());
    result.questionAfter = await page.inputValue('#q');
    result.tableCount = await page.$$eval('table', (els) => els.length);
    result.railCount = await page.$$eval('.rail-item', (els) => els.length);
    result.bodyText = await page.evaluate(() => document.body.innerText);
    result.crop = await page.evaluate(() => {
      const form = document.querySelector('form');
      const out = document.getElementById('out');
      const top = form ? form.getBoundingClientRect().top : 0;
      const bottom = out ? out.getBoundingClientRect().bottom : document.body.getBoundingClientRect().height;
      return { top, bottom, innerH: innerHeight };
    });
    result.consoleErrors = consoleErrors;
    result.pageErrors = pageErrors;
    await page.screenshot({ path: OUT_PNG });
  }

  fs.writeFileSync(OUT_JSON, JSON.stringify(result, null, 2));
  await browser.close();
})().catch((err) => {
  console.error('BROWSER_SCRIPT_FAILED ' + ((err && err.stack) || err));
  process.exit(1);
});
"""

BROWSER_CAPTURE_JS = r"""'use strict';
// p23_shots.py 临时生成：真前端录屏素材（PNG 帧 + 时间戳 + 步骤轨状态历史）。
// 用法：node capture_page.cjs <frame-dir> <meta.json>
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const FRAME_DIR = process.argv[2];
const META_PATH = process.argv[3];
const URL = 'http://127.0.0.1:18097';
const QUESTION = '华北销售额';
const SAMPLE_MS = 180;

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

(async () => {
  fs.mkdirSync(FRAME_DIR, { recursive: true });
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-gpu',
      '--hide-scrollbars',
      '--force-device-scale-factor=1',
      '--lang=zh-CN',
      '--disable-dev-shm-usage',
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1100, height: 1200 },
    deviceScaleFactor: 1,
    locale: 'zh-CN',
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => pageErrors.push(String(e)));
  const meta = { url: URL, question: QUESTION, frames: [], railHistory: [], statusHistory: [] };

  await page.goto(URL, { waitUntil: 'load', timeout: 30000 });
  await page.waitForFunction(
    () => document.querySelectorAll('.rail-item').length === 12,
    null, { timeout: 30000 },
  );
  await page.waitForTimeout(400);          // 等页面稳定、字体就绪

  // 只观察、不改 DOM：记录步骤轨状态变化（哪几步真的亮过「执行中」）和运行状态。
  await page.evaluate(() => {
    window.__railHistory = [];
    window.__statusHistory = [];
    const rail = document.querySelector('.rail');
    const snap = () => {
      const running = [...document.querySelectorAll('.rail-item.rail-running .rail-label')]
        .map((e) => e.textContent.trim());
      const success = document.querySelectorAll('.rail-item.rail-success').length;
      const skipped = document.querySelectorAll('.rail-item.rail-skipped').length;
      const hist = window.__railHistory;
      const key = running.join('|') + '#' + success + '#' + skipped;
      const last = hist[hist.length - 1];
      if (!last || last.key !== key) hist.push({ t: Date.now(), key, running, success, skipped });
    };
    new MutationObserver(snap).observe(rail, {
      subtree: true, attributes: true, attributeFilter: ['class'], childList: true,
    });
    snap();
    // 高频兜底：前 11 步后端各 0–3ms，React 可能把多次状态更新合到同一批渲染里，
    // MutationObserver 会合并中间态；15ms 采样能多记录一些「完成」条数中间值。
    setInterval(snap, 15);
    const statusEl = document.querySelector('[data-testid="run-status"]');
    if (statusEl) {
      new MutationObserver(() => {
        const text = (statusEl.textContent || '').trim();
        const hist = window.__statusHistory;
        const last = hist[hist.length - 1];
        if (!last || last.text !== text) hist.push({ t: Date.now(), text });
      }).observe(statusEl, { childList: true, characterData: true, subtree: true });
      window.__statusHistory.push({ t: Date.now(), text: (statusEl.textContent || '').trim() });
    }
  });

  const t0 = Date.now();
  const now = () => Date.now() - t0;
  const captureStartAt = now();

  // 后台录制循环：每 ~180ms 截一帧，记录真实时间戳。
  let capturing = true;
  const frames = [];
  const captureLoop = (async () => {
    while (capturing) {
      const t = now();
      const file = `raw-${String(frames.length).padStart(4, '0')}.png`;
      try {
        await page.screenshot({ path: path.join(FRAME_DIR, file) });
      } catch (err) {
        meta.captureError = String((err && err.message) || err);
      }
      frames.push({ t, file });
      const spent = now() - t;
      await sleep(Math.max(0, SAMPLE_MS - spent));
    }
  })();

  // —— 真操作：清空输入框 → 逐字敲「华北销售额」→ 点「提问」→ 等「已完成」——
  await page.fill('textarea[aria-label="问题"]', '');
  meta.clearedAt = now();
  await page.waitForTimeout(150);

  const typeStart = now();
  await page.keyboard.type(QUESTION, { delay: 60 });
  meta.typeStartAt = typeStart;
  meta.typeEndAt = now();
  meta.typeMs = meta.typeEndAt - typeStart;
  await page.waitForTimeout(150);

  meta.clickAt = now();
  await page.click('button[type="submit"]', { timeout: 10000 });
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="run-status"]');
    return el !== null && el.textContent.trim() === '已完成';
  }, null, { timeout: 90000 });
  meta.resultAt = now();

  await page.waitForTimeout(1600);         // 结果停留：再多录约 9 帧
  meta.captureEndAt = now();
  meta.railHistory = await page.evaluate(() => window.__railHistory || []);
  meta.statusHistory = await page.evaluate(() => window.__statusHistory || []);
  meta.railSuccess = await page.$$eval('.rail-item.rail-success', (els) => els.length);
  meta.railSkipped = await page.$$eval('.rail-item.rail-skipped', (els) => els.length);
  meta.stepsCount = await page.$$eval('.rail-item', (els) => els.length);
  meta.railStatuses = await page.$$eval('.rail-status', (els) => els.map((e) => e.textContent.trim()));
  meta.badges = await page.$$eval('.badges .badge', (els) => els.map((e) => e.innerText.trim()));
  meta.runStatus = await page.$eval('[data-testid="run-status"]', (e) => e.textContent.trim());
  meta.tableCells = await page.$$eval('table tbody td', (els) => els.map((e) => e.innerText.trim()));
  meta.tableHeaders = await page.$$eval('table thead th', (els) => els.map((e) => e.innerText.trim()));
  meta.bodyText = await page.evaluate(() => document.body.innerText);
  meta.crop = await page.evaluate(() => {
    const app = document.querySelector('.app');
    const footer = document.querySelector('.footer');
    const top = app ? app.getBoundingClientRect().top : 0;
    const bottom = footer ? footer.getBoundingClientRect().bottom : document.body.getBoundingClientRect().height;
    return { top, bottom, innerH: innerHeight };
  });
  meta.consoleErrors = consoleErrors;
  meta.pageErrors = pageErrors;
  capturing = false;
  await captureLoop;

  meta.captureStartAt = captureStartAt;
  meta.frames = frames;
  fs.writeFileSync(META_PATH, JSON.stringify(meta, null, 2));
  await browser.close();
})().catch((err) => {
  console.error('BROWSER_CAPTURE_FAILED ' + ((err && err.stack) || err));
  process.exit(1);
});
"""

# ---------------------------------------------------------------- 小工具

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def say(msg: str = "") -> None:
    print(msg, flush=True)


def section(title: str) -> None:
    say("")
    say("─" * 78)
    say(title)
    say("─" * 78)


def stack_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(PORTS)
    return env


def run_cmd(args: list[str], timeout: float = 180.0, cwd: Path | None = None,
            env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"命令失败（exit={proc.returncode}）：{' '.join(args)}\n{detail[-3000:]}")
    return proc


def compose(*args: str, timeout: float = 300.0, check: bool = True) -> subprocess.CompletedProcess:
    return run_cmd([*COMPOSE, *args], timeout=timeout, env=stack_env(), cwd=REPO) if check else subprocess.run(
        [*COMPOSE, *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, env=stack_env(), cwd=REPO,
    )


def docker_names_ids() -> dict[str, str]:
    proc = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.ID}}"],
        capture_output=True, text=True, timeout=60,
    )
    mapping: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "\t" in line:
            name, cid = line.split("\t", 1)
            mapping[name.strip()] = cid.strip()
    return mapping


def container_health(name: str) -> tuple[str | None, str | None]:
    """返回 (status, health)。容器不存在 → (None, None)。"""
    proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}", name],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return None, None
    parts = proc.stdout.strip().split()
    status = parts[0] if parts else None
    health = parts[1] if len(parts) > 1 else None
    return status, health


def container_exit_code(name: str) -> int | None:
    proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}} {{.State.ExitCode}}", name],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return None
    parts = proc.stdout.strip().split()
    if len(parts) != 2 or parts[0] != "exited":
        return None
    return int(parts[1])


def wait_until(what: str, predicate, timeout: float, interval: float = 0.5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise RuntimeError(f"等待超时：{what}（{timeout:.0f}s）")


def wait_healthy(name: str, timeout: float = 300.0) -> None:
    def ok() -> bool:
        status, health = container_health(name)
        if status == "running" and health == "healthy":
            return True
        if status in ("exited", "dead"):
            raise RuntimeError(f"{name} 起不来：status={status}（docker logs {name} 看详情）")
        return False

    wait_until(f"{name} healthy", ok, timeout, interval=2.0)


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def http_get(url: str, timeout: float = 3.0) -> tuple[int, str] | None:
    try:
        with _OPENER.open(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception:
        return None


def http_put_json(url: str, payload: dict, timeout: float = 10.0) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="PUT", headers={"Content-Type": "application/json"})
    with _OPENER.open(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def image_size(path: Path) -> tuple[int, int]:
    out = run_cmd(["identify", "-format", "%w %h", str(path)], timeout=60).stdout.strip()
    width, height = out.split()
    return int(width), int(height)


def docker_image_exists(image: str) -> bool:
    proc = subprocess.run(["docker", "image", "inspect", image],
                          capture_output=True, text=True, timeout=60)
    return proc.returncode == 0


# ---------------------------------------------------------------- 敏感串 / 逐字检查


def check_no_secrets(label: str, text: str) -> None:
    """硬约束：页面文本里不得出现用户名 / 主机名 / 绝对路径 / 隔离端口。"""
    forbidden = [
        "/home/", "/tmp/", "/root/", "/Users/", "/var/",
        getpass.getuser(), socket.gethostname(),
        "127.0.0.1", "localhost",
        PORTS["MYSQL_HOST_PORT"], PORTS["ES_HOST_PORT"], PORTS["QDRANT_HOST_PORT"],
        PORTS["BACKEND_HOST_PORT"], PORTS["FRONTEND_HOST_PORT"],
        "18097", "18147", "13347", "19247", "16347",
    ]
    hits = [needle for needle in forbidden if needle and needle in text]
    if hits:
        raise RuntimeError(f"{label} 里出现禁止字符串 {hits}：\n{text[:1200]}")
    say(f"    ✅ 敏感串检查（{label}）：0 命中（用户名 / 主机名 / 绝对路径 / 隔离端口）")


def ocr_text(png: Path) -> str:
    """白底浏览器图 OCR：原图 + 3 倍放大、多 PSM 取并集；没有 tesseract 返回空。"""
    if shutil.which("tesseract") is None:
        say("    ⚠️  未装 tesseract，跳过 OCR（DOM 文本已核对）")
        return ""

    def _tess(source: Path, psm: str) -> str:
        proc = subprocess.run(
            ["tesseract", str(source), "stdout", "-l", "eng", "--psm", psm],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180,
        )
        return proc.stdout or ""

    texts = [_tess(png, "6"), _tess(png, "11")]
    big = png.with_name(png.stem + ".3x.png")
    try:
        run_cmd(["convert", str(png), "-resize", "300%", str(big)], timeout=120)
        texts.append(_tess(big, "6"))
    except Exception:
        pass
    finally:
        big.unlink(missing_ok=True)
    return "\n".join(texts)


def ocr_must_contain(label: str, png: Path, needles: list[list[str]]) -> None:
    """needles 是「任一命中即可」的分组列表，如 [["41,099.5", "41099.5"]]。"""
    text = ocr_text(png)
    if not text.strip():
        return
    flat = "".join(text.split())
    missing = [group for group in needles
               if not any(needle in flat for needle in group)]
    say(f"    OCR（{label}）关键串：{' / '.join(g[0] for g in needles)} → "
        f"{'命中' if not missing else '未命中 ' + str(missing)}")
    if missing:
        raise RuntimeError(f"{label} 的 OCR 文本里没读到 {missing}：{text[:600]!r}")
    check_no_secrets(f"OCR 文本（{label}）", text)


# ---------------------------------------------------------------- 起停隔离栈


def preflight(reuse: bool) -> None:
    missing = [tool for tool in ("docker", "google-chrome", "convert", "identify", "node")
               if shutil.which(tool) is None]
    if missing:
        sys.exit(f"缺少依赖：{', '.join(missing)}（本脚本不装新依赖）")
    if not (PLAYWRIGHT_CORE / "package.json").is_file():
        sys.exit(f"找不到 {PLAYWRIGHT_CORE}（需要 system/frontend/node_modules/playwright-core）")
    if not PAGE.is_file():
        sys.exit(f"找不到页面 {PAGE}")
    if not reuse:
        for image in (FRONTEND_IMAGE, BACKEND_IMAGE):
            if not docker_image_exists(image):
                sys.exit(f"本地没有镜像 {image}：先按第 13 页构建（make docker-up）再重跑本脚本")
        for key in ("MYSQL_HOST_PORT", "ES_HOST_PORT", "QDRANT_HOST_PORT",
                    "BACKEND_HOST_PORT", "FRONTEND_HOST_PORT"):
            port = int(PORTS[key])
            if port_open(port):
                sys.exit(f"端口 {port}（{key}）已被占用：先停掉占用它的服务再重跑本脚本")
        for name in ("p23-html",):
            if name in docker_names_ids():
                say(f"发现上一轮残留的容器 {name}，先删除")
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)
    IMAGES.mkdir(parents=True, exist_ok=True)


def start_stack() -> None:
    section("起隔离栈 1/4：依赖 mysql / elasticsearch / qdrant（先起，再关 ES 磁盘 watermark）")
    compose("up", "-d", "mysql", "elasticsearch", "qdrant", timeout=300)
    for name in (f"{PROJECT}-mysql-1", f"{PROJECT}-elasticsearch-1", f"{PROJECT}-qdrant-1"):
        wait_healthy(name, timeout=300)
        say(f"    ✅ {name} healthy")

    say("    磁盘 90%：关 ES 磁盘分配 watermark，否则 ES 从 yellow 变不了 green")
    status, body = http_put_json(
        f"{ES_URL}/_cluster/settings",
        {"persistent": {"cluster.routing.allocation.disk.threshold_enabled": False}},
    )
    if status != 200 or '"acknowledged":true' not in body.replace(" ", ""):
        raise RuntimeError(f"ES watermark 没关掉：HTTP {status} {body[:400]}")
    say("    ✅ ES 磁盘 watermark 已关（acknowledged）")

    section("起隔离栈 2/4：init / backend / frontend（--no-build，用缓存镜像）")
    compose("up", "-d", "--no-build", "init", "backend", "frontend", timeout=600)
    code = None

    def init_done() -> bool:
        nonlocal code
        code = container_exit_code(f"{PROJECT}-init-1")
        return code is not None

    wait_until("init 容器退出", init_done, timeout=300, interval=2.0)
    if code != 0:
        raise RuntimeError(f"init 退出码 {code}（不是 0）")
    say(f"    ✅ {PROJECT}-init-1 Exited (0)")
    wait_healthy(f"{PROJECT}-backend-1", timeout=300)
    say(f"    ✅ {PROJECT}-backend-1 healthy")
    wait_healthy(f"{PROJECT}-frontend-1", timeout=300)
    say(f"    ✅ {PROJECT}-frontend-1 healthy")

    section("起隔离栈 3/4：入口自检（页面 200 / 后端 /api/health）")
    got = None

    def page_ready() -> bool:
        nonlocal got
        if port_open(int(PORTS["FRONTEND_HOST_PORT"])):
            got = http_get(f"{WEB_URL}/")
            return bool(got and got[0] == 200 and "电商问数智能体" in got[1])
        return False

    wait_until("真前端首页", page_ready, timeout=120, interval=1.0)
    say(f"    ✅ {WEB_URL}/ 200，首页有「电商问数智能体」")
    health = http_get(f"{API_URL}/api/health")
    if not health or health[0] != 200 or '"ok"' not in health[1]:
        raise RuntimeError(f"后端 /api/health 不正常：{health}")
    say(f"    ✅ {API_URL}/api/health = {health[1].strip()}")
    say("    ✅ docker compose ps 里五个长驻服务 healthy（frontend 在）：")
    for name in (f"{PROJECT}-mysql-1", f"{PROJECT}-elasticsearch-1", f"{PROJECT}-qdrant-1",
                 f"{PROJECT}-backend-1", f"{PROJECT}-frontend-1"):
        status, health_status = container_health(name)
        say(f"      {name}: {status} ({health_status})")


def stop_frontend() -> None:
    section("拆一刀 1/4：docker compose stop frontend（让出入口，compose 网络与后端都还在）")
    compose("stop", "frontend", timeout=120)
    say(f"    ✅ frontend 已停；{WEB_URL} 不再监听 = {not port_open(int(PORTS['FRONTEND_HOST_PORT']))}")


def write_p23_html() -> Path:
    """从 page-23.md 的 ```html 块逐字抽出 17 行页面 + 3 处接线。"""
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(r"```html\n(.*?)\n```", text, re.S)
    if not match:
        raise RuntimeError(f"{PAGE} 里找不到 ```html 代码块")
    html = match.group(1) + "\n"
    if "fetch('/api/query'" not in html or "rows[0][0]" not in html:
        raise RuntimeError("从 page-23.md 抽出的 HTML 不是「17 行 + 3 处接线」版本")
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    target = HTML_DIR / "index.html"
    target.write_text(html, encoding="utf-8")
    target.chmod(0o644)          # 第 9 页同款坑：太严 nginx 回 403
    return target


def start_p23_html(index: Path) -> None:
    section("拆一刀 2/4：真前端镜像起临时 nginx `p23-html`（compose 网络 + 同一个 18097）")
    subprocess.run(["docker", "rm", "-f", "p23-html"], capture_output=True, timeout=60)
    run_cmd([
        "docker", "run", "-d", "--name", "p23-html",
        "--network", NETWORK,
        "-p", f"127.0.0.1:{PORTS['FRONTEND_HOST_PORT']}:80",
        "-v", f"{index}:/usr/share/nginx/html/index.html:ro",
        FRONTEND_IMAGE,
    ], timeout=120, cwd=REPO)

    def ready() -> bool:
        got = http_get(f"{WEB_URL}/")
        return bool(got and got[0] == 200 and "问一句" in got[1])

    wait_until("p23-html 入口就绪", ready, timeout=60, interval=1.0)
    say(f"    ✅ {WEB_URL}/ 返回 page-23.md 里那份 index.html（`<form> + <pre> + 3 处接线`）")


def restore_frontend() -> None:
    section("拆一刀 5/5 / GIF 1/3：删临时 nginx，把真前端起回来（healthy 再刷新）")
    subprocess.run(["docker", "rm", "-f", "p23-html"], capture_output=True, timeout=120)
    shutil.rmtree(HTML_DIR, ignore_errors=True)
    compose("up", "-d", "--no-build", "frontend", timeout=300)
    wait_healthy(f"{PROJECT}-frontend-1", timeout=300)
    got = None

    def ready() -> bool:
        nonlocal got
        got = http_get(f"{WEB_URL}/")
        return bool(got and got[0] == 200 and "电商问数智能体" in got[1])

    wait_until("真前端恢复", ready, timeout=120, interval=1.0)
    say(f"    ✅ {PROJECT}-frontend-1 healthy；{WEB_URL}/ 又是真前端")


# ---------------------------------------------------------------- 浏览器截图


def run_browser(work: Path, js_name: str, args: list[str], timeout: float = 240.0) -> None:
    env = os.environ.copy()
    env["NODE_PATH"] = str(PLAYWRIGHT_CORE.parent)
    env["LANGUAGE"] = "zh_CN.UTF-8"
    env["LANG"] = "zh_CN.UTF-8"
    cmd = ["node", str(work / js_name), *args]
    proc = subprocess.run(
        cmd, cwd=work, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"浏览器脚本失败：\n" + (proc.stderr or proc.stdout)[-4000:])


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"浏览器脚本没有写出 {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def crop_page(raw: Path, target: Path, top: float, bottom: float) -> tuple[int, int]:
    """按 DOM 量出的内容上下界裁掉页面空白，宽度保持 1100px，再加 1px 灰边。"""
    raw_w, raw_h = image_size(raw)
    if raw_w != WINDOW_W:
        raise RuntimeError(f"{raw.name} 宽度是 {raw_w}px，不是约定的 {WINDOW_W}px")
    y0 = max(0, int(round(top)) - CROP_PAD)
    y1 = min(raw_h, int(round(bottom)) + CROP_PAD)
    if y1 - y0 < 80:
        raise RuntimeError(f"裁剪范围只有 {y1 - y0}px，不像有内容")
    tmp = target.with_name(target.stem + ".crop.png")
    run_cmd([
        "convert", str(raw),
        "-crop", f"{WINDOW_W}x{y1 - y0}+0+{y0}", "+repage",
        "-shave", "1x0",
        "-bordercolor", "#c9d1d9", "-border", str(BORDER_PX),
        str(tmp),
    ], timeout=120)
    tmp.replace(target)
    return image_size(target)


def run_frontend_once(work: Path, attempt: int) -> tuple[dict, Path]:
    """真前端问一句并截图；返回 (DOM 事实, 原始截图路径)。"""
    raw = work / f"frontend-{attempt}.raw.png"
    facts_path = work / f"frontend-{attempt}.json"
    run_browser(work, "browser_shot.cjs", ["frontend", str(facts_path), str(raw)])
    return load_json(facts_path), raw


def check_frontend_facts(facts: dict, header_name: str) -> None:
    """逐字对账（取自浏览器 DOM，中文也在里面）。"""
    if facts.get("stepsCount") != 12:
        raise RuntimeError(f"步骤轨不是 12 条：{facts.get('stepsCount')}")
    if facts.get("railSuccess") != 11 or facts.get("railSkipped") != 1:
        raise RuntimeError(f"步骤轨状态不是 11 完成 + 1 未触发："
                           f"{facts.get('railSuccess')} / {facts.get('railSkipped')}")
    statuses = facts.get("railStatuses") or []
    if statuses.count("完成") != 11 or statuses.count("未触发") != 1:
        raise RuntimeError(f"轨道文案不对：{statuses}")
    skipped_index = statuses.index("未触发")
    if facts["railLabels"][skipped_index] != "校正SQL":
        raise RuntimeError(f"未触发那条不是 校正SQL：{facts['railLabels'][skipped_index]}")
    badges = facts.get("badgesAfter") or []
    for needle in ("12 步", "1 条件步", "已完成"):
        if not any(needle in badge for badge in badges):
            raise RuntimeError(f"badge 里没有 {needle}：{badges}")
    if facts.get("runStatus") != "已完成":
        raise RuntimeError(f"状态不是 已完成：{facts.get('runStatus')!r}")
    if facts.get("queryBubbles") != [QUESTION]:
        raise RuntimeError(f"对话气泡里的问题不是 {QUESTION}：{facts.get('queryBubbles')}")
    if facts.get("tableCells") != ["41,099.5"]:
        raise RuntimeError(f"结果表单元格不是 41,099.5：{facts.get('tableCells')}")
    if facts.get("consoleErrors") or facts.get("pageErrors"):
        raise RuntimeError(f"浏览器有 console error / pageerror："
                           f"{facts.get('consoleErrors')} {facts.get('pageErrors')}")
    body = facts.get("bodyText", "")
    for needle in ("41,099.5", "12 步", "1 条件步", "已完成", "未触发", "校正SQL", header_name):
        if needle not in body:
            raise RuntimeError(f"页面 DOM 文本里没有 {needle}")
    check_no_secrets("真前端页面 DOM 文本", body)


def shot_frontend(work: Path) -> dict:
    section("图 A / 拆一刀前：真前端问「华北销售额」→ 步骤轨 12 条 + 结果表 41,099.5")
    facts: dict = {}
    raw: Path | None = None
    header_name = ""
    # LLM 生成 SQL 的列别名偶尔是「成交总额」而不是「销售额」（真跑实测约 1/5）。
    # 图按 runbook 期望对「销售额 number」；换一次真跑，最多 3 次，绝不改图。
    for attempt in range(1, 4):
        facts, raw = run_frontend_once(work, attempt)
        headers = facts.get("tableHeaders") or []
        header_name = (headers[0].replace("number", "").strip() if len(headers) == 1 else "")
        say(f"    第 {attempt} 次真跑：步骤轨完成 {facts.get('railSuccess')} + 未触发 "
            f"{facts.get('railSkipped')}；结果表 {headers} → {facts.get('tableCells')}"
            f"；中途生成SQL执行中={facts.get('midRunningSeen')}")
        if header_name == "销售额":
            break
        say(f"    ⚠️ 这次 LLM 把列别名写成 {header_name!r}（真实别名波动）；"
            f"再真跑一次换回「销售额」…")

    assert raw is not None
    say(f"    标题={facts.get('title')!r}  步骤轨={facts.get('stepsCount')} 条")
    say(f"    输入框填 {facts.get('inputValue')!r}；按钮 {facts.get('buttons')}")
    say(f"    中途「生成SQL 执行中」捕获={facts.get('midRunningSeen')}"
        f"（{facts.get('midRunningText', '')!r}）")
    say(f"    步骤轨：完成 {facts.get('railSuccess')} + 未触发 {facts.get('railSkipped')}"
        f"（{facts.get('railStatuses')}）")
    say(f"    badge：{facts.get('badgesAfter')}   状态：{facts.get('runStatus')!r}")
    say(f"    结果表：{facts.get('tableHeaders')} → {facts.get('tableCells')}")
    say(f"    console error：{facts.get('consoleErrors')}；pageerror：{facts.get('pageErrors')}")

    if len(facts.get("tableHeaders") or []) != 1 or "number" not in (facts["tableHeaders"][0]):
        raise RuntimeError(f"结果表不是单列 number：{facts.get('tableHeaders')}")
    if header_name != "销售额":
        say(f"    ⚠️ 3 次真跑的列别名都不是「销售额」（最后一次 {header_name!r}）；"
            f"图保留这次真跑，报告里说明")
    check_frontend_facts(facts, header_name)
    say(f"    ✅ 逐字对账：12 步（11 完成 + 1 未触发 校正SQL）/ badge 12 步·1 条件步·已完成"
        f" / 表头 {header_name} number / 单元格 41,099.5 / console 0 error")

    crop = facts.get("crop") or {}
    size = crop_page(raw, PNG_FRONTEND, float(crop.get("top", 0)),
                     float(crop.get("bottom", 0)))
    say(f"    🖼  {PNG_FRONTEND.relative_to(REPO)}  {size[0]}x{size[1]}  "
        f"{PNG_FRONTEND.stat().st_size / 1024:.0f} KB（裁自 {raw.name} 1100x1200，"
        f"内容 {int(crop.get('top', 0))}–{int(crop.get('bottom', 0))}）")
    ocr_must_contain("图 A", PNG_FRONTEND, [["41,099.5", "41099.5"]])
    return facts


def shot_html(work: Path, index: Path) -> dict:
    section("拆一刀 3/4：浏览器打开同一个 18097，点「问一句」→ #out 停在 41099.5")
    raw = work / "html.raw.png"
    facts_path = work / "html.json"
    run_browser(work, "browser_shot.cjs", ["html", str(facts_path), str(raw)])
    facts = load_json(facts_path)
    say(f"    页面 title={facts.get('title')!r}  输入框默认值={facts.get('defaultQuestion')!r}"
        f"  按钮={facts.get('buttonText')!r}")
    say(f"    #out = {facts.get('outText')!r}；table 数={facts.get('tableCount')}；"
        f"步骤轨 rail-item 数={facts.get('railCount')}")
    say(f"    console error：{facts.get('consoleErrors')}")

    if facts.get("outText") != "41099.5":
        raise RuntimeError(f"#out 不是 41099.5：{facts.get('outText')!r}")
    if facts.get("defaultQuestion") != QUESTION:
        raise RuntimeError(f"输入框默认值不是 {QUESTION}：{facts.get('defaultQuestion')!r}")
    if facts.get("buttonText") != "问一句":
        raise RuntimeError(f"按钮文字不是 问一句：{facts.get('buttonText')!r}")
    if facts.get("tableCount") != 0:
        raise RuntimeError(f"拆一刀页面不该有结果表，却找到 {facts.get('tableCount')} 个 table")
    if facts.get("railCount") != 0:
        raise RuntimeError(f"拆一刀页面不该有步骤轨，却找到 {facts.get('railCount')} 个 rail-item")
    body = facts.get("bodyText", "")
    if "41099.5" not in body:
        raise RuntimeError("拆一刀页面 DOM 文本里没有 41099.5")
    # 输入框的值不是 innerText（<input> 的 value 不渲染成文本），
    # 问题「华北销售额」上面已用 inputValue 逐字核对过，这里只核对渲染出来的按钮文字。
    if "问一句" not in body:
        raise RuntimeError("拆一刀页面 DOM 文本里没有 问一句")
    if facts.get("consoleErrors"):
        raise RuntimeError(f"拆一刀页面有 console error：{facts.get('consoleErrors')}")
    check_no_secrets("拆一刀页面 DOM 文本", body)
    say("    ✅ 同一问题、同一后端：极简入口停在 41099.5；无步骤轨、无结果表（装修层被拆掉）")

    crop = facts.get("crop") or {}
    size = crop_page(raw, PNG_HTML, float(crop.get("top", 0)),
                     float(crop.get("bottom", 0)))
    say(f"    🖼  {PNG_HTML.relative_to(REPO)}  {size[0]}x{size[1]}  "
        f"{PNG_HTML.stat().st_size / 1024:.0f} KB")
    ocr_must_contain("图 B", PNG_HTML, [["41099.5", "41,099.5"]])
    return facts


# ---------------------------------------------------------------- GIF


def run_browser_capture(work: Path, timeout: float = 300.0) -> dict:
    section("GIF 2/3：真前端逐字敲「华北销售额」→ 点「提问」→ 每 180ms 截一帧")
    frames_dir = work / "frames"
    meta_path = work / "capture-meta.json"
    js = work / "capture_page.cjs"
    env = os.environ.copy()
    env["NODE_PATH"] = str(PLAYWRIGHT_CORE.parent)
    env["LANGUAGE"] = "zh_CN.UTF-8"
    env["LANG"] = "zh_CN.UTF-8"
    proc = subprocess.run(
        ["node", str(js), str(frames_dir), str(meta_path)],
        cwd=work, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError("浏览器录制脚本失败：\n" + (proc.stderr or proc.stdout)[-4000:])
    meta = load_json(meta_path)
    frames = meta.get("frames") or []
    if len(frames) < 20:
        raise RuntimeError(f"只录到 {len(frames)} 帧，太少")
    say(f"    录到 {len(frames)} 帧，覆盖 {frames[-1]['t'] - frames[0]['t']}ms；"
        f"敲字 {meta.get('typeMs')}ms，点击后 {meta.get('resultAt')}ms 出结果")
    say(f"    最终：步骤轨 {meta.get('stepsCount')} 条 / 完成 {meta.get('railSuccess')} + "
        f"未触发 {meta.get('railSkipped')}；结果表 {meta.get('tableCells')}；"
        f"状态 {meta.get('runStatus')!r}")
    rail_hist = meta.get("railHistory") or []
    running_seen = []
    for entry in rail_hist:
        for label in entry.get("running") or []:
            if label not in running_seen:
                running_seen.append(label)
    successes = sorted({entry.get("success") for entry in rail_hist if isinstance(entry.get("success"), int)})
    status_hist = [entry.get("text") for entry in (meta.get("statusHistory") or [])]
    say(f"    步骤轨观测：亮过「执行中」的步骤 {running_seen}")
    say(f"    「完成」条数随时间的取值 {successes}（逐条增加 = 步骤轨逐条亮）")
    say(f"    状态变化：{status_hist}")

    if meta.get("tableCells") != ["41,099.5"] or meta.get("runStatus") != "已完成":
        raise RuntimeError(f"GIF 录制的最终画面不对：{meta.get('tableCells')} "
                           f"{meta.get('runStatus')!r}")
    if meta.get("stepsCount") != 12 or meta.get("railSuccess") != 11 or meta.get("railSkipped") != 1:
        raise RuntimeError(f"GIF 录制最终步骤轨不对：{meta.get('stepsCount')} / "
                           f"{meta.get('railSuccess')} / {meta.get('railSkipped')}")
    # 真实时序：前 11 步后端各 0–3ms，几乎同一批渲染就亮了；真正肉眼可见的
    # 「执行中」是 generate_sql（约 6s）。所以只要求：生成SQL 亮过、完成条数有过程。
    if "生成SQL" not in running_seen:
        raise RuntimeError(f"没看到「生成SQL」亮「执行中」（观测到 {running_seen}）")
    if len(successes) < 4:
        raise RuntimeError(f"「完成」条数只出现过 {successes} 种，看不出步骤轨在亮")
    if not status_hist or status_hist[0] != "待命":
        raise RuntimeError(f"运行状态起点不是 待命：{status_hist}")
    if status_hist[-1] != "已完成":
        raise RuntimeError(f"运行状态终点不是 已完成：{status_hist}")
    if (meta.get("resultAt", 0) - meta.get("clickAt", 0)) < 1000:
        raise RuntimeError("点「提问」后不到 1 秒就出结果，不像 SSE 逐条刷新")
    check_no_secrets("GIF 页面 DOM 文本", meta.get("bodyText", ""))
    return meta


def frame_bbox(path: Path) -> tuple[int, int, int, int]:
    out = run_cmd(["convert", str(path), "-format", "%@", "info:"], timeout=60).stdout.strip()
    match = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", out)
    if not match:
        raise RuntimeError(f"找不到 {path.name} 的内容边界：{out!r}")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def crop_frame(raw: Path, target: Path, y0: int, y1: int) -> None:
    run_cmd([
        "convert", str(raw),
        "-crop", f"{WINDOW_W}x{y1 - y0}+0+{y0}", "+repage",
        "-shave", "1x0",
        "-bordercolor", "#c9d1d9", "-border", str(BORDER_PX),
        str(target),
    ], timeout=120)


def thin_out(picks: list[dict], limit: int) -> list[dict]:
    """均匀抽稀到 limit 帧（首末帧必留）：录制久（LLM 慢）也不让 GIF 超 8 秒。"""
    if len(picks) <= limit:
        return picks
    if limit <= 1:
        return [picks[0]]
    idx = [round(i * (len(picks) - 1) / (limit - 1)) for i in range(limit)]
    return [picks[i] for i in idx]


def build_timeline(meta: dict) -> dict:
    raw = sorted(meta["frames"], key=lambda f: f["t"])
    times = [f["t"] for f in raw]
    capture_start, capture_end = times[0], times[-1]
    tick = capture_start
    picks: list[dict] = []
    i = 0
    while tick <= capture_end:
        while i + 1 < len(times) and times[i + 1] <= tick:
            i += 1
        picks.append(raw[i])
        tick += SAMPLE_MS
    if picks[-1] is not raw[-1]:
        picks.append(raw[-1])

    delay_s = GIF_DELAY / 100.0
    hold_min = int(round(FINAL_HOLD_MIN_SECONDS / delay_s))          # ≥1.2s 末帧停留
    max_frames = int(GIF_MAX_SECONDS / delay_s)                     # 66 帧 = 7.92s
    min_frames = int(GIF_MIN_SECONDS / delay_s)                     # 50 帧 = 6.00s
    allowed_picks = max(10, max_frames - PRE_ROLL_FRAMES - hold_min)
    chosen = thin_out(picks, allowed_picks)                          # LLM 慢 → 均匀抽稀
    hold = max(hold_min, min_frames - PRE_ROLL_FRAMES - len(chosen))
    plan = [chosen[0]] * PRE_ROLL_FRAMES + chosen + [chosen[-1]] * hold
    duration = round(len(plan) * delay_s, 2)
    return {
        "frames": plan,
        "duration_s": duration,
        "final_hold_s": round(hold * delay_s, 2),
        "sampled": len(picks),
        "kept": len(chosen),
        "capture_s": round((capture_end - capture_start) / 1000.0, 2),
        "speedup": round((capture_end - capture_start) / 1000.0 / duration, 2),
    }


def make_gif(work: Path, meta: dict) -> None:
    section("GIF 3/3：统一裁剪 → 120ms/帧合成 → 首/中/末帧自检")
    raw_paths = [work / "frames" / f["file"] for f in meta["frames"]]
    missing = [p.name for p in raw_paths if not p.is_file()]
    if missing:
        raise RuntimeError(f"缺帧：{missing[:5]}")

    crop = meta.get("crop") or {}
    top = float(crop.get("top", 0))
    bottom = float(crop.get("bottom", 0))
    if bottom - top < 200:
        raise RuntimeError(f"页面内容高度只有 {bottom - top}px，不像完整界面")
    y0 = max(0, int(round(top)) - CROP_PAD)
    y1 = min(VIEWPORT_H, int(round(bottom)) + CROP_PAD)
    say(f"    统一裁剪：y0={y0} y1={y1}（内容 {int(top)}–{int(bottom)}，"
        f"加 1px 边框后 {WINDOW_W}x{y1 - y0 + 2 * BORDER_PX}）")

    crop_dir = work / "cropped"
    crop_dir.mkdir()
    cropped: list[Path] = []
    for raw in raw_paths:
        target = crop_dir / raw.name
        crop_frame(raw, target, y0, y1)
        cropped.append(target)
    w, h = image_size(cropped[0])
    if w != WINDOW_W:
        raise RuntimeError(f"裁剪后宽 {w}px ≠ {WINDOW_W}px")

    plan = build_timeline(meta)
    index_of = {f["file"]: i for i, f in enumerate(meta["frames"])}
    plan_paths = [cropped[index_of[f["file"]]] for f in plan["frames"]]
    gif_frames = work / "gif-frames"
    gif_frames.mkdir()
    final_paths: list[Path] = []
    for i, src in enumerate(plan_paths):
        dst = gif_frames / f"gif-{i:04d}.png"
        shutil.copyfile(src, dst)
        final_paths.append(dst)
    say(f"    GIF 帧：{len(final_paths)} 帧 × {GIF_DELAY}/100s = {plan['duration_s']}s"
        f"（真跑录制 {plan['capture_s']}s → 采样 {plan['sampled']} 帧 → 均匀保留 "
        f"{plan['kept']} 帧，{plan['speedup']}x 回放，末帧停留 {plan['final_hold_s']}s）")

    cmd = ["convert", "-delay", str(GIF_DELAY), "-loop", "0"]
    cmd += [str(p) for p in final_paths]
    cmd += ["-layers", "Optimize", str(GIF_DEMO)]
    run_cmd(cmd, timeout=600)

    # 注意 format 末尾要带 \n：ImageMagick 多帧时不会替每一帧补换行。
    out = run_cmd(["identify", "-format", "%w %h %n\n", str(GIF_DEMO)], timeout=120).stdout
    first = out.splitlines()[0].split()
    gw, gh, gn = (int(x) for x in first)
    gbytes = GIF_DEMO.stat().st_size
    say(f"    🖼  {GIF_DEMO.relative_to(REPO)}  {gw}x{gh}  帧数 {gn}  {gbytes / 1024:.0f} KB")
    if gbytes > GIF_MAX_BYTES:
        raise RuntimeError(f"GIF {gbytes} 字节 > 上限 {GIF_MAX_BYTES}")
    if (gw, gh) != (WINDOW_W, h):
        raise RuntimeError(f"GIF 尺寸 {gw}x{gh} ≠ 帧尺寸 {WINDOW_W}x{h}")
    if not (GIF_MIN_SECONDS - 0.05 <= plan["duration_s"] <= GIF_MAX_SECONDS + 0.05):
        raise RuntimeError(f"GIF 时长 {plan['duration_s']}s 不在 6–8s 内")

    check_dir = work / "gif-check"
    check_dir.mkdir()
    run_cmd(["convert", str(GIF_DEMO), "-coalesce", str(check_dir / "frame-%03d.png")], timeout=300)
    all_frames = sorted(check_dir.glob("frame-*.png"))
    if len(all_frames) < 3:
        raise RuntimeError("抽帧失败")
    first_frame, mid_frame, last_frame = (all_frames[0], all_frames[len(all_frames) // 3],
                                          all_frames[-1])

    def ae(a: Path, b: Path) -> int:
        proc = subprocess.run(["compare", "-metric", "AE", str(a), str(b), "null:"],
                              capture_output=True, text=True, timeout=120)
        raw = (proc.stderr or proc.stdout or "").strip().split()
        try:
            return int(float(raw[0])) if raw else 0
        except ValueError:
            return -1

    ae_first_last = ae(first_frame, last_frame)
    ae_first_mid = ae(first_frame, mid_frame)
    ae_mid_last = ae(mid_frame, last_frame)
    say(f"    首/中/末帧 compare -metric AE：首↔末 {ae_first_last}  首↔中 {ae_first_mid}  "
        f"中↔末 {ae_mid_last}（0 = 相同）")
    if ae_first_last <= 0:
        raise RuntimeError("GIF 首↔末帧相同，没有动画")
    if ae_first_mid <= 0 and ae_mid_last <= 0:
        raise RuntimeError("GIF 只有首末两种画面，看不出过程")
    import hashlib
    hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in all_frames}
    say(f"    全片唯一画面数：{len(hashes)} / {gn}（≥4 说明画面在变化）")
    if len(hashes) < 4:
        raise RuntimeError("GIF 唯一画面不足 4 种，看不出过程")
    ocr_must_contain("GIF 末帧", last_frame, [["41,099.5", "41099.5"]])
    # 留证：首/中/末帧拷成临时文件，报告里用 identify 引用
    for tag, frame in (("first", first_frame), ("mid", mid_frame), ("last", last_frame)):
        shutil.copyfile(frame, work / f"gif-{tag}.png")


# ---------------------------------------------------------------- 清理


def down_stack() -> None:
    section("收尾 1/3：删临时 nginx / p23-html 目录 / docker compose down -v")
    subprocess.run(["docker", "rm", "-f", "p23-html"], capture_output=True, timeout=120)
    shutil.rmtree(HTML_DIR, ignore_errors=True)
    say("    ✅ 临时 nginx 容器 p23-html 已删、p23-html/ 目录已删")
    compose("down", "-v", "--remove-orphans", timeout=300, check=False)
    say("    ✅ docker compose -p p23shots down -v（0 容器 / 0 卷 / 0 网络）")


def cleanup_workdir(work: Path) -> None:
    shutil.rmtree(work, ignore_errors=True)


def restore_uv_lock() -> None:
    proc = subprocess.run(["git", "status", "--porcelain", "system/backend/uv.lock"],
                          capture_output=True, text=True, timeout=60, cwd=REPO)
    if proc.stdout.strip():
        run_cmd(["git", "checkout", "--", "system/backend/uv.lock"], timeout=60, cwd=REPO)
        say("    ✅ system/backend/uv.lock 有改动 → git checkout -- system/backend/uv.lock 已还原")
    else:
        say("    ✅ system/backend/uv.lock 未改动")


def user_containers(ids: dict[str, str]) -> dict[str, str]:
    """排除本脚本的隔离栈容器，只留用户自己的容器（用户栈 24 个）。"""
    return {name: cid for name, cid in ids.items()
            if not name.startswith(PROJECT) and name != "p23-html"}


def verify_clean(before_ids: dict[str, str], reuse: bool) -> None:
    section("收尾 2/3：残留与用户栈对比（24 个容器 ID 集合前后一致）")
    if not reuse:
        names = docker_names_ids()
        leftovers = sorted(name for name in names if name.startswith(PROJECT) or name == "p23-html")
        if leftovers:
            raise RuntimeError(f"还有残留容器：{leftovers}")
        volumes = subprocess.run(["docker", "volume", "ls", "--format", "{{.Name}}"],
                                 capture_output=True, text=True, timeout=60).stdout.splitlines()
        leftover_volumes = [v for v in volumes if v.startswith(PROJECT)]
        if leftover_volumes:
            raise RuntimeError(f"还有残留卷：{leftover_volumes}")
        networks = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"],
                                  capture_output=True, text=True, timeout=60).stdout.splitlines()
        if NETWORK in networks:
            raise RuntimeError(f"还有残留网络：{NETWORK}")
        say("    ✅ 无残留容器 / 卷 / 网络（隔离栈 0 残留）")

    after_ids = docker_names_ids()
    user_before = user_containers(before_ids)
    user_after = user_containers(after_ids)
    changed = {k: (v, user_after.get(k)) for k, v in user_before.items()
               if user_after.get(k) != v}
    added = sorted(set(user_after) - set(user_before))
    removed = sorted(set(user_before) - set(user_after))
    if changed or removed:
        raise RuntimeError(f"用户栈前后不一致：删除 {removed} 变化 {changed}")
    if added:
        # 别的会话可能也在起自己的栈，只提示不算失败（本脚本不新增用户栈容器）。
        say(f"    ⚠️  期间出现其它新容器（非本脚本）：{added}")
    tag = "（--reuse 未起停栈）" if reuse else ""
    say(f"    ✅ 用户栈 {len(user_before)} 个容器 ID 集合前后一致{tag}")


def verify_page_images() -> None:
    section("收尾 3/3：交付物尺寸 / 大小自检")
    for path in (PNG_FRONTEND, PNG_HTML, GIF_DEMO):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"缺交付物 {path}")
    for path in (PNG_FRONTEND, PNG_HTML):
        w, h = image_size(path)
        say(f"    {path.name}  {w}x{h}  {path.stat().st_size / 1024:.0f} KB")
        if w != WINDOW_W:
            raise RuntimeError(f"{path.name} 宽 {w}px ≠ {WINDOW_W}px")
        if not (60 <= h <= 1400):
            raise RuntimeError(f"{path.name} 高 {h}px 不在合理范围")
    out = run_cmd(["identify", "-format", "%w %h %n\n", str(GIF_DEMO)], timeout=120).stdout
    first = out.splitlines()[0].split()
    gw, gh, gn = (int(x) for x in first)
    say(f"    {GIF_DEMO.name}  {gw}x{gh}  {gn} 帧  "
        f"{GIF_DEMO.stat().st_size / 1024:.0f} KB（上限 {GIF_MAX_BYTES // 1024} KB）")
    if gw != WINDOW_W:
        raise RuntimeError(f"{GIF_DEMO.name} 宽 {gw}px ≠ {WINDOW_W}px")
    if GIF_DEMO.stat().st_size > GIF_MAX_BYTES:
        raise RuntimeError(f"{GIF_DEMO.name} 超过 2.5MB 上限")


# ---------------------------------------------------------------- 主流程


def main() -> int:
    parser = argparse.ArgumentParser(description="第 23 页真跑截图 / GIF（隔离栈 p23shots）")
    parser.add_argument("--reuse", action="store_true",
                        help="栈已起着就跳过起停（跑完不 down，便于反复调图）")
    args = parser.parse_args()

    sys.dont_write_bytecode = True
    started = time.monotonic()
    say("=" * 78)
    say("p23_shots.py —— 真跑第 23 页（L5：17 行 HTML → 真前端），隔离栈 p23shots")
    say(f"仓库：{REPO}")
    say(f"输出：{PNG_FRONTEND.relative_to(REPO)} / {PNG_HTML.relative_to(REPO)} / "
        f"{GIF_DEMO.relative_to(REPO)}")
    say(f"隔离端口：mysql {PORTS['MYSQL_HOST_PORT']} / ES {PORTS['ES_HOST_PORT']} / "
        f"Qdrant {PORTS['QDRANT_HOST_PORT']} / backend {PORTS['BACKEND_HOST_PORT']} / "
        f"frontend {PORTS['FRONTEND_HOST_PORT']}（图内不出现）")
    say("=" * 78)

    before_ids = docker_names_ids()
    say(f"用户栈快照：{len(before_ids)} 个容器（脚本不碰它们）")
    preflight(args.reuse)

    work: Path | None = None
    ok = False
    try:
        work = Path(tempfile.mkdtemp(prefix="manual-p23-shots-"))
        (work / "browser_shot.cjs").write_text(BROWSER_SHOT_JS, encoding="utf-8")
        (work / "capture_page.cjs").write_text(BROWSER_CAPTURE_JS, encoding="utf-8")
        say(f"临时工作区：{work}（浏览器脚本 / 录屏帧，跑完删）")

        if not args.reuse:
            start_stack()
        else:
            section("--reuse：跳过起栈，先确认隔离栈健康")
            for name in (f"{PROJECT}-mysql-1", f"{PROJECT}-elasticsearch-1", f"{PROJECT}-qdrant-1",
                         f"{PROJECT}-backend-1", f"{PROJECT}-frontend-1"):
                wait_healthy(name, timeout=60)
            say("    ✅ 五个长驻服务 healthy")
            got = http_get(f"{WEB_URL}/")
            if not got or got[0] != 200:
                raise RuntimeError(f"真前端没在 {WEB_URL} 上：{got}")
            say(f"    ✅ {WEB_URL}/ 200")

        # ---- 图 A：真前端
        facts_frontend = shot_frontend(work)

        # ---- 图 B：拆一刀
        stop_frontend()
        index = write_p23_html()
        say(f"    ✅ 从 page-23.md 抽出 {len(index.read_text(encoding='utf-8').splitlines())} 行"
            f" HTML → {index.relative_to(REPO)}（chmod 644）")
        start_p23_html(index)
        facts_html = shot_html(work, index)

        # ---- 还原 + GIF
        restore_frontend()
        meta = run_browser_capture(work)
        make_gif(work, meta)

        ok = True
        section("真跑事实汇总（写进报告用）")
        say(f"    真前端：步骤轨 {facts_frontend.get('stepsCount')} 条 = 完成 "
            f"{facts_frontend.get('railSuccess')} + 未触发 {facts_frontend.get('railSkipped')}"
            f"（校正SQL）；badge {facts_frontend.get('badgesAfter')}；结果表 "
            f"{facts_frontend.get('tableHeaders')} → {facts_frontend.get('tableCells')}")
        say(f"    拆一刀：{facts_html.get('title')!r} 的极简页面，同一问题 #out="
            f"{facts_html.get('outText')!r}；table={facts_html.get('tableCount')}、"
            f"rail-item={facts_html.get('railCount')}（装修层拆掉）")
        gif_first = run_cmd(["identify", "-format", "%w %h %n\n", str(GIF_DEMO)],
                            timeout=120).stdout.splitlines()[0].split()
        say(f"    GIF：{GIF_DEMO.name} {gif_first[0]}x{gif_first[1]}（{gif_first[2]} 帧），"
            f"{GIF_DEMO.stat().st_size / 1024:.0f} KB")
        pg = facts_frontend.get("crop") or {}
        say(f"    图 A 尺寸 {image_size(PNG_FRONTEND)}；图 B 尺寸 {image_size(PNG_HTML)}；"
            f"页面内容 {int(pg.get('top', 0))}–{int(pg.get('bottom', 0))}px（1100 宽 @1x）")
    except KeyboardInterrupt:
        say("\n被 Ctrl+C 中断，开始清理……")
        return 130
    except Exception as exc:  # noqa: BLE001
        say(f"\n❌ 出错：{exc}")
        return 1
    finally:
        if work is not None:
            cleanup_workdir(work)
            say(f"\n清理临时工作区 {work} ... done")
        restore_uv_lock()
        if not args.reuse:
            try:
                down_stack()
                verify_clean(before_ids, reuse=False)
                verify_page_images()
            except Exception as exc:  # noqa: BLE001
                say(f"\n❌ 收尾出错：{exc}")
                ok = False
        else:
            try:
                verify_clean(before_ids, reuse=True)
                verify_page_images()
            except Exception as exc:  # noqa: BLE001
                say(f"\n❌ 收尾出错：{exc}")
                ok = False

    say("")
    say("=" * 78)
    if ok:
        say(f"完成：{PNG_FRONTEND.name} / {PNG_HTML.name} / {GIF_DEMO.name}")
        say(f"用时 {time.monotonic() - started:.1f}s；重跑：python3 tutorial/shots/p23_shots.py")
        say("下一步（人工）：把三条 markdown 图片行嵌进 tutorial/page-23.md，"
            "再跑 python3 tutorial/shots/audit_book.py 与 make audit。")
        return 0
    say("未完成：看上面的报错（栈/临时目录已尽力清理）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
