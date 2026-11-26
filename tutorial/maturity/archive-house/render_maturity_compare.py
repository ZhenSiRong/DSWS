#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_maturity_compare.py —— 「骨架版 vs 成熟版」同构对照图（一张 PNG）。

在仓库根目录一条命令重跑：

    python3 tutorial/shots/render_maturity_compare.py

读：`tutorial/maturity/data.json`（唯一数据源：12 件交付物 × `skeleton` / `mature` / `delta`；
    编号 / 名字 / 位置 / 页码与 `tutorial/completeness/v2/data.json` 逐字一致，脚本逐项比对）
写：`tutorial/maturity/compare-skeleton-vs-full.png`（3200×2000，横向两面板）

图在说什么（一句话）：**同一棵树 —— 骨架版每个节点都是壳，成熟版每个节点都长成真机制。**
所以版式不是左右各画一张图，而是**同一张 12 行表**：

- 每一行 = 一件交付物；左块（骨架版 L1，冷灰 + 虚线框）与右块（成熟版 L4，
  实线框 + 橙色「新增能力」标签）在同一行、同一高度，编号 01–12 两边相同；
- 行与行之间用**细虚线 + 同号圆标**把左块右缘连到右块左缘：拓扑没变，壳变真；
- 每块内是「编号 + 名字 + 位置」+ 1–2 行「壳 / 真」说明；
- 底部图例 + 12 条 delta 一行摘要。

实现（只用本机工具，不引外部 CDN / 字体）：

1. 读数据 + 结构自检 + 与 `completeness/v2/data.json` 的 12 件逐项比对（编号一致）；
2. 组版：HTML + CSS，设计画布 1600×1000 CSS px，`#poster` 1560×960（留 20px 白边）；
3. 无头 Chrome 先 `--dump-dom` 读回版式测量值（左右行顶是否对齐、文字有没有溢出、
   标签/连线/delta 数量），任一不满足就退出码 1 —— 不生成一张「看起来对」的错图；
4. 再 `--screenshot`（`--force-device-scale-factor=2` → 3200×2000），
   然后 `convert -trim` 去掉白边并 `-extent` 回 3200×2000；
5. 成图自检：PNG 尺寸、橙色是否只在成熟版一侧、字节里有没有用户名 / 绝对路径 / 口令。

依赖：本机 `/usr/bin/google-chrome`、ImageMagick `convert`、Noto Sans CJK SC、DejaVu Sans Mono。
不改十页正文、SPEC、completeness、flow、README、决策文档；只写本脚本 + data.json + PNG。
"""

from __future__ import annotations

import html
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent            # tutorial/shots
REPO = HERE.parents[1]                            # 仓库根目录
DATA_PATH = REPO / "manual" / "maturity" / "data.json"
OUT_PNG = REPO / "manual" / "maturity" / "compare-skeleton-vs-full.png"
V2_DATA_PATH = REPO / "manual" / "completeness" / "v2" / "data.json"

CHROME = "/usr/bin/google-chrome"
CONVERT = shutil.which("convert") or "/usr/bin/convert"

# 设计画布：1600×1000 CSS px；#poster 1560×960 居中（四边 20px 白边，trim 用）。
DESIGN_W, DESIGN_H = 1600, 1000
SCALE = 2
OUT_W, OUT_H = DESIGN_W * SCALE, DESIGN_H * SCALE            # 3200×2000
POSTER_W, POSTER_H = 1560, 960
MARGIN = 20

# 版式常量（与 CSS 里的 grid 定义必须一致；改一处要连着改）。
PANEL_W, GUTTER_W = 730, 60
HEAD_ROW_H = 44
ROW_H = 56
ROWS = 12
STAGE_H = HEAD_ROW_H + ROW_H * ROWS                            # 716
ORANGE = "#C2410C"

RERUN = "python3 tutorial/shots/render_maturity_compare.py"

# 成图 / HTML / 数据里不许出现的字符串（用户名、绝对路径、口令）。
HOST_USER = Path.home().name
FORBIDDEN = [
    "/home/", "/Users/", "/tmp/", HOST_USER,
    "labpass", "change-me", "MYSQL_ROOT_PASSWORD", "REBUILD_DW_RO_PASSWORD",
    "root@", "-uroot", "sk-",
]
# 目视 / OCR 抽查必须能认出的关键真值（都来自十页「你应该看到」或仓库契约）。
REQUIRED_TOKENS = ["41099.5", "115", "127.0.0.1:3307", "12/12"]

TAG_MARKS = {"dashed", "solid", "tag", "link"}


# ------------------------------------------------------------------ 小工具

def esc(text: object) -> str:
    """文本节点转义（不转义引号，中文与引号原样保留）。"""
    return html.escape(str(text), quote=False)


INLINE_CODE = re.compile(r"`([^`]+)`")


def rich(text: str) -> str:
    """把 `code` 渲染成等宽小标签，其余转义。"""
    out: list[str] = []
    pos = 0
    for m in INLINE_CODE.finditer(text):
        out.append(esc(text[pos:m.start()]))
        out.append(f"<code>{esc(m.group(1))}</code>")
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def plain(text: str) -> str:
    """去掉反引号（用于长度校验 / 关键词检查）。"""
    return INLINE_CODE.sub(r"\1", text)


def display_len(text: str) -> float:
    """粗略显示宽度：CJK 记 1，ASCII 记 0.55（块宽约 690px、字号 9.7px）。"""
    total = 0.0
    for ch in plain(text):
        total += 1.0 if ord(ch) > 0x2E7F else 0.55
    return total



def fail(msg: str):
    print(f"✗ {msg}", file=sys.stderr)
    raise SystemExit(1)


def check_text_forbidden(text: str, where: str) -> None:
    for bad in FORBIDDEN:
        if bad and bad in text:
            fail(f"{where} 里出现禁用字符串 {bad!r}（不许出现用户名 / 绝对路径 / 口令）")


def png_size(png: Path) -> tuple[int, int]:
    raw = png.read_bytes()[:33]
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{png} 不是 PNG")
    return struct.unpack(">II", raw[16:24])


# ------------------------------------------------------------------ 读数据 + 自检

REQUIRED_TOP = ("schema", "title", "thesis", "kicker", "panels", "source_refs",
                "counts", "legend", "tag_vocabulary", "tag_glossary", "artifacts", "rerun")


def load_json(path: Path, label: str) -> dict:
    if not path.exists():
        fail(f"找不到{label} {path.relative_to(REPO)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.relative_to(REPO)} 不是合法 JSON：{exc}")
    if not isinstance(data, dict):
        fail(f"{path.relative_to(REPO)} 顶层必须是对象")
    return data


def validate_structure(data: dict, v2: dict) -> None:
    errs: list[str] = []
    missing = [k for k in REQUIRED_TOP if k not in data]
    if missing:
        errs.append(f"data.json 缺顶层字段：{', '.join(missing)}")
    if not str(data.get("schema", "")).startswith("maturity-compare"):
        errs.append(f"schema={data.get('schema')!r}，应为 maturity-compare/…")
    if str(data.get("rerun", "")) != RERUN:
        errs.append(f"rerun={data.get('rerun')!r}，应为本脚本命令 {RERUN!r}")

    panels = data.get("panels") or {}
    for side in ("left", "right"):
        p = panels.get(side) or {}
        for key in ("label", "level", "hint", "style"):
            if not str(p.get(key, "")).strip():
                errs.append(f"panels.{side} 缺 {key}")
    if (panels.get("left") or {}).get("style") != "dashed":
        errs.append("panels.left.style 必须是 dashed（骨架版=虚线壳）")
    if (panels.get("right") or {}).get("style") != "solid":
        errs.append("panels.right.style 必须是 solid（成熟版=实线真实现）")

    legend = data.get("legend") or []
    marks = [str(x.get("mark")) for x in legend]
    if len(legend) != 4 or set(marks) != TAG_MARKS:
        errs.append(f"legend 必须是 4 条且 mark={sorted(TAG_MARKS)}，实际 {marks}")
    for item in legend:
        for key in ("label", "desc"):
            if not str(item.get(key, "")).strip():
                errs.append(f"legend 条目 {item.get('mark')!r} 缺 {key}")

    vocab = data.get("tag_vocabulary") or []
    if len(vocab) < 8 or len(set(vocab)) != len(vocab):
        errs.append("tag_vocabulary 至少 8 个且不许重复")
    glossary = data.get("tag_glossary") or {}
    if set(glossary) != set(vocab):
        errs.append("tag_glossary 的键必须与 tag_vocabulary 完全一致")

    arts = data.get("artifacts") or []
    if len(arts) != 12:
        errs.append(f"交付物 {len(arts)} 件，D42/D43 口径是 12 件")
    nos = [a.get("no") for a in arts]
    if nos != list(range(1, len(arts) + 1)):
        errs.append(f"编号必须是 01–12 连续，实际 {nos}")
    ids = [a.get("id") for a in arts]
    if len(set(ids)) != len(ids):
        errs.append("交付物 id 有重复")
    used_tags: list[str] = []
    deltas: list[str] = []
    for a in arts:
        tag = f"#{a.get('no')}"
        for key in ("id", "name", "kind", "location", "pages",
                    "skeleton", "mature", "delta", "tags"):
            if key not in a:
                errs.append(f"{tag} 缺字段 {key}")
        for key in ("skeleton", "mature", "delta"):
            text = str(a.get(key) or "").strip()
            if len(plain(text)) < 10:
                errs.append(f"{tag}.{key} 太短：{text!r}")
        skeleton, mature, delta = str(a.get("skeleton") or ""), str(a.get("mature") or ""), str(a.get("delta") or "")
        if display_len(skeleton) > 138:
            errs.append(f"{tag}.skeleton 显示宽度 {display_len(skeleton):.0f} > 138，会超过 2 行")
        if display_len(mature) > 138:
            errs.append(f"{tag}.mature 显示宽度 {display_len(mature):.0f} > 138，会超过 2 行")
        if display_len(delta) > 52:
            errs.append(f"{tag}.delta 显示宽度 {display_len(delta):.0f} > 52，底部一行放不下")
        tags = a.get("tags") or []
        if not (1 <= len(tags) <= 3):
            errs.append(f"{tag} 标签 {len(tags)} 个，应 1–3 个")
        if len(set(tags)) != len(tags):
            errs.append(f"{tag} 标签重复")
        for t in tags:
            if t not in vocab:
                errs.append(f"{tag} 标签 {t!r} 不在 tag_vocabulary 里")
        used_tags.extend(tags)
        deltas.append(str(a.get("delta") or ""))
        pages = a.get("pages") or []
        if not pages:
            errs.append(f"{tag} 没有 pages")
        for pid in pages:
            if not (REPO / "manual" / f"{pid}.md").exists():
                errs.append(f"{tag} 的页面 {pid}.md 不存在")
        evidence = a.get("evidence") or {}
        for key in ("skeleton", "mature"):
            if not str(evidence.get(key, "")).strip():
                errs.append(f"{tag}.evidence 缺 {key}")
    if len(set(deltas)) != len(deltas):
        errs.append("12 条 delta 有重复（每件应各说一格的差）")
    if set(used_tags) != set(vocab):
        errs.append(f"词表与实际用到的标签不一致：未用 {set(vocab) - set(used_tags)} / 多出 {set(used_tags) - set(vocab)}")

    counts = data.get("counts") or {}
    if counts.get("artifacts") != len(arts):
        errs.append(f"counts.artifacts={counts.get('artifacts')} ≠ 实际 {len(arts)}")
    if counts.get("deltas") != len(deltas):
        errs.append(f"counts.deltas={counts.get('deltas')} ≠ 实际 {len(deltas)}")
    if counts.get("tags") != len(used_tags):
        errs.append(f"counts.tags={counts.get('tags')} ≠ 实际 {len(used_tags)}")

    # ---- 与 completeness/v2 的 12 件逐项一致（编号/名字/位置是「同一棵树」的共同口径）
    v2_art = v2.get("artifacts") or []
    if len(v2_art) != len(arts):
        errs.append(f"completeness/v2 有 {len(v2_art)} 件，本数据 {len(arts)} 件，口径不一致")
    v2_by_no = {x.get("no"): x for x in v2_art}
    for a in arts:
        b = v2_by_no.get(a.get("no"))
        if b is None:
            errs.append(f"completeness/v2 里找不到编号 {a.get('no')}")
            continue
        for key in ("id", "name", "kind", "location", "pages"):
            if a.get(key) != b.get(key):
                errs.append(f"#{a.get('no')}.{key} 与 completeness/v2 不一致："
                            f"{a.get(key)!r} ≠ {b.get(key)!r}")

    if errs:
        print("✗ 数据自检失败：")
        for e in errs:
            print(f"  - {e}")
        raise SystemExit(1)
    print(f"  ✓ 结构：12 件 × (skeleton / mature / delta)，编号 01–12 连续，"
          f"{len(used_tags)} 个标签 / {len(set(used_tags))} 种")
    print("  ✓ 口径：12/12 件的 no / id / name / kind / location / pages 与 completeness/v2 逐字一致")
    print(f"  ✓ 字段：skeleton 最长 {max(display_len(a['skeleton']) for a in arts):.0f} 显示宽，"
          f"mature 最长 {max(display_len(a['mature']) for a in arts):.0f}，"
          f"delta 最长 {max(display_len(a['delta']) for a in arts):.0f}")


# ------------------------------------------------------------------ 组版（HTML + CSS）

CSS = """
@page { size: 1600px 1000px; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #ffffff; }
body {
  width: 1600px; height: 1000px; overflow: hidden; padding: 20px;
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
  color: #111; -webkit-font-smoothing: antialiased;
}
#poster {
  position: relative; width: 1560px; height: 960px; margin: 0 auto;
  padding: 14px 20px 12px; background: #F5F4F1;
  display: flex; flex-direction: column;
}
.hdr {
  display: flex; align-items: flex-start; justify-content: space-between;
  border-bottom: 2px solid #1B1B1B; padding-bottom: 6px; flex: 0 0 auto;
}
.kicker { font-size: 10.2px; line-height: 12px; letter-spacing: .7px; color: #555; font-weight: 700; }
h1 { margin: 2px 0 0; font-size: 25.5px; line-height: 29px; font-weight: 900; letter-spacing: .2px; }
.hmeta { margin-top: 1px; font-size: 9.8px; line-height: 12px; color: #444; }
.hmeta b { font-weight: 900; }
.hdr-r { flex: 0 0 auto; padding-left: 16px; }
.stamp {
  display: flex; align-items: center; gap: 8px;
  border: 1.5px solid #1B1B1B; border-radius: 6px; padding: 3px 10px; background: #fff;
}
.stamp b { font: 900 19px/1 "DejaVu Sans Mono", monospace; }
.stamp span { font-size: 8.4px; line-height: 1.3; color: #444; }

.stage {
  margin-top: 8px; flex: 0 0 auto; position: relative;
  display: grid;
  grid-template-columns: 730px 60px 730px;
  grid-template-rows: 44px repeat(12, 56px);
}
.pbg { border-radius: 8px; }
.pbg.left { grid-column: 1; grid-row: 1 / -1; background: #EDF1F6; border: 2px dashed #8A97A5; }
.pbg.right { grid-column: 3; grid-row: 1 / -1; background: #FFFFFF; border: 2px solid #1E1E1E; }

.phead { position: relative; z-index: 3; display: flex; align-items: center; gap: 9px; padding: 0 15px; }
.phead.left { grid-column: 1; grid-row: 1; }
.phead.right { grid-column: 3; grid-row: 1; }
.phead.mid { grid-column: 2; grid-row: 1; flex-direction: column; justify-content: center; gap: 0; padding: 0; }
.lv { font: 900 10px/1 "DejaVu Sans Mono", monospace; color: #fff; padding: 4px 6px; border-radius: 4px; }
.phead.left .lv { background: #46545F; }
.phead.right .lv { background: #C2410C; }
.ptitle { font-size: 14px; font-weight: 900; letter-spacing: .6px; }
.phead.left .ptitle { color: #1F2B36; }
.pnote { font-size: 9.2px; color: #5E6B77; white-space: nowrap; }
.phead.right .pnote { color: #555; }
.pcount { margin-left: auto; font-size: 8.4px; color: #5E6B77; white-space: nowrap; }
.phead.right .pcount { color: #555; }
.mid-arrow { font: 900 13px/1 "DejaVu Sans", sans-serif; color: #8B8B8B; }
.mid-cap { font-size: 7.4px; letter-spacing: 1.2px; color: #8B8B8B; margin-top: 2px; }

.block { position: relative; z-index: 2; margin: 1px 10px; padding: 1px 8px 2px; border-radius: 4px; overflow: hidden; }
.block.left { grid-column: 1; background: #F8FAFC; border: 1.4px dashed #7F8C9A; }
.block.right { grid-column: 3; background: #FFFFFF; border: 1.4px solid #232323; }
.bhead { display: flex; align-items: center; gap: 5px; height: 14px; line-height: 14px; }
.no {
  flex: 0 0 auto; font: 700 8.2px/1 "DejaVu Sans Mono", monospace;
  border: 1px solid #8A8A8A; border-radius: 3px; padding: 1px 3px; color: #222; background: #fff;
}
.nm { font-size: 11.2px; font-weight: 900; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.block.left .nm { color: #22303C; }
.block.right .nm { color: #111; }
.nm code { font-family: "DejaVu Sans Mono", monospace; font-size: 9.6px; background: transparent; padding: 0; }
.src {
  flex: 0 0 auto; margin-left: auto; font-size: 7.8px; color: #5E6B77;
  background: #E2E9F0; border-radius: 3px; padding: 1px 4px; white-space: nowrap;
}
.tags { flex: 0 0 auto; margin-left: auto; display: flex; gap: 3px; }
.tag {
  font-size: 7.8px; line-height: 9.2px; font-weight: 700; padding: 1px 4px; border-radius: 8px;
  border: 1px solid #E2793C; background: #FCEBDD; color: #A63A0E; white-space: nowrap;
}
.loc {
  height: 10.4px; line-height: 10.4px; font-size: 8px;
  font-family: "DejaVu Sans Mono", "Noto Sans CJK SC", monospace;
  color: #5E6B77; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bdesc { height: 22.4px; line-height: 11.2px; font-size: 9.7px; overflow: hidden; }
.block.left .bdesc { color: #43505C; }
.block.right .bdesc { color: #222; }
code {
  font-family: "DejaVu Sans Mono", "Noto Sans CJK SC", monospace; font-size: .92em;
  background: rgba(0,0,0,.055); border-radius: 2px; padding: 0 1.5px;
}
.block.right code { background: #F1EDE7; }

.conn { grid-column: 2; position: relative; z-index: 3; display: flex; align-items: center; justify-content: center; }
.conn::before {
  content: ""; position: absolute; left: 0; right: 0; top: 50%;
  border-top: 1px dashed #9B9B9B;
}
.lno {
  position: relative; width: 21px; height: 21px; border-radius: 50%;
  background: #F5F4F1; border: 1px solid #8B8B8B; color: #222;
  display: flex; align-items: center; justify-content: center;
  font: 700 7.8px/1 "DejaVu Sans Mono", monospace;
}

.foot { margin-top: auto; flex: 0 0 auto; }
.legend {
  display: flex; align-items: center; gap: 18px; flex-wrap: nowrap;
  border-top: 1.5px solid #1B1B1B; padding-top: 5px;
  font-size: 8.7px; color: #333;
}
.lg { display: flex; align-items: center; gap: 5px; white-space: nowrap; }
.sw { display: inline-block; width: 21px; height: 11px; border-radius: 2px; flex: 0 0 auto; }
.sw.dashed { border: 1.4px dashed #6F7C89; background: #EDF1F6; }
.sw.solid { border: 1.4px solid #1B1B1B; background: #fff; }
.sw.connlink { position: relative; border: none; width: 24px; }
.sw.connlink::before { content: ""; position: absolute; left: 0; right: 0; top: 50%; border-top: 1px dashed #9B9B9B; }
.tag-sample {
  display: inline-block; font-size: 7.8px; line-height: 9.2px; font-weight: 700;
  padding: 1px 4px; border-radius: 8px; border: 1px solid #E2793C;
  background: #FCEBDD; color: #A63A0E; white-space: nowrap; flex: 0 0 auto;
}
.dhead { display: flex; align-items: baseline; gap: 8px; margin-top: 5px; }
.dtitle { font-size: 10.4px; font-weight: 900; }
.dsub { font-size: 8.2px; color: #666; }
.dgrid {
  display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: repeat(6, auto);
  grid-auto-flow: column; column-gap: 26px; row-gap: 1.5px; margin-top: 2px;
}
.d { display: flex; gap: 5px; font-size: 8.7px; line-height: 12px; color: #222; min-width: 0; }
.dn { flex: 0 0 auto; font: 700 7.9px/12px "DejaVu Sans Mono", monospace; color: #6E6E6E; }
.dt { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.note { margin-top: 4px; font-size: 7.9px; line-height: 10px; color: #666; }
.note code { font-size: 7.5px; }
"""

MEASURE_JS = """
window.addEventListener("load", function () {
  function rnd(x) { return Math.round(x * 100) / 100; }
  var out = {};
  var poster = document.getElementById("poster");
  var pr = poster.getBoundingClientRect();
  out.posterW = Math.round(pr.width);
  out.posterH = Math.round(pr.height);
  out.posterScrollH = poster.scrollHeight;
  out.docW = document.documentElement.scrollWidth;
  out.docH = document.documentElement.scrollHeight;
  var st = document.querySelector(".stage").getBoundingClientRect();
  out.stageTop = Math.round(st.top * 10) / 10;
  out.stageH = Math.round(st.height * 10) / 10;
  var L = document.querySelectorAll(".block.left");
  var R = document.querySelectorAll(".block.right");
  out.left = L.length; out.right = R.length;
  out.blocks = document.querySelectorAll(".block").length;
  out.links = document.querySelectorAll(".conn").length;
  out.names = document.querySelectorAll(".nm").length;
  out.descs = document.querySelectorAll(".bdesc").length;
  out.tags = document.querySelectorAll(".tags .tag").length;
  out.deltas = document.querySelectorAll(".dgrid .d").length;
  var mis = 0, badNo = 0;
  for (var i = 0; i < L.length && i < R.length; i++) {
    var a = L[i].getBoundingClientRect(), b = R[i].getBoundingClientRect();
    if (Math.abs(a.top - b.top) > 0.5 || Math.abs(a.height - b.height) > 0.5) mis++;
    var exp = ("0" + (i + 1)).slice(-2);
    if (L[i].getAttribute("data-no") !== exp || R[i].getAttribute("data-no") !== exp) badNo++;
  }
  out.misalign = mis; out.badNo = badNo;
  var overflow = 0, maxLines = 0;
  var ds = document.querySelectorAll(".bdesc");
  for (var j = 0; j < ds.length; j++) {
    var el = ds[j];
    var lh = parseFloat(getComputedStyle(el).lineHeight) || 1;
    var lines = el.scrollHeight / lh;
    if (lines > maxLines) maxLines = lines;
    if (lines > 2.05) overflow++;
  }
  out.overflow = overflow; out.maxLines = Math.round(maxLines * 10) / 10;
  var bo = 0;
  var bs = document.querySelectorAll(".block");
  for (var k = 0; k < bs.length; k++) {
    var bb = bs[k];
    if (bb.scrollHeight - bb.clientHeight > 1 || bb.scrollWidth - bb.clientWidth > 1) bo++;
  }
  out.blockOverflow = bo;
  var nameTrunc = 0;
  var nms = document.querySelectorAll(".nm");
  for (var n = 0; n < nms.length; n++) { if (nms[n].scrollWidth - nms[n].clientWidth > 1) nameTrunc++; }
  out.nameTrunc = nameTrunc;
  var locTrunc = 0;
  var locs = document.querySelectorAll(".loc");
  for (var q = 0; q < locs.length; q++) { if (locs[q].scrollWidth - locs[q].clientWidth > 1) locTrunc++; }
  out.locTrunc = locTrunc;
  var dTrunc = 0;
  var dts = document.querySelectorAll(".dt");
  for (var w = 0; w < dts.length; w++) { if (dts[w].scrollWidth - dts[w].clientWidth > 1) dTrunc++; }
  out.deltaTrunc = dTrunc;
  document.title = "CHK " + JSON.stringify(out);
});
"""


def page_label(pages: list[str]) -> str:
    nums = []
    for pid in pages:
        num = pid.split("-", 1)[1].lstrip("0") or "0"
        nums.append(num)
    return "第 " + " / ".join(nums) + " 页"


def header_html(data: dict) -> str:
    return (
        '<header class="hdr">'
        '<div class="hdr-l">'
        f'<div class="kicker">{esc(data["kicker"])}</div>'
        f'<h1>{rich(data["thesis"])}</h1>'
        '<div class="hmeta">左 = <b>现在这 10 页造出来的东西（壳）</b>　·　'
        '右 = <b>本项目仓库里的真实工程能力（真）</b>　·　'
        '编号 / 名字 / 位置同 <b>tutorial/completeness/v2/data.json</b></div>'
        '</div>'
        '<div class="hdr-r"><div class="stamp"><b>12/12</b>'
        '<span>件交付物<br>左右同构对齐</span></div></div>'
        '</header>'
    )


def panel_head_html(side: str, data: dict, count: int) -> str:
    p = data["panels"][side]
    extra = "全是壳 / 占位" if side == "left" else "都长成真机制"
    return (
        f'<div class="phead {side}">'
        f'<span class="lv">{esc(p["level"])}</span>'
        f'<span class="ptitle">{esc(p["label"])}</span>'
        f'<span class="pnote">{esc(p["hint"])}</span>'
        f'<span class="pcount">{count} 件 · {extra}</span>'
        '</div>'
    )


def block_html(art: dict, side: str) -> str:
    if side == "left":
        right = f'<span class="src">{esc(page_label(art["pages"]))}</span>'
        desc = art["skeleton"]
    else:
        tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in art["tags"])
        right = f'<span class="tags">{tags}</span>'
        desc = art["mature"]
    return (
        f'<div class="block {side}" data-no="{art["no"]:02d}" data-aid="{esc(art["id"])}" '
        f'style="grid-row: {art["no"] + 1}">'
        f'<div class="bhead"><span class="no">{art["no"]:02d}</span>'
        f'<span class="nm">{rich(art["name"])}</span>{right}</div>'
        f'<div class="loc">{rich(art["location"])}</div>'
        f'<div class="bdesc">{rich(desc)}</div>'
        '</div>'
    )


def legend_html(data: dict) -> str:
    items = []
    for item in data["legend"]:
        mark = str(item["mark"])
        if mark == "tag":
            swatch = '<span class="tag-sample">新增能力</span>'
        elif mark == "link":
            swatch = '<span class="sw connlink"></span>'
        else:
            swatch = f'<span class="sw {mark}"></span>'
        items.append(
            f'<span class="lg">{swatch}<b>{esc(item["label"])}</b>'
            f'<span>{esc(item["desc"])}</span></span>'
        )
    return '<div class="legend">' + "".join(items) + "</div>"


def footer_html(data: dict) -> str:
    deltas = "".join(
        f'<div class="d"><span class="dn">{i:02d}</span>'
        f'<span class="dt">{rich(a["delta"])}</span></div>'
        for i, a in enumerate(data["artifacts"], 1)
    )
    return (
        '<footer class="foot">'
        + legend_html(data)
        + '<div class="dhead"><span class="dtitle">差的那一格 · 12 条 delta</span>'
        '<span class="dsub">（左：现在能跑的壳 → 右：成熟版对应的真机制）</span></div>'
        f'<div class="dgrid">{deltas}</div>'
        '<div class="note">数据 <code>tutorial/maturity/data.json</code>（唯一数据源）'
        '　·　重跑 <code>' + esc(data["rerun"]) + '</code>'
        '　·　渲染：本机 Chrome 无头截图 + <code>convert -trim</code>，本地字体，无外部请求</div>'
        '</footer>'
    )


def build_html(data: dict) -> str:
    stage = ['<div class="stage">',
             '<div class="pbg left"></div><div class="pbg right"></div>',
             panel_head_html("left", data, len(data["artifacts"])),
             '<div class="phead mid"><span class="mid-arrow">⇄</span>'
             '<span class="mid-cap">同构</span></div>',
             panel_head_html("right", data, len(data["artifacts"]))]
    for art in data["artifacts"]:
        stage.append(block_html(art, "left"))
        stage.append(f'<div class="conn" style="grid-row: {art["no"] + 1}">'
                     f'<span class="lno">{art["no"]:02d}</span></div>')
        stage.append(block_html(art, "right"))
    stage.append("</div>")
    return (
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<title>{esc(data["title"])}</title>'
        f'<style>{CSS}</style></head><body>'
        f'<div id="poster">{header_html(data)}{"".join(stage)}{footer_html(data)}</div>'
        f'<script>{MEASURE_JS}</script></body></html>\n'
    )


# ------------------------------------------------------------------ HTML 自检

EXTERNAL_URL = re.compile(r"https?://([^\s\"'<>]+)", re.I)


def check_html(page: str, data: dict) -> None:
    errs: list[str] = []
    total_tags = sum(len(a["tags"]) for a in data["artifacts"])
    expect = {
        "left 块": (page.count('class="block left"'), 12),
        "right 块": (page.count('class="block right"'), 12),
        "行间连线": (page.count('class="conn"'), 12),
        "橙标签": (page.count('<span class="tag">'), total_tags),
        "名字出现次数": (page.count('class="nm"'), 24),
        "壳/真说明": (page.count('class="bdesc"'), 24),
        "delta 行": (page.count('class="d"'), 12),
        "面板背景": (page.count('class="pbg '), 2),
    }
    for name, (got, want) in expect.items():
        if got != want:
            errs.append(f"{name} {got} 个，应为 {want} 个")
    for i in range(1, 13):
        if f'data-no="{i:02d}"' not in page:
            errs.append(f"HTML 缺编号 {i:02d}")
    if page.count("data-aid=") != 24:
        errs.append(f"data-aid 出现 {page.count('data-aid=')} 次，应为 24 次（左右各 12）")

    # 无外部请求痕迹：不许有任何资源引用 / 外部 URL / 网络 API
    if re.search(r"\b(?:src|href)\s*=", page, re.I):
        errs.append("HTML 里出现 src= / href= 资源引用（应为纯自包含单文件）")
    for token in ("<link", "<img", "<iframe", "<object", "<embed", "<video", "<audio",
                  "@import", "url(", "fetch(", "XMLHttpRequest", "import(", "//cdn"):
        if token.lower() in page.lower():
            errs.append(f"HTML 里出现外部请求痕迹 {token!r}")
    hosts: set[str] = set()
    for m in EXTERNAL_URL.finditer(page):
        host = m.group(1).split("/")[0].split(":")[0].lower()
        hosts.add(host)
        if host not in ("127.0.0.1", "localhost"):
            errs.append(f"出现外部 URL 主机 {host!r}（只允许 127.0.0.1 / localhost 的本地端点文本）")

    check_text_forbidden(page, "HTML")
    for token in REQUIRED_TOKENS:
        if token not in page:
            errs.append(f"HTML 里缺少关键真值 {token!r}（OCR 抽查会找不到）")
    for css_token in ('border: 1.4px dashed', 'border: 1.4px solid', 'border: 2px dashed', 'border: 2px solid'):
        if css_token not in page:
            errs.append(f"CSS 缺样式 {css_token!r}（虚线=壳 / 实线=真 的图例对不上）")
    if "Noto Sans CJK SC" not in page:
        errs.append("CSS 没有指定中文字体 Noto Sans CJK SC")
    for art in data["artifacts"]:
        if esc(art["id"]) not in page:
            errs.append(f"HTML 缺交付物 id {art['id']!r}")
        if esc(art["delta"]) not in page:
            errs.append(f"HTML 缺 delta {art['delta']!r}")
    if errs:
        print("✗ HTML 自检失败：")
        for e in errs:
            print(f"  - {e}")
        raise SystemExit(1)
    print(f"  ✓ 版式元素：左块 12 · 右块 12 · 连线 12 · 橙标签 {total_tags} · "
          f"说明 24 · delta 12 · 面板 2")
    print(f"  ✓ 无外部请求痕迹：0 个 src/href 资源引用；URL 主机只有本地 {sorted(hosts) or '无'}")
    print("  ✓ 无用户名 / 绝对路径 / 口令；关键真值齐全（41099.5 / 115 / 127.0.0.1:3307 / 12/12）")


# ------------------------------------------------------------------ Chrome

CHROME_BASE = [
    CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
    "--disable-dev-shm-usage", "--disable-background-networking",
    "--disable-component-update", "--disable-default-apps", "--disable-sync",
    "--no-first-run", "--no-default-browser-check", "--metrics-recording-only",
    "--disable-features=Translate,MediaRouter", "--font-render-hinting=none",
    "--disable-lcd-text", "--force-color-profile=srgb",
]


def run_chrome(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(CHROME_BASE + args, capture_output=True, text=True, timeout=timeout)


def measure_layout(page_html: Path, work: Path) -> dict:
    proc = run_chrome([
        f"--window-size={DESIGN_W},{DESIGN_H}",
        "--virtual-time-budget=4000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", page_html.as_uri(),
    ])
    m = re.search(r"<title>CHK (\{.*?\})</title>", proc.stdout, re.S)
    if not m:
        fail("版式测量失败：Chrome 没回 CHK 标记\n" + (proc.stderr or proc.stdout)[-1200:])
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        fail(f"版式测量结果不是 JSON：{exc}")
    return data


def validate_layout(m: dict, data: dict) -> None:
    total_tags = sum(len(a["tags"]) for a in data["artifacts"])
    checks = [
        ("画布", m["posterW"] == POSTER_W and m["posterH"] == POSTER_H,
         f'#poster {m["posterW"]}×{m["posterH"]}（应 {POSTER_W}×{POSTER_H}）'),
        ("不超页", m["posterScrollH"] <= POSTER_H and m["docW"] <= DESIGN_W and m["docH"] <= DESIGN_H,
         f'内容高 {m["posterScrollH"]} / 文档 {m["docW"]}×{m["docH"]}（应 ≤ {POSTER_W}×{POSTER_H} / {DESIGN_W}×{DESIGN_H}）'),
        ("左右块数", m["left"] == 12 and m["right"] == 12, f'左 {m["left"]} / 右 {m["right"]}'),
        ("连线", m["links"] == 12, f'{m["links"]} 条'),
        ("名字 / 说明", m["names"] == 24 and m["descs"] == 24, f'{m["names"]} / {m["descs"]}'),
        ("同构对齐", m["misalign"] == 0,
         f'{12 - m["misalign"]}/12 行左右块顶边完全对齐（错位 {m["misalign"]} 行）'),
        ("编号一致", m["badNo"] == 0, f'两边编号与行序一致（错号 {m["badNo"]}）'),
        ("说明不超 2 行", m["overflow"] == 0 and m["maxLines"] <= 2.05,
         f'最多 {m["maxLines"]} 行（超行 {m["overflow"]} 块）'),
        ("块内不溢出", m["blockOverflow"] == 0, f'溢出 {m["blockOverflow"]} 块'),
        ("名字不被截断", m["nameTrunc"] == 0, f'截断 {m["nameTrunc"]} 个'),
        ("位置不被截断", m["locTrunc"] == 0, f'截断 {m["locTrunc"]} 个'),
        ("delta 不被截断", m["deltaTrunc"] == 0, f'截断 {m["deltaTrunc"]} 条'),
        ("标签数", m["tags"] == total_tags, f'{m["tags"]} 个（应 {total_tags}）'),
        ("delta 数", m["deltas"] == 12, f'{m["deltas"]} 条'),
    ]
    bad = 0
    for name, ok, detail in checks:
        if ok:
            print(f"  ✓ {name}：{detail}")
        else:
            bad += 1
            print(f"  ✗ {name}：{detail}")
    if bad:
        fail(f"版式自检 {bad} 项不通过 —— 不截图，先修版式")


def screenshot(page_html: Path, png: Path, work: Path) -> None:
    png.unlink(missing_ok=True)
    proc = run_chrome([
        f"--window-size={DESIGN_W},{DESIGN_H}",
        f"--force-device-scale-factor={SCALE}",
        "--virtual-time-budget=4000",
        f"--user-data-dir={work / 'chrome-shot'}",
        f"--screenshot={png}", page_html.as_uri(),
    ])
    if not png.exists() or png.stat().st_size == 0:
        fail("截图失败：" + (proc.stderr or proc.stdout)[-1200:])


# ------------------------------------------------------------------ 成图校验

def img_mean(png: Path, crop: str) -> float:
    proc = subprocess.run(
        [CONVERT, str(png), "-crop", crop, "+repage",
         "-format", "%[fx:mean]", "info:"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        fail(f"ImageMagick 取像素失败：{proc.stderr[-400:]}")
    try:
        return float(proc.stdout.strip())
    except ValueError:
        fail(f"ImageMagick 像素输出不是数字：{proc.stdout!r}")


def orange_fraction(png: Path, crop: str) -> float:
    """橙色 (#C2410C ± fuzz) 像素占比：把橙色变透明后，mean.a = 非橙占比。"""
    proc = subprocess.run(
        [CONVERT, str(png), "-crop", crop, "+repage",
         "-fuzz", "12%", "-transparent", ORANGE, "-format", "%[fx:mean.a]", "info:"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        fail(f"ImageMagick 橙色统计失败：{proc.stderr[-400:]}")
    try:
        alpha = float(proc.stdout.strip())
    except ValueError:
        fail(f"ImageMagick 橙色统计输出不是数字：{proc.stdout!r}")
    return max(0.0, min(1.0, 1.0 - alpha))


def trim_and_pad(raw: Path, out: Path) -> tuple[int, int]:
    """convert -trim 去白边 + -extent 回 3200×2000。"""
    probe = subprocess.run(
        [CONVERT, str(raw), "-trim", "+repage", "-format", "%w %h", "info:"],
        capture_output=True, text=True, timeout=120,
    )
    if probe.returncode != 0:
        fail(f"convert -trim 失败：{probe.stderr[-500:]}")
    try:
        tw, th = (int(x) for x in probe.stdout.split())
    except ValueError:
        fail(f"trim 尺寸输出异常：{probe.stdout!r}")
    if tw > OUT_W or th > OUT_H:
        fail(f"trim 后 {tw}×{th} 超过成品画布 {OUT_W}×{OUT_H}（版式溢出了）")
    proc = subprocess.run(
        [CONVERT, str(raw), "-trim", "+repage",
         "-background", "white", "-gravity", "center",
         "-extent", f"{OUT_W}x{OUT_H}", "-strip", str(out)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        fail(f"convert 回画布失败：{proc.stderr[-500:]}")
    return tw, th


def check_png(png: Path, raw_size: tuple[int, int], trimmed: tuple[int, int],
              metrics: dict) -> None:
    pw, ph = png_size(png)
    if (pw, ph) != (OUT_W, OUT_H):
        fail(f"成品尺寸 {pw}×{ph}，应为 {OUT_W}×{OUT_H}")
    corner = img_mean(png, "1x1+0+0")
    inside = img_mean(png, "1x1+80+80")
    if corner < 0.995:
        fail(f"成品左上角不是白边（mean={corner:.3f}），trim / extent 没按预期留白")
    if inside > 0.99:
        fail(f"画布内 (80,80) 是纯白（mean={inside:.3f}），poster 没落在预期位置")

    # 橙色只允许出现在成熟版面板区（不能出现在左面板，也不能靠底部图例的样例蒙混）。
    # 用测量到的 .stage 位置换算到成图像素：trim + extent 之后 poster 的偏移 = 留白。
    x_off = (OUT_W - trimmed[0]) // 2
    y_off = (OUT_H - trimmed[1]) // 2
    stage_y = y_off + round((metrics["stageTop"] - MARGIN) * SCALE)
    stage_h = round(metrics["stageH"] * SCALE)
    left_crop = f"{OUT_W // 2}x{stage_h}+0+{stage_y}"
    right_crop = f"{OUT_W // 2}x{stage_h}+{OUT_W // 2}+{stage_y}"
    left_orange = orange_fraction(png, left_crop)
    right_orange = orange_fraction(png, right_crop)
    if left_orange > 0.0005:
        fail(f"骨架版面板出现橙色（{left_orange:.4%}），橙色只能属于成熟版的「新增能力」标签")
    if right_orange < 0.002:
        fail(f"成熟版面板橙色标签太少（{right_orange:.4%}），标签可能没渲染出来")
    check_text_forbidden(png.read_bytes().decode("latin-1", "ignore"), f"{OUT_PNG.name} 字节")
    print(f"  ✓ 尺寸：raw {raw_size[0]}×{raw_size[1]} → trim {trimmed[0]}×{trimmed[1]} → "
          f"成品 {pw}×{ph}（{OUT_W}×{OUT_H}）")
    print(f"  ✓ 橙色只属于成熟版面板：左 {left_orange:.4%}（应 ≈0）/ 右 {right_orange:.4%}（新增能力标签）")
    print("  ✓ 字节里没有用户名 / 绝对路径 / 口令")


# ------------------------------------------------------------------ main

def main(argv: list[str]) -> int:
    if not Path(CHROME).exists():
        fail(f"找不到 Chrome：{CHROME}")
    if not Path(CONVERT).exists():
        fail(f"找不到 ImageMagick convert：{CONVERT}")
    check_only = "--check-only" in argv
    print("「骨架版 vs 成熟版」同构对照图：tutorial/maturity/data.json → 一张 3200×2000 PNG")
    print(f"  画布：{DESIGN_W}×{DESIGN_H} CSS @{SCALE}x = {OUT_W}×{OUT_H}；"
          f"#poster {POSTER_W}×{POSTER_H}；{ROWS} 行 × 左右两面板")
    if check_only:
        print("  模式：--check-only（只做数据 / 版式自检，不截图）")

    data = load_json(DATA_PATH, "数据文件")
    v2 = load_json(V2_DATA_PATH, "completeness/v2 数据文件")
    check_text_forbidden(DATA_PATH.read_text(encoding="utf-8"), "data.json")
    validate_structure(data, v2)

    page = build_html(data)
    check_html(page, data)

    with tempfile.TemporaryDirectory(prefix="maturity-compare-") as tmp:
        work = Path(tmp)
        html_path = work / "compare.html"
        html_path.write_text(page, encoding="utf-8")
        print("  版式测量（Chrome --dump-dom）")
        metrics = measure_layout(html_path, work)
        validate_layout(metrics, data)
        if check_only:
            print("\n完成（--check-only）：数据 / HTML / 版式自检全过；未生成 PNG。")
            return 0

        print("  截图（Chrome --screenshot，@2x）")
        raw = work / "compare.raw.png"
        screenshot(html_path, raw, work)
        raw_size = png_size(raw)
        if raw_size != (OUT_W, OUT_H):
            fail(f"截图尺寸 {raw_size[0]}×{raw_size[1]}，应为 {OUT_W}×{OUT_H}"
                 "（检查 window-size / force-device-scale-factor）")

        print("  去白边（convert -trim）并回画布")
        padded = work / "compare.padded.png"
        trimmed = trim_and_pad(raw, padded)

        print("  成图自检")
        check_png(padded, raw_size, trimmed, metrics)
        OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(padded, OUT_PNG)

    size = OUT_PNG.stat().st_size
    print(f"\n完成 ✓ {OUT_PNG.relative_to(REPO)}  {OUT_W}×{OUT_H}  {size / 1024:.0f} KB")
    print(f"  数据源：tutorial/maturity/data.json（12 件 × skeleton/mature/delta，"
          f"编号/名字/位置同 completeness/v2）；重跑：{RERUN}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
