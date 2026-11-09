#!/usr/bin/env python3
"""Generate the four validation figures for the Editorial style sample."""
from __future__ import annotations

import html
from pathlib import Path

OUT = Path(__file__).resolve().parent
W, H = 1600, 1100

INK = "#111111"
INK2 = "#5B5B5B"
LINE = "#D9D3C7"
PAPER = "#FFFDF8"
COBALT = "#1F4E9C"
RUST = "#B24A2E"
FOREST = "#2F5D46"
MUSTARD = "#C58B1B"
TINT = "#E7EDF8"
WASH = "#F8F5ED"


def t(x, y, text, size=28, fill=INK, weight="400", anchor="start", family="Noto Sans CJK SC"):
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{html.escape(text)}</text>'
    )


def lines(x, y, texts, size=28, fill=INK, weight="400", anchor="start", gap=38):
    out = [t(x, y, texts[0], size, fill, weight, anchor)]
    for i, s in enumerate(texts[1:], 1):
        out.append(t(x, y + i * gap, s, size, fill, weight, anchor))
    return "".join(out)


def box(x, y, w, h, title, body, accent=COBALT, fill=PAPER, title_size=34, body_size=26):
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{accent}" stroke-width="2.4"/>',
        t(x + 22, y + 46, title, title_size, accent, "700"),
    ]
    for i, line in enumerate(body):
        parts.append(t(x + 22, y + 88 + i * 38, line, body_size, INK2))
    return "".join(parts)


def arrow(x1, y1, x2, y2, color=INK, width=2.6, head=12):
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="{width}" marker-end="url(#arrow-{color[1:]})"/>'
    )


def defs():
    colors = [INK, COBALT, RUST, FOREST, MUSTARD]
    markers = []
    for c in colors:
        markers.append(
            f'<marker id="arrow-{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>'
        )
    return "<defs>" + "".join(markers) + "</defs>"


def svg(body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">{defs()}{body}</svg>'
    )


# ---------- 0a · 一次问数，五道关 ----------
parts = [
    t(80, 76, "一次问数，五道关", 42, INK, "700"),
    t(80, 118, "单轮 · 单库 · 只读 · 可拒答", 26, INK2),
]
xs = [70, 370, 670, 970, 1270]
boxes = [
    ("用户提问", ["自然语言", "POST /api/query"]),
    ("生成", ["一条 SQL", "或一次拒答", "S4"]),
    ("策略闸", ["单语句 / 只读", "表列白名单", "S5"]),
    ("只读执行", ["dw_reader", "max_execution", "_time", "S5"]),
    ("回答", ["result / error", "SSE 三事件", "S7"]),
]
for i, (title, body) in enumerate(boxes):
    accent = RUST if i == 2 else COBALT
    parts.append(box(xs[i], 220, 260, 300, title, body, accent))
for i in range(4):
    parts.append(arrow(xs[i] + 260, 370, xs[i + 1], 370, INK))
# refuse branch
parts.append(arrow(xs[2] + 130, 520, xs[2] + 130, 650, RUST))
parts.append(box(xs[2], 650, 260, 150, "拒绝", ["SQL_REJECTED", "原因码在 detail"], RUST, "#FBF0EC", 32, 24))
parts.append(t(xs[4] + 20, 640, "0 行 = empty", 24, INK2))
parts.append(t(xs[4] + 20, 680, "取消 = cancelled", 24, INK2))
parts.append(t(80, 930, "每一关都回答同一个问题：这条 SQL 凭什么可以继续？", 28, INK2))
parts.append(t(80, 980, "闸门在连库之前；拒绝也是一个可判定的结论。", 24, INK2))
(OUT / "fig-0a-one-minute.svg").write_text(svg("".join(parts)), encoding="utf-8")

# ---------- 0b · 四道交接 ----------
parts = [
    t(80, 76, "四道交接：每一站都要交出一个判据", 42, INK, "700"),
    t(80, 118, "上一阶段留下风险，这一阶段压住不确定性，判据是一条可重复的命令。", 26, INK2),
]
cols = [
    ("S4 → S5", "01", ["SQL 看起来对，但", "可能写库、越权、", "拖垮服务"], ["36 条注入全拒", "11 条零误杀"]),
    ("S5 → S6", "02", ["拒绝是一个结论，", "但用户看不到结论"], ["每类失败对上", "码 / 类 / 步骤"]),
    ("S6 → S7", "03", ["事件有名字，但", "界面可能不认"], ["生成物与夹具", "逐字一致"]),
    ("S7 → S8", "04", ["开发机能跑，换", "一台机器未必能起"], ["启动链与", "验收脚本"]),
]
xs = [80, 460, 840, 1220]
for i, (stage, num, risk, proof) in enumerate(cols):
    x = xs[i]
    parts.append(t(x, 200, stage, 30, COBALT, "700"))
    parts.append(t(x + 270, 200, num, 40, LINE, "700", "end"))
    parts.append(box(x, 230, 300, 180, "留下的风险", risk, RUST, "#FBF0EC", 28, 24))
    parts.append(arrow(x + 150, 410, x + 150, 490, INK))
    parts.append(box(x, 490, 300, 170, "判据", proof, COBALT, TINT, 28, 24))
parts.append(t(80, 740, "可停点 = 这一类不确定性有了可重复的判据，不是「功能做完」。", 28, INK2))
parts.append(t(80, 790, "四站都交得出判据，才把「能跑」变成「敢用」。", 24, INK2))
(OUT / "fig-0b-four-handoffs.svg").write_text(svg("".join(parts)), encoding="utf-8")

# ---------- 3-2a · 三层单向依赖 ----------
parts = [
    t(80, 76, "三层单向依赖：改契约，不改生成物", 42, INK, "700"),
    t(80, 118, "契约 → 生成物 → 运行时；箭头只向下，手改生成物等于在运行时层伪造事实源。", 26, INK2),
]
bands = [
    (180, "事实源", ["contracts/*.yaml / *.json", "表、列、步骤、错误码"], FOREST, "#EEF4EF"),
    (470, "生成物", ["frontend/src/generated/*", "由契约生成，不能手改"], COBALT, TINT),
    (760, "运行时", ["SseParser / App.tsx", "只读生成物，不回头改契约"], MUSTARD, "#FBF3E2"),
]
for y, title, body, accent, fill in bands:
    parts.append(box(140, y, 1100, 190, title, body, accent, fill, 34, 26))
parts.append(arrow(690, 370, 690, 460, FOREST))
parts.append(t(710, 425, "生成", 24, FOREST))
parts.append(arrow(690, 660, 690, 750, COBALT))
parts.append(t(710, 715, "约束", 24, COBALT))
# crossed hand-edit arrow
parts.append(f'<line x1="1300" y1="850" x2="1300" y2="330" stroke="{RUST}" stroke-width="2.2" stroke-dasharray="8 8" marker-end="url(#arrow-{RUST[1:]})"/>')
parts.append(t(1322, 560, "手改 =", 22, RUST, "700"))
parts.append(t(1322, 594, "伪造事实源", 22, RUST, "700"))
parts.append(t(1322, 640, "--check 会红", 21, RUST))
(OUT / "fig-3-2a-three-layers.svg").write_text(svg("".join(parts)), encoding="utf-8")

# ---------- 4-2a · 六服务启动链 ----------
parts = [
    t(80, 76, "六服务启动链：三条边决定页面能不能打开", 42, INK, "700"),
    t(80, 118, "三存储 healthy → init 退出 0 → backend healthy → frontend。", 26, INK2),
]
stores = [("mysql", 180), ("elasticsearch", 330), ("qdrant", 480)]
for name, y in stores:
    parts.append(box(80, y, 280, 110, name, ["healthy"], COBALT, TINT, 30, 24))
parts.append(arrow(360, 235, 480, 375, COBALT))
parts.append(arrow(360, 385, 480, 395, COBALT))
parts.append(arrow(360, 535, 480, 415, COBALT))
parts.append(box(480, 300, 300, 240, "init", ["建库 / 只读账号 / S2 校验", "退出 0"], RUST, "#FBF0EC", 34, 24))
parts.append(arrow(780, 420, 900, 420, RUST))
parts.append(t(790, 400, "exit 0", 22, RUST))
parts.append(box(900, 330, 280, 180, "backend", ["FastAPI · 单 worker", "healthy"], MUSTARD, "#FBF3E2", 30, 24))
parts.append(arrow(1180, 420, 1250, 420, MUSTARD))
parts.append(box(1250, 360, 240, 120, "frontend", ["nginx · 8080"], FOREST, "#EEF4EF", 28, 22))
parts.append(t(80, 760, "service_healthy = 持续为真", 26, COBALT, "700"))
parts.append(t(80, 800, "service_completed_successfully = 一次性结果", 26, RUST, "700"))
parts.append(t(80, 870, "页面 502 先查这条链，不要一上来改 nginx。", 26, INK2))
(OUT / "fig-4-2a-startup-chain.svg").write_text(svg("".join(parts)), encoding="utf-8")

# ---------- 0a · 一次真实问数（教材版走查） ----------
parts = [
    t(80, 76, "一次真实问数：SQL 从哪来，在哪被拦", 42, INK, "700"),
    t(80, 118, "示例：上个月华东的销售额是多少", 26, INK2),
]
rows = [
    ("01", "用户提问", "自然语言", "上个月华东的销售额是多少？", "单轮 / 单库 / 只读 / 可拒答"),
    ("02", "生成 SQL", "S4", "一条 SQL，或一次拒答", ""),
    ("03", "策略闸", "S5", "单语句 / 只读 / 表列白名单 / LIMIT", ""),
    ("04", "只读执行", "S5", "dw_reader · max_execution_time = 5000", ""),
    ("05", "结果", "S7", "按列类型渲染，不把数字变成字符串", ""),
]
for i, (num, label, tag, note, extra) in enumerate(rows):
    y = 170 + i * 172
    accent = RUST if i == 2 else COBALT
    parts.append(f'<circle cx="120" cy="{y+48}" r="27" fill="{accent}"/>')
    parts.append(t(120, y + 57, num, 24, "#FFFFFF", "700", "middle"))
    parts.append(t(170, y + 42, label, 30, INK, "700"))
    parts.append(t(170, y + 76, tag, 22, accent, "700"))
    parts.append(f'<rect x="400" y="{y}" width="1120" height="150" rx="4" fill="{PAPER}" stroke="{LINE}" stroke-width="1.6"/>')
    if i == 1:
        parts.append(f'<rect x="420" y="{y+10}" width="1080" height="130" rx="3" fill="#151515"/>')
        code = [
            "SELECT SUM(order_amount) AS 销售额",
            "FROM fact_order JOIN dim_region",
            "  ON fact_order.region_id = dim_region.region_id",
            "WHERE dim_region.region_name = '华东'",
        ]
        for j, line in enumerate(code):
            parts.append(t(440, y + 45 + j * 27, line, 18, "#F3EBDD", "400", family="DejaVu Sans Mono"))
        parts.append(t(1250, y + 45, "或一次拒答", 20, "#C58B1B", "700", "end"))
    elif i == 2:
        checks = ["PASS  单语句", "PASS  只读根节点", "PASS  表 / 列在白名单", "PASS  补 LIMIT 1000"]
        for j, line in enumerate(checks):
            parts.append(t(430, y + 38 + j * 29, line, 22, FOREST, "700"))
        parts.append(t(900, y + 60, "UNION", 26, RUST, "700"))
        parts.append(t(900, y + 94, "→ SQL_REJECTED", 22, RUST, "700"))
        parts.append(t(900, y + 124, "原因码在 detail", 20, RUST))
    elif i == 3:
        parts.append(t(430, y + 50, "dw_reader", 28, COBALT, "700"))
        parts.append(t(430, y + 88, "max_execution_time = 5000", 22, INK2))
        parts.append(t(430, y + 122, "执行 decision.sql，不是模型原文", 22, INK2))
    elif i == 4:
        # mini result table
        parts.append(f'<rect x="430" y="{y+24}" width="620" height="36" fill="{TINT}"/>')
        parts.append(t(450, y + 49, "地区", 22, INK, "700"))
        parts.append(t(700, y + 49, "销售额", 22, INK, "700"))
        parts.append(f'<line x1="430" y1="{y+60}" x2="1050" y2="{y+60}" stroke="{INK}" stroke-width="1.2"/>')
        parts.append(t(450, y + 98, "华东", 24, INK))
        parts.append(t(700, y + 98, "87200.0", 24, INK, family="DejaVu Sans Mono"))
        parts.append(t(1100, y + 60, "number → 数字", 22, FOREST, "700"))
        parts.append(t(1100, y + 94, "不是 \"87200.0\"", 22, INK2))
    else:
        parts.append(t(430, y + 60, note, 30, INK, "700"))
        parts.append(t(430, y + 102, extra, 22, INK2))
parts.append(t(80, 1040, "关键：执行的是策略重新序列化后的 decision.sql；拒绝也是一个可判定的结论。", 26, INK2))
(OUT / "fig-0a-trace.svg").write_text(svg("".join(parts)), encoding="utf-8")

print("wrote 4 svgs + trace")


# ---------- 3-5a · Decimal("10") vs "10"（侧栏对照） ----------
def svg2(body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800" '
        f'width="600" height="800">{defs()}{body}</svg>'
    )

p = [
    t(30, 44, "旧系统", 30, RUST, "700"),
    t(30, 78, "default=str", 22, INK2, family="DejaVu Sans Mono"),
    f'<rect x="30" y="100" width="540" height="210" rx="4" fill="#FBF0EC" stroke="{RUST}" stroke-width="2"/>',
    t(55, 170, '{"销量": "10"}', 28, RUST, "700", family="DejaVu Sans Mono"),
    t(55, 225, "字符串 \"10\"", 26, RUST, "700"),
    t(55, 265, "不能求和", 26, RUST, "700"),
    arrow(300, 330, 300, 405, RUST),
    t(320, 375, "default=str", 22, RUST, "700", family="DejaVu Sans Mono"),
    t(30, 465, "新系统", 30, FOREST, "700"),
    t(30, 499, "归一化", 22, INK2),
    f'<rect x="30" y="520" width="540" height="210" rx="4" fill="#EEF4EF" stroke="{FOREST}" stroke-width="2"/>',
    t(55, 590, '{"销量": 10}', 28, FOREST, "700", family="DejaVu Sans Mono"),
    t(55, 645, "数字 10", 26, FOREST, "700"),
    t(55, 685, "可以求和", 26, FOREST, "700"),
    t(30, 780, '复制到表格："10" ≠ 10', 20, INK2),
]
(OUT / "fig-3-5a-decimal.svg").write_text(svg2("".join(p)), encoding="utf-8")
print("wrote side decimal figure")
