# 第 11 页 · 学生视角独立重放报告
- 现场：`/tmp/replay-p11`（复制 lab/、contracts/、scripts/lab、fixtures/、backend/app，软链 backend/.venv；未起服务、未碰容器/端口）。学生起始文件 = `manual/shots/term_render.py` 的 `APP_PAGE_08`，先确认出 5 行 SQL 再按 page-11.md 逐字操作；只读本页依赖的第 6/8 页做跨页核对，未读任何 agent 报告或实现笔记。
- **一句话结论：能独立跟做。** 三步改动照抄可运行；两条验收命令的关键行、拆一刀的报错类型/退出码/还原/末行全部对得上；但有 1 处会真卡住学生的 cwd 陷阱和 1 处第 8 页交接事实错误，建议先修。

## 环节核对
| 环节 | 可执行? | 期望一致? | 问题数 |
|---|---|---|---|
| 前置（术语） | 是 | 否（`L1` 未定义） | 1 |
| 第 1 步 加两行 import | 是 | 否（"import time 是最后一行"不成立，但照做可跑） | 1 |
| 第 2 步 删 CONTRACT（9 行）+ 换加载/函数 | 是 | 是（确为 9 行；无多空行、无缩进错） | 0 |
| 第 3 步 只换 build_sql 前 3 行 | 是 | 是（后 4 行未动，输出逐字一致） | 0 |
| 验收 1 `backend/.venv/bin/python -m lab.app` | 是 | 是（5 行逐字，见附） | 0 |
| 验收 2 `cd backend && .venv/bin/python -m app.schema_contract --check` | 是 | 关键行是；首行与措辞有差 | 2 |
| 拆一刀 save→删华北→报错→reset | 是（需在仓库根） | StopIteration/exit 1/还原/末行都对；traceback 是删节版、命名规则不全 | 3 |
| 未保存陷阱 | 是 | 是（第 13 行明说；实测旧码输出与改后完全相同） | 0 |
| 对账/结语 | — | 否（REGIONS/METRICS 仍硬编码） | 1 |

## 问题清单

| page-11.md:行 | 原文摘录 | 问题 | 建议改法 |
|---|---|---|---|
| :2 | 「本页接 L1 留下的 lab/app.py」 | `L1` 全书仅此一处、没有定义，只读这本书的学生不知道指什么 | 改成「第 8 页留下的」 |
| :15 | 「`import time` 是第 8 页 import 区的最后一行」 | 与实际不符：`import time` 后还有空行 + `from fastapi import FastAPI`、`from fastapi.responses import StreamingResponse`、`from pydantic import BaseModel` 三行；"在 import time 下面插"仍可运行，但学生会犹豫插哪（实测插到最后一行也跑得通、行号仍 48） | 删掉断言，改「插在 `import time` 与下面空行之间」 |
| :45 | 「第二条的 `cd backend` 不能省，不然报 `No module named 'app'`」 | 只有保留 `backend/.venv/bin/python` 从根跑才报 ModuleNotFoundError；真省掉 cd 敲 `.venv/bin/python` 报的是 `No such file or directory` | 改「必须先 `cd backend`；在仓库根跑 `-m app.*` 会 `No module named 'app'`」 |
| :47-50、:79、:80、:88 | 命令块以 `cd backend && ...` 结束；拆一刀三条命令都写成仓库根相对路径 | **最卡人**：跑完第二条 shell 停在 backend/，随后 `scripts/lab save`、`backend/.venv/bin/python -m lab.app`、`scripts/lab reset` 全报 `No such file or directory`（exit 127），页面没让 `cd ..` | 命令块后加「跑完 `cd ..` 回仓库根」；或第二条改 `(cd backend && .venv/bin/python -m app.schema_contract --check)` |
| :64-68 | 期望输出从 `PASS: 5 张表 ...` 开始 | 真实 `--check` 首行是 `== 1/3 契约 ↔ DDL/数据 ==`，PASS 在第二行；2/3 的 PASS 行实际是 `PASS: 旧系统 14 条问题 / 8 个代码（预期红）`。关键行 PASS / S1 PASS 一致 | 首行补 `== 1/3 契约 ↔ DDL/数据 ==`，或标「截自第 2 行」 |
| :83-87 | 「报错原文（路径用 ... 略去，行号以你的文件为准）」 | 不是原文：真实 traceback 多 `<frozen runpy>` 两帧和 `File ".../app.py", line 107, in <module>` 帧（`print(...)` 下还有 `~~~~~^^^^` 指示行）；但 `line 48, in build_sql`、`StopIteration`、exit 1 全中 | 标「已略去 runpy/`__main__` 外层帧与 ^ 指示行」 |
| :79 | 「名字只能用字母、数字、点、下划线、短横线」 | 漏了「必须以字母或数字开头」；`p11-before` 不受影响 | 补「且以字母或数字开头」 |
| :75 | 「指标公式、地区全集都不再写死在代码里」 | 与交付代码不符：`REGIONS`/`METRICS` 仍硬编码在 lab/app.py 14-15 行，`extract_keywords` 仍用它；只有 `build_sql` 的公式与地区取值来自契约 | 限定为「build_sql 的指标公式和地区取值不再写死」 |

最容易卡住的点：只有上表 :47-50 那条（我实测三条命令全 127，新手会停 >1 分钟）；其余（import 位置、traceback 多帧、--check 首行）实测都 <1 分钟。

## 附：关键证据

最终 `lab/app.py` 关键片段（完整 107 行；`region = next(...)` 恰在第 48 行，与页面 traceback 行号一致）：

```python
import json
import pymysql
import time
import yaml
from pathlib import Path
...
ROOT = Path(__file__).resolve().parents[1]
CONTRACT = yaml.safe_load((ROOT / "contracts" / "schema.contract.yaml")
                          .read_text(encoding="utf-8"))
...
def build_sql(keywords: list[str]) -> str:
    region = next(k for k in keywords if k in _region_values())
    metric = next(k for k in keywords if _metric_formula(k))
    sql = f"""SELECT dim_region.region_name, {_metric_formula(metric)} AS sales
...（FROM/JOIN/WHERE/GROUP BY 4 行原样，见验收 1；末行 return sql）
```
验收 1 真实输出（与第 6 页/第 11 页逐字一致，diff 为空，exit 0）：

```
SELECT dim_region.region_name, SUM(fact_order.order_amount) AS sales
FROM fact_order
JOIN dim_region ON fact_order.region_id = dim_region.region_id
WHERE dim_region.region_name = '华北'
GROUP BY dim_region.region_name
```
验收 2 真实输出（节选，exit 0）：`== 1/3 契约 ↔ DDL/数据 ==` / `PASS: 5 张表 / 24 列 / 115 行 / GMV=279159.5 / 销量=622` / `== 2/3 负向夹具（必须红） ==` / `PASS: 旧系统 14 条问题 / 8 个代码（预期红）`（8 个代码逐条列出）/ `== 3/3 文档新鲜度 ==` / `PASS: docs/SCHEMA-CONTRACT.md 与契约一致` / `S1 PASS`。

拆一刀真实报错（删 `values` 里的 `华北` 后，exit 1）：

```
Traceback (most recent call last):
  File "<frozen runpy>", line 203, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/tmp/replay-p11/lab/app.py", line 107, in <module>
    print(build_sql(extract_keywords("华北销售额")))
          ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/tmp/replay-p11/lab/app.py", line 48, in build_sql
    region = next(k for k in keywords if k in _region_values())
StopIteration
```

还原：`scripts/lab reset p11-before --yes` exit 0，末行 `现在工作区与快照 "p11-before" 完全一致。`（覆盖 1 个文件）；再跑 5 行 SQL 回来、`WHERE ... '华北'` 稳在第 4 行。
未保存陷阱：`APP_PAGE_08` 原文件与改后文件输出 diff 为空——旧代码确实打同样 5 行；第 13 行已明说"输出一样看不出没保存"，并指到「拆一刀」验证，讲清楚了。本报告未修改 manual/page-11.md。
