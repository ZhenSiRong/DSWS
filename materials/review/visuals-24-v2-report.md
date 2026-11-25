# 24 页「实体 / 喻体」页首图全面铺开报告（2026-11-25）

> 用户确认：p00–p02 试点通过，全面铺开剩余 21 页；结构=左实体（真实对象+职能+命令）/ 右喻体（AI 插画+①②③映射），文字全部 HTML 实时可编辑。

## 覆盖

| 项 | 结果 |
| - | - |
| 页面引用 `images/page-NN-visual.webp` | **24/24** |
| 页首图设计源 `manual/designs/page-NN/index.html` | 24 |
| 可编辑版 `editor.html`（含另存/覆盖按钮） | 24 |
| `data/page-NN.json`（文案/卡片/映射） | 24 |
| 喻体插画 `art/metaphor.jpeg` | 24（p00–p02 试点 + 21 页新生成） |
| 旧 AI 漫画 | 25 张归档 `manual/images/archive/comics-v1/` |
| 页面残留 `comic.webp` 引用 | 0 |

## 内容模型

- 左栏：真实对象（Docker/uv/MySQL/nginx…）+ 在本项目里的职责 + 可核对命令/判据；
- 右栏：Seedream 生成的无字喻体插画 + 3 条 ①②③ 映射（喻体元素 → 真实职能）；
- 底部：一条判据。
- 所有文字（标题、实体卡、映射、判据）都是 HTML 标签；插画只做素材，可重生成替换。

## 生图与去字

- 端点 `ep-20261109172906-d7fr4`（doubao-seedream-5-0-flash-260915），1536×1024，纯 prompt（本地图生图需 SSO，未用旧图）。
- 21 条 prompt 见 `manual/designs/art-prompts.md`；p00–p02 见各自 `art-prompt.md`。
- p12/p18 首版把 `SELECT` 画进图里（字烤进像素不可编辑），已重新生成无字版；入库规则：**图里不出现任何文字**，有字就重生成/修复。

## 闸门

```
python3 manual/shots/audit_book.py  → 页面：24/24 通过；README 坏链：0
make audit                          → AUDIT PASS 5/5
python3 scripts/verify.py --fast    → T0 PASS（24 契约）
make verify                         → T1 PASS（14/14 offline）
manual/shots/render_read.py --all   → 24 页阅读版，幂等
```

## 编辑与保存

- 服务：`scripts/design-serve.py 8788`（静态 + `POST /api/save`）
- 入口：`http://127.0.0.1:8788/manual/designs/`
- 编辑器顶栏新增 **另存为 HTML** / **覆盖保存**；覆盖保存会备份到 `page-NN/out/`、重建 editor/PNG/WebP/阅读版并跑 audit。
- 改文案也可改 `data/page-NN.json` → `python3 manual/designs/build_visuals.py NN`。

## 已知限制

- 插画由纯 prompt 生成，风格统一但个别页细节（p12/p18 重生成后线条偏简、p23 装修场景）还可以逐页精修；
- 编辑器仍用 editable-design 的拆解视图，卡片版式下部分布局断言不通过（不影响改字/导出）；
- 文案事实已按页面核对，个别描述可继续人工润色。
