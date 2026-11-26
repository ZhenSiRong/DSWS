# `lab`：教学用快照与回滚（v1）

> 对应 D33（对学生隐藏 VCS 的版本快照）与 D46 第 6 条（工程债里 `lab` CLI 最先做）。
> 实现：`toolbox/scripts/lab`；测试：`toolbox/scripts/tests/test_lab.sh`。

## 为什么需要

L2–L4 每页都有一个「拆一刀」：改一行契约、删一个校验、换一套夹具，看系统怎么坏。
学生改坏了要能一句话回到"拆之前"，但不该先在课上踩 git 的 detached HEAD / stash / 冲突。
`lab` 只做这一件事：**给白名单文件拍快照、比对、回滚**，不碰版本控制。

## 三条主命令

```bash
./scripts/lab save before-schema          # 拍快照：白名单文件 + manifest.json
./scripts/lab diff before-schema          # 新增/修改/删除清单 + 统一 diff
./scripts/lab reset before-schema --yes   # 恢复；不加 --yes 只打印计划、不动文件
./scripts/lab list                        # 辅助：快照名字/时间/文件数/git HEAD
./scripts/lab help                        # 一屏帮助
```

`reset` 不带 `--yes` 时只打印计划（一个文件都没动）：

```
如果现在恢复（--yes），会：
  删除（快照里没有、工作区多出来的文件）：1 个
    - system/contracts/new.contract.yaml
  …（写回、覆盖同理，各带文件清单）
没有 --yes，一个文件都没动。
```

## 安全规则

1. **reset 必须显式 `--yes`**：不加只打印"会删除/写回/覆盖什么"，退出码非 0。
2. **自动安全快照**：加了 `--yes` 也会先拍 `pre-reset-<时间>`；恢复错了就
   `./scripts/lab reset pre-reset-... --yes --no-safety` 回到恢复前。
3. **快照只读**：同名 `save` 直接拒绝、不覆盖（D33 第 5 条）。覆盖会悄悄销毁
   "学生以为还在"的存档点，而拒绝的代价只是换个名字；自动安全快照用秒级时间戳，
   重名再加 `-2`，不会撞名。确实要重拍就先 `rm -rf .lab/snapshots/<名字>`。

## 白名单与排除

只跟踪：`system/contracts/`、`compose.yaml`、`lab/`、`system/backend/app/`、`system/backend/tests/`、`system/fixtures/`、`system/frontend/src/`。
目录不存在就跳过，manifest 里记 `present: false`；`manifest.json` 还记录时间、git HEAD、
每个文件的 sha256 与文件数，方便老师对账。
学生自己的代码（`lab/app.py`、`lab/db.py` 等）也在保护范围内：拆坏执行器/应用后一样能 `reset` 回来（`reset` 会删掉 `lab/` 里快照之外的新文件，这是整目录恢复语义）。

永不入快照、也永不被 `reset` 删除：`.env`、`.env.*`、`.venv`、`node_modules`、
`__pycache__`、`.git`（另含 `*.pyc`、`.DS_Store`）。密钥不会进 `.lab/`。

## 限制：v1 不覆盖 DB / 容器

`lab` 只管文件。**数据库内容、容器状态、Docker 卷不在快照里**，`reset` 也不会重启或灌库。
拆一刀动了数据/容器后要回到干净环境，手动重建：

```bash
make docker-down && make docker-up   # 重建容器；卷内容保留
make docker-reset                    # 连卷一起删（破坏性；之后需重新灌 system/fixtures/dw.sql）
```

v1 也不跟踪符号链接、空目录、文件名含换行/制表符的极端文件；没有 `lab start/done`
overlay 跳转（D33 的跳转留到 v2，先用 `save`/`reset` 顶住）。

## 恢复事故处理

- **恢复错了**：用 `reset` 打印的 `pre-reset-...` 快照回退（见安全规则 2）。
- **误删了当前快照**：`.lab/` 在 `.gitignore` 里，本地无备份；只能重跑起点或找老师。
- **快照不完整**（缺 manifest/tree）：`lab` 拒绝使用并提示删掉重拍，不会盲恢复。

## 与 D33 的对应

| D33 要求 | v1 状态 |
|---|---|
| 快照含文件状态；`lab save` | ✅ 本工具 |
| overlay 跳转不切分支 | ⏳ v2（现用 save/reset 平替） |
| 容器/DB 回滚需 `--yes` | ✅ 门槛先用在文件 reset；容器回滚 v2 |
| 快照只读、不可覆盖 | ✅ 同名 save 拒绝 |
| 学生不接触 git | ✅ 三条命令都不出现 git 操作 |

验证：`bash toolbox/scripts/tests/test_lab.sh`（纯 shell）；语法检查 `bash -n toolbox/scripts/lab`（有 shellcheck 时再跑 `shellcheck toolbox/scripts/lab`）。
