# 学生验证 01 · S5 离线安全门禁

## 1. 配置

| 项 | 值 |
|---|---|
| 日期 | 2026-11-09 |
| 学生 agent | CodeBuddy |
| 模型 | `hy3` |
| 思考强度 | `low` |
| 最大轮次 | 40 |
| 工作目录 | `/home/zhensirong/.local/share/opencode/worktree/b313e3/student-pdf-validation` |
| 唯一可读指南 | `/tmp/opencode/student-pdf/dsws-design-editorial.pdf` |
| PDF SHA256 | `afa9d43844d28ee3bdd324b2727a5158c213557c87d390ec83407c6566a228b4` |
| 任务书 | `student-task-01.md` |
| 原始输出 | `report.md` |

隔离措施：PDF 先复制到 `/tmp/opencode/student-pdf/`，只把该目录通过 `--add-dir` 授权；
学生接触不到 `design/book/chapters/` 与 `design/book-editorial/`。任务书明确禁止读审计目录、
禁止 commit、禁止联网。

## 2. 结果

学生**独立完成**，置信度自评 95/100。

- `make stage5`：36/36 拒绝、11/11 放行、8/8 基线通过、`S5 PASS`
- 多语句 `SELECT 1 ...; DROP TABLE fact_order` → `SQL_MULTIPLE_STATEMENTS`
- 集合运算 `UNION ...` → `SQL_FORBIDDEN_CONSTRUCT`
- 正常聚合 `SUM(...) AS gmv` → 放行，自动补 `LIMIT 1000`

## 3. 独立复核（协调方执行，不采信学生自述）

在同一个 worktree 重跑 `make stage5`，结果与学生报告逐条一致：

```
注入语料：36/36 条按预期拒绝
零误杀语料：11/11 条放行
S4 基线：8/8 条 SQL 通过策略
179 passed, 2 skipped
812 passed, 30 skipped
S5 PASS
```

同时核对了学生引用的 PDF 原文（p.77 的四条子命令）与仓库 `Makefile` 的 `stage5` 目标，
两处一致；worktree `git status` 干净，没有 commit 或越界改动。

## 4. 归因分类

| 发现 | 归类 | 处理 |
|---|---|---|
| 学生需自行补 `uv run --offline` 才能在断网约束下跑通 | 测试环境约束（非教材缺陷） | 教材无需改；若面向离线读者，可在 1.6 补一句「无网络时用 `uv run --offline`，依赖需已在 `uv.lock` 缓存」 |
| `pdftotext` 处理 6.9MB PDF 默认超时 | 学生侧工具 | 不影响教材 |
| `stage5-live` 需 MySQL 与 `REBUILD_DW_RO_PASSWORD` | 教材已声明，属预期 | 本任务只测离线门禁，未执行 |

结论：**S5 章节作为操作指南是合格的**——低思考强度、PDF-only 的学生能按图索骥完成，
不需要作者口头补充。教材侧无阻断性缺陷。

## 5. 备注

- 任务只覆盖离线门禁；`stage5-live`（只读账号真的写不了）仍未由学生验证。
- 尚未跑 `medium` 对照组；如需确认「低强度也能过、不是偶然」，再跑一次 medium 复测。
