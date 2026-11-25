# 第 17 页 v3 收口报告（R5 · 发布前终验）

> 依据：[adversarial-page-17-v2.md](adversarial-page-17-v2.md)（R4 对抗审查：**0 高 / 3 中 / 8 低**，共 11 条）。分支 `continue-iterate`，HEAD `f434c9f` + R1–R4 未提交改动。本轮**只改文档/页面/配置**（未动 `backend/`、`frontend/` 实现代码），**未提交**（commit 由 lead 做）、**未启动容器/栈**。

## 一、11 条逐条状态

| # | 报告位置 | 严重度 | 状态 | 改动（文件:行） |
|:--|:--|:--:|:--:|:--|
| 1 | page-17.md:52 第 6 步缺真模型前置 | 中 | **已修** | `page-17.md:52`：标题改「自己采多次（**本步要真模型**）」；写清默认栈不配 key 时后端走确定性生成器、`_build_corrector()` 返回 `None`——同一问题一次过校验，只会采到「无需校正 3/3」，采不到触发/成功，**这是预期不是 bug**；要采先按 `appendix/llm-endpoint.md` 配 `REBUILD_LLM_*` 再 `docker compose up -d --force-recreate backend` 重启、先跑 `scripts/llm_check.py` 自检；没配 key/没起栈就跳过。`:3` 前置同步改「只有第 6 步要真模型 + 开栈」。**端口指路**：成熟版 `8088` 来自第 23 页第 2 步 `docker run -p 127.0.0.1:8088:80`；只按第 13 页起整栈默认是教学版 `8080`；`:57` 写清 `FRONTEND_HOST_PORT`（教学版界面入口，nginx 反代 `backend:8100`）与 `BACKEND_HOST_PORT`（只影响直连 API）的区别，并说明与 8080/8088 两个界面无关。 |
| 2 | gui-debugging.md:27 py-spy 卡命令照抄失败 | 中 | **已修** | `gui-debugging.md:27`：没在跑的脚本改成 `py-spy record -o /tmp/p.json -f speedscope -- python your_script.py`，并注明 `--` 后必须跟**解释器命令**（直接写 `-- your_script.py` 报 `Permission denied`）；对运行中进程仍为 `-p <pid>`。实跑补丁：本机 `python` 不在 PATH，故卡片加「系统里没有 `python` 就写 `python3`，或写解释器全路径」。 |
| 3 | page-17.md:92 live_probe 实为 5 类 | 中 | **已修** | `page-17.md:92`：改「按同一套**五类**口径统计：无需校正 / 触发并成功 / 触发失败 / 校验红但没进校正 `validate_fail_no_correction`，另有传输失败 `transport_error`；成功率分母同为 success+fail、不含后两类」；`:57` + 表格同步升为五列（新增「校验红未校正」），「四类表」改「五类表」，分母说明保留。 |
| 4 | page-17.md:50「看完 `q`…用 `c`」顺序矛盾 | 低 | **已修** | `page-17.md:50`：改「想留现场就按 `c` 跑完这条；若直接按 `q` 退出，pytest 会记一条 `1 failed, 13 deselected … BdbQuit`（pdb 中途退出的预期记录，不是把测试弄坏），重跑整条 pytest 即回 `14 passed`」。实跑复现 `q`→`1 failed, 13 deselected`、`c`→`1 passed, 13 deselected`。 |
| 5 | gui-debugging.md:33-34 scalene 裸命令/1.x 非自包含 | 低 | **已修** | `gui-debugging.md:33`：装进项目 venv 后命令写 `backend/.venv/bin/scalene`（或 `uv run scalene`），并注明「别敲裸 `scalene`」；`:34`：1.x 旧写法补「直接出单文件，但仍引 CDN 的 jquery/bootstrap/prism，离线打开不完整，**非自包含**」；2.x `--standalone` 大小按本轮实测改「约 1.7 MB、随 profile 数据变」。 |
| 6 | gui-debugging.md:78 Zed 卡「debugpy 端口」 | 低 | **已修** | `gui-debugging.md:78`：删「debugpy 端口」说法，改「新建 `.zed/debug.json`（仓库里没有这个文件，样例在 `review/zed-debug/debug.json`，复制一份到 `.zed/debug.json`），换 `program`/`python`；调试端口由 Zed 的 debugpy adapter 自己管，不用手填」。 |
| 7 | OVERVIEW.md:69 + README.md:142 单次真模型现场当证据 | 低 | **已修** | `OVERVIEW.md:69`、`README.md:142`：现场那行补「**单次现场样例，不是成功率证据**，成功率按 `trials≥3` 多次采样写」。 |
| 8 | README.md:101 probe 口径落后于 ACCEPTANCE | 低 | **已修** | `README.md:101`：p17 判据行删掉常规 probe，改成「`14 passed` + `S6 PASS` + 语料 11/9；**拆一刀另有** `probe_correction.py` → `{"total": 20, "mismatch": 0}`」，与 `ACCEPTANCE.md:44` 一致。 |
| 9 | page-00.md:15「第 17 页会用到 pipx」措辞 | 低 | **已修** | `page-00.md:15`：改「附录工具卡会用到；**pipx 是「换项目/可选工具」的通用装法**」；保留 `uv tool install pipx` / 系统 pip 两条装法，以及「p17 要追项目自己的 pytest 时另按该页第 5 步装进 `backend/.venv`」的区分。 |
| 10 | page-17.md:50 `--min_duration 1ms` 解释不完整 | 低 | **已修** | `page-17.md:50`：改「约留 ≥1ms 的调用（收尾事件仍可能 <1ms，属正常）；不加它会写满环形缓冲、丢早期数据——实测约 170 MB，浏览器打不开；嫌大也可调 `--tracer_entries`」。附录 viztracer 卡 `:22` 同步同一口径。 |
| 11 | 报告其它低优先项 | — | **已处理** | ① `review/README.md` 索引补 R3 修复、R4 对抗、R5 收口三行（原来只停 R2 重放）；② 四类→五类归并边角（R3 残留偏差 2）已按 #3 处理；③ `make doctor` 加 pipx 检查**不改**：`Makefile` 属门禁/实现，本轮约束只改文档/页面/配置，page-00 已把 pipx 明标可选并给 uv/临时 venv 替代；④ 历史报告 `replay-page-17-v2.md` 保持原样（证据与行号是当时状态）。 |

**附录自检额外发现（非 R4 条目）**：LangGraph Studio 卡在干净 pipx 环境里照卡片命令跑会 `ModuleNotFoundError: No module named 'sqlglot'`（`langgraph.json` 的 `dependencies` 指 `backend`，图会 import 后端依赖）。已修 `gui-debugging.md:68`：先 `pipx inject langgraph-cli pyyaml sqlglot pymysql jsonschema`，一条命令加 `--no-browser`；修后原命令起得来（见终验 §2.5）。

## 二、终验输出（2026-11-22 真跑）

### 2.1 结构 / 审计

```text
$ python3 manual/shots/audit_book.py
页面：24/24 通过；README 坏链：0

$ make audit
== 2/4 空白错误：git diff --check ==
  OK：无空白错误
== 3/4 backend/uv.lock 是否被 uv 改写 ==
  OK：backend/uv.lock 与仓库一致
== 4/4 敏感串：manual/ 不得出现 zhensirong 或 /home/ ==
  OK：manual/ 无敏感串
AUDIT PASS：4/4 全绿（结构 / 空白 / uv.lock / 敏感串）
```

### 2.2 p17 结构与约束

- `wc -l manual/page-17.md` → **134**（≤134；本轮新增文字全部落在既有行内，未增行）。
- `grep -c '^## '` → **6**；末段 `## 拆一刀（L3 级考核）`；段序 = 这一页构建什么 / 猜一猜 / 动手 / 你应该看到 / 对账 / 拆一刀。
- `grep 'manual/shots/' manual/page-17.md` → **无匹配**（无教师脚本入口）。

### 2.3 p17 离线判据复跑

```text
$ backend/.venv/bin/python -m pytest backend/tests/agent/test_correct.py -q
14 passed in 0.11s

$ (cd backend && .venv/bin/python -m app.scripts.failures --check)
== 2/2 错误码表（路线图点名的 7 个码必须都在） ==
  错误码表：16 个码，路线图要求的 7 个全在
S6 PASS

$ PYTHONPATH=backend backend/.venv/bin/python eval/probe_correction.py | tail -1
{"total": 20, "mismatch": 0}
```

### 2.4 bash -n / 敏感串 / uv.lock

- `bash -n`：对本轮 `git status` 里 **14 个改动 md** 抽出的 **30 个 ```bash 块**逐块检查 → **失败 0**。
- 敏感串：本轮改动的 5 个正文件（page-17、gui-debugging、OVERVIEW、README、page-00）`grep -nE 'zhensirong|/home/|/Users/|sk-…'` → **全部无匹配**；`make audit` 第 4 项通过。
- `git status --short backend/uv.lock` → **空**（uv.lock 干净；viztracer 装进 `backend/.venv` 前后 sha `742c289…` 一致）。

### 2.5 附录 9 张卡逐卡自检

| 卡 | 自检命令 / 样本 | 结果 |
|:--|:--|:--|
| viztracer | viztracer 1.1.1（pipx 装）`viztracer --help`；小样本 `viztracer -o v.json tiny.py`；项目 venv 里 `backend/.venv/bin/python -m viztracer --min_duration 1ms -m pytest …` | `--open/--attach/--min_duration/--tracer_entries` 均在；小样本 `traceEvents: 6`；项目 venv 跑出 `Total Entries: 3732` + `result.json` 9,877,677 B（≈9.88 MB），卸装后 `find_spec`=None |
| py-spy | 0.4.4：`py-spy record -o p.json -f speedscope -- python3 tiny.py`；旧写法 `-- tiny.py` 复现 | 新写法 `Wrote speedscope file … Samples: 6`；旧写法 `Failed to create process … Permission denied (os error 13)`；注意本机无 `python` 命令（卡片已加 `python3`/全路径兜底） |
| scalene | 2.4.0：`scalene run -o s.json heavy.py`；`scalene view --standalone s.json`；`scalene view --html s.json` | run 产出 117,727 B；`--standalone` → 1,778,583 B、`<script src` **0 个**（自包含）；`--html` → 140,532 B、3 个外链 script（jquery/bootstrap/prism，双击白页）。1.x（1.5.51）"引 CDN 非自包含"沿用 R4 实测 |
| pdb | 页面原命令 + stdin 管道：`b correct.py:183`→`c`→`p`×3→`q` / `c` | 断点 183 命中；`p policy.max_attempts`→`1`、`p error.retryable`→`True`、`p attempts`→`*** NameError`；`q`→`1 failed, 13 deselected`；改 `c`→`1 passed, 13 deselected` |
| pytest | `backend/.venv/bin/python -m pytest … -q`；`-k proposes_a_new_sql` | `14 passed`；`1 passed, 13 deselected` |
| curl | `curl --help all` 查 `-sN` 参数 | `-N, --no-buffer` 存在；完整 SSE 需真栈，本轮按约束未起栈（静态核对） |
| Chrome DevTools | 无命令（F12） | 需真栈 + 浏览器，本轮未跑（约束；卡片已有说明） |
| LangGraph Studio | pipx 0.4.43：`langgraph dev --help`、`langgraph.json` 校验、注入依赖后按卡命令起 30s | `--port`/`--no-browser` 在；裸 pipx 环境复现 `ModuleNotFoundError: sqlglot`→按补充 `pipx inject` 后启动成功（打印 API/Studio URL、无 `failed to load`），随后杀掉并删临时 `.langgraph_api/` |
| Zed | `zed --version`（1.30.2）；`python3 -m json.tool review/zed-debug/debug.json`；`ls .zed` | CLI 可用；样例 JSON 合法，键 = adapter/cwd/env/justMyCode/label/program/python/request/stopOnEntry（**无 port**）；`.zed/` 不存在 → 卡片"复制样例自建"与实际一致；GUI 未实拍（headless） |

### 2.6 清理确认

- [x] 临时安装全卸：`pipx uninstall-all`（langgraph-cli / py-spy / scalene / viztracer）+ `uv tool uninstall pipx`；`uv tool list` → `No tools installed`；`command -v pipx py-spy scalene viztracer langgraph` 全无。
- [x] pipx 数据目录（`~/.local/share/pipx`、`~/.cache/pipx`、`~/.local/state/pipx`）与 `/tmp/r5work`、`/tmp/lgs-r5`、`result.json`、`manual/review/langgraph-studio/.langgraph_api/` 已删；无残留 langgraph/viztracer 进程、2024 端口未监听。
- [x] `backend/.venv` 的 viztracer 及其传递依赖 objprint 已卸（`find_spec` 均为 None）；`backend/uv.lock` sha 前后一致、`git status` 干净。
- [x] 未启动容器/栈（`docker compose ps` 未触碰），未提交。

## 三、文件 diff 摘要（本轮）

| 文件 | 改动 |
|:--|:--|
| `manual/page-17.md` | :3 前置；:50 pdb 顺序 + `--min_duration`/`--tracer_entries`；:52 第 6 步真模型前置 + 端口指路；:57 五类表 + 端口区别；:59-61 表格加「校验红未校正」列；:92 五类口径。**行数 134 不变**。 |
| `manual/appendix/gui-debugging.md` | :22 viztracer 环形缓冲口径；:27 py-spy 新写法 + 解释器兜底；:33-34 scalene 项目 venv 路径 / 1.x 非自包含 / standalone 1.7 MB；:68-69 Studio 依赖注入 + `--no-browser`；:78 Zed 自建 `.zed/debug.json`、删 debugport。 |
| `manual/OVERVIEW.md` | :69 单次现场 = 不是成功率证据。 |
| `manual/README.md` | :101 p17 probe 移到「拆一刀另有」；:142 单次现场标注。 |
| `manual/page-00.md` | :15 pipx 措辞（通用装法；p17 另按第 5 步装项目 venv）。 |
| `manual/review/README.md` | 索引补 R3 修复 / R4 对抗 / R5 收口三行。 |
| `manual/review/fix-page-17-v3.md` | 本报告（新增）。 |

本轮未触碰（保持 R1–R3 状态）：`manual/ACCEPTANCE.md`、`manual/appendix/llm-endpoint.md`、`manual/shots/*.py`（+1 行是前几轮改动）、`humen-desicions/TODO.md` 等。

## 四、残留偏差 / 明确不改

1. **第 6 步线上采样与真模型未跑**：本轮约束「不启动容器/栈、不配 key」，第 6 步修的是「不配 key 时页面不再误导 + 配了怎么采」的口径与流程（`appendix/llm-endpoint.md` + `scripts/llm_check.py`），线上四/五类采样留待有栈环境。
2. **py-spy `-p <pid>` attach 未实跑**：本机 `yama ptrace_scope=1`，非 root 对非子进程 attach 被拒（与 R4 相同的环境限制）；卡片已写「要对进程有权限／容器内 `--cap-add SYS_PTRACE`」，spawn 新写法已实跑。
3. **scalene 1.x 未重测**：1.5.51 的 CDN 证据沿用 R4 实测；2.x 两种 `view` 本轮均已复跑。
4. **curl / Chrome DevTools 完整链路未跑**：需真栈；只做了参数级静态核对（`-N`），真栈行为已有 p7/p8/p23 与 R4 证据。
5. **Zed / Studio 的 GUI 未实拍**：Zed 无窗口实拍（headless）、Studio 远程 LangSmith UI 需联网；本地 CLI/配置/API 启动已验证，卡片与「诚实边界」已注明。
6. **`make doctor` 未加 pipx 检查**：`Makefile` 属门禁实现，本轮不改实现；理由与替代写法见 #11。
7. **历史报告不改**：`review/replay-page-17-v2.md`、`review/adversarial-page-17-v2.md` 的结论/严重度是当时快照，保留原样；修复状态以本报告为准。
8. **p17 五类表与探针的边角**：页面表是「学生现场观察」的五栏（把 `validate_fail_no_correction` 单列），与 `eval/live_probe.py` 的 5 个 class 名一一对应；分母口径 success+fail 与探针 `correction_success_rate` 一致，未再改实现。
