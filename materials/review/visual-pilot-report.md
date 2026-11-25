# 前 3 页「可编辑页首图」试点报告（kimi worker + lead 收尾）

> 日期：2026-11-24；基线：`continue-iterate` @ `5305072`（v1.1.0）
> 目标：把 p00–p02 的 AI 栅格漫画换成代码原生、可编辑、可低 token 修改的页首图。

## 交付物

| 页 | 设计源 | 可编辑产物 | 渲染/页面 |
|---|---|---|---|
| p00 | `manual/designs/page-00/index.html` | `editor.html`（editable-design 运行时） | `out/poster.png`(1600×1000) → `manual/images/page-00-visual.webp`（43KB） |
| p01 | `manual/designs/page-01/index.html` | `editor.html` | `out/poster.png` → `manual/images/page-01-visual.webp`（51KB） |
| p02 | `manual/designs/page-02/index.html` | `editor.html` | `out/poster.png` → `manual/images/page-02-visual.webp`（44KB） |

- 页面引用已从 `images/page-NN-comic.webp` 换成 `images/page-NN-visual.webp`；**旧 AI 漫画保留**（归档，不删）。
- 阅读版 HTML：`manual/read/page-00/01/02.html` 已由 `render_read.py` 重生成。

## 设计口径（用户已确认）

- 真实工具 + 一句"在本项目里负责什么" + 一句判据/用法；不再用手工具隐喻。
- 固定画布 1600×1000；白底/黑字/单橙 `#E65100`；无渐变无阴影无运行时外链。
- 所有文字为实时 HTML 文本（可选中编辑），图标本地 SVG（`assets/`）；字体用系统 Noto Sans CJK。
- p00 六张工具卡（Docker/uv/Node+npm/GNU Make/curl/Git）；p01 容器 vs 宿主 + 127.0.0.1 判据；p02 导入 dw.sql + 5 分区/115 行。

## 验证

```
python3 manual/shots/audit_book.py       → 页面：24/24 通过；README 坏链：0
python3 scripts/verify.py --fast         → T0 PASS（0.01s）
python3 scripts/verify.py（补 backend/.venv 后）→ T1 PASS（10.96s，4/4 offline）
python3 manual/shots/render_read.py 00 01 02 → 三页 HTML 重生成
```

editable-design 校验：
- `check-contract.mjs`：✅ 固化视觉零偏差、字体加载、无控制台报错；
- `check-fonts.sh`：字体存在（Noto Sans CJK SC / Mono）；
- `verify.mjs`：**文字编辑/拖拽/撤销/导出往返/localStorage 草稿全部 ✅**；
  5 项失败集中在**编辑器布局微调**（左右缩放带来 0.5px 高度漂移、撤销恢复宽高、拆解视图列宽/中央基底约束），不影响改字与导出；记录为已知限制，后续模板调优再修。

## 事实核对

- p00 端口 3307/8000/8081 与 `manual/page-00.md` 一致；
- p01 `127.0.0.1:3307` / `docker exec` / 空库无 `dw` 与页面一致；
- p02 `docker exec -i lab-mysql mysql -uroot -plabpass < fixtures/dw.sql` 与 5 表（`dim_customer`/`dim_date`/`dim_product`/`dim_region`/`fact_order`）、115 行、华北 19 与页面一致。

## 已知限制 / 后续

1. 三页的 `editor.html` 可改字/拖拽/导出，但拆解视图的 5 项布局校验未过（见上）；若要严格过 editable-design 的交付契约，需要再调模板（增加背景/固定基底、约束图层高度）。
2. `out/` 被设计目录 `.gitignore` 忽略；`poster.png` 由 `render-poster.sh`/editable-design 可重建；仓库只提交设计源 + WebP。
3. 若用户认可，按同一模板铺剩余 21 页；旧 AI 漫画统一归档到 `manual/images/archive/comics-v1/`（本试点未移动，避免与 v1.1.0 引用混乱）。
