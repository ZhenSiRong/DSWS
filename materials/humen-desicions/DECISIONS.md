# 决策记录

> 本目录保存本项目的计划、决策与评审证据。最后更新：2026-11-21（D55）。

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
| D11 | 图表优化范围 | 32 张技术图全量审计，正文引用优先 | `07-figure-comprehension-plan.md` |
| D12 | 图表分轨 | A 可读化（21）/ B 类比横幅（5）/ B1 漫画（6） | 同上 §3 |
| D13 | 可理解性判据 | 三问盲测（2/3）+ 3 张学生抽检 | 同上 §4 |
| D14 | 结构类做法 | 加读图带 + 高亮主路径，不重画 | 同上 §5 |
| D15 | 概念类预算 | 6 张 Lite 漫画，Pro 0；其余加横幅 | 同上 §5 |
| D16 | 文档分类 | 设计文档进 `materials/design/`/`system/contracts/`；过程文档进 `materials/humen-desicions/`/`materials/pilot/`/`system/eval/` | `08-doc-placement.md` |
| D17 | 视频结尾角标 | `DSWS · 验收完成` → `DSWS · 演示完成` | 已完成，commit `89611d9` |
| D18 | 两份文档 | `design-doc.pdf`（32 图 + 地图）与 `dev-book.pdf` 分开；教材图集章改为索引 | `08-doc-placement.md`、`materials/design/design-doc.pdf` |
| D19 | 读图带 | 32 张 SVG 注入“回答什么 + 读图 1→2→3”；design-doc 78 页、dev-book 162 页 | `materials/design/scripts/add_reading_band.py` |
| D20 | 教材重构 | **新写主线练本（9 页起）+ 原书 162 页降为参考书**，两册一起交 | `09-ablation-course.md` §D20 |
| D21 | 练本切法 | 九个"能跑的里程碑"（建表→种子→HTTP→硬编码→抽词→拼SQL→真执行→SSE→界面）；界面可降级附录 | 同上 §D21 |
| D22 | 教学法内核 | **猜 → 造 → 对账**（每页：预测问题 → 动手 → 应见判据 → 对账） | 同上 §D22 |
| D23 | 单页预算 | 1 代码段 ≤40 行 + ≤3 命令 + 1 个"你应该看到" + 1 个"猜" + 1–3 行自改任务 | 同上 §D23 |
| D24 | 代码形态 | 第 1–5 页整段可复制，第 6 页起转 diff | 同上 §D24 |
| D25 | 构建式非部署式 | 禁止以 `compose up -d` 作教学起点；每页必须新增可独立验收的行为 | 同上 §D25 |
| D26 | 36h 分配 | 手册 16 / 演示 10 / 答辩 6 / 缓冲 4；**先花 2h 验证演示链路** | 同上 §D26、`10-three-day-plan.md` |
| D27 | worktree 隔离 | 隔离代码/依赖/运行单元；**数据默认共享**（前提：全链路只读 + 不跑 init） | 同上 §D27 |
| D28 | 六格仪表盘 | 代码/依赖/数据/配置/行为/环境，每格"声明-现场-身份"；只有代码格不同才可归因 | 同上 §D28 |
| D29 | 录制边界 | 演示轨真 LLM、实验轨 **provider 层录制回放**；SSE 夹具不含 prompt，不够回答"为什么" | 同上 §D29 |
| D30 | 运行截图 | 每页至少 1 张由脚本真跑并渲染的 runshot（第 8、9 页各 2 张）；脚本入库可重跑 | `09-ablation-course.md` §D30 |
| D31 | 活动定义/网络图 | 节点=构建活动，验证=活动完成判据；第 2 页改为导入 dw.sql；用单代号网络图（AON/PDM），一份源供手册与答辩 | `09-ablation-course.md` §D31 |
| D32 | AOA 对照 | 主线仍用 AON；双代号只作对照附录（11 事件/10 箭线/0 虚活动），用于讲「为什么选 AON」 | `09-ablation-course.md` §D32 |
| D33 | 教学版本快照 | 11 边界快照 S0–S10、overlay 跳转、先保存才能跳、快照只读不可覆盖；容器/数据回滚需显式确认；验收后实现 | `09-ablation-course.md` §D33 |
| D34 | 封装梯度 | 前 10 页抽象体验（一命令一活动），后续每页对活动减一层封装、永不去完 | `09-ablation-course.md` §D34 |
| D35 | 三段式结构 | 十活动 × 三档 = 30 页；Part I=Lv0（新写）、Part II=Lv1（现有 10 页）、Part III=Lv2（新写）；按档分 Part；难度=独立决策点数 | `09-ablation-course.md` §D35 |
| D36 | 修订优先/命名 | 先修订现有 10 页成体验教程，Lv2 后置（合计 20 页）；`lab` 子命令用具体工作名（起容器/灌数据/起服务…），不用 A 编号 | `09-ablation-course.md` §D36 |
| D37 | 体验判据 | 每页五判据（3 分钟可见结果/可打脸的反直觉点/真截图/心智模型句/可复核）+ 正文代码压到关键 3–5 行、全文件进附录 | `09-ablation-course.md` §D37 |
| D38 | 完备性装置 | C4 三层 + L0 地基条；每层一张「责任×证据」矩阵；三态图例；完备=行/列全覆盖+跨层边通；能力从运行时需求倒推 | `09-ablation-course.md` §D38 |
| D39 | 建成证明交互版 | 中分视图（左全局结构/右多卡矩阵）、等大面积、单文件 HTML 离线可用、data.json 单源、空白/答案态切换、实时完备判定 | `09-ablation-course.md` §D39 |
| D40 | 状态编辑方向 | 卡片三态可编辑（▢→◧→■），结构图徽章由卡片状态派生；判定与印章同步重算；答案态只读 | `09-ablation-course.md` §D40 |
| D41 | 状态粒度 | 真源下沉到「能力格」；节点/槽位/结构图全部派生；顶部徽章只读并显示派生构成 | `09-ablation-course.md` §D41 |
| D42 | 建成证明 v2 | 行=交付物（容器/库表/数据/进程/接口/函数/端点/页面/链路）+ 显式位置 + 每行 1–3 检验点（命令+期望输出）；先样例后全量 | `09-ablation-course.md` §D42 |
| D43 | v2 全量替换 | 海报与交互页都改为直读 `completeness/v2/data.json`；v1 产物归档；交互沿用 D39–D41（检验点级可编辑、行派生、实时判定） | `09-ablation-course.md` §D43 |
| D44 | 四级模型修正 | L1 纵向造件；L2–L4 是横切系统（数据与部署真实性/生成与校验正确性/安全可观测）= 换/审/守；23 页 = 10+4+4+5；证明矩阵改为 12 件 × 横切属性 | `09-ablation-course.md` §D44 |
| D45 | 隐喻换城市 | 主隐喻=城市设施+管网；粒度：建筑=运行单元/窗口=端点/办事员=函数/货架=库表/道路=网络；标题统一「问题+方案」；先样例后全换；房子归档 | `09-ablation-course.md` §D45 |
| D46 | 内容生产计划 | 视觉冻结；级间串行+级内 1 写手 1 验证者；每页 DoD 五项+重放；主线不碰真 LLM；lab CLI 最先做；每级一批验收 | `09-ablation-course.md` §D46 |
| D47 | L2–L4 页面模板 | 六段骨架不变，末段「自己改一下」→「拆一刀」；每级末页为级考核；编号从 page-10 起 | `09-ablation-course.md` §D47 |
| D48 | 写作规范 | 所有 `cd` 用子 shell；每页交稿前整段连续执行；重放必测连续粘贴 | `09-ablation-course.md` §D48 |
| D54 | 工具定义三层 | 原子工具（装一次/一条命令/浏览器输出，换项目可用）· 项目一层命令（make/pytest/curl，可进学生步骤）· 项目夹具脚本（教师/CI 用，不进学生步骤）；p17 撤 `pdb_step_demo.py` 入口改 viztracer/pdb + 项目自带 pytest；附录改工具卡；第 0 页预装 `pipx install viztracer py-spy scalene` | `09-ablation-course.md` §D54；`QA-DECISIONS.md` R8 |
| D55 | 版本与发行 | v1.0.0 = 当前 HEAD `2542d71`；p17 改造后 v1.1.0；新分支 `continue-iterate`；发布包 = manual-24p.zip + 三份 PDF + SHA256 + notes；tag/push/release 由用户执行，lead 只维护决策文档 | `09-ablation-course.md` §D55 |
| D53 | GUI 调试教学 | 三 GIU 路径进附录（VizTracer 时间线 / LangGraph Studio 12 节点 / Chrome DevTools；Zed 配置未实拍）+ CLI 兜底；p17 只加 1 行指针，正文不加图 | `09-ablation-course.md` §D53；`QA-DECISIONS.md` R7 |
| D51 | 装修对象=成熟版原版前端 | L5 装修终点是 `materials/deliverable/v2/original-frontend/`（原版 shopkeeper-agent，React 19 + Tailwind 3.4.17）；教学版重建前端降为脚手架（8080 对照）；拆一刀=成熟版换回 17 行 HTML 仍出 41099.5 | `09-ablation-course.md` §D51 |
| D52 | 执行轨迹可视化 | 左=真前端界面 / 右=同一次真跑的 settrace 行级轨迹；18–25s 慢节奏；资产归 p23（`page-23-exec-trace.*`）；p17 不放此图，改"学习者自录工具"方向；C（pdb 离线）留附录/答辩 | `09-ablation-course.md` §D52；`QA-DECISIONS.md` R6 |
| D50 | 24 页全书：L5「装」体验层 | 不重编号，末尾追加 page-23（第 23 页）；配比 10+4+4+5+1=24；L5 = 第五个横切系统（体验层）只 1 页（装修不改变承重墙）；拆一刀 = 前端换回第 9 页 17 行 HTML，同一问题仍出 41099.5 | `09-ablation-course.md` §D50 |

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
| `07-figure-comprehension-plan.md` | 32 张图的可理解性优化计划（2026-11-09 确认） |
| `08-doc-placement.md` | 设计文档 vs 过程文档的定义与放置规则 |
| `09-ablation-course.md` | **消融实验式教材重构：D20–D29 决策与逻辑**（2026-11-15） |
| `10-three-day-plan.md` | **三天冲刺计划、验收判据、防跑偏机制** |

## 4. 尚未决定

- `MANUAL.pdf` 的具体范围（P1）。
- 181s v1 视频是否长期保留（当前：归档不动）。

---

## 5. 执行状态（2026-11-09）

| 项 | 状态 | 证据 |
|---|---|---|
| 教材改写 | ✅ 211 页 | §2.4 LangGraph/12→10、§2.7 故障八/九、§5 DeepSeek、§3.2 Tailwind；PDF p.56/88/89/98/201 |
| 契约 12→10 | ✅ 机器可校验 | `system/contracts/steps.yaml` 的 `stages`；`system/backend/tests/test_steps_stages.py`；46 passed |
| 一致性测试 | ✅ C1–C6 | `system/eval/conformance/reference-baseline.json`（干净树全绿） |
| 校正实测 | ✅ 5/5 触发后成功 | `system/eval/live-report.json`；单次会失败，已写进教材 |
| Capstone | ✅ 学生修复 4 缺陷后全绿 | `materials/pilot/student-capstone-record.md` |
| 视频 | ✅ 61.27s，含校正段 | `materials/deliverable/v2/DSWS-v2-original-ui-demo.mp4`（30.2–45.2s） |
| 5051 | ✅ 四项能力外部验证通过 | `materials/deliverable/v2/evidence/2026-11-09-5051-smoke.md` |
| 5051 部署 | ⛔ SSH 被拒 | `Permission denied (publickey)` |

**待用户提供**：`root@8.155.135.97` 的 SSH 私钥/密码（用于同步新契约或镜像）；
以及是否允许把新视频与教材推送到 GitHub `main`（README 外链指向 main）。

---

## 6. 决策锚定机制（2026-11-15 起）

- **开工三问**：今天的活对应 `10-three-day-plan.md` 哪一格？服务 A–E 哪条判据？有新想法吗（→ 先进 `09` 的"待决策"，不直接开工）。
- **收工三问**：判据推进了哪条（一行证据）？有没有偏离 D20–D29（写进偏差记录，不改口径）？明天第一件事？
- **跑偏判定**：既挂不上 A–E 判据、也挂不上 D 编号的事 → 立即停手。
- **决策变更**：不删旧条目；新开 D 号并注明"取代 Dxx"。
