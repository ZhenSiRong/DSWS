All green and the PDF basis is confirmed (lines 1434/1443/1845/1918: conditional step `correct_sql` must emit an explicit `skipped` and never be left as a grey pending block).

## 完成情况

`make stage5` 现已全绿。我没有修改任何测试、没有读取 `design/book*`、没有 `git commit`、没有联网。

### 修改的文件（共 3 个）及依据 PDF 的章节

**1. `backend/app/generate/guard.py`**
- 缺陷：S4 静态校验的「规则 #4 无常量投影」被整段删掉（原文留了一行注释 `# --- 4. （缺陷注入：常量投影检查被移除） ---`），导致 `SQL_CONSTANT_PROJECTION` 不再被发出。
- 修复：恢复对每条 `SELECT` 投影调用 `_is_constant_projection`，违规时追加 `GuardViolation("SQL_CONSTANT_PROJECTION", ...)`。
- 依据：**PDF 第二部分 S4 静态校验 规则 #4**（dsws.txt:4491-4495）："无常量投影：SELECT 列表里不得出现字面量或裸 NULL，否则 SQL_CONSTANT_PROJECTION；聚合表达式里的 CAST(... AS DECIMAL(10,2)) 属于类型声明，不算常量。"

**2. `backend/app/agent/orchestrator.py`**
- 缺陷：`_skip_correct()` 是个声称返回 `Iterator` 的生成器，却用 `return` 结尾（`return None`）。所有"图提前终止"（生成拒答/失败、GraphHalt、GraphCancelled）的路径都会 `yield from self._skip_correct()` → `TypeError: 'NoneType' object is not iterable` → 被兜成 `INTERNAL_ERROR`，淹没真实的错误码。
- 修复：`return` 改为 `yield self._progress(CORRECT_STEP, "skipped")`，显式补一条 `correct_sql` 的 skipped 事件。
- 依据：**审计缺陷 D4**（dsws.txt:1434、1443："correct_sql 在设计上可能不执行，如果它没有显式的 skipped，前端就永远灰着"；1845："任何提前结束都要显式发 skipped"；1918："条件步骤有 skipped 或终态"），以及 `contracts/steps.yaml` 第 3 条规则。

**3. `contracts/errors.yaml`**
- 缺陷 A：`SQL_REJECTED` 的 `retryable` 被写成 `true`，但合约注释（文件 28-30 行）与 PDF 都规定它"永远不可重试"。这导致 `propose_correction` 会拿被安全策略拒绝的 SQL 去问模型——正是注入开口子。
- 缺陷 B：`correction.max_attempts` 被写成 `2`，而路线图规定"校正最多一次"。
- 修复：`SQL_REJECTED.retryable: true → false`；`correction.max_attempts: 2 → 1`。
- 依据：dsws.txt:605 "SQL_REJECTED 永远不可重试"；:4525 "errors.yaml 的 correction 段：max_attempts: 1"；:6729 "（correction.max_attempts: 1）。SQL_REJECTED 永远不可重试"。

> 注：前端 `frontend/src/generated/contract.json` 此前已存为 `SQL_REJECTED: retryable=false`，所以修正 `errors.yaml` 后"生成物新鲜度"测试自动一致，无需重跑生成器，也没有手写改生成物。

### `make stage5` 最终输出（关键行）
```
== S5 · 安全策略门禁（注入语料 100% 拒绝 + 零误杀） ==
  1/3 注入语料：36/36 条按预期拒绝
  2/3 零误杀语料：11/11 条放行
  3/3 S4 基线：8/8 条 SQL 通过策略
== S5 · 注入语料判定表 == 语料：47 条，失败 0 条（全 PASS）
== S5 · 安全层测试 == 179 passed, 2 skipped
== S5 · 全部后端测试（S0 + S1 + S2 + S3 + S4 + S5） == 812 passed, 30 skipped
S5 PASS
```

### 其它
- 是否独立完成：是（全程仅依据 PDF 与仓库内的合约/测试定位并修复，未借助外部信息）。
- 置信度：**95**。四个缺陷都有 PDF 明文佐证，且 33 个失败用例全部转绿、全量后端测试无回归（812 passed）。扣掉的 5 分是因为我未逐行比对 PDF 里每一处可能被注入的位置，但所有可见失败已清零且修复均指向合约本身的不一致。
