# 章节 → 代码映射（WBS 2.1）

> 用途：任何一条教材断言，都能回到至少一个 `file:line`。

| 章节 | 主题 | 主要代码 / 契约 | 关键证据 |
|---|---|---|---|
| `00-front.md` | 全书导读、三个根因、S0–S8 地图 | `contracts/*.yaml`、`docs/S7-HANDOFF.md`、`fixtures/sse/*` | 根因对应阶段表；图 3-0 |
| `10-s0-s4.md` | S0 骨架、S1 契约、S2 元知识、S3 检索、S4 生成 | `backend/app/schema_contract.py`、`backend/app/recall/*`、`backend/app/generate/*` | `make stage0..stage4`；`tests/recall/golden.yaml` |
| `20-s5-s8.md` | S5 安全、S6 失败通道、S7 前端、S8 生产化 | `backend/app/security/*`、`backend/app/agent/*`、`frontend/src/*` | `make stage5..stage8`；`contracts/errors.yaml` |
| `30-atlas.md` | 设计图集 | `diagrams/**/*.svg` | 图中节点/边与契约一致 |
| `40-ops.md` | 部署与运维 | `compose.yaml`、`Dockerfile*`、`scripts/*` | `docker compose up` + smoke |
| `90-appendix.md` | 错误码、步骤、SSE、约定 | `contracts/steps.yaml`、`errors.yaml`、`sse.schema.json` | `contracts_gen --check` |

## 本轮新增/修改

| 位置 | 改动 | 依据 |
|---|---|---|
| `20-s5-s8.md` §2.4 | 新增「图结构：12 个节点怎么落成 LangGraph」+ 12→10 表 | `backend/app/agent/graph.py:428`；`tests/test_s6_langgraph.py:96` |
| `20-s5-s8.md` §2.7 | 新增故障八（单次≠已修复）、故障九（拒绝层不固定） | `eval/live-report.json` |
| `10-s0-s4.md` §5 | 新增 DeepSeek/OpenAI 兼容接入与三个环境变量 | `backend/app/generate/provider.py:180` |
| `20-s5-s8.md` §3.2 | 新增 React 19 + Tailwind 界面栈说明 | `frontend/package.json`、`frontend/src/styles.css` |
| `90-appendix.md` 表 B-1 | 增加「阶段」列，标注 12→10 | `contracts/steps.yaml` |
| `contracts/steps.yaml` | 新增 `stages` 与每节点 `stage` | 本表 + `test_steps_stages.py` |
| `backend/tests/test_steps_stages.py` | 新增契约测试：不重不漏 | 同上 |
