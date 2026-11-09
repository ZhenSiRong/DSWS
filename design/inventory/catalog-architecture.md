# 图集目录草稿 · 01 架构（01–06）

> 作者：T1 / Qoder · 基线 `eea5e75` · 2026-10-29
> 源目录：`design/diagrams/01-architecture/`，每张图三件套：`.mmd` / `.dot`（源）+ `.svg`（渲染）+ `.md`（说明）。

## 总表

| 编号 | 标题 | 类型 | 回答的问题 | 源文件 | SVG | 状态 |
|---|---|---|---|---|---|---|
| 01 | C4-L1 系统上下文 | flowchart TB | DSWS 的系统边界在哪？生产链路读哪些外部系统？ | `01-c4-context.mmd` | `01-c4-context.svg` | ✅ |
| 02 | C4-L2 容器图 | flowchart TB | 一次请求跨哪些容器？S2 构建与 init 在哪？ | `02-c4-container.mmd` | `02-c4-container.svg` | ✅ |
| 03 | backend/app 模块依赖 | Graphviz digraph | 谁 import 谁？构建时与查询时依赖如何分层？ | `03-backend-modules.dot` | `03-backend-modules.svg` | ✅ |
| 04 | 前端文件树 | flowchart LR | 前端谁调用谁？SSE 解析与契约类型住在哪？ | `04-frontend-tree.mmd` | `04-frontend-tree.svg` | ✅ |
| 05 | 阶段演进 S0→S8 | block-beta | 每阶段新增哪类不确定性？可停点是什么？ | `05-stage-evolution.mmd` | `05-stage-evolution.svg` | ✅ |
| 06 | 构建时 vs 查询时 | flowchart LR | S2 退出后，查询各阶段各自读什么？ | `06-build-vs-query.mmd` | `06-build-vs-query.svg` | ✅ |

## 逐张证据

### 01 · C4-L1 系统上下文

- 源文件：`backend/app/main.py` L147 `create_app`、L170/L174/L183/L193/L226 五个端点
- 源文件：`contracts/`（13 个契约文件，✅ 本机 `ls`）
- 证据：`README.md` L195「上下文 8 阶段；可选 S3 召回」
- 证据：`README.md` L232–L238「S2 只写 `*_rebuild`；生产上下文由 `OfflineContextBuilder` 生成」
- 边界：旧系统只以文件夹具存在（🟡）；LLM 端点未联调（⚪）

### 02 · C4-L2 容器图

- 源文件：`compose.yaml` L11–L160（六服务与端口）
- 源文件：`backend/app/main.py` L147–L236；`agent/orchestrator.py` L126/L199
- 源文件：`generate/context.py` L363–L376（8 阶段）；`security/policy.py` L298；`security/executor.py` L161/L226
- 源文件：`build_meta_knowledge.py` L87–L109（CLI 四开关）
- 证据：`README.md` L74–L76（init/backend/frontend 端口与职责）
- 边界：本地 dev 不经 nginx；S3 recall 画在部署边界外（🟡 架构判断）

### 03 · backend/app 模块依赖

- 源文件：`backend/app/**/*.py` 的 AST import 清单（✅ 2026-10-29 本机脚本）
- 源文件：`generate/context.py` L30–L32；`generate/pipeline.py` L192–L206
- 源文件：`agent/orchestrator.py` L43/L126/L199–L214；`security/policy.py` L298；`security/executor.py` L161/L226
- 源文件：`recall/pipeline.py` L35；`recall/nodes.py` L260–L261
- 边界：文件组聚合，逐文件清单见 `software-census.md` §3；`validate → guard/policy` 调用为读码推断（🟡）

### 04 · 前端文件树

- 源文件：`frontend/src/App.tsx` L140–L162、L238–L241、L336–L343
- 源文件：`frontend/src/lib/api.ts` L47/L78/L169/L197/L211/L232
- 源文件：`frontend/src/lib/result.ts` L41/L76/L103；`generated/sse.ts` L69
- 证据：`frontend/src/components/` 5 个组件、`generated/` 3 个生成物（✅ 本机 `ls`）
- 边界：仓库无 `lib/sse.ts`，解析器在 `lib/api.ts`（✅ 本机 `ls`）；浏览器端到端未跑（⚪）

### 05 · 阶段演进 S0→S8

- 源文件：`README.md` L13–L24（S0–S8 阶段表；S8 待做）
- 源文件：`Makefile` L14–L156（`stage0`–`stage7`）
- 源文件：`design/WBS.md` L44–L52（图目录）
- 证据：`contracts/steps.yaml` 12 步；`contracts/errors.yaml` 16 码 / 3 类；注入语料 36 拒 + 11 允许（✅ YAML 解析）
- 边界：S8 灰框=未实现（⚪）；可停点是验收口径，不代表独立交付

### 06 · 构建时 vs 查询时

- 源文件：`build_meta_knowledge.py` L4–L7/L87–L109；`generate/context.py` L94/L392
- 源文件：`agent/orchestrator.py` L43/L214；`security/executor.py` L161/L226；`recall/pipeline.py` L35
- 证据：`README.md` L195、L232–L238；`compose.yaml` L83–L104（init 一次性容器）
- 边界：S3→S4 为可选 `RecallState`（🟡）；S2 实际写入计数未在 Docker 中实测（⚪）

## 编号占用

01–06 已占用；T2 用 07–13，T3 从 14 起，T4 用 25–32。
