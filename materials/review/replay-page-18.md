# 第 18 页独立重放报告（学生视角 · 守只读账号）

**一句话结论**：核心判据全部可复现——`source` 静默、`--provision-ro-account` 开出恰好 SELECT、`--verify-ro-account` 回 PASS（写操作 `1142`）；`GRANT ALL ON dw.*` 后门禁红且 3 项问题与页面逐字一致；`scripts/lab diff` 仍报“工作区与快照完全一致”（`reset` 也救不了），REVOKE / provision 两条还原都回 PASS；整段连续执行 pwd 不变、无 127。问题集中在**前置依赖没写全**和**拆一刀新开终端的误导性报错**，页面本身可重放。

## 环节表

| 环节 | 页面命令 | 预期 | 实测 | 判定 |
|---|---|---|---|---|
| 拍快照 :19 | `scripts/lab save p18-before` | `已保存快照 …` | “169 个文件”，rc=0 | ✅ |
| source :25 | `source scripts/export-docker-env.sh` | 一个字都不打印 | 无输出、rc=0；`REBUILD_MYSQL_ROOT_PASSWORD`/`REBUILD_DW_RO_PASSWORD` 已导出、端口 3310 | ✅ |
| 开通 :31 | `(cd backend && .venv/bin/python -m app.scripts.security --provision-ro-account)` | 4 条“已执行”+ 就绪行 | 逐字一致（`IDENTIFIED BY '***'`） | ✅ |
| 判据 :37 | `… --verify-ro-account` | PASS + 1142 + 双 `GRANT GRANT` 前缀 | 逐字一致（IP 实测 `172.23.0.1`，页面已注明因机器而异） | ✅ |
| 可选 :43 | `make stage5-live` | 节选 + 末行 `S5 LIVE PASS` | 全部出现，末行一致；实测 1s（页面称约 2 秒） | ✅ |
| 拆一刀 :86 | `docker compose exec -T mysql mysql -uroot -p"$REBUILD_MYSQL_ROOT_PASSWORD" -e "GRANT ALL ON dw.* …"` | 仅客户端 warning、rc=0 | 一致 | ✅ |
| 门禁红 :87 | `… --verify-ro-account` | 退出 1 + `FAIL: 3 项问题` + 3 条原文 | 逐字一致（真终端顺序同页面） | ✅ |
| lab diff :103 | `scripts/lab diff p18-before` | “工作区与快照完全一致” | “工作区与快照完全一致，什么都不用恢复。” | ✅ |
| lab reset :103 | `scripts/lab reset p18-before --yes`（页面称救不了） | 不恢复文件、门禁仍红 | “…不需要恢复”，verify 仍 `FAIL` | ✅ 结论成立 |
| REVOKE 还原 :103 | 正文内联的 REVOKE+GRANT SELECT | 回 PASS | rc=0，verify PASS；PASS 状态下可重复执行 | ✅ |
| 重建还原 :106-107 | provision + verify | 末行回 PASS | 一致 | ✅ |
| 对账数字 :76 | `SELECT COUNT(*)` / UPDATE·DROP·跨库 | 115 / 全部 1142 | 115；UPDATE、DROP、`mysql.user` 均 `ERROR 1142` | ✅ |
| 测试条数 :77 | `backend/tests/security/test_account.py` | 10 条 | `10 passed` | ✅ |
| 整段连续 :3 | 同一 shell 顺序跑 :19→:107 | pwd 不变、无 127 | START/FINAL 均 `/tmp/replay-p18b`；11 条命令仅 2 处预期 rc=1（红判据、同名快照），末尾仍 PASS | ✅ |
| 同名快照 :16 | 再跑 `lab save p18-before` | 被拒 | “同名快照 … 不能覆盖”，提示换名 | ✅ |

## 问题清单（6 条）

| page-18.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| :3 | 前置只说“整座城在跑、`.env` 已由 `make docker-env` 生成” | 【歧义/最易卡】:31/:37/:106/:107 用 `backend/.venv/bin/python`，:43 用宿主 `uv run`，前置没写这两样是第 0 页 `make install` 的产物；实测把 `backend/.venv` 移走后立即 `bash: .venv/bin/python: No such file or directory`（退出 127） | 前置补一句“`backend/.venv`（及宿主 `uv`）已由第 0 页 `make install` 建好；缺了就 `cd backend && uv sync --frozen`” |
| :3 | “第 13 页起的整座城在跑” | 【跨页】实测只起 mysql 单服务即可跑通本页全部判据，ES/Qdrant/backend/frontend 都没起；前置比实际硬，ES 起不来的学生会误以为本页不能做 | 前置改为“至少 `mysql` healthy；整栈都在时可顺带做第 13 页 `docker-smoke` 第 7 步” |
| :86 | `docker compose exec -T mysql mysql -uroot -p"$REBUILD_MYSQL_ROOT_PASSWORD" …` | 【易卡】密码变量只在 :25 source；拆一刀新开终端时实测变成 `Enter password:` + `ERROR 1045 (28000): Access denied … (using password: NO)`，像库/密码坏了，实际只是忘了 `source`（:22 只预告了 python 侧报错） | 拆一刀开头显式写“沿用 :25 的终端；新终端先重新 `source`”，或在命令前加 `: "${REBUILD_MYSQL_ROOT_PASSWORD:?先 source scripts/export-docker-env.sh}"` 守卫 |
| :103 | “也可以显式撤销：`docker compose … -e "REVOKE ALL PRIVILEGES, GRANT OPTION FROM …; GRANT SELECT …"`（二选一）” | 【歧义】两条还原命令一条在代码块、一条塞正文；REVOKE 长命令双/单引号套分号，从正文复制易断；“二选一”没标推荐 | 给它独立代码块，并写明“推荐用 :106 的 provision 一句还原；REVOKE 版只用于理解权限差” |
| :16、:19、:103 | “同名快照会被拒，重做本页就换个名字” + 固定的 `p18-before` | 【歧义】换名后 :103 的 `lab diff p18-before` 仍指旧快照（文件没变所以结果仍“一致”，但语义错位）；`scripts/lab help` 只有 save/diff/reset/list，没有删快照命令，旧名永久占位 | 写“若换了快照名，把下文 `p18-before` 一并替换”，或说明旧快照留在 `.lab/snapshots/` 不影响本页结论 |
| :92-:101 | 拆一刀期望输出：明细在前、`FAIL: 3 项问题` 在后 | 【期望输出】真终端（pty）逐字一致；但学生用 `tee` 或 IDE 捕获日志时（stdout 缓冲、FAIL 走 stderr）顺序变成 FAIL 摘要在前，容易怀疑“输出不对” | 期望输出块加一句“重定向/保存日志时摘要在前，是缓冲顺序，不算错” |

四类覆盖：指令不可执行/歧义 = 1、4、5；期望输出不符 = 6（其余 4 段期望输出逐字核对一致，仅 IP 按页面说明变化）；跨页衔接 = 2；最易卡 = 1、3。
跨页未复核项：:77 说第 13 页 `docker-smoke` 第 7 步跑同一条 `--verify-ro-account`，静态核对属实（`scripts/docker-smoke.sh:186-188`），:28 的“第 13 页 init 已开通”也见 `docker_init.py:123`，但本次只起 mysql、未起整栈，未动态复核。

## 真输出摘录

```text
# :37 正常态（PASS，exit 0）
写操作尝试：写操作被拒绝：(1142, "UPDATE command denied to user 'dw_reader'@'172.23.0.1' for table 'fact_order'")
PASS: 该账号在 dw 上只有 SELECT
# :87 GRANT ALL 之后（FAIL，exit 1）
  GRANT GRANT ALL PRIVILEGES ON `dw`.* TO `dw_reader`@`%`
写操作尝试：写操作被放行（权限配置有误）
FAIL: 3 项问题
  - 账号持有不该有的权限：GRANT ALL PRIVILEGES ON `dw`.* TO `dw_reader`@`%`
  - 账号没有 SELECT 权限：['GRANT USAGE ON *.* TO `dw_reader`@`%`', 'GRANT ALL PRIVILEGES ON `dw`.* TO `dw_reader`@`%`']
  - 写操作被放行（权限配置有误）
# :103 lab diff / lab reset 都看不到数据库
  工作区与快照完全一致，什么都不用恢复。          ← diff
  工作区已经和快照完全一致，不需要恢复。          ← reset --yes
# :43 末行；:3 连续执行
S5 LIVE PASS
START_PWD=/tmp/replay-p18b  FINAL_PWD=/tmp/replay-p18b  （全文无 exit 127）
# 缺 .venv / 忘 source 的实测报错
bash: .venv/bin/python: No such file or directory      （RC=127）
Enter password: ERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: NO)
```

## 临时环境声明

- 仓库副本 `/tmp/replay-p18b`（不含 `.git`）；compose project `rp18b`（`COMPOSE_PROJECT_NAME` 写进临时 `.env`，页面里的 `docker compose` 原样可跑），只起 mysql 单服务，容器 `rp18b-mysql`（`compose.override.yaml` 仅改容器名便于清理）。
- 页面默认端口按临时环境替换：MySQL `3306`→`3310`（`MYSQL_HOST_PORT`）；页面命令零改动，端口差异只来自 `.env`。临时 `.env` 三把密码均为临时值（不落报告）；ES/Qdrant/backend/frontend 未起。
- 未改 `manual/page-18.md`，未碰用户栈/容器；重放后已 `docker rm -f rp18b-mysql` 并删除临时副本（含临时 `.env`、`.lab`；副本无 `uv.lock` 改动）。
