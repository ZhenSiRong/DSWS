# 新手册构建管线（tutorial → HTML + PDF）

把 `tutorial/` 正典渲染成一本可交付的手册：**自包含 HTML + A4 PDF**。md 仍是唯一正典，产物不手改。

## 产物

```
materials/deliverable/tutorial-book/
  tutorial-book.html    # 单文件：CSS/图片全部内嵌，可直接分享
  tutorial-book.pdf     # A4：封面/目录页码/页眉页脚/章节分页（WeasyPrint，约 131 页）
  tutorial-book.pdf.meta
  README.md             # 自动生成
```

## 构建

```bash
make book          # 同时出 HTML + PDF
make book-html     # 只出 HTML
make book-pdf      # 只出 PDF
```

底层：

```bash
python3 toolbox/book/build_manual.py --html
python3 toolbox/book/build_manual.py --print-html      # 生成隐藏的 .print.html + assets
uv run --offline --with weasyprint python3 toolbox/book/render_pdf.py \
  materials/deliverable/tutorial-book/.print.html \
  materials/deliverable/tutorial-book/tutorial-book.pdf
```

- HTML：系统 `python3` + `markdown`；图片 base64 内嵌。
- PDF：WeasyPrint 只从 uv 缓存环境跑（`--offline` 可用），因此拆成 `render_pdf.py`，避免 uv 环境缺 markdown。
- 如果本机没有 weasyprint 缓存：`uv run --with weasyprint ...`（联网一次）。

## 内容口径

- 章节：封面 → 怎么用这本手册 → 目录 → 全书地图（OVERVIEW.md）→ page-00…page-23 → 封底。
- 每页仍按六段模板；图片来自 `tutorial/images/`，页首图为最新的实体/喻体版。
- 页码由 WeasyPrint `target-counter` 自动生成，不要手写。
- 改页面只改 `tutorial/page-*.md` / `OVERVIEW.md`，然后重跑 `make book`。

## 设计

- `toolbox/book/book.css`：A4 版式、封面、目录、章节、代码块、表格、图注、页眉页脚。
- 字体：Noto Serif/Sans CJK SC + Noto Sans Mono CJK SC（系统已有）。
- 自包含 HTML 是发布阅读版；PDF 是打印/评审版，两者同一份 HTML 结构。
