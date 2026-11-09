# 书稿排版风格样张 · 共用任务书

你是一位书籍设计师 + WeasyPrint 排版工程师。任务：在指定的工作树里，为《DSWS 从零到一》做一套完整样张（封面 + 目录 + `00-front` + `20-s5-s8`），并构建 PDF。**不要只换配色**；要有一套完整的版式系统。

## 工作树与构建

- 你的工作树：`design/style-lab/<id>/design`（相对仓库根目录）。
- 样张清单已设为 `chapters/00-front.md` + `chapters/20-s5-s8.md`（约 54 页）。
- 样式文件：`book/book.css`。
- 封面/目录 HTML：`scripts/build_book.py` 的 `cover_html()` 与 `build_toc()`。
- 构建：

```bash
cd design/style-lab/<id>/design
../../.venv/bin/python scripts/build_book.py
../../.venv/bin/python scripts/build_pdf.py
```

- 产物：`book/pdf/dsws-design-atlas.pdf`；复制到 `design/style-lab/<id>/dsws-style-<id>.pdf`。
- 预览：用 `pdftoppm` 导出封面 + 2 页正文到 `design/style-lab/<id>/preview-cover.png`、`preview-body.png`。

## 硬约束

- **不修改** `book/chapters/*.md` 的任何文字、数字、表格行、代码块、图链接；只改 CSS 与 `cover_html()` / `build_toc()` 的 HTML 结构。
- A4；只用本机字体：`Noto Sans CJK SC`、`Noto Serif CJK SC`、`Noto Sans Mono CJK SC`、`DejaVu Sans Mono`。
- 封面文字固定：`DSWS 从零到一`、`电商问数智能体 · 设计图集与开发手册`、`baseline eea5e75 · 2026-10-29`、`v1.0 · 教学与评审双用途`、`32 张设计图 · S0–S8 全流程`。可改字体/字号/位置/图形语言，不可改文案。
- 目录必须保留页码（`target-counter`），可点击。
- 32 张 SVG 的路径、图号、图注文字不动；可改外框、底色、尺寸、图注排版；若要重着色，必须脚本化并写进 notes。
- 不允许文字溢出、表格列挤压、代码块横向溢出、图被裁切；表格/代码在 8pt 左右仍可读。
- 不新增正文事实、不新增 ✅/🟡/⚪、不新增表格行/代码块。
- 视觉上必须与另外 5 套明显不同，不是同一模板换色。
- 构建完成后必须检查：封面、目录、章首页、正文跨页、表格、代码块、图、检查清单、复习题。

## 交付

- PDF（40–90 页）。
- `design/style-lab/<id>/style-notes.md`：概念 3 句；字体/网格/色板/组件规则；做了什么；已知限制；与另外 5 套的差异。
- 2 张 PNG 预览：`preview-cover.png`、`preview-body.png`。
- 最后用 `worker_done` 三句话汇报：做了什么、PDF 路径、最大风险。
