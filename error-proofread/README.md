# error-proofread · 真机实测问题台账

本目录收「用户实跑 / 校对时发现、且已修正」的练本问题，一行一条，格式固定：

**日期 | 页 | 问题 | 修法 | 验证**

截图等证据按页命名，放在本目录；对应正文与生成脚本以仓库当前版本为准。

| 日期 | 页 | 问题 | 修法 | 验证 |
|---|---|---|---|---|
| 2026-11-18 | 第 3 页 | 终端 1 实际会继续打印访问日志（`INFO: 127.0.0.1:<临时端口> - "GET /health HTTP/1.1" 200 OK`），页面「你应该看到」只列启动日志，与实测不一致；另实测出现陌生路径 404（如 `GET /v1/models`），容易被误认为本页代码出错 | `page-03.md`：`## 你应该看到` 补访问日志说明，`## 对账` 新增陌生路径 404 解释（本机别的程序在探测 8000，忽略即可，也可换端口）；`term_render.py` 新增 `log` 步骤类型与单页渲染；重生成 `page-03-health.png`（含访问日志行） | 只重跑 `term_render.py page-03`：启动日志 + `GET /health` 访问日志上图，`{"ok":true}` 与页面「你应该看到」逐行对账通过（commit 6e279a8）；实测对照图留档 `page3-终端1的预期输出与我实际看到的不一样.png` |
| 2026-11-18 | 第 0 页 | `make doctor -v` 实测只打印 GNU Make 版本：`-v` 被 make 自己吃掉，`doctor` 根本没执行 | 正文改用 Makefile 已有入口 `make doctor-v`（= `bash scripts/doctor.sh -v`），并注明「`-v` 会被 make 吃掉，所以是 `doctor-v`」；同批把「七件事」改为「三件事（工具、依赖、端口）」、「第 5 项检查」改为「`make doctor` 的端口检查」 | 审计记录见 `manual/review/completeness-audit.md` 第 53–54 行；commit 20b913f 记录 `make doctor` 12/12 通过、`page-00-prep.png` 同步重生成 |
| 2026-11-18 | 第 6 页（连锁第 7、8 页） | 第 6 页原让把 24 行整段插在 `extract_keywords` 与 `@app.get("/health")` 之间，导致 `if __name__ == "__main__":` 入口块被塞进文件中间；第 7 页又要求在 `build_sql` 与 `@app.get` 之间插 `run_sql`，这个间隙被入口块占住，学生必然插错；第 8 页再让「接在文件最后」，会再叠一层，最终块顺序混乱 | `page-06.md`「## 动手」拆成两步：前 21 行（`CONTRACT` + `build_sql`）插中间，最后 3 行（空行 + `if __name__` + `print`）追加到文件最末尾，并说明「这 3 行是程序入口，故意放最后：uvicorn 导入模块时不执行，只有 `python -m lab.app` 才执行」；`page-08.md` 改为接在 `@app.post("/api/query")` 之后、`if __name__ == "__main__":` 那 3 行之前；`page-07.md` 原指令复核与新结构无冲突，不改；`term_render.py` 第 6/7/8 页的组装文件同步改为 `__main__` 永在末尾（仅内部实现，终端输出不变） | 从第 5 页完整代码块出发、按三页新文字逐字组装：`grep -n "__main__"` = 94（全文件最大顶层块行号，其后只剩 `print`）；8001 实跑（不用 8000）：`backend/.venv/bin/python -m lab.app` 5 行 SQL、`/health` 回 `{"ok":true}`、`curl /api/stream` 的 `progress` = 12 + 1 条 result（`41099.5`）；`term_render.py page-06` 重跑逐行对账 ✅，重生成图与旧图逐像素一致（已还原，图像无变更）；`term_render.py` 调整后的 APP_PAGE_06/07/08 也逐个在 8001 实跑通过（5 行 SQL / rows 41099.5 / progress=12）；page-08 对应组装文件只多一个文件末尾 `__main__` 守卫（uvicorn 不执行），因用户 8000 端口被占用未重拍，流式输出行为不变 |
