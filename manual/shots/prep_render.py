#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prep_render.py —— 真跑练本第 0 页（开课前准备）的命令，渲染成终端截图。

一条命令重跑这张图（在仓库根目录）：

    python3 manual/shots/prep_render.py

它模拟**学生刚克隆完**的状态：用 `git archive HEAD` 把已提交的文件导到临时目录
（所以没有 `.env`、`backend/.venv`、`frontend/node_modules`），在那里逐字真跑
`manual/page-00.md`「## 动手」里的 5 组命令，捕获「命令 + 真实输出」，复用
`term_render.py` 的 HTML 模板与 chrome 无头截图，输出
`manual/images/page-00-prep.png`（1100px 宽，深色终端版式）。

`uv sync` 的 62 行 `+ 包名==版本` 安装清单太长，图上只保留前 2 行 + 一行省略说明。
不新增依赖：只用本机已有的 git / docker / uv / node / make / google-chrome / ImageMagick。
跑完自动删临时目录，不改仓库文件。
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True  # 不生成 manual/shots/__pycache__

import term_render as tr  # noqa: E402

OUT_NAME = "page-00-prep.png"
FORBIDDEN = ["/home/", "/Users/", ".dsh", "zhensirong"]

# 与 manual/page-00.md「## 动手」逐字一致（改页面时这里要同步）
STEPS = [
    "docker --version",
    "uv --version\nnode -v\ncurl --version | head -1",
    "make install",
    "backend/.venv/bin/python -V",
    'for p in 3307 8000 8081; do (echo >/dev/tcp/127.0.0.1/$p) 2>/dev/null && echo "$p 被占用" || echo "$p 空闲"; done',
]

PKG_LIST_NOTE = "…（其余安装清单略）"


def run(cmd: str, cwd: Path, timeout: float = 600.0) -> list[str]:
    proc = subprocess.run(
        cmd, shell=True, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    out = proc.stdout or ""
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败（exit={proc.returncode}）：{cmd}\n--- 输出 ---\n{out}")
    return out.splitlines()


def curate_for_shot(lines: list[str]) -> list[str]:
    """把 uv 的 62 行安装清单压成 2 行 + 省略说明，其余原样。"""
    kept: list[str] = []
    pkg_seen = 0
    for line in lines:
        if re.match(r"^ \+ \S+==\S+$", line):
            pkg_seen += 1
            if pkg_seen <= 2:
                kept.append(line)
            elif pkg_seen == 3:
                kept.append(PKG_LIST_NOTE)
            continue
        kept.append(line)
    return kept


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="prep-render-") as tmp:
        work = Path(tmp)
        clone = work / "clone"
        clone.mkdir()
        archive = subprocess.run(
            "git archive HEAD | tar -x -C " + shlex.quote(str(clone)),
            shell=True, cwd=tr.REPO, capture_output=True, text=True, timeout=120,
        )
        if archive.returncode != 0:
            raise RuntimeError("git archive 失败：\n" + (archive.stderr or ""))

        for gone in (".env", "backend/.venv", "frontend/node_modules"):
            if (clone / gone).exists():
                raise RuntimeError(f"临时克隆里不该有 {gone}，模拟学生环境失败")

        records: dict[int, dict] = {}
        raw_outputs: dict[int, list[str]] = {}
        for i, cmd in enumerate(STEPS):
            print(f"[{i + 1}/{len(STEPS)}] $ {cmd}", flush=True)
            lines = run(cmd, clone)
            raw_outputs[i] = lines
            records[i] = {"cmd": cmd, "lines": curate_for_shot(lines)}

        ports = raw_outputs[len(STEPS) - 1]
        if ports != ["3307 空闲", "8000 空闲", "8081 空闲"]:
            raise RuntimeError(
                "端口现在不空，图和页面会对不上；先停掉占用者再重跑：\n" + "\n".join(ports)
            )

        panes = [
            {
                "title": "终端 · 第 0 页的真跑输出（模拟刚克隆完）",
                "items": [
                    item
                    for i in range(len(STEPS))
                    for item in ({"step": i, "part": "cmd"}, {"step": i, "part": "out"})
                ],
            }
        ]

        html_text = tr.build_html(panes, records)
        html_path = work / "page-00-prep.html"
        html_path.write_text(html_text, encoding="utf-8")

        raw = work / "page-00-prep.raw.png"
        target = tr.IMAGES / OUT_NAME
        tr.chrome_screenshot(html_path, raw, work / "chrome-profile")
        w, h = tr.trim_png(raw, target)

    text = target.name + "\n" + "\n".join(
        line for lines in raw_outputs.values() for line in lines
    )
    leaked = [p for p in FORBIDDEN if p in text]
    if leaked:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"图里出现了不该有的信息：{leaked}")
    if re.search(r"\b(root|zhensirong)@", text):
        target.unlink(missing_ok=True)
        raise RuntimeError("图里出现了用户名/主机名提示符")
    print(f"🖼  {target.relative_to(tr.REPO)}  {w}x{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
