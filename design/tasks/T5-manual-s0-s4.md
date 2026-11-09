# T5 · 开发手册 S0–S4（opencode）

## 角色与工作树

你是 DSWS 重建手册的作者之一。工作树：

```text
/home/zhensirong/VM-Share/DSWS-design
```

先读：

1. `design/WBS.md`
2. `design/STYLEGUIDE.md`
3. `design/inventory/facts.md`
4. `docs/SETUP-FROM-SCRATCH.md` §0–§3（S0–S4 的命令、期望输出、故障）
5. `README.md` §当前进度、§快速开始、§核心设计
6. `Makefile` 的 `stage0`–`stage4`
7. `backend/app/main.py`、`agent/orchestrator.py`
8. `backend/app/schema_contract.py`
9. `backend/app/build_meta_knowledge.py`、`build/pipeline.py`、`build/plan.py`
10. `backend/app/recall/pipeline.py`、`recall/nodes.py`
11. `backend/app/generate/pipeline.py`、`generate/guard.py`、`generate/provider.py`
12. `contracts/schema.contract.yaml`、`steps.yaml`

## 目标

写出一份「新手能照着做、评审者能顺着查」的 S0–S4 手册。不是命令清单，而是每一步都回答：

> 这个阶段要消灭哪个不确定性？实体是谁？输入是什么？输出写到哪？查询时还在不在场？怎么证明它真的成立？

## 必须产出

`design/book/chapters/10-s0-s4.md`，9,000–12,000 汉字（不含代码）。结构：

```markdown
# 第二部分 · S0–S4：从骨架到生成

## 0. 这一部分的地图
（一张表：阶段 / 新增能力 / 新增不确定性 / 可停点 / 前置）

## 1. S0 · 先让管道跑通
### 1.1 问题
### 1.2 实体与边界
### 1.3 输入
### 1.4 动作（真实命令 + 代码路径）
### 1.5 输出
### 1.6 验收（命令、期望输出、失败含义）
### 1.7 常见故障
### 1.8 证据
### 1.9 检查清单

## 2. S1 · 契约是唯一事实源
（同上 9 小节）

## 3. S2 · 构建元知识
（同上；必须讲清「一次性 CLI，不是常驻进程」；用 `dim_region.region_name` 与 `fact_order.order_amount` 两个真实例子）

## 4. S3 · 检索
（同上；必须讲清 ES / Qdrant / Meta 各自负责什么，20 题黄金集）

## 5. S4 · 生成 SQL
（同上；必须讲清确定性生成器 vs LLM、输出 schema、guard 静态校验、correct_sql 条件执行）

## 6. 走到这里，系统能做什么、还不能做什么
（明确 S5 才补安全执行，S6 才补失败通道）
```

## 写作要求

- 每阶段开头用 3–5 句话讲「为什么需要这个阶段」，再讲怎么做。
- 命令必须来自 `Makefile` / `docs/SETUP-FROM-SCRATCH.md`，逐字准确。
- 期望输出必须给真实计数：5 / 24 / 6 / 9 / 76 / 98 / 22；写清哪些是 ✅ 实测、哪些是 🟡 推导。
- 每个阶段至少一张表：输入/输出/证据。
- 每个阶段至少一个「故障 → 先查什么 → 怎么修」表。
- 代码引用写 `路径:函数名`，不要贴大段源码；关键 5–15 行可以贴。
- 图引用使用相对路径，例如 `![图 08 · S2 构建流水线时序](../diagrams/02-runtime/08-s2-build-sequence.svg)`；图会在最终组装时存在。
- 不编造「已跑通」；本机 Docker 无权限、无 LLM 端点的地方标 ⚪。
- 结尾给 8–12 道复习题（不要答案，答案放附录或下一章）。

## 约束

- 只写 `design/book/chapters/10-s0-s4.md`。
- 不要改源码、契约、其他章节。
- 中文教学语气；先问题后命令；比喻必须能落回真实表名/计数/错误码。
- 不要复制整篇 `SETUP-FROM-SCRATCH.md`；要提炼「为什么」和「怎么判断」。

## 验收

- 文件存在，字数 ≥9,000 汉字。
- S0–S4 每阶段都有 9 个小节。
- 所有命令能在 `Makefile` 找到。
- 所有计数与 `facts.md` 一致。
- 至少引用 6 张图，路径指向 `design/diagrams/**`。
