# 第 17 页 v2 重放问题修复报告（R3 · 修复者）

> 依据：[replay-page-17-v2.md](replay-page-17-v2.md)（12 条：0 高 / 4 中 / 8 低）。分支 `continue-iterate`，HEAD `f434c9f` + R1 未提交改造；本报告只记录改动与只读核对，**未提交**。

## 一、12 条逐条状态

| # | 报告位置 | 严重度 | 状态 | 改动（文件:位置） |
|:--|:--|:--:|:--:|:--|
| 1 | p17:50 `q` 退出后 BdbQuit 未预告 | 中 | **已修** | `page-17.md:50` 补：`q` 会让 pytest 记一条 `1 failed, 13 deselected … BdbQuit`，是 pdb 中途退出的预期记录，不是把测试弄坏；用 `c` 跑完这条，或 `q` 后重跑整条 pytest 即回 `14 passed` |
| 2 | ACCEPTANCE:112「成功态不可复现」与 p17:7 口径冲突 | 中 | **已修** | `page-17.md:7`：v2 改为「**单次复现过**纠正成功态」+ 证据 `v2-natural-correct-success.sse`，`**不能稳定复现、不能当判据**`；`ACCEPTANCE.md:112`：标题改「**真 LLM 成功态不能稳定复现、不能当判据**」，补 v2 单次证据，保留 `trials>=3` + 成功率 + 失败分类 |
| 3 | 附录 scalene `--html` 非自包含 | 中 | **已修** | `gui-debugging.md:33-35`：改为 2.x（实测 2.4.0）`scalene view --standalone`（自包含单文件约 1.66 MB）；写明 `--html` 引用 jquery/bootstrap/prism 等外部资源、双击白页；保留 1.x（实测 1.5.51）`scalene --html --outfile …` 旧写法；命令标注版本 |
| 4 | page-00 没教装 pipx、附录 4 卡依赖 pipx | 中 | **已修** | `page-00.md:15` 补 pipx 安装：首选 `uv tool install pipx`（装完 `pipx --version` 自检），或 `python3 -m pip install --user pipx && python3 -m pipx ensurepath`（系统 Python 无 pip 时用 uv 那条）；说明不装 pipx 可用 `uv tool install viztracer` 或临时 venv 替代；`gui-debugging.md:3-5` 附录开头补「安装前提」；`page-17.md:42`「只装进」→「本页这一步只把」 |
| 5 | p17:50「第二条」指代不清 | 低 | **已修** | `page-17.md:50` → 「第三条（pdb 那条）」（第 5 步代码块 3 条命令，pdb 是第三条） |
| 6 | p17:77 `p attempts` 悬空/NameError 说明 | 低 | **已修** | `page-17.md:50` 命令旁括号加「顺手敲 `p attempts` 会报 `NameError`，原因见下」；`:77` 解释顺成一段：`attempts` 是 graph 状态计数（`graph.py` 初始 0、校正成功才 +1），不在 `propose_correction` 这一帧 |
| 7 | p17:81 pdb 输出实际两行、页面合成一行 | 低 | **已修** | `page-17.md:79-86` 拆回两行：`> …(183)propose_correction()` + `-> if policy.max_attempts < 1:`；`Breakpoint 1 at …` 移到 `:77` 前置说明（净行数 0） |
| 8 | p17:77「约 6.7 ms」伪精确 | 低 | **已修** | `page-17.md:77` → 「约 6 ms、本机实测 5.8–6.3 ms」（取自 R2 报告 6 次调用实测） |
| 9 | 四类表两套名称 | 低 | **已修** | 统一为「无需校正 / 触发并成功 / 触发失败 / 传输失败」：`page-17.md:59` 表头保持，`:57` 分母写「触发校正次数 = 触发并成功 + 触发失败」，`:92` 对账改同一套口径（不再用「校正机会/校正成功/校正失败」） |
| 10 | 附录 Studio 卡缺目录；Zed 卡样例指教师夹具 | 低 | **已修** | `gui-debugging.md:69` Studio 一条命令改为 `(cd manual/review/langgraph-studio && langgraph dev --port 2024)`；`:80` Zed 卡注明样例 `program` 是教师夹具 `manual/shots/pdb_step_demo.py`，换项目换成自己的入口脚本/测试 |
| 11 | ACCEPTANCE:44 / :122 与 p17 新命令不同步 | 低 | **已修** | `ACCEPTANCE.md:44`：p17 基线的 probe 移到「拆一刀另有」；`:122` L3 失败查找补 `review/replay-page-17-v2.md`（p17 最新；v1 已过时） |
| 12 | 报告其它低优先项 | — | **已处理** | 8 类必查清单中「端口与 `.env`」：`page-17.md:52` 第 6 步补「改过 `.env` 的 `FRONTEND_HOST_PORT` / `BACKEND_HOST_PORT` 就用你的端口」；其余项见下「残留偏差」 |

**额外一致性（报告未单列、跨页同口径）**：`appendix/llm-endpoint.md` §1 / §7 的「真模型成功态**不可复现**」→「**不能稳定复现**」（与 p17/ACCEPTANCE 统一；原句已有「本机这一次…不代表每次」解释，语义不变）。

## 二、前后摘录（关键四处）

1. p17:50（pdb 命令说明）——改前只有「看完 `q`（`-s` 不能省…）」；改后补：
   `**q 会让 pytest 记一条 1 failed, 13 deselected … BdbQuit，那是 pdb 中途退出的预期记录，不是你把测试弄坏**；看完用 c 跑完这条，或 q 后重跑整条 pytest 即回 14 passed。`
2. p17:7（这一页构建什么）——改前「v2 **已复现**纠正成功态…不能保证每次复现」；改后「v2 **单次复现过**纠正成功态（证据 `v2-natural-correct-success.sse`…），但触发取决于模型是否生成可重试错误，**不能稳定复现、不能当判据**」。
3. ACCEPTANCE:112——改前「**真 LLM 成功态不可复现**」；改后「**真 LLM 成功态不能稳定复现、不能当判据**：p17 页首与对账写明——v2 单次复现过（证据…），但触发取决于模型、不能保证每次复现；成功率只能写多次采样（trials>=3）+ 成功率 + 失败分类，不许写已修复」。
4. 附录 scalene——改前「`scalene view --html` 生成单文件 HTML，双击也能看」；改后「2.x（实测 2.4.0）`scalene view --standalone` 生成自包含单文件 `scalene-profile.html`（约 1.66 MB）；`--html` 只生成引用 jquery/bootstrap/prism 等外部资源的 HTML，那些资源不写出来，双击白页，别用；1.x（实测 1.5.51）旧写法 `scalene --html --outfile …`」。

## 三、验证记录（全部只读 / 离线，未起栈、未提交）

- 行数：`wc -l manual/page-17.md` → **134**（改前 134，未增）；六段结构不变（末段「拆一刀（L3 级考核）」）。
- `python3 manual/shots/audit_book.py` → `页面：24/24 通过；README 坏链：0`。
- `make audit` → `AUDIT PASS：4/4 全绿（结构 / 空白 / uv.lock / 敏感串）`。
- p17 离线判据重跑：pytest `14 passed in 0.13s`；`failures --check` → `S6 PASS`；`probe_correction.py | tail -1` → `{"total": 20, "mismatch": 0}`。
- `bash -n`：改到的 5 个 md 的全部 bash 块通过（page-17 8 块、ACCEPTANCE 2 块、page-00 4 块、gui-debugging 0 块、llm-endpoint 4 块），失败 0。
- 命令只读核对：
  - scalene 2.4.0（临时 venv）：`scalene view --help` 确认 `--standalone`（implies `--html`）；实测 `--html` 产出 39,205 B，引用 `jquery-3.6.0.slim.min.js` / `bootstrap.bundle.min.js` / `prism.css` / `scalene-gui-bundle.js` 且不写出；`--standalone` 产出 **1,677,256 B（≈1.66 MB）** 自包含单文件。
  - scalene 1.5.51（临时 venv）：`scalene --html --outfile /tmp/s.html tiny.py` 产出 1,602,906 B 单文件。
  - pipx 1.18.19：`pipx install --help` 为 `package_spec [package_spec ...]`，多包安装成立；`uv tool install pipx` 实测装成、`pipx --version` 可查，随后卸载复原；`uv tool install viztracer` 实测装成（viztracer 1.1.1）、随后卸载复原。
  - pdb（真实 pytest）：断点回显 `Breakpoint 1 at …/correct.py:183`；断点处输出两行 `> …(183)propose_correction()` / `-> if policy.max_attempts < 1:`；`p policy.max_attempts`→1、`p error.retryable`→True、`p attempts`→`*** NameError`；`q`→`1 failed, 13 deselected` + `BdbQuit`；改敲 `c` 跑完→`1 passed, 13 deselected`。
- 敏感串：`make audit` 第 4 项通过（manual/ 无用户名 / 家目录）；新增文字统一用 `…` 省略路径。
- 未提交：本报告与上述改动均留在工作区，`git status` 无新增意外文件（`atlas/`、`gui-walkthrough.md`、`replay-page-17-v2.md` 为前几轮既有）。

## 四、残留偏差 / 明确不改

1. **page-17 第 6 步未重跑**（需要整栈 + 成熟版）；按本轮约束只做离线判据与只读核对，四类表的线上采样留待 R4/R5 验收。
2. **四类归并的边角**：`eval/live_probe.py` 实际还有一个 `validate_fail_no_correction` 分支（validate 红但校正没跑，如不可重试码），页面四列表未单列；本轮按任务指定的四个名称统一，未加第五列（受页宽/行数预算与指令约束）。成功率分母已明确为「触发并成功 + 触发失败」，与探针 `correction_success_rate` 分母一致。
3. **`review/replay-page-17-v2.md` 保持原样**（历史报告，不改证据/行号）；`review/README.md` 索引行仍描述 R2 结果，未代 R4 更新。
4. **`make doctor` 未加 pipx 检查**：`Makefile`/`scripts` 属实现/配置，本轮约束只改文档/页面，故改为在 page-00 明说 pipx 可选、并给 uv/临时 venv 替代。
5. 报告第 12 条的其余清单项（如「重录假绿」）不适用本页，无改动；`llm-endpoint.md` 两处措辞属额外一致性修正，已在上文注明。
