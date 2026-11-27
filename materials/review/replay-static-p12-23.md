# 第 12–23 页独立重放报告（学生视角 · 静态/离线 · 可复现/跟随性测试）

> 依据 [REPLAY-TEMPLATE](REPLAY-TEMPLATE.md)、[SPEC](../tutorial/SPEC.md)、`GLOSSARY.md`「断层」五类、[verify-line](../docs/verify-line.md)。
> 范围：`tutorial/page-12.md` … `tutorial/page-23.md` 共 12 页；只测静态/离线部分，**不起 docker 栈、不跑拆一刀消融**（留待栈测/消融测代理）。

## 结论

12 页里 10 页可独立跟做：全部 14 个离线判据 + `make stage4/5/7` 聚合门禁 + 基线 10/10 逐字复现，数字、行号、夹具计数、契约字段几乎全命中。**2 条 blocker 断层**都是「页面代码/命令里的路径失效」：p12 的 `lab/db.py` 代码贴片读 `ROOT/contracts/sql.policy.yaml`（仓库根自 `d19565c` 移除兼容软链后该路径不存在），p23 的 `docker run` 挂载路径漏了 `materials/` 前缀——两处都会让学生照做当场失败，且都被 `coverage: static` 契约漏检（假绿）。先修这两条；另 1 条 should（p18 对 `.env.example` 的描述不准确）。跨页前置（⑤）0 条断层。

## 范围声明

- 真跑：p14–p21 全部离线 verify 块（pytest ×7、`app.scripts.failures --check/--scenarios`、`probe_correction.py`、`app.scripts.security --check/--corpus`、`record_sse --check`、TestClient 观测面脚本、`app.scripts.generate --baseline`、`app.scripts.contracts_gen --check`）+ `make stage4` / `make stage5` / `make stage7` + `tests/frontend` 全量 + 全后端 843 条 + `system/frontend` `npm test`。隔离手段 = 只读执行、零 docker。
- 方式：单 shell、从仓库根逐块执行；pytest 一律加 `-p no:cacheprovider`；uv 侧只经 Makefile 的 `uv run --frozen`（页面声明它不改 lock，实测属实）。
- 静态核对：页面引用的路径/符号/行号逐一 grep；夹具与语料计数（golden 20 / baseline 10 / scenarios 9 / injection 36+11 / correction.jsonl 20 / sse 14）程序化清点；`dw-real.sql`、`dw.sql` 解析复算金额（1144735.50 / 279159.50 / 408 非空）；`toolbox/scripts/verify.py --fast`（T0 页面↔契约同步，24/24 PASS）。
- 替换：无（未起容器/端口，不涉及映射）。
- 时点与版本：2026-11-27 上午；HEAD `34eb9fb`；uv.lock sha `bedd8223…c3b73760` 前后一致。
- 未做与原因：① 拆一刀消融（任务明确排除，全部记「待消融测」）；② 需栈命令（`docker exec` 灌库、`make docker-up/docker-smoke/stage3/stage5-live`、curl 8080、停/启 ES、浏览器对照）记「待栈测」；③ p17-viztracer 块（`uv pip install` 装包进 `.venv` + `--open` 开浏览器 + pdb 交互，契约 `kind: manual`）不跑；④ `lab save` 未用页面快照名（`p14-before` 等）执行——避免与后续按页重放的栈测代理撞名（同名 save 会被拒），改用一次性名 `replay-static-tmp` 验证机制与文件数后即删，页面名的字面命令留待栈测代理按页执行。

## 逐页环节表（期望 / 实测 / 判定）

### 第 12 页 · 换真执行器（无 verify 注解；契约 `coverage: static`）

| 环节（page-12.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 前置（:5） | p11 的 `lab/app.py`、p10 的 `dw-real.sql` | 两页均建立；`lab/app.py` 有 `/api/query`、`/api/stream`，`run_sql` 恰 10 行（:71-80） | 通过 |
| 第 1 步 灌 `dw-real`（:28） | `docker exec … dw-real.sql` | 命令依赖栈，跳过 | 待栈测 |
| 第 2 步 `lab/db.py` 代码贴片（:33-83） | 粘贴即可用 | **`ROOT/contracts/sql.policy.yaml` 不存在**（断层①，见清单）；其余字段 `limits.default_limit`/`timeout.connect_timeout_s`/`max_execution_time_ms` 均在 `system/contracts/sql.policy.yaml`（L72/82/78）命中 | **不通过（blocker）** |
| 第 3 步 换 `run_sql` + 验证（:85-97） | 回 1000 | 需库，跳过；`run_sql` 确为「`def run_sql` 到 `conn.close()` 共 10 行」，与贴片一致 | 待栈测 |
| 第 4 步 `python -m lab.db` 自检（:101-103） | 7 行输出 | 需库，跳过 | 待栈测 |
| 「你应该看到」（:107-115） | 裸游标 `(1144735.4994544983,)` / `1144735.50` / 差 `-0.0005455017` / 上限 1000 / PermissionError / 超时 | 静态复算 `dw-real.sql`：fact_order 410 行、金额非空 408（对账「408 个近似值」属实）、十进制和 = **1144735.50**、dim_date **1461** 行 ✓；float 尾数随 MySQL 版本（页面已自注） | 静态通过，数值待栈测 |
| 拆一刀（:140-149） | 改 `default_limit` 后回 1461 | 白名单确含 `lab`（`toolbox/scripts/lab:31`）；名字校验（字母/数字/点/下划线/短横线、字母数字开头、中文拒）实测与页面逐字一致；契约注释「# 明细查询默认最多返回多少行」命中 | 机制通过，消融待测 |
| 跨页（p10/p11→p12；p12→p13） | 前置已建立 / p13 要求停手动件 | p10:38-40 建 `dw-real.sql`、p11:5 建 `lab/app.py` ✓；p13:33 要求删 `lab-mysql lab-nginx` ✓ | 通过 |

### 第 13 页 · 换真部署（无 verify 注解；`coverage: static`）

| 环节（page-13.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 1 步 `lab save`（:30） | 快照 | 机制见 p12 行；`169 个文件` 实测一致 | 通过 |
| 第 2 步 停手动件（:33） | 删两个容器 | 依赖栈 | 待栈测 |
| 第 3 步 `make docker-env`（:41-43） | 末行 `已生成 …` | Makefile:174 仅在无 `.env` 时生成，生成器末行 `已生成 {output}` ✓；端口表 3307/9200/6333/8100/8080 与 `.env.example:23-27` 逐行一致，`FRONTEND_BIND=0.0.0.0` ✓ | 静态通过 |
| 第 4-6 步 起栈/smoke（:65-79） | 8 步、末行 `DOCKER SMOKE PASS` | 命令依赖栈 | 待栈测 |
| 「你应该看到」（:89-126） | ps 5 行、`ps -a` 第 6 行 init、smoke 8 步节选 | `docker-smoke.sh` 8 步标题逐字命中（`== 1/8 … ==`…`== 8/8 …`）、`meta: verify passed; skip rebuild`、`DOCKER SMOKE PASS`、`fail "120 秒内服务状态没齐"`、health 等待 360 秒，均在脚本内核实 | 静态通过，实跑待栈测 |
| 对账（:137-150） | `service_healthy` 4 处等 | `compose.yaml` 全文 `condition: service_healthy` **恰 4 处** ✓；init `restart: "no"` + `app.scripts.docker_init` ✓；backend `service_completed_successfully` ✓ | 通过 |
| 拆一刀（:170-186） | 删 init 后 3/8 红 | 描述与 compose 结构一致（init 段 3 处 service_healthy 后即 `backend:`） | 静态通过，消融待测 |
| 跨页（p13→p14） | 栈留着跑 | :192「整座城先留着跑」✓ | 通过 |

### 第 14 页 · 审检索

| 环节（page-14.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2 步 pytest recall（:44） | `18 passed, 23 skipped` | `18 passed, 23 skipped in 0.36s` | **通过** |
| 第 3 步 `make stage3`（:66） | S2/41/813/S3 PASS | 依赖整栈 | 待栈测 |
| 静态核对 | golden 20 题、`expected_*`/`must_not`、`OfflineContextBuilder` | 全部命中；23 skipped = 20 题 + 3 汇总、41 = 18+20+3 自洽；`recall-demo.sh` 确写 `/tmp/rebuild-s3-recall.yaml` 且 stage3 `head -n 40` ✓ | 通过 |
| 「你应该看到」（:74-91） | 逐字 | 离线行逐字命中；`813 passed, 30 skipped`（stage3 末段）与我独立跑的全量一致 | 通过（在线部分待栈测） |
| 拆一刀（:126-166） | 停 ES 后查询照常、黄金集整片红 | 命令依赖栈 | 待栈测（「硬撑 279159.5」的总销售额已静态复算 `dw.sql` = 279159.50 ✓） |

### 第 15 页 · 审生成

| 环节（page-15.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2 步 pytest generate（:45） | `122 passed, 5 skipped` | `122 passed, 5 skipped in 0.73s` | **通过** |
| 第 3 步 `make stage4`（:52） | 基线 10/10（拒答 2）→ 122/5 → 813/30 → `S4 PASS` | 实跑：`基线：10/10 通过（拒答 2）`；b01/b02 两行 SQL 与页面**逐字一致**；`122 passed, 5 skipped`；`813 passed, 30 skipped`；末行 `S4 PASS` | **通过** |
| uv.lock 声明（:26） | stage* 走 `--frozen` 不改 lock | sha 前后均 `bedd8223…` ✓；裸 `uv run` 仅在 `recall-demo.sh`/`stage0-ui.sh`/`stage6-ui.sh`（页面点名的三处）✓ | 通过 |
| 静态核对 | GMV 公式、`SUM(fact_order.order_amount)` 全文 3 处 | `schema.contract.yaml:336-339` 命中，全文恰 3 处（「别用全局替换…3 个指标」成立）；baseline b01-b10 = 8 sql + 2 refusal ✓ | 通过 |
| 备注 | `Makefile:88: baseline` | 实际 `baseline:` 在 Makefile:87（漂移 1 行）；页面自带免责「行号随 Makefile 排版变」，不计断层 | 备注 |
| 拆一刀（:103-142） | 8/10、12 failed、`FAIL: 3 个契约问题` | 按任务范围跳过 | 待消融测 |

### 第 16 页 · 审校验

| 环节（page-16.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2 步 pytest test_guard（:31） | `26 passed` | `26 passed in 0.31s` | **通过** |
| 第 3 步 `failures --check`（:38） | `S6 PASS` + `错误码表：16 个码，路线图要求的 7 个全在` | 两行逐字命中 | **通过** |
| 第 4 步 probe + 分布（:45-46） | `{"total": 20, "mismatch": 0}`；5/3/2/2/2/2 + 4×1 | 逐字命中（含 4 个单条码的名单） | **通过** |
| 静态核对 | 16 码、9 场景、20 语料、`policy.py:460` 同名循环 | errors.yaml 恰 16 码；scenarios.yaml 9 条；correction.jsonl 20 行；`policy.py:460` = `for column in tree.find_all(exp.Column):` **行号精确** | 通过 |
| 拆一刀（:99-122） | `1 failed, 25 passed`、mismatch 3 | 跳过 | 待消融测 |
| 跨页（p16→p17） | 拆一刀须 reset | p16:128 给出 reset 步骤 ✓，p17:7-9 前置自带自查命令 ✓ | 通过 |

### 第 17 页 · 审纠错

| 环节（page-17.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2 步 pytest test_correct（:55） | `14 passed` | `14 passed in 0.10s` | **通过** |
| 第 3 步 `failures --check`（:64） | `S6 PASS` | 命中 | **通过** |
| 第 4 步 scenarios + 语料（:75-77） | corrected 行 + 9/11 + 11/9 | `` | `corrected` | 校正闭环成功 | result | - | - | `` 逐字命中；`9 "retryable": false` / `11 "retryable": true` / `11 "expect": "corrected"` / `9 "expect": "rejected"` 全命中 | **通过** |
| 第 5 步 viztracer/pdb（:84-86） | 装包+开浏览器+交互 | 契约 `kind: manual`，跳过 | 不适用（manual） |
| 静态核对 | `correct.py:183`、CorrectionProposal 字段、errors.yaml correction 段、6 个 retryable 码 | :183 恰为 `if policy.max_attempts < 1:`；字段 `attempted/ok/error/note` 与贴片一致；`max_attempts: 1`/`revalidate: true`/`revalidate_with: [guard, policy]` ✓；retryable 6 码与页面名单一致 ✓ | 通过 |
| 证据指针（:23-24、:178-180） | PRD-对照表第 13 行、README-v2:172、两个 .sse、FINDINGS §3.1 | 全部存在且内容对得上（16.31s、触发=true 纠正成功=false；v2-natural-correct-success.sse 等）；`live_probe.py` 五类计数口径齐全；`build_datasets.py` 确按 `retryable` 校验 | 通过 |
| 拆一刀（:204-236） | 5 failed / corrected 红 / probe 绿 | 跳过 | 待消融测 |

### 第 18 页 · 守账号（无 verify 注解；`coverage: static`）

| 环节（page-18.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2-4 步（:46-58） | source / 开通 / `PASS: 该账号在 dw 上只有 SELECT` | 全部依赖 MySQL | 待栈测 |
| 静态核对 | `--provision-ro-account`/`--verify-ro-account` 旗标、test_account.py 10 条、导出两个密码变量、`stage5-live` 目标、`user: dw_reader` | 全部命中（`security.py` 旗标 ✓、`test_account.py` 恰 10 条 ✓、`export-docker-env.sh:690-691` ✓、Makefile:107 ✓、sql.policy.yaml:87 ✓） | 通过 |
| 对账（:158） | `lab reset` 救不了数据库 | WHITELIST 只收文件/目录快照，不含数据库 ✓ | 通过 |
| 描述核对（:34） | 「`.env.example` 里只有 `change-me-ro` 占位」 | 实际有两行占位（`MYSQL_ROOT_PASSWORD=change-me-root`、`REBUILD_DW_RO_PASSWORD=change-me-ro`）| **should（断层②，见清单）** |
| 跨页（p18→p19；p22 引用） | init 重建 dw_reader | compose init 命令 `app.scripts.docker_init` + 页内说明一致 | 通过 |

### 第 19 页 · 守策略

| 环节（page-19.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2 步 `security --check`（:39） | `36/36` + `11/11` + `8/8` + `S5 PASS` | 四行逐字命中 | **通过** |
| 第 3 步 `--corpus` 过滤（:50） | 6 行三类构造 + `语料：47 条，失败 0 条` | 6 行逐字命中（multi_statement ×2 / executable_comment ×2 / union ×2），47 条 = 36+11 ✓ | **通过** |
| 第 4 步 `make stage5`（:61） | `179 passed, 2 skipped` + `813 passed, 30 skipped` + `S5 PASS` | 实跑 `make stage5`：两段计数与末行 `S5 PASS` 全命中；uv.lock sha 不变 | **通过** |
| 静态核对 | `forbid_set_operations: true` 在 L31、4 行后 `forbid_executable_comments` | L31 / L35 ✓；`errors.reason_codes`（L117）✓；injection yaml 36+11 ✓ | 通过 |
| 拆一刀（:119-145） | `34/36`、`gate=1`、码退化 | 跳过 | 待消融测 |
| 跨页（p19→p20） | 拆一刀须还原 | p19:150 给 reset；p20:11-19 前置给 reset + 双自查（`31:  forbid_set_operations: true` 精确命中实测 ✓） | 通过 |

### 第 20 页 · 守取消

| 环节（page-20.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2 步 pytest（:49-50） | `6 passed, 108 deselected` + `114 passed` | `6 passed, 108 deselected in 0.49s`；`114 passed in 5.18s` | **通过** |
| 第 3 步 夹具逐帧 + `record_sse --check`（:59-60） | 2 帧（skipped + CANCELLED）逐字 + `S7 SSE RECORD PASS（14 个夹具与真实输出一致）` | 两帧逐字命中；PASS 行逐字命中 | **通过** |
| 静态核对 | `cancel.py:37`、L64、14 夹具构成、happy 24 帧 | `self._event.set()` 恰在 :37（CancelToken.cancel 内唯一）；`CancelRegistry.cancel` 在 :64 ✓；14 = 9 场景 + cancelled + 4 手写（pseudo_row/unknown_event/empty_rows/null_column）✓；happy.json 24 帧 ✓ | 通过 |
| 拆一刀（:107-133） | 2 failed、夹具不同步 | 跳过 | 待消融测 |

### 第 21 页 · 守可观测

| 环节（page-21.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 1 步 TestClient 观测面（:41-52） | steps=12/条件 correct_sql、errors=16/3 类、happy 23/12/一次、llm_refusal 19/10 | 四行**逐字命中** | **通过** |
| 第 2 步 `record_sse --check`（:59） | `S7 SSE RECORD PASS（14 个夹具与真实输出一致）` | 逐字命中 | **通过** |
| 第 3 步 协议测试（:70-71） | `30 passed` + `Tests  40 passed (40)` | `30 passed in 2.48s`；`Tests  40 passed (40)`（末行 Duration ✓） | **通过** |
| 第 4 步 `make stage7`（:78） | 6 段门禁 → `S7 PASS` | 实跑：contracts_gen PASS、record_sse PASS、`45 passed`（tests/frontend 全量 45 条声明属实）、npm 40、`813 passed, 30 skipped`、`S7 PASS`；uv.lock 不变 | **通过** |
| 静态核对 | record_sse L39/195/199-205/201/205、graph.py:428 及 L430-436/438-442/444-452/453/454、`test_s6_langgraph.py:96`、steps.yaml | 行号**全部精确命中**（含 `_normalize` 块结构与「只删两行赋值会缩进报错」的 if/elif 布局）；steps.yaml 12 节点/10 stages/条件 `correct_sql` ✓ | 通过 |
| 拆一刀（:173-205） | 10 条夹具红、4 条手写不红 | 跳过 | 待消融测 |

### 第 22 页 · 守回归（无 verify 注解；`coverage: static`）

| 环节（page-22.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 2 步 全量 pytest（:45） | `813 passed, 30 skipped`（843 条） | `813 passed, 30 skipped in 35.27s` | **通过** |
| 第 3 步 npm test（:50） | `Tests  40 passed (40)` | 命中 | **通过** |
| 第 4 步 `make docker-smoke`（:57） | 8 步 → `DOCKER SMOKE PASS` | 依赖整栈 | 待栈测 |
| 静态核对 | 8 步表、`120 秒`/`360 秒`、`meta: verify passed; skip rebuild`、README S8 待做、`--provision-ro-account` 还原 | 全部命中（smoke 步骤号与页面两处 8 步表一致；README:53「S8 性能 | 待做」✓） | 通过 |
| 拆一刀（:136-180） | 终端 B 窗口注入、第 7 步红 | 跳过 | 待消融测（窗口 ~3s 只能实跑验证） |

### 第 23 页 · 装体验（无 verify 注解；`coverage: static`）

| 环节（page-23.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--|
| 第 1 步 起栈（:31-34） | 镜像判断 + up | 依赖栈 | 待栈测 |
| 第 2 步 `docker run` 成熟版（:46-49） | 挂 `dist/` 与 `nginx.conf` | **挂载路径 `$PWD/deliverable/v2/...` 不存在**（断层①，见清单）；正确路径为 `materials/deliverable/v2/original-frontend/{dist,nginx.conf}`（页面表格 :17 与对账 :78 写的就是 `materials/...`） | **不通过（blocker）** |
| 第 3 步 npm test（:55） | `Tests  40 passed (40)` | 命中（同 p21） | **通过** |
| 静态核对 | `shopkeeper-rebuild_default`、`NGINX_IMAGE`、React19/Tailwind3.4.17、`agentApi.ts`、`StepRail.tsx`、17 行 HTML | compose `name: shopkeeper-rebuild`（L1）+ `frontend:local`（L149）+ `FRONTEND_HOST_PORT:-8080`（L160）✓；`generate_docker_env.py` 按 `.env.example` 模板生成含 `NGINX_IMAGE` ✓；React `^19.0.0` / Tailwind `^3.4.17` ✓；`agentApi.ts:89` `${API_BASE_URL}/api/query` ✓；`lab/index.html` 恰 17 行 ✓ | 通过 |
| 拆一刀（:95-151） | 29 行 HTML 出 `41099.5` | 跳过 | 待消融测 |
| 跨页（p22→p23） | 拆一刀已还原、smoke PASS | :5 前置声明 ✓ | 通过 |

## 断层清单

| # | 页码 | 类别 | 现象 | 期望 | 建议修法 | severity |
|:--:|:--|:--:|:--|:--|:--|:--:|
| 1 | page-12.md:42（`lab/db.py` 代码贴片） | ① | 代码 `yaml.safe_load((ROOT / "contracts" / "sql.policy.yaml").read_text(...))` 解析到 `<仓库根>/contracts/sql.policy.yaml`，该路径**不存在**（真实契约在 `system/contracts/sql.policy.yaml`）。学生照贴后 `python -m lab.db` 在 import 期 `FileNotFoundError`，第 3/4 步与整页判据全部不可达。根因：`d19565c refactor(layout): 移除全部兼容软链，统一 canonical 路径` 删掉根目录 `contracts` 软链时页面没同步（③式根因、①式现象）；page-12.yaml `coverage: static` 只查 `system/contracts/sql.policy.yaml` 存在、不解析 python 贴片内路径，T0 假绿 | 贴片读 `ROOT / "system" / "contracts" / "sql.policy.yaml"`（与同页拆一刀「打开 `system/contracts/sql.policy.yaml`」一致） | 把代码贴片第 42 行改为 `POLICY = yaml.safe_load((ROOT / "system" / "contracts" / "sql.policy.yaml").read_text(encoding="utf-8"))`；契约 page-12.yaml 可加一条符号断言防回潮（如 `pattern: '"system" / "contracts"'` 挂到页面引用说明） | **blocker** |
| 2 | page-23.md:47-48（`docker run` 两个 `-v`） | ① | 挂载 `-v "$PWD/deliverable/v2/original-frontend/dist:..."`、`-v "$PWD/deliverable/v2/original-frontend/nginx.conf:..."`——仓库根无 `deliverable/`（只有 `deliverables/` 与 `materials/deliverable/`）。同页表格 :17 与对账 :78 写的 `materials/deliverable/v2/original-frontend/` 是对的，唯命令漏前缀；page-23.yaml static.paths 也写正确路径，T0 假绿。学生照敲：docker 把不存在的 host 路径自动建成空目录挂入，8088 起来但页面空/404、反代配置丢失，对照实验做不成 | 命令挂 `$PWD/materials/deliverable/v2/original-frontend/dist` 与 `$PWD/materials/deliverable/v2/original-frontend/nginx.conf` | 两个 `-v` 的 host 路径加 `materials/` 前缀；命令与契约路径保持同一写法 | **blocker** |
| 3 | page-18.md:34 | ② | 「`.env.example` 里只有 `change-me-ro` 占位」与实际不符：`.env.example` 有两行占位（`MYSQL_ROOT_PASSWORD=change-me-root`、`REBUILD_DW_RO_PASSWORD=change-me-ro`） | 描述与文件内容一致 | 改成「`.env.example` 里只有 `change-me-root` / `change-me-ro` 占位」 | should |

统计：① 2 条 / ② 1 条 / ③ 0 条（p12 根因含③式成因，按现象归①）/ ④ 0 条（28 张证据图/gif 全部存在；内容新鲜度需截图比对，超出静态范围）/ ⑤ 0 条（p12←p10/p11、p17←p16、p20←p19、p21←p20、p23←p22 的前置均有回绿/自查闭环）。**blocker 2 条，should 1 条。**

## 真输出摘录

```text
$ system/backend/.venv/bin/python -m pytest system/backend/tests/recall -q
18 passed, 23 skipped in 0.36s
$ system/backend/.venv/bin/python -m pytest system/backend/tests/generate -q
122 passed, 5 skipped in 0.73s
$ (cd system/backend && .venv/bin/python -m app.scripts.failures --check)
  错误码表：16 个码，路线图要求的 7 个全在
S6 PASS
$ PYTHONPATH=system/backend system/backend/.venv/bin/python system/eval/probe_correction.py | tail -1
{"total": 20, "mismatch": 0}
$ (cd system/backend && .venv/bin/python -m app.scripts.record_sse --check)
S7 SSE RECORD PASS（14 个夹具与真实输出一致）
$ make stage4
基线：10/10 通过（拒答 2）   （b01/b02 SQL 与页面逐字一致）
813 passed, 30 skipped in 31.13s
S4 PASS
$ make stage7
S7 CONTRACT GEN PASS（3 个文件与契约一致）
45 passed / Tests  40 passed (40) / 813 passed, 30 skipped
S7 PASS
$ sha1sum system/backend/uv.lock   # 跑前跑后
bedd82235e7e326869509dad27b963cfc3b73760  system/backend/uv.lock
```

（秒数、耗时随机器变化；其余逐字输出见各页环节表。）

## 清理确认

- [x] 容器 / compose 项目：未启动（全程零 docker）
- [x] 临时目录：`system/frontend/dist`（`make stage7` 的 `npm run build` 产物，跑前不存在）已删；`.lab/snapshots/replay-static-tmp`（`lab save` 机制验证用）已删
- [x] `system/backend/uv.lock`：前后 sha 一致 `bedd8223…c3b73760`，未触碰
- [x] `.lab/`：仅新建过 `replay-static-tmp` 并已清；既有 `p17-evidence-20261126`、`pre-reset-20261126-102531` 未碰；页面快照名（`p14-before`…`p22-before`）刻意未占用
- [x] 用户栈：未触碰
- [x] 只新增本报告 `materials/review/replay-static-p12-23.md`；`tutorial/page-12.md`…`page-23.md` 与源码未改（git status 无改动条目）；`system/backend/.pytest_cache` 为 `make stage*` 按页原样跑 pytest 的既有缓存（gitignored），未清理

## 8 类必查清单

- [x] **uv.lock 改写** → 结论：通过。跑过 `make stage4/5/7`、多个 pytest、baseline 生成器；sha 前后一致，且实证「裸 `uv run` 只在 recall-demo.sh / stage0-ui.sh / stage6-ui.sh」与页面声明一致。
- [x] **cwd 子 shell** → 结论：通过。页面命令均用 `(cd … && …)` 子 shell，逐块跑完 `pwd` 仍在仓库根，无 exit 127。
- [x] **管道退出码** → 结论：通过。页面自带正确口径（p19 拆一刀 `gate=${PIPESTATUS[0]}`、p16/p17 `| tail -1` 判据行），无把红判据记绿之处。
- [x] **端口与 `.env`** → 结论：通过。p13/p14/p17/p23 均注明 8080 为 `.env` 默认值可替换、不改 `compose.yaml`；端口表与 `.env.example` 逐行一致。
- [x] **lab 快照边界（DB、uv.lock）** → 结论：通过。p12/p18/p21 正确声明「完全一致只承诺白名单文件」；白名单实测不含 `.env`/数据库/uv.lock。
- [x] **重录假绿** → 结论：通过。p20/p21 明确警告「别照 record_sse 提示重录」；本次全程只 `--check`。
- [x] **精确行号与同名代码** → 结论：通过。`policy.py:460`、`cancel.py:37/L64`、`correct.py:183`、`record_sse.py L39/195/199-205/201/205`、`graph.py:428` 各段、`test_s6_langgraph.py:96`、`sql.policy.yaml:31` 全部精确命中；p16 对「同名循环两处、别全局替换」有专门警告。
- [x] **跨页前置回绿** → 结论：通过。p17←p16、p20←p19、p21←p20、p23←p22 的前置都带 reset/自查命令，且 p20 的自查行 `31:  forbid_set_operations: true` 与实文件精确一致；⑤类 0 条断层。
