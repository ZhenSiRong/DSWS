# 纠错链 · claims（人读版）

> 链：纠错链（图 12 S6 校正闭环状态机 + 图 31 失败注入矩阵）
> 机器可读版：[`claims.yaml`](claims.yaml)。status 口径：**verified** = 2026-11-27 本轮 probe 真跑通过；**inferred** = 只有真跑记录/证据文件、本轮未重跑；**unknown** = 证据缺口，不用「行业惯例」补。
> 左页 v1→v4 是**教学编撰**（D57 编撰声明见 spread 左页脚注）；右页与本表的终态结论全部挂代码/契约/真跑证据。

## Claim 表

| id | 主张 | 类型 | status | 证据锚 |
|---|---|---|---|---|
| C1 | 安全拒绝永不补考：SQL_REJECTED retryable=false，被拒 SQL 不回模型 | invariant | verified | errors.yaml · correct.py:176 · graph.py:316 · S6 PASS |
| C2 | 校正有界且回退唯一：「校验→校正→校验」唯一回退边，补考上限 N（契约名 correction.max_attempts）= 1 [当前值] | invariant | verified | errors.yaml correction 段 · graph.py:309–317 · 14 passed |
| C3 | 校正产物不豁免安检：重过 guard+policy，原 SQL 留 detail.original_sql | invariant | verified | errors.yaml revalidate_with · correct.py:23 · 14 passed |
| C4 | 20 条语料是「进不进补考」的名单（11 进 / 9 拒），不是成功率 | descriptive | verified | correction.jsonl（11 true/9 false 本轮 grep 真跑） |
| C5 | 真实补考不保证成功；成功率按 trials≥3 采样，分母=触发校正次数 | decision | unknown | PRD #3 那次真跑（触发=true/成功=false，耗时 16.31s）· v2 成功态 SSE；真模型采样未跑 |
| C6 | N=1 没有 sweep 实验依据（为何不是 2） | decision | unknown | errors.yaml max_attempts:1 · 无 N-sweep 数据 |

分布：**6 条 = 4 verified / 0 inferred / 2 unknown**。

## 逐条证据

### C1 · 安全拒绝永不补考（verified）
- 契约：`system/contracts/errors.yaml` 顶部注释 + `SQL_REJECTED.retryable: false`；`correction` 段与错误码表同源。
- 代码：`correct.py:176` `if not error.retryable` 直接不尝试；`graph.py:316` 只有 `failure.retryable` 才路由进 `CORRECT_STEP`。
- 本轮真跑：`(cd system/backend && .venv/bin/python -m app.scripts.failures --check)` → `S6 PASS`（9 场景含 `sql_rejected` 以 SQL_REJECTED 收尾、校正未触发）。
- 消融（未跑，预期红）：把 `SQL_REJECTED.retryable` 改 true → `failures --check` / 安全用例红（sql_rejected 场景进补考，与安全链 S1 同口径）；`build_datasets.py` 对账也会报错（expect 与 retryable 错位）——两视角。

### C2 · 有界单回退（verified）
- 契约：`correction.max_attempts: 1`；代码：`graph.py` `_route_after_validate`（retryable 且 `attempts < max_attempts` 才校正）、`correct.py:183` `policy.max_attempts < 1` 直接拒。
- 本轮真跑：`(cd system/backend && .venv/bin/python -m pytest tests/agent/test_correct.py -q)` → `14 passed in 0.20s`。
- 消融（p17 记录，`materials/review/adversarial-page-17-v2.md` 独立逐字复现）：入口短路 → `5 failed, 9 passed`，失败矩阵只红 `corrected` 一格；probe 20 条照绿（它量的是 guard/policy 发码，不量校正）。

### C3 · 改完必须复检（verified）
- 契约：`revalidate: true` / `revalidate_with: [guard, policy]`；校正后回 `validate_sql(gates=DEFAULT_GATES)`（graph.py），无豁免；原 SQL 留 `detail.original_sql`（correct.py:23 / errors.py:344–357）。
- 本轮真跑：同上 14 passed（含「上下文有等价字段时，改完能重过校验」断言）。

### C4 · 语料是名单不是成功率（verified）
- 本轮真跑：`grep -o '"retryable": [a-z]*' system/eval/correction.jsonl | sort | uniq -c` → `9 false / 11 true`；`expect` 同分布（11 corrected / 9 rejected）。
- `build_datasets.py` 用 `errors.yaml` 逐条校验 expect↔retryable；语料里**一条重试结局都没有**，拿它算成功率（11/20 或 11/11）都是假的（page-17 对账）。错误码 16 码 = 6 可重试 + 10 不可重试。

### C5 · 补考不保证成功（unknown）
- 样本 A：PRD 对照表 #3 真实云端模型——validate 红 → correct 那次真跑 16.31s → 列名仍不在契约（触发=true、纠正成功=false）。
- 样本 B：`materials/deliverable/v2/evidence/v2-natural-correct-success.sse` 单次复现过成功态；`system/eval/FINDINGS.md` §3.1 4 次里 3 次成功。
- 两样本结论不一 → 判据只能写「trials≥3 + 成功率 + 失败分类」，分母是触发校正次数。本轮未跑真模型采样（REBUILD_LLM_* 为空），故 unknown。

### C6 · N 的取值依据缺失（unknown）
- `max_attempts: 1` 是**当前值**；没有 N=0/1/2/3 等成本 sweep（最终通过率/延迟/成本/安全拒绝数）。
- **反悔点**：拿到 sweep 数据前，把 N 改成 2/3（或 0）都属于拍脑袋；改 N 前先跑实验。

## 反悔点 / 与源码的冲突（reconciler 只改叙事、不改源码）

1. **N=0 的口径冲突**：pilot/学生版叙事「N=0、1、3 都可以谈」，但 `errors.py:235` 把 `max_attempts < 1` 直接判非法（「至少为 1」）——N=0 不能只改契约，得连代码校验一起改；本链 spread 按源码口径写「N=1 是当前值」，不再宣称 N=0 可平滑配置。
2. **图 12 源文档行号过期（已修复）**：`12-s6-correction-state.md` 原称回退条件「写死在 orchestrator.py L305」，图源已改指 `graph.py` `_route_after_validate`（L309–L317）；`orchestrator.py` 无该循环。spread/claims 按源码引用 graph.py。
3. **语料标记易误读**：`expect: corrected` 只说「该进补考」，不等于「补考会成功」（page-17 对账已澄清）；任何把 11/20 当成功率的表述都按错误处理。
4. **图 12 的 retryable=false 清单不全（已修复）**：图源原列 8 个 false 码，现已补全为 10 个（16 码 − 6 可重试，含 SQL_EXECUTION_ERROR / INTERNAL_ERROR），与 errors.yaml 同口径。
