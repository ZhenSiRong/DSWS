# storyboard.md · 用户旅程设计（journey）· CP1 一页 brief

> 规格：`toolbox/workflows/design-doc-growth.md` §5.3。用户只回：`继续` / `改 X` / `停`。
> 版式口径：D57（左页 2×2 v1→v4 Z 字，每格「做法 + 被什么打脸 + 补上了什么」，v4 标「当前」；右页终态 + 证据 + 可重跑命令）。

## 链名与核心问题

- **链名**：用户旅程设计（journey，A 类，D56 新增链）
- **核心问题（一句话）**：用户从「输入中文问题」到「看到结果表」的旅程，每一步锚定在哪段源码上——以及这个旅程是怎么从「白屏等待」长成「每步有名字」的？

## Claim 表（详见 claims.yaml / claims.md）

| id | 主张 | status |
|---|---|---|
| J1 | 一次问数 = 一张 12 节点图，id 逐字来自 steps.yaml，10 stage 分组 | verified |
| J2 | SSE 流必以 result 或 error 收尾，绝不静默 | verified |
| J3 | validate_sql 双关（guard+policy），拒绝在执行前有名字 | verified |
| J4 | correct_sql ≤1 次、校正后重验；SQL_REJECTED 永不进 correction | verified |
| J5 | run_sql 拒绝不连库；dw_reader 仅 SELECT、去多语句、会话超时 | verified |
| J6 | 前端按契约解析事件（未知类型留痕、无终态补 STREAM_INCOMPLETE） | verified |
| J7 | 结果表按契约类型渲染；空结果=空态；伪 SQL 有止损卡 | verified |
| J8 | 3024→TIMEOUT 已实测；1205/1317 未真触发、取消竞态无测试 | unknown |

## 候选与被剪枝理由（决策空间，[重构]）

1. **[重构] 旅程图画「页面截图流」**——被 J1/J3 杀掉：旅程的锚点是文件:符号，不是界面截图；截图说不清 validate 双关在哪一步。
2. **[重构] 旅程按 10 步（stage）画 10 格**——被 J1 杀掉一半、留下一半：stage 是教学分组，但 SSE 是 12 节点逐条 progress；图上按节点链画、标注 stage 号，两者都保。
3. **[重构] 把 correct_sql 画成「必经步骤」**——被 J4 杀掉：它是 conditional（steps.yaml `conditional: true`），不触发时显式 skipped；画成必经会复制旧前端「永远灰块」的错误印象。
4. **留下**：按源码真实调用链画「前端 → 路由 → 图节点 ⇄ 校正 → 执行 → SSE → 渲染」，每格标文件·符号（journey-map.svg ①–⑪）。

## 未知 / 反悔点

- [部分实证] 真库侧（2026-11-27）：3024→TIMEOUT 真库实测转正，SHOW GRANTS 已由安全链 S6 实证；[未知] 1205/1317 未真触发（仅参数化单测）、取消竞态无真并发测试（tests/security 的 2 skipped 是拒答题 runtime skip，非真库用例）。
- [未知] 执行期间取消丢结果的竞态只有代码路径，未做并发实测。
- 反悔点：max_attempts=1 是 [当前值] 不是原则；「10 步」是 stages 分组口径，不是 10 条事件；v1–v4 为教学编撰（D57）。

## 计划的两页布局

- **左页（问题/直觉）**：2×2 Z 字 v1「白屏等待」→ v2「流式步骤条」→ v3「有名字的错误+一次校正」→ v4「契约驱动全程旅程」（当前）；每格做法/被打脸/补上；底部编撰声明（生成器自动加）。
- **右页（证据/落地）**：journey-map.svg（①–⑪ 每步标文件·符号）+ 3 条证据（12 节点/10 步同源、双保险边界、流必收尾+类型渲染）+ 可重跑命令（pytest / npm test）+ [未知] 框 + 带走一句话。

## 请用户决定的 1–3 个问题

1. v1–v4 的生长主轴选「体验可见性」（白屏→流式→错误可读→契约驱动）——是否换成「错误处理」主轴？
2. 右页图用 journey-map.svg（自绘步骤图）——要不要改放 frontend 截图？（建议不改：截图不承载符号锚点）
3. J8 的真库验证是否排入后续（起 docker 栈复跑 tests/security）？
