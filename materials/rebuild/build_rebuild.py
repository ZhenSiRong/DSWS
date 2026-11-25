#!/usr/bin/env python3
"""build_rebuild.py — 把 p17 阅读版重构成块组件版（g2 点选重构的等价产物）。

纪律：内容对等（Q8 判据1）——只 rewrap 语义元素，文本节点原样保留，
保护区的命令/数字/路径/判据原句零改动。重构版自正典，不回写 manual/read/。

跑：uv run --with beautifulsoup4 python manual/rebuild/build_rebuild.py
产物：manual/rebuild/page-17.rebuild.html（链接 rebuild.css + 阅读版基线样式）
"""
import re
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "manual/read/page-17.html"
OUT = ROOT / "manual/rebuild/page-17.rebuild.html"

# md 派生基线（Q4：记录 md 的 git 提交 + 日期；md 后续改动不自动同步）
baseline = subprocess.run(
    ["git", "log", "-1", "--format=%h %ci", "--", "manual/page-17.md"],
    cwd=ROOT, capture_output=True, text=True).stdout.strip()

soup = BeautifulSoup(SRC.read_text(encoding="utf-8"), "html.parser")
main = soup.select_one("main.page")
children = list(main.children)

out = BeautifulSoup("<main class='page'></main>", "html.parser")
new_main = out.main


def add(tag, **attrs):
    el = out.new_tag(tag, **attrs)
    new_main.append(el)
    return el


# ① 页面导航 + ② 阅读进度条（置顶）
nav = add("nav", **{"class": "rb-nav"})
nav.append(BeautifulSoup(
    '<a href="../read/page-16.html">← 上一页</a>'
    '<a href="#rb-toc">目录</a>'
    '<a href="../read/page-18.html">下一页 →</a>', "html.parser"))
prog = add("div", **{"class": "rb-progress"})
prog.append(out.new_tag("span"))

# ⑧ 锚点目录：从 h2 生成，并给 h2 赋 id
toc = add("nav", **{"class": "rb-toc", "id": "rb-toc"})
toc.append(BeautifulSoup('<p class="rb-toc-title">本页目录</p>', "html.parser"))
toc_ul = out.new_tag("ul")
toc.append(toc_ul)
sec = 0
for el in children:
    if getattr(el, "name", None) == "h2":
        sec += 1
        el["id"] = f"sec-{sec}"
        li = out.new_tag("li")
        a = out.new_tag("a", href=f"#sec-{sec}")
        a.string = el.get_text()
        li.append(a)
        toc_ul.append(li)

# 逐元素 rewrap（文本不动）
step_no = 0
i = 0
kids = [c for c in children if getattr(c, "name", None)]
while i < len(kids):
    el = kids[i]
    name = el.name

    if name == "pre":
        # ③ 代码块 + 复制按钮（pre 原样保留）
        wrap = out.new_tag("div", **{"class": "rb-code"})
        btn = out.new_tag("button", **{"class": "rb-copy", "type": "button"})
        btn.string = "复制"
        wrap.append(btn)
        wrap.append(el.extract())
        new_main.append(wrap)

    elif name == "blockquote":
        # ④ callout：前置=note，你现在拥有=tip
        txt = el.get_text()
        kind = "tip" if "你现在拥有" in txt else "note"
        wrap = out.new_tag("div", **{"class": f"rb-callout {kind}"})
        for c in list(el.contents):
            wrap.append(c.extract())
        new_main.append(wrap)

    elif name == "p" and el.find("img") and not el.get_text(strip=True):
        # ⑦ 漫画图 + caption（合并紧随的 p.caption）
        fig = out.new_tag("figure", **{"class": "rb-comic"})
        fig.append(el.find("img").extract())
        cap = kids[i + 1] if i + 1 < len(kids) else None
        if cap is not None and cap.name == "p" and "caption" in (cap.get("class") or []):
            fc = out.new_tag("figcaption")
            for c in list(cap.contents):
                fc.append(c.extract())
            fig.append(fc)
            i += 1
        new_main.append(fig)

    elif name == "table":
        # ⑥ 对照表：加类，内容不动
        el["class"] = (el.get("class") or []) + ["rb-compare"]
        new_main.append(el.extract())

    elif name == "p":
        strong = el.find("strong")
        m = re.match(r"第\s*(\d+)\s*步", strong.get_text()) if strong else None
        if m:
            # ⑤ 步骤卡：编号 + 标题 + 该段正文（原样）
            step_no += 1
            card = out.new_tag("div", **{"class": "rb-step"})
            num = out.new_tag("div", **{"class": "rb-step-num"})
            num.string = m.group(1)
            card.append(num)
            body = out.new_tag("div")
            for c in list(el.contents):
                body.append(c.extract())
            card.append(body)
            new_main.append(card)
        else:
            new_main.append(el.extract())

    else:
        new_main.append(el.extract())
    i += 1

html = (
    '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '<title>第 17 页 · 审纠错 · 重构版</title>\n'
    f'<!-- 派生基线：manual/page-17.md @ {baseline}；md 改动不自动同步，需显式重移植 -->\n'
    '<link rel="stylesheet" href="../../assets/lesson.css">\n'
    '<link rel="stylesheet" href="../../assets/read.css">\n'
    '<link rel="stylesheet" href="rebuild.css">\n'
    '</head>\n<body>\n' + str(new_main) + '\n<script src="rebuild.js"></script>\n</body>\n</html>\n'
)
OUT.write_text(html, encoding="utf-8")
print(f"产物 {OUT.relative_to(ROOT)}（{len(html)} 字节）")
print(f"派生基线 {baseline}")
print(f"步骤卡 {step_no}、h2 锚点 {sec}")