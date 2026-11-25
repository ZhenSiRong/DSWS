# T3 交接 · 数据 / 安全图（14–24）

## 1. 产出清单

### 数据图（`design/diagrams/03-data/`）

| 编号 | 源文件 | 说明 | SVG |
|---|---|---|---|
| 14 | `14-er-diagram.mmd` | `14-er-diagram.md` | `14-er-diagram.svg` |
| 15 | `15-contract-model.mmd` | `15-contract-model.md` | `15-contract-model.svg` |
| 16 | `16-three-store-layout.mmd` | `16-three-store-layout.md` | `16-three-store-layout.svg` |
| 17 | `17-s2-lineage.mmd` | `17-s2-lineage.md` | `17-s2-lineage.svg` |
| 18 | `18-meta-schema.mmd` | `18-meta-schema.md` | `18-meta-schema.svg` |
| 19 | `19-value-domain-decision.mmd` | `19-value-domain-decision.md` | `19-value-domain-decision.svg` |

### 安全图（`design/diagrams/04-security/`）

| 编号 | 源文件 | 说明 | SVG |
|---|---|---|---|
| 20 | `20-trust-boundary.mmd` | `20-trust-boundary.md` | `20-trust-boundary.svg` |
| 21 | `21-defense-in-depth.mmd` | `21-defense-in-depth.md` | `21-defense-in-depth.svg` |
| 22 | `22-sql-policy-flow.mmd` | `22-sql-policy-flow.md` | `22-sql-policy-flow.svg` |
| 23 | `23-readonly-grants.mmd` | `23-readonly-grants.md` | `23-readonly-grants.svg` |
| 24 | `24-error-taxonomy.mmd` | `24-error-taxonomy.md` | `24-error-taxonomy.svg` |

### 目录

- `design/inventory/catalog-data-security.md`：14–24 的编号、标题、问题、源文件、SVG、证据、状态。
- `design/inventory/handoff-T3.md`：本文件。

## 2. 渲染与验收

```bash
cd /home/zhensirong/VM-Share/DSWS-design/design
python3 scripts/render_all.py
ls diagrams/03-data/*.svg diagrams/04-security/*.svg
```

本次结果（✅ 2026-10-29 本机）：

```text
32 mermaid, 1 graphviz, 0 failure(s), 32 up-to-date
```

T3 的 11 张图全部生成 SVG，且每张 SVG 都有显式 `width` / `height`，可被 WeasyPrint 直接嵌入。

计数复核：

- 14：5/5 表；`fact_order.order_id` 注释「一行一单」。
- 15：5 表 / 24 列 / 6 指标 / 9 条列—指标关系。
- 17：`5 / 24 / 6 / 9 / 76 / 98 / 22` 全部出现；241 = 44 + 76 + 98 + 22 + 1（🟡 公式推导）。
- 24：16/16 错误码；6 个 `retryable=true`；class 与 `contracts/errors.yaml` 逐字一致。

## 3. 实现说明

- Mermaid 源统一使用 `%%` 标题注释，不使用 frontmatter。原因：`render_all.py` 的 `viewBox` 正则不匹配负坐标，frontmatter 会让部分图被误设成嵌套 marker 的 `10x10`；改用注释后根 `viewBox` 为正，尺寸正确。
- 流程图统一加 `%%{init: {"flowchart": {"diagramPadding": 0}}}%%`，避免顶部负 padding 触发同一问题。
- 安全图说明均包含三件事：攻击者能做什么、被哪一层挡住、证据在哪。
- 未改任何源码、契约或既有文档；只写 `design/diagrams/03-data/`、`design/diagrams/04-security/`、`design/inventory/`。

## 4. 未决 / 未验证

| 项 | 状态 | 说明 |
|---|---|---|
| `--fresh` 写三存储 | ⚪ | Docker socket 无权限，计数来自 `--dry-run` 与代码公式 |
| 真实 MySQL `--verify-ro-account` | ⚪ | 本机未连库；只读结论来自 `account.py` 与契约 |
| 真实 LLM 生成 | ⚪ | 无端点 / 无 Key；LLM 边界由上下文构造代码推导 |
| 全量后端测试 782 | 🟡 | `facts.md` 引用 README 声称，本机未跑 |

没有阻塞交付的未决问题。

## 5. 读过的文件

- `design/WBS.md`
- `design/STYLEGUIDE.md`
- `design/inventory/facts.md`
- `contracts/schema.contract.yaml`
- `contracts/sql.policy.yaml`
- `contracts/errors.yaml`
- `fixtures/dw.sql`
- `backend/app/build/plan.py`
- `backend/app/build/meta_store.py`
- `backend/app/build/es_store.py`
- `backend/app/build/qdrant_store.py`
- `backend/app/build/pipeline.py`
- `backend/app/build/config.py`
- `backend/app/security/policy.py`
- `backend/app/security/executor.py`
- `backend/app/security/pipeline.py`
- `backend/app/security/account.py`
- `backend/app/scripts/security.py`
- `backend/app/agent/errors.py`
- `backend/app/agent/correct.py`
- `backend/app/agent/validate.py`
- `backend/app/generate/guard.py`
- `backend/app/recall/catalog.py`
- `backend/app/recall/models.py`
- `design/scripts/render_all.py`
- `design/scripts/check_deliverables.py`
