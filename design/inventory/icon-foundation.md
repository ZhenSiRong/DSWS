# 证据标记图标系统 · 基础版

> 基线 `eea5e75` · 工作树 `/home/zhensirong/VM-Share/DSWS-design` · 2026-11-03
> 范围：只做 HTML 生成阶段的内联 SVG 替换，不碰 `design/style-lab/` 的六套样张。

## 1. 结论

书稿里的 ✅ / 🟡 / ⚪ 在 `markdown.markdown()` 之后被换成 Lucide（MIT）内联 SVG，源文件一个字没动。全书 306 个标记 → 306 个图标（169 / 53 / 84），`book.html` 里已无这三个字符；PDF 重建 180 页，与改前页数一致。

## 2. 图标映射

| 标记 | 含义 | Lucide 图标 | stroke 颜色 | 类名 | aria-label |
|---|---|---|---|---|---|
| ✅ | 已验证 | `circle-check` | `#15803D` | `status-icon status-ok` | 已验证 |
| 🟡 | 推断 | `circle-alert` | `#B45309` | `status-icon status-warn` | 推断 |
| ⚪ | 未验证 | `circle-help` | `#6B7280` | `status-icon status-unknown` | 未验证 |

统一规格：`viewBox="0 0 24 24"`、`fill="none"`、`stroke-width="2"`、`stroke-linecap/linejoin="round"`、`role="img"`，尺寸由 `book.css` 的 `.status-icon` 给（`3.2mm` 见方，`vertical-align: -0.15em`，`margin: 0 0.25mm`，`display: inline-block`）。图形只用 `circle` / `path` / `line`，没有文字、没有 emoji、没有 icon font。

## 3. 改了哪些文件

| 文件 | 改动 |
|---|---|
| `design/scripts/status_icons.py`（新建） | 三个 SVG 常量 + `replace_status_markers(html_text) -> str`；`<pre>` / `<code>` 整段跳过，标签与属性值不替换 |
| `design/scripts/build_book.py` | `markdown.markdown()` → `add_table_captions()` 之后、`build_toc()` / 写盘之前调 `replace_status_markers(body)`；`strip_tags()` 把 `<svg>` 换成它的 `aria-label`，目录里那一行标题才不会变成「5. 证据等级： / / 」 |
| `design/book/book.css` | 新增「证据标记图标」小节：`.status-icon` 与三个颜色类 |
| `design/book/chapters/00-front.md` | §5 表格前加一句：`图标对照：圆形勾号 = 已验证；圆形感叹号 = 推断；圆形问号 = 未验证。`（全文唯一一处章节改动） |
| `design/book/pdf/dsws-design-atlas.pre-icons.pdf` | 改前的 180 页 PDF 备份 |
| `design/book/pdf/dsws-design-atlas.pdf` | 重建结果，180 页 |

没有改 `build_pdf.py`、`render_all.py`、任何图表、表格行、代码块、标题，也没有动 `design/style-lab/`。

## 4. 标记统计（改后重新数）

| 章节 | ✅ | 🟡 | ⚪ | 小计 |
|---|---:|---:|---:|---:|
| `00-front.md` | 10 | 14 | 11 | 35 |
| `10-s0-s4.md` | 26 | 10 | 9 | 45 |
| `20-s5-s8.md` | 45 | 9 | 25 | 79 |
| `30-atlas.md` | 78 | 10 | 22 | 110 |
| `40-ops.md` | 3 | 2 | 10 | 15 |
| `90-appendix.md` | 7 | 8 | 7 | 22 |
| **合计** | **169** | **53** | **84** | **306** |

与任务给的基线（169 / 53 / 84，共 306）一致。改后 `book.html` 中 ✅/🟡/⚪ 各 0 个，`<svg class="status-icon…">` 306 个（ok 169 / warn 53 / unknown 84）。

## 5. 构建与验收

```bash
cd design
cp -p book/pdf/dsws-design-atlas.pdf book/pdf/dsws-design-atlas.pre-icons.pdf
style-lab/.venv/bin/python scripts/build_book.py   # 6 chapters, 353,332 chars
style-lab/.venv/bin/python scripts/build_pdf.py   # 180 pages · 4.89 MB · 21s
```

WeasyPrint 70.0 / markdown 3.11.2，只用 `design/style-lab/.venv/bin/python`。

已核对的项：

- **页数**：改前 180 页（`pdfinfo` 确认），改后 180 页，无章节错位。
- **正文**：`pdftotext` 全量对比改前/改后文本，差异只有三类——目录行 `✅ / 🟡 / ⚪` 变「已验证 / 推断 / 未验证」、正文里 306 个标记变成空（图标是矢量，不产出文本）、新增的「图标对照」那一句。没有别的字被改动或重排丢字。
- **抽查页面**：P9「5. 证据等级」表（三行三色图标）、P54 表 3-1（行内 ⚪ 在「本工作树标」后面）、P65 表 3-2（表题里的 ✅）、P100「证据与边界」段（行内 ✅ 在括号里）、P8 §5 标题（三个图标连排）。
- **对齐**：`vertical-align: -0.15em` 让圆心略低于文字中线、圆底贴基线，跟中文方块字并排不显得「浮起来」。
- **可打印**：纯线条、单色、无渐变、无位图；图标在 PDF 里是矢量路径，不依赖任何 emoji 字体。

## 6. 观感

**100% 屏幕（96 dpi）**：3.2mm ≈ 12px，图标比正文汉字略小一圈，与 10.2pt 正文并排时是「标记」而不是「插图」的份量；三种颜色在灰底表头行、深色代码块外都能分辨。圆形外框直径 20/24 × 3.2mm ≈ 2.67mm，是实际着墨尺寸。

**打印尺寸（A4，300–400 dpi 栅格化检查）**：线宽 2/24 × 3.2mm ≈ 0.27mm ≈ 0.76pt，高于常见 0.5pt 细线门槛，激光打印不会断线；勾、感叹号、问号在 3.2mm 下笔画间距仍分得开。表格里图标与「已验证 / 推断 / 未验证」三列文字左对齐后，行高没有被撑开（表格仍是 `8.7pt` 行距）。

## 7. 已知问题与边界

1. **`currentColor` 在 WeasyPrint 70 里不生效。** 实测内联 SVG 的 `stroke="currentColor"` 会被画成黑色，所以颜色写死在每个 SVG 的 `stroke` 上；`book.css` 的三个 `.status-*` 颜色类保留，供浏览器预览和将来支持 `currentColor` 的渲染器使用，在 PDF 里目前是冗余的。若以后换渲染器并想改回 `currentColor`，只需改 `status_icons.py` 的 `_icon()`。
2. **PDF 里再也搜不到 ✅ / 🟡 / ⚪。** 图标是矢量图形，不产生文本层；用 `pdftotext` / 阅读器搜 emoji 会落空，要搜「已验证 / 推断 / 未验证」。这是换图标的必然代价，不是 bug。
3. **目录行为有一处小改。** `strip_tags()` 现在会把 `<svg>` 换成 `aria-label` 文本，所以目录里 §5 显示「5. 证据等级：已验证 / 推断 / 未验证」。不改这一行，目录会留下「： / / 」三个孤零零的斜杠。
4. **标题里的图标偏小。** `h2` 是 14.5pt（约 5.1mm 字高），图标固定 3.2mm，视觉上比标题字小一号。这一批按「统一 3.2mm」执行；若后续要让标题图标跟字号联动，可在 CSS 里给 `h1 svg.status-icon, h2 svg.status-icon` 单独放宽到 4mm。
5. **⚪ 选了 `circle-help`（问号）而不是 `circle-dashed`。** 虚线圆在 3.2mm、0.27mm 线宽下会碎成点，打印不可靠；问号与「未验证」的语义也更直白。
6. **未覆盖范围。** `design/style-lab/` 六套样张仍用各自的方式处理标记（本次未动）；`design/diagrams/` 的 SVG 图源里若出现这三个字符，也不会被这套替换处理——它只作用于 `book.html` 的正文 HTML。
