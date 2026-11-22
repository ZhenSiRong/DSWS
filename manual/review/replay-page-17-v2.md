# 第 17 页独立重放报告（学生视角 · L3 审纠错 · v2 原子工具版）

## 结论
能独立跟做：第 1–5 步 + 拆一刀 + 还原全部复现，新增第 5 步（viztracer 时间线 + pdb 断点）真跑通过，第 6 步需栈/真模型未跑。共 12 个问题：高 0 / 中 4 / 低 8；最该先修 ① p17:50 `q` 退出后 pytest 报 `1 failed…BdbQuit` 未预告（易被当成跑坏）② ACCEPTANCE:112「成功态不可复现」与 p17:7「v2 已复现」冲突 ③ 附录 scalene `--html` 不是自包含单文件（实测双击白页，应 `--standalone`）。

## 范围声明
- 真跑/方式：工作区 `continue-iterate`（含 R1 未提交改造）从仓库根单 shell 依次跑第 1–5 步、拆一刀、还原；无栈、无模型 key。15 条命令后 `pwd` 恒仓库根、无 exit 127；pdb 用 `printf` 管道喂键模拟键盘；拆一刀后 `lab reset` 还原（`correct.py` sha `6b6966c…` 复原）。
- 静态核对：附录 9 卡对当前 CLI（临时 venv 装 py-spy 0.4.4 / scalene 2.4.0，另装 scalene 1.5.51 核 1.x 写法）；page-00 预装段、6 个脚本头标、review/README 说明行、ACCEPTANCE L3；py-spy 采样/Studio 起服务只核 CLI 与已有证据，未重跑。
- 替换与差异：无端口/容器替换；headless 下 `--open` 不弹浏览器、只打印 `vizviewer result.json`（页面未兜底，记环境差异）。
- 时点与版本：2026-11-22 10:00–10:20（+08:00）；HEAD `f434c9f`；`page-17.md` sha `ffa7f14…`、`gui-debugging.md` `621ea6c…`、`page-00.md` `6a8b0c0…`、`backend/uv.lock` `742c289…`；viztracer 1.1.1。未做：第 6 步、P16 未还原反例（沿用 v1 实测 + TRAPS 9）、附录 py-spy/Studio 全流程。

## 环节表
| 环节（page-17.md:行） | 可执行? | 期望一致? | 问题数 |
|:--|:--:|:--|:--:|
| 前置（:3） | 是 | 是：自查 `--check \| tail -2` 见 `S6 PASS`，绿态照做成立 | 0 |
| 第 1 步 拍快照（:16-20） | 是 | 是：`已保存快照 "p17-before"：169 个文件。`（页面已注数字可变） | 0 |
| 第 2 步 pytest（:24-26、:68） | 是 | 是：`14 passed in 0.10s`（页面 0.11s，已注秒数变） | 0 |
| 第 3–4 步 矩阵+语料（:30-40、:69-75） | 是 | 是：`corrected 期望 result 实际 result`、`S6 PASS`；`9 false/11 true/11 corrected/9 rejected` 逐字一致 | 0 |
| 第 5 步 viztracer（:44-46、:50） | 是 | 部分：trace 3505 条 / `result.json` 9.2 MB / 3.6 s，`propose_correction` 6 次 5.8–6.3 ms；不加 `--min_duration` 实测 167 MB（≈170） | 1 |
| 第 5 步 pdb（:47、:50、:77-86） | 是 | 是：断点 `correct.py:183`、`p policy.max_attempts`=1、`p error.retryable`=True、`p attempts` NameError（诚实）；`-s` 缺失与 `b app/agent/…` 两条反例均复现；交互说明见问题 | 4 |
| 第 6 步 自己采多次（:52-61） | 否（需栈） | —：未起栈；静态与 page-23 8088、ACCEPTANCE 默认端口一致；四类表口径见问题 6 | 1 |
| 「你应该看到」/对账（:63-96） | — | 部分：第 2–4 步逐字一致；第 5 步块见问题 7–9；v2 引用 `README-v2.md:172`、`PRD-对照表.md:13`、FINDINGS §3.1/§2 逐条对上 | 0 |
| 拆一刀（:98-124） | 是 | 是：`5 failed, 9 passed in 0.14s`；只红 `corrected`（实际 `SQL_SYNTAX`）；probe `mismatch: 0` | 0 |
| 还原（:126-132） | 是 | 是：reset 末行一致；回 `14 passed in 0.11s` + `S6 PASS`；`correct.py` sha 复原 | 0 |
| 跨页与附带静态（:3、:7、:92；ACCEPTANCE；附录 9 卡/page-00/脚本头） | —（静态） | 部分：P16 前置、v2 证据、`llm-endpoint.md` 链接、6/6 夹具头标、review/README 说明行均在；9 卡均 4/4 结构、无学生入口指向仓库脚本；ACCEPTANCE:112/:44/:122 与 scalene/Studio/Zed/pipx 见问题 | 6 |
| **合计** | | | **12** |

## 问题清单
| page-17.md:行 | 原文摘录 | 问题（事实/歧义/跨页/易卡） | 建议改法 | 严重度 |
|:--|:--|:--|:--|:--:|
| :50 | 「看完 `q`（`-s` 不能省…）」 | 易卡：q 中途退出后 pytest 报 `1 failed, 13 deselected … BdbQuit`（实测），页面没说是预期，学生会以为把测试弄坏 | 补「q 会让这条测试记 `1 failed`（BdbQuit），是预期，不是环境坏」 | 中 |
| gui-debugging.md:33 | 「`scalene view --html` 生成单文件 HTML，双击也能看」 | 事实：scalene 2.4.0 实测 `--html` 的 html 引用 `jquery/bootstrap/prism/scalene-gui-bundle.js` 且这些文件未写出，双击白页；自包含单文件是 `--standalone`（实测 1.66 MB） | 改「`scalene view --standalone` 生成自包含单文件；`--html` 只生成引用外部资源的 HTML」 | 中 |
| manual/ACCEPTANCE.md:112 | 「**真 LLM 成功态不可复现**」 | 跨页/事实：page-17:7 已写 v2「已复现纠正成功态（自然问数+故障注入）」，只是不能保证每次复现；验收口径落后且与页面打架 | 改「真 LLM 成功态不稳定、不能保证每次复现（v2 已有成功样本）」 | 中 |
| page-00.md:15 | 「`pipx install viztracer py-spy scalene`」 | 易卡：pipx 不在必装五样、`make doctor` 不查、没给装法；本机实测 `pipx: command not found`，附录 4 卡安装行同样依赖 pipx | 补「先装 pipx（官网）」或改用已必装的 uv：`uv tool install viztracer py-spy scalene`；并给 p17:42「只装进」加「本页这一步」 | 中 |
| :50 | 「第二条进 pdb 后依次敲…」 | 歧义：第 5 步代码块 3 条命令（install / viztracer / pdb），pdb 是第三条，"第二条"无指代 | 改「第三条（pdb）…」或「接着跑 pdb 那条」 | 低 |
| :59-61 与 :92 | 四类表头「无需校正/触发并成功/触发失败/传输失败」；:92「live_probe 四类：无需校正/校正机会/校正成功/校正失败」 | 歧义：同页两套"四类"名称不同，"传输失败"也不在 `eval/live_probe.py` 分类里（其四类为 no_correction_needed / correction_opportunity / correction_success / correction_fail） | 表头与 :92 统一（如「无需校正/校正成功/校正失败/传输失败」），并写清分母=成功+失败 | 低 |
| :77 | 「Wall Duration 约 6.7 ms」 | 事实：同一命令本机 6 次调用 5.8–6.3 ms；"约"可接受，但给范围更稳 | 改「约 6 ms（本机 5.8–6.3）」 | 低 |
| :81 | 「> …(183)propose_correction() -> if policy.max_attempts < 1:」 | 事实：实际 pdb 输出两行（`> …(183)propose_correction()` 换行 `-> if …`），页面合并成一行，照抄对不上 | 拆回两行 | 低 |
| :77 | 「`p attempts` 会报 NameError——`attempts` 是 graph 状态里的计数…」 | 歧义：正文没让学生敲 `p attempts`，却在"你应该看到"解释它；解释本身诚实（实测 NameError；`graph.py:274` 初始 0、`:367` 校正成功才 +1） | 前文加「顺手敲 `p attempts` 会报…」，或改成 `p error.code`（实测 `'SQL_SYNTAX'`） | 低 |
| gui-debugging.md:67 | 「在带 `langgraph.json` 的目录跑 `langgraph dev --port 2024`」 | 易卡：本仓库 `langgraph.json` 只在 `manual/review/langgraph-studio/`，卡片没给目录，学生在仓库根起不来 | 补「本仓库：`(cd manual/review/langgraph-studio && langgraph dev --port 2024)`」 | 低 |
| gui-debugging.md:76 + review/zed-debug/debug.json | 「本项目样例在 review/zed-debug/debug.json」 | 跨页：样例 `program` 仍指教师夹具 `manual/shots/pdb_step_demo.py`（D54 学生入口原则残留；卡片已注未实拍） | 样例改指 `backend/tests/agent/test_correct.py` 或标注"仅演示配置" | 低 |
| manual/ACCEPTANCE.md:44、:122 | p17 逐页对账列 `eval/probe_correction.py`；L3 失败查找仍指 v1 报告 | 跨页：probe 只在 page-17 拆一刀跑，非第 1–5 步基线；失败查找未含本 v2 报告 | :44 标「（拆一刀）」；:122 补 `replay-page-17-v2.md` | 低 |

## 真输出摘录
```text
$ backend/.venv/bin/python -m pytest backend/tests/agent/test_correct.py -q
14 passed in 0.10s
$ (cd backend && .venv/bin/python -m app.scripts.failures --check) → corrected 期望 result 实际 result；S6 PASS
$ grep -o '"retryable": [a-z]*' eval/correction.jsonl | sort | uniq -c → 9 false；11 true
$ viztracer --open --min_duration 1ms -m pytest … → 14 passed；Total Entries: 3505；result.json 9.2 MB（3.6 s）
$ python -m pdb -m pytest … -s -k "proposes_a_new_sql" → 断点 correct.py:183；p policy.max_attempts→1；p error.retryable→True；p attempts→NameError
拆一刀：5 failed, 9 passed in 0.14s / corrected 实际 SQL_SYNTAX / probe {"total": 20, "mismatch": 0}
reset → 现在工作区与快照 "p17-before" 完全一致。→ 14 passed in 0.11s；S6 PASS
```

## 清理确认
- [x] 容器/compose：未启动；用户栈未触碰。viztracer 按页装进 `backend/.venv` 后已卸载（`find_spec` False）。
- [x] 临时文件：仓库根 `result.json` 已删；`.lab/`（`p17-before` + `pre-reset-…`）已删；`/tmp/r2p17` 已删（含 167 MB full-trace、py-spy/scalene 临时 venv）；`backend/uv.lock` sha `742c289…` 前后一致。
- [x] 审计：`python3 manual/shots/audit_book.py` → `页面：24/24 通过；README 坏链：0`；`make audit` → `AUDIT PASS：4/4 全绿`。
- [x] 只新增本报告 + `review/README.md` 索引行；`page-17.md`、`gui-debugging.md`、`page-00.md` sha 前后一致（见范围声明）；`backend/app/agent/correct.py` sha 复原 `6b6966c…`。

## 8 类必查清单（逐条打勾再交）
- [x] **uv.lock 改写**：→ 通过：`uv pip install --python backend/.venv/bin/python viztracer` 前后 sha `742c289…` 不变，卸载后仍不变，`git status` 无 uv.lock。
- [x] **cwd 子 shell**：→ 通过：含 `cd backend` 的命令全在 `( … )` 里；15 条命令后 `pwd` 恒仓库根、无 exit 127。
- [x] **管道退出码**：→ 通过：页内 5 处管道（tail/uniq）只取文字不当门禁；拆一刀 pytest 单独命令实测 exit=1，红判据看 `FAIL: 1 项不符合预期` 文本。
- [x] **端口与 `.env`**：→ 部分：第 6 步未跑（需栈）；8088/8080 与 page-23/ACCEPTANCE 默认一致，但页面未提醒"改过 `.env` 用你的端口"（低，未单列）。
- [x] **lab 快照边界（DB、uv.lock）**：→ 通过：只快照白名单 169 文件；DB/uv.lock 不在；reset 后 `correct.py` sha 复原，`pre-reset-…` 实测生成。
- [x] **重录假绿**：→ 不适用：本页无 `record_sse`/夹具重录；拆一刀读 `eval/` 语料，不产生假基线。
- [x] **精确行号与同名代码**：→ 通过：`correct.py:183` = `if policy.max_attempts < 1:`；`policy = contract.correction` 源码唯一；`def propose_correction` 唯一；`b app/agent/…` 实测报 not found。
- [x] **跨页前置回绿**：→ 通过：:3 可执行自查真跑得 `S6 PASS`；P16 未还原后果沿用 v1 实测（`1 failed, 13 passed` / `mismatch 3`），本次未重造；ACCEPTANCE:112 冲突另列问题 3。
