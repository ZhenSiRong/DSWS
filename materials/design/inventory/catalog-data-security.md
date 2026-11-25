# 数据 / 安全图目录（14–24）

> 基线：`eea5e75`（2026-10-29）。所有 SVG 由 `design/scripts/render_all.py` 从同名 `.mmd` 生成。
> 计数以 `design/inventory/facts.md` 为准；表名、列名、错误码逐字取自契约。

| 编号 | 标题 | 回答的问题 | 源文件 | SVG | 证据 | 状态 |
|---|---|---|---|---|---|---|
| 14 | 数仓 ER 图（5 表） | 5 张表的主键、粒度、逻辑外键；`fact_order` 一行一单 | `diagrams/03-data/14-er-diagram.mmd` | `14-er-diagram.svg` | `contracts/schema.contract.yaml` L26–L399；`fixtures/dw.sql` L13–L323 | ✅ 5/5 表已覆盖 |
| 15 | 契约模型 | Table / Column / Metric / ValueDomain / ColumnMetric 的字段与关系 | `diagrams/03-data/15-contract-model.mmd` | `15-contract-model.svg` | `contracts/schema.contract.yaml` L15–L399；`backend/app/build/plan.py` L69–L192 | ✅ 5 类 24 列 6 指标 9 关系 |
| 16 | 三存储知识布局 | `region_name` 与 `order_amount` 如何变成 Meta 行、ES 文档、Qdrant 点 | `diagrams/03-data/16-three-store-layout.mmd` | `16-three-store-layout.svg` | `backend/app/build/plan.py` L209–L243、L312–L378；`meta_store.py` L36–L48；`es_store.py` L21–L33；`qdrant_store.py` L113–L145 | ✅ 两例均含 1 Meta 行 / 5 或 0 ES / 5 Qdrant |
| 17 | S2 数据 lineage | 契约 + `dw.sql` → BuildPlan → 三存储 + manifest；计数 5/24/6/9/76/98/22 | `diagrams/03-data/17-s2-lineage.mmd` | `17-s2-lineage.svg` | `backend/app/build/pipeline.py` L196–L291；`plan.py` L174–L185；`build_meta_knowledge.py --dry-run`（✅ 2026-10-27） | ✅ 计数与 `facts.md` L52–L67 一致 |
| 18 | Meta 表结构 | `table_info` / `column_info` / `metric_info` / `column_metric` / `build_manifest` 的字段与主键 | `diagrams/03-data/18-meta-schema.mmd` | `18-meta-schema.svg` | `backend/app/build/meta_store.py` L25–L95、L236–L341 | ✅ 5/5 表，复合主键已标 |
| 19 | 值域分类决策树 | enum → ES；range → 不写 ES；`sync_values` 的作用 | `diagrams/03-data/19-value-domain-decision.mmd` | `19-value-domain-decision.svg` | `backend/app/build/plan.py` L209–L225、L312–L341；`recall/models.py` L16、L92–L93 | ✅ 76 篇 ES 文档的规则可复算 |
| 20 | 信任边界与攻击面 | 浏览器 / 前端 / FastAPI / LLM / 三存储 / 旧系统的边界与数据流 | `diagrams/04-security/20-trust-boundary.mmd` | `20-trust-boundary.svg` | `backend/app/security/executor.py` L1–L20；`policy.py` L298–L528；`contracts/sql.policy.yaml` L84–L93；`fixtures/dw.sql` L9 | ✅ 7 类攻击路径各有拦截层 |
| 21 | 五层纵深防御 | 契约白名单 → 静态 guard → 策略 → 只读执行器 → 错误通道/审计 | `diagrams/04-security/21-defense-in-depth.mmd` | `21-defense-in-depth.svg` | `backend/app/agent/validate.py` L31–L70；`guard.py` L151–L315；`executor.py` L161–L287；`agent/errors.py` L274–L350 | ✅ 五层与失败路径齐全 |
| 22 | SQL 策略判定流程 | 单语句 → 只读 → 表白名单 → 列白名单 → 常量投影 → ORDER BY/LIMIT → 放行/拒绝 | `diagrams/04-security/22-sql-policy-flow.mmd` | `22-sql-policy-flow.svg` | `policy.py` L298–L528；`guard.py` L151–L315；`validate.py` L31–L70；`sql.policy.yaml` L19–L125 | ✅ 六关 + 收尾，实际调用顺序已注明 |
| 23 | 只读账号权限模型 | `dw_reader` 只有 SELECT；应用账号与只读账号分离 | `diagrams/04-security/23-readonly-grants.mmd` | `23-readonly-grants.svg` | `backend/app/security/account.py` L17–L112、L142–L190；`sql.policy.yaml` L84–L93；`fixtures/dw.sql` L9 | ✅ GRANT 与禁止清单齐全 |
| 24 | 错误码分类 | 16 个错误码按 `failure` / `empty` / `cancelled` 分类，标出 `retryable` | `diagrams/04-security/24-error-taxonomy.mmd` | `24-error-taxonomy.svg` | `contracts/errors.yaml` L34–L148；`backend/app/agent/errors.py` L155–L220、L274–L350；`agent/correct.py` L144–L232 | ✅ 16/16 码，6 个 retryable |

## 验收快照

- 14：ER 图 5 个实体，`fact_order` 的 `order_id` 注释为「一行一单」。
- 17：`5 / 24 / 6 / 9 / 76 / 98 / 22` 全部出现在图与说明中；44 Meta 行 + 76 + 98 + 22 + 1 = 241（🟡 公式推导）。
- 19：`enum` 与低基数 `open` 写 ES，`range` / `id` / `foreign_key` 不写；`sync_values` 语义明确。
- 24：16 个码全部出现；`retryable=true` 恰好 6 个。

## 未决 / 边界

- `--fresh` 写三存储未实跑（Docker socket 无权限），计数来自 `--dry-run`（✅ 2026-10-27）与代码公式（🟡）。
- 真实 LLM 与真实 MySQL `--verify-ro-account` 未执行（⚪），相关结论标注在各自 `.md` 的「边界」段。
