# DSWS 设计图集 + 从零到一手册 · WBS

> 基线：`eea5e75`（2026-10-29 拉取）
> 工作树：`/home/zhensirong/VM-Share/DSWS-design`（分支 `design/atlas`）
> 原则：设计产物与源码隔离；所有结论必须能指到文件、命令输出或契约。

## 0. 最终交付物

| 交付物 | 路径 | 验收 |
|---|---|---|
| 设计图集 | `design/diagrams/**` | 至少 24 张图，覆盖架构、运行时、数据、安全、部署、测试六个角度 |
| 图集目录 | `design/inventory/diagram-catalog.md` | 每张图有编号、问题、证据、源文件、渲染文件 |
| 软件普查 | `design/inventory/software-census.md` | 模块、入口、端口、契约、计数、测试数全部有出处 |
| 开发手册 | `design/book/chapters/**` | S0–S8 每阶段：问题→实体→输入→动作→输出→验收→故障→证据 |
| 书稿 | `design/book/book.md` | 合并后的单一 Markdown 源 |
| PDF | `design/book/pdf/dsws-design-atlas.pdf` | ≥30 页，A4，有封面、目录、页码、图目录、书签 |
| 渲染脚本 | `design/scripts/**` | 一条命令重建全部 SVG 与 PDF |

## 1. 任务分解

### Wave 1 · 事实与图（可并行）

| ID | 任务 | 负责 | 输出 | 依赖 |
|---|---|---|---|---|
| T1 | 软件普查 + 架构图 | qoder | `inventory/software-census.md`、`diagrams/01-architecture/*` | 无 |
| T2 | 运行时/时序图 | codebuddy | `diagrams/02-runtime/*` | 无 |
| T3 | 数据/安全图 | opencode | `diagrams/03-data/*`、`diagrams/04-security/*` | 无 |
| T4 | 部署/测试图 | qoder | `diagrams/05-deployment/*`、`diagrams/06-testing/*` | 无 |

### Wave 2 · 手册正文（依赖 T1–T4 的图号，但可先写文字）

| ID | 任务 | 负责 | 输出 | 依赖 |
|---|---|---|---|---|
| T5 | 手册 S0–S4 | opencode | `book/chapters/part1-s0-s4.md` | T1 |
| T6 | 手册 S5–S8 | codebuddy | `book/chapters/part2-s5-s8.md` | T3 |
| T7 | 手册前置/后置 | qoder | `book/chapters/part0-*.md`、`part3-*.md` | T1–T4 |

### Wave 3 · 组装与验收（协调者亲自做）

| ID | 任务 | 负责 | 输出 | 依赖 |
|---|---|---|---|---|
| T8 | 合并书稿、生成 PDF、QA | 协调者 | `book/book.md`、`book/pdf/*.pdf`、`inventory/qa-report.md` | T5–T7 |

## 2. 图目录（目标 30 张）

### 01 架构（6）
1. C4-L1 系统上下文
2. C4-L2 容器图
3. 后端模块依赖图
4. 前端组件树
5. 阶段演进图 S0–S8
6. 构建时 vs 查询时

### 02 运行时（7）
7. 端到端请求生命周期
8. S2 构建流水线时序
9. S3 召回流水线时序
10. S4 生成 SQL 流水线
11. S5 安全校验与执行
12. S6 校正闭环状态机
13. S7 SSE 事件序列

### 03 数据（6）
14. 数仓 ER 图
15. 契约模型（表/列/指标/值域）
16. 三存储知识布局
17. S2 数据 lineage
18. Meta 表结构
19. 值域分类决策树

### 04 安全（5）
20. 信任边界与攻击面
21. 五层防御纵深
22. SQL 策略判定流程
23. 只读账号权限模型
24. 错误码分类与 UI 映射

### 05 部署（4）
25. Docker Compose 拓扑
26. 端口与网络暴露面
27. 启动顺序与健康检查
28. 旧系统 / rebuild 隔离

### 06 测试（4）
29. 测试金字塔与阶段门禁
30. S0–S8 验收链路
31. 失败注入矩阵
32. 证据台账（已验证/未验证）

> 数量目标 32；若某图合并，目录中必须说明合并到哪张。

## 3. 每个任务的通用约束

- 只写自己目录下的文件；不要改 `backend/`、`frontend/`、`contracts/`、`docs/`。
- 图源必须是文本：Mermaid `.mmd` 或 Graphviz `.dot`；渲染产物 `.svg` 同目录。
- 每张图配一个 `.md` 说明：回答什么问题、关键元素、证据文件、已知边界。
- 中文标题，英文标识符保留原文；颜色遵循 `STYLEGUIDE.md`。
- 不允许编造计数、表名、错误码。拿不到的证据标 `未验证`。
- 完成后在 `design/inventory/handoff-<task>.md` 写：产出清单、命令、未决问题。

## 4. 验收命令

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py          # 渲染全部 mermaid + graphviz
python3 scripts/build_book.py          # 合并 Markdown -> HTML
python3 scripts/build_pdf.py           # HTML -> PDF
python3 scripts/check_deliverables.py  # 页数、图数、断链、占位符
```
