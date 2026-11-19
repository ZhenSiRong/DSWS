#!/usr/bin/env python3
"""audit_book.py —— 23 页全书结构审计（离线、只读）

检查项（每页 page-00 … page-22）：
  1. H1 形如 `# 第 N 页 · 标题`，N 与文件名一致
  2. 恰好六个 `##` 段，名称与顺序符合 L1/L2–L4 模板
     L1：这一页构建什么 / 猜一猜 / 动手 / 你应该看到 / 对账 / 自己改一下
     L2–L4：同上但末段为「拆一刀」（级末页允许「拆一刀（Lx 级考核）」）
  3. 代码围栏成对（``` 数量为偶数）
  4. 正文图片引用 `](images/xxx.png)` 全部存在
  5. 不出现用户名 / 家目录绝对路径
  6. README 的相对链接全部存在

用法：
  python3 manual/shots/audit_book.py            # 打印审计表；有 FAIL 时退出码 1
  python3 manual/shots/audit_book.py --verbose  # 额外打印每页问题明细
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MANUAL = Path(__file__).resolve().parent.parent
PAGES = [MANUAL / f"page-{i:02d}.md" for i in range(23)]

L1_LAST = "自己改一下"
L2L4_LAST = "拆一刀"
BASE_SECTIONS = ["这一页构建什么", "猜一猜", "动手", "你应该看到", "对账"]

USER_BAD = ["zhensirong", "/home/", "/Users/"]
IMG_RE = re.compile(r"\]\((images/[^)\s]+)\)")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def check_page(path: Path) -> list[str]:
    problems: list[str] = []
    if not path.exists():
        return [f"文件不存在：{path.name}"]
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    idx = int(path.stem.split("-")[1])

    # 1. H1
    if not lines or not lines[0].startswith("# "):
        problems.append("首行不是 H1")
    else:
        m = re.match(r"^# 第\s*(\d+)\s*页\s*·\s*\S", lines[0])
        if not m:
            problems.append(f"H1 格式不符：{lines[0][:40]}")
        elif int(m.group(1)) != idx:
            problems.append(f"H1 页码 {m.group(1)} ≠ 文件名 {idx}")

    # 2. 六段
    h2 = [ln[3:].strip() for ln in lines if ln.startswith("## ")]
    if idx == 0:
        # 例外：第 0 页是开课前准备，含「提前说明 / 卡住了看这里 / 重来一遍」三段，
        # 且没有「猜一猜」（与 L1 主线六段不同，属有意设计，见 SPEC 前置假设规则）。
        want0 = ["这一页构建什么", "提前说明", "动手", "你应该看到",
                 "卡住了看这里", "自己改一下", "重来一遍（回到起点）"]
        if h2 != want0:
            problems.append(f"第 0 页段名/顺序不符：{h2}")
        fences = sum(1 for ln in lines if ln.strip().startswith("```"))
        if fences % 2 != 0:
            problems.append(f"代码围栏数 {fences} 为奇数")
        for rel in IMG_RE.findall(text):
            if not (MANUAL / rel).exists():
                problems.append(f"图片缺失：{rel}")
        for bad in USER_BAD:
            if bad in text:
                problems.append(f"出现敏感串：{bad}")
        return problems
    want_last = L1_LAST if idx <= 9 else L2L4_LAST
    want = BASE_SECTIONS + [want_last]
    if len(h2) != 6:
        problems.append(f"## 段数 {len(h2)} ≠ 6：{h2}")
    else:
        for i, (got, exp) in enumerate(zip(h2, want)):
            if i == 5 and idx >= 10:
                if not got.startswith(L2L4_LAST):
                    problems.append(f"末段应为「{L2L4_LAST}…」，实际「{got}」")
            elif got != exp:
                problems.append(f"第 {i + 1} 段应为「{exp}」，实际「{got}」")

    # 3. 围栏成对
    fences = sum(1 for ln in lines if ln.strip().startswith("```"))
    if fences % 2 != 0:
        problems.append(f"代码围栏数 {fences} 为奇数")

    # 4. 图片存在
    for rel in IMG_RE.findall(text):
        if not (MANUAL / rel).exists():
            problems.append(f"图片缺失：{rel}")

    # 5. 用户名/绝对路径
    for bad in USER_BAD:
        if bad in text:
            problems.append(f"出现敏感串：{bad}")
    return problems


def check_readme() -> list[str]:
    problems: list[str] = []
    readme = MANUAL / "README.md"
    if not readme.exists():
        return ["README.md 不存在"]
    for rel in LINK_RE.findall(readme.read_text(encoding="utf-8")):
        if rel.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = (MANUAL / rel).resolve()
        if not target.exists():
            problems.append(f"README 坏链：{rel}")
    return problems


def main() -> int:
    verbose = "--verbose" in sys.argv
    failures = 0
    print(f"{'页':<10}{'行数':>5}  {'结果'}")
    print("-" * 42)
    for path in PAGES:
        problems = check_page(path)
        n = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        flag = "OK" if not problems else f"FAIL×{len(problems)}"
        print(f"{path.stem:<10}{n:>5}  {flag}")
        if problems:
            failures += 1
            if verbose:
                for p in problems:
                    print(f"    - {p}")
    readme_problems = check_readme()
    print("-" * 42)
    print(f"页面：{len(PAGES) - failures}/{len(PAGES)} 通过；README 坏链：{len(readme_problems)}")
    if readme_problems and verbose:
        for p in readme_problems:
            print(f"    - {p}")
    return 0 if failures == 0 and not readme_problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
