# 课程目录草案 v2 · 23 页（造 → 换 → 审 → 守）

> 依据：`humen-desicions/09-ablation-course.md` D44（四级 = 四种工程动作，10+4+4+5 = 23 页）；D34 封装梯度、D35 三段式降级、D42/D43 交付物口径。基线：`manual/page-00.md`–`manual/page-09.md`、`manual/maturity/stages.json`、`manual/map/data.json`。
> 口径：L1 十页原样（page-00–09，只列标题）；L2–L4 十三页新写，编号 page-10–22（文中记 P10–P22），沿用 `page-0N` 命名。本文件只做盘点与目录，不改任何现有文件。
> 数字：2026-11-19 本机实测——`pytest --collect-only` 843 条、全套 `813 passed / 30 skipped`、前端 `40 passed`、离线门禁 `S1/S5/S6/S7 PASS`。README 的 782/31 与实测不一致（见 E-7）。

## A. 素材盘点表

按 S 阶段与能力块逐项核实（路径均存在；测试数为实跑值，不是文件里的 `def test_` 计数）。

| 能力（阶段） | 可复用素材（文件路径） | 状态 | 备注 |
|---|---|---|---|
| 契约（S0/S1） | `contracts/steps.yaml`（12 节点/10 段）、`contracts/sse.schema.json`（3 事件）、`contracts/errors.yaml`（16 码/3 类）、`contracts/schema.contract.yaml`（5 表/24 列/6 指标）、`contracts/sql.output.schema.json`；检查/生成 `backend/app/schema_contract.py`、`backend/app/scripts/contracts_gen.py`；测试 `backend/tests/test_s0_contract.py`(19)、`test_s1_schema_contract.py`(40) | 可直接用 | `--check` / `--check-doc` / `contracts_gen --check` 全离线；L2 判据直接引用 |
| 元知识构建（S2） | `backend/app/build_meta_knowledge.py`、`backend/app/build/`（es_store / qdrant_store / embedding / meta_store / pipeline / plan）、`fixtures/dw.sql`；测试 `test_s2_build.py`(17)、`test_meta_store.py`(4)；`make stage2` | 可直接用 | `--dry-run/--fresh/--verify/--assert-idempotent` 现成；需三存储 |
| 检索 ES/Qdrant（S3） | `backend/app/recall/`（clients 509 行、keywords、nodes、pipeline、render）、`backend/tests/recall/golden.yaml`（20 题）、`eval/golden.jsonl`（retrieval 20 条）、`scripts/recall-demo.sh`、`make stage3`；`backend/tests/recall/` 离线 `18 passed, 23 skipped` | 可直接用 | 集成 23 条需三存储；线上主链路不走检索（见 P14 拆一刀） |
| SQL 生成·确定性（S4） | `backend/app/generate/deterministic.py`(433)、`context.py`、`intent.py`、`prompts.py`、`output_schema.py`、`backend/tests/generate/baseline.yaml`（10 题）、`make stage4` / `make baseline`；`tests/generate` 实跑 `122 passed, 5 skipped` | 可直接用 | 离线可复现；`--now` 可注入时间钉死结果 |
| SQL 生成·LLM（S4 可选） | `backend/app/generate/provider.py`(257，HttpLlmGenerator)、README「LLM 接入」四变量、`eval/correction_live.jsonl`(8)、`eval/live_probe.py`、`eval/probe_correction.py`、`eval/FINDINGS.md` | 需改造 | key 不入库；缺 `trials>=3` 统计脚本；FINDINGS 已给采样口径 |
| 校验（S4 静态 + S6 关卡） | `backend/app/generate/guard.py`、`backend/app/agent/validate.py`、`contracts/sql.output.schema.json`、`eval/correction.jsonl`(20，含 `expect_code`)、`tests/generate/test_guard.py`（实跑 26） | 可直接用 | 错误码对齐另见 `tests/agent/test_error_alignment.py` |
| 纠错（S6） | `backend/app/agent/correct.py`(238，最多 1 次)、`contracts/prompts/correct_sql.prompt`、`fixtures/failures/scenarios.yaml` 的 `corrected` 场景、`tests/agent/test_correct.py`（14 passed）、`deliverable/PRD-对照表.md` 第 13 行 | 需改造 | 真模型「纠正成功」未复现；需加「上下文外列」变体做离线复现 |
| 只读账号（S5） | `backend/app/security/account.py`(185)、`backend/app/scripts/security.py --provision-ro-account/--verify-ro-account/--demo`、`backend/app/scripts/docker_init.py`、`make stage5-live`、`scripts/docker-smoke.sh` 第 7 步、`tests/security/test_account.py`（10 passed） | 可直接用 | 需 MySQL + 环境变量 `REBUILD_DW_RO_PASSWORD`（密码不入库） |
| SQL 策略（S5） | `backend/app/security/policy.py`(536)、`executor.py`(287)、`pipeline.py`、`backend/app/sqllex.py`、`contracts/sql.policy.yaml`、`fixtures/injection/sql-injection.yaml`（拒 36 / 放 11）、`make stage5`；`tests/security` 实跑 `179 passed, 2 skipped` | 可直接用 | 离线门禁实测 `36/36 + 11/11 + 8/8` |
| 取消（S6） | `backend/app/agent/cancel.py`(75)、`backend/app/main.py` 的 `POST /api/cancel`、`fixtures/sse/cancelled.json`、`tests/agent`（实跑 114 passed）、`make stage6-ui` | 可直接用 | 浏览器验收含取消；取消是独立状态而非 done |
| 失败矩阵（S6） | `fixtures/failures/scenarios.yaml`（9 场景：happy/6 类失败/slow/corrected）、`backend/app/scenarios/`（app + loader）、`backend/app/scripts/failures.py --check/--table/--scenarios`、`tests/agent/test_scenarios.py`、`frontend/tests/s6_failures.mjs` | 可直接用 | `--check` 实测 `S6 PASS`（9 场景结局 + 16 码） |
| SSE 录制回放（S7） | `backend/app/scripts/record_sse.py`（`--check`）、`fixtures/sse/`（14 条）、`frontend/tests/replay-server.mjs`、`tests/frontend/test_sse_fixtures.py`、`make stage7` | 可直接用 | 实测 `S7 SSE RECORD PASS（14 个夹具与真实输出一致）` |
| docker 编排 | `compose.yaml`（6 服务：mysql / elasticsearch / qdrant / init / backend / frontend）、`compose.lab-ui.yaml`、`docker/backend.Dockerfile`、`docker/frontend.Dockerfile`、`docker/nginx.conf`、`docs/DOCKER-DEPLOY.md`、`make docker-env/up/down/logs/reset` | 可直接用 | `.env` 由 `make docker-env` 生成（随机密码，不入库） |
| smoke 验收 | `scripts/docker-smoke.sh`（8 步 + init 幂等）、`scripts/smoke_checks.py`、`scripts/docker-reset.sh`、`tests/test_docker_smoke_script.py`（10 passed）、`tests/test_smoke_checks.py`（53 passed） | 可直接用 | 8 步覆盖健康/步骤数/真查询/nginx 缓冲/只读/S2 对账；**本次未实跑**（需起栈） |
| 黄金集 | `eval/golden.jsonl`(30 = 检索 20 + SQL 基线 10)、`backend/tests/recall/golden.yaml`(20)、`backend/tests/generate/baseline.yaml`(10)、`eval/freeze.py`/`freeze.json`、`eval/conformance/`（8 个 gate，`report.json` 全 pass） | 可直接用 | 判据要按 FINDINGS 改成多次采样，不写「已修复」 |
| 环境与门禁 | `scripts/doctor.sh`（12 项：工具 6 + 依赖 3 + 端口 3）、`Makefile`（25 个目标：12 个 stage 验收 = 9 个 stage + 3 个 -ui，7 个 docker-*，6 个辅助）、`docs/SETUP-FROM-SCRATCH.md` | 可直接用 | 判据要求 3307/8000/8081 空闲 |
| 教材正文（S0–S8） | `design/book/chapters/10-s0-s4.md`(1006 行)、`20-s5-s8.md`(1223 行)、`design/book/manifest.txt`、`design/book-editorial/build_book.py`（组装 `book.html`） | 需改造 | 正文是「构建顺序」，不是「消融动作」；要抽成 1 页 1 刀的切片 |
| 可观测（metrics/日志/追踪） | 现只有 `/api/health`、`/api/steps`、`/api/errors`、SSE `duration_ms`、`docker compose logs`；后端无 metrics / 追踪，日志只有 `backend/app/security/policy.py:33` 把 sqlglot 调成 ERROR | 没有 | 应用层观测面可当素材；运维级可观测必须新写（见 D3-2） |
| 性能（S8） | 无（README「S8 性能：待做」） | 没有 | 不在 23 页内，仅作 L4 回归页反面案例 |

**合计：19 条 = 可直接用 14 · 需改造 3 · 没有 2。**

## B. 四级课程结构（一句话讲清每级学习动作）

| 级 | 一句话学习动作 | 页数 | 页码 | 每页固定三步 |
|---|---|---|---|---|
| L1 造 | 一件一件把骨架造出来：每页造一个零件，看到它能跑 | 10 | page-00–09 | 猜→动手→你应该看到（现有页原样） |
| L2 换 | 把实验室替身换成真件、接上外部世界：数据/契约/执行器/编排各换一处 | 4 | page-10–13 | 找到替身→换真件→同一判据仍绿 |
| L3 审 | 机器输出不确定，先预注册判据再让错误发生：检索/生成/校验/纠错各审一道 | 4 | page-14–17 | 写下判据→故意打坏→看判据抓没抓住 |
| L4 守 | 制造故障与越权，证明防线有效：账号/策略/取消/可观测/回归各守一道 | 5 | page-18–22 | 拆一道防线→看系统是否变红→还原 |

每级最后一页的「拆一刀」升级为该级**升级考核**：L2 拆编排（P13）、L3 拆检索（P17）、L4 拆只读账号（P22）。升级考核不看「页面做完没有」，只看「拆完能不能说清哪条判据抓到了、哪条没抓到」——这正是把「拆一刀」从页内小实验升格为级间考试。

## C. 23 页目录草案

> 命令前缀约定：`pytest` = `cd backend && .venv/bin/python -m pytest`（其后的 `tests/` 开头路径都相对 `backend/`）；`npm test` = `cd frontend && npm run test`；`make` 均在仓库根执行。L1 十页只填标题，不重设计。

| 页码 | 级 | 页标题 | 教学目标（学生这次做什么动作） | 完成判据（可执行命令 → 期望输出） | 拆一刀（拆什么 → 看什么） | 素材 | 交付物 | 行数/难度 |
|---|---|---|---|---|---|---|---|---|
| page-00 | L1 造 | 开课前准备 | 现有 | 现有 | — | 现有 | ① | 现有 |
| page-01 | L1 造 | 创建 MySQL 容器（空库） | 现有 | 现有 | — | 现有 | ② | 现有 |
| page-02 | L1 造 | 导入 dw.sql：建表灌数据 | 现有 | 现有 | — | 现有 | ③④ | 现有 |
| page-03 | L1 造 | 让服务在 8000 端口回答问题 | 现有 | 现有 | — | 现有 | ⑤ | 现有 |
| page-04 | L1 造 | 加一个能收问题的接口 | 现有 | 现有 | — | 现有 | ⑥ | 现有 |
| page-05 | L1 造 | 从一句话里抽出关键词 | 现有 | 现有 | — | 现有 | ⑦ | 现有 |
| page-06 | L1 造 | 照契约生成那条带 JOIN 的 SQL | 现有 | 现有 | — | 现有 | ⑧ | 现有 |
| page-07 | L1 造 | 把 SQL 真交给 MySQL | 现有 | 现有 | — | 现有 | ⑨ | 现有 |
| page-08 | L1 造 | 让答案一条条推送出来（SSE） | 现有 | 现有 | — | 现有 | ⑩ | 现有 |
| page-09 | L1 造 | 给浏览器一个入口：nginx 反代 + 一个页面 | 现有 | 现有 | — | 现有 | ⑪⑫ | 现有 |
| page-10 | L2 换 | 换成真数据：数据 / 契约 / 元知识三方对账 | 把自己的数据域替换 `fixtures/dw.sql`，同步 `contracts/schema.contract.yaml` 的行数/总额/日期域/值域，再重建 S2 元知识 | `make stage1` → `S1 PASS`；`make stage2` → `S2 PASS`（dry-run→fresh→verify→幂等；需三存储） | 只改 `fixtures/dw.sql` 一条 `order_amount`、不动契约 → `schema_contract --check` 第 1/3 步报数据对账失败；再用 `--write-doc` 看第 3/3 步文档新鲜度 | 半现成 | ③④ | 350 行/中高 |
| page-11 | L2 换 | 换成真契约：内联 CONTRACT → contracts/ 唯一事实源 | 把第 6 页内联的简化契约换掉，让步骤/SSE/错误码/Schema 四份契约同时驱动后端与前端类型；改契约→重新生成→查新鲜度 | `make stage1` → `S1 PASS`；`cd backend && .venv/bin/python -m app.scripts.contracts_gen --check` → `S7 CONTRACT GEN PASS（3 个文件与契约一致）`（离线实测） | 在 `contracts/steps.yaml` 改/加一个节点、不重跑生成 → `contracts_gen --check` 变红并列出 3 个过期生成物；重生成后转绿 | 现成 | ③ | 350 行/中 |
| page-12 | L2 换 | 换成真执行：裸 pymysql → 只读执行器与类型保真 | 把第 7 页 `run_sql` 的 root 直连换成交付物 ⑨ 的 `app/security/executor.py`：策略先行→执行→DECIMAL/DATE 归一化→自动 LIMIT / 超时 | `pytest -q tests/security/test_executor.py tests/agent/test_values.py` → `31 passed`（离线实测） | 关掉 `backend/app/agent/values.py` 的 DECIMAL 归一化 → `rows[0].sales` 从 `41099.5` 变 `"41099.5"`，`test_values` 变红；正好接上第 7 页「数字还是字符串」的猜题 | 现成 | ⑨（+⑤） | 300 行/中高 |
| page-13 | L2 换 | 换成真部署：手动 docker run → compose 六服务 + 一键验收 | 把「docker run 两个容器 + 本机 uvicorn」换成 `compose.yaml`：healthcheck 门控、一次性 init、`service_completed_successfully` 依赖、nginx 关缓冲 | `make docker-up` → `make docker-smoke` → `DOCKER SMOKE PASS`（8 步 + init 幂等；需 Docker 与干净端口，**本次未实跑**，约 20 分钟） | **升级考核**：拆编排——init 的 `service_completed_successfully` 改 `service_started`，或 nginx `proxy_buffering off` 改回 on → `make docker-smoke` 在第 1–3 / 6 步变红；记录并还原 | 现成 | ①②⑪⑫ | 400 行/高 |
| page-14 | L3 审 | 审检索：召回空了的答案，你凭什么信 | 用 20 题检索黄金集设计三条判据（该命中 / 不该出现 / 输出规模上限），判断「召回为空」是失败还是可接受 | `make stage3` → `S3 PASS`（需三存储）；离线 `pytest -q tests/recall` → `18 passed, 23 skipped`（集成 23 条需三存储，实测） | 停掉 elasticsearch（或清 `value_index_rebuild`）重跑 S3 黄金集 → 看哪些题变红；再对 `POST /api/query` 问同一句 → 答案照旧，暴露「线上上下文是契约离线裁剪，检索不在主链路」 | 现成 | ⑦（+③④） | 350 行/中高 |
| page-15 | L3 审 | 审生成：确定性生成器与 LLM 的同一把尺 | 同一组 10 题基线先用确定性生成器跑通、再切 LLM 跑；写清哪些结论可复现、哪些必须多次采样 | `make stage4` → `S4 PASS`；`cd backend && .venv/bin/python -m app.scripts.generate --baseline` → `基线：10/10 通过（拒答 2）`（实测） | 拆掉上下文 8 阶段中的一段（如 `filter_metric`）→ 基线掉几题；LLM 侧按 `eval/FINDINGS.md` 同题 3 次采样看成功率，禁止单次下结论 | 半现成 | ⑧ | 400 行/高 |
| page-16 | L3 审 | 审校验：把错误 SQL 拦在执行之前 | 摊开生成与执行之间那道闸（单语句/只读/表白名单/常量投影/ORDER BY/LIMIT），给 16 个错误码配上「该给谁看」 | `make stage5` → `S5 PASS`；`cd backend && .venv/bin/python -m app.scripts.failures --check` → `S6 PASS`（9 场景 + 16 码，实测） | 在 `backend/app/agent/graph.py` 里 bypass `validate_sql`，用 `eval/correction.jsonl` 的 20 条 `expect_code` 对照 → 看错误码退化成哪一类，或直接执行错 SQL | 现成 | ⑧⑨ | 350 行/中 |
| page-17 | L3 审 | 审纠错：1 次重试能修好什么、修不好什么 | 把纠错当「一次有上限的赌博」审：重试 1 次、必须重新校验、只对可重试错误生效；用多次采样说成功率，不写「已修复」 | `make stage6` → `S6 PASS`；`cd backend && .venv/bin/python -m app.scripts.failures --scenarios` 的 `corrected` 期望 `result`；`pytest -q tests/agent/test_correct.py` → `14 passed`（实测） | **升级考核**：拆检索——把 `scenarios.yaml` 的 `corrected` 场景换成「上下文外的列」（离线，必跑）；有 LLM 时再对照 `generate --live` 的实模型结果 → 重试次数仍是 1，结局变 `SQL_UNKNOWN_COLUMN`，复现 `deliverable/PRD-对照表.md` 第 13 行的「触发=true、纠正成功=false」 | 半现成 | ⑧⑨ | 400 行/高 |
| page-18 | L4 守 | 守账号：只读账号真的写不了吗 | 开通 `dw_reader` 并亲手验证它写不了；把「只读」从提示词搬进数据库权限，做「旧系统能写 / 新系统写不了」两屏对比 | `make stage5-live` → `S5 LIVE PASS`（需 MySQL + `REBUILD_DW_RO_PASSWORD`）；compose 内 `python -m app.scripts.security --verify-ro-account`（= smoke 第 7 步） | 给 `dw_reader` 执行 `GRANT ALL ON dw.*` 后重跑 `--verify-ro-account` → 写操作成功、门禁红；撤销后还原 | 现成 | ⑨ | 300 行/中 |
| page-19 | L4 守 | 守策略：36 条注入全拒、11 条正常零误杀 | 用注入语料审六道 AST 拦截，理解为什么 UNION / 可执行注释要整类拒，而不是逐个修补 | `make stage5` → `S5 PASS`；`cd backend && .venv/bin/python -m app.scripts.security --check` → `36/36 拒绝 + 11/11 放行 + 8/8 基线`（实测）；`--corpus` 打判定表 | 关掉 `contracts/sql.policy.yaml` 的 `forbid_set_operations` → 重跑 `--check`，数漏几条、原因码变成什么 | 现成 | ⑨ | 400 行/中高 |
| page-20 | L4 守 | 守取消：点了停止，系统真的停了吗 | 让取消成为独立状态（不是 done、不是 failure）：服务端真停下、发 `CANCELLED`、界面标「已取消」 | `make stage6-ui`（浏览器：6 类失败 + 取消，需 Chrome/Edge）；离线 `pytest -q tests/agent/test_api.py tests/agent/test_orchestrator.py` → `40 passed`（实测） | 复现旧系统 bug——把取消收尾改成 `done`（或删掉 `backend/app/agent/cancel.py` 的 CANCELLED 事件）→ 用 `fixtures/sse/cancelled.json` 回放，看 SSE / 界面判据在哪一步红 | 现成 | ⑩ | 300 行/中 |
| page-21 | L4 守 | 守可观测：12 条进度 + 14 条夹具能证明什么 | 说清「现在在干什么、错在哪一步」靠哪三样：12 条 progress 事件、`/api/steps` + `/api/errors` 目录、录制回放夹具；划清「应用层观测 ≠ 运维可观测」 | `make stage7` → `S7 PASS`；`cd backend && .venv/bin/python -m app.scripts.record_sse --check` → `S7 SSE RECORD PASS（14 个夹具…）`（实测）；`npm test` → `40 passed`（实测） | 去掉 `backend/app/scripts/record_sse.py` 的两处归一化（`duration_ms`/`request_id`）→ `--check` 变红；说明可观测只能断言稳定量，不能断言每次都变的量 | 半现成 | ⑩⑪⑫ | 350 行/中高 |
| page-22 | L4 守 | 守回归：一套门禁能不能替你值班 | 把 8 步 smoke + stage0–7 门禁当值班网，逐条说清每条防哪类退化，写下「看到什么才算没退化」 | `make docker-smoke` → `DOCKER SMOKE PASS`；`make stage0`…`make stage7` 逐条 PASS；`pytest -q` → `813 passed, 30 skipped`（实测）；`npm test` → `40 passed` | **升级考核**：拆只读账号——给 `dw_reader` `GRANT ALL` 后重跑 `make docker-smoke`，只看第 7 步是否红、其它步是否照绿，判「回归网有没有牙」，再还原 | 现成 | ⑫（全部） | 400 行/中高 |

## D. 复用与空白清单

### D1 能直接复用（10 条）

1. 契约链路：`contracts/` 6 份契约 + `backend/app/schema_contract.py` + `backend/app/scripts/contracts_gen.py`；`--check`、`contracts_gen --check` 均离线绿（实测 `S1 PASS` / 3 个文件一致），可直接当 L2 判据。
2. 安全双件：`backend/app/security/policy.py` + `executor.py` + `contracts/sql.policy.yaml` + `fixtures/injection/sql-injection.yaml`（拒 36 / 放 11）+ `security.py --check`，实测 `36/36 + 11/11 + 8/8`，L4 策略页整页判据现成。
3. 只读账号三件套：`account.py` + `security.py --provision-ro-account/--verify-ro-account/--demo` + `backend/app/scripts/docker_init.py` + `make stage5-live` + smoke 第 7 步，L4 只读页。
4. 失败矩阵：`fixtures/failures/scenarios.yaml`（9 场景）+ `backend/app/scenarios/` + `failures.py --check`，实测 `S6 PASS`（9 场景结局 + 16 码），供 L3 校验/纠错页。
5. 纠错闭环：`backend/app/agent/correct.py` + `contracts/prompts/correct_sql.prompt` + `tests/agent/test_correct.py`（14 passed），供 L3 纠错页。
6. 黄金集：`eval/golden.jsonl`(30) + `backend/tests/recall/golden.yaml`(20) + `backend/tests/generate/baseline.yaml`(10) + `eval/conformance/`（8 gate），供 L3 检索/生成页。
7. 录制回放：`record_sse --check`（实测 14 夹具一致）+ `fixtures/sse/` 14 条 + `frontend/tests/replay-server.mjs` + `make stage7`，供 L4 可观测页。
8. 编排与验收：`compose.yaml` 6 服务 + `scripts/docker-smoke.sh` 8 步 + `scripts/smoke_checks.py` + `make docker-*`，供 L2 部署与 L4 回归页。
9. 口径数据：`manual/completeness/v2/data.json`（12 件 × 24 检验点）+ `manual/map/data.json`（10 页对照）+ `manual/maturity/stages.json`（四阶段），目录编号与页映射现成。
10. S0–S8 正文：`design/book/chapters/10-s0-s4.md`(1006 行) + `20-s5-s8.md`(1223 行)（由 `design/book-editorial/build_book.py` 组装成 `book.html`），可作参考书直引。

### D2 需改造（10 条）

1. `design/book/chapters/`（6 章）：构建顺序叙事 → 每页抽「1 个动作 + 1 条判据 + 1 刀」，改 13 个切片，不重写整章。
2. `manual/page-00.md`–`manual/page-09.md`：正文不动，只加 L1→L4 级标签与四动作导航；`manual/review/walkthrough.md` 指出「判据 4 心智模型句全缺」，属 L1 修订债，不在本草案范围。
3. `fixtures/dw.sql` + `contracts/schema.contract.yaml`：L2 数据页需要第二数据集/换域，并同步行数、总额、日期域；现只有演示集。
4. `backend/app/generate/provider.py` 的 LLM 路径：把「3 次采样 + 成功率」做成可跑脚本；`eval/FINDINGS.md` 给了口径，`eval/live_probe.py`、`eval/probe_correction.py` 可复用。
5. `fixtures/failures/scenarios.yaml`：加「上下文外列」变体（离线复现纠正失败），并给每个场景补一行「该看哪条判据」。
6. `eval/golden.jsonl`(30) 与 `correction.jsonl`(20)：从 CI 断言改成教学判据卡（每页 1–2 条可手抄），并写清容差（precision / 规模上限 / 采样次数）。
7. `scripts/docker-smoke.sh`：8 步是整体验收，教学需拆出可单步执行的 `--only <n>` 与每步一行摘要（现在只能整跑或读源码）。
8. `fixtures/sse/` 14 条：夹具要配「对应哪类界面缺陷」索引；`scripts/stage7-ui.sh` 的 13 条 F1–F13 是现成索引，可直接搬成表。
9. `manual/maturity/stages.json`：口径仍是「每级固定件」（`artifacts_grown` 1–5 / 6–8 / 9–12），与 D44「横切系统 × 接线点」冲突，需重画后 C 表「交付物」列才能对齐。
10. `deliverable/PRD-对照表.md`（27 行，第 13 行）：真实模型「纠正成功=false」必须写进 L3 纠错页当已知现象，不能藏。

### D3 完全没有、必须新写

1. **L2–L4 十三页正文 + 13 张真截图**：13 × 300–450 行 ≈ 4,000–5,500 行；截图沿用 `manual/shots/` 的 `term_render.py`、`web_shots.py` 扩到新页（现有 15 张只覆盖 L1）。
2. **结构化日志 / 指标 / 追踪**（L4 可观测）：后端无 metrics / 追踪，也没有请求日志；最小可行 = 请求 ID + 每步 `duration_ms` + 错误码计数，估 150–250 行 + 1 个端点 + 4–6 个测试。
3. **第二数据集 + 换数手册**（L2 数据页）：新数据域 SQL 约 100–150 行 + 操作步骤约 200 行。
4. **LLM 多次采样 harness**（L3 生成/纠错）：`trials>=3`、成功率、失败分类；复用现有 probe 脚本，估 150–250 行。
5. **「拆一刀」公共工具**：一条命令回滚（`lab save/reset/diff`）。仓库 `lab/` 只有 `app.py`、`index.html`、`default.conf`，无 CLI；没有它，学生改坏 `compose.yaml` / `contracts/` 后无法一键还原，估 150–250 行 shell。
6. **4 个消融脚本**：L2 拆编排、L3 拆检索、L4 拆只读账号、L4 拆归一化——每个 40–80 行 + 期望输出快照。

## E. 风险与待定（8 条）

1. **L3 依赖 LLM 可复现性**：默认确定性生成器离线可复现，但「审机器输出」必须碰 LLM；`eval/FINDINGS.md` §3.1 记录同题 1 次失败、随后 3 次成功——判据必须 `trials>=3` 并写成功率，单次演示会骗人。
2. **L3 纠错页的成功态从未复现**：`deliverable/PRD-对照表.md` 第 13 行是「触发=true、纠正成功=false」；页面目标必须从「学会修复」改成「学会判断一次修复不可信」。
3. **L4 缺故障注入工具与可观测底座**：无 metrics / 日志 / 追踪、无 chaos 工具；「制造故障证明防线有效」目前只能靠 `docker stop`、`GRANT ALL`、改 `compose.yaml`——可行但偏手工，且需要一套「拆前/拆后」基线快照。
4. **拆一刀的隔离与回滚未落地**：D27 要求 worktree 隔离 + 学生只记三条命令，但仓库无 `lab` CLI；不先建工具，L2–L4 实验改坏契约/编排后无法一键还原，有事故风险。
5. **L1 是否按四动作重排**：D44 只定义 L2–L4；L1 仍是 A0–A9 的「造」。建议只在导航加级标签、不改页（否则与 `manual/SPEC.md` 六段模板冲突），待确认。
6. **环境门槛与课时**：L2 部署 / L4 回归需干净 Docker + 三个空闲端口（起草时本机 `make doctor` 实测 9/12，3307/8000/8081 被占）；`make docker-smoke` 首次要构建镜像 + 等健康，时长未实测（估 10–20 分钟），可能撑破 45 分钟/页。
7. **测试数字会漂**：README 写 782 passed / 31 skipped，实测 813 / 30（843 collected）。页内判据应写「0 failed 且总数 ≥ N」，不要写死通过数。
8. **交付物编号口径冲突**：`manual/maturity/stages.json` 仍按「每级长固定件」，D44 要求改成「横切系统 × 接线点」；未重画前，C 表「交付物」列与成熟度图会打架（本草案先用 `completeness/v2/data.json` 的 ①–⑫）。
