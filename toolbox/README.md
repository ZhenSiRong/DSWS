# toolbox · 制作教程的工具

- `page-visuals/`：页首图设计源与构建器 `build_visuals.py`；`data/page-NN.json` 是文案数据，`page-NN/editor.html` 可改字/拖拽/导出。
- `shots/`：截图、图表、执行轨迹渲染；`audit_book.py` 结构审计，`render_read.py` 阅读版生成。
- `verify/`：T0/T1 契约与 `README.md`；`contracts/page-NN.yaml`。
- `scripts/`：验收、docker、lab、task 台账、设计编辑服务。
- `workflows/`：任务台账与评审。

入口：`python3 toolbox/shots/audit_book.py`、`python3 toolbox/scripts/verify.py --fast`、`make audit`/`make verify`。
