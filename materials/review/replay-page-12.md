# 第 12 页独立重放报告（学生视角 · 换真执行器）

> 现场：`/tmp/replay-p12`（复制 fixtures/、contracts/、scripts/lab、backend/app、backend/.venv(软链)、docs/SCHEMA-CONTRACT.md、compose.yaml、lab/；`lab/app.py` 用 `term_render.APP_PAGE_08`（L1 最终版）写出）。临时 MySQL `replay-p12-mysql`（mysql:8.0.46，127.0.0.1:3310）替代页面 `lab-mysql:3307` 并声明；未碰用户 lab-mysql/8000/8081。`lab/db.py` 仅两处 `port=3307`→`3310`，其余逐字；`.env` 的 MYSQL_HOST_PORT=3310（本页代码不读 .env）。
> 重放时点 2026-11-19 16:39–16:52；仓库 `scripts/lab` 为 commit 20eb637（16:42，白名单已含 `lab`）。

**一句话结论**：整条指令链可照抄执行——48 行 `db.py` 能跑、`run_sql`「10 行」对得上、7/7 期望输出逐字命中、拆一刀与 `lab reset` 实测真还原；但「1144735.50 才算得准」与第 10 页清洗结论冲突，拆一刀的 `default_limit`/`max_limit` 说明有歧义，且第 10 页白名单清单已过时——这 3 条先修。

## 环节表

| # | 环节 | 真结果（学生视角） | 问题数 |
|---|---|---|---|
| 准备 | 先灌 `fixtures/dw.sql`＝第 10 页收尾态 | `fact_order=115`，与页 :16「115 行」假设一致；若漏做收尾（库停在第 10 页中段的 410 行 dw-real），第 1 步重灌 dw-real 幂等、不报错 | 0 |
| 1 | `docker exec -i … < fixtures/dw-real.sql` | 0.7s；`fact_order=410`、`dim_date=1461`；pwd 不变 | 0 |
| 2 | 48 行 `lab/db.py` 逐字粘贴 | 48 行、0 tab、`py_compile` OK；`ROOT=parents[1]` 正确读到 `contracts/sql.policy.yaml`；四道闸行为全对 | 1（#3） |
| 3 | app.py 加 `from lab import db`＋`run_sql` 10 行→2 行 | 「共 10 行」在 APP_PAGE_08 与第 11 页版里都唯一对得上；替换后编译、`import lab.app`、`run_sql` 调用均 OK；但页面无验证 | 1（#4） |
| 4 | `backend/.venv/bin/python -m lab.db` | 7 行与「你应该看到」**逐字一致（diff 为空）**；4 次 5.24/5.30/5.30/5.32s（「5 秒多」✓）；stderr 空 | 0 |
| 拆一刀 | save → 改 default_limit → 跑 → reset → 跑 | 只有 `上限` 行变 1461、其余 6 行不变；reset 末行逐字命中；回 1000 行 | 2（#2、#6） |
| 跨页 | 第 10 页 DB 态 / 第 11 页 app.py / 拆一刀替代方案 | DB=115 假设成立、app.py 假设成立、reset 真还原；1144735.50 口径与页 10 冲突；第 10 页白名单清单过时 | 2（#1、#5） |

**四类合计（按主类计）：① 指令/歧义 2（#3、#4）· ② 期望不符 0 · ③ 跨页 2（#1、#5）· ④ 最易卡 2（#2、#6，其中 #2 兼①）**；共 6 条。自己未卡 >1 分钟（预判卡点即 #2、#6）。

## 问题清单

| page-12.md:行 | 原文 | 问题 | 建议 |
|---|---|---|---|
| :7（另 :11） | 「…`dw-real` 的 410 行带分金额才算得准：`1144735.50`」／猜 1「和真实值 `1144735.50` 差多少」 | 与第 10 页结论冲突：第 10 页把 1144735.50 判为不洗不筛的 **naive 值**（含重复 +5197.40、孤儿 +1798、未来单 +1399），「清洗后 1136341.10 才敢报数」。本页把同一值称「算得准/真实值」，学生会以为第 10 页白洗了；本页真正要证的只是 FLOAT→DECIMAL 的位数 | 改成「十进制下 SUM=1144735.50；这仍是第 10 页的 naive 口径（清洗后 1136341.10），本页只证 FLOAT→DECIMAL 不产生尾数，不负责清洗」 |
| :108 | 「…别改下一行 `max_limit`，它也是 1000」 | ①「下一行」实际隔一条注释（:71 注释/:72 default_limit/:73 注释/:74 max_limit）；②「它也是 1000」不构成理由；③`lab/db.py` 只读 `default_limit`、**从未实现 max_limit**，契约 :73「超过这个值的 LIMIT 会被截断」是空承诺；④实测只改 max_limit（1000→100000）自检仍 `1000 行`，与 :108 预期 1461 不符；⑤改完 default_limit(100000)>max_limit(1000)，契约自相矛盾 | :108 明写「本页执行器只读 default_limit；max_limit 是工业版概念、Lab 版未实现」，并删掉「别改下一行」的误导 |
| :31 | 「`TIMEOUT_S = 5    # 闸 3：建连 / 读各 5 秒`」 | 读超时写死 5s，与契约 `timeout.read_timeout_s: 10`（contracts/sql.policy.yaml:80）不一致；:108 的「执行器从契约读上限，不是写死在代码里」只对 LIMIT 成立，超时恰是反例；学生按契约审代码会看到 5/10 两套值 | 从契约读 connect/read 超时；或注释写清「Lab 版 5s 写死（= max_execution_time_ms），read_timeout_s=10 留给工业版」 |
| :71 | 「（不保存…自检不读 `app.py`，看不出来）」 | 页面自认第 3 步无验证：实测 7 行自检完全不 import app.py → 漏保存/漏加 import/漏换 run_sql 三种错全绿；本页也没有 curl 兜底 | 第 4 步后加 `backend/.venv/bin/python -c "import lab.app; print('app ok')"`（不启动服务，能抓 import/语法错） |
| :107–109（涉第 10 页 :24） | 拆一刀改 `contracts/sql.policy.yaml` 而非 `lab/db.py` | 替代方案**能理解、reset 真还原**（契约回 1000、自检回 1000 行 ✓）；但第 10 页 :24 写「快照**也不含 `lab/`**（`lab/app.py` 不进快照）」已过时：当前 `scripts/lab` 白名单含 `lab`，p12-before 快照 102 个文件里就有 `lab/db.py`、`lab/app.py`；实测改 db.py 硬编码 LIMIT 再 reset 也能还原。两页拼起来矛盾，且第 12 页没解释「为何改契约不改代码」 | 第 12 页拆一刀 1 补一句「lab/ 现在也在快照里；改契约是为验证『上限来自契约』（改代码也能过自检，却测不出单源）」；同步修第 10 页 :24 |
| :78 vs :108 | 「（这条整体要等 5 秒多，最后一项是超时，别以为卡住）」（只在第 4 步） | 拆一刀第 2 步再跑同一条自检同样 5.3s（实测 5.24–5.32s），:108 只说「其它几行不变」，未再提醒等待，易再次误判卡死 | :108 末补「（这条同样要等 5 秒）」 |

## 验证通过项（不算问题）

- 48 行代码块逐字可跑：`py_compile` OK、无 tab；`ROOT = Path(__file__).resolve().parents[1]` 在任何 cwd 下都指向仓库根，配置读取路径正确，`Limit/TIMEOUT` 生效。
- 「`def run_sql` 到 `conn.close()` 共 10 行」：APP_PAGE_08 与「第 11 页三处改动后」的 app.py 里都恰好 10 行且唯一；页 :74–75 两行替换块逐字一致。
- 全页无 `cd`；每条命令跑完 `pwd` 都是仓库根（页面 :16 的括号提示成立）。仅提醒：第 4 步若在 `backend/` 里跑会 `ModuleNotFoundError: No module named 'lab'`，「仓库根」提示建议从第 1 步括号上提到页首。
- 期望输出全对：7/7 行 + 拆一刀两条内联预期（1461/1000）逐字命中。唯一环境风险：超时行的「The read operation timed out」来自 SSL 层文案；页面只给 float 尾数加了「随 MySQL 版本略有不同」，建议给这一行也加「认 2013/Lost connection 即可」。
- 跨页实测：第 10 页收尾 = 重灌 `fixtures/dw.sql` → **115 行**（410 是收尾前的中间态，非第 10 页留下的状态）；第 12 页 :16 的 115 假设与第 10 页一致。第 11 页版 app.py 未动 run_sql，与 :71 假设一致。

## 真输出摘录

（现场替代：`lab-mysql`→`replay-p12-mysql`、3307→3310；其余逐字）

```text
$ backend/.venv/bin/python -m lab.db        # 5.30s，exit 0，stderr 空
裸游标  ： (1144735.4994544983,)
float   ： 1144735.4994544983 float
金额行  ： dict {'sales': Decimal('1144735.50')}
差      ： -0.0005455017
上限    ： 1000 行（dim_date 共 1461 行）
拒绝    ： PermissionError 只读执行器只放行 SELECT：UPDATE
超时    ： OperationalError (2013, 'Lost connection to MySQL server during query (The read operation timed out)')
```

```text
# 拆一刀 2：default_limit 1000→100000 后重跑，与拆前 diff 只有一行
-上限    ： 1000 行（dim_date 共 1461 行）
+上限    ： 1461 行（dim_date 共 1461 行）
# 反例：只改 max_limit 1000→100000（default_limit 不动）→ 上限    ： 1000 行（dim_date 共 1461 行）
# 拆一刀 3：scripts/lab reset p12-before --yes 末行（逐字命中）
现在工作区与快照 "p12-before" 完全一致。
```
