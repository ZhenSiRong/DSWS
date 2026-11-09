全部跑通，且结果与 PDF 完全一致。下面是交付报告。

---

# 学生验证任务 01 · S5 离线安全门禁 — 验证报告

**执行日期**：2026-11-09（周一）
**操作指南依据**：`/tmp/opencode/student-pdf/dsws-design-editorial.pdf` 第三部分「1. S5 · 安全边界」(PDF 页脚编号 69–78)
**唯一可写目录**：`/home/zhensirong/.local/share/opencode/worktree/b313e3/student-pdf-validation`

> 约束遵守：未读 `design/book/chapters/`、`design/book-editorial/`；未联网、未 `git commit`、未改仓库外文件。

## 步骤 1 · 找到并执行 S5 离线验收命令

- **PDF 原文命令**（页脚 p.77，Makefile `stage5`）：`make stage5`，它依次做四件事——
  `cd backend && uv run python -m app.scripts.security --check`
  `cd backend && uv run python -m app.scripts.security --corpus`
  `cd backend && uv run pytest -q tests/security`
  `cd backend && uv run pytest -q`
- **期望**：注入语料 36/36 全拒、零误杀 11/11 全放、S4 基线 8/8 通过，安全测试与全量测试全绿，末尾打印 `S5 PASS`。
- **实际输出（关键行）**：
  - `注入语料：36/36 条按预期拒绝`
  - `零误杀语料：11/11 条放行`
  - `S4 基线：8/8 条 SQL 通过策略`
  - `tests/security: 179 passed, 2 skipped`
  - `全部后端测试: 812 passed, 30 skipped`
  - 末尾 `S5 PASS`，Makefile 退出码 0。

✅ 与 PDF 给出的本机判据（36/36、11/11、8/8）逐字一致。

## 步骤 2 · 复现两条应被拒绝的 SQL

都用 PDF 页脚 p.78 给出的逐条复现形式：`uv run python -m app.scripts.security --policy "..."`

| 用例 | 命令关键参数 | 实际判定 | 原因码 | PDF 对照 |
|---|---|---|---|---|
| 多语句 | `SELECT 1 AS a FROM fact_order LIMIT 1; DROP TABLE fact_order` | 拒绝 | `SQL_MULTIPLE_STATEMENTS`（`实际解析出 2 条`） | 表 3-2 `multi_statement_drop` 一致 |
| 集合运算 | `SELECT order_amount FROM fact_order UNION SELECT customer_id FROM dim_customer` | 拒绝 | `SQL_FORBIDDEN_CONSTRUCT`（出现集合运算 Union） | 表 3-2 `union_exfiltration` 一致 |

✅ 两条均按预期拒绝，原因码与 PDF 表 3-2 精确匹配。

## 步骤 3 · 验证正常查询放行并确认自动补 LIMIT

- **命令**：`--policy "SELECT SUM(fact_order.order_amount) AS gmv FROM fact_order"`
- **期望**（PDF 例题）：放行，策略自动补 `LIMIT 1000`，最终可执行文本带 `LIMIT 1000`。
- **实际输出（关键行）**：
  - `判定：放行（自动 LIMIT = 1000）`
  - `可执行的 SQL：SELECT SUM(fact_order.order_amount) AS gmv FROM fact_order LIMIT 1000`

✅ 正常聚合查询被放行，自动补上的 LIMIT = **1000**，与 PDF「1.5 输出 / 例题」一致。

## 卡点 / 信息缺口

- **stage5-live 未执行（预期内，非阻塞）**：PDF 把只读账号验收（`--provision-ro-account` / `--verify-ro-account` / `--demo`）拆到 `make stage5-live`，明确需要 MySQL + 环境变量 `REBUILD_DW_RO_PASSWORD`，且本工作树 PDF 标为「未验证」。本任务只要求**离线**门禁，故未做；若要补需先起 MySQL 并注入密码。
- **PDF 表述清晰度**：S5 章节页脚编号 69–78，命令清单在 p.77、`--policy` 逐条例在 p.78，无歧义；表 3-2 与正文对多语句/集合运算的原因码定义一致，未发现矛盾页。
- **提取工具耗时**：`pdftotext` 对这本 6.9MB 的 PDF 默认超时，需放宽超时；属工具问题，不影响 PDF 内容本身。

## 是否独立完成

**是**。仅以 PDF 为操作指南，命令与预期全部来自 PDF，本机执行并如实记录输出；未参考任何答案/审计目录。

## 置信度

**95 / 100**。离线门禁四类判据（36/36、11/11、8/8、安全+全量测试全绿）与两条指定拒绝 SQL、一条放行查询，均逐字命中 PDF，证据充分。扣 5 分只因 stage5-live（需 MySQL）按任务范围未实跑，不算本步证明项。

## 用到的、但 PDF 里没写的隐含知识

1. **`uv run --offline` 离线执行**：PDF 只说「uv 按锁文件准备环境再执行」，未提断网时如何满足「不要联网」约束。实测本机 `~/.cache/uv` 已有 `uv.lock` 对应的 62 个包缓存，首次 `uv run --offline` 自动建 `.venv`（约 38ms）并直接运行，无需联网。这是离线跑通 `make stage5` 的前提。
2. **首次 `uv run` 自动从 `uv.lock`+缓存建环境**：不必预先 `uv sync`，命令自带建环境能力，但依赖缓存命中；若缓存缺失则会触发联网（被约束禁止），因此必须加 `--offline` 显式锁死。
3. **`make stage5` 会顺带跑全量后端测试（812 条，约 27s）**：PDF 列出了 4 条子命令（含末尾 `uv run pytest -q`），但易误以为只跑安全门禁；实际耗时主要来自全量测试，属预期。

---

需要我接着补做 `make stage5-live`（需先确认 MySQL 是否已起、并有 `REBUILD_DW_RO_PASSWORD`）吗？这一步 PDF 本身标为未验证，不在本次离线任务范围内。
