# 图集目录草稿 · 02 运行时（07–13）

> 作者：T2 / codebuddy · 基线 `eea5e75` · 2026-10-29
> 源目录：`design/diagrams/02-runtime/`，每张图三件套：`.mmd`（源）+ `.svg`（渲染）+ `.md`（说明）。

## 总表

| 编号 | 标题 | 类型 | 回答的问题 | 源文件 | SVG | 状态 |
|---|---|---|---|---|---|---|
| 07 | 端到端请求生命周期 | sequenceDiagram | 一次问数里谁把什么交给谁？失败/空结果/取消在哪分叉？ | `07-end-to-end-request.mmd` | `07-end-to-end-request.svg` | ✅ |
| 08 | S2 构建流水线时序 | sequenceDiagram | 谁读契约、谁写三存储、四个开关各改变什么？ | `08-s2-build-sequence.mmd` | `08-s2-build-sequence.svg` | ✅ |
| 09 | S3 召回流水线时序 | sequenceDiagram | 三存储各被问几次？候选怎么合并、怎么被裁掉？ | `09-s3-recall-sequence.mmd` | `09-s3-recall-sequence.svg` | ✅ |
| 10 | S4 生成 SQL 流水线 | sequenceDiagram | 上下文怎么进提示词？两道校验为什么是这个顺序？ | `10-s4-generate-sequence.mmd` | `10-s4-generate-sequence.svg` | ✅ |
| 11 | S5 安全校验与执行 | sequenceDiagram | 策略在哪查两次？拒绝/超时/执行错误三个出口怎么分？ | `11-s5-security-sequence.mmd` | `11-s5-security-sequence.svg` | ✅ |
| 12 | S6 校正闭环状态机 | stateDiagram-v2 | 什么时候走 `correct_sql`？哪些失败不可重试？ | `12-s6-correction-state.mmd` | `12-s6-correction-state.svg` | ✅ |
| 13 | S7 SSE 事件序列 | sequenceDiagram | 三种事件怎么落到三个组件？`skipped`/`cancelled` 长什么样？ | `13-s7-sse-sequence.mmd` | `13-s7-sse-sequence.svg` | ✅ |

## 逐张证据

### 07 · 端到端请求生命周期

- 源文件：`backend/app/main.py`（L207 `query`、L227 `cancel`、L250 `_sse`、L262 `_stream`）
- 源文件：`backend/app/agent/orchestrator.py`（L199 `events`、L211 `_run`、L365–L389 收尾）
- 源文件：`backend/app/generate/context.py`（L363 `phases`）
- 证据：8 阶段与 `contracts/steps.yaml` 前 8 项逐条对齐（✅ 读码）
- 证据：同步生成器跑在工作线程 + 队列（✅ `main.py` L272–L294）
- 边界：生产路径用 `OfflineContextBuilder`，**不访问** ES/Qdrant；三存储召回见 09（✅ 读码，容易误判）

### 08 · S2 构建流水线时序

- 源文件：`Makefile` L39–L45；`backend/app/build_meta_knowledge.py` L87–L131
- 源文件：`backend/app/build/pipeline.py` L196–L305（写序 L263–L284）
- 证据：`uv run --frozen python -m app.build_meta_knowledge --dry-run` → 5/24/6/9、76、98、22（✅ 2026-10-29 本机）
- 证据：写入合计 241（🟡 由 `counts()` 公式推导，未 `--fresh` 实测）
- 边界：`--fresh` 未跑（⚪ 本机 Docker socket 无权限）

### 09 · S3 召回流水线时序

- 源文件：`backend/app/recall/pipeline.py` L35–L118
- 源文件：`backend/app/recall/nodes.py` L44–L47（限额）、L143/L239/L260/L285/L404/L582/L751/L810（8 节点）
- 证据：计数 76 / 98 / 22 与 `facts.md` §5 一致（✅ dry-run 输出）
- 证据：实际顺序是「列 → 取值 → 指标」，且 `load_snapshot()` 在最前（✅ `pipeline.py` L66–L78）
- 边界：真实命中率未测（⚪ 需三存储）

### 10 · S4 生成 SQL 流水线

- 源文件：`backend/app/generate/pipeline.py` L72–L177
- 源文件：`backend/app/generate/provider.py` L109–L124（7 槽位）、L138（确定性生成器）
- 源文件：`backend/app/generate/guard.py` L151–L310；`backend/app/agent/validate.py` L31
- 证据：形状校验（`output_schema.validate_payload`）先于静态校验（✅ `pipeline.py` L112–L133）
- 证据：`max_attempts: 1`（✅ `contracts/errors.yaml`）
- 边界：真实 LLM 未跑（⚪）

### 11 · S5 安全校验与执行

- 源文件：`backend/app/security/executor.py` L226 `execute`、L243 `_run`、L218 `_prepare_session`、L136 `_map_error`
- 源文件：`backend/app/security/policy.py` L298 `enforce`
- 证据：策略拒绝时**不连库**（✅ `executor.py` L229–L241）
- 证据：两次 `enforce()`（✅ `validate.py` L56–L70 + `executor.py` L228）
- 边界：真实超时行为未测（⚪）

### 12 · S6 校正闭环状态机

- 源文件：`backend/app/agent/orchestrator.py` L282、L305–L340、L365–L415、L417–L441
- 源文件：`backend/app/agent/errors.py` L292 `retryable`
- 证据：唯一的回退边 `校验 → 校正 → 校验`，最多 1 次（✅ 读码）
- 证据：`retryable=false` 直接终止（✅ `orchestrator.py` L305）
- 边界：一次真实校正往返未跑（⚪ 需 LLM）

### 13 · S7 SSE 事件序列

- 源文件：`contracts/sse.schema.json`（3 种事件、`progress.status` 4 值、`error.class` 3 值）
- 源文件：`frontend/src/App.tsx` L141–L176；`StepRail.tsx` L33–L57；`ResultTable.tsx` L46；`ErrorCard.tsx` L32
- 证据：`skipped` 由 `_skip_correct()` 显式补发（✅ `orchestrator.py` L168–L180）
- 证据：取消不是 done（✅ `App.tsx` L171–L175、L210–L217）
- 边界：浏览器渲染未验收（⚪）；`ResultTable` 的 0 行分支在生产路径不可达（✅ 读码）

## 编号占用

07–13 已占用；T3 从 14 起，T1 用 01–06，T4 用 25–32。
