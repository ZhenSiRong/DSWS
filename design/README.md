# DSWS 设计工作树

这个目录只放设计产物，不放运行时代码。源码基线是 `eea5e75`，与 `DSWS-colleague` 分离，避免设计文件混进同事仓库。

## 先看哪里

| 想做什么 | 打开 |
|---|---|
| 看任务拆分与验收 | `WBS.md` |
| 看图的画法与证据规范 | `STYLEGUIDE.md` |
| 查真实计数、端口、契约 | `inventory/facts.md` |
| 看 32 张图的目录 | `inventory/diagram-catalog.md` |
| 读手册正文 | `book/chapters/*.md` |
| 生成 PDF | `python3 scripts/build_book.py` + `python3 scripts/build_pdf.py` |

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
