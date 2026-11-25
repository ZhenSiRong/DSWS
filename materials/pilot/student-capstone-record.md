# Capstone 学生验证（2026-11-09）

## 1. 设置

| 项 | 值 |
|---|---|
| 学生 | CodeBuddy `hy3 --effort low`，40 轮 |
| 输入 | 只有 PDF（211 页，SHA 见下） |
| 工作树 | `/tmp/opencode/capstone`（`95ab5f6` + 4 处注入缺陷） |
| 禁读 | `design/book/*`、`design/book-editorial/*` |
| 禁做 | 改测试绕过、commit、联网 |

## 2. 注入的 4 处缺陷

| # | 文件 | 缺陷 | 教材依据 |
|---:|---|---|---|
| A | `contracts/errors.yaml` | `SQL_REJECTED.retryable` 改成 `true` | 「策略拒绝永远不可重试」 |
| B | `contracts/errors.yaml` | `correction.max_attempts` 改成 `2` | 「校正最多一次」 |
| C | `backend/app/agent/orchestrator.py` | `_skip_correct()` 不再发 `skipped` | 「条件步骤必须显式 skipped」 |
| D | `backend/app/generate/guard.py` | 删除常量投影检查 | 「无常量 / NULL 投影」 |

## 3. 修复前（证明尺子能抓到）

```
FAIL C3d_detection - {"total": 20, "mismatch": 2}
FAIL C3a_loop - 6 failed, 24 passed
FAIL C4_stage5 - S5 PASS（退出码非 0）
GATES FAILED
```

## 4. 学生结果

- 4 处缺陷全部定位并修复；`make stage5` → **812 passed, 30 skipped, S5 PASS**。
- 自评独立完成，置信度 95。
- 修复只动源码，**没有改任何测试**（`git diff --name-only | grep tests/` = 0）。
- 报告：`pilot/student-capstone-report.md`。

## 5. 协调方独立复跑

```
PASS C1_contract - 12 nodes; match=True
PASS C6_health - HTTP 200
PASS C5_frontend - title_ok=True asset_ok=True
PASS C2b_baseline - 基线：10/10 通过（拒答 2）
PASS C3d_detection - {"total": 20, "mismatch": 0}
PASS C2r_recall - 3 passed, 23 skipped
PASS C3a_loop - 30 passed
PASS C4_stage5 - S5 PASS
ALL PASS
```

## 6. 与参考实现的差异

学生修复后，`git diff` 只涉及 `backend/app/generate/guard.py`：
- 用 `select.expressions` 而非 `select.selects` 遍历投影；
- 违规 detail 不带原始 SQL 片段；
- 命中第一条后 `break`。

行为通过全部 C1–C6，属于「等价实现」而非「逐字相同」。这正是验收口径：
**看一致性测试的通过集合，不看代码相似度。**

## 7. 结论

一个低思考强度、PDF-only 的学生，能在 40 轮内修好 4 个契约级缺陷，
并把系统拉回与参考实现一致的行为集合。教材在这一组任务上是合格的。

## 8. 已知限制

- 只验证了「修复型」路径，没有验证从零重建。
- 学生是否偷看 `design/book` 无法从进程内证明；任务书明确禁止，报告未引用书稿源文件。
