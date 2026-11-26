# 设计生长工作流（design-doc-growth）

> 触发方式：**主动触发**。用户说“跑 <链名>”或指定一张 A 类图时开始；不做定时生产。
> 产出：一条链的**一份**叙事跨页（默认 2 页），不是“评审版 + 学生版”两套。
> 规格状态：v1，2026-11-26。实现/验收以此文件为准。

## 1. 适用范围

只处理已冻结的 A 类链：

| 链 | 图 | 状态 |
|---|---|---|
| 纠错链 | 12 + 31 | pilot 已完成 |
| 安全链 | 22 + 23 + 24 | 下一条 |
| 契约链 | 15 + 16 + 19 | 待排 |
| 运行链 | 27 | 待排 |
| 用户旅程设计 | 问数旅程图（新建） | 2026-11-27 起（D56） |

B/C 类图不在本工作流里；它们走自动生成/附录，不写决策生长叙事。

## 2. 触发

- **唯一正常触发**：用户点名一条链，或点名某张 A 类图所属的链。
- 不设每周定时产出。
- 不在代码变更时自动重写叙事；变更只进审计工作流。

## 3. 输入

每次运行必须拿到：

1. 该链的 A 类图源：`materials/design/diagrams/` 下的 `.md` + `.svg`；
2. 相关代码/契约/测试：实际路径写进 claims；
3. 已记录证据：`tutorial/page-*.md`、`materials/review/`、PRD/验收文档、真跑截图；
4. 决策记录：`materials/humen-desicions/` 中能对上的 D 编号或说明“无记录”；
5. 已有结论/未知项：上一版 claims 或 pilot 产物。

找不到“当时为什么”时，允许**教学编撰**生长时间线（D57）：时间线是教学重构、不是 commit 历史，必须带**编撰声明**；但 claim/证据规则不变——终态设计必须由代码/契约/真跑证据锚定，证据缺口照标 `[unknown]`，禁止用“行业惯例”补空。

### 3.1 `claims.yaml` 最小 schema

```yaml
chain: security
items:
  - id: S1
    claim: "策略拒绝的 SQL 绝不送回模型重试"
    type: invariant          # invariant | decision | descriptive
    sources:
      - system/contracts/errors.yaml#SQL_REJECTED
      - system/backend/app/agent/correct.py
    probe:
      - (cd system/backend && .venv/bin/python -m app.scripts.failures --check)
    ablation:
      - "把 SQL_REJECTED 的 retryable 改成 true：36/36 安全用例应出现失败"
    status: verified          # verified | inferred | unknown
```

没有 source 的 claim 不合法；没有 probe/ablation 的 claim 只能是 `inferred/unknown`。

## 4. 产出目录

```text
materials/design/decision-growth/<chain>/
  claims.yaml          # 机器可读：claim / type / sources / probe / ablation / status
  claims.md            # 人读：claim 表 + 证据 + 反悔点
  storyboard.md        # CP1 的一页 brief
  spread.html          # 固定画布（默认 1540×1600 ×2 页）
  spread.png           # 渲染产物
  evidence/            # 截图、输出摘录（可选，引用原路径亦可）
  final-brief.md       # CP2 的 brief
```

除非用户另行指定，所有叙事产物只写这个目录；不改 30 页设计文档正文，等待用户确认后由发布/装配步骤合入。

## 5. 步骤

### 5.1 Claim harvest（无 checkpoint）

- 从图源、代码、契约、测试、PRD/评审里抽 4–8 条 claim；
- 每条 claim 必须写明：
  - `id`、一句主张、类型 `invariant | decision | descriptive`；
  - `sources`（文件/行号或章节）；
  - `probe`（可跑命令或可查的测试）；
  - `ablation`（删掉什么，应该出现什么红）；
  - `status`：`verified | inferred | unknown`。
- `[unknown]` 是合法结果，禁止用“行业惯例”补空。

### 5.2 决策空间与证据剪枝（无 checkpoint）

- 写 2–4 条候选做法；候选可以是**重构的决策空间**，但必须标 `[重构]`；
- 每条候选写“被哪条证据杀掉/留下”；
- 不允许把“当前实现”直接写成“唯一正确做法”；参数值（例如 N=1）只能标为 `[当前值]`，除非有实验证据。

### 5.3 CP1：Storyboard brief（人审）

只交一页 `storyboard.md`，不交完整视觉。必须包含：

- 链名、核心问题（一句话）；
- claim 表（4–8 条，带 status）；
- 2–4 条候选与被剪枝理由；
- 未知/反悔点；
- 计划的两页布局（左页问题/直觉，右页证据/落地）；
- 请用户决定的 1–3 个问题。

用户只回：`继续` / `改 X` / `停`。不要求用户读草稿。

### 5.4 视觉生产（无 checkpoint）

- 固定画布；**渐进稿版式（D57）**：左页 2×2 四格、Z 字阅读 v1→v2→v3→v4，每格「做法 + 被什么打脸 + 补上了什么」，v4 格标「当前」；右页“答案/证据/验证”（终态设计 + 证据 + 可重跑命令）；
- 文字用学生能懂的中文；术语首次出现给一句白话；
- 所有数字与结论都必须能在 claims 里找到；
- 每条证据必须显式挂到某条候选/claim，不能只放一张截图；
- 至少保留一个 `[未知]` 框，禁止全绿；
- 输出 `spread.html` + `spread.png`。

### 5.5 验证（无 checkpoint）

- 若 claim 有 probe：真跑；
- 若 claim 有 ablation：执行并记录预期红；
- 检查画布：无裁切、无重叠、最小字号不低于既定下限；
- 检查叙事：每个结论有 source/probe/ablation 或 `[unknown]`；
- 检查“反行业答案”：删除所有“高内聚低耦合 / 最佳实践 / 业界通常”式空话；
- 检查术语：至少 3 个关键术语在页内有白话定义。

### 5.6 CP2：Final brief（人审）

`final-brief.md` 必须包含：

- 一条链的结论（3 句以内）；
- `spread.png` 链接 + `claims.yaml` 链接；
- 已跑命令/结果；
- 已知未知；
- 学生可读性检查结果；
- 是否有需要改 30 页设计文档/教程/契约的后续动作。

用户回：`收` / `改 X` / `停`。

### 5.7 学生可读性检查（CP2 前）

找**一个没参与生产的人**（或独立 reviewer），只看 `spread.png`，让他复述：

1. N / 参数是什么；
2. 哪些错误不能重试；
3. 拆掉什么会红。

三项都能说对才算通过；说不出来就改图，不改说明。
另有**三轴质量线**（2026-11-27 追加）：**愿学**（开头有钩子、问题先行）/ **爱学**（有故事感、读完有成就感）/ **能学**（台阶平、术语白话、命令能上手）。终验前按三轴做一轮全面检查/修订。

### 5.8 独立 reviewer（CP2 前）

reviewer 只查三件事：

- claim 有没有证据，参数有没有被当成原则；
- 候选是不是稻草人；
- 学生版有没有术语墙/字太小/证据与结论错位。

reviewer 给 `VERDICT: pass|blocker` + 一句理由；blocker 必须修。

## 6. 角色

- **AI 生产者**：挖证据、写 claim、做视觉、跑验证；
- **独立 reviewer**：事实/逻辑/可读性复核；
- **用户**：CP1 定方向、CP2 终审；不做逐字校对。

## 7. Definition of done

一条链完成，当且仅当：

- [ ] `claims.yaml` 每条 claim 有 source + probe/ablation 或 `[unknown]`；
- [ ] `storyboard.md` 经用户 CP1 通过；
- [ ] `spread.html/.png` 完成，且无裁切/重叠；
- [ ] 所有证据都能挂到 claim/候选；
- [ ] 没有“行业答案”空话；
- [ ] 学生可读性检查通过；
- [ ] reviewer 无 blocker；
- [ ] 用户 CP2 通过；
- [ ] `final-brief.md` 落盘。

## 8. 批量模式（例如“今晚把 4 条链都跑完”）

- 同一晚多条链：**CP1 合并为一份 storyboard brief**，每条链 1 页摘要，一次确认；
- 视觉阶段可以并行，但每条链仍单独跑 5.5 验证；
- **CP2 仍逐链 final brief**；用户可一次回复多条（`收链1/收链2`）。

## 9. 设计文档装配（CP2 之后，不在本 workflow 自动做）

- 每条链产出独立两页 `spread.pdf`（由 `spread.html` 的 print CSS 生成）；
- 默认先出 **`materials/design/decision-growth/design-growth.pdf` 增补卷**，不改旧 30 页 PDF；
- 用户若要求合入主设计文档：由装配步骤替换对应 A 类图页，更新目录/页码，跑 `build_design_doc_30.py` 的同类构建并检查页数；
- 合入前必须再跑一次本链的 probe/ablation，禁止“改完图就直接合”。

## 10. 明确不做

- 不做“评审版 + 学生版”两套（2026-11-26 用户决定）；
- 不自动改契约/代码；只指出“要改什么、怎么验”；
- 不把 N=1 之类当前值伪装成设计原则；
- 不把教学编撰冒充真实历史：生长时间线须带编撰声明（D57）；叙事校对（reconciler）只改叙事、不改源码/源配置，冲突以源码为准并留痕。
