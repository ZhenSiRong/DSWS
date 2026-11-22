# 第 17 页 v2 对抗式独立审查（R4 · 未采信 R2/R3 结论，自己重跑）

> 对象：工作区 `continue-iterate`（HEAD `f434c9f` + R1–R3 未提交改动），`page-17.md` 134 行。本报告只读+实测，未改任何页面/文档/代码，未提交、未起栈。

## 结论
**达到 v1.1.0 可发布标准（0 高）**：结构 24/24、`make audit` 4/4；第 1–5 步、拆一刀、还原的离线判据全部逐字复现；pdb / viztracer / scalene / pipx 四条新原子工具链真跑成立。R2 的 12 条复核 10 条干净，#9、#12 两条修复不完整（→M3、→L1），#1 补丁措辞带出 L2；另新发现 L4–L8（L6 是 README 未随 ACCEPTANCE 同步，非 R2 原条目）。建议发版前修 M1–M3（M1 决定第 6 步能否采到数），L 级可留 R5。

## 问题清单（0 高 / 3 中 / 8 低）
| 文件:行 | 问题 | 证据（命令 + 输出） | 严重度 | 建议 |
|:--|:--|:--|:--:|:--|
| page-17.md:52 | 第 6 步没写"需真模型"前置：默认栈是确定性生成器且**没有校正器**，3 次结局恒同一类，采不到"触发几次/成功几次" | `grep REBUILD_LLM .env.example` 三行值为空；`backend/app/main.py:104-121` 无 key→`DeterministicGenerator`+`None`；离线 `generate_sql('查询销售额大于平均销售额的商品')`→SQL 直接 `validate_sql` 返回 `None`（无校正机会）；p23 成熟版 8088 要到第 23 页才起 | 中 | 第 6 步补"先按 appendix/llm-endpoint 配 `REBUILD_LLM_*` 并重启 backend；不配 key 时后端走确定性生成器+无校正器，3 次结局完全相同" |
| gui-debugging.md:27 | py-spy"没在跑的脚本"命令照抄失败：`-- your_script.py` 是被直接 exec 的程序，普通 `.py` 没有 shebang/执行位就报错 | `py-spy record -o /tmp/p.json -f speedscope -- /tmp/r4work/tiny.py` → `Error: Failed to create process '…/tiny.py': Permission denied (os error 13)`；改 `-- /tmp/r4tools/bin/python …/tiny.py` → `Wrote speedscope file… Samples: 12`（加 shebang+chmod 才碰巧能跑） | 中 | 改 `py-spy record -o /tmp/p.json -f speedscope -- python your_script.py` |
| page-17.md:92 | 称 `eval/live_probe.py`"按同一套四类口径统计"不实：探针 classify 有**5 类**（多 `validate_fail_no_correction`）+ `transport_error`；页面四列表缺第 5 类，只对上了分母（success+fail） | `eval/live_probe.py:83` `return "validate_fail_no_correction"`、`:101` `transport_error`、`:119-120` `success_rate = success/(success+fail)` | 中 | 改"探针五类；成功率分母同为 success+fail"，或表下加脚注列 `validate_fail_no_correction`（validate 红但没进校正） |
| page-17.md:52 | 端口指路错：8088 由 p23 `docker run -p` 决定，8080 跟 `FRONTEND_HOST_PORT`；`BACKEND_HOST_PORT` 与这两个 UI 端口无关（nginx 内部反代 `backend:8100`） | `compose.yaml:133/160`、`docker/nginx.conf` `proxy_pass http://backend:8100`；`page-23.md:27-30` 起 8088 用 `-p 127.0.0.1:8088:80` | 低 | 改成"8088 被占就改 p23 的 `-p`；教学版 8080 跟 `FRONTEND_HOST_PORT`；`BACKEND_HOST_PORT` 只影响直连 API" |
| page-17.md:50 | "看完 `q`…；看完用 `c` 跑完这条，或 `q` 后重跑…"顺序矛盾：按了 q 已退出，不能再 c | 实测 q→`1 failed, 13 deselected`+`BdbQuit`；重新跑进断点后按 c→`1 passed, 13 deselected` | 低 | 改"想留现场按 `c` 跑完；按 `q` 退出后重跑整条 pytest 即回 `14 passed`" |
| gui-debugging.md:33-34 | scalene 装进项目 venv 后命令仍是裸 `scalene`（要 PATH/激活），与 viztracer 卡的显式路径不一致；1.x"直接出单文件"实测引用 CDN，不是自包含 | `scalene view --standalone`→1,695,149 B、0 个 `<script src>`；`view --html`→57,098 B、引 `jquery/bootstrap/prism` 且不写出；1.5.51 `--html --outfile`→1,606,725 B、引 `cdn.jsdelivr.net`/`code.jquery.com` | 低 | 项目 venv 情形写 `backend/.venv/bin/scalene …`；1.x 注明"单文件但资源在 CDN，离线双击不完整" |
| gui-debugging.md:78 | Zed 卡让改 `.zed/debug.json` 的"debugpy 端口"：仓库无 `.zed/debug.json`（样例在 `review/zed-debug/debug.json`），样例键无 port（只有 program/python/adapter…），端口只出现在 runbook 的手动 `--listen 127.0.0.1:5679` | `cat review/zed-debug/debug.json` → keys `['adapter','cwd','env','justMyCode','label','program','python','request','stopOnEntry']`；`ls .zed` → 不存在 | 低 | 改"把 `review/zed-debug/debug.json` 复制成 `.zed/debug.json`，换 `program`/`python` 路径；debugpy 端口由 adapter 自管" |
| OVERVIEW.md:69 + manual/README.md:142 | 仍把"真模型现场"单次运行当"看到/全书最强项"证据，无"单次、不能当判据"标注；与 p17/ACCEPTANCE/llm-endpoint 新口径不一致 | `grep -n '真模型现场' manual/OVERVIEW.md manual/README.md` 两处均列 `validate:error→correct:success→5 行`；`ACCEPTANCE.md:112` 已写"不能稳定复现、不能当判据" | 低 | 两处补"单次现场，不是判据；成功率按 trials≥3 采样" |
| manual/README.md:101 | p17 判据行仍把 `probe_correction.py` 列为常规判据，实际它只在「拆一刀」；ACCEPTANCE:44 已标"拆一刀另有" | `grep -n 'probe_correction' manual/page-17.md` → 仅 :114（拆一刀内）；`ACCEPTANCE.md:44` 已改口径 | 低 | README 行把 probe 移到"拆一刀另有"，与 ACCEPTANCE 同步 |
| page-00.md:15 | "附录工具卡与第 17 页会用到 [pipx 那套]"措辞：p17 实际用 `uv pip install` 装进 `backend/.venv`，不走 pipx | p17:45 只出现 `uv pip install --python backend/.venv/bin/python viztracer`；实测该路径可装（viztracer 1.1.1）且不改 `uv.lock` | 低 | 改"附录工具卡会用到 pipx；p17 另按该页第 5 步装进项目 venv" |
| page-17.md:50 | `--min_duration 1ms` 并非"只留慢于 1ms 的调用"（实测仍有 4 个 <1ms 的收尾事件）；不加时 169,176,892 B 且环形缓冲已丢早期数据，"170 MB"属实但解释不完整 | trace 3717 条中 4 条 `<1000µs`（atexit/finalizer）；不加参数时输出 `Circular buffer is full, you lost some early data` | 低 | 改"约留 ≥1ms 的调用；不加会 169 MB 且丢早期数据，可调 `--tracer_entries`" |

## 最严重 3 条（带证据）
1. **M1 第 6 步采不到数**：默认 `.env` 的 `REBUILD_LLM_*` 为空 → `backend/app/main.py:104-121` 用确定性生成器、校正器为 `None`；对页内同一问题，确定性 SQL 直接过校验（离线实测 `validation error: None`），所以无论点 3 次还是 curl 3 次都是"无需校正 3/3"，与页首"触发取决于模型是否生成可重试错误"矛盾。修法见上。
2. **M2 py-spy 命令照抄失败**：`-- your_script.py` 实测报 `Failed to create process…`（普通 .py 无执行位/shebang）；正确是 `-- python your_script.py`（实测生成 speedscope JSON）。
3. **M3 四类口径仍不实**：`live_probe.py:83/101/119` 有 `validate_fail_no_correction` 与 `transport_error` 两个页表未覆盖的类别；页面"同一套四类"应改成"五类+transport，分母 success+fail"。

## 真跑清单（仓库根、单 shell 连续执行）
- 前置/第 2–4 步：`failures --check | tail -2` → `S6 PASS`；pytest → `14 passed in 0.12s`；`--check` → 9 行场景 + `S6 PASS`；语料 → `9 false / 11 true / 11 corrected / 9 rejected`；`--scenarios | grep corrected` → `校正闭环成功 | result`。
- 第 1 步/拆一刀/还原：`lab save p17-before` → `169 个文件`；插 4 行后 → `5 failed, 9 passed in 0.15s`、`corrected 期望 result 实际 SQL_SYNTAX`、`FAIL: 1 项不符合预期`、probe `{"total": 20, "mismatch": 0}`；`lab reset --yes` → 生成 `pre-reset-…`、`现在工作区与快照 "p17-before" 完全一致。`、回 `14 passed` + `S6 PASS`，`correct.py` sha 复原。
- pdb（stdin 管道）：断点 `correct.py(183)`；`p policy.max_attempts`→`1`；`p error.retryable`→`True`；`p error.code`→`'SQL_SYNTAX'`；`p attempts`→`*** NameError`；`q`→`1 failed, 13 deselected`+`BdbQuit`；`c`→`1 passed, 13 deselected`；省 `-s`→`OSError: … Consider using -s.`；`b app/agent/…`→`not found from sys.path`。
- viztracer（按页装进 backend/.venv 1.1.1）：trace 3717 条 / `result.json` 9,881,946 B / 4.9 s；`propose_correction` 6 次 5.8–6.4 ms；`uv.lock` sha 前后不变，跑完已卸载（`find_spec` None）。
- scalene 2.4.0（临时 venv）：`run -o /tmp/s.json` + `view --standalone` → 1,695,149 B 自包含；`view --html` → 外部资源；另装 1.5.51 复核旧写法。pipx 1.18.19：`uv tool install pipx` + `pipx install viztracer py-spy scalene` 全装成（1.1.1/0.4.4/2.4.0）；`uv tool install viztracer` 干净环境亦成立；Studio 卡 `pipx install "langgraph-cli[inmem]"` 装成 0.4.43、`langgraph dev --help` 有 `--port`。
- 结构/审计：`wc -l page-17.md` → 134；六段 + 末段拆一刀；图片存在；`audit_book.py` → `24/24；坏链 0`；`make audit` → `AUDIT PASS：4/4`。

## 未跑 / 静态清单
- 第 6 步线上采样、真模型、`eval/live_probe.py` 实跑：**未跑**（不起栈、不配 key；只静态核对 `page-23.md`、`compose.yaml`、`.env.example`、`backend/app/main.py`）。
- LangGraph Studio 实起/联网、Chrome DevTools、Zed GUI 实拍：未跑（只核 CLI/命令/目录/样例；Studio 需联网已注明）。
- py-spy 容器内 `--cap-add SYS_PTRACE`、attach：本机 `yama ptrace_scope=1` 下非 root attach 被拒（环境限制，卡片已写"要对进程有权限"）。
- 容器/栈未启动；页面/文档/代码未改；未提交。

## 清理确认
- [x] pipx 应用（viztracer/py-spy/scalene/langgraph-cli）与 pipx 本体已卸；`uv tool list` 空；`backend/.venv` 无 viztracer（独立 venv 安装/卸载，`uv.lock` sha `742c289…` 前后一致，`git status` 无该文件）。
- [x] `/tmp/r4tools`、`/tmp/r4old`、`/tmp/r4work*`、`/tmp/s*.json|html`、`/tmp/p*.json`、日志、`result.json` 已删；`.lab/`（本次 `p17-before`+`pre-reset-…`）已删；`backend/app/agent/correct.py` sha `6b6966c…` 复原。
- [x] 另清理上一轮遗留的 `/tmp/scalene-*` 锁文件（R2 清理声明只覆盖 `/tmp/r2p17`，scalene 自落在 `/tmp` 的锁文件未被清）；本次结束 `git status` 与开工记录一致、无新增未跟踪临时文件。
