# 今晚总计划：教材收口 → 学生复现 → 视频 → 5051 对齐

## 0. 一句话目标

用一本 **PDF-only 就能照着做** 的教材，把学生带到「能复现 `ZhenSiRong/DSWS` 的核心行为」；
以 **SQL 校正准确性** 为第一判据；然后用同一套系统重录演示视频，并把 `5051` 更新到与 PRD 一致。

「相差无几」不按代码相似度判，按 **同一套一致性测试的通过集合** 判。

---

## 1. 已核实的事实基线（本次只读勘察）

| 项 | 事实 | 证据 |
|---|---|---|
| 参考仓库 | `git@github.com:ZhenSiRong/DSWS.git`，当前分支 `design/atlas` | `git remote -v` |
| 工作流 | 真实 `langgraph.graph.StateGraph`，12 个节点与 `contracts/steps.yaml` 完全一致 | `backend/app/agent/graph.py`、`backend/tests/test_s6_langgraph.py:96` |
| 校正闭环 | `correct_sql` 最多 **1** 次；校正后必须重过 `guard` + `policy` | `contracts/errors.yaml:42-48` |
| 安全策略 | 36 条注入全拒、11 条零误杀、8 条 S4 基线 | 学生实测 `make stage5` |
| 前端 | 重建版与线上原版均为 React 19；线上原版 Tailwind 3.4.17 | `frontend/package.json`、`deliverable/v2/original-frontend/package.json` |
| 5051 | nginx + docker compose；`/api/health` 200，`/api/steps` 返回 12 节点；构建于 2026-11-06 | `curl` |
| LLM | `REBUILD_LLM_BASE_URL / _API_KEY / _MODEL`，兼容 DeepSeek | `backend/app/generate/provider.py:180-193`、README:119 |
| 本地 Key | `DEEPSEEK_API_KEY` 在 `~/.bashrc`（未导出到当前进程） | `grep ~/.bashrc` |
| 教材 | 207 页；`correct_sql` 出现 51 次，`validate_sql` 28 次；**`LangGraph` 出现 0 次** | `pdftotext` |
| 视频 | 现有 46s / 1080p / 30fps，README 用 jsDelivr 外链 | `deliverable/v2/` |
| PRD | 「12 节点 / 10 步」是 PRD 口径；仓库只有 12 节点，没有「10 步」的契约化定义 | `prd.md:7` |

**由此得到两个真缺口：**

1. 教材没教 LangGraph 的图结构，也没把「12 节点 → 10 步」讲清楚；学生照书做，最多做出等价的自研编排。
2. 「学生成果 ≈ 仓库」目前没有任何统一判据，只有人工感觉。

---

## 2. 验收口径：一致性测试（Conformance Suite）

新建 `eval/conformance/`，对 **参考实现** 与 **学生产物** 跑同一套测试。

| 组 | 内容 | 通过线 | 权重 |
|---|---|---|---|
| C1 契约 | `/api/steps` 12 个 id 逐字一致；SSE 12 节点齐全；`correct_sql` 可 skipped；16 个通道码齐全 | 100% | 必过 |
| C2 问数 | 30 条黄金问题（8 条召回黄金集 + 10 条 S4 基线 + 12 条新增） | 结果集等价 ≥90%，拒答码精确 | 高 |
| C3 校正 | 20 条注入故障，覆盖 6 类（列名/表名/语法/别名/不安全构造/类型） | 修好并重校验 ≥80%；0 次越权执行；尝试 ≤1 次 | **最高** |
| C4 安全 | 36 条注入语料 + 11 条零误杀 + 8 条基线 | 100% | 必过 |
| C5 前端 | 构建通过；问数表格、拒绝错误卡两条主流程 | 2/2 | 中 |
| C6 部署 | `docker compose up` 后 health / steps / 一次真实问数 | 全绿 | 中 |

**「相差无几」判定**：C1、C4 必须 100%；C2 ≥90%；C3 ≥80%；C5、C6 全绿；且与参考实现的通过集合差异 ≤1 条。

### C3 校正专项（重点）

| 类别 | 例子 | 期望 |
|---|---|---|
| 未知列 | `fact_order.amount` | 改回 `order_amount` |
| 未知表 | `fact_sales` | 改回 `fact_order` |
| 语法错 | 缺 `)` / 错关键字 | 语法修复 |
| 别名错 | `ORDER BY 销售额` 但未定义 | 解析到投影别名 |
| 不安全构造 | `UNION` / 多语句 | **不校正，直接拒绝**（这是安全性，不是可修复错误） |
| 类型/空值 | `Decimal` 参与字符串拼接 | 保持类型保真或拒答 |

指标：`规则命中 → correct_sql 被真实触发 → 重校验通过 → 执行成功`。
同时记录 `original_sql / corrected_sql / attempts / 最终 error`，失败必须能归因。

---

## 3. 七个阶段（含工具与门禁）

| 阶段 | 任务 | 工具 | 门禁 / 产出 | 回退 |
|---|---|---|---|---|
| **P0 冻结基线** | 锁定 main commit、契约、黄金集、5051 现状；把 `DEEPSEEK_API_KEY` 映射到 `REBUILD_LLM_*` | shell + `git` + `curl` | `eval/baseline.json`：参考实现跑出的 C1–C6 结果 | 基线不绿，先修环境不写教材 |
| **P1 教材审计** | 逐章抽取事实断言，回查 `file:line`；标出「书里有、代码没有」和「代码有、书里没有」 | `Grep/Read` + `pdftotext` | 缺口表（严重度 + 修法 + 验收点） | 有争议条目挂起，先不改 |
| **P2 教材改写** | 补 LangGraph 图结构、12→10 分组、校正闭环、DeepSeek 接入、前端与部署 | `Edit` + `make_figure.sh` | 每章「事实可回溯」清单；图过自动门禁 + 逐字复核 | 按章节回滚 |
| **P3 学生验证** | 6 个章节任务 + 1 个修复型 capstone；PDF-only、独立 worktree、hy3 low | CodeBuddy + worktree | 任务报告 + 协调方独立复跑 + C1–C6 | 卡点归因：教材/环境/学生 |
| **P4 视频** | 3+1 场景重录：GMV、排名、UNION 拒绝、**校正回环** | Playwright + Chrome + ffmpeg | 1080p60 MP4 ≤60s + GIF ≤8MB；与真实 SSE 对齐 | 保留旧视频 |
| **P5 5051 对齐** | 备份 → 构建 → 重启 → 冒烟 → 回滚预案 | `ssh` + `docker compose` | C1/C2/C3/C4/C6 在线通过 | 旧镜像 tag 回滚 |
| **P6 交付** | 设计文档 ≥30 页、源码 1 套、开发手册 1 套；回归 | 构建 + `git status` | 交付清单逐项勾选 | 未过项显式标注 |

### P2 具体改动（按缺口排序）

1. 新增「LangGraph 图」一节：`StateGraph`、12 节点、条件边 `validate_sql → run_sql / correct_sql / END`、`correct_sql → validate_sql`。
2. 把「12 节点 / 10 步」写成显式映射表（哪 10 步、哪些节点合并），并落进 `contracts/steps.yaml` 的 `stage` 字段。
3. 校正闭环单独成节：为什么最多 1 次、为什么必须重校验、为什么安全拒绝不参与校正。
4. 补 DeepSeek/OpenAI 兼容接入与「无 Key 时显式 skipped」。
5. 前端：React 19 + Tailwind，聊天式提问 + 结果表格 + 错误卡。
6. 部署：5051 的 compose 拓扑与冒烟命令。

### P3 学生验证协议

- 每个任务：新建 worktree，PDF 副本放 `/tmp` 独立目录，`--add-dir` 只授权该目录。
- 基线 `hy3 --effort low`；capstone 追加一次 `medium` 对照。
- 协调方必须**独立复跑**学生声称的命令，不采信自述。
- 失败归因三选一：教材缺前提 / 环境问题 / 学生能力；只有「教材」才改书。

### P4 视频脚本（建议）

| 场景 | 画面重点 | 旁白/字幕 |
|---|---|---|
| 1 GMV 问数 | 12 节点依次 running→success，5 行真实数据 | 「一句中文，12 个节点，一条真 SQL」 |
| 2 商品排名 | `correct_sql skipped` | 「不是每次都要校正」 |
| 3 UNION 拒绝 | `SQL_REJECTED` + 原因码 | 「危险构造不校正，直接拒绝」 |
| 4 校正回环 | 校验失败 → `correct_sql` → 重校验 → 成功 | 「改完必须再过一次安检」 |

### P5 5051 更新顺序

1. `ssh root@8.155.135.97`：`docker compose ps`、记录镜像 tag、备份 nginx 根目录。
2. 服务器 `.env` 注入 `REBUILD_LLM_*`（不打印 Key）。
3. 构建 backend + 原版 frontend，`up -d`。
4. 冒烟：`/api/health`、`/api/steps`=12、一次问数、一次校正、一次拒绝。
5. 任一失败：回滚旧 tag，保留日志。

---

## 4. 交付清单

| 要求 | 对应物 | 现状 |
|---|---|---|
| 设计文档 ≥30 页 | `design-doc.pdf`（78 页）+ `dev-book.pdf`（163 页） | 已满足 |
| 源代码 1 套 | 本仓库 `main` | 已满足 |
| 开发手册 1 套 | `docs/SETUP-FROM-SCRATCH.md`（1131 行）+ README | 需确认是否单独成册 |
| 四项功能 | NL2SQL / LangGraph 12 节点 / 校正闭环 / React 19 + Tailwind | 线上已具备，需复验 |
| 视频 | `deliverable/v2/*.mp4` + README 外链 | 需重录 |

---

## 5. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 学生 capstone 时间过长 | 用修复型 starter，限 40 轮；先跑 low，medium 只做对照 |
| DeepSeek 不稳定/超时 | 校正测试固定 seed 与超时；失败计入「环境」而非「教材」 |
| 5051 更新打断演示 | 先备份镜像 tag，2 分钟内可回滚 |
| 视频录到假数据 | 只录真实 SSE，保留 `.sse` 证据文件 |
| 教材改动引入新错误 | 每条改动带 `file:line` + before/after，逐条复核 |

---

## 6. 需要你拍板的 6 个分叉

1. **判定口径**：用一致性测试（推荐），还是要求代码结构也接近参考仓库？
2. **学生起点**：修复型 starter（推荐，现实可完成），还是从零重建？
3. **视频**：是否加入「校正回环」场景（推荐加，正好对应第一判据）？
4. **5051**：允许 2–3 分钟重启窗口并备份回滚（推荐）吗？
5. **教材**：是否把 LangGraph 图结构与「12→10 步」映射补成正式章节（推荐补）？
6. **交付物**：开发手册单独出 `MANUAL.pdf`（推荐），还是就用现有 PDF 的第 5 部分？

---

## 7. 执行顺序（今晚）

```
P0 基线 ──► P1 审计 ──► P2 改写 ──► P3 学生验证 ──► P5 5051 对齐 ──► P4 视频 ──► P6 交付
                 │            │             │
                 └── 缺口表 ──┘             └── 卡点回写 P2
```

P2 与 P5 可并行：部署只依赖「当前可运行的系统」，不依赖教材改完。
P3 必须等 P2 出 PDF；P4 必须等 P5 完成，因为视频录的是更新后的 5051。
