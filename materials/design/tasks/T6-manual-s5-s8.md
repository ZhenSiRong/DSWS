# T6 · 开发手册 S5–S8（codebuddy）

## 角色与工作树

你是 DSWS 重建手册的作者之一。工作树：

```text
/home/zhensirong/VM-Share/DSWS-design
```

先读：

1. `design/WBS.md`
2. `design/STYLEGUIDE.md`
3. `design/inventory/facts.md`
4. `docs/SETUP-FROM-SCRATCH.md` §2.8–§2.10、§3
5. `Makefile` 的 `stage5`–`stage7`、`stage5-live`、`stage6-ui`、`stage7-ui`
6. `backend/app/security/policy.py`、`executor.py`、`pipeline.py`
7. `backend/app/agent/correct.py`、`agent/errors.py`、`agent/cancel.py`
8. `contracts/sql.policy.yaml`、`errors.yaml`、`sse.schema.json`
9. `backend/app/main.py`、`backend/app/scenarios/app.py`
10. `frontend/src/App.tsx`、`components/*`、`lib/*`
11. `README.md` §核心设计、§必须知道的约束

## 目标

写出 S5–S8 的手册：安全边界、失败通道、前端收口、生产化。每一阶段都要回答「新增了什么不确定性、怎么证明它被消灭」。

## 必须产出

`design/book/chapters/20-s5-s8.md`，9,000–12,000 汉字（不含代码）。结构：

```markdown
# 第三部分 · S5–S8：从能跑到敢用

## 0. 这一部分的地图
（阶段 / 新增能力 / 新增不确定性 / 可停点 / 前置）

## 1. S5 · 安全边界
### 1.1 问题：为什么 S4 的 SQL 不能直接执行
### 1.2 实体与边界：策略、执行器、账号
### 1.3 输入：SQL 文本 + 契约 + 策略
### 1.4 动作：AST 解析 → 策略判定 → 只读执行
### 1.5 输出：放行 / 拒绝 / 执行错误
### 1.6 验收：注入语料 100% 拒绝、零误杀、只读账号写不了
### 1.7 常见故障
### 1.8 证据
### 1.9 检查清单

## 2. S6 · 失败通道
（同上；必须讲清 16 个错误码、3 个 class、retryable、校正闭环只重试一次、取消不是 done）

## 3. S7 · 前端收口
（同上；必须讲清契约生成物、SSE 三种事件、StepRail 的 skipped、ErrorCard 的三种渲染、类型保真 Decimal）

## 4. S8 · 生产化（边界与下一步）
（不是已实现清单；讲清 Docker、健康检查、隔离、可观测性、容量、权限、未验证边界）

## 5. 走到这里，系统能做什么、还不能做什么
（明确哪些是 ✅ 已验证、哪些是 🟡 推断、哪些是 ⚪ 未验证）

## 6. 复习题
（8–12 道，不要答案）
```

## 写作要求

- 每阶段开头讲「上一阶段留下了什么风险」，再讲本阶段怎么补。
- 命令必须来自 `Makefile` / `docs/SETUP-FROM-SCRATCH.md`，逐字准确。
- S5 必须给至少 3 条真实注入 SQL 与判定结果（从 `fixtures/injection/` 或 `security/corpus.py` 取），并说明为什么被拒。
- S6 必须给 16 个错误码的完整表：code / class / retryable / UI 表现。
- S7 必须给 SSE 事件样例（progress / result / error 各一条）和前端状态迁移。
- S8 不要吹牛：Docker 全栈本机未跑，标 ⚪；782 tests 是 README 声称，标 🟡。
- 图引用用相对路径，例如 `![图 21 · 五层防御纵深](../diagrams/04-security/21-defense-in-depth.svg)`。
- 代码引用写 `路径:函数名`；关键 5–15 行可以贴。

## 约束

- 只写 `design/book/chapters/20-s5-s8.md`。
- 不要改源码、契约、其他章节。
- 中文教学语气；先问题后命令；比喻必须能落回真实表名/计数/错误码。
- 不要复制整篇 `SETUP-FROM-SCRATCH.md`。

## 验收

- 文件存在，字数 ≥9,000 汉字。
- S5–S8 每阶段都有完整小节。
- 16 个错误码全部出现，class/retryable 与契约一致。
- 至少引用 6 张图，路径指向 `design/diagrams/**`。
