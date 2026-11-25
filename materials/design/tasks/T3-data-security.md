# T3 · 数据 / 安全图（opencode）

## 角色与工作树

你是 DSWS 重建项目的设计图集作者之一。工作树：

```text
/home/zhensirong/VM-Share/DSWS-design
```

先读：

1. `design/WBS.md`
2. `design/STYLEGUIDE.md`
3. `design/inventory/facts.md`
4. `contracts/schema.contract.yaml`
5. `fixtures/dw.sql`
6. `backend/app/build/plan.py`、`meta_store.py`、`es_store.py`、`qdrant_store.py`
7. `backend/app/security/policy.py`、`executor.py`、`pipeline.py`
8. `contracts/sql.policy.yaml`、`contracts/errors.yaml`
9. `backend/app/agent/errors.py`、`backend/app/agent/correct.py`

## 目标

产出 11 张数据与安全图，回答「数据长什么样、知识怎么落三存储、信任边界在哪、失败怎么分类」。

## 必须产出

目录：`design/diagrams/03-data/`（14–19）与 `design/diagrams/04-security/`（20–24）。

| 编号 | 文件 | 类型 | 内容要求 |
|---|---|---|---|
| 14 | `03-data/14-er-diagram.mmd` | erDiagram | 5 表、主键、逻辑外键、粒度注释；标出 `fact_order` 一行一单 |
| 15 | `03-data/15-contract-model.mmd` | classDiagram 或 flowchart | 契约对象：Table / Column / Metric / ValueDomain / ColumnMetric；字段与关系 |
| 16 | `03-data/16-three-store-layout.mmd` | flowchart | 一份契约如何翻译成 Meta 行、ES 文档、Qdrant 点；用 `region_name` 与 `order_amount` 两个真实例子 |
| 17 | `03-data/17-s2-lineage.mmd` | flowchart LR | `schema.contract.yaml` + `fixtures/dw.sql` → BuildPlan → 三存储 + manifest；标出 5/24/6/9/76/98/22 |
| 18 | `03-data/18-meta-schema.mmd` | erDiagram | `table_info` / `column_info` / `metric_info` / `column_metric` / `build_manifest` 的字段与主键 |
| 19 | `03-data/19-value-domain-decision.mmd` | flowchart TD | 值域分类：enum → ES 文档；range → 不写 ES；`sync_values` 的作用 |
| 20 | `04-security/20-trust-boundary.mmd` | flowchart | 浏览器 / 前端 / FastAPI / LLM / 三存储 / 旧系统 的信任边界与数据流 |
| 21 | `04-security/21-defense-in-depth.mmd` | flowchart | 五层：契约白名单 → 静态 guard → 策略判定 → 只读执行器 → 错误通道/审计 |
| 22 | `04-security/22-sql-policy-flow.mmd` | flowchart TD | 单语句 → 只读 → 表白名单 → 列白名单 → 常量投影 → ORDER BY / LIMIT → 放行/拒绝 |
| 23 | `04-security/23-readonly-grants.mmd` | flowchart | `dw_reader` 的 GRANT：只读、无写、无 DDL；应用账号与只读账号分离 |
| 24 | `04-security/24-error-taxonomy.mmd` | flowchart | 16 个错误码按 `failure` / `empty` / `cancelled` 分类，标出 `retryable` |

每张图配同名 `.md` 说明，按 `STYLEGUIDE.md` §7 模板。安全图必须写「攻击者能做什么、被哪一层挡住、证据在哪」。

### 目录草稿

`design/inventory/catalog-data-security.md`：14–24 的编号、标题、问题、源文件、SVG、证据、状态。

### 交接

`design/inventory/handoff-T3.md`：产出清单、渲染命令、未决问题、读过的文件。

## 约束

- 只写 `design/inventory/`、`design/diagrams/03-data/`、`design/diagrams/04-security/`。
- 不要改源码、契约、文档。
- 表名、列名、错误码必须逐字准确；不要编造 `city`、`price` 之类不存在的列。
- 16 个错误码必须全部出现，且 class 与 `contracts/errors.yaml` 一致。
- 计数与 `facts.md` 一致。

## 验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/03-data/*.svg diagrams/04-security/*.svg
```

11 个 SVG 全部生成；错误码图覆盖 16/16；ER 图覆盖 5/5 表。
