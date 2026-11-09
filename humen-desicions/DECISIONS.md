# 决策记录

> 本目录保存本项目的计划、决策与评审证据。最后更新：2026-11-09。

## 1. 已批准的决定

| # | 决定 | 取值 | 依据 |
|---|---|---|---|
| D1 | 教材验收口径 | 一致性测试（C1–C6），不按代码相似度 | `04-course-workflow.md` |
| D2 | 学生起点 | 修复型 starter + capstone | `04-course-workflow.md` |
| D3 | 今晚学生任务 | **只做 capstone**，6 个章节任务移出 | `06-wbs-and-agents.md` §5 |
| D4 | 视频 | 不整片重录；**方案 A**：把校正成功段插入 46s README 视频 | `06-wbs-and-agents.md` §6 |
| D5 | 5051 更新 | 允许 2–3 分钟重启，先备份可回滚 | `04-course-workflow.md` |
| D6 | 教材补充 | 补 LangGraph 图结构与「12 节点 → 10 步」映射 | `04-course-workflow.md` |
| D7 | 开发手册 | 后续单独出 `MANUAL.pdf`（P1） | `06-wbs-and-agents.md` |
| D8 | 资源配置 | 2 学生 + 1 构建；Lite 12 张；Pro 0 张 | `05-resource-plan.md` |
| D9 | 人工评审 | 2 次：资源方案 + 终审 | `05-resource-plan.md` |
| D10 | WBS 粒度 | 47 个工作包，够用 | `06-wbs-and-agents.md` |

## 2. 评审证据

- `decision-05-resource.json`：资源方案 `approved`，0 条批注。
- `decision-06-wbs.json`：WBS 批注 1 条，选择视频方案 **A**。

## 3. 文件索引

| 文件 | 内容 |
|---|---|
| `02-figure-validation-pipeline.md` | 插图生产与验证流程 |
| `02-flow-main.mmd` | 主流程图 |
| `02-flow-tools.mmd` | 工具选择决策树 |
| `02-flow-student.mmd` | 学生验证流程 |
| `04-course-workflow.md` | 七阶段总流程与一致性测试设计 |
| `05-resource-plan.md` | 资源/工具利用方案（已批准） |
| `06-wbs-and-agents.md` | WBS + Agent 分工 + RACI（终版） |

## 4. 尚未决定

- `MANUAL.pdf` 的具体范围（P1）。
- 181s v1 视频是否长期保留（当前：归档不动）。

---

## 5. 执行状态（2026-11-09）

| 项 | 状态 | 证据 |
|---|---|---|
| 教材改写 | ✅ 211 页 | §2.4 LangGraph/12→10、§2.7 故障八/九、§5 DeepSeek、§3.2 Tailwind；PDF p.56/88/89/98/201 |
| 契约 12→10 | ✅ 机器可校验 | `contracts/steps.yaml` 的 `stages`；`backend/tests/test_steps_stages.py`；46 passed |
| 一致性测试 | ✅ C1–C6 | `eval/conformance/reference-baseline.json`（干净树全绿） |
| 校正实测 | ✅ 5/5 触发后成功 | `eval/live-report.json`；单次会失败，已写进教材 |
| Capstone | ✅ 学生修复 4 缺陷后全绿 | `pilot/student-capstone-record.md` |
| 视频 | ✅ 61.27s，含校正段 | `deliverable/v2/DSWS-v2-original-ui-demo.mp4`（30.2–45.2s） |
| 5051 | ✅ 四项能力外部验证通过 | `deliverable/v2/evidence/2026-11-09-5051-smoke.md` |
| 5051 部署 | ⛔ SSH 被拒 | `Permission denied (publickey)` |

**待用户提供**：`root@8.155.135.97` 的 SSH 私钥/密码（用于同步新契约或镜像）；
以及是否允许把新视频与教材推送到 GitHub `main`（README 外链指向 main）。
