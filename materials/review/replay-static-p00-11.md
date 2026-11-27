# p00–p11 静态/离线独立重放报告（学生视角 · 可复现/跟随性测试）

> 重放者：独立重放者（静态/离线范围）；日期 2026-11-27；仓库 HEAD `34eb9fb`（页面文件 2026-11-26 15:08）。
> 范围：`tutorial/page-00.md` … `page-11.md` 共 12 页，只测静态/离线部分；不起 docker 栈、不跑拆一刀消融（由后续栈测代理做）。
> 模板依据 [REPLAY-TEMPLATE](REPLAY-TEMPLATE.md)；断层五类口径见 `GLOSSARY.md`「断层」与 `materials/docs/verify-line.md`。

## 0. 总闸：make verify（T0/T1，全书只跑一次，最先跑）

```text
$ make verify          # python3 toolbox/scripts/verify.py；uv 口径 --frozen（uv.lock 前后无 diff）
...
页：24/24 通过；块：49（offline 14 / manual 35）
静态页：16（coverage: static，只做 T0 路径/符号检查，无 offline 块）
执行：14/14 个 offline 块通过
T1 PASS（耗时 27.17s）
```

判定：**通过**。p00–p09、p11 均为 `coverage: static`（页面不挂 verify 注解，T1 不执行）；p00–p11 范围内唯一 T1 真跑块是 page-10 的 `p10-schema-contract`，通过。

## 范围声明

- 真跑：`make install` / `make doctor`（p00）；p10 的 offline 块 `app.schema_contract --check`（按契约原命令）；p03–p06 全部代码贴片 + uvicorn + curl（在 `/tmp` 沙箱镜像「仓库根」布局执行，避免覆盖仓库里 gitignored 的 `lab/` 学生产物）；p07 空关键词 500 形态；p10 第 5 步/拆一刀 1/3 字段 FAIL 计数（在 `/tmp` 副本 `system/contracts` 上改，仓库原件未动）；p11 贴片原样执行 + 修法验证。隔离手段 = 临时目录（已删）。
- 方式：单 shell 从仓库根执行；不整段连续跑（p01–p02、p07–p10 多数命令要 docker 栈）；无 `exit 127`。
- 静态核对：dw.sql / dw-real.sql / dw-real.expected.json / dw-real.checks.sql 全量数字复算（Python 解析 INSERT）；schema.contract.yaml / steps.yaml / sse.schema.json / pyproject.toml / Makefile / doctor.sh / toolbox/scripts/lab / schema_contract.py 源码核对；30 张页面引用图片存在性；跨页前置逐页推演。不整栈重跑的原因：本阶段红线「不起 docker 栈」。
- 替换：p03–p06 沙箱目录 `/tmp/replay-lab` 代替仓库根（`lab/app.py` 落在沙箱，`python` 用绝对路径 `system/backend/.venv/bin/python`）；p11 沙箱 `/tmp/replay-p11`（`system`、`materials` 软链回真仓库，镜像「仓库根+lab/」布局）；p10 变体实验在 `/tmp/replay-rc` 副本上做，均未落仓库。端口未换（8000 实测空闲）。
- 时点与版本：2026-11-27 上午；HEAD `34eb9fb251efc31fbeabd0004925330f7a61789b`。
- 未做与原因：所有 docker 命令（p01/p02/p07/p08/p09/p10 的 manual 块与拆一刀）→ **待栈测**；`toolbox/scripts/lab save/reset`（p10/p11）→ 有副作用（写 `.lab/`），只读红线跳过；p00「自己改一下」占 8000 的变体 → 只验了失败行格式（本机 3307 已被占，见环境备注）；截图画面新旧（④类画面级）→ 无看图能力，只验存在性；pytest 块 → p00–p11 无（pytest 从 p14 起），本范围无需 `-p no:cacheprovider`。

**环境备注（非断层）**：本机 3307 被用户自己的 `shopkeeper-rebuild-mysql-1` 栈占用（`127.0.0.1:3307->3306`），故 `make doctor` 全绿行 `12/12 通过` 与「端口 ✓ 3307」未能观察；观察到的是页面「卡住了看这里」描述的失败形态（`✗ 3307 被占用：ss -tlnp | grep :3307 找到 PID，再 kill -15 <PID>` + `11/12 通过（1 项没过）`）。该栈未触碰。

## 逐页重放（期望 / 实测 / 判定）

### page-00 · 开课前准备

| 环节（page-00.md:行） | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 第 1 条 `make install`（:56） | uv sync --frozen + npm ci；npm「added 118 packages, and audited 125 packages」（数字随环境） | 首跑 npm `added 118 packages, and audited 125 packages in 26s`；uv 62 包 | 通过 |
| 第 2 条 `make doctor`（:62） | 4 行：工具 6 项（docker/daemon/uv/node/make/curl）/ 依赖 3 项 / 端口 3307·8000·8081 / 末行判定 | 行结构、工具 6 项、依赖 3 项逐项一致；端口行因 3307 被占用出 `✗ 3307` + 修法行 + `11/12 通过（1 项没过）`，make 报 Error 1 | 通过（结构/文案/失败形态全对；12/12 全绿行受环境占用遮蔽） |
| 「你应该看到」`Checked 62 packages`（:103） | 复跑 make install 变一行 `Checked 62 packages in 0.55ms` 这种 | `Checked 62 packages in 0.66ms` | 通过 |
| 自己改一下：占 8000 → `✗ 8000`、`11/12 通过（1 项没过）`（:130-138） | 失败形态两行 | 失败行格式已由 3307 案例验证；8000 变体未叠加复跑（会变 10/12） | 部分验证（格式通过） |
| 「重来一遍」docker/rm（:152-158） | 容器干净/端口全空 | docker 命令 | 待栈测 |
| 静态：Makefile `install:/doctor:/doctor-v:`、doctor.sh 端口循环与判定 printf、`.env.example`、`system/fixtures/dw.sql`、`toolbox/scripts/lab`、`make docker-env` 回退 `uv python find` | 契约符号全命中 | 全部命中（find-python.sh:57 `uv python find`） | 通过 |

### page-01 · 创建 MySQL 容器（空库）

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 第 1 条 docker run（:28-35） | 起 `lab-mysql`，镜像从 `.env.example` 的 `MYSQL_IMAGE` 读 | docker 命令 | 待栈测 |
| 第 2 条 until logs（:56） | 等 `port: 3306` | docker 命令 | 待栈测 |
| 第 3 条 SELECT VERSION/SHOW DATABASES（:64） | 5 行：8.0.x + 4 系统库，无 `dw` | docker 命令 | 待栈测 |
| 静态：`.env.example` `MYSQL_IMAGE=mysql:8.0`；dw.sql `CREATE DATABASE IF NOT EXISTS dw`(:8)、`GRANT ALL PRIVILEGES ON dw.* TO 'didilili'@'%'`(:9) | 存在且命中 | 命中；页面 :43-45 的 GRANT 解释与源码一致 | 通过 |
| 自己改：`ERROR 1049 (42000): Unknown database 'dw'`（:100） | 报错文案 | docker 命令 | 待栈测 |

### page-02 · 导入 dw.sql

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 第 1 条 `docker exec -i … < system/fixtures/dw.sql`（:24） | 静默导入 | docker 命令 | 待栈测 |
| 第 2 条 SHOW TABLES → 5 行按字母序（:32） | dim_customer/dim_date/dim_product/dim_region/fact_order | dw.sql 5 个 CREATE TABLE，表名与序一致 | 通过（静态） |
| 第 3 条 115 / 19 / 前 3 单（:40-49） | `115`、`19`、`ORD20250102002 北京市 华北 899`、`ORD20250109001 … 599`、`ORD20250114001 … 75` | 解析 dw.sql：fact_order 115 行；R004(华北) 19 单；前 3 单订单号/省市/金额逐字一致（899/599/75） | 通过（静态） |
| 对账「5 张表合计 246 行（dim_date 90 等）」（:76） | 246 / 90 | 6+20+15+90+115=246；dim_date=90 | 通过 |
| 自己改 #2 华南 26 单 / 70202 / R001 广东省（:86） | 26 / 70202 | R001 26 单，SUM=70202.0，dim_region `('R001','广东省','华南')` | 通过 |
| 自己改 #3 重灌不翻倍（:87） | `DROP TABLE IF EXISTS` 先删旧表 | dw.sql 含 5 处 `DROP TABLE IF EXISTS` | 通过 |

### page-03 · 最小 HTTP 服务

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 贴片（:30-38）+ uvicorn（:44）+ curl（:54） | `{"ok":true}`；日志 `Uvicorn running on http://127.0.0.1:8000 …` | 沙箱真跑：curl 输出 `{"ok":true}` 逐字；日志 4 行与 :62-65 逐字一致，访问日志 `INFO: 127.0.0.1:<临时端口> - "GET /health HTTP/1.1" 200 OK` 与 :68 一致 | 通过 |
| 对账/卡住的报错文案（:91-96） | Connection refused / ModuleNotFoundError 等 | 未逐一复现（静态合理） | 未验（低风险） |
| 自己改 /healthz 404（:102-104） | `{"detail":"Not Found"}` | 未复跑（FastAPI 标准行为） | 未验（低风险） |

### page-04 · /api/query 硬编码返回

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 贴片（:26-50）+ 两条 curl（:61-62） | 两行一字不差 `{"question":"华北销售额","keywords":[],"sql":null,"rows":[]}` | 沙箱真跑 ×2，输出与 :68-69 逐字一致 | 通过 |

### page-05 · 抽关键词

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 贴片（:29-65）+ 两条 curl（:76-77） | `["华北","销售额"]` / `["华东","销售额"]` | 沙箱真跑，两行与 :83-84 逐字一致 | 通过 |
| 自己改 #2 METRICS 对调（:102-103） | `["华北","订单量","销售额"]` | 代码扫描序推导一致（未复跑） | 通过（推导） |

### page-06 · 契约字典 + build_sql

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 24 行贴片分两步（:30-53；20 行+4 行计数） | 共 24 行 / 前 20 行 / 剩 4 行 | 计数逐行核对：24/20/4 全对 | 通过 |
| `python -m lab.app`（:67） | 5 行 SQL（:77-81） | 沙箱真跑（p5 底稿+插入），5 行逐字一致，exit 0 | 通过 |
| 对账「CONTRACT 是 schema.contract.yaml 的浓缩版」（:70-72） | 三处对应属实 | 契约核对：外键两列、`SUM(fact_order.order_amount)`、`region_name` 取值 `华北` 均在契约中 | 通过 |

### page-07 · 真执行 SQL

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| run_sql/query 贴片（:40-68）+ curl（:80） | `rows:[{"region_name":"华北","sales":41099.5}]` | 需 MySQL | 待栈测 |
| 数据红线 41099.5（:86-100） | 华北 19 单 SUM = 41099.5 | 解析 dw.sql 复算 = 41099.5 ✓；JSON 中 sql 字符串 `\n` 转义形态与贴片构造一致 | 通过（静态） |
| 对账：空关键词 500（:102-107） | 体 `Internal Server Error`；日志 500 行；traceback 末行 `RuntimeError: coroutine raised StopIteration` | 沙箱真跑，三者逐字命中 | 通过 |
| 自己改 107373.0 / 26（:122-126） | 华东 SUM=107373.0；华南 COUNT=26 | 复算 R002+R005=107373.0；R001 去重单数 26 | 通过（静态） |

### page-08 · SSE

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| STEPS 12 名（:40-42） | 与 `system/contracts/steps.yaml` 一致 | 12 个 id 逐字一致 | 通过 |
| curl -sN 流式（:68） | 12 条 progress + 1 条 result，约 1.8s | 需 MySQL（result 要 run_sql） | 待栈测 |
| :104「真实契约里 result 还带 columns」 | 与 sse.schema.json 对照 | 契约还要求 `data` 必含 `columns`+`rows` 且 rows 是「数组的数组」；页面事件的 rows 是对象数组且无 columns，差异披露不全 | **断层 ②（should）** |
| 自己改 0.5s→约 6 秒 / grep -c=12（:110-115） | 6.02s / 12 | 12×0.5=6 ✓ 推导一致 | 通过（推导） |

### page-09 · nginx 反代 + 页面

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| default.conf 8 行（:45-53）/ index.html 17 行（:61-77）/ JS 9 行（:134） | 8 / 17 / 9 | 计数逐行核对全对 | 通过 |
| docker run lab-nginx（:85-89）+ 浏览器（:102） | 8081 出 41099.5 | docker/浏览器 | 待栈测 |
| 静态：`.env.example` `NGINX_IMAGE=nginx:1.27-alpine`；`system/docker/nginx.conf` `proxy_buffering off` | 命中 | 命中（契约符号核对） | 通过 |
| 自己改 华东销售额 → 107373（:149-151） | 页面显示 107373 | 复算 107373.0，JS 数字显示去 .0 ✓ | 通过（静态） |

### page-10 · 换真数据

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 第 1 步 `lab save p10-before`（:27，manual） | 拍快照 | 有副作用（写 `.lab/`），只读红线跳过 | 跳过（待人工） |
| 第 2/3 步 docker exec 灌 dw-real / checks（:38,:49，manual） | 410 行、对账关键行 | docker 命令 | 待栈测 |
| 第 4 步 offline 块（:55） | `PASS: 5 张表 / 24 列 / 115 行 / GMV=279159.5 / 销量=622`、`S1 PASS`、exit 0 | 真跑（契约命令原样）：两行逐字命中，exit 0；另见「2/3 负向夹具 PASS（8 个代码）」「3/3 文档新鲜度 PASS」 | 通过 |
| 第 5 步 expected_fact_rows→410（:59-61） | `[DATASET_ROW_COUNT] …契约声明 410 行，fact_order 实际 115 行` + `FAIL: 1` | /tmp 副本复现，两行逐字命中，exit 1 | 通过 |
| 「3 个字段一起改得到 FAIL: 3」（:61） | FAIL: 3 | 副本复现：ROW_COUNT+DATE_RANGE+TOTAL_AMOUNT 三条 + `FAIL: 3 个契约问题` | 通过 |
| 拆一刀 1（:131-136） | `METRIC_VALUE_MISMATCH … 公式实际值 279159.5 ≠ 契约期望 1` + `FAIL: 2` | 副本复现逐字命中 | 通过 |
| 对账数字（:84-125） | D1=2、D2=2/1、D3=2(华东区,华北区)、D4=1(+1798.00)、D5=1(+1399.00)、D6=1/1、D7=191、410→405、naive 1144735.50、clean 1136341.10、差 8394.40=5197.40+1798.00+1399.00、wrong_join 496/1359154.30、真数据华北 35 行/61890.00 | 解析 dw-real.sql + expected.json + checks.sql 全量复算：**全部逐项命中**（405/1136341.10/496/1359154.30 等精确一致） | 通过 |
| 白名单/命名规则/同名拒绝/reset 末行（:29,:33,:138） | 7 项白名单、字母数字开头、≤64 字符、同名拒绝、`现在工作区与快照 "…" 完全一致。` | toolbox/scripts/lab:31 WHITELIST 逐项一致；:225-237 命名规则一致；:325 同名拒绝；:731 末行逐字一致 | 通过 |
| 拆一刀 3/收尾（:140-147） | DB 不随 reset 还原；重灌 dw.sql | docker 命令 | 待栈测 |

### page-11 · 换真契约

| 环节 | 期望 | 实测 | 判定 |
|:--|:--|:--|:--:|
| 第 2 步贴片加载契约（:29-31） | `python -m lab.app` 打出 5 行 SQL | **照页面原样拼好真跑：`FileNotFoundError: …/contracts/schema.contract.yaml`，exit 1**。`ROOT=parents[1]` 即仓库根，而仓库根 `contracts/` 软链已在 d19565c「移除全部兼容软链」中删除，契约实际在 `system/contracts/` | **断层 ①（blocker）** |
| 修法验证 | `ROOT / "system" / "contracts"` | 副本验证：可读，GMV `formula=SUM(fact_order.order_amount)`、`values=[华南,华东,西南,华北,华中]`（与拆一刀引文一致） | 修法成立 |
| `_region_values`/`_metric_formula`（:34-44） | 按契约结构取值 | 契约结构核对：`tables[].name/columns[].name/value_domain.values`、`metrics[].name/aliases/formula` 全部存在；GMV `aliases: [销售额, 成交总额, 订单总额]` 与 :93 一致 | 通过 |
| 第二条 `(cd system/backend && … --check)`（:62） | S1 PASS + 负向夹具 8 个代码 | 真跑输出与 :81-84 一致（115 行/GMV/销量全命中）；「在仓库根跑 `-m app.schema_contract` 报 No module named 'app'」逐字复现 | 通过 |
| 拆一刀 2 traceback（:109-114） | `StopIteration`，行号随文件 | StopIteration 形态与代码一致（行号页面已免责） | 通过（推导） |

## 断层清单（五类）

| # | 页码 | 类别 | 现象 | 期望 | 建议修法 | severity |
|:--|:--|:--:|:--|:--|:--|:--:|
| 1 | page-11.md:29-31 | ① | 贴片 `(ROOT / "contracts" / "schema.contract.yaml")` 指向仓库根 `contracts/`，该兼容软链已在 d19565c 删除（根因属 ③：布局重构改了路径、页面没跟改）。照页面拼好 `lab/app.py` 后 `python -m lab.app` 实测 `FileNotFoundError: …/contracts/schema.contract.yaml`、退出码 1，本页主线「5 行 SQL + 拆一刀」全断 | 读到 `system/contracts/schema.contract.yaml`，打出与第 6 页逐字一致的 5 行 SQL | 贴片改为 `(ROOT / "system" / "contracts" / "schema.contract.yaml")`（已实测可读）；同 commit 核对 `images/page-11-contract.png` 是否需重拍 | **blocker** |
| 2 | page-08.md:83,104 | ② | 页面 result 事件 `data` 只带 `rows`（对象数组），而 `system/contracts/sse.schema.json` 要求 `data` 必含 `columns`+`rows` 且 rows 是「数组的数组」；页面只披露「真实契约里 result 还带 columns」，学生照契约核对会发现形状对不上 | 页面明确写出与契约的全部差异（rows 形状也不同，本页事件不完全符合 sse.schema.json） | :104 补一句：「真实契约里 `result` 的 `data` 必须同时有 `columns` 和 `rows`，且 `rows` 是与 `columns` 对齐的数组的数组；这一页只发对象数组的 `rows`，够第 9 页用但不合 `sse.schema.json`」 | should |

其余 10 页未见断层；p00 12/12 全绿行受环境 3307 占用遮蔽属环境备注（见「范围声明」），不算断层。跨页前置（⑤类）：p01→p02（容器先建）、p03→p04…p08（逐页 lab/app.py 与服务）、p09（p08 服务 + `--host 0.0.0.0`）、p10（p01/p02 栈）、p11（L1=p08 底稿）在各页「前置」均已显式声明，且 p10 拆一刀 2 未 reset 会红 p11 的 `--check` 也被 p10:142 明示——未见 ⑤ 断层。证据（④类）：p00–p11 全部 30 张引用图片存在；画面新旧无法静态判定（未做）。

## 真输出摘录

```text
$ make doctor                       # p00（3307 被外部栈占用，非断层）
工具  ✓ docker 29.1.3  ✓ daemon  ✓ uv 0.13.1  ✓ node v24.21.0  ✓ make 4.3  ✓ curl 8.5.0
依赖  ✓ Python 3.14.8（要求 ≥3.12）  ✓ uv 62 个包全兼容  ✓ npm 依赖无缺失
端口  ✗ 3307  ✓ 8000  ✓ 8081
  ✗ 3307 被占用：ss -tlnp | grep :3307 找到 PID，再 kill -15 <PID>
11/12 通过（1 项没过）

$ (cd system/backend && .venv/bin/python -m app.schema_contract --check)   # p10 offline 块
PASS: 5 张表 / 24 列 / 115 行 / GMV=279159.5 / 销量=622
...
S1 PASS

$ curl -s http://127.0.0.1:8000/health        # p03 沙箱
{"ok":true}

$ system/backend/.venv/bin/python -m lab.app  # p06 沙箱（与页面 5 行逐字一致）
SELECT dim_region.region_name, SUM(fact_order.order_amount) AS sales
FROM fact_order
JOIN dim_region ON fact_order.region_id = dim_region.region_id
WHERE dim_region.region_name = '华北'
GROUP BY dim_region.region_name

$ system/backend/.venv/bin/python -m lab.app  # p11 原样贴片（blocker 复现）
FileNotFoundError: [Errno 2] No such file or directory: '.../contracts/schema.contract.yaml'
exit=1
```

（机器相关：版本号、耗时、临时端口随环境变。）

## 清理确认

- [x] 容器 / compose 项目：未启动（docker 全部跳过；用户的 `shopkeeper-rebuild-*` 等栈未触碰）
- [x] 临时目录：`/tmp/replay-lab`、`/tmp/replay-p11`、`/tmp/replay-rc`、`/tmp/replay-contract` 已删
- [x] `system/backend/uv.lock`：前后 sha 一致（`git diff` 空；全程 `uv sync --frozen` / 契约原命令）
- [x] `.lab/`：未新建（p10/p11 的 lab save 跳过，未碰并发会话快照）
- [x] 用户栈：`shopkeeper-rebuild-mysql-1` 等容器与端口前后对比不变（3307 仍由其占用）
- [x] 只新增本报告；`tutorial/page-*.md` 未改（`git status` 仅原有 3 个 untracked 用户文件 + 本报告）

## 8 类必查清单

- [x] **uv.lock 改写**：全程 `--frozen`，`git diff system/backend/uv.lock` 为空 → 结论：通过（diff 空）。
- [x] **cwd 子 shell**：p10/p11 的 `(cd system/backend && …)` 子 shell 原样执行，`pwd` 始终回仓库根 → 结论：通过（复跑后仍在仓库根）。
- [x] **管道退出码**：判据均直接取退出码/全文输出（`make doctor` 看 make Error、`--check` 看 exit 与 FAIL 行），未用 `| tail` 吞码 → 结论：通过（p10 块 exit=0、变体 exit=1 均直读）。
- [x] **端口与 `.env`**：curl 端口 8000 与页面/doctor 口径一致；`.env` 未建（p01 命令读的是 `.env.example`，页面 :45 已声明）→ 结论：通过。
- [x] **lab 快照边界（DB、uv.lock）**：p10:29-31 已明示「不含数据库」；本次未动快照 → 结论：通过（页面披露与 lab 脚本 WHITELIST 一致）。
- [x] **重录假绿**：未重录任何夹具；`--check` 均对既有 dw.sql 跑 → 结论：不适用（无重录动作）。
- [x] **精确行号与同名代码**：页面无 `文件:行号` 式引用；p11 traceback 行号页面已免责（:107「行号以你的文件为准」）→ 结论：通过。
- [x] **跨页前置回绿**：未跑任何拆一刀（本阶段红线），p10/p11 的契约改动仅在 /tmp 副本上做，仓库契约原件未动 → 结论：通过（原件前后一致）。
