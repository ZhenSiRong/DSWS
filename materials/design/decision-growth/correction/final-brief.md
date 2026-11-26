# Final brief（CP2）· 纠错链

> 产物：[`spread.png`](spread.png) / [`spread.html`](spread.html) / [`spread.pdf`](spread.pdf) · [`claims.yaml`](claims.yaml) · [`claims.md`](claims.md) · [`storyboard.md`](storyboard.md)
> 用户回：`收` / `改 X` / `停`。

## 一、结论（3 句）

纠错不是「多试几次」，是**一次有边界的补考**：只给 6 个可重试错误码、最多补考 N=1 次（当前值）、改完重过 guard + policy。**安全拒绝永不补考**——被拒 SQL 回模型等于给注入开重试口子。补考不保证成功，成功率只能按 trials≥3 采样写，N 的取值缺 sweep 实验依据。

## 二、已跑命令 / 结果（2026-11-27 本轮真跑）

| 命令 | 结果 |
|---|---|
| `(cd system/backend && .venv/bin/python -m pytest tests/agent/test_correct.py -q)` | `14 passed in 0.20s` |
| `(cd system/backend && .venv/bin/python -m app.scripts.failures --check)` | `S6 PASS`（16 码 / 路线图 7 码全在） |
| `grep -o '"retryable": [a-z]*' system/eval/correction.jsonl \| sort \| uniq -c` | `9 false / 11 true`（expect 同分布 9 rejected / 11 corrected） |
| `python3 materials/design/scripts/make_decision_growth.py --render correction` | spread.html + spread.png + spread.pdf |
| `python3 materials/design/scripts/check_spread.py correction` | `PASS`（v1 → v2 → v3 → v4 · 当前，无溢出/裁切） |
| `python3 -c "import yaml; yaml.safe_load(open('materials/design/decision-growth/correction/claims.yaml'))"` | 合法（另 data.yaml 已被生成器 safe_load） |

**消融（记录证据，本轮未重跑）**：p17 拆一刀（`propose_correction` 入口短路）→ `5 failed, 9 passed`，失败矩阵 9 场景只红 `corrected` 一格；`materials/review/adversarial-page-17-v2.md` 独立逐字复现过同一组数。

## 三、学生可读性三问（CP2 前自答；独立 reviewer 复核待做）

1. **N / 参数是什么**：N = `contracts/errors.yaml` 里 `correction.max_attempts`，**当前值 1**——最多补考 1 次；它是策略参数不是设计原则，改它要先做 N=0/1/2/3 等成本 sweep（且 `errors.py:235` 判 `max_attempts<1` 非法，N=0 得连代码一起改）。
2. **哪些错误不能重试**：**16 码 = 6 可重试 + 10 不可重试**——10 个 `retryable=false` 的码都不进补考，重点是 **SQL_REJECTED（安全拒绝）**、SQL_NOT_READ_ONLY、SQL_MULTIPLE_STATEMENTS、SQL_EMPTY、EMPTY_RESULT、TIMEOUT、CANCELLED、LLM_REFUSAL、SQL_EXECUTION_ERROR、INTERNAL_ERROR；只有 6 个码可重试（SQL_SYNTAX / SQL_UNKNOWN_COLUMN / SQL_UNKNOWN_TABLE / SQL_CONSTANT_PROJECTION / SQL_MISSING_ORDER_BY / SQL_MISSING_LIMIT，名单同 errors.yaml）。
3. **拆掉什么会红**：拆掉 `propose_correction` 校正入口 → `5 failed, 9 passed`（14 条测试红 5 条）、失败矩阵只红 `corrected` 一格；probe 20 条语料**照绿**（它量 guard/policy 发码，不量校正）——单元判据和失败矩阵抓得到，语料判据抓不到。

## 四、已知未知

- **[未知]** N=1 的依据：无 sweep 数据，「为何不是 2」没有实验答案；改 N 前先跑 N=0/1/2/3 比较通过率/延迟/成本/安全拒绝数。
- **[未知]** 长期成功率：PRD #3 触发=true/成功=false（那次真跑耗时 16.31s），v2 单次成功态——两样本不一，单次演示不能当判据。
- 本轮未跑：真模型多次采样（需开栈 + `REBUILD_LLM_*`）、p17 拆一刀重放（需改 correct.py，超出本任务写域）。

## 五、发现的矛盾（留痕，reconciler 按源码改叙事）

1. **N=0 口径**：pilot/学生版「N=0、1、3 都可以谈」vs `errors.py:235` 把 `max_attempts<1` 判非法——spread 已按源码口径改为「N=1 是当前值」。
2. **图 12 行号过期（已修复）**：`12-s6-correction-state.md` 原称回退条件在 `orchestrator.py L305`，图源已改指 `graph.py` `_route_after_validate`（L309–L317）。
3. **图 12 retryable=false 清单不全（已修复）**：图源原列 8 个 false 码，现已补全为 10 个（16 码 − 6 可重试，含 SQL_EXECUTION_ERROR / INTERNAL_ERROR），与 errors.yaml 同口径。
4. **语料标记易误读**：`expect: corrected` ≠ 校正会成功；11/20 不能当成功率。

## 六、后续动作（不在本任务自动做）

- 教程/图源：`tutorial/page-17.md` 无需改；图源 `materials/design/diagrams/02-runtime/12-s6-correction-state.md` 已修复——回退条件改指 `graph.py` `_route_after_validate`（L309–L317），retryable=false 清单补全 10 码，无需再动。
- 30 页设计文档装配：待 CP2 通过后由装配步骤合入增补卷/主 PDF（`design-doc-growth.md` §9），合入前再跑一次 probe/ablation。
- 学生可读性：三问答案已在 §三；「找一个没参与生产的人复述」一步本任务无法自证，留独立 reviewer（§5.8）执行，VERDICT 待填。
