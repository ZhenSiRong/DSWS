#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_page_shots.py —— 配置驱动的通用页面运行截图框架（练本 tutorial/shots）。

    python3 tutorial/shots/render_page_shots.py page-19       # 跑一页
    python3 tutorial/shots/render_page_shots.py --all         # 跑 captures/ 全部配置
    python3 tutorial/shots/render_page_shots.py 19 --dry-run  # 只打印步骤

配置在 tutorial/shots/captures/<page>.json（schema 见 SHOTS-FRAMEWORK.md）：顶层
page/title/output/stack/embed/ocr_keywords + panels；panel = 一块终端窗口
（heading + commands[] + expect_lines[]，display=all 显示全部输出、matched 只显示
命中的真实行做节选）。commands 是页面原文命令，也可用 {run, show} 对象（run=执行
替身，show=false 只跑不显示）；expect_lines 是页面「你应该看到」里必须有、且 … 当
通配的行——逐行对账即页面 ↔ 真跑输出的逐字自检。

流程：rsync /tmp 副本（排除 .git/node_modules/.venv，软链 system/backend/.venv）→ 按 stack
起隔离栈（full: compose -p + .env 端口覆盖，等健康后跑页、跑完 down -v；mysql: 临时
容器 rm -f；none: 离线页）→ PTY 真跑页面命令 → 复用 term_render 的 CSS/字体渲染
深色终端版式 → 无头 Chrome @2x 截图 → 自检（逐行对账/OCR/禁止串/尺寸/页面嵌入）。
自检失败退出码 2（图仍生成），命令出错退出码 1。旧脚本保留为历史、不改它们；embed
默认 verify 只核对，mode=replace 才写页面且重复跑幂等。依赖：google-chrome、
ImageMagick、rsync；重栈页另需 docker；OCR 可选 tesseract。
"""
from __future__ import annotations

import argparse, getpass, json, os, pty, re, select, shutil, signal
import socket, struct, subprocess, sys, tempfile, termios, time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
TMP_ROOT = Path("/tmp/shots-page-framework")    # 副本工作区根（跑完删）
WINDOW_W_CSS, DEVICE_SCALE = 1600, 2            # @2x → PNG 宽 3200
WINDOW_H_CSS, MIN_PNG_H = 3600, 1800
PAGE_BG = "#04070b"
FORBIDDEN = ["/home/", "/root/", "/Users/", "/tmp/", "/var/", ".dsh", "MSYS"]
FULL_PORTS = {"MYSQL_HOST_PORT": 13337, "ES_HOST_PORT": 19237,
              "QDRANT_HOST_PORT": 16357, "BACKEND_HOST_PORT": 18137,
              "FRONTEND_HOST_PORT": 18077}
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>]")

sys.dont_write_bytecode = True                  # 不在 tutorial/shots 里写 __pycache__
sys.path.insert(0, str(HERE))
import term_render as tr  # noqa: E402

tr.CSS = tr.CSS.replace("1100px", f"{WINDOW_W_CSS}px")   # 只换窗宽，版式不动
CSS = tr.CSS + "\n.dim { color: var(--dim); }  /* …（省略）标注 */\n"


def say(msg: str = "") -> None:
    print(msg, flush=True)

def section(title: str) -> None:
    say(f"\n{'─' * 78}\n{title}\n{'─' * 78}")

def norm_line(line: str) -> str:
    return re.sub(r"[ \t\u00a0]+", " ", ANSI_RE.sub("", line)).strip()

def wildcard_regex(expected: str) -> re.Pattern:
    """期望行 → 正则：秒数当通配、… 当 .+?（其余字面量转义）。"""
    text = re.sub(r"in \d+\.\d+s", "in …", norm_line(expected))
    return re.compile(re.escape(text).replace(re.escape("…"), ".+?"))

def note_line(line: str) -> bool:
    text = line.strip()
    return not text or text.startswith("#") or text in ("...", "…", "……")

def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO / path

def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)

def docker(cmd: list[str], timeout: float = 300) -> str:
    proc = subprocess.run(["docker", *cmd], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"docker {' '.join(cmd)} 失败："
                           f"{(proc.stderr or proc.stdout or '')[-1200:]}")
    return proc.stdout or ""

def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["_path"] = str(path)
    cfg.setdefault("page", path.stem); cfg.setdefault("title", cfg["page"])
    cfg.setdefault("output", f"tutorial/images/{cfg['page']}.png")
    cfg.setdefault("work_dir", str(TMP_ROOT / f"work-{cfg['page']}"))
    st = cfg.setdefault("stack", {}); st.setdefault("mode", "none")
    if st["mode"] not in ("none", "mysql", "full"):
        raise ValueError(f"stack.mode 只能是 none/mysql/full：{st['mode']!r}")
    st.setdefault("project", f"shots-{re.sub(r'[^a-z0-9]+', '-', cfg['page'].lower())}")
    st.setdefault("exec_replace", [])
    if st["mode"] == "full": st.setdefault("env_ports", dict(FULL_PORTS))
    mysql = st.setdefault("mysql", {"image": "mysql:8.0", "root_password": "labpass"})
    mysql.setdefault("container", f"{st['project']}-mysql")
    mysql.setdefault("port", (st.get("env_ports") or {}).get("MYSQL_HOST_PORT", 3310))
    if emb := cfg.get("embed"):
        emb.setdefault("mode", "verify"); emb.setdefault("anchor", "## 对账")
        emb.setdefault("position", "before")
    panels = cfg.get("panels") or []
    if not panels: raise ValueError(f"{path.name}：panels 不能为空")
    for i, panel in enumerate(panels, 1):
        if not all(panel.get(k) for k in ("heading", "commands", "expect_lines")):
            raise ValueError(f"{path.name} 第 {i} 个 panel 缺 heading/commands/expect_lines")
        panel.setdefault("display", "all"); panel.setdefault("timeout", 600)
        allow = panel.setdefault("allow_exit", [0])
        panel["allow_exit"] = [allow] if isinstance(allow, int) else list(allow)
        panel["_cmds"] = []
        for c in panel["commands"]:
            c = {"text": c} if isinstance(c, str) else dict(c)
            panel["_cmds"].append({
                "text": c.get("text") or c["run"], "run": c.get("run"),
                "show": c.get("show", True),
                "timeout": float(c.get("timeout", panel["timeout"])),
                "allow_exit": tuple(c.get("allow_exit", panel["allow_exit"]))})
    cfg["_panels"] = panels
    return cfg

def stack_ports(cfg: dict) -> list[int]:
    st = cfg["stack"]
    if st["mode"] == "mysql": return [int(st["mysql"]["port"])]
    return [int(v) for v in st["env_ports"].values()] if st["mode"] == "full" else []

def cfg_exec(cfg: dict, text: str) -> str:
    """页面原文命令 → 隔离环境执行命令（渲染仍显示页面原文）。"""
    st = cfg["stack"]
    if st["mode"] == "full":
        text = re.sub(r"\bdocker compose\b", f"docker compose -p {st['project']}", text)
    elif st["mode"] == "mysql":
        text = text.replace("lab-mysql", st["mysql"]["container"])
    for old, new in st["exec_replace"]: text = text.replace(old, new)
    return text

def cfg_display(cfg: dict, line: str) -> str:
    for old, new in cfg["stack"]["exec_replace"]: line = line.replace(old, new)
    return line

def prepare_workspace(cfg: dict) -> Path:
    """rsync 仓库到 /tmp 副本：命令在副本里跑，图里不出现绝对路径。"""
    work = Path(cfg["work_dir"])
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    cmd = ["rsync", "-a"]
    for item in (".git", ".lab", "node_modules", "__pycache__", ".pytest_cache",
                 ".mypy_cache", ".ruff_cache", ".venv", ".env", "design", "packages",
                 "tutorial/images", "atlas"):
        cmd += ["--exclude", item]
    subprocess.run(cmd + [str(REPO) + "/", str(work) + "/"], check=True, timeout=600)
    venv = work / "backend" / ".venv"
    if not venv.exists() and (REPO / "backend" / ".venv").exists():
        venv.symlink_to(REPO / "backend" / ".venv", target_is_directory=True)
    return work

def compose(work: Path, project: str, args: list[str], timeout: float = 900) -> str:
    proc = subprocess.run(["docker", "compose", "-p", project, *args], cwd=work,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(args)} 失败："
                           f"{(proc.stdout or '')[-1200:]}\n{(proc.stderr or '')[-1200:]}")
    return proc.stdout or ""

def wait_stack(work: Path, project: str, timeout: float = 480) -> None:
    """等 compose 栈就绪：长驻容器 running+healthy，一次性容器 exited(0)。"""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        rows = []
        for line in compose(work, project, ["ps", "-a", "--format", "json"]).splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
        bad = [r for r in rows if not (
            (r.get("State") == "running" and r.get("Health", "") in ("", "healthy"))
            or (r.get("State") == "exited" and r.get("ExitCode") == 0))]
        for row in bad:
            if row.get("State") == "exited" and row.get("ExitCode") not in (0, -1):
                logs = subprocess.run(["docker", "logs", "--tail", "15", row["Name"]],
                                      capture_output=True, text=True).stdout
                raise RuntimeError(f"{row['Name']} 退出码 {row['ExitCode']}：\n{logs[-2000:]}")
        if rows and not bad:
            say(f"      → 栈就绪（{time.monotonic() - t0:.0f}s）：{len(rows)} 个容器")
            return
        time.sleep(2)
    raise RuntimeError(f"{timeout}s 内栈未就绪")

def stack_start(cfg: dict, work: Path) -> dict | None:
    st = cfg["stack"]
    if st["mode"] == "none":
        say("  隔离栈=none（离线页，不启动容器）"); return None
    if st["mode"] == "mysql":
        m = st["mysql"]; name = m["container"]; port = int(m["port"])
        if name in tr.docker_names(): docker(["rm", "-f", name], timeout=120)
        say(f"  起临时 MySQL {name}（127.0.0.1:{port}->3306，不碰 lab-mysql）")
        docker(["run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:3306",
                "-e", f"MYSQL_ROOT_PASSWORD={m['root_password']}", "-e", "MYSQL_USER=didilili",
                "-e", f"MYSQL_PASSWORD={m['root_password']}", m["image"]])
        try:
            for _ in range(150):
                logs = subprocess.run(["docker", "logs", name], capture_output=True,
                                      text=True, encoding="utf-8",
                                      errors="replace").stdout or ""
                if "port: 3306" in logs:
                    say("      → MySQL 就绪")
                    return {"kind": "mysql", "container": name}
                time.sleep(2)
            raise RuntimeError("临时 MySQL 300 秒还没就绪")
        except Exception:
            try: docker(["rm", "-f", name], timeout=120)
            except Exception: pass
            raise
    project = st["project"]
    if any(n.startswith(f"{project}-") for n in tr.docker_names()):
        compose(work, project, ["down", "-v", "--remove-orphans"], timeout=300)
    env_text = (REPO / ".env").read_text(encoding="utf-8")
    for var, port in st["env_ports"].items():
        env_text, n = re.subn(rf"^{var}=.*$", f"{var}={port}", env_text, flags=re.M)
        if n != 1: raise RuntimeError(f"仓库 .env 里找不到 {var}= 这一行")
    (work / ".env").write_text(
        re.sub(r"^FRONTEND_BIND=.*$", "FRONTEND_BIND=127.0.0.1", env_text, flags=re.M),
        encoding="utf-8")
    say(f"  起隔离 compose 栈 project={project}（--no-build，端口覆盖 {st['env_ports']}）")
    compose(work, project, ["up", "-d", "--no-build"], timeout=900)
    wait_stack(work, project)
    return {"kind": "full", "project": project, "work": work}

def stack_stop(handle: dict | None) -> list[str]:
    if not handle: return []
    try:
        if handle["kind"] == "mysql":
            docker(["rm", "-f", handle["container"]], timeout=120)
            return [f"已删临时容器 {handle['container']}"]
        compose(handle["work"], handle["project"], ["down", "-v", "--remove-orphans"],
                timeout=300)
        left = compose(handle["work"], handle["project"],
                       ["ps", "-a", "--format", "{{.Name}}"]).split()
        return ([f"⚠️ 仍有容器残留：{left}"] if left else
                [f"down -v：{handle['project']} 容器/卷/网络已清"])
    except Exception as exc:  # noqa: BLE001
        return [f"⚠️ 清理隔离栈失败：{exc}"]

def run_pty(cmd: str, cwd: Path, timeout: float,
            allowed: tuple[int, ...] = (0,)) -> tuple[list[str], int]:
    """PTY 捕获：保留 stdout/stderr 在真终端里的交织顺序（管道会打乱缓冲）。"""
    env = os.environ.copy()
    env.update({"UV_OFFLINE": "1", "TERM": "dumb", "NO_COLOR": "1",
                "PYTHONDONTWRITEBYTECODE": "1"})
    master, slave = pty.openpty()
    import fcntl
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 200, 240, 0, 0))
    proc = subprocess.Popen(["bash", "-c", cmd], cwd=cwd, stdin=slave, stdout=slave,
                            stderr=slave, close_fds=True, env=env, start_new_session=True)
    os.close(slave)
    chunks, deadline = [], time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=10)
                raise RuntimeError(f"命令超时（{timeout}s）：{cmd}")
            try: ready, _, _ = select.select([master], [], [], 0.5)
            except OSError: break
            if ready:
                try: data = os.read(master, 65536)
                except OSError: break      # 子进程退出后读 master 会报 EIO
                if not data: break
                chunks.append(data)
            elif proc.poll() is not None:   # 没有待读数据且子进程已退出
                break
    finally:
        try: os.close(master)
        except OSError: pass
    code = proc.wait(timeout=timeout)
    lines = ANSI_RE.sub("", b"".join(chunks).decode("utf-8", "replace")).split("\n")
    lines = [line.rstrip("\r") for line in lines]
    while lines and lines[-1] == "": lines.pop()
    if code not in allowed:
        raise RuntimeError(f"命令失败（exit={code}，允许 {allowed}）：{cmd}\n"
                           + "\n".join(lines[-30:]))
    return lines, code

def check_expected(expect_lines: list, actual: list[str]) -> tuple[bool, str]:
    """期望行按顺序命中真跑输出（… 通配；# 注释与 ... 分段行跳过）。"""
    lines = [norm_line(line) for line in actual if norm_line(line)]
    pos, checked, missing = 0, 0, []
    for expected in expect_lines:
        if not isinstance(expected, str) or note_line(expected): continue
        regex = wildcard_regex(expected)
        while pos < len(lines):
            if regex.search(lines[pos]):
                pos, checked = pos + 1, checked + 1
                break
            pos += 1
        else:
            missing.append(expected)
    if missing: return False, f"真跑输出里找不到 {len(missing)} 行：{missing[:3]}"
    return True, f"{checked} 行按顺序命中（输出 {len(lines)} 行）"

def select_display(panel: dict, lines: list[str]) -> list[str]:
    if panel["display"] == "all": return lines
    patterns = [wildcard_regex(item) for item in panel["expect_lines"]
                if isinstance(item, str) and not note_line(item)]
    return [line for line in lines
            if any(regex.search(norm_line(line)) for regex in patterns)]

def run_panel(cfg: dict, work: Path, panel: dict, index: int) -> dict:
    say(f"  panel {index}/{len(cfg['_panels'])} · {panel['heading']}")
    recs: list[dict] = []
    for item in panel["_cmds"]:
        exec_cmd = cfg_exec(cfg, item["run"] or item["text"])
        say(f"    $ {item['text']}" + ("" if exec_cmd == item["text"]
                                       else f"\n      （执行：{exec_cmd}）"))
        t0 = time.monotonic()
        lines, code = run_pty(exec_cmd, work, item["timeout"], item["allow_exit"])
        lines = [cfg_display(cfg, line) for line in lines]
        recs.append({"text": item["text"], "lines": lines, "show": item["show"]})
        say(f"      → exit {code}，{len(lines)} 行（{time.monotonic() - t0:.1f}s）")
    ok, detail = check_expected(panel["expect_lines"],
                                [line for rec in recs for line in rec["lines"]])
    rows: list[tuple[str, str]] = []
    for rec in recs:
        if rec["show"]:
            rows.append(("cmd", rec["text"]))
            rows.extend(("out", line) for line in select_display(panel, rec["lines"]))
    say(f"    逐行对账：{'✅' if ok else '❌'} {detail}")
    return {"panel": panel, "rows": rows, "check": (ok, detail)}

def build_html(panes: list[dict]) -> str:
    chunks = []
    for pane in panes:
        rows: list[str] = []
        for kind, text in pane["rows"]:
            if kind == "cmd": rows.extend(tr.html_cmd_lines(text))
            elif kind == "out": rows.append(tr.html_out_line(text))
            else: rows.append(f'<span class="dim">{tr.esc(text)}</span>')
        chunks.append(f'<div class="pane"><div class="titlebar">{tr.esc(pane["title"])}'
                      f'</div><pre>{"\n".join(rows)}</pre></div>')
    return ('<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f"<style>{CSS}</style></head><body><div class=\"wrap\">"
            f'{"\n".join(chunks)}</div></body></html>\n')

def identify_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(["identify", "-format", "%w %h", str(path)], check=True,
                         capture_output=True, text=True, timeout=60).stdout.split()
    return int(out[0]), int(out[1])

def render_png(cfg: dict, runs: list[dict], tmpdir: Path) -> Path:
    """无头 Chrome @2x 截图 → -trim → 不足 1800px 高补背景。"""
    html_path = tmpdir / f"{cfg['page']}.html"
    html_path.write_text(build_html(
        [{"title": run["panel"]["heading"], "rows": run["rows"]} for run in runs]),
        encoding="utf-8")
    raw = tmpdir / "raw.png"; raw.unlink(missing_ok=True)
    proc = subprocess.run(
        ["google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
         "--hide-scrollbars", f"--force-device-scale-factor={DEVICE_SCALE}",
         f"--window-size={WINDOW_W_CSS},{WINDOW_H_CSS}",
         f"--user-data-dir={tmpdir / 'chrome'}", f"--screenshot={raw}",
         html_path.as_uri()], capture_output=True, text=True, timeout=180)
    if not raw.exists() or not raw.stat().st_size:
        raise RuntimeError("chrome 截图失败：\n" + (proc.stderr or proc.stdout or "")[-4000:])
    if identify_size(raw)[0] != WINDOW_W_CSS * DEVICE_SCALE:
        raise RuntimeError(f"截图宽不是 {WINDOW_W_CSS * DEVICE_SCALE}px（@2x）")
    trimmed = tmpdir / "trim.png"
    subprocess.run(["convert", str(raw), "-trim", "+repage", str(trimmed)],
                   check=True, capture_output=True, timeout=120)
    height = identify_size(trimmed)[1]
    target = resolve(cfg["output"]); target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["convert", str(trimmed), "-gravity", "center", "-background", PAGE_BG,
                    "-extent", f"{WINDOW_W_CSS * DEVICE_SCALE}x{max(height, MIN_PNG_H)}",
                    str(target)], check=True, capture_output=True, timeout=120)
    final_w, final_h = identify_size(target)
    if final_w != WINDOW_W_CSS * DEVICE_SCALE or final_h < MIN_PNG_H:
        raise RuntimeError(f"{target.name} 尺寸 {final_w}x{final_h} 不符合 @2x 约定")
    return target

def ocr_text(png: Path, tmpdir: Path) -> str:
    """深色终端图反色后 OCR；没装 tesseract / Pillow 就返回空串。"""
    if shutil.which("tesseract") is None: return ""
    try: from PIL import Image, ImageOps
    except Exception: return ""
    tmp = tmpdir / "ocr.png"
    with Image.open(png) as image:
        ImageOps.expand(ImageOps.invert(image.convert("L")), border=24, fill=255).save(tmp)
    try:
        return "\n".join(subprocess.run(
            ["tesseract", str(tmp), "stdout", "--psm", psm], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180).stdout or ""
            for psm in ("6", "11"))
    finally:
        tmp.unlink(missing_ok=True)

def forbidden_strings(cfg: dict) -> list[str]:
    items = list(FORBIDDEN) + [getpass.getuser()]
    items += [str(port) for port in stack_ports(cfg)]
    items.append(cfg["stack"].get("project", ""))
    items.append(cfg["stack"].get("mysql", {}).get("container", ""))
    return [item for item in dict.fromkeys(items) if item]

def apply_embed(cfg: dict) -> tuple[bool, str]:
    """页面嵌入：verify 只核对；replace 幂等（同一行在则替换/去重，无则按锚点插入）。"""
    emb = cfg.get("embed")
    if not emb or emb.get("mode") == "off": return True, "未配置（跳过）"
    path = resolve(emb["path"])
    if not path.is_file(): return False, f"页面不存在：{rel(path)}"
    line = f"![{emb.get('alt') or cfg['title']}]({emb['image']})"
    text = path.read_text(encoding="utf-8"); lines = text.splitlines()
    same = [i for i, row in enumerate(lines)
            if row.startswith("![") and f"]({emb['image']})" in row]
    if emb["mode"] == "verify":
        if not same: return False, f"页面缺嵌入行（verify 不写）：{line[:56]}…"
        return True, (f"已嵌入同一行（{rel(path)}，verify 未改写）"
                      if lines[same[0]].strip() == line else
                      f"已嵌同一张图（alt 不同，verify 不写）：{lines[same[0]][:44]}…")
    if same:      # 幂等：替换成新行、去掉重复
        seen, new_lines = False, []
        for i, row in enumerate(lines):
            if i in same:
                if not seen: new_lines.append(line); seen = True
            else: new_lines.append(row)
        new_text = "\n".join(new_lines) + "\n"
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            return True, f"已有同一行 → 已替换/去重（{rel(path)}）"
        return True, "同一行已存在，未改动（幂等）"
    anchor = emb["anchor"]
    index = next((i for i, row in enumerate(lines) if anchor and anchor in row), None)
    if index is None: return False, f"页面里找不到锚点 {anchor!r}"
    insert_at = index if emb["position"] == "before" else index + 1
    path.write_text("\n".join(lines[:insert_at] + ["", line, ""] + lines[insert_at:]) + "\n",
                    encoding="utf-8")
    return True, f"已插入到锚点「{anchor}」{emb['position']}"

def final_checks(cfg: dict, runs: list[dict], png: Path, tmpdir: Path) -> bool:
    ok, shown = True, [run["panel"]["heading"] for run in runs]
    for run in runs:
        for _kind, text in run["rows"]: shown.extend(text.split("\n"))
    width, height = identify_size(png)
    good = width == WINDOW_W_CSS * DEVICE_SCALE and height >= MIN_PNG_H
    ok = ok and good
    say(f"  尺寸      ：{'✅' if good else '❌'} {width}x{height}（@2x，高 ≥{MIN_PNG_H}）")
    say(f"  🖼 输出   ：{rel(png)}  {width}x{height}")
    passed, detail = apply_embed(cfg); ok = ok and passed
    say(f"  页面嵌入  ：{'✅' if passed else '❌'} {detail}")
    hits = [n for n in forbidden_strings(cfg) if any(n in line for line in shown)]
    ok = ok and not hits
    say(f"  禁止串    ：{'✅ 无用户名/绝对路径/隔离端口/口令' if not hits else f'❌ {hits}'}")
    keywords, text = cfg.get("ocr_keywords") or [], ocr_text(png, tmpdir)
    if not text:
        say("  OCR       ：⚠️  没有 tesseract/Pillow，跳过（主对账已用渲染前原文完成）")
    elif not keywords:
        say("  OCR       ：⚠️  配置未给 ocr_keywords，跳过")
    else:
        flat = re.sub(r"[^0-9A-Za-z.]", "", text)
        miss = [k for k in keywords if re.sub(r"[^0-9A-Za-z.]", "", k) not in flat]
        ok = ok and not miss
        say(f"  OCR       ：{'✅' if not miss else '❌'} {len(keywords) - len(miss)}"
            f"/{len(keywords)} 命中" + (f"，未命中 {miss}" if miss else ""))
    return ok

def preflight(cfg: dict) -> None:
    need = ["google-chrome", "convert", "identify", "rsync"]
    if cfg["stack"]["mode"] != "none": need.append("docker")
    if missing := [tool for tool in need if shutil.which(tool) is None]:
        raise RuntimeError(f"缺少依赖：{', '.join(missing)}（本框架不装新依赖）")
    if not (REPO / "backend" / ".venv" / "bin" / "python").exists():
        raise RuntimeError("system/backend/.venv 不存在；先按第 0 页准备好环境")
    if cfg["stack"]["mode"] == "full" and not (REPO / ".env").is_file():
        raise RuntimeError("缺少 .env；先按第 13 页 `make docker-env` 生成")
    busy = []
    for port in stack_ports(cfg):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex(("127.0.0.1", port)) == 0: busy.append(port)
    if busy: raise RuntimeError(f"隔离端口 {busy} 被占用；先停掉占用者再重跑")

def run_one(path: Path) -> tuple[bool, bool]:
    """跑一页：返回 (自检是否全过, 是否执行出错)。"""
    try:
        cfg = load_config(path)
    except Exception as exc:  # noqa: BLE001
        say(f"❌ 配置错误：{exc}"); return False, True
    t0 = time.monotonic(); section(f"{cfg['page']} · {cfg['title']}")
    user_before = tr.docker_names()
    ok, crashed, work, stack = True, False, None, None
    try:
        preflight(cfg)
        work = prepare_workspace(cfg)
        say(f"  工作区={work}（副本，软链 system/backend/.venv；跑完删）")
        stack = stack_start(cfg, work)
        runs = []
        with tempfile.TemporaryDirectory(prefix=f"shots-{cfg['page']}-") as tmp:
            tmpdir = Path(tmp)
            for index, panel in enumerate(cfg["_panels"], 1):
                run = run_panel(cfg, work, panel, index)
                runs.append(run); ok = ok and run["check"][0]
            ok = final_checks(cfg, runs, render_png(cfg, runs, tmpdir), tmpdir) and ok
    except KeyboardInterrupt:
        say("\n被 Ctrl+C 中断，开始清理……"); raise
    except Exception as exc:  # noqa: BLE001
        crashed, ok = True, False; say(f"  ❌ 出错：{exc}")
    finally:
        section("清理")
        for note in stack_stop(stack): say(f"  {note}")
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
            say(f"  {'✅' if not work.exists() else '⚠️ '} 副本已删：{work}")
        user_after = tr.docker_names()
        if user_before == user_after:
            say(f"  ✅ 用户栈未变（{len(user_before)} 个容器前后一致）")
        else:
            say(f"  ⚠️  容器前后不一致：+{sorted(set(user_after) - set(user_before))}"
                f" -{sorted(set(user_before) - set(user_after))}")
        say(f"  用时 {time.monotonic() - t0:.1f}s")
    return ok, crashed

def plan_lines(cfg: dict) -> list[str]:
    st, emb = cfg["stack"], cfg.get("embed")
    lines = [f"  page    ：{cfg['page']} · {cfg['title']}",
             f"  配置    ：{rel(Path(cfg['_path']))}",
             f"  输出    ：{rel(resolve(cfg['output']))}"
             f"（{WINDOW_W_CSS * DEVICE_SCALE}×≥{MIN_PNG_H} px @2x）",
             f"  工作区  ：副本 → {cfg['work_dir']}（rsync 排除 .git/node_modules/.venv，"
             "软链 system/backend/.venv）"]
    if st["mode"] == "none":
        lines.append("  隔离栈  ：none（离线页，不启动容器）")
    elif st["mode"] == "mysql":
        lines.append(f"  隔离栈  ：mysql → 临时容器 {st['mysql']['container']} "
                     f"127.0.0.1:{st['mysql']['port']}->3306，跑完 rm -f")
    else:
        lines.append(f"  隔离栈  ：full → docker compose -p {st['project']} up -d "
                     f"--no-build + .env 端口覆盖 {st['env_ports']}，跑完 down -v")
    for old, new in st["exec_replace"]:
        lines.append(f"            执行替身 {old} → {new}（渲染时换回）")
    if emb:
        lines.append(f"  页面嵌入：{emb['mode']} → {emb['path']}（{emb['image']}；"
                     f"锚点 {emb['anchor']!r} {emb['position']}）")
    for index, panel in enumerate(cfg["_panels"], 1):
        lines.append(f"  panel {index}/{len(cfg['_panels'])} · {panel['heading']}"
                     f"（display={panel['display']}）")
        for item in panel["_cmds"]:
            lines.append(f"    $ {item['text']}")
            exec_cmd = cfg_exec(cfg, item["run"] or item["text"])
            if exec_cmd != item["text"]: lines.append(f"      （执行：{exec_cmd}）")
    lines.append(f"  自检    ：逐行对账 / OCR {len(cfg.get('ocr_keywords') or [])} 关键字"
                 " / 禁止串 / 尺寸 / 页面嵌入")
    lines.append("  清理    ：down -v（如起栈）/ 删副本 / 用户栈前后对比")
    return lines

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="通用页面运行截图框架：读 captures/<page>.json，真跑命令并渲染截图")
    parser.add_argument("page_id", nargs="?", help="页 id（page-19 或 19）")
    parser.add_argument("--all", action="store_true", dest="all_pages",
                        help="跑 captures/ 下全部配置")
    parser.add_argument("--dry-run", action="store_true", help="只打印步骤，不执行")
    args = parser.parse_args(argv)
    if not args.all_pages and not args.page_id: parser.error("给出 <page-id> 或用 --all")
    captures = HERE / "captures"
    if args.all_pages:
        files = sorted(captures.glob("*.json"))
    else:
        name = args.page_id if args.page_id.startswith("page-") else f"page-{args.page_id}"
        files = [captures / f"{name.removesuffix('.json')}.json"]
    if not files:
        say(f"❌ {captures} 下没有 *.json 配置"); return 2
    if args.dry_run:
        section("render_page_shots.py · --dry-run（只打印步骤，不执行、不写文件）")
        for path in files:
            if not path.is_file(): say(f"❌ 找不到配置：{path}"); return 2
            say("\n" + "=" * 78)
            for line in plan_lines(load_config(path)): say(line)
        say(f"\n（--dry-run 完成：{len(files)} 份配置，未执行任何命令）"); return 0
    failed = crashed = False
    for path in files:
        if not path.is_file():
            say(f"❌ 找不到配置：{path}"); failed = True; continue
        ok, page_crashed = run_one(path)
        failed, crashed = failed or not ok, crashed or page_crashed
    if crashed:
        say("\n❌ 有页面在跑命令时出错（退出码 1）"); return 1
    say("\n✅ 全部配置通过自检" if not failed else "\n⚠️  有自检未过（见图与上面 ❌ 行）")
    return 0 if not failed else 2

if __name__ == "__main__":
    sys.exit(main())
