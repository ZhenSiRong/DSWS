# T1 · 软件普查 + 架构图（qoder）

## 角色与工作树

你是 DSWS 重建项目的设计图集作者之一。工作树：

```text
/home/zhensirong/VM-Share/DSWS-design
```

先读：

1. `design/WBS.md`
2. `design/STYLEGUIDE.md`
3. `design/inventory/facts.md`
4. `README.md`
5. `docs/SETUP-FROM-SCRATCH.md` 的目录与 S0–S7 章节
6. `backend/app/`、`frontend/src/`、`contracts/`

## 目标

产出「软件普查 + 架构角度」的 6 张图，以及一份可复核的软件普查。

## 必须产出

### A. 软件普查

`design/inventory/software-census.md`，至少包含：

- 代码规模：后端 Python 文件数、测试文件数、前端源文件数、契约文件数。
- 分层清单：契约层、构建层（S2）、召回层（S3）、生成层（S4）、安全层（S5）、失败通道（S6）、前端（S7）、场景/夹具。
- 每个模块：路径、职责、关键入口、被谁调用、构建时/查询时。
- 5 个 HTTP 端点、12 个步骤、16 个错误码、3 种 SSE 事件。
- 5 张表 / 24 列 / 6 指标 / 9 条列—指标关系。
- 端口表：8100 / 5273 / 8080 / 3306 / 9200 / 6333。
- 测试：45 个后端测试文件；README 声称 782 passed（标 🟡，本机未跑）。
- 一张「模块 → 文件 → 证据」表。

### B. 六张架构图

目录：`design/diagrams/01-architecture/`

| 编号 | 文件 | 内容要求 |
|---|---|---|
| 01 | `01-c4-context.mmd` | C4-L1：用户、浏览器、DSWS、MySQL/ES/Qdrant、LLM（可选）、旧系统（只读夹具） |
| 02 | `02-c4-container.mmd` | C4-L2：frontend、FastAPI、AgentRunner、recall、generate、security、build CLI、三存储、init |
| 03 | `03-backend-modules.dot` | Graphviz：`backend/app/` 模块依赖，边标「import/调用」，标出构建时与查询时 |
| 04 | `04-frontend-tree.mmd` | `App.tsx` → `Composer` / `StepRail` / `ResultTable` / `ErrorCard` / `PseudoErrorCard`，以及 `lib/api`、`lib/sse`、`lib/result` |
| 05 | `05-stage-evolution.mmd` | S0→S8 演进：每阶段新增的「不确定性」与「可停点」 |
| 06 | `06-build-vs-query.mmd` | 构建时 vs 查询时：S2 CLI 退出后，S3/S4/S5 直接读三存储 |

每张图配同名 `.md` 说明，按 `STYLEGUIDE.md` §7 模板：一句话、回答什么问题、图例、关键元素、证据、边界。

### C. 目录草稿

`design/inventory/catalog-architecture.md`：列出 01–06 的编号、标题、问题、源文件、SVG、证据、状态（✅/🟡/⚪）。

### D. 交接

`design/inventory/handoff-T1.md`：产出清单、渲染命令、未决问题、你实际读过的文件。

## 约束

- 只写 `design/inventory/` 与 `design/diagrams/01-architecture/` 下的文件。
- 不要改 `backend/`、`frontend/`、`contracts/`、`docs/`、`Makefile`。
- 图源必须是 `.mmd` 或 `.dot`；不要手写 SVG。
- 计数必须与 `facts.md` 一致；不确定的标 🟡 或 ⚪。
- Mermaid 不要用 `htmlLabels`（渲染脚本已关）；节点文字 ≤18 汉字。
- 每张图必须能回答一个具体问题，不要画「万物互联」装饰图。

## 验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/01-architecture/*.svg
```

6 个 SVG 全部生成；`software-census.md` 里的每个计数都能在仓库里找到出处。
