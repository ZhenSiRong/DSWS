#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_completeness.py —— 《建成证明》v2 海报（A4 一页 ×2：答案版 + 空白版）。

在仓库根目录一条命令重跑（同时出两张 PNG，README 里的链接不变）：

    python3 tutorial/shots/render_completeness.py

读：`tutorial/completeness/v2/data.json`（**单源数据**：12 件交付物 × 1–3 个检验点，共 24 个）
写：`tutorial/completeness/poster-answer.png`  答案版，全部检验点 ■
    `tutorial/completeness/poster-blank.png`   空白版，检验点方框留空，打印后自己涂

依据 `materials/humen-desicions/09-ablation-course.md`：

- **D42**：行 = 具体交付物（container / db / data / process / endpoint / function / chain），
  每行显式写「位置」，1–3 个检验点，每点给「命令 + 期望输出」；
  勾满一行 = 这件东西建成，12 行全满 = 系统完备（AON 只作顺序提示，不参与勾选）。
- **D43**：海报直读 v2 数据、输出仍为 `completeness/poster-*.png`，并还掉 D39 遗留的
  「海报硬编码、非单源」债；v1（行=架构节点的四层矩阵）已归档到 `completeness/archive-v1/`。

版式沿用 v2 单页样例（`tutorial/shots/render_v2_sample.py` 的模板与校验逻辑）：一张
「零件 | 位置 | 检验点（命令 → 期望输出）| 页」表 + 页眉 + 底部三条完备判据 + 生成命令脚注；
A4 竖向、黑白灰、Noto Sans CJK，命令与输出用等宽。

脚本做四件事：

1. **逐条溯源校验**：每个检验点的「期望输出」必须能在 `evidence_source` 指向的
   `tutorial/page-0X.md` 正文里逐字 grep 到（多行逐行查），并标出命中的页内段落
   （「你应该看到」/「对账」/「重来一遍」等）。任一 FAIL 就退出码 1 ——
   **FAIL 只许修 `completeness/v2/data.json`，不许改十页正文**。
   同时核对结构：12–14 件交付物、每件 1–3 个检验点、依赖 id 存在、页面存在、计数自洽。
2. **组版**：HTML + CSS，设计画布 1240×1754（= A4 @150dpi），`@page size A4`。
3. **量高**：headless Chrome 读回 `#poster` 内容宽度、内容自然高度与页脚底边，
   超过 A4 画布（1240×1754）就报错退出，不悄悄裁切。
4. **截图 + 核对**：`--window-size=1240,1754 --force-device-scale-factor=2`，
   成品 2480×3508（= A4 @300dpi）；再核对 PNG 尺寸、内容高度，以及 HTML / PNG / 数据里
   没有用户名 / 绝对路径 / 口令；成品也不许出现 v1 或「单页样例」口径的字样。

确定性：除页脚印的「生成时间」外，两张 PNG 完全由 `v2/data.json` 决定（同一分钟内重跑，
字节一致）。测试/打印可放心缓存。

依赖：本机已有的 python3 / google-chrome / Noto Sans CJK SC / DejaVu Sans(Mono)。
不改 `v2/data.json`、`explorer.html`、`build_explorer.py`、十页正文、flow 文件与历史截图。
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tutorial/shots
REPO = HERE.parents[1]                          # 仓库根目录
COMPLETENESS_DIR = REPO / "manual" / "completeness"
V2_DIR = COMPLETENESS_DIR / "v2"
DATA_PATH = V2_DIR / "data.json"
ANSWER_PNG = COMPLETENESS_DIR / "poster-answer.png"
BLANK_PNG = COMPLETENESS_DIR / "poster-blank.png"
PAGES_DIR = REPO / "manual"

CHROME = "google-chrome"
PAGE_W, PAGE_H = 1240, 1754                     # A4 竖向 @150dpi
SHOT_W, SHOT_H = PAGE_W * 2, PAGE_H * 2         # A4 竖向 @300dpi

# 页眉 kicker 与脚注「重跑命令」的回退值：v2/data.json 里的 kicker / rerun 仍是
# D42「单页样例」口径（“…供确认后再全量替换 v1” / “render_v2_sample.py”），而
# v2/data.json 不在本脚本的改动范围；成品海报必须写 D43 的生产口径与真实生成命令。
# （数据升为生产口径后，effective_kicker / effective_rerun 会自动改用数据里的值。）
KICKER = "D43 · v2 单源 · 12 件交付物 × 24 个检验点"
RERUN = "python3 tutorial/shots/render_completeness.py"


def effective_kicker(data: dict) -> tuple[str, bool]:
    """页眉 kicker：data.json 若已是生产口径就用它；否则用 D43 口径（当前是 D42 样例口径）。"""
    raw = str(data.get("kicker") or "").strip()
    if raw and "样例" not in raw:
        return raw, False
    return KICKER, True


def effective_rerun(data: dict) -> tuple[str, bool]:
    """脚注重跑命令：data.json 若已指向本脚本就用它；否则固定为本脚本命令（当前指 v2 样例脚本）。"""
    raw = str(data.get("rerun") or "").strip()
    if raw and "render_v2_sample" not in raw:
        return raw, False
    return RERUN, True

# 成图 / HTML / 数据里不许出现的字符串（本机用户名、绝对路径、口令）
HOST_USER = Path.home().name          # 不在源码里写死本机用户名
FORBIDDEN = ["/home/", "/Users/", "/tmp/", HOST_USER, "root@", ".dsh",
             "-uroot", "-plab", "labpass", "MYSQL_ROOT_PASSWORD"]
# 目视/OCR 抽查必须能在图上辨认的关键值
REQUIRED_TOKENS = ["41099.5", "COUNT(*)", "12/12", "ERR_CONNECTION_REFUSED",
                   "8.0.46", "115"]
# 成品海报不许残留的 v1 / 样例口径字样（数据单源里这两处由上面的 KICKER / RERUN 覆盖）
STALE_TERMS = ["四层", "15 列", "责任 × 证据", "单页样例", "样例", "render_v2_sample"]

BOX = {"answer": "■", "blank": "▢"}
PAGE_REF = re.compile(r"page-(\d{2})\.md:(\d+)(?:[-,–](\d+))?")
HEADING = re.compile(r"^##\s+(.+?)\s*$")
INLINE_CODE = re.compile(r"`([^`]+)`")

REQUIRED_TOP_KEYS = ("schema", "title", "subtitle", "counts", "legend",
                     "completeness_criteria", "notes", "artifacts")


# ------------------------------------------------------------------ 小工具

def esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def rich(text: str) -> str:
    """把 `code` 渲染成等宽小标签，其余部分做 HTML 转义。"""
    out: list[str] = []
    pos = 0
    for m in INLINE_CODE.finditer(text):
        out.append(esc(text[pos:m.start()]))
        out.append(f'<code>{esc(m.group(1))}</code>')
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def plain(text: str) -> str:
    return INLINE_CODE.sub(r"\1", text)


def code_text(text: str) -> str:
    """期望输出：转义后加 <wbr>，让长 JSON 优先在逗号 / 分号 / 管道 / 键值冒号后断行。"""
    out = esc(text)
    for ch in (",", ";", "|"):
        out = out.replace(ch, ch + "<wbr>")
    out = out.replace('":', '":<wbr>')
    return out


def command_html(text: str) -> str:
    """命令：按空格切成 token，token 内不许断行（避免把 --data-urlencode、中文参数拆开）。"""
    parts = [p for p in text.split(" ") if p]
    return " ".join(f'<span class="tok">{esc(p)}</span>' for p in parts)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def page_filename(page_id: str) -> Path:
    return PAGES_DIR / f"{page_id}.md"


def page_label(pages: list[str]) -> str:
    labels = []
    for pid in pages:
        num = pid.split("-", 1)[1].lstrip("0") or "0"
        labels.append(f"第 {num} 页")
    return "、".join(labels)


def sections_of(lines: list[str]) -> list[tuple[int, str]]:
    secs: list[tuple[int, str]] = []
    for idx, line in enumerate(lines, 1):
        m = HEADING.match(line)
        if m:
            secs.append((idx, m.group(1)))
    return secs


def section_at(line_no: int, secs: list[tuple[int, str]]) -> str:
    title = "（页首）"
    for start, name in secs:
        if start <= line_no:
            title = name
        else:
            break
    return title


# ------------------------------------------------------------------ 读数据 / 结构校验

def load_data() -> dict:
    if not DATA_PATH.exists():
        raise SystemExit(f"找不到数据文件 {DATA_PATH}（应在 tutorial/completeness/v2/data.json）")
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"data.json 不是合法 JSON：{exc}") from exc
    return data


def validate_structure(data: dict) -> None:
    errs: list[str] = []

    missing = [k for k in REQUIRED_TOP_KEYS if k not in data]
    if missing:
        errs.append(f"data.json 缺顶层字段：{', '.join(missing)}")
    if not str(data.get("schema", "")).startswith("completeness-v2"):
        errs.append(f"schema={data.get('schema')!r}，应为 completeness-v2/…")
    if len(data.get("legend") or []) != 3:
        errs.append(f"legend 必须三条（▢/◧/■），实际 {len(data.get('legend') or [])} 条")
    if len(data.get("completeness_criteria") or []) != 3:
        errs.append("completeness_criteria 必须三条（D42 完备判据）")
    if not data.get("notes"):
        errs.append("notes 为空：脚注至少写清判据出处与机器差异")

    arts = data.get("artifacts") or []
    if not (12 <= len(arts) <= 14):
        errs.append(f"交付物件数 {len(arts)}，D42 要求 12–14 件")
    ids = {a.get("id") for a in arts}
    total_cp = 0
    for a in arts:
        no = a.get("no", "?")
        for key in ("id", "name", "kind", "location", "pages", "checkpoints", "depends_on"):
            if key not in a:
                errs.append(f"#{no} 缺字段 {key}")
        pages = a.get("pages") or []
        if not pages:
            errs.append(f"#{no} 没有 pages")
        for pid in pages:
            if not page_filename(pid).exists():
                errs.append(f"#{no} 的页面 {pid}.md 不存在")
        cps = a.get("checkpoints") or []
        if not (1 <= len(cps) <= 3):
            errs.append(f"#{no} 检验点 {len(cps)} 个，D42 要求每行 1–3 个")
        total_cp += len(cps)
        for i, cp in enumerate(cps, 1):
            for key in ("criterion", "command", "expected_output", "evidence_source"):
                if not str(cp.get(key, "")).strip():
                    errs.append(f"#{no} 第 {i} 个检验点缺 {key}")
            m = PAGE_REF.search(cp.get("evidence_source", ""))
            if not m:
                errs.append(f"#{no} 第 {i} 个检验点 evidence_source 里没有 page-XX.md:行号")
            elif f"page-{m.group(1)}" not in pages:
                errs.append(f"#{no} 第 {i} 个检验点的溯源页 page-{m.group(1)} 不在 pages 里")
            if m and not page_filename(f"page-{m.group(1)}").exists():
                errs.append(f"#{no} 第 {i} 个检验点的页面 page-{m.group(1)}.md 不存在")
        for dep in a.get("depends_on") or []:
            if dep not in ids:
                errs.append(f"#{no} 的 depends_on 指向不存在的 id {dep!r}")
            elif dep == a.get("id"):
                errs.append(f"#{no} 依赖自己")
    counts = data.get("counts") or {}
    if counts.get("artifacts") not in (None, len(arts)):
        errs.append(f"counts.artifacts={counts.get('artifacts')} 与实际 {len(arts)} 不符")
    if counts.get("checkpoints") not in (None, total_cp):
        errs.append(f"counts.checkpoints={counts.get('checkpoints')} 与实际 {total_cp} 不符")
    if errs:
        print("✗ 数据结构校验失败：")
        for e in errs:
            print(f"  - {e}")
        raise SystemExit(1)
    print(f"✓ 数据结构：{len(arts)} 件交付物 / {total_cp} 个检验点 / "
          f"每件 {min(len(a['checkpoints']) for a in arts)}–"
          f"{max(len(a['checkpoints']) for a in arts)} 个检验点")


# ------------------------------------------------------------------ 逐条溯源校验

def trace_check(data: dict) -> int:
    total = ok = fails = 0
    print("\n逐条溯源校验（期望输出必须能在对应页正文 grep 到）")
    for art in data["artifacts"]:
        cps = art["checkpoints"]
        print(f"\n#{art['no']:02d} {plain(art['name'])}  "
              f"[{page_label(art['pages'])}]  {len(cps)} 个检验点")
        for i, cp in enumerate(cps, 1):
            total += 1
            expected_lines = [ln for ln in cp["expected_output"].split("\n") if ln.strip()]
            m = PAGE_REF.search(cp["evidence_source"])
            problems: list[str] = []
            hits: list[tuple[int, str]] = []
            outside: list[int] = []
            if not m:
                problems.append("evidence_source 里没有 page-XX.md:行号")
            else:
                page_file = page_filename(f"page-{m.group(1)}")
                lines = page_file.read_text(encoding="utf-8").splitlines()
                norm_lines = [normalize(ln) for ln in lines]
                secs = sections_of(lines)
                lo, hi = int(m.group(2)), int(m.group(3) or m.group(2))
                for exp in expected_lines:
                    needle = normalize(exp)
                    all_hits = [n for n, nl in enumerate(norm_lines, 1) if needle in nl]
                    if not all_hits:
                        problems.append(f"页内 grep 不到期望输出：{exp!r}")
                        continue
                    in_range = [n for n in all_hits if lo <= n <= hi]
                    chosen = in_range[0] if in_range else all_hits[0]
                    if not in_range:
                        outside.append(chosen)
                    hits.append((chosen, section_at(chosen, secs)))
            if problems:
                fails += 1
                print(f"  [{i}] FAIL  {plain(cp['criterion'])}")
                for p in problems:
                    print(f"        - {p}")
                continue
            ok += 1
            cited = f"page-{m.group(1)}.md:{m.group(2)}"
            if m.group(3):
                cited += f"-{m.group(3)}"
            sec_names = []
            for _, name in hits:
                if name not in sec_names:
                    sec_names.append(name)
            where = " / ".join(f"「{s}」" for s in sec_names)
            extra = ""
            if outside:
                extra = f"（页内实际命中 {'、'.join(f':{n}' for n in outside)}，不在引用行段，仍算页内原文）"
            print(f"  [{i}] PASS  {plain(cp['criterion'])}  ·  {cited} {where}{extra}")
    print(f"\n汇总：{ok}/{total} 检验点溯源 PASS · FAIL {fails}")
    return fails


# ------------------------------------------------------------------ HTML 组版

def header_html(data: dict, mode: str, total_cp: int, total_art: int) -> str:
    kicker, _ = effective_kicker(data)
    if mode == "answer":
        badge = f"{BOX['answer']} {total_cp}/{total_cp} · {total_art}/{total_art} 行"
        badge_note = "答案版 · 全部检验点 ■（供对照）"
    else:
        badge = f"{BOX['blank']} 0/{total_cp} · 0/{total_art} 行"
        badge_note = "空白版 · 打印后自己涂：▢ → ◧ → ■"
    return (
        '<div class="hdr">'
        '<div class="hdr-left">'
        f'<div class="kicker">{rich(kicker)}</div>'
        f'<h1>{rich(data["title"])}</h1>'
        f'<div class="sub">{rich(data["subtitle"])}</div>'
        f'<div class="meta">判据出处：{rich("`tutorial/page-00…09.md` 的「你应该看到」真跑输出（脚本逐条溯源校验）")}</div>'
        f'<div class="meta">{rich(data["order_hint"])}</div>'
        '</div>'
        '<div class="hdr-right">'
        f'<div class="badge {mode}">{badge}</div>'
        f'<div class="badge-note">{badge_note}</div>'
        '</div></div>'
    )


def checkpoint_html(cp: dict, mode: str) -> str:
    expected_lines = [ln for ln in cp["expected_output"].split("\n") if ln.strip()]
    expected = "<br>".join(code_text(ln) for ln in expected_lines)
    return (
        '<div class="cp">'
        f'<div class="cp-h"><span class="box {mode}">{BOX[mode]}</span>'
        f'<span class="crit">{rich(cp["criterion"])}</span></div>'
        f'<div class="cmd">{command_html(cp["command"])}</div>'
        f'<div class="exp"><span class="arrow">→</span> {expected}</div>'
        '</div>'
    )


def artifact_row_html(art: dict, mode: str) -> str:
    cps = art["checkpoints"]
    cols = f"cols-{len(cps)}"
    checks = "".join(checkpoint_html(cp, mode) for cp in cps)
    return (
        '<tr>'
        f'<td class="art"><div class="ano">{art["no"]:02d}</div>'
        f'<div class="aname">{rich(art["name"])}</div>'
        f'<div class="akind">{rich(art["kind"])}</div></td>'
        f'<td class="loc">{rich(art["location"])}</td>'
        f'<td class="chk"><div class="cps {cols}">{checks}</div></td>'
        f'<td class="pg">{page_label(art["pages"])}</td>'
        '</tr>'
    )


def table_html(data: dict, mode: str, total_cp: int) -> str:
    rows = "".join(artifact_row_html(a, mode) for a in data["artifacts"])
    return (
        '<table class="main">'
        '<colgroup><col style="width:158px"><col style="width:214px">'
        '<col><col style="width:60px"></colgroup>'
        '<thead><tr><th class="th-art">零件</th><th class="th-loc">位置</th>'
        '<th class="th-chk">检验点（命令 → 期望输出）'
        f'<span class="th-count">{total_cp} 格</span></th>'
        '<th class="th-pg">页</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def footer_html(data: dict, mode: str, now: str) -> str:
    rerun, _ = effective_rerun(data)
    criteria = []
    for item in data["completeness_criteria"]:
        criteria.append(
            '<div class="cr">'
            f'<span class="box {mode}">{BOX[mode]}</span>'
            f'<div class="cr-t"><b>{rich(item["text"])}</b>'
            f'<span>{rich(item["hint"])}</span></div>'
            '</div>'
        )
    legend_line = " · ".join(f"{item['mark']} {item['name']}" for item in data["legend"])
    notes = "".join(f'<div class="note">{rich(n)}</div>' for n in data.get("notes", []))
    return (
        '<div class="foot">'
        '<div class="cr-h">完备判据（三条全 ■ 才算完备）</div>'
        f'<div class="criteria">{"".join(criteria)}</div>'
        '<div class="foot-meta">'
        f'<span><b>生成时间</b> {esc(now)}</span>'
        '<span class="sep">·</span>'
        f'<span><b>重跑命令</b> <code>{esc(rerun)}</code></span>'
        '<span class="sep">·</span>'
        f'<span><b>图例</b> {esc(legend_line)}</span>'
        '</div>'
        f'<div class="notes">{notes}</div>'
        '</div>'
    )


def build_html(data: dict, mode: str, now: str) -> str:
    total_cp = sum(len(a["checkpoints"]) for a in data["artifacts"])
    total_art = len(data["artifacts"])
    body = (
        header_html(data, mode, total_cp, total_art)
        + table_html(data, mode, total_cp)
        + footer_html(data, mode, now)
    )
    return (
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<title>建成证明 v2 海报 {mode}</title>'
        f'<style>{CSS}</style></head><body>'
        f'<div class="poster {mode}" id="poster">{body}</div>'
        '<script>'
        'window.addEventListener("load", function () {'
        'var p = document.getElementById("poster");'
        'var t = document.querySelector("table.main");'
        'var f = document.querySelector(".foot");'
        'var pr = p.getBoundingClientRect(), tr = t.getBoundingClientRect(),'
        '    fr = f.getBoundingClientRect();'
        'var natural = Math.round(tr.bottom - pr.top) + 12'
        '  + Math.round(fr.height) + Math.round(parseFloat(getComputedStyle(p).paddingBottom));'
        'document.title = "DIM " + p.scrollWidth + " " + p.scrollHeight + " "'
        '  + Math.round(fr.bottom - pr.top) + " " + natural;'
        '});'
        '</script></body></html>\n'
    )


# ------------------------------------------------------------------ CSS

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #ffffff; }
body { width: 1240px; min-height: 1754px; }
.poster {
  width: 1240px; min-height: 1754px; padding: 24px 38px 26px;
  display: flex; flex-direction: column;
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
  color: #111; -webkit-font-smoothing: antialiased;
}
code, .cmd, .exp, .loc code, .note code, .foot-meta code {
  font-family: "DejaVu Sans Mono", "Noto Sans CJK SC", monospace;
}

/* ---------- 页眉 ---------- */
.hdr { display: flex; justify-content: space-between; align-items: flex-start;
       border-bottom: 3.5px solid #111; padding-bottom: 9px; }
.hdr-left { flex: 1 1 auto; min-width: 0; }
.kicker { font-size: 12px; letter-spacing: .6px; color: #555; }
h1 { margin: 2px 0 0; font-size: 35px; line-height: 1.12; font-weight: 900; letter-spacing: .3px; }
.sub { margin-top: 3px; font-size: 15px; color: #111; }
.sub b { font-weight: 900; }
.meta { margin-top: 3px; font-size: 10.6px; color: #555; line-height: 1.32; }
.hdr-right { flex: 0 0 auto; text-align: right; padding-left: 16px; }
.badge { display: inline-block; border: 2.5px solid #111; border-radius: 5px;
         padding: 4px 13px; font-size: 19px; font-weight: 900; letter-spacing: 1.5px;
         font-family: "DejaVu Sans", "Noto Sans CJK SC", sans-serif; }
.badge.answer { background: #111; color: #fff; }
.badge.blank { background: #fff; color: #111; }
.badge-note { margin-top: 4px; font-size: 11px; color: #555; }

/* ---------- 物料清单表 ---------- */
table.main { width: 100%; border-collapse: collapse; table-layout: fixed;
             margin-top: 9px; border: 1.6px solid #111; }
.main th, .main td { border-bottom: 1px solid #b9b9b9; vertical-align: top;
                     padding: 6px 7px; }
.main thead th { background: #e7e7e7; border-bottom: 2px solid #111;
                 font-size: 13px; font-weight: 900; text-align: left;
                 padding: 5px 7px; }
.main tbody tr:last-child td { border-bottom: none; }
.th-chk .th-count { float: right; font-size: 10.2px; color: #555; font-weight: 600; }
.th-pg { text-align: center !important; }

.art { border-right: 1px solid #b9b9b9; }
.ano { display: inline-block; background: #111; color: #fff; border-radius: 2px;
       font-family: "DejaVu Sans Mono", monospace; font-size: 10.5px; line-height: 15px;
       padding: 0 4px; font-weight: 700; }
.aname { margin-top: 2px; font-size: 14.6px; font-weight: 900; line-height: 1.18;
         word-break: keep-all; }
.aname code { font-size: 12.2px; font-weight: 700; background: #ededed;
              border-radius: 2px; padding: 0 2px; }
.akind { margin-top: 2px; font-size: 10.2px; color: #666; line-height: 1.25; }

.loc { border-right: 1px solid #b9b9b9; font-size: 10.9px; line-height: 1.34; color: #222; }
.loc code { font-size: 10.4px; background: #f0f0f0; border-radius: 2px; padding: 0 2px; }

.chk { border-right: 1px solid #b9b9b9; }
.cps { display: flex; gap: 6px; align-items: stretch; }
.cp { flex: 1 1 0; min-width: 0; border: 1px solid #b3b3b3; border-radius: 4px;
      padding: 3px 6px 4px; background: #fff; }
.cp-h { display: flex; align-items: flex-start; gap: 3px; }
.box { font-family: "DejaVu Sans", "Noto Sans CJK SC", sans-serif;
       font-size: 16px; line-height: 1; flex: 0 0 auto; width: 16px; text-align: center; }
.box.answer { color: #111; }
.box.blank { color: #111; }
.crit { font-size: 11.9px; font-weight: 700; line-height: 1.22; }
.crit code { font-size: 10.9px; background: #ededed; border-radius: 2px; padding: 0 1px; }
.cmd { margin: 3px 0 2px; padding: 2px 5px; background: #f1f1f1;
       border-left: 2px solid #999; font-size: 10.1px; line-height: 1.28; color: #222;
       overflow-wrap: break-word; }
.exp { font-size: 11.9px; font-weight: 700; line-height: 1.28;
       overflow-wrap: break-word; word-break: keep-all; }
.tok { white-space: nowrap; }
.exp .arrow { font-weight: 400; }
.pg { text-align: center; font-size: 11.8px; font-weight: 900; line-height: 1.3; }

/* ---------- 页脚 ---------- */
.foot { margin-top: auto; padding-top: 9px; border-top: 3px solid #111; }
.cr-h { font-size: 11.8px; font-weight: 900; letter-spacing: .5px; margin-bottom: 4px; }
.criteria { display: flex; gap: 7px; }
.cr { flex: 1 1 0; display: flex; align-items: flex-start; gap: 5px;
      border: 1.4px solid #111; border-radius: 4px; padding: 4px 8px; }
.cr-t { min-width: 0; }
.cr-t b { display: block; font-size: 12px; font-weight: 900; line-height: 1.2; }
.cr-t span { display: block; margin-top: 1px; font-size: 10px; line-height: 1.28; color: #333; }
.cr-t code { font-size: 9.8px; background: #ededed; border-radius: 2px; padding: 0 1px; }
.foot-meta { margin-top: 7px; font-size: 10.4px; color: #333; }
.foot-meta b { font-weight: 900; }
.foot-meta code { font-size: 10px; background: #ededed; border-radius: 2px; padding: 0 2px; }
.foot-meta .sep { color: #999; padding: 0 4px; }
.notes { margin-top: 5px; }
.note { font-size: 9.2px; color: #555; line-height: 1.32; }
.note code { font-size: 9px; background: #f0f0f0; border-radius: 2px; padding: 0 1px; }
"""


# ------------------------------------------------------------------ Chrome

def chrome(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--disable-dev-shm-usage"]
    return subprocess.run(cmd + args, capture_output=True, text=True, timeout=180)


def measure(page_html: Path, work: Path) -> tuple[int, int, int, int]:
    proc = chrome([
        f"--window-size={PAGE_W},{PAGE_H}",
        "--virtual-time-budget=5000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", page_html.as_uri(),
    ])
    m = re.search(r"<title>DIM (\d+) (\d+) (\d+) (\d+)</title>", proc.stdout)
    if not m:
        raise SystemExit(f"量高失败：chrome 没回 DIM 标记\n{proc.stderr[-1500:]}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))


def screenshot(page_html: Path, png: Path, work: Path) -> None:
    png.unlink(missing_ok=True)
    proc = chrome([
        f"--window-size={PAGE_W},{PAGE_H}",
        "--force-device-scale-factor=2",
        "--virtual-time-budget=5000",
        f"--user-data-dir={work / 'chrome-shot'}",
        f"--screenshot={png}", page_html.as_uri(),
    ])
    if not png.exists() or png.stat().st_size == 0:
        raise SystemExit(f"截图失败：{(proc.stderr or proc.stdout)[-1500:]}")


def png_size(png: Path) -> tuple[int, int]:
    raw = png.read_bytes()[:33]
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{png} 不是 PNG")
    return struct.unpack(">II", raw[16:24])


def check_forbidden(text: str, where: str) -> None:
    for bad in FORBIDDEN:
        if bad and bad in text:
            raise SystemExit(f"{where} 里出现禁用字符串 {bad!r}"
                             "（不许出现用户名 / 绝对路径 / 口令）")


# ------------------------------------------------------------------ 渲染

def render(data: dict, mode: str, out_png: Path, now: str) -> tuple[int, int, int]:
    total_cp = sum(len(a["checkpoints"]) for a in data["artifacts"])
    page = build_html(data, mode, now)
    check_forbidden(page, f"{mode} HTML")
    for stale in STALE_TERMS:
        if stale in page:
            raise SystemExit(f"{mode} HTML 里残留 v1/样例口径字样 {stale!r}"
                             "（成品不许自称样例；kicker / 重跑命令应已覆盖）")
    if "Noto Sans CJK SC" not in page:
        raise SystemExit("CSS 没有指定中文字体 Noto Sans CJK SC")
    for token in REQUIRED_TOKENS:
        if token not in page:
            raise SystemExit(f"{mode} HTML 里缺少关键值 {token!r}（OCR 抽查会找不到）")
    boxes = total_cp + len(data["completeness_criteria"])
    odd = 'class="box blank"' if mode == "answer" else 'class="box answer"'
    own = f'class="box {mode}"'
    if page.count(own) != boxes:
        raise SystemExit(f"{mode} 版方框数 {page.count(own)}，应为 {boxes}"
                         "（24 个检验点 + 3 条完备判据）")
    if odd in page:
        raise SystemExit(f"{mode} 版混进了另一版的方框样式")

    with tempfile.TemporaryDirectory(prefix="poster-v2-") as tmp:
        work = Path(tmp)
        html_path = work / f"poster-{mode}.html"
        html_path.write_text(page, encoding="utf-8")
        w, h, foot_bottom, natural = measure(html_path, work)
        if w > PAGE_W:
            raise SystemExit(f"{mode} 版内容宽度 {w}px 超过 A4 画布 {PAGE_W}px（会横向裁切）")
        if h > PAGE_H or foot_bottom > PAGE_H or natural > PAGE_H:
            raise SystemExit(f"{mode} 版内容高度 {max(h, foot_bottom, natural)}px 超过 A4 画布 "
                             f"{PAGE_H}px（会超出一页），页脚底边 {foot_bottom} / 自然高度 {natural}")
        raw = work / f"poster-{mode}.raw.png"
        screenshot(html_path, raw, work)
        png_bytes = raw.read_bytes()

    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(png_bytes)

    pw, ph = png_size(out_png)
    if (pw, ph) != (SHOT_W, SHOT_H):
        raise SystemExit(f"{out_png.name} 尺寸 {pw}x{ph}，应为 {SHOT_W}x{SHOT_H}（A4 @300dpi）")
    check_forbidden(png_bytes.decode("latin-1", "ignore"), f"{out_png.name} 字节")
    print(f"  ✓ {out_png.relative_to(REPO)}  {pw}x{ph}  "
          f"（内容 {w}x{max(foot_bottom, natural)} / 画布 {PAGE_W}x{PAGE_H}，"
          f"页脚底边 {foot_bottom}）")
    return w, foot_bottom, natural


def main() -> int:
    print("《建成证明》v2 海报：tutorial/completeness/v2/data.json → 两张 A4 PNG")
    data = load_data()
    total_cp = sum(len(a["checkpoints"]) for a in data.get("artifacts") or [])
    print(f"  数据：{DATA_PATH.relative_to(REPO)}"
          f"（schema={data.get('schema')}，status={data.get('status')}，"
          f"{len(data.get('artifacts') or [])} 件 × {total_cp} 个检验点）")
    kicker, kicker_fallback = effective_kicker(data)
    rerun, rerun_fallback = effective_rerun(data)
    print(f"  页眉/脚注：kicker={kicker!r}；重跑命令={rerun!r}")
    if kicker_fallback or rerun_fallback:
        print("  注：data.json 的 kicker / rerun 仍是 D42「单页样例」口径（不在本脚本改动范围），"
              "已分别回退到 D43 口径 / 本脚本命令；数据升为生产口径后会自动跟随。")
    check_forbidden(DATA_PATH.read_text(encoding="utf-8"), "data.json")
    validate_structure(data)
    failures = trace_check(data)
    if failures:
        print(f"\n✗ 溯源校验有 {failures} 条 FAIL：只许修 v2/data.json，不许改十页正文。")
        return 1

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    print("\n渲染（A4 竖向 1240×1754 设计画布，截图 ×2 = 2480×3508）")
    render(data, "answer", ANSWER_PNG, now)
    render(data, "blank", BLANK_PNG, now)

    total_cp = sum(len(a["checkpoints"]) for a in data["artifacts"])
    print(f"\n完成：{len(data['artifacts'])} 件交付物 · {total_cp}/{total_cp} 溯源 PASS；"
          f"两张 PNG 均为 {SHOT_W}×{SHOT_H}（A4 竖向 / 300dpi），内容高度 ≤ {PAGE_H}px，"
          "可 100% 打印。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
