# 分支与发布拓扑（2026-11-25 清理后）

## 目标

双线制：**发布锚点**与**集成线**分离，tag 不可变，临时分支用完即删。

| 角色 | 分支 | 规则 |
|---|---|---|
| 发布锚点 | `main` | 指向最新已发布 tag（当前 `v1.1.0` = `5305072`）；每次发版 fast-forward 到新 tag，不直接在 main 上开发 |
| 集成线 | `continue-iterate` | 日常开发与合并都在这里；发版时 fast-forward 到 `main` 并打 tag |
| 一次性分支 | `task/*`、`orca/*`、`materials/design/*`、`reorg/*` | 从集成线切出，合并/放弃后立即删除；不再保留旧 worktree |
| 本地备份线 | `backup/*` | 只存在本地，不推送；确认 WIP 处理完后删除 |

## 历史规则

- **已发布 tag（s0–s3、v1.0.0、v1.1.0）不重写、不移动**。
- 已推送的提交默认不重写；只允许整理**未推送**的本地提交（需要时再单独确认）。
- 合并优先 fast-forward；确需保留分支语境时才用 `--no-ff`。
- 删除分支前先确认其提交已被集成线包含（或已归档 bundle）。

## 本次清理记录（2026-11-25）

- 删除本地 29 个已合并/已归档分支；worktree 从 24 个降到 2 个（`DSWS-design` = main，`DSWS-design-lab` = continue-iterate）。
- 远端删除 4 个陈旧分支：`In-C`、`materials/design/atlas`、`backup/main-before-cleanup-20261106`、`orca/fix-correct-sql-cb`。
- 推送：`continue-iterate` `5305072..cabc02b`，`main` `4711132..5305072`（均 fast-forward，无 force）。
- 全部分支/提交已备份到仓库外：`../DSWS-archive/2026-11-25/git-topology/dsws-all-refs-*.bundle`。
- 未提交 WIP 保留在两个本地 backup 分支 + 归档目录，待用户 review 后再决定提交/删除。

## 发版流程（下次 v1.2）

```bash
cd /home/zhensirong/VM-Share/DSWS-design-lab
make audit && make verify
git push origin continue-iterate
# 在 main worktree：
git -C /home/zhensirong/VM-Share/DSWS-design merge --ff-only v1.2.0
git tag -a v1.2.0 -m "v1.2.0 · ..."
git push origin continue-iterate main v1.2.0
```
