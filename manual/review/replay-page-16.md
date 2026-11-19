# 第 16 页重放报告（学生视角 · 2026-11-19）

**一句话结论**：本页可完整离线重放，三条判据与「拆一刀」的全部数字/行文均复现；「错 SQL 被第二道关接住、没被执行、码退化为 SQL_REJECTED」经实测成立（执行器 0 次调用、终局 validate_sql）；仅 6 处小瑕疵（2 中 4 低），PYTHONPATH 旧注释与 policy.py 同名行最该先补。

重放环境：`/tmp/replay-p16` 仓库副本（无 `.env`、无栈），全部命令在 `unshare -rn` 断网命名空间执行；原仓库文件未改（`manual/page-16.md` 未动）。

## 环节表

| # | 环节（page-16.md 行） | 实测结果 | 问题数 |
|:--:|---|---|:--:|
| 0 | 离线前提（:3） | 断网 + 无 .env 跑通三步，未连 MySQL/ES/Qdrant/模型 | 0 |
| 1 | 第 1 步快照（:16–20） | `已保存快照 "p16-before"：169 个文件。`；同名再 save 被拒 | 0 |
| 2 | 第 2 步 pytest（:22–26） | `26 passed`；19 个 test 函数（含 8 条参数化）= 26，9 个违规码各有负例 | 0 |
| 3 | 第 3 步失败矩阵（:28–32） | 9 场景与 `scenarios.yaml` 一致（码/类别/失败步骤均被脚本断言）；`16 个码，路线图要求的 7 个全在`；`S6 PASS`；子 shell 后 pwd 仍在仓库根 | 0 |
| 4 | 第 4 步 probe+分布（:34–39） | `{"total": 20, "mismatch": 0}`；分布 10 行逐字一致（前 6 行 + 后 4 码各 1） | 1 |
| 5 | 你应该看到（:45–60） | 26 passed / S6 PASS / total、mismatch / 分布 全部对；秒数为机器相关 | 1 |
| 6 | 这一页构建什么（:5–12） | 20 语料 / 16 码 / 9 场景的描述与后文、代码一致；仅「9 个失败场景」措辞不准 | 1 |
| 7 | 对账（:62–68） | 10 种码 = 9 静态 + SQL_REJECTED、16 码总数、剩余 6 码、「五张表」error_alignment 实测 11 passed，全部核实 | 0 |
| 8 | 拆一刀（:74–92） | 严格只改一行：`1 failed, 25 passed`（`test_unknown_column_is_rejected`）；`FAIL: 1 项`；c01/c02/c07 `actual []`；`mismatch: 3`；执行器 0 调用 | 2 |
| 9 | 还原回绿（:97–105） | `S6 PASS`、`mismatch: 0`；guard.py 与原件逐字节一致；reset 真实输出 11 行 | 1 |
| 10 | 跨页衔接（第 15/17/19 页） | 第 15 页末为 reset 后绿态、本页无需栈；第 17 页「自动校正闭环」、第 19 页「审策略」与目录一致 | 0 |
| 11 | D48 整段连续粘贴（:3） | 单 shell 从仓库根连跑全页命令（含拆一刀 + 还原）：pwd 始终不变、无 exit 127、无 not found | 0 |

## 问题清单（6 条）

`page-16.md:行 | 原文 | 问题 | 建议`

| # | 行 | 原文（节选） | 问题（实测） | 建议 |
|:--:|:--:|---|---|---|
| 1 | :34 | `PYTHONPATH=backend backend/.venv/bin/python eval/probe_correction.py` | 命令本身可跑（mismatch 0）；但 `eval/probe_correction.py` 的 docstring 用法 `cd backend && .venv/bin/python ../eval/probe_correction.py` 实测 `ModuleNotFoundError: No module named 'app'`。页面没提旧注释失效，也没解释为何必须加 PYTHONPATH | :34 补一句「脚本注释里的旧用法会 ModuleNotFound，必须按下行加 PYTHONPATH」，或改 docstring |
| 2 | :74 | 搜 `for column in tree.find_all` … 只改这一行 | 同款 `for column in tree.find_all(exp.Column):` 在 `backend/app/security/policy.py:460` 也有一行；若用 IDE 全局替换会连第二道关一起拆——实测双向都拆后 failures 报 3 项（实际 `EMPTY_RESULT`、类别 `empty`、步骤 `run_sql`），错 SQL 被放行到执行，实验结论失真 | 补一句「只改 guard.py；policy.py 有同名一行，别全局替换」 |
| 3 | :102–105 | `现在工作区与快照 "p16-before" 完全一致。` 等 3 行 | reset 真实输出 11 行：先打印恢复计划、`pre-reset-<时间戳>` 安全快照、覆盖明细，末行才是这句；页面未标「节选」，逐字核对不符（时间戳每次不同） | 标「节选，末行…」，或给出完整输出形态并说明时间戳会变 |
| 4 | :47 / :85 | `26 passed in 0.41s` / `1 failed, 25 passed in 0.32s` | 秒数随机器/缓存变化：实测 0.33/0.35/0.45/0.79s（0.32 有一次正好）；页面未注 | 加「秒数因机器而异」（第 15 页已有先例） |
| 5 | :7 | `16 个错误码 + 9 个失败场景` | 9 个场景里 happy/slow/corrected 期望 `result`，只有 6 个是失败；`failures.py` 的 help 也写「6 类失败」 | 改「16 码 + 9 个场景（6 类失败 + 3 条对照）」 |
| 6 | :79–81 | 拆一刀三条判据命令块 | pytest/failures 预期退出码为 1；若学生用 `set -e` 或遇错即停的 runner，第三条 probe 不会执行，看不到 mismatch 3 | 补一句「前两条返回 1 是判据在报红（预期），三条都要跑完」 |

## 真输出摘录（断网 + 无 .env 实测）

```text
# 第 2 / 3 / 4 步
26 passed in 0.35s
  sql_unknown_column   期望 SQL_UNKNOWN_COLUMN   实际 SQL_UNKNOWN_COLUMN
  错误码表：16 个码，路线图要求的 7 个全在
S6 PASS
{"total": 20, "mismatch": 0}
      5 SQL_REJECTED / 3 SQL_UNKNOWN_COLUMN / 2 SQL_UNKNOWN_TABLE / 2 SQL_SYNTAX
      2 SQL_NOT_READ_ONLY / 2 SQL_CONSTANT_PROJECTION
      1 SQL_MULTIPLE_STATEMENTS / 1 SQL_MISSING_ORDER_BY / 1 SQL_MISSING_LIMIT / 1 SQL_EMPTY

# 拆一刀后（只改 guard.py 一行）
1 failed, 25 passed in 0.32s        # FAILED …::test_unknown_column_is_rejected
FAIL: 1 项不符合预期
  - sql_unknown_column: 错误码不符（期望 SQL_UNKNOWN_COLUMN，实际 SQL_REJECTED）
FAIL c01 expected SQL_UNKNOWN_COLUMN actual []
FAIL c02 expected SQL_UNKNOWN_COLUMN actual []
FAIL c07 expected SQL_UNKNOWN_COLUMN actual []
{"total": 20, "mismatch": 3}

# 同一次拆刀后直接取场景终局事件（页面结论的核心证据）
executor_calls: []                  # 错 SQL 没有真的执行
terminal: {"code":"SQL_REJECTED","class":"failure","step":"validate_sql",
           "message":"列 dim_region.no_such_column 不在契约白名单里…",
           "detail":{"reason_code":"SQL_COLUMN_NOT_ALLOWED"}}
steps: generate_sql success → validate_sql error → correct_sql skipped（无 run_sql）

# 回绿
现在工作区与快照 "p16-before" 完全一致。
S6 PASS
{"total": 20, "mismatch": 0}
```

## 清理

`/tmp/replay-p16`（含其中 `.lab`）与 `/tmp/p16logs` 已删除；`manual/page-16.md` 未改（sha256 `4f277cf2…`）；本重放未在原仓库创建 `.lab`——期间出现过的 `.lab/`（`p17-before`/`pre-reset-*`，18:00 生成）属并发 writer-l3-p17，已由其自行清理；用户栈（lab-* 容器）未触碰。
