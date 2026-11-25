# 第 14 页独立重放报告（学生视角 · 审检索）

**一句话结论**：主线命令全部可执行、核心判据可复现（`18 passed, 23 skipped`、`S2/S3 PASS`、停 ES 后主链路 `41099.5`、黄金集 23 errors、`火星销售额` 硬撑 `279159.5`、恢复 ES 后回 `S3 PASS`）；但 `recall stats` 写死的候选数（13/5）与实测不符且不稳定（实测 10/6、8/6），另有 2 处恢复/衔接说明会让学生多等 20 秒到 8 分钟。

重放方式：`/tmp/replay-p14` 仓库副本；隔离 project `p14audit`，端口覆盖 mysql 13317 / ES 19217 / Qdrant 16337 / backend 18117 / frontend 18087（页面默认 8080 一律替换为 18087，`docker compose` 一律加 `-p p14audit`）；`up -d --no-build` 复用已有 `shopkeeper-rebuild/*` 镜像，未重建。页面文字未改，只按页操作。

## 环节表

| 环节 | 页面命令（替换后） | 预期 | 实测 | 判定 |
|---|---|---|---|---|
| 前置（第 13 页遗留） | `docker compose -p p14audit ps` | 五个长驻 healthy | 5 个 healthy，init `Exited (0)` 且日志 `S2 VERIFY PASS` | ✅ 假设成立 |
| 拍快照 :20 | `scripts/lab save p14-before` | `已保存快照 "p14-before"：169 个文件` | 逐字一致（169） | ✅ |
| 离线判据 :28 | `backend/.venv/bin/python -m pytest backend/tests/recall -q` | `18 passed, 23 skipped` | `18 passed, 23 skipped in 0.42s` | ✅ |
| source env :36 | `source scripts/export-docker-env.sh` | 成功时无输出 | 无输出、exit 0 | ✅ |
| 真跑 20 题 :37 | `make stage3` | `S2 VERIFY PASS` / `41 passed` / `813 passed, 30 skipped` / `S3 PASS` | 全部出现（`41 passed in 1.22s`、`813 passed, 30 skipped in 32.49s`） | ✅ |
| 检索统计行 :57 | 同上（节选） | `candidates[columns=13 values=1 metrics=5]` | `columns=10 metrics=6`（首跑）、`columns=8 metrics=6`（Qdrant 重启后） | ❌ 数字不符且不稳定 |
| 停 ES :81 | `docker compose -p p14audit stop elasticsearch` | 只停检索 | 返回 0、ES `Stopped` | ✅ |
| 停 ES 后查数 :85 | `curl ...127.0.0.1:18087/api/query -d '{"query":"华北销售额"}'` | `rows: [[41099.5]]` | 逐字一致 | ✅ |
| 黄金集变红 :95 | `(cd backend && REBUILD_INTEGRATION=1 .venv/bin/python -m pytest -q tests/recall)` | `18 passed, 23 errors` + 指定 Failed 文本 | 23 errors（0.57s）、Failed 文本逐字一致 | ✅ |
| 恢复 ES :106 | `docker compose -p p14audit start elasticsearch; ... ps` | 回到 healthy | 立即 `ps` 显示 `(health: starting)`，约 20–22s 后才 healthy | ⚠️ 文案无等待判据 |
| 恢复后复验 :104 | `make stage3` | 回到 `S3 PASS` | `S2 VERIFY PASS` / `813 passed, 30 skipped` / `S3 PASS` | ✅ |
| 连续执行（整段） | 同一 shell 连续跑完 :20–:108 | pwd 不变、无 exit 127 | pwd 全程 `/tmp/replay-p14`、无 127（仅 :95 按预期 exit 1） | ✅ |
| 契约外未知词 :71 | 同一条 curl 改问 `火星销售额` | `279159.5`（硬撑） | ES 停/启两种状态都回 `279159.5` | ✅ 核实无误 |

补充：`lab save` 同名再拍实测被拒，提示"换一个名字 / `scripts/lab list`"，与 :18 预告一致 ✅；`make stage3` 首次跑离线缓存目录已清，结果不变。

## 问题清单（8 条）

| page-14.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| :3、:18 | "本页不改仓库里的任何文件" / "本页不动文件" | 第 1 步 `lab save` 实测在仓库内写 `.lab/snapshots/p14-before/`（169 个文件），:104 又说"本页没改文件"，口径自相矛盾 | 改成"不改受版本控制的文件；lab 快照会写 `.lab/`（已被忽略）" |
| :104–108 | "把停掉的服务拉回来，等它回到 healthy" | 无等待判据/时长：`docker compose start` 立即返回，`ps` 先显示 `(health: starting)`，约 20–22s 才 healthy；此刻跑 `make stage3` 会红 | 写明"轮询 `ps` 到显示 `(healthy)`（约 20–30 秒）再继续"，或给一条等待命令 |
| :28 | `backend/.venv/bin/python -m pytest ...` | 依赖 `backend/.venv`（第 0 页 `make install` 产物），本页前置只说"整栈还在跑"；新终端/跳页时 `.venv` 不在会直接找不到解释器 | 前置补一句"backend/.venv 已由第 0 页建好" |
| :57、:67 | `candidates[columns=13 values=1 metrics=5]`、"13 个字段候选被裁成 5 个" | 实测 10/6 与 8/6（同一环境重启 Qdrant 后变化）；仓库 `docs/SETUP-FROM-SCRATCH.md:460` 又写 12/4，三处不一致；候选数随向量索引装载状态变，不可逐字对 | 去具体候选数（`columns=… values=1 metrics=…`），或标注"示例值，因索引状态而异" |
| :33 | "红在第一条 `S2 FAIL: 连接 … 失败`" | 真实错误文本不是这个：实测 `S2 FAIL: 读取 manifest 失败：(2003, "Can't connect to MySQL server on '127.0.0.1' ([Errno 111] Connection refused)")` | 照抄真实错误，或改述为"红在读 manifest、连不上 MySQL" |
| :36、:95（跨页） | 只在第 3 步 `source`；拆一刀第 3 步直接再跑 pytest | "同一终端整段执行"只在 :3 说一次；拆一刀若新开终端，实测红 `S2 FAIL: 缺少环境变量 REBUILD_MYSQL_PASSWORD…宿主机请先 source scripts/export-docker-env.sh`（不是黄金集变红） | 拆一刀开头显式写"沿用同一 shell；新终端先重新 `source`" |
| :33（跨页） | "回第 13 页 `make docker-up`" | `make docker-up` = `docker compose up -d --build`（第 13 页称首次约 8 分钟）；只是栈被停掉时 `docker compose start` / `up -d`（不 `--build`）即可，恢复代价被放大 | 区分故障：栈没起 → `up -d`；改了代码/镜像 → 才 `--build` |
| :3、:85（最易卡） | "把下面的 8080 换成你那个端口" + `curl ...:8080/...` | 提示只在前置一行；实测端口改过后照抄 8080 会打到本机无关服务，回 `{"message":"Router not found for request POST /api/query"}`（404，像"接口坏了"） | 在 curl 代码块旁就地提示，或改成从 `.env` 取端口的写法 |

## 真输出摘录

```text
$ backend/.venv/bin/python -m pytest backend/tests/recall -q
18 passed, 23 skipped in 0.42s
$ source scripts/export-docker-env.sh && make stage3        # 节选
S2 VERIFY PASS
41 passed in 1.22s
recall stats: query='华北销售额' keywords=3 es_roundtrips=1 qdrant_roundtrips=2 (column=1 metric=1) meta_roundtrips=5 candidates[columns=10 values=1 metrics=6] final[tables=2 columns=5 metrics=1 values=1]
813 passed, 30 skipped in 32.49s
S3 PASS
$ curl ...18087/api/query -d '{"query":"华北销售额"}'        # ES 已停
data: {"type": "result", "data": {"columns": [{"name": "销售额", "type": "number"}], "rows": [[41099.5]]}}
$ curl ...18087/api/query -d '{"query":"火星销售额"}'        # 契约外未知词
data: {"type": "result", "data": {"columns": [{"name": "销售额", "type": "number"}], "rows": [[279159.5]]}}
$ (cd backend && REBUILD_INTEGRATION=1 .venv/bin/python -m pytest -q tests/recall)   # ES 已停
18 passed, 23 errors in 0.57s
E  Failed: REBUILD_INTEGRATION=1 但服务不可用：{'mysql': True, 'es': False, 'qdrant': True}；请先启动 MySQL/ES/Qdrant 并 make stage2
$ docker compose -p p14audit ps elasticsearch                # start 后立即查
p14audit-elasticsearch-1  Up Less than a second (health: starting)   # 约 20s 后 (healthy)
$ make stage3                                                # 恢复后
S2 VERIFY PASS ... 813 passed, 30 skipped in 28.46s ... S3 PASS
```

## 隔离声明与清理

- 只读原仓库；页面命令在 `/tmp/replay-p14` 副本执行（仅改副本 `.env` 的上述 5 个端口 + `FRONTEND_BIND=127.0.0.1`）。`manual/page-14.md` 未改。
- 起栈为审计方按第 13 页等价方式补的前置（页面未给起栈命令）：`docker compose -p p14audit up -d --no-build`，复用 `shopkeeper-rebuild/backend:local`、`shopkeeper-rebuild/frontend:local`（镜像未重建）。
- 全程未碰用户栈/容器/端口（`dsws-trace`、`dsws-lab-ui`、`lab-mysql`、`lab-nginx`、`appsmith` 等前后状态一致）。
- 磁盘 88% 下 ES 仅报 low disk watermark（85%，副本不分配）告警，写入与 S2/S3 验收均正常。
- 清理已完成：`docker compose -p p14audit down -v`（6 个容器含一次性 init + 3 卷 + 网络全删，无 p14audit 残留）；删除 `/tmp/replay-p14`、`/tmp/rebuild-s3-recall.yaml` 及临时日志；磁盘回到 88%。
