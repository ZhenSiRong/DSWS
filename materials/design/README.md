# DSWS 设计工作树

这个目录只放设计产物，不放运行时代码。源码基线是 `eea5e75`，与 `DSWS-colleague` 分离，避免设计文件混进同事仓库。

## 先看哪里

| 想做什么 | 打开 |
|---|---|
| 看任务拆分与验收 | `WBS.md` |
| 看图的画法与证据规范 | `STYLEGUIDE.md` |
| 查真实计数、端口、契约 | `inventory/facts.md` |
| 看 32 张图的目录 | `inventory/diagram-catalog.md` |
| 读开发教材正文 | `book/chapters/*.md` |
| 读设计文档（32 图 + 地图） | `design-doc.pdf` |
| 读精选版设计文档（30 图 / 32 页 / 一图一页） | `design-doc-30.pdf` |
| 读开发教材成书 | `book-editorial/pdf/dev-book.pdf` |
| 生成 PDF | `python3 scripts/build_book.py` + `python3 scripts/build_pdf.py` |

- 精选版用途：`design-doc-30.pdf` 从 78 页完整版精选 30 图、一图一页、共 32 页（PRD「≥30 页」），比原版更有重点。
- 选图表/重跑：32→30 的保留与删除理由见该 PDF 第 2 页「精选目录 · 32 图选 30」；重跑 `uv venv /tmp/dd30 && uv pip install --python /tmp/dd30/bin/python weasyprint && /tmp/dd30/bin/python design/scripts/build_design_doc_30.py`。

## 一条命令重建

```bash
cd design
python3 scripts/render_all.py
python3 scripts/build_book.py
/tmp/opencode/pdfvenv/bin/python scripts/build_pdf.py
/tmp/opencode/pdfvenv/bin/python scripts/check_deliverables.py
```

## 目录

```text
design/
  WBS.md
  STYLEGUIDE.md
  inventory/     事实、普查、图目录、交接
  diagrams/      01-architecture ... 06-testing
  book/          chapters、book.html、pdf
  scripts/       渲染、组装、QA
  assets/        mermaid.min.js
  tasks/         派发给 agent 的任务书
```

## 设计文档与废弃图集（2026-11-26）

- **当前设计文档**：`design-doc.pdf`（78 页，32 张图 + 读图地图）与 `design-doc-30.pdf`（32 页精选）。
- `book/pdf/dsws-design-atlas.pdf` 与 `.pre-icons.pdf` 是**废弃的教程/图集文档**，已从仓库移除，归档在 `../DSWS-archive/2026-11-25/design-atlas-deprecated/`（含 SHA256SUMS）。
- 旧 `book/` 构建脚本仍保留，仅作历史复现，不再作为设计文档交付。
