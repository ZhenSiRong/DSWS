# 第 19 页重放报告（学生视角 · 独立重放）

> 环境：`/tmp/replay-p19` 全量副本（删 `.git`/`.env`/`.lab`，保留 `backend/.venv`），无 MySQL/栈、无 `.env`；`strace` 实测 `--check` 0 条外部连接、`make stage5` 只有 loopback 测试服务器连接；把第 18 页的 `.env` 与 `source scripts/export-docker-env.sh` 放回来复跑结果不变。只按页面文字操作，未读 writer 报告，未碰用户栈。

**一句话结论**：核心判据与拆一刀全部逐字复现（36/36 + 11/11 + 8/8 + S5 PASS；关掉 `forbid_set_operations` 后 `FAIL: 2 项`、两行原因码退化、11/11 与 8/8 不动、reset 回绿），页面可重放；最大问题是第 4 步 `uv run` 改写 `backend/uv.lock` 而 `lab reset` 救不回（实测 2,812 行 diff），其次是拆一刀"退出码 1"与页面管道命令实际 `$?`=0 的矛盾。共 8 条问题（高 1 / 中 2 / 低 5）。
## 环节表

| # | 环节 | 页面命令/判据 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | 第 1 步快照（L16-20） | `scripts/lab save p19-before` | `已保存快照 "p19-before"：169 个文件。` exit 0 | ✅ 逐字一致 |
| 2 | 第 2 步门禁（L22-26） | `(cd backend && .venv/bin/python -m app.scripts.security --check)` | 36/36、11/11、8/8、`S5 PASS`，exit 0 | ✅ 逐字一致 |
| 3 | 第 3 步判定表（L28-32） | `--corpus ... 2>&1 \| grep -E "..."` | 6 行构造 + `语料：47 条，失败 0 条`，exit 0 | ✅ 逐字一致 |
| 4 | 第 4 步 stage5（L34-38） | `make stage5` | `179 passed, 2 skipped`；`813 passed, 30 skipped`；`S5 PASS`；wall 33.7–39.4s，exit 0 | ⚠️ 结果对，有副作用（问题 1/3/4） |
| 5 | 拆一刀（L79-96） | 改 `forbid_set_operations: false` → `... \| tail -8` | 34/36、11/11、8/8、`FAIL: 2 项` + 两行原因码退化；门禁本体 exit 1 | ⚠️ 输出逐字一致；管道 `$?`=0（问题 2） |
| 6 | 还原回绿（L98-108） | `scripts/lab reset p19-before --yes` + `--check \| tail -1` | 末两行 `完全一致` + `S5 PASS`，exit 0；policy 回 `true` | ⚠️ 白名单内回绿；`uv.lock` 仍脏（问题 1） |
| 7 | D48 连续执行（L3） | 同一 shell 按页顺序连续执行全部命令 | pwd 始终仓库根、无 exit 127 | ✅ D48 满足 |
| 8 | 结论段再拆（L110） | 关 `forbid_executable_comments` 重跑 | `executable_comment_union/drop: 竟然被放行了` 共 2 行，exit 1，再 reset 回绿 | ✅ 逐字一致 |
## 问题清单

| page-19.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| 34,37,98-108 | "前提：本机有 `uv` 且 `backend/.venv` 依赖已装好（没有就跳过…）"；"现在工作区与快照 "p19-before" 完全一致。" | **高**：`make stage5` 的 `uv run` 按本机 uv index 重写 `backend/uv.lock`（pypi.org→清华镜像，1,249 行改动、diff 2,812 行）；`scripts/lab` 白名单不含它，reset 后文件仍脏，输出却说"完全一致" | 页面补"跑完 `make stage5` 用 `git checkout -- backend/uv.lock` 还原"；Makefile 改用 `uv run --frozen`（实测不改锁） |
| 82,96 | "… \| tail -8"；"退出码 1。" | **中**：页面命令的退出码是 `tail` 的 0，学生 `echo $?` 看到 0 与"退出码 1"矛盾（门禁本体确为 1，需 `${PIPESTATUS[0]}`） | 命令后加 `; echo "gate=${PIPESTATUS[0]}"`，或注明"退出码看门禁本体（管道末尾是 tail 的 0）" |
| 34 | "本机有 `uv` 且 `backend/.venv` 依赖已装好（没有就跳过…）" | **中**：两项前提没有可执行的检查命令，"没有"指 uv 还是依赖不清；uv 在而依赖没装时 `uv run` 会联网 sync，与"本页离线/不用服务"冲突 | 给检查命令（如 `cd backend && uv run --offline --frozen python -c "import app"`），写明不满足就跳过第 4 步 |
| 34 | "先跑 179 条安全测试，再跑 813 条全后端、占 40 秒" | **低**：实测 `179 passed, 2 skipped`、`813 passed, 30 skipped`（共收集 843 条）；两处数字都漏了 skipped | 改成 "179 passed(+2 skipped)；全后端 843 条（813 passed / 30 skipped）" |
| 28-32 | "下面的 grep 只留四类构造" | **低**：实际只留 3 类构造（多语句/可执行注释/集合运算）+1 行 stderr 汇总；`--corpus` 全表命令、退出码（拆一刀后为 1）、`PYTHONUNBUFFERED=1` 的作用（保证汇总在表尾，去掉则跑到表头）都没说明 | 改"三类构造"；补"看全 47 行去掉 grep"，并注明 `--corpus` 失败时退出码非 0 |
| 3 | "第 2、3 步的判据只读 `contracts/` 与 `fixtures/`" | **低**：`--check` 还读 `backend/tests/generate/baseline.yaml`（S4 基线）；第 2/3 步依赖 `backend/.venv`，但前置未列 | "只读契约/夹具/基线"；前置补 `.venv` 来源（前几页装好） |
| 16 | "同名快照会被拒，重做本页换个名字" | **低**：下文 reset/检查命令硬编码 `p19-before`（L101-102、L107），换名重做时需同步改，页面未提示 | 在换名提示后加"下面命令里的 p19-before 也一起换" |
| 79 | "找到 `forbid_set_operations: true`，只把这处改成 `false`" | **低**：未给行号/YAML 上下文；实测唯一（L31，`statement:` 段内 2 空格缩进），但 4 行后还有 `forbid_executable_comments: true`，粗心易改错 | 补"L31，`statement:` 下缩进 2 格，只改这个开关" |
## 真输出摘录

第 2 步（逐字）：
```text
== 1/3 注入语料（必须 100% 拒绝） ==
  注入语料：36/36 条按预期拒绝
== 2/3 零误杀语料（必须全部放行） ==
  零误杀语料：11/11 条放行
== 3/3 S4 基线零误杀 ==
  S4 基线：8/8 条 SQL 通过策略
S5 PASS
```
第 3 步（逐字核对 6 行全对，此处摘 2 行 + 汇总）：
```text
| union_exfiltration | SQL_FORBIDDEN_CONSTRUCT | SQL_FORBIDDEN_CONSTRUCT | PASS |
| union_all_exfiltration | SQL_FORBIDDEN_CONSTRUCT | SQL_FORBIDDEN_CONSTRUCT | PASS |
语料：47 条，失败 0 条
```
拆一刀（逐字，`tail -8`）：
```text
  注入语料：34/36 条按预期拒绝
== 2/3 零误杀语料（必须全部放行） ==
  零误杀语料：11/11 条放行
== 3/3 S4 基线零误杀 ==
  S4 基线：8/8 条 SQL 通过策略
FAIL: 2 项不符合预期
  - union_exfiltration: 原因码不符（期望 SQL_FORBIDDEN_CONSTRUCT，实际 SQL_NOT_READ_ONLY）
  - union_all_exfiltration: 原因码不符（期望 SQL_FORBIDDEN_CONSTRUCT，实际 SQL_NOT_READ_ONLY）
```
第 4 步 / reset（节选）：
```text
179 passed, 2 skipped in 1.03s
813 passed, 30 skipped in 32.80s
S5 PASS
现在工作区与快照 "p19-before" 完全一致。
```
## 清理确认

- `rm -rf /tmp/replay-p19`（副本 `.lab` 快照与 `uv.lock` 改动随之删除），`/tmp/p19-*` 临时日志一并删除。
- 源仓库只新增本报告，未改 `manual/page-19.md`，未运行任何栈/数据库命令。
