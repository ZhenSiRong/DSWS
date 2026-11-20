# 第 21 页补图 · pdb 终端单步 + 12 节点左右对照 runbook
> 结论：离线单步证明「SQL 四节点各自执行到哪些判断」——guard 拒绝给名字、校正三条件都满足才 attempt 一次、候选过真解析器、二次校验通过才执行。不改页面/判据；页面第 21 页讨论 12 节点与 LangGraph，故图名用 `page-21-pdb-step.gif`（第 17 页已有 `page-17-live-correct.gif`，不抢名）。
## 1. 产物
- `manual/images/page-21-pdb-step.gif`：1600×2902 @2x / 66 帧 / 14cs/帧 / 9.24s 循环 / 1.2MB。左栏 12 节点时间轴 + 4 步回边，NODE 标记驱动高亮；右栏 pdb 终端逐行出现。
- `manual/review/pdb-step-transcript.txt`：真 pdb 会话 120 行（命令 + 源码行 + p 变量值；仓库绝对前缀已归一为相对路径）。
- `manual/review/pdb-step-frames/`：首/中/末帧 PNG（自检留证，可删）。
- 脚本：`manual/shots/pdb_step_demo.py`（被单步的离线程序）、`manual/shots/render_pdb_step.py`（PTY 录 pdb → 渲染 → 合成 → 自检）。
## 2. 重跑（仓库根目录；不启容器、不连 MySQL/ES/Qdrant/LLM）
```bash
python3 manual/shots/render_pdb_step.py                 # 录 pdb + 渲染 + 合成 + 自检
python3 manual/shots/render_pdb_step.py --capture-only  # 只重录 transcript
python3 manual/shots/render_pdb_step.py --render-only   # 用现有 transcript 只渲染
```
依赖（本机已装）：`backend/.venv`（Python 3.14）、google-chrome、ffmpeg、ImageMagick、tesseract（英文包）。
## 3. 断点行号与 pdb 命令序列（真实会话，脚本自动注入）
```text
# 启动（cwd=仓库根；PYTHONPATH=backend，break 才能用 app/... 相对 sys.path）
PYTHONPATH=backend backend/.venv/bin/python -m pdb manual/shots/pdb_step_demo.py
b app/generate/guard.py:306      # if violations: ——拒绝分支
b app/agent/correct.py:169       # if corrector is None: ——触发条件①
b app/agent/correct.py:176       # if not error.retryable: ——触发条件②
b app/agent/correct.py:183       # if policy.max_attempts < 1: ——触发条件③
b app/generate/provider.py:257   # parse_model_payload 的 return payload
b app/agent/validate.py:71       # validate_sql 的 return None（二次校验通过）
c
# 各断点停下后：p violations[0].code / p violations[0].message / p sql_before
# p corrector / p corrector.name / p error.code / p error.retryable
# p policy.max_attempts / p policy.revalidate / p attempts / p sql_after
# up / down 用来切到调用方帧看变量；n 下一行；c 到下个断点；q 退出
```
## 4. 这段演示证明了什么 / 不能证明什么
- 证明：四节点走真代码（`guard.check_sql` → `validate_sql` → `propose_correction` → `validate_sql` → `run_sql` 边界）；拒绝分支返回 `SQL_UNKNOWN_COLUMN` + 原因；三触发条件（有校正器 / 可重试 / `max_attempts=1`）全满足才为假模型产物 attempt 一次（attempts 1/1）；候选来自 `parse_model_payload` 解析的 JSON；二次 `validate_sql` 返回 `None` 才继续。
- 不能证明：假模型一定改对、假执行器的结果、真实时延——真实触发与成功现场见 `manual/review/correction-live-trigger.sse`（27 帧，`validate_sql:error → correct_sql:success → 二次 validate:success → run_sql:success`）。
- 诚实边界：GIF 右栏是 transcript 的「上屏节选」——启动 banner / 断点设置 / 程序结束后的 restart 尾巴不上屏（全文 120 行见 transcript）；左栏「真模型现场」数字直接从 SSE 解析，不是手抄。
## 5. 本次自检（脚本每次重跑都会重做，红则退出码 1）
- GIF：`identify` 1600×2902 / 66 帧 / 每帧 delay=14cs ⇒ 9.24s 循环 / 1.24MB（≤3MB）；`compare -metric AE` 首↔末 588659、首↔中 451141、中↔末 480813；全片唯一画面 51/66。
- 末帧 tesseract OCR 命中 `correct_sql` / `SQL_UNKNOWN_COLUMN` / `max_attempts` / `validate_sql` / `run_sql`；首/中/末三帧 OCR 均无 `zhensirong` / `/home/`；transcript 25 条关键证据全在、无敏感串。
- 首/中/末帧 sha256：`d0fe9ff2…` / `ef293f45…` / `5137f8a3…`（完整值见 `manual/review/pdb-step-frames/`，`sha256sum` 可复核）。
