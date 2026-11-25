# 证据图标替换 · 验收记录

> 2026-11-03 · 工作树 `/home/zhensirong/VM-Share/DSWS-design`
> 范围：主书 + 六套 `design/style-lab/` 样张

## 1. 结论

✅ / 🟡 / ⚪ 已全部替换为 **Lucide 内联 SVG**（circle-check / circle-alert / circle-help），没有 emoji、icon font 或 Unicode 几何符号。源 Markdown 里的标记保持原样，替换只发生在 `build_book.py` 的 HTML 生成阶段。

## 2. 统计

| 对象 | 图标数 | HTML 中 emoji | 页数 | 文件 |
|---|---:|---:|---:|---|
| 主书 | 306 | 0 | 180 | `design/book/pdf/dsws-design-atlas.pdf` |
| 01 瑞士网格 | 114 | 0 | 55 | `design/style-lab/01-swiss/dsws-style-01-swiss.pdf` |
| 02 学术衬线 | 114 | 0 | 60 | `design/style-lab/02-serif/dsws-style-02-serif.pdf` |
| 03 编辑杂志 | 114 | 0 | 67 | `design/style-lab/03-editorial/dsws-style-03-editorial.pdf` |
| 04 日式留白 | 114 | 0 | 70 | `design/style-lab/04-japanese/dsws-style-04-japanese.pdf` |
| 05 工程蓝图 | 114 | 0 | 52 | `design/style-lab/05-blueprint/dsws-style-05-blueprint.pdf` |
| 06 终端开发者志 | 114 | 0 | 51 | `design/style-lab/06-terminal/dsws-style-06-terminal.pdf` |

主书 306 = ✅169 / 🟡53 / ⚪84；六套样张各 114 = `00-front` 35 + `20-s5-s8` 79。PDF 文本层里也已无这三个字符（`pdftotext` 计数为 0）。

## 3. 映射与样式

| 标记 | 含义 | Lucide | 默认色 | 类名 |
|---|---|---|---|---|
| ✅ | 已验证 | circle-check | #15803D | `status-ok` |
| 🟡 | 推断 | circle-alert | #B45309 | `status-warn` |
| ⚪ | 未验证 | circle-help | #6B7280 | `status-unknown` |

- 规格：24×24 viewBox、stroke 2、`fill="none"`、3.2mm 见方、`vertical-align:-0.15em`。
- 六套样张按各自色板调整了图标颜色（见各套 `status_icons.py` 的 `_COLORS`）。
- WeasyPrint 70 不解析内联 SVG 的 `currentColor`，所以 stroke 颜色写死在 SVG 里；CSS 颜色类保留给浏览器预览。

## 4. 产物

- 基础实现：`design/scripts/status_icons.py`、`design/scripts/build_book.py`、`design/book/book.css`
- 图例：`design/book/chapters/00-front.md` 新增一句「图标对照：圆形勾号 = 已验证；圆形感叹号 = 推断；圆形问号 = 未验证。」
- 基础报告：`design/inventory/icon-foundation.md`
- 预览：`design/style-lab/preview/contact-covers.png`、`card-*.png`（卡片正文页已换成带图标的证据标记页）
- 改前 PDF 备份：`design/book/pdf/dsws-design-atlas.pre-icons.pdf`

## 5. 已知问题

1. PDF 里搜不到 emoji 了；要搜「已验证 / 推断 / 未验证」。
2. 目录里 §5 显示「5. 证据等级：已验证 / 推断 / 未验证」，因为 `strip_tags()` 把 `<svg>` 换成了 `aria-label`；这是为了避免目录出现「： / / 」。
3. 3.2mm 图标在 04 日式留白 / 03 编辑杂志的窄栏里偏小；若选这两套，可把 `.status-icon` 调到 3.6mm 再统一重建。
4. 三套样张（01/02/05）的 `style-notes.md` 末尾已补图标行；03/04/06 的说明是本次补写的，若后续改版式需同步更新。

## 6. 还剩什么

- 用户还未选定六套中的哪一套铺到整本 180 页。当前整本主书是「原主书版式 + 新图标」，不是六套样张之一。
- 选定后：把该套的 `book.css` / `cover_html()` / `build_toc()` 合并到 `design/`，重建整本 PDF，再跑一次本文件的统计与抽查。
