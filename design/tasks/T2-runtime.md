# T2 · 运行时 / 时序图（codebuddy）

## 角色与工作树

你是 DSWS 重建项目的设计图集作者之一。工作树：

```text
/home/zhensirong/VM-Share/DSWS-design
```

先读：

1. `design/WBS.md`
2. `design/STYLEGUIDE.md`
3. `design/inventory/facts.md`
4. `backend/app/main.py`
5. `backend/app/agent/orchestrator.py`
6. `backend/app/build_meta_knowledge.py`、`backend/app/build/pipeline.py`
7. `backend/app/recall/pipeline.py`、`backend/app/recall/nodes.py`
8. `backend/app/generate/pipeline.py`、`backend/app/generate/guard.py`
9. `backend/app/security/pipeline.py`、`backend/app/security/executor.py`
10. `contracts/steps.yaml`、`contracts/errors.yaml`、`contracts/sse.schema.json`

## 目标

产出 7 张运行时图，回答「一次请求/一次构建，谁在什么时候把什么交给谁」。

## 必须产出

目录：`design/diagrams/02-runtime/`

| 编号 | 文件 | 类型 | 内容要求 |
|---|---|---|---|
| 07 | `07-end-to-end-request.mmd` | sequenceDiagram | 浏览器 → FastAPI → AgentRunner → recall → generate → validate → security → MySQL → SSE；标出成功、空结果、失败、取消四条收尾 |
| 08 | `08-s2-build-sequence.mmd` | sequenceDiagram | `make stage2` → CLI → plan → Meta → ES → Qdrant → manifest → exit；标出 `--dry-run` / `--fresh` / `--verify` / `--assert-idempotent` 四个开关 |
| 09 | `09-s3-recall-sequence.mmd` | sequenceDiagram | 关键词 → ES 取值召回 → Qdrant 列/指标召回 → Meta 取详情 → 合并 → 过滤；标出 76 / 98 / 22 三个计数 |
| 10 | `10-s4-generate-sequence.mmd` | sequenceDiagram | 上下文 8 阶段 → 生成器（确定性 / LLM）→ 输出 schema 校验 → guard 静态校验；标出 `correct_sql` 的条件性 |
| 11 | `11-s5-security-sequence.mmd` | sequenceDiagram | SQL 文本 → 策略判定 → 只读执行器 → 结果/错误；标出拒绝、超时、执行错误三个出口 |
| 12 | `12-s6-correction-state.mmd` | stateDiagram-v2 | 初始 → 生成 → 校验 → [可重试] 校正一次 → 再校验 → 执行 → result / error；标出 `retryable=false` 直接终止 |
| 13 | `13-s7-sse-sequence.mmd` | sequenceDiagram | 后端 `progress`/`result`/`error` → 前端 `StepRail` / `ResultTable` / `ErrorCard`；标出 `skipped` 与 `cancelled` 的 UI 语义 |

每张图配同名 `.md` 说明（模板见 `STYLEGUIDE.md` §7），必须写：

- 参与者是谁（真实进程/类名）。
- 正常路径、失败路径、取消路径分别在哪一步分叉。
- 证据：文件 + 行号/函数名；命令输出标 ✅/🟡/⚪。

### 目录草稿

`design/inventory/catalog-runtime.md`：07–13 的编号、标题、问题、源文件、SVG、证据、状态。

### 交接

`design/inventory/handoff-T2.md`：产出清单、渲染命令、未决问题、读过的文件。

## 约束

- 只写 `design/inventory/` 与 `design/diagrams/02-runtime/`。
- 不要改源码、契约、文档。
- Mermaid 时序图参与者用真实名字：`Browser`、`FastAPI`、`AgentRunner`、`RecallPipeline`、`Generator`、`Guard`、`ReadOnlyExecutor`、`MySQL`、`ES`、`Qdrant`、`LLM`。
- 不要把所有分支塞进一张图；每张图只讲一条主线 + 两个关键分叉。
- 计数必须与 `facts.md` 一致。

## 验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/02-runtime/*.svg
```

7 个 SVG 全部生成；每张 `.md` 都能指到至少 2 个真实文件/函数。
