# 页首图（page visual）· 可编辑设计源

> 术语见 `GLOSSARY.md`「页首图」：可编辑、代码原生渲染的概念图，不是 AI 生成的整张栅格插画。
> 旧 AI 漫画已归档到 `manual/images/archive/comics-v1/`；页面只引用 `manual/images/page-NN-visual.webp`。

## 目录

```
manual/designs/
  _shared/icons/          # 本地品牌 SVG（docker/uv/node/mysql/nginx/...）+ 通用图标
  data/page-NN.json       # 每页文案与内容（改这里就能改图）
  page-NN/
    index.html            # 设计源（1600×1000 固定画布，实时文本，无外链）
    editor.html           # 可编辑版：拖拽/改字/改字号/导出（editable-design 运行时）
    poster.json           # 画布元数据
    out/poster.png        # 渲染产物（.gitignore 不提交，可重建）
  build_visuals.py        # 共享模板：data JSON → index.html → PNG → WebP + editor
```

## 改一张图（最常见）

```bash
# 1) 改文案/卡片：编辑 manual/designs/data/page-03.json
# 2) 重新生成 HTML + 编辑器 + PNG + WebP（只构建这一页）
python3 manual/designs/build_visuals.py 03
# 3) 重生成阅读版 HTML + 审计
python3 manual/shots/render_read.py 03
python3 manual/shots/audit_book.py
```

- 想只改文字：直接改 `data/page-NN.json` 里的 `title` / `subtitle` / `cards[].role` / `cards[].judge` / `steps[].detail` / `footer`；
- 想改版式：`layout` 支持 `cards`（3 张或 4 张）、`steps`（3–5 步）、`compare`（左右对照）、`table`；
- 想改颜色/字号：`build_visuals.py` 里的 `CSS`（白底、`#1a1a1a` 墨色、`#E65100` 橙点缀）；
- 想换图标：把 SVG 放进 `_shared/icons/`，在 data 里写 `"icon": "mysql"`。

## 页面引用

页面 md 里只引用渲染产物：

```markdown
![第 3 页 · 把服务开到 8000：一个接口，一次真正的“对外说话”](images/page-03-visual.webp)
```

`out/poster.png` 是 1600×1000；WebP 用 `convert out/poster.png -quality 82 ...` 生成（build 脚本自动做）。

## 多页构建 / 新增一页

```bash
python3 manual/designs/build_visuals.py              # 全部已登记页
python3 manual/designs/build_visuals.py 05 06        # 指定页
python3 manual/designs/build_visuals.py --no-editor  # 只出 PNG/WebP
```

新增：在 `build_visuals.py` 的 `DATA` 里加一页（或写 `data/page-NN.json` 后补 DATA 引用），跑构建，再把页面 md 的图引用改成 `page-NN-visual.webp`。

## 已知边界

- 编辑器（editable-design 运行时）能改字/拖拽/缩放/导出；其 `verify.mjs` 的「拆解视图」若干布局断言对这类卡片版式不一定全过（改字/导出不受影响）。
- 文件是**实时 HTML 文本**，不是生成图；不要再用 AI 重画整张图，否则又回到不可 diff 的旧路。


## 实体 / 喻体对照版式（`layout: "entity_metaphor"`）

用于有"比喻解释"的页：左栏 `left_cards`（真实对象 + 职责 + 命令），右栏一张 AI 生成的喻体插画 `art/metaphor.jpeg`，下方 `mappings` 用 ①②③ 把喻体元素映射回真实职能；文字全部 HTML 实时文本，插画可重生成。

- 插画生成记录：每页 `art-prompt.md`（Seedream 端点/尺寸/prompt）。
- 注意：本机 `arkcli --input @本地图` 图生图需要 SSO 登录，当前为纯 prompt 生成；旧图归档在 `manual/images/archive/comics-v1/`。
- 示例：`manual/designs/page-00`、`page-01`、`page-02`。


## 编辑服务（给用户直接改）

```bash
scripts/design-serve.sh 8788
# 浏览器打开： http://127.0.0.1:8788/manual/designs/
```

- 入口页列出三张试点；点「编辑」进 `editor.html`：双击改字、拖动、四角缩放、顶部导出 HTML。
- 浏览器里的草稿存在 localStorage；要写回仓库需「下载 HTML」替换对应 `page-NN/index.html`，再跑 `python3 manual/designs/build_visuals.py NN` 重出 PNG/WebP。


## 在编辑器里改完，怎么「另存 / 覆盖保存」

编辑器没有"保存到仓库"按钮，分三层：

1. **浏览器草稿（自动）**：改完自动存 localStorage，刷新会恢复；只存在当前浏览器，不是仓库文件。
2. **另存文件**：点顶部「下载 HTML」→ 浏览器下载到下载目录（文件名以浏览器为准），这就是你的编辑版，可以自己改名保存。
3. **覆盖回项目**：

```bash
# 把下载的 HTML 覆盖 page-00 的 index.html，并重出 editor/PNG/WebP/阅读版
scripts/design-save.sh 00 ~/Downloads/index.edited.html

# 只重出当前 index.html 的 PNG/WebP（没有再传 HTML）
scripts/design-save.sh 00
```

- 覆盖前会备份旧版：`page-NN/index.YYYYMMDD-HHMMSS.bak.html`
- 会重新生成 `editor.html`（否则编辑器还显示旧版本）
- 会重渲染 `out/poster.png` → `manual/images/page-NN-visual.webp`，并重生成阅读版 HTML + 跑 audit

**注意**：`python3 manual/designs/build_visuals.py NN` 会用 `data/page-NN.json` **完全重建 index.html**，会覆盖你在编辑器里的手工改动。只想改文案时用它；想保留手工拖拽/排版时用 `design-save.sh`。


## 编辑器里的「另存为 / 覆盖保存」按钮（推荐）

用 `scripts/design-serve.py` 启动服务后（不是普通 `http.server`），每个 `editor.html` 右下角会出现两个按钮：

- **另存为 HTML**：把当前编辑版下载到浏览器下载目录（自己命名），即"另存"。
- **覆盖保存到项目**：直接把当前编辑版写回 `page-NN/index.html`，并自动：
  1. 备份旧版到 `page-NN/out/index.<时间戳>.bak.html`
  2. 重建 `editor.html`（继续可编辑）
  3. 重渲染 `out/poster.png` 与 `manual/images/page-NN-visual.webp`
  4. 重生成阅读版 HTML + 跑 `audit_book`（右下角显示结果）

启动：`python3 scripts/design-serve.py 8788`；入口 `http://127.0.0.1:8788/manual/designs/`。  
若服务没起，也可用命令行：`scripts/design-save.sh 00 ~/Downloads/page-00-edited.html`。
