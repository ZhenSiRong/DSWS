# 13 · HTML 重构版阅读层（grill 会话）

> 状态：**grill 会话已收口**（2026-11-23，Q8/Q9 均已答）；开工进度看 `14-progress-gantt.md`。
> 背景：md 派生 HTML 永不手改（第 4 轮纪律不破）；但用户批准**第三条轨道**——
> 重构版可以不以 md 为正典，用可视化工具点选出组件、人为优化阅读体验。
> 与 11/12 的关系：11=md 阅读层（学生入口），12=作者复核编辑器（MarkText），13=HTML 重构实验轨。

## 已核实的事实

| # | 事实 | 出处 |
| - | - | - |
| G1 | 现有阅读版 HTML 是生成物：`render_read.py` → `tutorial/read/`，0 处内联样式，观感全由 lesson.css+read.css 决定 | 2026-11-23 核实 |
| G2 | 仓库已有"实验轨先于转正"先例：`materials/design/style-lab/01-swiss…06-terminal`，各带 preview/specs | ls materials/design/style-lab |
| G3 | GrapesJS：BSD-3 开源 Web Builder **框架**（非现成 App）；组件/块系统、样式管理器、可导入现有 HTML、导出干净 HTML/CSS；需自托管一个编辑器页 | WebSearch 2026 多方 |
| G4 | 其余候选：VvvebJs（开源，成熟度低）、Webstudio（AGPL，偏 React 应用）、TinaCMS（开源自托管 CMS，需先有站点框架）、Pinegrow（付费闭源，出局）、BlueGriffon/KompoZer/Brackets（已死） | WebSearch + 产品现状 |
| G5 | 仓库已有 Node 环境（system/frontend/node_modules 存在）；Python3 可起静态服务 | 仓库结构 |
| G6 | 审计边界：`audit_book.py` 只查 `tutorial/page-XX.md` 与 README 链接，不扫自建 HTML 目录 | audit_book.py |

## 第 1 轮落定（2026-11-23，用户对话拍板）

> 用户原话：「Q1 A+B 首先是方便的 CSS 样式持续迭代，其次是想要有个用点 UI 就能创建新组件/所见即所得的 HTML 编辑工具去人为优化/重构 HTML 版的教程文档；Q2 以 MD 为正典的 HTML 永不手改，但重构版的可以不以 md 为正典；Q3 A+B+C。」

| 题 | 落定 |
| - | - |
| Q1 对象 | ✅ A+B：主需求=CSS 持续迭代；次需求=可视化 HTML 工具（点选建组件）重构阅读版 |
| Q2 正典边界 | ✅ md 派生 HTML 永不手改；**重构版独立成轨，可不以 md 为正典** |
| Q3 痛点 | ✅ A 观感待调 + B 缺组件 + C 内容在 HTML 上改更顺 |

## 设计树

```
HTML 侧
├── H1 「HTML 编辑器」对象           ✅ A+B（CSS 迭代 + 重构工具）
├── H2 正典边界                      ✅ md 派生永不手改；重构版独立正典
├── H3 痛点                           ✅ A+B+C
├── H4 重构轨定位与同步政策           ✅ 实验轨 `tutorial/rebuild/`，p17 试点，不自动同步
├── H5 重构工具选型                   ✅ GrapesJS 试点（BSD-3）
├── H6 CSS 迭代工具链                 ✅ livereload（实现口径见下）
├── H7 第一批组件清单                 ✅ 8 块（p17 先用 ③④⑤⑥⑦⑧ 子集）
├── 术语「重构版」                    ✅ 已写进 GLOSSARY
├── 试点判据（p17 重构一页）          ✅ Q8 六条已同意（2026-11-23）
└── ADR（双正典治理）                 ✅ `materials/docs/adr/0001-dual-canon.md`（2026-11-23）
```

## 第 2 轮落定（2026-11-23，用户对话拍板）

> 用户原话：「Q4 可以，开个实验轨在/manual/rebuild/上；Q5 GrapesJS试点；Q6 引入livereload；Q7 ok」

| 题 | 落定 |
| - | - |
| Q4 定位 | ✅ 实验轨 `tutorial/rebuild/`；先 p17；记录 md 派生基线；不自动同步；不替换 `tutorial/read/` |
| Q5 工具 | ✅ GrapesJS 试点；自托管 `tutorial/rebuild/editor.html`；导入阅读版 HTML 为起点；导出 HTML/CSS 落盘 |
| Q6 迭代链 | ✅ 引入 livereload；**实现口径**：用 `uv run --with livereload` 起服务（零仓库依赖、不污染 backend 依赖），监听 `materials/assets/*.css` 与 `tutorial/read/*.html`，浏览器自动刷新；满意度后把改动抄回 `materials/assets/read.css` 再 `render_read.py --all` |
| Q7 组件 | ✅ 8 块词表；p17 先用 ③代码块＋复制 ④callout ⑤步骤卡 ⑥对照表 ⑦漫画＋caption ⑧右侧锚点目录；导航/进度条后置 |

## 第 3 轮问题（待答）

### ❓ Q8 · 试点判据：p17 重构页算不算成功的六条？

1. **内容对等**：判据原句、命令、数字、路径逐项在重构页可 grep 到（保护区机器核对）。
2. **组件可用**：复制按钮真能复制、callout 正常渲染、TOC 锚点跳转正常。
3. **正典不破**：`tutorial/read/` 与 `tutorial/page-*.md` git diff 为空（只新增 rebuild 目录）。
4. **闸门不破**：`audit_book.py` 仍 24/24、README 坏链 0。
5. **肉眼裁决**：与 `tutorial/read/page-17.html` 并排，你判定更好读。
6. **可重现**：GrapesJS 项目 state JSON 重新打开再导出，产物一致（幂等）。

### ❓ Q9 · ADR：要不要写「双正典治理」决策记录？

md 正典（练本内容真相）＋重构版自正典（呈现真相）是长期治理规则，满足 ADR 三条（难逆/需解释/真取舍）。

➡️ 推荐：Q8 按六条验收；Q9 同意写 ADR（`materials/docs/adr/0001-dual-canon.md`，中文）。

> Q9 已落定（2026-11-23，用户「Q9 写」）：ADR 已写进 `materials/docs/adr/0001-dual-canon.md`。

## 第 2 轮问题原文（已答，存档）

### ❓ Q4 · 重构轨定位：实验轨还是正式轨？

- 实验轨（推荐）：`tutorial/rebuild/` 目录，先重构 p17 一页，与 `tutorial/read/` 并存对照；
  重构页顶部记录派生基线（md 的 git 提交 + 日期）；md 后续改动**不自动同步**，需显式重移植。
  判据：p17 重构页「同内容、更好读、带组件」由用户肉眼裁决；不替换现有阅读版。
- 正式轨：直接定为目标入口，替换 `tutorial/read/`（成本大，回滚难）。

### ❓ Q5 · 重构工具：GrapesJS 试点？

- A（推荐）：GrapesJS（BSD-3）——自托管一个 `tutorial/rebuild/editor.html`，注册 6–8 个自定义块（见 Q7），
  导入现有 p17 阅读版 HTML 当起点，点选重构后导出 HTML/CSS 落盘；项目 state 存 JSON 侧文件。
- B：VvvebJs / Webstudio —— 成熟度或形态（React 应用）不匹配，不推荐。
- C：不引建站器，手写 Web Components —— 违背"点选建组件"的诉求，只在 A 试点失败时回退。

### ❓ Q6 · CSS 迭代工具链：浏览器 devtools + 本地静态服务？

- A（推荐）：`toolbox/scripts/read-serve.sh` 起 `python3 -m http.server`（仓库根），浏览器 devtools 实时调样式，
  满意后把改动抄回 `materials/assets/read.css`，再 `render_read.py --all` 重生成；零新依赖。
- B：引入 livereload/浏览器自动刷新（多一个依赖，收益小）。
- C：Qoder 预览面板（受 IDE 限制，devtools 仍是正主）。

### ❓ Q7 · 第一批组件清单（点选块的词表）？

推荐 8 个：①页面导航（上一页/下一页/目录）②阅读进度条 ③代码块＋复制按钮 ④提示卡 callout（4 色）
⑤步骤卡（编号+标题+正文+预期输出）⑥对照表（两列事实）⑦漫画图＋caption 卡 ⑧锚点目录（右侧 TOC）。
来源：Q3-B 缺组件 + 现有六段模板的语义块。

## 待落定后创建

- 术语：GLOSSARY 增「重构版（rebuild）」（不以 md 为正典的 HTML 重构轨；与阅读层、阅读版 HTML 划界）。
- ADR 候选：双正典治理（md 正典 + 重构版自正典）——难逆、需解释、有真实取舍，满足三条。