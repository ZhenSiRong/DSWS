# Q&A 决策记录（grill 回合）

> 本文件记录"一问一答"回合里的问题与决定，供回看"当时为什么这么定"。
> 长期规范仍进 [`09-ablation-course.md`](09-ablation-course.md) 的 **D 系列**；索引进 [`DECISIONS.md`](DECISIONS.md)。本文件只做逐轮索引，不替代 D 编号。
> 最后更新：2026-11-21。

## 规则

1. 一轮 grill = 一节；记录「日期 / 轮次 / 问题 / 用户选择 / 落地（文件或 commit）」。
2. 影响长期口径的，升格为 D 号并在此标注 `→ Dxx`；未升格的只在本文件。
3. 未拍板的事项写「待定」，不写成已决定。

## R1 · retro：经验沉淀（2026-11-19）

| 问题 | 决定 |
|---|---|
| 沉淀载体 | 仓库 `AGENTS.md`（导航指针）+ `manual/TRAPS.md`（陷阱表）+ 全局 skill `tutorial-production` |
| 自动化护栏 | `uv run --frozen` + `make audit` + `.githooks/pre-commit` |
| 重放 | 固定 `REPLAY-TEMPLATE.md`（六段 + 8 类必查） |
| 截图工具 | 抽公共 `render_page_shots.py` 框架（旧 4 套退役） |

落地：commit `4b2a1f2`、`a2633cb`；skill `~/.agents/skills/tutorial-production/`。

## R2 · Orca 工具链与免费额度 agent（2026-11-19/20）

| 问题 | 决定 |
|---|---|
| 用途 | 跨模型独立评审用 Orca worker；同构重复用内置 subagent |
| 默认 agent | `opencode2`（免费模型必须是 `opencode/*-free` 类；其默认模型已修为 `opencode/deepseek-v4.1-flash-free`） |
| 协调 | `worker-start` 监督模式（可追问、可回收） |
| 分工规则写哪 | `AGENTS.md` 派单行 + skill `dispatch-rules.md` |

落地：commit `4b2a1f2`（steering）、`fd8f992`（p17 真模型探针证据）；`orca-review-01/02`。

## R3 · PRD 功能清单怎么"突出"（2026-11-20）

| 问题 | 决定 |
|---|---|
| 突出重点的形式 | **不在 24 页正文加 PRD 标签/不重排**；只在 README 覆盖矩阵 + OVERVIEW 答辩一页露出（Q1 C） |
| LangGraph 缺口 | 在 p21「对账」后加 **「深入探讨：12 个节点就是一张 LangGraph 图」**（H3，不破六段） |
| 自校验/自纠错 | README 矩阵标 **★★★**（书里最深） |
| 前端技术栈 | p23 补事实：成熟版 React 19 + Tailwind 3.4.17；教学版 4.3.4 |
| 设计文档数量 | 从 78 页原版精选 **30 图一图一页 → `design/design-doc-30.pdf`（32 页）** |
| 矩阵放哪 | README 表 + OVERVIEW 答辩一页（Q6 A） |

落地：commit `fe4c3f0`、`e92be50`；[`manual/README.md`](../manual/README.md) PRD 矩阵、[`manual/OVERVIEW.md`](../manual/OVERVIEW.md) 答辩一页、[`manual/page-21.md`](../manual/page-21.md) 深入探讨。

## R4 · 23 → 24 页 + 城市图/AON（2026-11-20）→ D50

| 问题 | 决定 |
|---|---|
| 新页位置/编号 | 末尾追加 `page-23.md`（第 23 页），**不重编号**（Q1 a） |
| 级归属 | **L5「装」体验层，1 页**；配比 10+4+4+5+1=24（Q2 a） |
| 判据 | `make docker-up` → 8080 问一句出 `41099.5`；`npm test` 40 passed；拆一刀换 17 行 HTML 仍出 `41099.5`（Q3 a） |
| 拆一刀 | 前端换回第 9 页 17 行 HTML（Q4 a） |
| 口径同步 | 一次性全仓翻修（audit、README、ACCEPTANCE、AGENTS、OVERVIEW、D44→D50）（Q5 a） |
| 城市图 | 旧 L1/23 页图冻结；`data-24.json` + `city-map-24.png`（Q6 a） |
| AON | L2–L5 **合并成一张**（18 节点/330 分钟） |

落地：commit `9e2fb3f`；[`manual/page-23.md`](../manual/page-23.md)、[`humen-desicions/09-ablation-course.md`](09-ablation-course.md) D50。

## R5 · 装修对象：成熟版，不是重建版（2026-11-20/21）→ D51

| 问题 | 决定 |
|---|---|
| 装修用什么前端 | **成熟版原版 `shopkeeper-agent`**（`deliverable/v2/original-frontend/`，React 19 + Tailwind 3.4.17，dist 现成），不是教学版重建前端 |
| 教学版定位 | **脚手架/对照**（compose 默认 8080，带 40 条协议测试；成熟版不带测试） |
| 演示方式 | 8088 起成熟版（nginx 挂 dist + 原版 nginx.conf，进 compose 网络）；8080 教学版对照 |
| 拆一刀 | 8088 成熟版换回 17 行 HTML，同一问题仍 `41099.5` |

落地：commit `47e9b6f`、`7891ff1`；[`manual/review/p23-mature-runbook.md`](../manual/review/p23-mature-runbook.md)、[`page-23-mature.png`](../manual/images/page-23-mature.png)。

## R6 · 执行轨迹可视化与归属（2026-11-21）→ D52

| 问题 | 决定 |
|---|---|
| 做哪个 | **A（执行轨迹）与 C（pdb 单步）都试**；最终**选 A**（真栈 + 真 LLM + 真前端） |
| A 的左栏 | **真前端界面**（成熟版真截图），不是节点时间轴 |
| A 的节奏 | 18–25s/循环；关键状态定格 2.4–3.2s；底部标"时间轴已压缩，非实速" |
| A 的归属 | **移到 p23**（改名 `page-23-exec-trace.*`），图注落"装修不换承重墙：同一句问题仍走同一条执行链"（Q1 A、Q4 a） |
| p17 怎么办 | **不在 p17 放这张图**；p17 要"让学习者学会自己操作工具去录证据"（方向待定 → 见「待办」） |
| p21 是否指过去 | 不加（Q5） |
| 图放 p23 哪个位置 | **用户自己处理**（Q3） |

落地：commit `3742da2`；资产 [`page-23-exec-trace.gif`](../manual/images/page-23-exec-trace.gif)、[`page-23-exec-trace.png`](../manual/images/page-23-exec-trace.png)；证据 [`exec-trace-v2/`](../manual/review/exec-trace-v2/)、[`exec-trace-runbook.md`](../manual/review/exec-trace-runbook.md)。

## 待定

- **p17「学习者自录证据」方案**（R6-Q2）：初步方向 = 三层脚手架
  1. 一条命令自己录：`curl -sN … /api/query | tee /tmp/correction.sse`，用 `grep` 对 `validate_sql:error → correct_sql:success → validate_sql:success`；
  2. 自己改契约触发/关闭：`contracts/errors.yaml` 的 `max_attempts` 改 0 → `correct_sql` 跳过 → 观察差异 → 还原；
  3. 工具化附录：`record_sse` / pdb / `sitecustomize + settrace` 三种录制法 + 一条命令渲染对照 GIF（复用 `render_pdb_step.py` / `render_exec_trace.py`）。
  待用户确认后再进 p17/附录，并升格为 D 号。

## 相关文件

- 长期决策：[`09-ablation-course.md`](09-ablation-course.md)（D 系列，最新 D52）
- 索引：[`DECISIONS.md`](DECISIONS.md)
- 教材验收：[`manual/ACCEPTANCE.md`](../manual/ACCEPTANCE.md)
