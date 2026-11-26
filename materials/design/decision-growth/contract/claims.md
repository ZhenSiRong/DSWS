# 契约链 · claims（人读版）

> 教学编撰声明（D57）：v1→v4 的生长时间线是**教学重构**，不是 commit 历史；每条 claim 的结论由代码/契约/真跑证据锚定。
> status 口径：`verified` = 本轮实跑 probe 或本轮/重放记录里的真跑证据（probe 里写了复核命令）；`inferred` = 只有代码/契约可证；`unknown` = 证据缺口。
> 数字口径：全部来自 `materials/design/decision-growth/contract/data.yaml` 及其引用的原始出处（page-10/11、契约、plan.py），不引入新数字。

## Claim 表

| id | 主张 | 类型 | status | 一句话证据 |
|---|---|---|---|---|
| C1 | 契约门禁拦得住契约漂移（115→410 立刻 FAIL: 1） | invariant | verified | page-10 拆一刀实测 + 本轮 `schema_contract --check` S1 PASS |
| C2 | 三存储从同一棵契约树派生（5/24/6/9、ES 76、Qdrant 98+22、0 writes） | invariant | verified | 本轮实跑 `build_meta_knowledge --dry-run` 计数逐项对上 |
| C3 | 值域分类：只有 enum/低基数 open 进 ES，range/主键/外键/度量不写 | decision | inferred | plan.py#_should_sync 代码可证；未单独消融实跑 |
| C4 | 门禁只读 DDL 快照、不读运行库（假绿边界） | invariant | verified | page-10：115 行快照 vs 410 行运行库实测 |
| C5 | lab/app.py 手抄 REGIONS/METRICS 是教学遗留，不纳入单源 claim | descriptive | verified | 真栈 probe（2026-11-27）：grep lab/app.py → REGIONS(:12)/METRICS(:13) 在场 |
| C6 | 文档从契约派生 + 新鲜度门禁（--write-doc / --check-doc） | decision | verified | 本轮 --check 第 3/3「文档新鲜度 PASS」 |
| C7 | S2 fresh 真写三存储已实证（S2 VERIFY PASS + 二次零写入）；阈值 1000 是 [当前值] | descriptive | verified | 真栈 make stage2（2026-11-27） |

## 每条的证据与反悔点

### C1 · 门禁拦得住契约漂移（verified）

- **证据**：`schema.contract.yaml#dataset` 的 `expected_fact_rows: 115` 是契约期望值；page-10 第 5 步把它改成 410 后 `--check` 立刻 `[DATASET_ROW_COUNT] FAIL: 1`，改回才绿（拆一刀实测）。本轮实跑 `--check` → `S1 PASS`，`pytest tests/test_s0_contract.py tests/test_s1_schema_contract.py` → 59 passed。
- **反悔点**：门禁不再核对期望值（--check 三段少一段）；或契约里允许「不检查行数」的逃生口——漂移就再也红不出来。

### C2 · 三存储同一棵契约树派生（verified）

- **证据**：`plan.py#BuildPlan.counts` 一次派生全部计数；本轮实跑 `build_meta_knowledge --dry-run`：`tables=5 columns=24 metrics=6 column_metrics=9 / ES values=76 / Qdrant column_points=98 metric_points=22 / DRY RUN: 0 writes`，与 data.yaml E2 逐位一致。派生链是 `契约 → BuildPlan → Meta/ES/Qdrant`（plan.py 头注：dry-run、单测、真构建共用同一份计划）。
- **反悔点**：有人绕过 BuildPlan 直写某一个存储（ES 或 Qdrant 里出现计划外的点）；或契约结构变了而 plan.py 不动——计数会当场对不上。

### C3 · 值域分类（inferred）

- **证据**：`plan.py#_should_sync` 的规则写得很直白——`role=dimension` 且 `kind ∈ {enum, open}` 且 `0 < distinct ≤ max_value_docs` 才同步；主键/外键、度量、range 全排除。图 16 figcap 同口径。**为什么不是 verified**：dry-run 的 ES 76 是这套规则跑出来的计数，但单独的消融没实跑（data.yaml 标 [代码可证] plan.py / stores）。
- **反悔点**：真数据换成高基数 open 列（distinct > 1000）后值全被滤掉、检索缺料——那时「低基数才同步」要重新定阈值；或 `_should_sync` 被改宽，ES 被主键/度量值淹没（v3 就是被这个打脸的）。

### C4 · 门禁只读 DDL 快照（verified）

- **证据**：`schema_contract.py` 的 `DDL_PATH = fixtures/dw.sql`、`load_ddl()` 装进**内存 SQLite**，文件头写着不需要 MySQL/Docker。page-10 实测：运行库换 410 行真数据，门禁仍报 `115 行 / S1 PASS`；把契约期望值改 410 才红——探针反证门禁不读运行库。三份数据在说话：运行库（410）、门禁快照（115）、契约期望值（115）。
- **反悔点**：门禁改成直连运行库核对——那 C4 的「假绿边界」描述就过期了，但同时 page-10 的整页叙事要重写；或 `fixtures/dw.sql` 快照更新而契约期望值不跟，出现新的错位。

### C5 · lab/app.py 手抄常量是教学遗留（verified）

- **证据**：page-11 尾注明说「`extract_keywords` 里的 REGIONS/METRICS 还是写死的，那是第 5 页的遗留，书内不再换」；data.yaml unknown 同口径「不纳入单源 claim」。教学上它是好反例：手抄字典是第二份口径，改漏一处就漂移（page-11 对账）。**probe 实测**（2026-11-27）：`grep -n "REGIONS\|METRICS" lab/app.py` → REGIONS(:12) / METRICS(:13) 手抄常量在场（L1 学生产物已从 `.lab/snapshots` 快照恢复到根目录）。
- **反悔点**：若后续演进把 lab/app.py 也接到契约上，这条要改成历史注脚；反之若有人拿 lab 的行为当契约单源的证据，漂移风险回来。

### C6 · 文档与契约同源（verified）

- **证据**：`schema_contract.py` 的 `--write-doc` / `--check-doc`；本轮 `--check` 第 3/3 段输出 `PASS: materials/docs/SCHEMA-CONTRACT.md 与契约一致`。文档不是手抄第二份，是契约的派生物。
- **反悔点**：有人手改 SCHEMA-CONTRACT.md 不回写契约（--check-doc 红）；或把 --check-doc 从 S1 里拿掉，文档悄悄过期。

### C7 · S2 fresh 真写三存储（verified）

- **证据**：真栈 `make stage2`（先 `source toolbox/scripts/export-docker-env.sh`）2026-11-27 实测——S2 VERIFY PASS（fresh 写三存储计数与 dry-run 一致：5/24/6/9、ES 76、Qdrant 98+22）+ IDEMPOTENT NOOP 0 writes。值域阈值 1000 保持 [当前值] 语义（低基数阈值：不同取值 ≤1000 的列才把完整值同步 ES）。
- **反悔点**：fresh 写入与 dry-run 计数再度漂移时 `--verify` 对账红——那时 C7 的实证要重跑；或 `make stage2` 的 verify 段被裁掉。
