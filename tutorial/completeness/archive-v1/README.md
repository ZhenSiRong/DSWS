# archive-v1 · 《建成证明》v1 历史存档（D38–D41）

> **一句话**：v1（D38–D41：行=架构节点的四层矩阵）已被 v2（D42：行=交付物）取代，仅存档；新入口见 [`../poster-answer.png`](../poster-answer.png) 与 [`../explorer.html`](../explorer.html)。

## 为什么有这个目录

依据 `materials/humen-desicions/09-ablation-course.md` 的 **D43 第 1 条**：v1 的数据与产物整体移入 `completeness/archive-v1/`，保留为 D38–D41 的历史证据。

- **v1 的问题**（D42 记录的学生实测反馈）：行 = 架构节点（C4 L1/L2/L3 + L0 地基），列 = 抽象能力（"接收提问"等）；学生跟着练完**不知道自己各自做完了没有**——12 行里 2 行没有对应页、MySQL 行合并 A1·A2、backend 行盖 A3–A8，列名在任何一页里都找不到，无从对账。
- **v2 的做法**：行 = 具体交付物（容器 / 库表 / 数据 / 进程 / 接口 / 函数 / 端点 / 页面 / 链路），每行显式写「位置」+ 1–3 个「命令 → 期望输出」检验点，判据全部取自第 0–9 页「你应该看到」。

本目录**只供追溯，不再维护**，所有链接与命令都应以现行 v2 为准。

## 文件清单

| 文件 | 原路径 | 说明 |
|---|---|---|
| `data.json` | `tutorial/completeness/data.json` | v1 单源数据：12 个架构节点 × 15 能力列（矩阵格级三态 ▢/◧/■） |
| `poster.md` | `tutorial/completeness/poster.md` | v1 海报源稿：叠层结构图 + 四张「责任 × 证据」矩阵 + 三态图例 + 三条判据 |
| `poster-answer.png` | `tutorial/completeness/poster-answer.png` | v1 **答案版**成品（A4 @300dpi，2480×3508）——新图覆盖前原样拷贝 |
| `poster-blank.png` | `tutorial/completeness/poster-blank.png` | v1 **空白版**成品（A4 @300dpi，2480×3508）——新图覆盖前原样拷贝 |
| `explorer.html` | `tutorial/completeness/explorer.html` | v1 交互原型成品（D41 生成，sha256 `7413cdb3…`）——原文件原位保留给 v2 重写，此处为覆盖前快照 |
| `render_completeness-v1.py` | `tutorial/shots/render_completeness.py` | v1 海报渲染器快照（硬编码四层矩阵，不读 JSON） |
| `build_explorer-v1.py` | `tutorial/shots/build_explorer.py` | v1 交互页生成器快照（读 v1 `data.json` + 反向核对 `poster.md`） |

> 旧的两张 v1 海报 PNG 不在原位置保留：D43 要求新图覆盖 `completeness/poster-*.png`（README 链接不变），所以把覆盖前的那一版原样拷进本目录作证据。

## 口径差异（v1 → v2）

| | v1（D38–D41） | v2（D42，现行） |
|---|---|---|
| 行 | 架构节点（C4 L1 上下文 / L2 容器 / L3 组件 + L0 地基横条） | 交付物（12 件：容器 / 库表 / 数据 / 进程 / 接口 / 函数 / 端点 / 页面 / 链路） |
| 列 / 格 | 抽象能力：15 列 × 48 格 | 检验点：24 个，每点「命令 + 期望输出」 |
| 状态 | 矩阵格三态 ▢/◧/■，节点状态由格派生 | 检验点三态 ▢/◧/■，行状态由检验点派生 |
| 完备判据 | ① 每行 ≥1■ ② 每列 ≥1■ ③ 跨层边都通 + 端到端证据 | ① 每行检验点全■ ② 12 行全■ ③ 端到端跑出 `41099.5` |
| 版面 | 结构图 + 四张矩阵 + 图例 + 判定规则 | 一张物料清单表（零件 / 位置 / 检验点 / 页）+ 三条完备判据 |

现行产物与重跑命令：

- 海报：`python3 tutorial/shots/render_completeness.py` → `../poster-answer.png`、`../poster-blank.png`（读 `../v2/data.json`）
- 交互页：`python3 tutorial/shots/build_explorer.py` → `../explorer.html`（读 `../v2/data.json`）
