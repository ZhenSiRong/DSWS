# 第 22 页重放报告（学生视角 · 独立重放）

> 环境：`/tmp/replay-p22` 全量 rsync 副本（删 `.git`/`.env`/`.lab`，保留 `backend/.venv` 与 `frontend/node_modules`），离线、无 MySQL/ES/栈；**未起任何容器、未跑 `make docker-smoke`、未碰用户栈**；只按页面文字操作，未读 writer 报告。**实跑**：第 1–3 步、skip 归因、`make docker-env`+`source`、`make -n`、smoke 检查器离线输入、只读判据离线仿真。**未实跑、静态核对**：smoke 8 步、级考核 GRANT ALL 窗口、终端 B 循环、`S2 VERIFY PASS`、`--provision-ro-account` 实跑（无库）。行号按 117 行版（sha `a8faef53`）。

**一句话结论**：离线部分逐字可复现（`813 passed, 30 skipped`、`Tests 40 passed (40)`、skip 23/5/2、843=813+30），第 1–3 步与 D48 连续执行通过，全栈部分页面文字与 `scripts/docker-smoke.sh`/`page-13` 静态一致；但级考核有两个「静默失败」口子——终端 B 的 init 容器 id 只解析一次且没有「栈停过先起栈」前置，第 5 步还原没写 `source`。共 9 条问题（高 2 / 中 3 / 低 4）。

## 环节表

| # | 环节 | 页面判据 | 实测 / 静态核对 | 判定 |
|---|---|---|---|---|
| 1 | 前置与栈（L3、L31） | 第 21 页全程离线、不碰栈；从第 13 页连续阅读时栈应仍在跑，**不需要**重启（第 14 页只停/起 ES 后还原） | 页面只写「第 13 页的 make docker-up 起过栈」（过去时），没写「若栈已停先起栈」；`make docker-smoke` 第 1 步自 `up` 能自愈，拆一刀不能（问题 1） | ⚠️ 缺兜底 |
| 2 | 第 1 步快照（L16-19） | `已保存快照 "p22-before"：169 个文件。`；同名被拒 | 实跑 169 个文件、exit 0；再存同名 exit 1，与「同名快照会被拒」一致；实际另多「位置/下一步」2 行 | ✅ 数字逐字 |
| 3 | 第 2 步全量 pytest（L21-24） | `813 passed, 30 skipped in 36.28s`，末行无 failed/error | 实跑两次均 `813 passed, 30 skipped`（33.71s / 26.62s，exit 0）；`-rs` 归因 23（REBUILD_INTEGRATION）+ 5（contract_alignment）+ 2（拒答）= 30；843=813+30 | ✅ 计数逐字 |
| 4 | 第 3 步前端（L26-29） | `      Tests  40 passed (40)` | 实跑 `Test Files 2 passed (2)`、`Tests  40 passed (40)`，exit 0 | ✅ 逐字 |
| 5 | 第 4 步 smoke（L31-34） | `.env`/Docker/栈在跑；8 步 + init 幂等 + `DOCKER SMOKE PASS` | **未实跑，静态核对**：脚本 8 个 `== n/8 ==`、第 7 步同一条 `--verify-ro-account`、第 8 步同一条 `build_meta_knowledge --verify`、fail-fast、init 幂等 grep 均对得上；离线喂 `ps` 表得 `services: backend=…, init=exited, …` 与 L48 逐字，`health: {"status":"ok","stage":"S7"}` 与 `main.py` 一致 | ✅ 静态一致 |
| 6 | 级考核时机（L68、L77-79） | init 退出后、第 7 步前注入；「先改权限再整跑」=0 步红 | **未实跑，静态核对**：`compose.yaml` init command=`app.scripts.docker_init`，每次 `up` 重跑 provision→verify→build_meta verify，猜 2 的「init 重置」成立，与 page-18 末句口径一致 | ✅ 一致 |
| 7 | 窗口（L79） | 「窗口实测只有约 3 秒」 | **未实跑**：页面/仓库无 `2.84` 字样（页面与 page-18 都写「约 3 秒」）；按第 2–6 步静态拆解量级 1.5–3s，自洽；但没写「没咬到怎么办」 | ⚠️ 缺兜底（问题 4） |
| 8 | 终端 B 循环（L80-87） | `source`→取 id→等 running→exited→GRANT | **未实跑，静态核对**：语法正确；`id` 只取一次，容器不存在/顺序反了会无限静默等待（问题 1）；缺 source 报错已离线复现（问题 2） | ⚠️ 有坑 |
| 9 | 级考核第 3 步（L89-102） | 1–6 绿、7 红、`FAIL: 3 项问题`、`DOCKER SMOKE FAIL: 只读账号验证未通过`、第 8 步不跑 | **未实跑，静态核对**：假连接仿真 `verify_account` 得恰好 3 problems + `写操作被放行（权限配置有误）`；`fail()` 退出码 1、第 8 步不跑；期望块顺序与真实/自己截图不符（问题 3） | ⚠️ 顺序不符 |
| 10 | 第 4 步单步 S2（L104） | 越权下仍 `S2 VERIFY PASS` | **未实跑，静态核对**：镜像无 ENTRYPOINT，`run … python -m app.build_meta_knowledge --verify` 只覆盖 CMD、不重跑 provision；`--verify` 末行确为 `S2 VERIFY PASS`；`| tail -1` 会盖掉退出码 | ✅ 结论成立 |
| 11 | 第 5 步还原（L106-115） | provision 回 SELECT，再整跑回 PASS | **未实跑**（无库）；缺 source 实测 exit 1 + `缺少环境变量 REBUILD_DW_RO_PASSWORD`；provision 语句=DROP/CREATE/GRANT/FLUSH，输出与 L112 一致 | ⚠️ 缺前置（问题 2） |
| 12 | D48 + 跨页（L3、L117） | 子 shell、同终端；page-18 末句、page-21 的 skip/843 | 实跑：全页 3 处 `cd` 均为 `(cd … && …)`，pwd 恒 `/tmp/replay-p22`、无 127；page-18「单步红/整跑被 init 重置」与 page-22 猜 2、级考核一致；page-21 L48「843 条 = 813 passed + 30 skipped」与 page-22 L11/L65 一致 | ✅ 满足/一致 |

## 问题清单

| page-22.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| 3、31、80-87 | 「第 13 页的 make docker-up 起过栈」／`id="$(docker compose ps -aq init)"` | **高**：终端 B 的 init 容器 id 只解析一次；若栈被 `make docker-down`/机器重启过（容器不存在），`docker inspect ""` 永远不等于 running/exited，B 无限静默等待；A 的 `up` 会新建 init，但 B 仍用空/旧 id，级考核既不红也不报错。页面没写「栈已停先起栈」或「先确认 init 容器在」 | 拆一刀第 2 步加前置：`docker compose ps -a` 必须能看到 init，栈停过先 `docker compose up -d`（不必 `make docker-up` 的 --build）；循环改为每轮重取 id 并加超时/报错 |
| 106-110 | `(cd backend && .venv/bin/python -m app.scripts.security --provision-ro-account)` | **高**：还原命令没写 `source scripts/export-docker-env.sh`，也没说在哪个终端跑；在终端 A/新终端实测 exit 1 `缺少环境变量 REBUILD_DW_RO_PASSWORD`，越权还原不了（page-18 第 2 步有 source，本页未承接） | 第 5 步前补 `source scripts/export-docker-env.sh`，或写明「在终端 B（已 source）里跑」 |
| 89-102 | 期望块：GRANT 行 → 写操作 → `FAIL: 3 项问题` | **中**：真实/自己截图（`page-22-ablation.png`）是 `FAIL: 3 项问题`+明细先出，账号/GRANT/写操作 stdout 随后；页面把顺序写成相反且未标节选、未解释 stdout/stderr 缓冲（page-18 只对 tee/重定向解释过），学生会以为输出不对 | 加一句「FAIL 摘要走 stderr 先到，顺序不固定」或按截图重排；与 page-18 那条互链 |
| 79、89-102 | 「窗口实测只有约 3 秒」 | **中**：只有警告没有兜底——慢机器/慢 `compose exec` 时 GRANT 可能落到第 7 步之后，A 8 步全绿；页面没写「A 仍全绿 = 注入晚了，整次重来」 | 期望块后补：A 仍 PASS 说明 GRANT 落晚/被 init 重置，重跑一次；可先 `docker compose exec -T mysql true` 预热 |
| 3 | 「命令都在仓库根目录、同一个终端里整段连续执行」 | **中/低**：拆一刀要终端 A/B 两个终端，新开终端未必在仓库根；B 的 `source scripts/…` 在别处失败后进入空 id 死循环 | 前置改成「除级考核的终端 B 外同一个终端；终端 B 也先到仓库根」 |
| 7、67 | 「…拼成一张回归网：一条命令替你值班」／stage0–7 分工 | **低**：本页 4 条命令没有任何一条跑 stage0–7，也没有聚合命令（Makefile 无 target）；page-21 的归一化退化（拆 `record_sse._normalize`）在 `tests/` 无引用（静态核对），不会被本页 pytest/npm/smoke 抓到，只有 `record_sse --check`/stage7 抓——「回归网」名不副实 | 给一条实际聚合示例（至少 `make stage7` + `make docker-smoke`），或把「一条命令」改成「每个门禁各一条命令」 |
| 41-45、106-115 | save/pytest/npm/provision 期望块 | **低**：save 实际多「位置/下一步」2 行、provision 实际多 4 行 `已执行：…`，两处未标「（节选）」 | 补「（节选）」或补全 |
| 46、60-61 | 「从上往下依次是 1/8 起栈、2/8 health…」 | **低**：块里没有 1/8 起栈那一行；实跑 nginx 行会出现两次（第 5 步 SSE 检查内部 + 第 6 步），页面块只显示一次 | 删「1/8 起栈」或标「（节选）」；nginx 行注明只留 6/8 一次 |
| 3、31 | 前置 / 第 4 步 | **低**：`docker-smoke.sh` 预检还要求宿主机 `python3`（≥3.8）和 `curl`，页面未列；`--build` 在镜像被清/首次时约 8 分钟（page-13 有，本页未点） | 前置补宿主机 python3/curl；一句「首次/镜像被清会重建，约 8 分钟」 |

## 真输出摘录

```text
# 第 1 步（实跑，169 与页面一致；另 2 行为页面省略）
已保存快照 "p22-before"：169 个文件。
# 第 2 步（实跑；秒数随机器变）
813 passed, 30 skipped in 33.71s
# 第 3 步（实跑）
Test Files  2 passed (2)
      Tests  40 passed (40)
# skip 归因（-rs，实跑）：23 + 5 + 2
23 × 设置 REBUILD_INTEGRATION=1 才运行真实 ES/Qdrant/Meta 集成测试
 5 × 输出形状不是 sql_or_refusal（test_contract_alignment.py:115）
 2 × 这一题是拒答（OUT_OF_RANGE / UNSUPPORTED_INTENT），不产生 SQL
# 只读判据离线仿真（假连接，无 MySQL）：恰好 3 problems
写操作被放行（权限配置有误） / FAIL: 3 项问题
# 缺 source 时 --provision-ro-account（实跑；连接前就退出，未碰 DB）exit 1
缺少环境变量 REBUILD_DW_RO_PASSWORD：只读账号的密码不在仓库里，必须由部署环境提供
```

## 清理确认

- `rm -rf /tmp/replay-p22` 及 `/tmp/p22_pytest.log`、`/tmp/p22_pytest_rs.log`、`/tmp/p22_npm.log` 已删；副本内 `make docker-env` 生成的 `.env`、`scripts/lab save` 生成的 `.lab` 随副本清除。
- 源仓库只新增本报告；未改 `manual/page-22.md`（sha `a8faef53` 前后一致）、未改 `backend/uv.lock`（sha `742c28…` 前后一致）；未新建 `.lab`；用户 `.env` 未动。
- 全程未起容器/栈、未执行任何 `docker` 命令、未跑 `make docker-smoke`；Docker 侧只做了 `make -n` 与静态读脚本，未碰用户栈。
- `/tmp/p22env.sh`、`/tmp/p22_l4_b.sh` 为 finish-p22 遗留（非本会话创建、含端口/循环、无密码），未改动。
