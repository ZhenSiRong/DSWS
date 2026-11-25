# 教材可跟随性验收线

> 解决「教材修订后跟做断层」：页面里的命令/路径/输出与仓库实现或环境脱节，学生照做失败。
> 术语口径见 `GLOSSARY.md`「验收线术语」；决策与被否选项见 `docs/adr/0002-followability-line.md`。
> 实现位置：`scripts/verify.py`（T0/T1）、`manual/verify/contracts/`（页面契约）、`scripts/acceptance/`（T2）。
> 页面契约的 schema 以 `manual/verify/README.md` 为准；本文是设计/使用说明，不复制全文。

## 1. 拦什么：五类断层

| 类 | 现象 | 先在哪层暴露 |
|---|---|---|
| ① 命令/路径失效 | 页面里的文件、命令、参数已改名或删除 | T0 静态路径/符号；T1 执行 |
| ② 预期输出对不上 | 页面写 `18 passed`，实跑变成 `21 passed` | T1 退出码/关键行断言 |
| ③ 代码改页面没改 | 行为变了，页面仍写旧输出 | T1（同 ②，根因在代码） |
| ④ 证据/截图过期假绿 | 截图还是旧界面/旧输出 | T0 证据缺失、T1 证据过期（默认 warn；`--strict` 升 fail） |
| ⑤ 跨页前置断裂 | 上一页产物/状态没恢复，本页照做失败（如 p17 依赖 p16 拆一刀已 reset） | 目前靠 T2/人工（v1 无自动前置检查）；T2 栈未起 SKIP |

## 2. 三层验收线

| 层 | 命令 | 预算 | 查什么 | 触发 |
|---|---|---|---|---|
| **T0** | `python3 scripts/verify.py --fast` | <2s | 契约解析；页面注解 ↔ 契约双向同步；静态路径/符号；证据存在 | pre-commit |
| **T1** | `python3 scripts/verify.py` / `make verify` | 典型 <1min（p17 实测 ~10s；单块超时上限 60s） | T0 + 执行 `kind: offline` 命令（退出码 + 关键行 + `page_contains`）；证据过期 warn | `make verify` / GitHub Actions / 手动 |
| **T2** | `make accept-l1` … `make accept-l5` | 视级考核 | 复用 `manual/ACCEPTANCE.md` 级考核：安全步骤自动、破坏性步骤 `MANUAL` | 本机 / 夜间 |

- T0/T1 **fail-closed**：非 0 即红，不放行，且不自动改任务台账。
- T2 需整栈已起；未起一律 **SKIP（退出码 2）**，SKIP 不是通过。
- `--strict`：证据文件缺失（T0/T1 扫描）与过期（T1）都升为失败；默认只 warn。
- T2 夜间失败按流程经 `scripts/task.py` 记台账；verify 自身不写台账。

## 3. 页面契约（摘要）

每页一个 `manual/verify/contracts/page-XX.yaml`（如 `page-17.yaml`）；页面内用 HTML 注释 `<!-- verify: <marker> -->` 标出可验块，渲染不可见。

契约只存「关键行/数字」，不存全量 stdout；至少要能对上：块标记与页内命令（两处必须一致）、`kind`、期望退出码与关键行、静态路径/符号、证据；可选 `page_contains` 把页面可见关键输出锚定到页面的 ` <!-- verify-out: <marker> --> ` text 围栏（只在别处出现不算）。

- **`kind: offline`**：T1 真跑。
- **`kind: manual`**：GUI 点选、交互、真模型块，留给 T2 人工判据。
- **`coverage: static`**：整栈页（全要 docker / 端口 / 真模型）用；契约只挂 `static.paths` / `static.symbols`，页面不写块注解，T0 只证明「页面引用的文件与符号还在」，T1 不执行——是诚实降级，不是执行通过。

字段名与校验规则以 `manual/verify/README.md` 为准。反假绿的硬规矩：页面块里的命令必须与契约命令一致；故意改基线时，页面、契约、证据放同一个 commit，并在提交说明里写清原因。

## 4. 给新页加契约（步骤）

1. 选块：只选「离线可跑、输出能用关键行断言」的块；GUI/交互/真模型先标 `manual`，留给 T2。
2. 页内标块：在块旁加 `<!-- verify: <marker> -->`（HTML 注释，渲染不可见）。
3. 建契约：`manual/verify/contracts/page-XX.yaml`，写命令、`kind`、期望退出码与关键行、静态路径/符号、证据；页面可见的关键输出写进 `page_contains`（schema 见 `manual/verify/README.md`）。
4. 自检：`python3 scripts/verify.py --fast` 过静态；再 `python3 scripts/verify.py` 真跑离线块。
5. 基线变更：改页面命令/输出时，同 commit 改契约与证据并说明原因。
6. 接 T2：需要整栈上验的 `manual` 块，落到对应级 `scripts/acceptance/level-l*.sh`（破坏性步骤标 `MANUAL`，人照 `manual/ACCEPTANCE.md` 做）。

## 5. 失败怎么排查

- **T0「页面块 ↔ 契约不同步」**：页内 marker 漏/多，或页面命令与契约命令不一致 → 两边改成同一句。
- **T0「静态路径/符号不存在」**：路径改名或删除 → 页面与契约同步更新；若是代码回归，修代码（断层 ①）。
- **T1「退出码/关键行不符」**：先看实际输出；有意行为变更按第 4 节第 5 步同 commit 改基线，否则是代码回归（断层 ②③）。
- **T0「证据不存在」/ T1「证据过期」warn**：重录证据，与页面/契约同 commit（断层 ④）。
- **T1「页面可见关键输出与真实输出不一致」**：页面写的数字/行与真实输出不同（断层 ②）→ 同 commit 改页面/契约并重跑。
- **跨页前置（断层 ⑤）**：v1 不自动检查，靠 T2 的栈预检、`MANUAL` 步骤与人工判据；上一页状态没恢复时先照该页收尾步骤还原。
- **T2 报 SKIP(2)**：栈未起，先按 `manual/ACCEPTANCE.md` 起栈；SKIP 不是通过。
- **T2 某级考核红**：安全步骤看脚本输出；`MANUAL` 步骤照 `manual/ACCEPTANCE.md` 的人工判据逐条核。

## 6. 与其他门禁的关系

- **`make audit`**：查页面结构/格式/敏感串/锁文件/台账，**不执行页面命令**；验收线补的是「命令能不能跑、输出对不对」这一层。
- **`pre-commit`**（`.githooks/pre-commit`）：保留 audit 等原有检查，并调用 T0（<2s）；T1 不进 pre-commit，交给 `make verify` / CI。
- **`manual/ACCEPTANCE.md`**：各级判据与级考核的唯一人工口径；T2 脚本复用其步骤，不另写判据。
- **`scripts/task.py` / `workflows/ledger.yaml`**：任务台账；T0/T1 不自动改，T2 夜间失败按流程记。
- **GitHub Actions**：只跑 T0/T1（离线、无 secrets）；T2 在本机/夜间跑。

## 7. 已知限制

- T1 只覆盖 `kind: offline` 块；GUI、交互、真模型输出不自动断言，靠 T2 人工判据兜底。
- T2 依赖整栈；未起栈一律 SKIP（退出码 2），不能当绿读。
- 证据缺失/过期（T0/T1）目前先 warn，基线稳定后才升 fail；需要更严可先用 `--strict`。
- 契约只存关键行/数字、不存全量输出，故断言不到细节输出；要更强保证得加契约或转 T2。
- T0 是静态检查，证明不了运行时行为；「页面命令与契约一致」只说明两处没分叉。
- 覆盖现状（2026-11-24）：24 页全部接入。8 页 `coverage: blocks`（14 个 offline 块由 T1 真跑，35 个块 manual 只同步），16 页整栈/GUI 页 `coverage: static`（只查路径与符号）。`python3 scripts/verify.py` 实测 24/24 通过、14/14 offline 块通过、约 30s。
- static 页只挡断层①（文件/符号被改名删除），挡不住②③（输出对不上、代码改了页面没改）；要升级得等这些页出现可离线执行的块，或靠 T2 级考核。
