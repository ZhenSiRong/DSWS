# 文档类型与放置规则

> 类型：开发（过程）文档。用来防止“计划写进教材”“设计只留在聊天里”。

## 1. 两类文档的分工

| 维度 | 设计文档 | 开发（过程）文档 |
|---|---|---|
| 回答 | 系统**是什么**、为什么这样设计 | 我们**怎么做的**、做到哪一步 |
| 读者 | 学习者、验收人、后续维护者 | 协作者、复盘者、未来的自己 |
| 生命周期 | 长期稳定，随版本演进 | 短期有效，随任务结束归档 |
| 判断标准 | 事实可回溯、结论可复现 | 决策有依据、过程有证据 |
| 典型内容 | 架构、契约、数据模型、接口、图、教程章节 | 计划、WBS、决策记录、审计、评测、验证报告 |
| 不应该包含 | “今晚谁做哪一步”“临时配额” | “系统最终长什么样”的权威定义 |

## 2. 本项目的放置位置

### 设计文档

| 内容 | 位置 |
|---|---|
| 教材正文（章节） | `materials/design/book/chapters/` |
| 图源与图注 | `materials/design/diagrams/`（`.mmd`/`.dot`/`.md`/`.svg`） |
| 契约（步骤/错误/策略/Schema/SSE） | `system/contracts/` |
| 设计文档成书 | `materials/design/design-doc.pdf`（32 图 + 读图地图） |
| 开发教材成书 | `materials/design/book-editorial/pdf/dev-book.pdf` |
| 教材样式与构建 | `materials/design/book-editorial/`、`materials/design/style-lab/` |

### 开发（过程）文档

| 内容 | 位置 |
|---|---|
| 决策、计划、WBS、分工 | `materials/humen-desicions/` |
| 学生验证记录、capstone 报告 | `materials/pilot/` |
| 评测数据、基线、探针与报告 | `system/eval/` |
| 部署/演示证据 | `materials/deliverable/v2/evidence/` |
| PRD 与验收对照 | `prd.md`、`materials/deliverable/v2/PRD-差异补齐.md` |

### 交付物

| 内容 | 位置 |
|---|---|
| 视频、GIF、截图 | `materials/deliverable/v2/` |
| 抽帧、证据 | `materials/deliverable/v2/evidence/` |

## 3. 三条硬规则

1. **教材只放稳定结论**：不放计划、配额、临时分工；所有事实必须能回到 `file:line` 或命令输出。
2. **决策必须落盘**：聊天里达成的取舍，当天写进 `materials/humen-desicions/DECISIONS.md`，否则视为未决定。
3. **过程文档可以引用设计文档，反之不行**：设计文档不引用“我们今晚怎么排期”。

## 4. 本次新增文档

| 文件 | 类型 | 内容 |
|---|---|---|
| `materials/humen-desicions/07-figure-comprehension-plan.md` | 过程 | 32 张图的优化计划、判据、预算 |
| `materials/humen-desicions/08-doc-placement.md` | 过程 | 本文：文档分类与放置规则 |
| `materials/design/diagrams/reading-paths.yaml` | 设计 | 每张图的“回答什么 / 1→2→3 / 失败” |
| `materials/design/scripts/add_reading_band.py` | 设计工具 | 给 SVG 注入读图带 |
| `materials/pilot/figure-audit.md` | 过程 | 盲测与抽检结果 |
