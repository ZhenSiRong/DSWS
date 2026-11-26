# TODO · 剩余工作

> 过程文档。完成一项勾一项，证据写链接或命令。

## P0 · 图表可理解性收口

- [ ] **6 张概念漫画**（Lite，图文并茂：图内带中文标题与对话气泡，推翻旧「文字外置」约定）——下一项，先做 12 号；阅读层试点 p17 已入 2 张（见 `materials/humen-desicions/11-reading-layer.md`）
  - [ ] 12 校正闭环：改错题 → 老师复核
  - [ ] 16 三存储：图书馆三套索引
  - [ ] 19 值域树：菜单可选范围
  - [ ] 20 信任边界：小区门禁
  - [ ] 29 测试金字塔：体检套餐
  - [ ] 31 失败矩阵：故障演练
  - 验收：门禁全过 + hy4free N/N + 5 秒读懂
- [~] **三问盲测（32 张）**：6/32 已完成（12/16/19/20/29/31，18/18 问全过），见 `materials/pilot/figure-audit.md`
- [ ] **学生抽检（3 张）**：`hy3 --effort low`，只看图复述
- [ ] 产出 `materials/pilot/figure-audit.md`，列出未过图与修法
- [ ] **阅读层全书铺开（第 4 轮）**：md 结构化优化 62 处长段/21 页，批 A（21/13/18）→ B（20/19/23/15/10）→ C 快通；阅读版 `tutorial/shots/render_read.py` 已转正（Q2 修订）；渐进铺开 AON 已出（`reading-layer-aon.mmd/.png`，关键路径 155 分钟估，`toolbox/scripts/render_reading_aon.py` 独立重算 CPM）；计划与闸门见 `11-reading-layer.md` 第 4 轮；下一步从 A21（p21）开工

## P1 · 文档与版面

- [ ] `MANUAL.pdf` 单独成册（从 dev-book 第 5 部分导出）
- [ ] dev-book 宽图改横版页（当前竖版缩得太小）
- [ ] design-doc 地图页溢出检查（78 页中有 10 页地图跨页）

## P1 · 环境内存治理（2026-11-21）

- [x] **earlyoom 整机兜底**：用户已 sudo 安装，v1.7 active + enabled（`systemctl is-active earlyoom`，进程 `-r 3600`）
- [ ] **compose 加 mem_limit**（可选，本轮未做）：compose.yaml 各服务无内存上限，ES 仅靠 -Xmx512m 管堆
- [ ] **embedding 容器重启循环**：散装容器 `embedding` 处于 Restarting 状态，与教材栈无关，待排查或停掉

## P1 · v1.1.0 发行残留（2026-11-22，接 /tmp/handoff-dsws-lab-2026-11-22.md）

- [x] **explorer 五阶段（A 方案）**：`build_explorer.py` 改读 `city/data-24.json` 五级正典（冻结 `data.json` 不动，前 4 级逐字漂移守卫）；`stages-city.json` 按 code 部分覆盖、L5 回退 D44+D50 文字；自检 + 无头 Chrome DOM 真跑全绿，4 张截图已重出
- [x] **图 05 读图路径源修复**：`build_reading_paths.py` 加 OVERRIDES（05 专属三步），reading-paths.json/yaml、diagram-catalog.md、SVG 读图带、30-atlas.md 五处一致；**PDF 缓修**（两本 PDF 里旧文案，发行前需重建 weasyprint 环境重出）
- [x] **materials/review/ 证据脱敏**：walkthrough / gui-walkthrough / demo-rehearsal 用 `<仓库根>` 占位；viztracer/trace.json 2167 处前缀剔除转仓库相对路径（JSON 仍合法）；timeline.html 内嵌数据本已相对化无需动；删 2 个含绝对路径的未跟踪 .pyc；`make audit` 4/4 全绿
- [x] **p17 第 6 步真模型线上采样**（trials=3）：deepseek-flash 实采 3/3 触发并成功（分母=触发次数，抽样数不外推）；证据 `tutorial/review/p17-live-sample.md` + `.json`（原始 SSE）；502 陷阱收进 TRAPS 14；采完已把 backend 还原确定性默认（MODEL/BASE_URL 置空 recreate + restart ui），要再采按证据里复现命令重新注入
- [ ] **两本 PDF 重建**（图 05 新读图带入册；/tmp/dd30、/tmp/opencode/pdfvenv 已失效，按 materials/design/README 用 uv 重建 weasyprint）
- [ ] **v1.1.0 发布包**：manual-24p.zip + 两本 PDF + dev-book.pdf + SHA256SUMS + RELEASE-NOTES.md；push/tag 命令块交用户（D55）

## P2 · 历史资产

- [ ] `backup/` 里确认不再需要的归档（v1 视频、frames、.rec）
- [x] 旧 `materials/design/book/pdf/dsws-design-atlas.pdf` 已归档到 `../DSWS-archive/2026-11-25/design-atlas-deprecated/`（2026-11-26）
- [ ] `materials/docs/*.md` 的本地改动单独提交或还原（非本次任务）

## 完成记录

| 日期 | 项 | 证据 |
|---|---|---|
| 2026-11-09 | 32 图读图带 + 地图 | `materials/design/design-doc.pdf` 78 页 |
| 2026-11-09 | 两份文档拆分 | design-doc + dev-book（162 页） |
| 2026-11-09 | 结尾角标改“演示完成” | commit `89611d9` |
| 2026-11-21 | 内存治理：关 win-for-workbuddy VM（禁自启+undefine+删 65G qcow2）、停 p17gui/dsws-trace 栈（down 不删卷，保留 dsws-lab-ui）、装 earlyoom | 已用 13G→4.4G，可用 10G；qcow2 已不存在；earlyoom active+enabled；/ 分区剩 56G |
| 2026-11-22 | explorer 五阶段 A 方案 + 图 05 源修复 + materials/review/ 脱敏 | `build_explorer.py` 自检全绿（五阶段 0/10→4→4→5→1 页）；audit_book 24/24；make audit 4/4 |
| 2026-11-22 | p17 第 6 步真模型线上采样 trials=3 | `materials/review/p17-live-sample.md`：五类表 0/3/0/0/0，成功率 3/3（抽样数）；TRAPS 14（force-recreate backend 后 nginx 502）；栈已还原确定性默认 |
| 2026-11-22 | p17 阅读层开工（第 2 轮落定后） | 2 张图文并茂漫画 WebP 入页（103KB/88KB，六段/判据/命令一字未动）；GLOSSARY 增「阅读层」；Q4 截图高度自适应（`render_l3_pages.py` 1800 地板→内容+80px，p17 两张重高 1194/1013）；audit_book 24/24、README 坏链 0；散文删减另议，待人工复核渲染后再定推广 |
| 2026-11-23 | p17 阅读层第 3 轮：散文结构化铺全页 | 14 处重写（领词＋列表＋ 端口小表）；最长段 739→220 字；12 代码块与 HEAD 逐块一致、保护区 17 项全在；audit 24/24；净字数 +5%（领词成本），总量压缩另议；见 `11-reading-layer.md` 第 3 轮 |
| 2026-11-23 | 阅读层第 4 轮：渐进铺开 AON 出图 | `reading-layer-aon.mmd`（17 节点/22 边）→ `.png`（2600×683）；`toolbox/scripts/render_reading_aon.py` 逐轮松弛独立重算 CPM、标注/class/linkStyle/注释四方对账、mermaid 渲染＋PNG 配色自检全过；关键路径 R0→A21→GA→RA→B20/B19→GB→RB→C→GC→RC→F（155 分钟估）；见 `11-reading-layer.md` 第 4 轮 |
