# 附录图 · VizTracer 时间线 evidence（2026-11-21）

> 本目录是 `manual/appendix/gui-debugging.md` 里 VizTracer 一节的实测证据。
> 生成物：`trace.json`（viztracer 原始 trace）/ `timeline.html`（单文件离线时间线）/
> 两张整窗截图 / 截图流水线脚本。**不提交**（review/ 证据，按仓库惯例留工作区）。

## 0. 环境

- Python：`backend/.venv` 的 3.14.8（复用 backend 依赖，不新装东西进仓库 venv）
- VizTracer：1.1.1，只装进一次性 venv `/tmp/vizenv`
- 浏览器：Google Chrome 155（headless）
- 被追踪代码：`manual/shots/trace_viztracer.py`（离线夹具，复用 `pdb_step_demo.py` 的
  `FakeGenerator` / `FakeExecutor`；不连模型、不连 MySQL、不启容器）

## 1. 复现命令（仓库根目录）

```bash
uv venv /tmp/vizenv --python 3.14
uv pip install --python /tmp/vizenv/bin/python viztracer

PYTHONPATH=/tmp/vizenv/lib/python3.14/site-packages \
    backend/.venv/bin/python manual/shots/trace_viztracer.py
# → manual/review/viztracer/trace.json + manual/review/viztracer/timeline.html

python3 manual/review/viztracer/capture_timeline.py
# → gui-overview.png / gui-selected.png / manual/images/gui-viztracer.png
```

## 2. 产物与实测数字

| 文件 | 内容 | 大小 |
|:--|:--|--:|
| `trace.json` | viztracer 原始 trace：2169 条事件（2167 条 X 事件） | 430,813 B |
| `timeline.html` | trace 内联进 viztracer 自带前端，单文件离线可开 | 2,867,204 B |
| `gui-overview.png` | 整窗 1600×1000，初始视图 | 82 KB |
| `gui-selected.png` | 点选 `guard_check` 条带后：Title / Start / Wall Duration / Self Time | 114 KB |
| `manual/images/gui-viztracer.png` | 裁到函数条带的成图 1600×550 | 171 KB |

同一次 trace 的耗时（`trace.json` 里 X 事件的 dur，单位换算成 ms）：

| 条带 | dur |
|:--|--:|
| `ask_once`（整条约 60.62 ms） | 60.62 ms |
| `graph_context_stages`（8 个上下文阶段） | 29.42 ms |
| `guard_check`（check_sql + validate_sql） | 15.78 ms |
| `correct_retry`（3 个触发条件 + 校正） | 8.85 ms |
| `second_validate` | 6.51 ms |
| `run_fake_sql`（假执行器边界） | 0.02 ms |

点选 `guard_check` 的详情面板读数为 `Wall Duration 15,784,580 ns`（与上表一致）。

## 3. 截图与 OCR 验证

```bash
python3 -c "from PIL import Image; im=Image.open('manual/images/gui-viztracer.png'); print(im.size)"
# (1600, 550)
tesseract manual/images/gui-viztracer.png stdout -l eng
```

OCR 输出（节选）：`ask_once  graph_context_stages correct_retry OfflineContextBuilder.__init__
valida... propos... build... bu... loa... d valida... enforce default_catalog`
→ `graph`、`correct` 命中 2 个（`guard` 条带在图上肉眼可读，OCR 未读出，按判据 ≥2 即通过）；
OCR 结果里无用户名、无 `/home/`、无绝对路径。

## 4. 与任务卡的偏差（都是工具现状，不是跳过验证）

1. **`vizviewer --output` 不存在**：`viztracer 1.1.1` 的 `vizviewer` 只有服务器模式
   （`vizviewer trace.json` 起本地 Perfetto 页面），没有 `--output`。单文件 HTML 走
   `viztracer.report_builder.ReportBuilder(...).save(html, file_info=False)`，与任务卡给的
   「Python API + vizviewer 模块」兜底等价。`vizviewer` 仍可用来看 raw trace
   （`vizviewer trace.json` 起本地 Perfetto 页面），但单文件 `timeline.html` 不需要它。
2. **`google-chrome --headless --screenshot` 拍不到时间线**：无头模式等到 load 就截图，
   而 `timeline.html` 的 trace 是 load 之后由 JS 异步导入的，直接拍只得到
   “Importing clock sync markers” 对话框（已复现）。改成 headless Chrome + DevTools 协议
   （`capture_timeline.py`）：等 10 s 导入完成再 `Page.captureScreenshot`。
3. **标签路径脱敏**：viztracer 原始事件名是 `函数名 (绝对路径:行号)`，直接进浏览器会把
   本机路径显示在时间线条带上。`trace_viztracer.py` 只在生成 HTML 时把事件名剥成函数名，
   `trace.json` 保持 viztracer 原始产物（因此 raw trace 里仍含路径，本目录留在工作区不提交）。
4. **成图是裁图**：整窗截图含工具栏、右侧空白和悬浮面板，成图只裁函数条带
   （裁剪框 `(497, 90, 1515, 440)` → 宽 1600），未重绘、未改色、未拼贴。

## 5. 清理

- `/tmp/vizenv`（一次性 venv）与 `/tmp/vizshot`（截图试验）跑完删除；仓库 venv 未安装 viztracer。
- 本目录保留 `trace.json` / `timeline.html` / 两张 png / `capture_timeline.py` 作证据，不提交。
- 未改 24 页正文、未碰 `manual/images/page-23-exec-trace.gif`。
