# 项目地图 · 四类存放

> 目标：教程内容、制作教程的工具、教程所教的示例系统、设计/研究资料**分开存放**。
> 旧路径（`manual/`、`backend/`、`scripts/`…）在仓库根保留了**兼容软链**，所以旧命令/旧文档还能跑；
> **新内容请写进下面四个真实目录**，软链只是过渡层。

## 1. `tutorial/` · 教程正典

学生读的内容：页面、阅读版、图片、课程表、城市坐标、验收口径。

```
tutorial/
  page-00.md … page-23.md   # 24 页正文（唯一正典）
  read/                     # render_read 派生的阅读版 HTML
  images/                   # 页内截图、图表、页首图 WebP、archive/ 旧漫画
  curriculum/ city/ map/ completeness/ maturity/ aon/ appendix/
  SPEC.md TRAPS.md ACCEPTANCE.md OVERVIEW.md README.md
  designs -> ../toolbox/page-visuals   # 兼容旧链接
  shots   -> ../toolbox/shots
  verify  -> ../toolbox/verify
  review  -> ../materials/review
```

## 2. `toolbox/` · 制作教程的工具

不直接给学生看，但生成/校验教程的流水线。

```
toolbox/
  page-visuals/   # 页首图：data/page-NN.json、index.html、editor.html、art/、build_visuals.py
  shots/          # 截图/图表/渲染脚本 + 审计 audit_book.py + render_read.py
  verify/         # T0/T1 契约：contracts/page-NN.yaml、README
  book/           # 新手册构建管线：tutorial → 自包含 HTML + A4 PDF
  scripts/        # 验收、docker、lab、task、设计服务等工具脚本
  workflows/      # 任务台账 ledger.yaml / reviews / 甘特
```

## 3. `system/` · 教程所教的示例系统

教程里真正被搭起来、被问数、被部署的那套「电商问数」代码。

```
system/
  backend/ frontend/ contracts/ fixtures/ docker/ deploy/
  compose.yaml compose.lab-ui.yaml
  lab/ eval/
```

## 4. `materials/` · 设计 / 研究 / 证据

设计评审、研究记录、发布物、证据截图、外部资料。

```
materials/
  design/          # 设计文档、图表、风格实验、PDF
  docs/            # setup/验收/verify 说明、ADR
  humen-desicions/ # 决策记录（D44/D50…）
  review/          # 评审证据、截图、replay 素材
  deliverable/     # v2 演示与交付物
  packages/ pilot/ assets/ error-proofread/
```

## 根目录

`README.md`（总入口）、`AGENTS.md`（导航）、`GLOSSARY.md`（术语）、`Makefile`（命令入口）、
`PROJECT-MAP.md`（本文件）、`.github/`、`.githooks/`、`.env.example`。

## 兼容软链（过渡，别在新代码里用）

| 旧路径 | 真实位置 |
|---|---|
| `manual/` | `tutorial/` |
| `backend/` `frontend/` `contracts/` `fixtures/` `docker/` `deploy/` `eval/` | `system/…` |
| `scripts/` | `toolbox/scripts/` |
| `design/` `docs/` `humen-desicions/` `packages/` `deliverable/` | `materials/…` |
| `compose.yaml` `compose.lab-ui.yaml` | `system/…` |
| `workflows/` | `toolbox/workflows/` |

> 生成物/缓存/发布归档不进仓库：已移到仓库外 `../DSWS-archive/2026-11-25/`（见归档 README）。
