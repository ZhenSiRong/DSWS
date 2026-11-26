# 说明书护栏：`make audit`、`make verify` 与 pre-commit

> 对应 retro 决议：uv 锁文件被改写、用户名/家目录泄露、页面结构回归，各配一道自动化门。
> 只读、离线、不改任何页面；实现见 `Makefile`（`audit` / `verify` / `install-hooks`）与 `.githooks/pre-commit`。
> 页面契约（防「跟做断层」）的设计与用法见 [`verify-line.md`](verify-line.md) 与 [ADR 0002](adr/0002-followability-line.md)。

## 一条命令：`make audit`

五项聚合并输出中文结论；任一项失败即中断（`audit_book.py` 等子命令退出码 1，
GNU make 对 recipe 失败统一返回 2：非 0 即红）。

| # | 检查 | 失败时怎么修 |
|---|---|---|
| 1 | `python3 tutorial/shots/audit_book.py`：24 页 H1/六段/围栏/图引用/README 坏链 | 按 FAIL 页号与明细改页面 |
| 2 | `git diff --check`：空白错误（行尾空格、冲突标记） | 删掉行尾空白 |
| 3 | `system/backend/uv.lock` 与仓库一致 | `git checkout -- system/backend/uv.lock` |
| 4 | `tutorial/` 不得出现 `zhensirong` 或 `/home/` | 换相对路径 / `<家目录>` 占位符 |
| 5 | `python3 toolbox/scripts/task.py check --quick`：任务台账 done 证据/依赖/甘特对账 | 按提示改台账，或 `task.py render` 重渲 |

## 页面契约跟随性：`make verify`（ADR 0002）

`make audit` 管「格式」，`make verify` 管「照页面做能不能跑通」——页面里的命令、路径、符号、关键输出与仓库实现是否一致。契约在 `tutorial/verify/contracts/page-XX.yaml`，页面里用 `<!-- verify: <marker> -->` 标可验块。

| 层 | 命令 | 预算 | 做什么 |
|---|---|---|---|
| T0 | `make verify-fast`（pre-commit 自动跑） | <2s | 契约解析、页面↔契约双向同步、静态路径/符号、证据存在；不执行页面命令 |
| T1 | `make verify`（CI 也跑） | <2min | T0 + 执行 `kind: offline` 命令，断言退出码/关键行；证据过期 warn，`--strict` 升 fail |
| T2 | `make accept-l1` … `make accept-l5` | 按级 | 复用 `ACCEPTANCE.md` 级考核；安全步骤自动、破坏性步骤标 `MANUAL`；栈未起 SKIP（退出码 2） |

第 4 项排除两类正当引用：`tutorial/review/`（重放报告按设计记录真实路径作证据）和
`tutorial/*.py`（校验/生成脚本自身以 `FORBIDDEN` 词表包含这些串）。`audit_book.py` 对
24 页与 README 另有同规则的逐页检查，不受上述排除影响。

## 为什么锁文件单独查

本机 `uv` 配了镜像源时，`make stage*` 里的 `uv run` 会按当前 index 静默重写
`system/backend/uv.lock`（实测 2,812 行 diff）。Makefile 已统一改成 `uv run --frozen` 阻止改写；
万一仍被改（手动 `uv run`、旧脚本），`toolbox/scripts/lab` 的快照白名单不含 `uv.lock`、`reset`
救不回——所以由 git 兜底。

## 启用提交前护栏（每人一次，仅本仓库）

```bash
make install-hooks    # git config core.hooksPath .githooks
```

- 不做：不改全局 git 配置；除了这个 make 目标，不替用户改配置。
- 绕过：`git commit --no-verify`（只在确认误报时用）。
- 停用：`git config --unset core.hooksPath`。
- `audit_book.py` 不存在时 pre-commit 自动跳过该项（防误伤历史 checkout）。
- pre-commit 现在检查五件事：结构审计 / uv.lock / 敏感串 / 任务台账 / 页面契约 T0（`toolbox/scripts/verify.py --fast`，<2s）；`toolbox/scripts/verify.py` 或 `tutorial/verify/contracts/` 不存在时自动跳过契约项（防误伤历史 checkout）。

## 提交前 vs CI vs 夜间

| 时机 | 跑什么 | 说明 |
|---|---|---|
| `git commit` | pre-commit：结构审计 + uv.lock + 敏感串 + 台账 + 契约 T0 | 秒级；绕过 `--no-verify` 留痕 |
| push / PR | GitHub Actions：结构审计 + 契约 T0 + T1 + verify 单测（`.github/workflows/verify.yml`） | 干净 checkout、离线、无 secrets |
| 本机/夜间 | `make accept-l1` … `accept-l5`（T2） | 需整栈已起；破坏性步骤只打印 `MANUAL`，不自动执行 |
