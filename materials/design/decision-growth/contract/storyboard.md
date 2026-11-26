# 契约链 · Storyboard（CP1 一页 brief）

> 教学编撰声明（D57）：生长时间线 v1→v4 是**教学重构**，不是 commit 历史；终态结论全部由代码/契约/真跑证据锚定。

**链名**：契约链（图 15/16/19 · `materials/design/diagrams/03-data/`）

**核心问题（一句话）**：一份契约，怎么让 SQL、三存储、文档不打架？——答案：不是「配置集中」，是让 system 的派生链从同一棵契约树上长出来：契约 → BuildPlan → Meta/ES/Qdrant → 文档/门禁。

## Claim 表

| id | 主张 | 类型 | status |
|---|---|---|---|
| C1 | 契约门禁拦得住漂移（115→410 立刻 FAIL: 1） | invariant | verified |
| C2 | 三存储从同一棵契约树派生（5/24/6/9、ES 76、Qdrant 98+22、0 writes） | invariant | verified |
| C3 | 值域分类：enum/低基数 open 进 ES，range/主键/外键/度量不写 | decision | inferred |
| C4 | 门禁只读 DDL 快照、不读运行库（假绿边界） | invariant | verified |
| C5 | lab/app.py 手抄常量是教学遗留，不纳入单源 claim | descriptive | verified |
| C6 | 文档从契约派生 + 新鲜度门禁 | decision | verified |
| C7 | S2 fresh 真写三存储已实证（S2 VERIFY PASS + 二次零写入）；阈值 1000 是 [当前值] | descriptive | verified |

（详见 `claims.yaml` / `claims.md`。）

## 候选与剪枝（决策空间，[重构] 表示重构的候选，不是真实历史）

| 候选 | 被什么打脸 / 留下 |
|---|---|
| C1 [重构] 各模块手写 schema/常量 | **杀**：改一处别处不跟（漂移）；lab/app.py 的 REGIONS/METRICS 就是遗留反例（page-11 尾注） |
| C2 [重构] 只做单一 DDL、其他从 DDL 猜 | **杀**：表结构对齐了，但指标公式、值域、别名、列—指标关系没有家（data.yaml v2） |
| C3 [重构] 契约 YAML 但所有值都往 ES 写 | **杀**：全量同步制造噪声、examples 被误当全集（data.yaml v3 fail）→ 补值域分类 |
| C4 [当前] 契约 → BuildPlan → 三存储 + 值域分类 + 文档/门禁派生 | **留**：dry-run 计数 5/24/6/9、ES 76、Qdrant 98+22 全部同源派生；改 115→410 门禁立红 |

参数只标 [当前值]：值域同步阈值 `max_value_docs=1000`（低基数阈值：不同取值 ≤1000 的列才把完整值同步 ES；`build/config.py:83`）；`correction.max_attempts=1` 是纠错链口径，不在本链展开。

## 未知 / 反悔点

- **[已实证]** S2 fresh 真写三存储（2026-11-27 真栈 `make stage2`）：S2 VERIFY PASS + IDEMPOTENT NOOP 0 writes（C7 转 verified）——fresh/verify 对账已闭环。
- **[假绿边界]** 门禁只读 DDL 快照（`fixtures/dw.sql` 115 行），换运行库真数据不会自动让门禁看新库；「换数据要换三处（运行库、快照、期望值）」必须写进设计（C4）。
- 反悔点：绕过 BuildPlan 直写存储（C2 倒）；门禁加逃生口不核对行数（C1 倒）；手改文档不回写且摘掉新鲜度检查（C6 倒）。

## 两页布局（D57 版式）

- **左页**：2×2 四格、Z 字阅读 v1→v2→v3→v4。每格「做法 + 被什么打脸 + 补上了什么」：v1 各模块手写 → v2 DDL 为源 → v3 契约 YAML → v4 值域分类 + 三存储（标「当前」）。
- **右页**：终态设计 + 证据 + 可重跑命令。上半：图 16（三存储布局，figcap 原文）+ 派生链一行「契约 → BuildPlan → Meta/ES/Qdrant → 文档/门禁」；下半：证据 E1 契约门禁（S1 PASS / 59 passed + 拆 115→410 FAIL: 1）、E2 dry-run 计数、E3 假绿边界（115 快照 vs 410 运行库）；右下固定 `[未知]` 框（阈值 1000 是 [当前值] + fresh 已实证边界）。

## 请用户决定（CP1）

1. S2 fresh 真写三存储已闭环（2026-11-27 真栈 `make stage2` 实证）；C3 提级待隔离消融（改 `_should_sync` 重跑 dry-run）。
2. 假绿边界（C4）在右页是独立一块还是并进 E3 证据块？它是本链最反直觉的一条，倾向独立。
3. lab/app.py 遗留反例（C5）要不要进左页 v1 格？它是活教材，但要一句话说明它是 L1 学生产物、不是 system 派生链的消费者。
