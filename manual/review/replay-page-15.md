# 第 15 页独立重放报告（学生视角 · 审生成）

> 方式：`/tmp/replay-p15` 仓库副本（HEAD `80da783` + 工作区未提交 `Makefile` 版，`backend/.venv` 用副本）按页面文字从仓库根**整段连续执行**；不启栈、不碰用户栈，strace 实测无外网、无 3306/9200/6333/8100/8080 连接。页面未改，本报告是唯一写入。

**一句话结论**：主线可完整重放，四组关键判据**逐字命中**（`122 passed, 5 skipped`／`基线：10/10 通过（拒答 2）`／`S4 PASS`／`813 passed, 30 skipped`；拆一刀后 `8/10`、`12 failed, 110 passed, 5 skipped`、`FAIL: 3` 与三个码全中），无阻断性错误；共 7 条交代缺口，3 条先修见文末。

## 环节表

| # | 环节（page-15.md 行） | 真结果（学生视角） | 问题数 |
|---|---|---|---|
| 1 | 前置/离线（:3、:7） | 不需栈/`.env`/模型 key：移走 `.env` 后 `make stage4` 仍 `813 passed, 30 skipped` + `S4 PASS`；strace 无外网、无服务端口（23 条 connect 全是 `test_smoke_checks.py` 自带 127.0.0.1 临时 socket） | 2 |
| 2 | 第 1 步快照（:18–:24） | `已保存快照 "p15-before"：169 个文件。`（与页面 169 一致）；同名再 save 被拒（rc=1，提示换名/`lab list`） | 1 |
| 3 | 第 2 步 pytest（:26–:44） | `122 passed, 5 skipped in 1.39s`（页面 0.96s，已声明秒数因机器而异）；`-rs` 实测 5 条 = 3×`extend_keywords_*` + `filter_metric/table_info`，与页面「召回扩展/上下文过滤提示词」一致 | 0 |
| 4 | 第 3 步 stage4（:32–:58） | 33.83s（页面「本机实测 38 秒」）；三行横幅/顺序逐字一致；`122 passed, 5 skipped in 0.76s`、`813 passed, 30 skipped`、末行 `S4 PASS` | 1 |
| 5 | 拆一刀·基线红（:70–:92） | 只改 1 行 → rc=2；`基线：8/10 通过（拒答 2）`；仅 b01/b04 两行 `[SQL_UNKNOWN_COLUMN] 列 fact_order.order_id 不在契约上下文里`；b02 仍 PASS；末行 `make: *** [Makefile:88: baseline] Error 1` 逐字一致 | 0 |
| 6 | 拆一刀·测试/契约（:94） | `12 failed, 110 passed, 5 skipped in 0.81s`（`test_baseline_case` 只红 b01/b04）；`(cd backend && .venv/bin/python -m app.schema_contract --check)` → `FAIL: 3 个契约问题`，3 码 `METRIC_RELEVANT_COLUMNS`／`METRIC_VALUE_MISMATCH`／`METRIC_FORMULA_SEMANTICS` | 1 |
| 7 | 还原（:96–:106） | reset 先拍 `pre-reset-20261119-174957`（169 文件），末行 `现在工作区与快照 "p15-before" 完全一致。`；再 `make baseline` → `基线：10/10 通过（拒答 2）` | 1 |
| 8 | D48 整段连续（:3） | 同一 shell 从仓库根顺序执行 9 条：`pwd` 始终不变、无 exit 127；中段手工改 YAML 不影响后续 | 0 |
| 9 | 最易卡（:32、:72–:76） | 38 秒有「别以为卡死」，实测 33.8s（strace 干扰下 49.8s），不会被当卡死；YAML 位置/4 空格缩进/只改 formula 的提醒都够，仅缺「别全局替换」防呆 | 1 |

**四类合计：① 指令/歧义 3 · ② 期望不符 0 · ③ 跨页 3 · ④ 最易卡 1，共 7 条。**

## 问题清单

| page-15.md:行 | 原文（摘） | 问题 | 建议 |
|---|---|---|---|
| :3/:32/:81（另 :99） | 「`make stage4` 完全离线」「还原并回绿」 | **副作用未交代**：本机 uv 全局配了镜像（`~/.config/uv/uv.toml`），`make stage4`/`make baseline` 里的 `uv run` 会**静默重写** `backend/uv.lock`（实测 2812 行 registry URL 变化，`UV_OFFLINE=1` 也照写）；lab 白名单不含它、`reset` 不还原 → 页面跑完 `git status` 仍脏。`uv run --frozen`／`--no-config` 实测不重写 | 第 3 步或还原后加一行：若 `git status` 里 `backend/uv.lock` 变了（uv 镜像配置导致），`git checkout -- backend/uv.lock`；或 Makefile 用 `uv run --frozen`（与第 0 页 `uv sync --frozen` 口径一致） |
| :18 与 :99 | 「同名快照会被拒，重做本页就换个名字」／`scripts/lab reset p15-before --yes` | 不自洽：重做换名后，后面 reset 仍写死 `p15-before`，会回滚到第一次的快照；lab 也没有删除命令，快照越积越多 | 补一句「重做时把本页后面所有 `p15-before` 一起换成新名字」 |
| :94 | 「第 11 页的契约自检也会报 3 处矛盾」 | 页面其它输出都给命令+期望，这里只有一句指路：没有命令、没有 `FAIL: 3`、没有 3 个码，学生要回翻第 11 页才知道怎么验 | 直接给 `(cd backend && .venv/bin/python -m app.schema_contract --check)` + 期望 `FAIL: 3 个契约问题` + 3 码（METRIC_RELEVANT_COLUMNS／METRIC_VALUE_MISMATCH／METRIC_FORMULA_SEMANTICS） |
| :3 | 「第 13 页的整栈可以继续跑着」 | 学生刚做完第 14 页（其拆一刀停过 ES、末尾 `docker compose start elasticsearch` 拉回），「第 13 页」编号错位，易让人回翻确认 | 「上一页（第 14 页）结束时的栈可以继续跑着——本页一条都不用」 |
| :7 | 「10 题黄金集 `baseline`」 | 术语冲突：第 14 页「黄金集」= 20 题；实际 baseline 10 题 = 8 题取自检索黄金集 + 2 题越界拒答题（`baseline.yaml` 注释） | 「10 题基线（8 题复用检索黄金集，另 2 题越界拒答）」 |
| :56 | 「813 passed, 30 skipped」 | 30 条 skipped 未解释（本页只解释了第 2 步的 5 条）：实测 30 = 23 条 `REBUILD_INTEGRATION` 集成 + 5 条提示词 + 2 条安全语料拒答题 | 加半句构成，或指回第 14 页对 23 条的说明 |
| :72–:76 | 「找到 `metrics:` 下 `name: GMV` 那段，只改 formula 这一行」 | 提醒基本够（4 空格缩进与文件一致、实测可解析），但没防全局替换：`SUM(fact_order.order_amount)` 在 AOV、平均件单价两条公式里也出现，Ctrl+H 会一次改坏 3 个指标，红的不止 b01/b04 | 加「别用全局替换，只动 GMV 这一行；改坏就 `scripts/lab reset p15-before --yes` 重来」 |

## 真输出摘录

（略去 make 回显的命令行；均为实跑原文）
```text
# 第 2 步
122 passed, 5 skipped in 1.39s
# 第 3 步
基线：10/10 通过（拒答 2）
122 passed, 5 skipped in 0.76s
813 passed, 30 skipped in 30.59s
S4 PASS
# 拆一刀 make baseline
| 华北销售额 | [SQL_UNKNOWN_COLUMN] 列 fact_order.order_id 不在契约上下文里 | FAIL |
| 品牌销售额 Top 3 | [SQL_UNKNOWN_COLUMN] 列 fact_order.order_id 不在契约上下文里 | FAIL |
基线：8/10 通过（拒答 2）
  - b01: 期望 SQL，实际拒答 SQL_UNKNOWN_COLUMN
  - b04: 期望 SQL，实际拒答 SQL_UNKNOWN_COLUMN
make: *** [Makefile:88: baseline] Error 1
# 同一刀
12 failed, 110 passed, 5 skipped in 0.81s
FAIL: 3 个契约问题
  [METRIC_RELEVANT_COLUMNS] metric.GMV: 公式引用 [...order_amount, ...order_id] ≠ relevant_columns [...order_amount]
  [METRIC_VALUE_MISMATCH] metric.GMV: 公式实际值 2427.473913043478 ≠ 契约期望 279159.5
  [METRIC_FORMULA_SEMANTICS] metric.GMV: GMV 的公式必须是 SUM(FACT_ORDER.ORDER_AMOUNT)
# 还原
现在工作区与快照 "p15-before" 完全一致。
基线：10/10 通过（拒答 2）
```
- 离线证据：移走 `.env` 后 `make stage4` 仍 `813 passed, 30 skipped`/`S4 PASS`；strace 无外网、无服务端口。
- 工作区：补做 `git checkout -- backend/uv.lock` 等价操作后，`/tmp` 副本与执行前逐文件 sha256 全同；原 repo 的 `.lab/`（p16 并行任务）未触碰。

## 最该先修 3 条

1. **:3/:32 `uv.lock` 被 `uv run` 静默重写**——镜像机的学生每次 `make` 都会把工作区改脏且 reset 不还，一行提示或 `--frozen` 即可。
2. **:72–:76 拆一刀防呆**——本页核心动作，补「别全局替换」免得多红 2 个指标、让学生怀疑判据坏了。
3. **:94 第 11 页自检**——「三处闸门同时响」里唯一不能当场照抄验证的一环；给命令 + 3 码，页面自洽。

> 清理：`/tmp/replay-p15`、`/tmp/replay-p15-logs` 已删除；未改 `manual/page-15.md`；`/tmp` 无本页残留。
