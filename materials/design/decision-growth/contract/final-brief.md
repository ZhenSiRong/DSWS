# 契约链 · Final brief（CP2）

> 教学编撰声明（D57）：生长时间线是教学重构，非 commit 历史；结论均由代码/契约/真跑证据锚定。

## 结论（3 句）

契约的价值不在「少写一份配置」，在「改一处，所有消费者必须一起被惊动」：契约 → BuildPlan → Meta/ES/Qdrant → 文档/门禁，三存储与文档全从同一棵契约树派生。值域分类（enum/低基数 open 进 ES，range/主键/外键/度量不写）解决了「所有值都往 ES 写」的噪声问题。门禁只读 DDL 快照不读运行库——这是必须写进设计的假绿边界：换数据要换三处（运行库、快照、期望值）。

## 产物链接

- 渐进稿：[`spread.png`](spread.png)（固定画布 1540×1120 ×2（跨页 3200×1170）；本目录 spread.* 由视觉步骤产出，产出后此链接直接生效）
- 机器可读 claims：[`claims.yaml`](claims.yaml)；人读版：[`claims.md`](claims.md)；CP1：[`storyboard.md`](storyboard.md)

## 已跑命令 / 结果

| 命令 | 结果 | 何时 |
|---|---|---|
| `(cd system/backend && .venv/bin/python -m app.schema_contract --check)` | 三段全 PASS（契约↔DDL/数据、负向夹具、文档新鲜度），S1 PASS | 本轮实跑 |
| `pytest -q tests/test_s0_contract.py tests/test_s1_schema_contract.py` | 59 passed | 本轮实跑 |
| `(cd system/backend && .venv/bin/python -m app.build_meta_knowledge --dry-run)` | 5 表/24 列/6 指标/9 列—指标；ES 76；Qdrant 98+22；0 writes | 本轮实跑 |
| `expected_fact_rows 115→410 → --check` | `[DATASET_ROW_COUNT] FAIL: 1`，改回才绿 | 本轮（2026-11-27）记录 + page-10 拆一刀实测 |
| `make stage2`（source export-docker-env.sh 后，fresh 真写三存储） | S2 VERIFY PASS（fresh 计数与 dry-run 一致）+ IDEMPOTENT NOOP 0 writes | 真栈补验 2026-11-27 |

## 已知未知

- S2 fresh 真写三存储已实证（2026-11-27 真栈 `make stage2`）：S2 VERIFY PASS——fresh 写入与 dry-run 计数一致（5/24/6/9、ES 76、Qdrant 98+22），且 IDEMPOTENT NOOP 0 writes → C7 `verified`。
- 值域同步阈值 `max_value_docs=1000` 是低基数阈值（不同取值 ≤1000 的列才把完整值同步 ES）[当前值]，不是设计原则（`build/config.py:83`）。
- 假绿边界：门禁核对的是 `fixtures/dw.sql` 115 行快照，不是运行库——换真数据必须三处一起换（page-10 已实测这个错位）。
- C3（值域分类）目前 `inferred`（plan.py 代码可证、未单独消融实跑）。

## 学生可读性检查（三项复述答案）

1. **N / 参数是什么**：5 表 / 24 列 / 6 指标 / 9 列—指标；ES 76 条值；Qdrant 98 列点 + 22 指标点；契约期望 115 行 fact_order（真数据是 410 行）；值域低基数阈值 1000 [当前值]（不同取值 ≤1000 的列才把完整值同步 ES）。
2. **哪些错误不能重试（不能靠重跑/自动校正解决）**：契约漂移类失败——`DATASET_ROW_COUNT`、`METRIC_VALUE_MISMATCH` 这类门禁红不会自愈，只能人改契约或快照，且三处（运行库、DDL 快照、期望值）必须一起换；把契约改坏（page-11 拆一刀）是当面 StopIteration，不是可重试错误。
3. **拆掉什么会红**：`expected_fact_rows` 115→410 → `FAIL: 1`；GMV `expected_value` 改错 → `METRIC_VALUE_MISMATCH` 多一条红；契约 `values` 删掉「华北」→ lab 的 `build_sql` 抛 StopIteration（page-11 拆一刀实测）；手改契约不跑 `--write-doc` → 文档新鲜度红。

## 后续动作

- 有：C7 已闭环（2026-11-27 真栈 `make stage2` S2 VERIFY PASS）；余下 C3 提级（隔离消融改 `_should_sync`，CP1 问题 1）；合入主 PDF 前按 workflow §9 重跑本链 probe（schema_contract --check + dry-run）。
- 无须改教程/契约：page-10/11 与 schema.contract.yaml 口径本轮已对上。
- 只报告不修改：data.yaml 引用的 `lab/app.py` 已从 `.lab/snapshots` 快照恢复到根目录（REGIONS/METRICS 手抄常量在），C5 的 probe 已实测（2026-11-27：REGIONS(:12)/METRICS(:13) 在场）→ C5 `verified`。
