# PRD 三类交付物

| 目录 | 内容 | 单独打包 |
|---|---|---|
| `design-doc/` | 决策生长版设计文档（A 类 5 链渐进稿，≥30 页） | `deliverables/packages/design-doc.zip` |
| `source-code/` | `system/` + Makefile + `.env.example` | `deliverables/packages/source-code.zip` |
| `tutorial-doc/` | 24 章教程 md + 成书 HTML/PDF | `deliverables/packages/tutorial-doc.zip` |

生成：`make deliverables`；三个目录互不依赖，可分别拷走/压缩。
