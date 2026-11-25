# DSWS 设计图集 · 样式与证据规范

## 1. 图的三种读者

每张图必须同时服务三类读者，缺一不可：

1. **新手**：只看图能说出「谁把什么交给谁」。
2. **实现者**：能顺着图找到真实文件、函数、表名。
3. **评审者**：能看出哪些是已验证事实，哪些是推断。

所以每张图都必须有：标题、一句话结论、图、图例、证据表。

## 2. 文件命名

```text
diagrams/<角度>/<两位编号>-<英文短名>.<ext>
diagrams/<角度>/<两位编号>-<英文短名>.md    # 说明
```

例：

```text
diagrams/02-runtime/08-s2-build-sequence.mmd
diagrams/02-runtime/08-s2-build-sequence.svg
diagrams/02-runtime/08-s2-build-sequence.md
```

编号在全图集内唯一，不按目录重新计数。

## 3. 颜色语义

| 颜色 | 含义 | 用法 |
|---|---|---|
| `#1d4ed8` 蓝 | 契约 / 事实源 | 契约文件、schema、steps、errors |
| `#0f766e` 青 | 存储 / 数据 | MySQL、ES、Qdrant、fixture |
| `#b45309` 橙 | 构建时任务 | S2、CLI、一次性批处理 |
| `#7c3aed` 紫 | 查询时服务 | FastAPI、recall、generate |
| `#b91c1c` 红 | 安全 / 失败 | 策略、拒绝、错误通道 |
| `#15803d` 绿 | 通过 / 已验证 | 验收、测试、健康 |
| `#6b7280` 灰 | 边界 / 未验证 | 旧系统、外部 LLM、未验证 |

不要用颜色表达「好/坏」以外的价值判断；红色只给安全与失败，不给普通数据。

## 4. Mermaid 约定

```mermaid
flowchart LR
  classDef contract fill:#eff6ff,stroke:#1d4ed8,color:#1e3a8a
  classDef store fill:#ecfdf5,stroke:#0f766e,color:#064e3b
  classDef build fill:#fff7ed,stroke:#b45309,color:#7c2d12
  classDef runtime fill:#f5f3ff,stroke:#7c3aed,color:#4c1d95
  classDef danger fill:#fef2f2,stroke:#b91c1c,color:#7f1d1d
  classDef pass fill:#f0fdf4,stroke:#15803d,color:#14532d
  classDef edge fill:#f9fafb,stroke:#6b7280,color:#374151
```

- 必须设置 `htmlLabels: false`（PDF 用 WeasyPrint，不支持 foreignObject）。
- 节点文字不超过 18 个汉字；超长说明放到 `.md`。
- 边必须有动词，不能只画箭头。
- 子图只用于「部署边界 / 信任边界 / 阶段」，不用于装饰。
- 时序图参与者用真实进程名：`Browser`、`FastAPI`、`AgentRunner`、`MySQL`、`ES`、`Qdrant`、`LLM`。

## 5. Graphviz 约定

- `rankdir=LR` 优先；层级图用 `TB`。
- 字体：`Noto Sans CJK SC`，字号 11–13。
- 节点 `style="rounded,filled"`，边框 1.2pt。
- 边标签用 `fontsize=10`，避免压线。
- 输出 `-Tsvg`，不要 PNG（PDF 需要矢量）。

## 6. 证据纪律

每个结论标一个状态：

| 标记 | 含义 | 要求 |
|---|---|---|
| ✅ 已验证 | 本机命令跑过 / 测试通过 / 文件明确存在 | 附命令或文件行号 |
| 🟡 推断 | 从代码结构推导，未实跑 | 写清推导链 |
| ⚪ 未验证 | 环境不具备 / 未执行 | 写清缺什么 |

禁止把 🟡 写成 ✅。禁止用「应该」「大概」代替证据。

## 7. 图说明模板

```markdown
# 08 · S2 构建流水线时序

**一句话**：S2 是一条一次性 CLI 任务，按 Meta → ES → Qdrant → manifest 的顺序写入，然后退出。

**这张图回答**：谁在读契约？谁在写三个存储？查询时 S2 还在不在？

**图例**：橙色=构建时任务；青色=存储；蓝色=契约。

**关键元素**：
- `build_meta_knowledge.py`：CLI 入口，解析四个开关。
- `pipeline.build()`：编排 noop / 修复 / 全量。
- `plan.py`：纯内存生成 `BuildPlan`。

**证据**：
- `backend/app/build_meta_knowledge.py` L1–L80
- `backend/app/build/pipeline.py` L199–L300
- `make stage2` 输出（✅ 2026-10-26 本机）

**边界**：本机 Docker socket 无权限，`--fresh` 未实跑；计数来自 `--dry-run`。
```

## 8. 书稿排版

- A4，页边距 20mm；正文 10.5pt，行高 1.65。
- 每章从新页开始；图不跨页；表格不跨页（尽量）。
- 图题在图下方：`图 08 · S2 构建流水线时序`。
- 表题在表上方：`表 2-1 · 三存储计数`。
- 代码块用等宽字体，超过 78 字符换行或缩小字号。
- 每页页脚：书名 + 页码；页眉：当前部分。
- 目录用 `target-counter` 生成真实页码。
