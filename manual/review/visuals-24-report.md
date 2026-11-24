# 24 页页首图全部可编辑化 · 验收报告（2026-11-24）

> 目标：按 Q1(a)/Q2(a)/Q3(a)/Q4(a)/Q6(a)/Q7(a) 把 24 页的 AI 栅格漫画全部换成**可编辑、代码原生的页首图**。
> 基线：`continue-iterate` @ `5305072`（v1.1.0）；本次提交 `b328122`（p00–p02 试点另见 `9b7fe4a`/worktree）。

## 覆盖（机器统计）

| 项 | 结果 |
| - | - |
| 页面引用 `images/page-NN-visual.webp` | **24/24** |
| `manual/images/page-*-visual.webp` | **24**（1600×1000，WebP q82，约 25KB/页） |
| `manual/designs/page-NN/index.html` | **24** |
| `manual/designs/page-NN/editor.html` | **24**（editable-design 运行时，可改字/拖拽/导出） |
| `manual/designs/data/page-NN.json` | 21（p00–p02 为试点定制版式，未走共享 data；后续可统一） |
| 旧 AI 漫画归档 | **25** → `manual/images/archive/comics-v1/` |
| 页面残留 `comic.webp` 引用 | **0** |

## 设计口径

- 白底 + 黑字/黑线 + 单橙 `#E65100`；1600×1000 固定画布；无渐变/阴影/运行时外链；字体系统 Noto Sans CJK。
- 真实对象 + 一句“在本项目里负责什么” + 一句判据/用法；页面级隐喻保留，不再给单个工具起比喻名。
- 本地品牌 SVG（`manual/designs/_shared/icons/`）+ 文字徽章；不联网、不生成 AI 图。

## 闸门

```
python3 manual/shots/audit_book.py  → 页面：24/24 通过；README 坏链：0
make audit                          → AUDIT PASS：5/5 全绿
python3 scripts/verify.py --fast    → T0 PASS（24 契约，0.08s）
make verify                         → T1 PASS（14/14 offline，26.7s）
manual/shots/render_read.py --all   → 24 页阅读版 HTML，幂等
```

## 可编辑性

- 改文案/卡片：编辑 `manual/designs/data/page-NN.json` → `python3 manual/designs/build_visuals.py NN` → 自动重出 HTML/editor/PNG/WebP；无需生图 token。
- 直接开 `manual/designs/page-NN/editor.html` 可拖拽/改字/导出；p00–p02 使用试点定制版式，其余 21 页为共享模板。
- 想统一版式/加页：见 `manual/designs/README.md`。

## 已知限制

- editable-design 的 `verify.mjs` 拆解视图在卡片/表格版式上仍有若干布局断言不通过（不影响改字/导出）；pilot 报告已记录。
- p00–p02 暂为试点定制版式，未走 `data/page-NN.json`；如需全 24 页同一模板，下一轮可迁移。
- 旧 AI 漫画只归档、不删除；v1.1.0 tag 不动，本次为 v1.2 前的工作提交。
