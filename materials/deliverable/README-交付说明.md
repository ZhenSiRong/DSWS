# 交付说明

- **成片**：`deliverable/DSWS-cloud-demo.mp4`（3 分钟，1080p30）。双击或 `mpv deliverable/DSWS-cloud-demo.mp4` 播放；右上角常驻「PRD 条目」角标，底部字幕条说明当前演示的功能。
- **五段内容**：① 05–29s 中文问数全绿（LLM 生成 3.4s，5 行结果）② 31–51s 12 节点工作流 ③ 53–103s 自校验先红 + correct_sql 真接管 16.31s（第二次 LLM 调用）④ 105–156s UNION 策略拒绝 SQL_REJECTED ⑤ 158–179s 结果表 string/number 类型保真。
- **对照**：每段时间码/截图/SSE 三件套在 `deliverable/annotations.yaml` 与 `deliverable/PRD-对照表.md`；逐帧抽图在 `deliverable/frames/`（`seg-03-final.png` 是"先红→接管→已校正 1 次"的最佳一帧）。
- **三条差距（写进了对照表）**：LangGraph 未用（自研 12 节点编排）；Tailwind 未用（手写 CSS+React 19 达成）；correct_sql 触发成功但本次未复现"纠正后变绿"。
- **真实性**：全程 Playwright 驱动系统 Chrome 操作云端前端，无回放、无 mock；原始 SSE 从浏览器现场抓取（`deliverable/evidence/*_browser.sse`）。

## v2 实例（2026-11-05 部署 / 2026-11-06 界面切换）

- **v2 成片**：`deliverable/v2/DSWS-v2-original-ui-demo.mp4`（46.27s，1920×1080 / 30fps）。录的是 `http://8.155.135.97:5051` 的原版界面：GMV 问数（12 节点全部 running→success，5 行真实数据）、商品级排名（`correct_sql skipped`，直接成功）、UNION 策略拒绝（`SQL_REJECTED`，错误码完整展示）。
- **v2 对照**：`deliverable/v2/README-v2.md`（部署与验证）、`deliverable/v2/PRD-差异补齐.md`（v1/v2 三项差距）、`deliverable/v2/annotations.yaml`（逐段标注）。
- **v2 差距**：LangGraph 12 节点**已补齐**；前端已换回原版 `shopkeeper-agent` 界面（React 19 + Tailwind 3.4），页面不再出现「教学版」「从零重建」；`correct_sql` 的失败根因已修复两次（第一次补 measure + `column_infos`；第二次把实体粒度补齐与指标命中解耦，并让校正在 `SQL_UNKNOWN_COLUMN/TABLE` 有合法替代时替换/补 JOIN）。自然问数 `查询销售额大于平均销售额的商品` 已触发 `validate_sql error → correct_sql success → validate_sql success`，见 `deliverable/v2/evidence/v2-natural-correct-success.sse`；故障注入样本仍保留用于稳定回归。
