# PRD 三类交付物

| 目录 | 内容 | 单独打包 |
|---|---|---|
| `design-doc/` | 180 页设计图集 + 30 页摘要 | `packages/design-doc.zip` |
| `source-code/` | `system/` + Makefile + `.env.example` | `packages/source-code.zip` |
| `tutorial-doc/` | 24 章教程 md + 成书 HTML/PDF | `packages/tutorial-doc.zip` |

生成：`make deliverables`；三个目录互不依赖，可分别拷走/压缩。
