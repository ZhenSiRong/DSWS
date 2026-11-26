# A 类设计文档 · 决策生长（5 链渐进稿）

> 2026-11-27 生产；按 `toolbox/workflows/design-doc-growth.md` 与 **D56/D57**（`materials/humen-desicions/15-design-growth-doc.md`）。
> 版式：左页 2×2 v1→v4「做法 → 被什么打脸 → 补上了什么」（v4=当前）+ 编撰声明；右页终态设计 + 证据 + 可重跑命令。
> 不是"评审版 + 学生版"两套；每链只有一份两页文档。

## 五条链

| 链 | 文档 | PDF | Claims | 状态 |
|---|---|---|---|---|
| 纠错 | [correction/spread.png](correction/spread.png) | [correction/spread.pdf](correction/spread.pdf) | [correction/claims.yaml](correction/claims.yaml) | R5+R6 pass / 学生「能学」 |
| 安全 | [security/spread.png](security/spread.png) | [security/spread.pdf](security/spread.pdf) | [security/claims.yaml](security/claims.yaml) | R5+R6 pass / 学生「能学」 |
| 契约 | [contract/spread.png](contract/spread.png) | [contract/spread.pdf](contract/spread.pdf) | [contract/claims.yaml](contract/claims.yaml) | R5+R6 pass / 学生「能学」 |
| 运行 | [runtime/spread.png](runtime/spread.png) | [runtime/spread.pdf](runtime/spread.pdf) | [runtime/claims.yaml](runtime/claims.yaml) | R5+R6 pass / 学生「能学」 |
| 用户旅程 | [journey/spread.png](journey/spread.png) | [journey/spread.pdf](journey/spread.pdf) | [journey/claims.yaml](journey/claims.yaml) | R5+R6 pass / 学生「能学」 |

审查记录见 [review.md](review.md)：对抗线 R5+R6 连续两轮 0 blocker（R1 BLOCKER(7) → R2 BLOCKER(10) → R3 PASS → R4 BLOCKER(1) → R5/R6 PASS）；学生线三轮（勉强 → 能学 → 能学）。probe 真栈补验 6 条转正、4 条缺口如实标注（2026-11-27）。

每链另有：`data.yaml`（生成器数据源）、`claims.md`（人读 claim 表）、`storyboard.md`（CP1 brief）、`final-brief.md`（CP2 brief）。

## 生产与验证工具

- `materials/design/scripts/make_decision_growth.py [--render]`：从 data.yaml 渲染 spread.html/png/pdf
- `materials/design/scripts/check_spread.py`：画布溢出/裁切/乱码/截断程序化检查（模型看不了图，以 DOM 度量代替目测）
- `materials/design/scripts/build_design_doc_growth.py`：组版整份设计文档 PDF（≥30 页，不含 B/C 类页，D56）

## 生产时实际验证（节选）

- 安全：`security --check` → 36/36 拒绝 / 11/11 放行 / 8/8 基线；`make stage5` → 813 passed / 30 skipped。
- 契约：`schema_contract --check` → S1 PASS；dry-run → 5/24/6/9、ES 76、Qdrant 98+22、0 writes。
- 运行：`docker compose config --quiet` → 0；2s/180s 条件轮询为 [当前值]。
- 纠错：`failures --check` → S6 PASS、16 码；`test_correct.py` → 14 passed。
- 旅程：12 节点/10 步与 steps.yaml 对账；backend 9 passed、frontend 40 passed、tests/security 179 passed / 2 skipped。

## 编撰声明（D57）

各链 v1→v4 的生长叙事是**教学重构**，不是 commit 历史或逐日日记；终态结论由右页代码/契约/真跑证据锚定。
后续 **reconciler** 只改叙事使其自恰、不改源码/源配置；叙事与源码冲突时以源码为准并留痕。

## 明确不做

- B/C 类图不入卷（D56）；不改 30 页旧主文档正文。
- 不把 `max_attempts: 1`、2s/180s、阈值 1000 等当前值写成设计原则。
- 不用"行业惯例/最佳实践"填补证据缺口；缺的照实标 `[未知]`。
