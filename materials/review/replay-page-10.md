# 第 10 页 · 学生视角独立重放报告

- 现场：`/tmp/replay-p10`（复制 `fixtures/`、`contracts/`、`scripts/lab`、`backend/app`、`docs/SCHEMA-CONTRACT.md`、`compose.yaml`，软链 `backend/.venv`；`lab/app.py` 用 `manual/shots/term_render.py` 的 `APP_PAGE_08` 写出）。临时 MySQL 容器 `replay-p10-mysql`（mysql:8.0，127.0.0.1:3311→3306），先灌 `fixtures/dw.sql` 回到 L1 状态（115 行）。未启动服务，未改仓库文件（只新增本报告），未读任何 writer/agent 报告。
- **替换声明**：页面命令里的 `lab-mysql` 一律替换为 `replay-p10-mysql`（页面命令不涉及宿主端口；任务指定的 3310 已被并行容器 `m-p12-mysql` 占用，故临时容器用 3311）。用户 `lab-mysql`(3307)/`lab-nginx`(8081)/8000 全程未碰（只读核对 3307 仍是 115 行）。
- 一句话结论：**核心实验全部复现**——换真数据后 `--check` 仍绿；契约 `expected_fact_rows` 改 410 后真红、报错原文逐字一致；拆一刀红/`lab reset` 还原文件/DB 仍 410/重灌回 115 全对；页面唯一 `cd` 在子 shell，每步后仍在仓库根。但正文有 3 处会让自学者卡住：前置顺序与第 11 页互相矛盾、对账段用"改契约之前"的状态写"现在"、拆一刀的还原被写成可选（漏做则下一关状态错误）。

## 环节表

| 环节 | 可执行? | 期望一致? | 问题数 |
|---|:--:|---|:--:|
| 前置（:3） | — | 否：阅读顺序自相矛盾 | 1 |
| 第 1 步 拍快照（:20-24） | 是（98 文件） | 描述与 `scripts/lab` 行为有出入 | 1 |
| 第 2 步 换数据（:26-30） | 是（115→410） | 是（只打印密码 Warning） | 1 |
| 第 3 步 对账（:32-34） | 是 | 数据行逐字命中；仅表头未展示 | 1 |
| 第 4 步 跑门禁（:37-41） | 是（exit 0） | 是（PASS 行 / S1 PASS） | 0 |
| 第 5 步 改契约（:43） | 是（exit 1） | 是（FAIL: 1）；"期望值"表述有歧义 | 1 |
| 「你应该看到」（:45-61） | — | 是（节选与原文一致） | 0 |
| 对账（:80-88） | — | 否：状态写错、"两处撞墙"不实 | 2 |
| 拆一刀 1（:92-97） | 是（exit 1） | 是（FAIL: 2，新行原文一致） | 0 |
| 拆一刀 2（:99） | 是 | 是（末行逐字、S1 PASS 假绿） | 0 |
| 拆一刀 3 / 跨页末态（:101-103） | 是（410→115） | 是，但还原被写成可选 | 1 |
| 跨页衔接（第 11/12 页） | — | 契约 115 假设成立；app.py 未被引用 | 0 |
| **合计** | | | **9** |

## 问题清单

| page-10.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| :3 | 「先读完第 11 页（L2 第一关），本页接它的 `contracts/schema.contract.yaml`」 | 阅读顺序矛盾：本页编号在 11 前；第 11 页自称接 L1 的 `lab/app.py` 且结尾指向"第 12 页"，全书无"先 11 后 10"约定。实测本页零依赖第 11 页产物（`--check` 离线读 `fixtures/dw.sql`，`lab/app.py` 未被任何命令引用） | 删掉该前置，改成"第 0 页 + 第 1、2 页"；若真要先做 11，连页号和第 11 页的"第 12 页"指针一起改 |
| :26-30 | 「命令和第 2 页灌 dw.sql 同款，只换文件」「`--default-character-set=utf8mb4` 让 `华东区` 这类中文按 UTF-8 进库」 | 两处不实：第 2 页命令不带这个 flag；`dw-real.sql:24`/`dw.sql:6`/`dw-real.checks.sql:9` 都自带 `SET NAMES utf8mb4`，实测去掉 flag 重灌后 R002 仍是 `华东区`（HEX `E58D8EE4B89CE58CBA`），末行 :103 重灌也不带 flag | 改"额外加了 `--default-character-set=utf8mb4`（可省略）；中文由文件里的 `SET NAMES utf8mb4` 保证" |
| :43 | 「把契约里的期望值改成真值」 | 只该改 `expected_fact_rows`；若学生把同段 `date_range`/`total_amount`/`total_quantity` 也改"真值"，实测红 3 条（ROW_COUNT+DATE_RANGE+TOTAL_AMOUNT），与页面 `FAIL: 1` 冲突 | 明说"只改 `expected_fact_rows`；另 3 项先别动——它们比的是旧快照，改红了会变多" |
| :82 | 「现在有三份数据在说话…契约期望值（`expected_fact_rows: 115`）…只换第一份…门禁绿，不代表数据真」 | 时序错位：对账紧接第 5 步，此刻契约已是 410、门禁红（学生刚看到 FAIL: 1）；"现在/115/绿"都是第 4 步的状态 | 改成"第 4 步那一刻：运行库 410/快照 115/契约 115 → 绿；第 5 步只是探针，拆一刀会还原" |
| :86 | 「本页只换了运行库」「装载器会在 ALTER TABLE ... DROP PRIMARY KEY 和重复 order_id 上撞墙」 | 本页也改了契约（对账时=410）；实测把 `dw-real.sql` 冒充 `fixtures/dw.sql` 只撞一处 `sqlite3.OperationalError: near "PRIMARY": syntax error`（裸 traceback），重复 `order_id` 在 ALTER 之后才 INSERT，执行不到 | 改"本页正式换的只有运行库；契约只临时改行数"；撞墙改成"卡在 SQLite 不支持的 DROP PRIMARY KEY" |
| :101 | 「要回演示数据就重灌（重灌后 `SELECT COUNT(*)` 回到 115，下一关从已知状态出发）」 | 语气像可选，但正文 5 步结束时 DB=410 真数据、契约红；实测漏做拆一刀 3 时第 12 页判据 `WHERE region_name='华北'` 得 35 行/61890.00，不是 41099.5；漏做拆一刀 2 时下一关 `--check` 红 | 改强制："本页结束前必须完成拆一刀 2/3——下一关的 41099.5 依赖 115 行演示集" |
| :18 | 「按顺序整段复制粘贴即可」 | 第 5 步要打开 yaml 改值并 Ctrl+S，第 3 步要读数；不能纯粘贴走完 | 改"命令逐段粘贴；第 5 步需手动改文件并保存" |
| :24 | 「名字只能用字母、数字、点、下划线、短横线」「只跟踪白名单文件（`contracts/`、`fixtures/`、`backend/`…）」 | 不全：脚本还要求首字符是字母/数字（实测 `.p10`/`-p10` 被拒）、≤64 字符、同名 save 直接 exit 1（复跑本页会卡第 1 步）；白名单实为 contracts、compose.yaml、backend/app、backend/tests、fixtures、frontend/src，**不含 `lab/`**（第 11 页的 app.py 不在 p10-before 里，页面没提） | 补"须以字母或数字开头；复跑换名字"；白名单写全或注明"`lab/`（含 app.py）不入快照" |
| :65-77 | 第 3 步对账摘录 | 实际每个 SELECT 前还有一行 Tab 分隔表头（`id dirty_class rows_hit` 等），摘录未展示；页面虽写"只摘关键行"，逐行核对仍会多出几行 | 加一行表头示例或注明"每段前有一行表头" |

## 最容易卡住的地方

- 实测最卡：对账段（上表 :82）——刚把契约改成 410 并看到红，正文却说"契约期望值 115、门禁绿、只换第一份"，我回头翻文件确认状态花了 >1 min。
- 其次：前置 :3 让人在"先读 11 还是先做 10"之间犹豫；若按页号顺序读，读第 11 页时又被告知"第 12 页会把它真交给数据库"，第 10 页被跳过。
- 命令本身都是 1 s 级；cwd 无坑：每步后 `pwd` 都在仓库根；拆一刀 2 末行、拆一刀 3 的 410→115 与页面完全一致。

## 真实输出摘录

第 4 步（换真数据后，exit 0；页内节选之外还有 2/3、3/3 两段 PASS）：
```text
== 1/3 契约 ↔ DDL/数据 ==
PASS: 5 张表 / 24 列 / 115 行 / GMV=279159.5 / 销量=622
S1 PASS
```
第 5 步（契约 410，exit 1）与拆一刀 1（GMV 期望值 1，exit 1）：
```text
  [DATASET_ROW_COUNT] dataset.expected_fact_rows: 契约声明 410 行，fact_order 实际 115 行
FAIL: 1 个契约问题
  [METRIC_VALUE_MISMATCH] metric.GMV: 公式实际值 279159.5 ≠ 契约期望 1
FAIL: 2 个契约问题
```
第 3 步对账表（实际为 Tab 分隔+表头；页面 13 行数据全部逐字命中）：
```text
D1	order_amount 为 NULL	2
D2	order_id 重复	2	1
D3	region_name 带“区”后缀	2	华东区,华北区
D4	region_id 孤儿行	1
D5	未来日期行	1
clean_rows	clean_orders	total_sales
405	405	1136341.10
D6	dim_region 同名(province)重复	1	1
D7	金额带分（非整数金额）	191
5	fact_order 原始行数	410
naive_sum_amount
1144735.50
```
其余关键实测：拆一刀 2 末行逐字 `现在工作区与快照 "p10-before" 完全一致。`，之后 `--check` 回 `S1 PASS`、DB `COUNT(*)`=410；拆一刀 3 重灌后 DB=115（GMV 279159.5、华北 19 单复现）；不带 charset flag 重灌 `dw-real.sql` 中文仍正确（R002 `华东区`）；§:43 若同改 3 个 dataset 字段得 `FAIL: 3 个契约问题`；真数据下 `WHERE region_name='华北'` 为 35 行/61890.00；`lab` 实测 `.p10` → `lab: 名字 '.p10' 要以字母或数字开头。`。
