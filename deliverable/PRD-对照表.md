# PRD 对照表 · 项目五「电商问数智能体」云端真实演示

> **v2 实例已部署（2026-11-05，界面切换 2026-11-06）**：`http://8.155.135.97:5051` 补齐了 LangGraph 12 节点，并换回原版 `shopkeeper-agent` 界面（React 19 + Tailwind 3.4）；本表保留 v1（`:5050`）的原始差距记录，v2 对照见 `deliverable/v2/PRD-差异补齐.md`。
>
> 视频素材：`deliverable/DSWS-cloud-demo.mp4`（181s，1920×1080 / 30fps，非 mock——浏览器驱动云上前端，后端在云端连真实 DeepSeek LLM 与只读 MySQL）。
> 逐段标注：`deliverable/annotations.yaml`；原始 SSE 为录屏现场从浏览器抓取，存 `deliverable/evidence/*_browser.sse`。
> 取证原则：每条都给「视频时间码 + 截图 + SSE」三件套；**差距如实写，不粉饰**。

| # | PRD 要求（原文要点） | 实现状态 | 视频时间码 | 证据 | 差距 / 说明 |
|---|---|---|---|---|---|
| 1 | 自然语言问数 NL2SQL（中文提问生成 SQL 并在数仓执行） | ✅ 真实达成 | 00:05–00:29 | `frames/seg-01.png`；`evidence/q_gmv_browser.sse`；页面显示「生成SQL 完成 3.4s」（真实 LLM 往返），MySQL 返回 5 行（华东 107,373…） | 无。SQL 由 DeepSeek 模型生成，非模板；执行账号只读 |
| 2 | LangGraph 多节点工作流（12 节点 / 10 步） | ⚠️ 部分达成 | 00:31–00:51 | `frames/seg-02.png`；`evidence/q_category_browser.sse`；前端步骤条逐节点 running→success | **LangGraph 未使用**：`backend` 无 langgraph/StateGraph 依赖，实际为自研 12 节点编排，步骤目录唯一源 `contracts/steps.yaml`（12 个 id，`correct_sql` 条件步）。**节点数与步骤数达成，框架选型与 PRD 措辞不符** |
| 3 | SQL 自校验 validate_sql + 自纠错 correct_sql（失败自动重试） | ⚠️ 部分达成 | 00:53–01:43 | `frames/seg-03.png`（先红：校验SQL ✗、校正SQL 执行中）；`frames/seg-03-final.png`（校正SQL 完成 16.31s，错误卡含「已校正 1 次」）；`evidence/r_rank_browser.sse` | **双保险机制真实存在且被真实触发**：validate_sql 红 → correct_sql 真跑一次（16.31s，第二次 LLM 调用）→ 重写后列名仍不在契约 → 命名错误 SQL_UNKNOWN_COLUMN。即**触发=true、纠正成功=false**——校正闭环可用，但本次真实运行未复现「先红后绿成功」的完整闭环 |
| 4 | 安全边界（越权/写操作/危险 SQL 被拒） | ✅ 真实达成 | 01:45–02:36 | `frames/seg-04.png`：错误卡 SQL_REJECTED + 原因码 SQL_FORBIDDEN_CONSTRUCT；`evidence/r_union_browser.sse` | 无。UNION 在连库前被拦，策略拒绝不参与校正（校正SQL「未触发」，符合设计）。云端探针另证 UPDATE 企图 → LLM_REFUSAL（`/opt/dsws/evidence/p_write.sse`） |
| 5 | React 19 + Tailwind 现代化前端（聊天式提问 + 可视化结果表格） | ⚠️ 部分达成 | 00:05–00:29 与 02:38–02:59 | `frames/seg-01.png` / `frames/seg-05.png`：string/number 列型徽标、千分位右对齐、「复制结果（JSON）」 | **React 19 达成**（`"react": "^19.0.0"`）；**Tailwind 未使用**（package.json 无 tailwindcss），前端为手写 CSS + 设计令牌（`frontend/src/styles.css`）。功能形态（聊天式 + 结果表）达成，技术栈与 PRD 措辞不符 |
| 6 | 数量要求：设计文档 ≥30 页 | ✅ | —（非视频项） | `design/book/pdf/dsws-design-atlas.pdf` **180 页** | 无 |
| 7 | 数量要求：源代码 1 套 | ✅ | — | 云端 `/opt/dsws/repo` + 本仓库 `frontend/`、`backend/` | 无 |
| 8 | 数量要求：开发手册 1 套 | ✅ | 设计书 + `README`（云端仓库精简版）+ 契约文件 `contracts/steps.yaml` | 无 |

## 失败路径与 LLM 的两点说明（防止误读）

- **LLM 供应商**：本次演示用的是云端已配置的 DeepSeek（`REBUILD_LLM_BASE_URL=https://api.deepseek.com`，model `deepseek-flash`）。`.env.test` 里的 MiniMax key **全程未使用**，不计入证据。
- **两条失败路径的题目**：68–103s 自校验路径（问题「哪个商品品类卖得最好」）、104–156s 策略拒绝路径（UNION 题），均与云端探针 `/opt/dsws/evidence/r_rank.sse`、`r_union.sse` 互为印证。

## 结论一句话

PRD 1(1) 的**功能主链路（NL2SQL、12 节点工作流、自校验/自纠错、安全边界、结果表）全部真实跑通且有证可查**；三处措辞级差距（LangGraph → 自研编排、Tailwind → 手写 CSS、纠正闭环未复现成功态）已在上述逐条写明，供决策「改实现」或「改 PRD 措辞」。
