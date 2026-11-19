# 说明书护栏：`make audit` 与 pre-commit

> 对应 retro 决议：uv 锁文件被改写、用户名/家目录泄露、页面结构回归，各配一道自动化门。
> 只读、离线、不改任何页面；实现见 `Makefile`（`audit` / `install-hooks`）与 `.githooks/pre-commit`。

## 一条命令：`make audit`

四项聚合并输出中文结论；任一项失败即中断（`audit_book.py` 等子命令退出码 1，
GNU make 对 recipe 失败统一返回 2：非 0 即红）。

| # | 检查 | 失败时怎么修 |
|---|---|---|
| 1 | `python3 manual/shots/audit_book.py`：23 页 H1/六段/围栏/图引用/README 坏链 | 按 FAIL 页号与明细改页面 |
| 2 | `git diff --check`：空白错误（行尾空格、冲突标记） | 删掉行尾空白 |
| 3 | `backend/uv.lock` 与仓库一致 | `git checkout -- backend/uv.lock` |
| 4 | `manual/` 不得出现 `zhensirong` 或 `/home/` | 换相对路径 / `<家目录>` 占位符 |

第 4 项排除两类正当引用：`manual/review/`（重放报告按设计记录真实路径作证据）和
`manual/*.py`（校验/生成脚本自身以 `FORBIDDEN` 词表包含这些串）。`audit_book.py` 对
23 页与 README 另有同规则的逐页检查，不受上述排除影响。

## 为什么锁文件单独查

本机 `uv` 配了镜像源时，`make stage*` 里的 `uv run` 会按当前 index 静默重写
`backend/uv.lock`（实测 2,812 行 diff）。Makefile 已统一改成 `uv run --frozen` 阻止改写；
万一仍被改（手动 `uv run`、旧脚本），`scripts/lab` 的快照白名单不含 `uv.lock`、`reset`
救不回——所以由 git 兜底。

## 启用提交前护栏（每人一次，仅本仓库）

```bash
make install-hooks    # git config core.hooksPath .githooks
```

- 不做：不改全局 git 配置；除了这个 make 目标，不替用户改配置。
- 绕过：`git commit --no-verify`（只在确认误报时用）。
- 停用：`git config --unset core.hooksPath`。
- `audit_book.py` 不存在时 pre-commit 自动跳过该项（防误伤历史 checkout）。
