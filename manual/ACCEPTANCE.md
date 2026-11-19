# 全书 23 页验收清单

> 按级验收：L1 按十页判据 + [建成证明海报](completeness/poster-answer.png)（12 件 × 24 个检验点），L2–L4 每级一条**级考核**（该级最后一页的「拆一刀」），再加一次**全量结构审计**；每页判据以「你应该看到」为准。命令都在仓库根目录、同一终端里整段执行（括号是子 shell）；期望输出只贴关键行，秒数、文件数、端口随机器变。

## 0. 前置
- **环境**：Docker 已运行；`uv`、Node.js LTS + npm、GNU Make、curl 齐（[page-00](page-00.md)「提前说明」）。`make install` 后 `make doctor` 末行 `12/12 通过`（page-00）。整栈建议至少 8 GB 内存（ES 堆固定 512 MB，来源 `../docs/DOCKER-DEPLOY.md` §1），并留出镜像与 ES 索引的磁盘空间（见下方水位坑）。
- **端口**：L1 用 3307 / 8000 / 8081（page-00 的端口三行）；L2 起 compose 用 3306 / 9200 / 6333 / 8100 / 8080（[page-13](page-13.md) 第 3 步）。被占就改 `.env` 里对应的 `*_HOST_PORT`，**别改 `compose.yaml`**（page-13）。
- **整栈与耗时**：p13 的级考核与 p22 要整栈；`make docker-up` 第一次构建约 8 分钟（page-13 实测）。L3 的 p15–p17、L4 的 p19–p21 判据大多离线（各页前置）。
- **已知环境坑**（重放报告实测）：① 带裸 `uv run` 的 `make stage3` / `stage0-ui` / `stage6-ui`（脚本里没有 `--frozen`）或手敲 `uv run` 会按本机镜像源重写 `backend/uv.lock`（`lab reset` 管不到它）——`git status` 显示变脏再 `git checkout -- backend/uv.lock`；Makefile 直接调的 `stage*` 都已 `uv run --frozen`，不会脏（[page-15](page-15.md)、[page-19](page-19.md)、[page-21](page-21.md)）；② ES 默认低/高/洪水水位 85% / 90% / 95%：85–89% 只告警、写入与 S2/S3 正常，≥90% 高水位才危险（不再分配分片）、≥95% 索引转只读（`review/replay-page-14.md`），别把盘跑满；③ 别在别人的栈上做级考核，要并行验收就用仓库副本 + 独立 compose 项目名 + 端口覆盖（见 `review/replay-page-14.md`、`review/replay-page-18.md`）。

## 1. 结构审计（任何环境可做）
`python3 manual/shots/audit_book.py` 是离线只读审计：查 23 页 H1/六段、代码围栏成对、图片引用、敏感串、`manual/README.md` 坏链；只验结构、不验判据真假。期望末行（来源 `shots/audit_book.py`）：

```text
页面：23/23 通过；README 坏链：0
```

## 2. L1 验收（page-00 – page-09，「造」）
十页各造一个零件，判据就是各页「你应该看到」；逐页对账（数字/输出均取自各页）：
- [p00](page-00.md) `make doctor` → `12/12 通过`；[p01](page-01.md) 容器 running、`SELECT VERSION()` 有输出且看不到 `dw`；[p02](page-02.md) 5 张表、`115`、华北 `19`。
- [p03](page-03.md) `/health` → `{"ok":true}`；[p04](page-04.md) 两次请求返回一字不差；[p05](page-05.md) `["华北","销售额"]`；[p06](page-06.md) 打出 5 行带 JOIN 的 SELECT；[p07](page-07.md) `sales` = `41099.5`；[p08](page-08.md) 12 条 `progress` + 1 条 `result`；[p09](page-09.md) 浏览器 `8081` 问一句出 `41099.5`；L1 无「拆一刀」，另用[建成证明海报](completeness/poster-answer.png)对账（来源 `manual/README.md`）。

## 3. L2 验收（page-10 – page-13，「换」真件）
逐页对账（命令/数字取自各页「动手」「你应该看到」）：
- [p10](page-10.md) 换真数据：清洗后 `405` 行 / `1136341.10`，naive `1144735.50`（差 `8,394.40`）；[p11](page-11.md) 换真契约：`backend/.venv/bin/python -m lab.app` 打出 5 行 SQL（与 p6 逐字一致），`(cd backend && .venv/bin/python -m app.schema_contract --check)` → `S1 PASS`。
- [p12](page-12.md) 换真执行器：`backend/.venv/bin/python -m lab.db` → 金额行 `Decimal('1144735.50')`、上限 `1000 行`、非 SELECT 抛 `PermissionError`、慢查询抛 `OperationalError`；[p13](page-13.md) 换真部署：`make docker-up` → `docker compose ps` 5 行 healthy、`ps -a` 多一行 `Exited (0)`（init），`make docker-smoke` → `DOCKER SMOKE PASS`。

**级考核（第 13 页「拆一刀」：拆编排）**——不看页面做完没有，看拆完能不能说清「起得来 ≠ 部署好」：
1. `make docker-down`（数据卷保留）。
2. 打开 `compose.yaml`：删 `init:` 整段（全文件 `condition: service_healthy` 有 4 处，别瞎删），再删 `backend` 的 `depends_on:` 里指向 init 的三行——只删 init，compose 会报 `service "backend" depends on undefined service "init": invalid compose project`；`docker compose config -q` 应通过、只剩 5 个服务。
3. 跑 `make docker-smoke`：第 **3/8** 步红（先轮询约 120 秒，别以为卡死）——五座长驻服务仍 healthy、`/api/health` 仍 200，但已没有 init；`no such service: init` 是预期内：

```text
== 3/8 五个长驻服务 healthy + init 正常退出 ==
init 没有成功退出（state=缺失, exit=?）
DOCKER SMOKE FAIL: 120 秒内服务状态没齐
```

4. 还原：`scripts/lab reset p13-before --yes`（末行 `现在工作区与快照 "p13-before" 完全一致。`）→ `make docker-up` → `make docker-smoke` 回到 `DOCKER SMOKE PASS`。命令与期望输出均取自 [page-13](page-13.md)「拆一刀」；还原后整座城留着跑，L3 要在这套栈上审。

## 4. L3 验收（page-14 – page-17，「审」不确定输出）
逐页对账：
- [p14](page-14.md) `backend/.venv/bin/python -m pytest backend/tests/recall -q` → `18 passed, 23 skipped`；`make stage3` → `S3 PASS`；`docker compose stop elasticsearch` 后 `POST /api/query` 仍回 `41099.5`，真检索黄金集 `18 passed, 23 errors`。
- [p15](page-15.md) `backend/.venv/bin/python -m pytest backend/tests/generate -q` → `122 passed, 5 skipped`；`make stage4` → `基线：10/10 通过（拒答 2）` + `S4 PASS`（本机实测 38 秒）；[p16](page-16.md) `backend/.venv/bin/python -m pytest backend/tests/generate/test_guard.py -q` → `26 passed`，`(cd backend && .venv/bin/python -m app.scripts.failures --check)` → `S6 PASS`，`PYTHONPATH=backend backend/.venv/bin/python eval/probe_correction.py | tail -1` → `{"total": 20, "mismatch": 0}`；[p17](page-17.md) `backend/.venv/bin/python -m pytest backend/tests/agent/test_correct.py -q` → `14 passed`，`(cd backend && .venv/bin/python -m app.scripts.failures --check)` → `S6 PASS`，`PYTHONPATH=backend backend/.venv/bin/python eval/probe_correction.py | tail -1` → `{"total": 20, "mismatch": 0}`，语料 `11` 条 `"retryable": true` / `9` 条 `"retryable": false`。

**级考核（第 17 页「拆一刀」：关纠错）**——答案不是「红变绿」，而是「哪条判据抓到了、哪条没抓到」：
1. 打开 `backend/app/agent/correct.py`，找到 `def propose_correction`，在 `policy = contract.correction` 后插 4 行（缩进 4 格）：立即 `return CorrectionProposal(`，参数 `attempted=False, ok=False, error=error, note="拆一刀：校正已关闭"`，再多一行 `)`（多行写法照 page-17 抄）。
2. 重跑三条判据（节选；秒数会变）：

```bash
backend/.venv/bin/python -m pytest backend/tests/agent/test_correct.py -q
(cd backend && PYTHONUNBUFFERED=1 .venv/bin/python -m app.scripts.failures --check) 2>&1 | tail -5
PYTHONPATH=backend backend/.venv/bin/python eval/probe_correction.py | tail -1
```

```text
5 failed, 9 passed in 0.14s
  corrected            期望 result               实际 SQL_SYNTAX
FAIL: 1 项不符合预期
{"total": 20, "mismatch": 0}
```

失败矩阵 9 个场景**只红 `corrected` 一格**，probe 的 20 条语料照绿——单元判据 + 失败矩阵抓到了，语料判据没抓到。
3. 还原：`scripts/lab reset p17-before --yes` → `现在工作区与快照 "p17-before" 完全一致。`；再跑 `backend/.venv/bin/python -m pytest backend/tests/agent/test_correct.py -q | tail -1` → `14 passed in 0.11s`、`(cd backend && .venv/bin/python -m app.scripts.failures --check | tail -1)` → `S6 PASS`（命令与输出均取自 page-17）。

## 5. L4 验收（page-18 – page-22，「守」事故与越权）
逐页对账：
- [p18](page-18.md) `(cd backend && .venv/bin/python -m app.scripts.security --verify-ro-account)` → 写操作被拒 `(1142, "UPDATE command denied…")` + `PASS: 该账号在 dw 上只有 SELECT`；可选 `make stage5-live` → `S5 LIVE PASS`。
- [p19](page-19.md) `(cd backend && .venv/bin/python -m app.scripts.security --check)` → `36/36` 拒绝 + `11/11` 放行 + `8/8` 基线 + `S5 PASS`；`--corpus` → `语料：47 条，失败 0 条`。
- [p20](page-20.md) `(cd backend && .venv/bin/python -m pytest tests/agent -q -k cancel)` → `6 passed, 108 deselected`；`(cd backend && .venv/bin/python -m app.scripts.record_sse --check)` → `S7 SSE RECORD PASS（14 个夹具与真实输出一致）`。
- [p21](page-21.md) `/api/steps = 12`（条件步骤 `correct_sql`）、`/api/errors = 16`（3 类）；夹具合契约 `30 passed`；`(cd frontend && npm test)` → `40 passed (40)`。
- [p22](page-22.md) `(cd backend && .venv/bin/python -m pytest -q)` → 无 `failed`（实测 `813 passed, 30 skipped`，数字会漂）；`(cd frontend && npm test)` → `40 passed (40)`；`make docker-smoke` → `DOCKER SMOKE PASS`。

**级考核（第 22 页「拆一刀」：抢窗口给 `dw_reader` 注入 GRANT ALL；命令与期望输出均取自 [page-22](page-22.md)「拆一刀」）**：
1. 终端 B 先粘、回车（让循环替你等，实测窗口只有约 3 秒），再在终端 A 跑 `make docker-smoke`：

```bash
source scripts/export-docker-env.sh
seen=0; end=$((SECONDS+60)); while [ "$SECONDS" -lt "$end" ]; do
  id="$(docker compose ps -aq init 2>/dev/null)"; [ -z "$id" ] && { sleep 0.1; continue; }
  s="$(docker inspect -f '{{.State.Status}}' "$id" 2>/dev/null)"; [ "$s" = running ] && seen=1
  [ "$seen" = 1 ] && [ "$s" = exited ] && { echo "watcher: 捕捉到 init 退出，立刻注入 GRANT ALL"; break; }
  sleep 0.1; done
[ "$seen" = 1 ] || { echo "没等到 init 跑起来（60 秒）：先确认栈已起、A 的 smoke 已开跑（docker compose ps -a），再重跑本步" >&2; exit 1; }
docker compose exec -T mysql mysql -uroot -p"$REBUILD_MYSQL_ROOT_PASSWORD" -e "GRANT ALL ON dw.* TO 'dw_reader'@'%'"
```

2. 期望：1–6 步全绿，第 **7** 步红，fail-fast 停在这里、第 8 步不跑；同一越权下第 8 步判据单跑仍 `S2 VERIFY PASS`（`docker compose run --rm --no-deps init python -m app.build_meta_knowledge --verify | tail -1`）：

```text
写操作尝试：写操作被放行（权限配置有误）
FAIL: 3 项问题
DOCKER SMOKE FAIL: 只读账号验证未通过
```

3. 还原回 PASS：`(cd backend && .venv/bin/python -m app.scripts.security --provision-ro-account)` → `只读账号就绪：'dw_reader'@'%' on dw (SELECT)`；再 `make docker-smoke` → `PASS: 该账号在 dw 上只有 SELECT` + `DOCKER SMOKE PASS`。答案：网有牙（第 7 步抓住）、定位精确（只红第 7 步）、边界清楚（跑之前就有的越权会被 init 修好，归 p18 单步判据管）。

## 6. 已知限制（诚实）
- **真 LLM 成功态不可复现**：p17 对账写明，成功率只能写成「多次采样（`trials>=3`）+ 成功率 + 失败分类」，不许写「已修复」；本清单不验真模型。
- **可观测只有应用层**：p21 对账——没有 metrics、追踪、结构化请求日志、告警，`duration_ms` 只发给浏览器；不能回答 QPS / 错误率 / P99。
- **重栈耗时**：`make docker-up` 首次约 8 分钟（p13），p22 要整栈；验收中途别重建镜像。
- **端口占用**：默认端口被占就改 `.env` 的 `*_HOST_PORT`，别改 `compose.yaml`（p13）。

## 7. 失败时看哪
| 级 / 范围 | 先看 |
|---|---|
| L1（p00–p09） | `review/walkthrough.md`、`review/replay-03-05.md`、`review/replay-06-09.md` |
| L2（p10–p13） | `review/replay-page-10.md` … `review/replay-page-13.md` |
| L3（p14–p17） | `review/replay-page-14.md` … `review/replay-page-17.md` |
| L4（p18–p22） | `review/replay-page-18.md` … `review/replay-page-22.md`（p18–p22 全有） |
| 环境 / 工具 / 奇怪报错 | `../error-proofread/README.md`（真机实测台账）、`../docs/DOCKER-DEPLOY.md` §1 |
| 新重放报告 / 报告写法 | 按 [review/REPLAY-TEMPLATE.md](review/REPLAY-TEMPLATE.md) 六段模板 + 8 类必查清单写（新报告先复制模板） |

报告里标「先修」的条目是写页时已知的坑：先按报告复现，再判是页面 bug 还是环境问题；复现不了再回到对应页「对账」。
