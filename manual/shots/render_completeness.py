#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_completeness.py —— 渲染「完备性证明」海报的两张 A4 PNG。

在仓库根目录一条命令重跑（同时出两张图）：

    python3 manual/shots/render_completeness.py

输出：

    manual/completeness/poster-blank.png    空白可打印版：槽位方框 ▢、矩阵格与证据列留空，供学生勾/涂
    manual/completeness/poster-answer.png   答案版：A0–A9 全 ■，矩阵填 ■/—，末列写第 0–9 页判据

依据 `humen-desicions/09-ablation-course.md` 的 **D38**：
C4 的 L1 上下文 / L2 容器 / L3 组件三层 + L0（环境、数据）底部地基横条；
每层一张「责任 × 证据」矩阵；三态图例 ▢ / ◧ / ■；完备判据三条
（每行 ≥ 1 个 ■、每列 ≥ 1 个 ■、跨层边都通且有端到端证据）。

它做四件事：

1. **组版**：把海报内容（结构图 / 四张矩阵 / 图例 / 判定规则）写成 HTML+CSS，
   A4 纵向、白底黑字、`@page size A4`，设计画布 1240×1754（= A4 @ 150dpi）。
2. **量高**：先用 `google-chrome --headless --dump-dom` 读回
   `#poster` 内容宽度与页脚底边位置，**超过 A4 画布就报错退出**（不会悄悄裁掉内容）。
3. **截图**：`--window-size=1240,1754 --force-device-scale-factor=2`，
   于是成品 PNG 是 2480×3508（= A4 @ 300dpi），打印尺寸正好一页。
4. **核对**：PNG 必须是 2480×3508；HTML 与 PNG 字节里都不许出现
   用户名 / 绝对路径（`/home/`、`/Users/`、`zhensirong` 等）。

字体：本机已装 `Noto Sans CJK SC`（中文字形）与 `DejaVu Sans`（▢/◧/■ 几何符号），
CSS 显式写字体栈，不联网、不装新依赖。证据全部取自 `manual/page-00…09.md`
的「你应该看到」（真跑输出），不在本脚本里另造数值。

依赖：本机已有的 python3 / google-chrome / Noto Sans CJK SC。
不改 `term_render.py` / `web_shots.py` / `render_flow.py` / `render_aoa.py`。
"""

from __future__ import annotations

import html
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent        # manual/shots
REPO = HERE.parents[1]                        # 仓库根目录
OUT_DIR = REPO / "manual" / "completeness"
CHROME = "google-chrome"

# A4 竖向：设计画布 1240×1754（150dpi），截图 ×2 → 2480×3508（300dpi）
PAGE_W, PAGE_H = 1240, 1754
SHOT_W, SHOT_H = PAGE_W * 2, PAGE_H * 2

# 成图里不许出现的字符串（用户名 / 绝对路径）
FORBIDDEN = ["/home/", "/Users/", "/tmp/", "zhensirong", "root@", ".dsh"]

GLYPH = {"answer": "■", "blank": "▢"}
DASH = "—"


# ------------------------------------------------------------------ 内容数据

# 四张矩阵：行 = 该层节点（责任），列 = 该层必须提供的能力；最后一列证据。
# 证据全部对应 manual/page-0X.md「你应该看到」的真跑输出。
MATRICES = [
    {
        "key": "l1",
        "title": "L1 · 上下文",
        "tag": "C4 L1",
        "cols": ["接收提问", "返回答案", "访问数据"],
        "rows": [
            ("人 → 系统交互", ["■", "■", DASH],
             "浏览器 :8081 输入「华北销售额」→ 页面出 41099.5"),
            ("系统 → 数据源访问", [DASH, DASH, "■"],
             "真执行 SELECT（JOIN dim_region）→ rows[0].sales=41099.5"),
        ],
        "widths": [200, 160, 160, 160, 480],
    },
    {
        "key": "l2",
        "title": "L2 · 容器",
        "tag": "C4 L2",
        "cols": ["静态与入口转发", "问答编排与 HTTP", "数据存储与查询"],
        "rows": [
            ("nginx:8081（A9）", ["■", DASH, DASH],
             "GET :8081/ → 200；浏览器经 :8081 出 41099.5"),
            ("backend:8000（A3）", [DASH, "■", DASH],
             'curl :8000/health → {"ok":true}；POST /api/query → rows[0].sales=41099.5'),
            ("MySQL:3307（A1·A2）", [DASH, DASH, "■"],
             "SELECT VERSION()=8.0.46；COUNT(*)=115；华北 SUM=41099.5"),
        ],
        "widths": [230, 150, 170, 150, 460],
    },
    {
        "key": "l3",
        "title": "L3 · 组件（backend:8000 内）",
        "tag": "C4 L3",
        "cols": ["收问", "抽词", "生成 SQL", "执行", "流式推送"],
        "rows": [
            ("A4 接口", ["■", DASH, DASH, DASH, DASH],
             'POST /api/query → keywords=[]、sql=null、rows=[]（两次一字不差）'),
            ("A5 抽词", [DASH, "■", DASH, DASH, DASH],
             'keywords=["华北","销售额"]'),
            ("A6 生成 SQL", [DASH, DASH, "■", DASH, DASH],
             "print 出 5 行 SELECT：SUM + JOIN dim_region + WHERE 华北"),
            ("A7 执行", [DASH, DASH, DASH, "■", DASH],
             "rows[0].sales=41099.5（19 条华北订单求和）"),
            ("A8 流式", [DASH, DASH, DASH, DASH, "■"],
             "progress=12 条 + result 1 条 → 41099.5"),
        ],
        "widths": [150, 82, 82, 96, 82, 82, 600],
    },
    {
        "key": "l0",
        "title": "L0 · 地基（非 C4）",
        "tag": "非 C4",
        "cols": ["可运行环境", "可查询数据"],
        "rows": [
            ("环境（A0）", ["■", DASH],
             "make doctor → 12/12 通过（工具 6 项 + 依赖 3 项 + 端口 3 项全 ✓）"),
            ("数据（A1·A2）", [DASH, "■"],
             "SELECT VERSION()=8.0.46；SHOW TABLES → 5 行；COUNT(*)=115"),
        ],
        "widths": [200, 180, 180, 600],
    },
]

# 结构图的节点（槽位状态方框只挂在「主位置」：A0–A2 在 L0、A3 在 L2 backend、
# A4–A8 在 L3、A9 在 L2 nginx。L1/L2 里其余标签只做映射，避免同一个槽位两处状态。
L1_NODES = [
    {"kind": "user", "name": "👤 用户", "note": "外部参与者"},
    {"kind": "sys", "name": "问数系统", "ref": "A3–A9", "note": "系统边界（构建范围）"},
    {"kind": "ext", "name": "MySQL（外部）", "ref": "A1·A2", "note": "外部依赖 · 数据源"},
]

L2_NODES = [
    {"name": "nginx:8081", "slot": "A9", "note": "静态页 · /api/ 反代"},
    {"name": "backend:8000", "slot": "A3", "note": "内含 A4–A8（见 L3）"},
    {"name": "MySQL:3307", "ref": "A1·A2", "note": "状态见 L0"},
]

L3_NODES = [
    {"name": "A4 接口", "slot": "A4", "note": "收 question"},
    {"name": "A5 抽词", "slot": "A5", "note": "问题 → 关键词"},
    {"name": "A6 生成 SQL", "slot": "A6", "note": "契约 → SELECT"},
    {"name": "A7 执行", "slot": "A7", "note": "pymysql → rows"},
    {"name": "A8 流式", "slot": "A8", "note": "SSE 逐条推"},
]

L0_NODES = [
    {"name": "A0 环境", "slot": "A0", "note": "Docker/uv/Node + 依赖"},
    {"name": "A1 建容器", "slot": "A1", "note": "lab-mysql · :3307"},
    {"name": "A2 导入数据", "slot": "A2", "note": "建表 + 灌数据"},
]


# ------------------------------------------------------------------ 小组件

def esc(text: str) -> str:
    return html.escape(text, quote=False)


def state(mode: str) -> str:
    return GLYPH[mode]


def node_html(mode: str, name: str, note: str = "", slot: str = "", ref: str = "",
              cls: str = "") -> str:
    """结构图节点：槽位编号 + 三态方框（slot），或只是映射标签（ref）。"""
    top = ""
    if slot:
        top = (f'<div class="ntop"><span class="slot">{esc(slot)}</span>'
               f'<span class="st">{state(mode)}</span></div>')
    elif ref:
        top = f'<div class="ntop"><span class="slot ref">{esc(ref)}</span></div>'
    note_html = f'<div class="nnote">{esc(note)}</div>' if note else ""
    return (f'<div class="node {cls}">{top}<div class="nname">{esc(name)}</div>'
            f'{note_html}</div>')


def arrow_html(label: str) -> str:
    return f'<div class="arrow"><span class="al">{esc(label)}</span><span class="ag">→</span></div>'


def layer_html(code: str, name: str, tag: str, lane: str) -> str:
    return (f'<div class="layer"><div class="lname"><b>{esc(code)}</b>'
            f'<span>{esc(name)}</span><small>{esc(tag)}</small></div>'
            f'<div class="lane {code.lower()}lane">{lane}</div></div>')


# ------------------------------------------------------------------ 结构图

def diagram_html(mode: str) -> str:
    l1 = (node_html(mode, "👤 用户", "外部参与者", cls="user")
          + arrow_html("A9 入口")
          + node_html(mode, "问数系统", "系统边界（构建范围）", ref="A3–A9", cls="sys")
          + arrow_html("A7 执行")
          + node_html(mode, "MySQL（外部）", "外部依赖 · 数据源", ref="A1·A2", cls="ext"))

    l2 = (node_html(mode, "nginx:8081", "静态页 · /api/ 反代", slot="A9", cls="nginx")
          + arrow_html("/api/ 反代")
          + node_html(mode, "backend:8000", "内含 A4–A8（见 L3）", slot="A3", cls="backend")
          + arrow_html("pymysql :3307")
          + node_html(mode, "MySQL:3307", "状态见 L0", ref="A1·A2", cls="mysql"))

    l3 = ""
    for i, n in enumerate(L3_NODES):
        if i:
            l3 += arrow_html(["问句", "关键词", "SQL", "rows"][i - 1])
        l3 += node_html(mode, n["name"], n["note"], slot=n["slot"], cls="comp")

    l0 = ""
    for i, n in enumerate(L0_NODES):
        if i:
            l0 += '<span class="sep">｜</span>'
        l0 += node_html(mode, n["name"], n["note"], slot=n["slot"], cls="base")

    if mode == "answer":
        foot = ('<span class="tick">■ 槽位 A0–A9：10/10 已建且判据通过</span>'
                '<span class="tick">端到端：浏览器 :8081 → :8000 → A4–A8 → MySQL:3307 → 41099.5 ✓</span>')
    else:
        foot = ('<span class="todo">▢ 槽位 A0–A9：__/10 已勾</span>'
                '<span class="todo">端到端：浏览器 :____ → :8000 → …… → :3307 → 结果 ________</span>')

    return (layer_html("L1", "上下文", "C4", l1)
            + layer_html("L2", "容器", "C4", l2)
            + layer_html("L3", "组件", "C4", l3)
            + layer_html("L0", "地基", "非 C4", l0)
            + f'<div class="diag-foot">{foot}</div>')


# ------------------------------------------------------------------ 矩阵

def matrix_html(mode: str, m: dict) -> str:
    nrow, ncol = len(m["rows"]), len(m["cols"])
    if mode == "answer":
        cov = f'行 {nrow}/{nrow} ✓　列 {ncol}/{ncol} ✓'
    else:
        cov = f'行 __/{nrow}　列 __/{ncol}'

    colgroup = "".join(f'<col style="width:{w}px">' for w in m["widths"])
    head = ('<tr><th class="rh">责任 ↓　能力 →</th>'
            + "".join(f"<th>{esc(c)}</th>" for c in m["cols"])
            + '<th class="evh">证据（实跑判据）</th></tr>')

    body = ""
    for label, marks, ev in m["rows"]:
        cells = ""
        for mark in marks:
            if mode == "answer":
                cls = "mark dash" if mark == DASH else "mark"
                cells += f'<td class="{cls}">{esc(mark)}</td>'
            else:
                cells += '<td class="mark empty"></td>'
        ev_html = esc(ev) if mode == "answer" else ""
        body += (f'<tr><th class="rh">{esc(label)}</th>{cells}'
                 f'<td class="ev{" blank" if mode == "blank" else ""}">{ev_html}</td></tr>')

    return (f'<div class="mtitle"><b>{esc(m["title"])}</b>'
            f'<span class="c4">{esc(m["tag"])}</span>'
            f'<span class="cov">{cov}</span></div>'
            f'<table class="mtx {m["key"]}"><colgroup>{colgroup}</colgroup>'
            f'<thead>{head}</thead><tbody>{body}</tbody></table>')


# ------------------------------------------------------------------ 图例 + 规则

def legend_html() -> str:
    items = [
        ("▢", "未建", "还没动手，或没跑通。按对应页从头做，做到该页「你应该看到」。"),
        ("◧", "已建未验", "做完了但没对判据。回该页重跑命令 / 刷新页面，看到判据才算数。"),
        ("■", "已建且判据通过", "输出与页面「你应该看到」逐字一致；把命令 + 输出写进矩阵末列。"),
    ]
    cards = "".join(
        f'<div class="lg-item"><span class="lgbox">{g}</span>'
        f'<div><b>{esc(t)}</b><p>{esc(d)}</p></div></div>'
        for g, t, d in items)
    return (f'<div class="lg">{cards}</div>'
            '<div class="lg-note">只允许 ▢ → ◧ → ■：做完 ≠ 通过；◧ 是最容易停住的状态，'
            '回页面把判据重跑一遍再涂黑。</div>')


def rules_html(mode: str) -> str:
    if mode == "answer":
        rows = [
            ("✓", "① 每行 ≥ 1 个 ■",
             "12 个节点行全部有 ■（节点不是空壳）"),
            ("✓", "② 每列 ≥ 1 个 ■",
             "13 项能力列全部有 ■（能力没有漏项）"),
            ("✓", "③ 跨层边都通 + 端到端证据",
             "浏览器 :8081 → nginx → :8000 → A4–A8 → MySQL:3307 → 41099.5"),
        ]
        final = ('<div class="final-text">四层全通过 ⇒ <b>系统能力完备</b></div>'
                 '<div class="final-sub">A0–A9 10/10 ■ · 12 行 × 13 列全绿 · 端到端 41099.5</div>'
                 '<div class="stamp">完备 ✓</div>')
    else:
        rows = [
            ("□", "① 每行 ≥ 1 个 ■", "行 __/12 有 ■（节点不是空壳）"),
            ("□", "② 每列 ≥ 1 个 ■", "列 __/13 有 ■（能力没有漏项）"),
            ("□", "③ 跨层边都通 + 端到端证据", "端到端最后一格看到的数：________"),
        ]
        final = ('<div class="final-text">四层全通过 ⇒ <b>系统能力完备</b></div>'
                 '<div class="final-sub">自己数一遍：■ 满 10 个、行/列都不留空、端到端出数</div>'
                 '<div class="stamp blank">待自检 □</div>')

    row_html = "".join(
        f'<div class="rrow"><span class="chk">{esc(c)}</span>'
        f'<b>{esc(t)}</b><span class="rt">{esc(d)}</span></div>'
        for c, t, d in rows)
    return row_html + f'<div class="final">{final}</div>'


# ------------------------------------------------------------------ 整页

def header_html(mode: str) -> str:
    if mode == "answer":
        badge, note = "答案版", "参考答案（空白版见 poster-blank.png）"
        lead = ("依据 D38：C4 三层 + L0 地基，每层一张「责任 × 证据」矩阵；"
                "每格要么 ■ 要么 —，末列写实跑判据。")
    else:
        badge, note = "空白版", "打印后勾三态 / 填矩阵（答案版见 poster-answer.png）"
        lead = ("依据 D38：C4 三层 + L0 地基，每层一张「责任 × 证据」矩阵；"
                "做完 ≠ 通过：把实跑判据填进末列。")
    return (f'<div class="hdr"><div class="hdr-left">'
            f'<div class="kicker">练本总装 · 第 0–9 页 · 依据 D38</div>'
            f'<h1>完备性证明 <span class="middot">·</span> 问数系统能力覆盖</h1>'
            f'<div class="sub">C4 三层：L1 上下文 / L2 容器 / L3 组件 ＋ L0 地基'
            f'<span class="bar">｜</span>槽位 A0–A9<span class="bar">｜</span>'
            f'四层全部通过 ⇒ 系统能力完备</div>'
            f'<div class="lead">{esc(lead)}</div></div>'
            f'<div class="hdr-right"><div class="badge {mode}">{esc(badge)}</div>'
            f'<div class="badge-note">{esc(note)}</div></div></div>')


def footer_html() -> str:
    return ('<div class="foot">判据出处：第 0–9 页「你应该看到」（真跑输出）；'
            '槽位编号与活动名见 flow.mmd；端口 3307 / 8000 / 8081 按 SPEC。'
            '版本号、包数量随机器不同，看到同类输出即算对上。</div>')


CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #ffffff; }
body {
  width: 1240px; min-height: 1754px;
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
  color: #111111;
  -webkit-font-smoothing: antialiased;
}
.poster {
  width: 1240px; min-height: 1754px; padding: 30px 44px 22px;
  display: flex; flex-direction: column;
}
.mono, .ev, .slot, .cov, .chk, .foot { font-family: "DejaVu Sans Mono", "Noto Sans CJK SC", monospace; }

/* ---------- 页眉 ---------- */
.hdr { display: flex; justify-content: space-between; align-items: flex-start;
       border-bottom: 3.5px solid #111; padding-bottom: 9px; }
.kicker { font-size: 13px; letter-spacing: .8px; color: #555; margin-bottom: 4px; }
h1 { margin: 0; font-size: 41px; line-height: 1.1; letter-spacing: .5px; font-weight: 900; }
h1 .middot { font-weight: 400; }
.sub { margin-top: 5px; font-size: 15.5px; color: #222; }
.sub .bar { color: #999; padding: 0 5px; }
.lead { margin-top: 4px; font-size: 13.5px; color: #555; }
.hdr-right { text-align: right; padding-left: 18px; flex: 0 0 auto; }
.badge { display: inline-block; border: 2.5px solid #111; border-radius: 5px;
         padding: 4px 14px; font-size: 19px; font-weight: 900; letter-spacing: 2px; }
.badge.blank { background: #fff; }
.badge.answer { background: #111; color: #fff; }
.badge-note { margin-top: 5px; font-size: 11.5px; color: #555; }

/* ---------- 分区标题 ---------- */
.sec { margin-top: 15px; }
.sec-h { display: flex; align-items: baseline; gap: 9px; margin-bottom: 6px; }
.sec-h .num { display: inline-block; background: #111; color: #fff; border-radius: 4px;
              width: 24px; height: 24px; line-height: 24px; text-align: center;
              font-size: 15px; font-weight: 700; flex: 0 0 auto; align-self: center; }
.sec-title { font-size: 21px; font-weight: 900; letter-spacing: .3px; }
.sec-hint { font-size: 12.5px; color: #555; }

/* ---------- ① 结构图 ---------- */
.diagram { border: 2px solid #111; border-radius: 8px; padding: 8px 12px 6px; }
.layer { display: flex; align-items: stretch; gap: 12px; padding: 7px 0; }
.layer + .layer { border-top: 1px dashed #b9b9b9; }
.lname { flex: 0 0 98px; display: flex; flex-direction: column; justify-content: center;
         border-right: 2.5px solid #111; padding-right: 10px; line-height: 1.25; }
.lname b { font-size: 19px; font-weight: 900; }
.lname span { font-size: 13px; color: #333; }
.lname small { font-size: 10.5px; color: #777; }
.lane { flex: 1; display: flex; align-items: center; justify-content: space-between;
        gap: 9px; padding: 0 6px; }
.node { border: 1.7px solid #111; border-radius: 6px; background: #fff;
        padding: 6px 11px 7px; text-align: left; }
.node .ntop { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
.slot { display: inline-block; font-size: 11.5px; line-height: 17px; padding: 0 5px;
        background: #ededed; border: 1px solid #888; border-radius: 3px; color: #222; }
.slot.ref { background: #fff; border-style: dashed; color: #555; }
.st { font-family: "DejaVu Sans", sans-serif; font-size: 19px; line-height: 1; }
.nname { font-size: 17px; font-weight: 800; line-height: 1.2; }
.nnote { font-size: 11.5px; color: #555; line-height: 1.25; margin-top: 2px; }
.arrow { display: flex; flex-direction: column; align-items: center; flex: 0 0 auto; }
.arrow .al { font-size: 10.5px; color: #555; line-height: 1.1; }
.arrow .ag { font-size: 25px; line-height: 1; font-family: "DejaVu Sans", sans-serif; }
.l1lane .node.user { min-width: 150px; }
.l1lane .node.sys { min-width: 270px; }
.l1lane .node.ext { min-width: 250px; }
.l1lane .node.user .nname { filter: grayscale(1); }
.l2lane .node { min-width: 245px; }
.l2lane .node.backend { min-width: 285px; }
.l3lane .node { min-width: 168px; padding-left: 9px; padding-right: 9px; }
.l3lane .nname { font-size: 15px; }
.l3lane .nnote { font-size: 11px; }
.sep { font-size: 20px; color: #999; }
.l0lane .node { min-width: 300px; }
.diag-foot { display: flex; gap: 18px; flex-wrap: wrap; border-top: 1.5px solid #111;
             margin-top: 6px; padding-top: 6px; font-size: 12.5px; }
.diag-foot .tick { font-weight: 700; }
.diag-foot .todo { color: #666; }

/* ---------- ② 矩阵 ---------- */
.mtitle { display: flex; align-items: center; gap: 8px; margin: 11px 0 4px; }
.mtitle b { font-size: 16px; font-weight: 900; }
.c4 { font-size: 10.5px; color: #555; border: 1px solid #999; border-radius: 3px; padding: 0 5px; }
.cov { margin-left: auto; font-size: 12px; color: #333; }
table.mtx { width: 100%; border-collapse: collapse; table-layout: fixed; }
.mtx th, .mtx td { border: 1px solid #333; padding: 4px 9px; vertical-align: middle; }
.mtx thead th { background: #e8e8e8; font-size: 14px; font-weight: 800;
                text-align: center; line-height: 1.2; }
.mtx thead th.rh, .mtx thead th.evh { text-align: left; }
.mtx tbody th { background: #f5f5f5; text-align: left; font-size: 14px;
                font-weight: 800; line-height: 1.2; }
.mtx td { height: 31px; }
.mtx td.mark { text-align: center; font-family: "DejaVu Sans", sans-serif;
               font-size: 19px; line-height: 1; font-weight: 700; }
.mtx td.mark.dash { color: #666; font-weight: 400; font-size: 16px; }
.mtx td.ev { font-size: 12.5px; line-height: 1.32; color: #111;
             overflow-wrap: anywhere; }
.mtx td.ev.blank { background: #fcfcfc; }
.poster.blank .mtx td { height: 35px; }
.poster.blank .mtx td.ev {
  background-image: linear-gradient(#cfcfcf, #cfcfcf);
  background-size: 100% 1px;
  background-position: 0 calc(100% - 8px);
  background-repeat: no-repeat;
}

/* ---------- ③ 图例 ---------- */
.lg { display: flex; gap: 12px; }
.lg-item { flex: 1 1 0; display: flex; gap: 10px; align-items: flex-start;
           border: 1.6px solid #111; border-radius: 6px; padding: 7px 11px; }
.lgbox { font-family: "DejaVu Sans", sans-serif; font-size: 31px; line-height: 1; }
.lg-item b { display: block; font-size: 15px; }
.lg-item p { margin: 2px 0 0; font-size: 12px; line-height: 1.4; color: #333; }
.lg-note { margin-top: 6px; font-size: 12px; color: #444; }

/* ---------- ④ 判定规则 ---------- */
.rrow { display: flex; align-items: baseline; gap: 9px; border: 1.2px solid #aaa;
        border-radius: 5px; padding: 5px 11px; margin-bottom: 5px; font-size: 13.5px; }
.rrow .chk { font-size: 17px; font-weight: 700; flex: 0 0 auto; }
.rrow b { flex: 0 0 auto; font-size: 14px; }
.rrow .rt { color: #333; }
.final { margin-top: 8px; display: flex; align-items: center; gap: 14px;
         border: 2.5px solid #111; border-radius: 6px; padding: 8px 14px; }
.final-text { font-size: 18px; font-weight: 800; flex: 0 0 auto; }
.final-sub { font-size: 12.5px; color: #333; flex: 1 1 auto; }
.stamp { flex: 0 0 auto; border: 3px double #111; padding: 1px 14px;
         font-size: 20px; font-weight: 900; letter-spacing: 2px; transform: rotate(-5deg); }
.stamp.blank { border: 2px dashed #888; color: #777; font-size: 15px;
               letter-spacing: 1px; transform: none; }
.foot { margin-top: 14px; padding-top: 6px; border-top: 1px solid #bbb;
        font-size: 11px; color: #555; line-height: 1.35; }
"""


def build_html(mode: str) -> str:
    body = (header_html(mode)
            + '<div class="sec"><div class="sec-h"><span class="num">①</span>'
              '<span class="sec-title">叠层结构图</span>'
              '<span class="sec-hint">从上到下 = C4 抽象层级；槽位 A0–A9 各一个三态方框（主位置）；虚线槽位 = 映射；L4 代码不上图</span></div>'
              f'<div class="diagram">{diagram_html(mode)}</div></div>'
            + '<div class="sec"><div class="sec-h"><span class="num">②</span>'
              '<span class="sec-title">四张「责任 × 证据」矩阵</span>'
              '<span class="sec-hint">行 = 该层节点，列 = 从运行时需求倒推的能力；■ = 由它提供且判据通过，— = 不由它提供</span></div>'
            + "".join(matrix_html(mode, m) for m in MATRICES)
            + '</div>'
            + '<div class="sec"><div class="sec-h"><span class="num">③</span>'
              '<span class="sec-title">三态图例</span>'
              '<span class="sec-hint">每个槽位、每个矩阵格只认三种状态</span></div>'
              f'{legend_html()}</div>'
            + '<div class="sec"><div class="sec-h"><span class="num">④</span>'
              '<span class="sec-title">判定规则</span>'
              '<span class="sec-hint">三条全绿才敢说「完备」；四层全通过 ⇒ 系统能力完备</span></div>'
              f'{rules_html(mode)}</div>'
            + footer_html())
    return ("<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<title>完备性证明海报</title>"
            f"<style>{CSS}</style></head><body>"
            f'<div class="poster {mode}" id="poster">{body}</div>'
            "<script>"
            "window.addEventListener('load', function(){"
            "var p=document.getElementById('poster');"
            "var f=document.querySelector('.foot');"
            "document.title='DIM '+p.scrollWidth+' '+Math.ceil(f.getBoundingClientRect().bottom);"
            "});"
            "</script></body></html>\n")


# ------------------------------------------------------------------ Chrome

def chrome(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--disable-dev-shm-usage"]
    return subprocess.run(cmd + args, capture_output=True, text=True, timeout=180)


def measure(page_html: Path, work: Path) -> tuple[int, int]:
    proc = chrome([
        f"--window-size={PAGE_W},{PAGE_H}",
        "--virtual-time-budget=5000",
        f"--user-data-dir={work / 'chrome-measure'}",
        "--dump-dom", page_html.as_uri(),
    ])
    m = re.search(r"<title>DIM (\d+) (\d+)</title>", proc.stdout)
    if not m:
        raise SystemExit(f"量高失败：chrome 没回 DIM 标记\n{proc.stderr[-1500:]}")
    return int(m.group(1)), int(m.group(2))


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
        if bad in text:
            raise SystemExit(f"{where} 里出现禁用字符串 {bad!r}（不许出现用户名 / 绝对路径）")


def render(mode: str, out_png: Path) -> None:
    page = build_html(mode)
    check_forbidden(page, f"{mode} HTML")
    if "Noto Sans CJK SC" not in page:
        raise SystemExit("CSS 没有指定中文字体 Noto Sans CJK SC")

    with tempfile.TemporaryDirectory(prefix="poster-") as tmp:
        work = Path(tmp)
        html_path = work / f"poster-{mode}.html"
        html_path.write_text(page, encoding="utf-8")

        w, h = measure(html_path, work)
        if w > PAGE_W:
            raise SystemExit(f"{mode} 版内容宽度 {w}px 超过 A4 画布 {PAGE_W}px（会横向裁切）")
        if h > PAGE_H:
            raise SystemExit(f"{mode} 版内容高度 {h}px 超过 A4 画布 {PAGE_H}px（会超出一页）")

        raw = work / f"poster-{mode}.raw.png"
        screenshot(html_path, raw, work)
        png_bytes = raw.read_bytes()

    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(png_bytes)

    pw, ph = png_size(out_png)
    if (pw, ph) != (SHOT_W, SHOT_H):
        raise SystemExit(f"{out_png} 尺寸 {pw}x{ph}，应为 {SHOT_W}x{SHOT_H}（A4 @300dpi）")
    check_forbidden(out_png.read_bytes().decode("latin-1", "ignore"), f"{out_png.name} 字节")
    print(f"  {out_png.relative_to(REPO)}  {pw}x{ph}  "
          f"（内容 {w}x{h} / 画布 {PAGE_W}x{PAGE_H}）")


def main() -> None:
    print("「完备性证明」海报：从 HTML+CSS 渲染两张 A4 PNG")
    for mode, filename in (("blank", "poster-blank.png"), ("answer", "poster-answer.png")):
        render(mode, OUT_DIR / filename)
    print("完成：空白版 + 答案版均为 2480×3508（A4 竖向 / 300dpi），可 100% 打印。")


if __name__ == "__main__":
    sys.exit(main())
