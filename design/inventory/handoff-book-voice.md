# 书稿叙事改写交接（《调试九法》风格参考）

日期：2026-10-30
工作树：`/home/zhensirong/VM-Share/DSWS-design`
Orca Run：`run_c608e381d786`
风格参考：`design/skills/book-voice-reference.md`
去 AI 味规则：`design/skills/de-ai-writing.md`

## 1. 目标

参考 EPUB《调试九法》的叙事优点，让 `design/book/chapters/*.md` 更像人写的技术书：用真实项目事故开场，用短句说规则，用能落回机制的类比，章末给一个可记忆的小结。

只借“怎么讲”，不借“讲什么”。《调试九法》的案例、福尔摩斯引语、虚构时间线和人物对话，一律没有搬进 DSWS 书稿。

## 2. 方法：只增不改

本轮没有重写现有段落，只在指定锚点插入新段落。现有行逐字保留，原因有两个：

1. `design/` 在当前工作树是未跟踪目录，`git diff` 看不到改动，靠逐行比对才能证明事实没漂。
2. 书稿里的数字、命令、图号、证据标记太多，整段改写容易在不知不觉中把“通常”写成“一定”。

验收脚本 `/tmp/opencode/verify-voice.py` 用 `difflib` 检查：相对基线只能有 `insert`，不能有 `replace` / `delete`；新增文字不能出现本文件没有的数字；新增标题必须在白名单里；代码块、表格行、图片链接、净增字节全部要过。

## 3. 分工

| 工作 | 执行者 | 范围 | 结果 |
|---|---|---|---|
| 书稿改写 A | qoder | `00-front.md`、`10-s0-s4.md`、`20-s5-s8.md` | 3 个开场、3 个小结，验收全绿 |
| 书稿改写 B | codebuddy | `30-atlas.md`、`40-ops.md`、`90-appendix.md` | 3 个开场、六个角度组各 1 句、2 个小结，验收全绿 |
| 交叉复核 A | qoder（只读） | codebuddy 的 3 个文件 | 1 个 blocker、3 个 should-fix、3 个 nit |
| 交叉复核 B | codebuddy（只读） | qoder 的 3 个文件 | 0 blocker、3 个 should-fix、3 个 nit |

协调、终审和少量措辞修正由 opencode 终端完成；没有把改写任务派给 opencode agent。

## 4. 改动规模

| 文件 | 插入行 | 净增字节 | 预算 | 新增标题 |
|---|---:|---:|---:|---|
| `00-front.md` | 10 | 728 | 1536 | `### 7.1 如果只记三件事` |
| `10-s0-s4.md` | 14 | 904 | 4096 | `### 6.1 本部分小结` |
| `20-s5-s8.md` | 11 | 1023 | 5120 | `### 5.1 本部分小结` |
| `30-atlas.md` | 23 | 1541 | 2048 | `## 8. 图集小结` |
| `40-ops.md` | 14 | 1014 | 2048 | `## 11. 排障小结` |
| `90-appendix.md` | 4 | 349 | 1024 | 无 |
| **合计** | **76** | **5559** | **15872** | 5 个 |

六个文件相对基线都是 0 条删除行。`30-atlas.md` 有一处**事实修正**，见 §6。

## 5. 各文件加了什么

### `00-front.md`

- 开场：旧系统的 `Decimal("10")` 经 `default=str` 变成 `"10"`；表格看起来正常，复制出去不能求和。
- 结尾：`### 7.1 如果只记三件事`，三条分别锚到 `contracts/`、✅/🟡/⚪、`contracts/errors.yaml`。

### `10-s0-s4.md`

- 开场：旧系统“客单价”同时算出 2427.47、448.81、5.41，三种口径都能自圆其说。
- 结尾：`### 6.1 本部分小结`，S0–S4 各一条，锚点是 12 步 / 1 个条件步骤、5 表 24 列 6 指标、241（🟡）、20 题黄金集、10/10 与拒答 2。

### `20-s5-s8.md`

- 开场：旧系统把 `SELECT '无法生成SQL…' AS error_message` 当成一行正常数据返回，前端渲染成 1 行 1 列的表，没有红色。
- 结尾：`### 5.1 本部分小结`，S5–S8 各一条，锚点是 36/36 与 11/11、16 个错误码 / 3 个 class、14 条夹具与 13 条 F 缺陷（⚪ 未跑）、S8 的 ⚪。

### `30-atlas.md`

- 开场：先读图 32；图都有 SVG，但有图不等于有证据。
- 六个角度组总纲各加 1 句“最容易误读什么”。
- 结尾：`## 8. 图集小结`，四条。

### `40-ops.md`

- 开场：本设计工作树跑 Docker 得到 `permission denied ... /var/run/docker.sock`，不是容器列表。
- §4 末尾：`docker compose ps -a` 先看 `running` 还是 `healthy`，`init` 退出码为 0 才有 backend。
- §8 末尾：页面 502 先看 `ps -a`；`init` 正常且 backend / frontend healthy，才轮到 nginx 反代。
- 结尾：`## 11. 排障小结`，三条。

### `90-appendix.md`

- 开场：`dim_region` 没有 `city`，`dim_product` 没有 `price`；记反了，校验时才会报未知列。
- 第二段：附录只做索引、速查、对账，数字指回 `design/inventory/facts.md`，✅/🟡/⚪ 保留原状态。

## 6. 交叉复核发现与处理

### 6.1 qoder 审 codebuddy

| 级别 | 发现 | 处理 |
|---|---|---|
| blocker | 新开场与小结写“图 20–24 还没有 SVG”，但 `design/diagrams/04-security/20-24*.svg` 实际存在 | 已改：开场改成“三十二张图都有 SVG，但有图不等于有证据”；`30-atlas.md` §0 原句改成“图 01–32 均已有 SVG；但图 20–24 的条目仍写「未生成」，是旧状态”；小结改成“有图不等于有证据” |
| should-fix | 测试组那句把 ✅ 窄化成“本工作树跑过那一次”，`STYLEGUIDE` 还包含“文件明确存在” | 已改：`✅` 只说明本机跑过或文件明确存在，不保证下次还过 |
| should-fix | 30 开场与小结重复同一句 SVG 判断 | 已改：开场讲“有图不等于有证据”，小结讲“引用前先看实际文件，再核对证据行” |
| should-fix | 40 §8 “页面 502 先看 init”与 `20-s5-s8.md` §4 的“backend healthy 但 502 查 nginx 反代”冲突 | 已改：先看 `ps -a`；`init` 正常且 backend / frontend healthy，才轮到 nginx |
| nit | 30 “箭头只是引用”语义含糊 | 已改：箭头只表示引用关系，不表示数据流 |
| nit | 40 “不是容器列表，而是” | 保留：参考文档 §5.4 已批准这个句式，且这里是真实反差 |
| nit | 90 “执行时才报未知列”不准确，S4 静态校验会先拦 | 已改：校验时才会报未知列 |

### 6.2 codebuddy 审 qoder

| 级别 | 发现 | 处理 |
|---|---|---|
| should-fix | `00-front` 小结把 ✅ 窄化成“本机跑过” | 已改：本机跑过或文件明确存在 |
| should-fix | `20-s5-s8` 小结说“13 条 F 缺陷各有浏览器用例”，漏了 ⚪ | 已改：补“但本工作树没跑（⚪）” |
| should-fix | S5 用“门禁”类比，与全书“阶段门禁 / 离线门禁”同词两义 | 已改：S5 像“闸机” |
| nit | `00-front` 开场没写“旧系统”，读者可能以为是 DSWS 现状 | 已改：加“旧系统的” |
| nit | `10` 小结与开头“能演示、能验收、能回退”几乎同句 | 已改：小结改成“没有验收命令的阶段，不算完成” |
| nit | `20` 的“Docker 全栈是 ⚪”与 `40` 小结跨章重复 | 已改：20 改成“这一步目前是 ⚪：只有清单，没有整机实跑” |

## 7. 事实修正说明

`30-atlas.md` §0 原句是：

> 截至定稿，图 01–19 与 25–32 已有 SVG；图 20–24 尚未生成。

实际文件里 20–24 的 SVG 已生成（`design/diagrams/04-security/20-trust-boundary.svg` 到 `24-error-taxonomy.svg`，39–51 KB）。本轮把这一句改成：

> 截至定稿，图 01–32 均已有 SVG；但图 20–24 的条目仍写「未生成」，是旧状态。

这是本轮唯一一处对基线行的修改。为了让 `verify-voice.py` 继续只检查新增内容，`/tmp/opencode/baseline-voice/30-atlas.md` 的同一行也同步成了修正后的句子；原始句子保留在本节，便于审计。

## 8. 未决问题

1. **图 20–24 的条目仍写“图 ⚪ 未生成”。** SVG 实际存在；`30-atlas.md` §0 已说明这是旧状态，但条目本身还没回填。建议下一轮做一次图状态对账，把 20–24 的证据行改成 ✅，并同步图 29–32 条目里“SVG 待渲染”的旧说法。
2. **图 29–32 的条目写“SVG 待渲染（⚪）”。** 实际 `design/diagrams/06-testing/29-32*.svg` 已存在。与第 1 条同批处理。
3. **`30-atlas.md` 第 13 行原句与条目矛盾。** 本轮已用“旧状态”说明，但没有逐条改条目；这是一次独立的事实回填，不建议混在叙事改写里做。

## 9. 验收

命令：

```bash
cd /home/zhensirong/VM-Share/DSWS-design
python3 /tmp/opencode/verify-voice.py \
  00-front.md 10-s0-s4.md 20-s5-s8.md \
  30-atlas.md 40-ops.md 90-appendix.md
```

结果：六个文件全部 `ok=true`；`only_insertions`、`no_new_numbers`、`new_headings_allowed`、`code_blocks_identical`、`fence_count_equal`、`table_rows_identical`、`image_links_exist`、`growth_within_budget` 八项全为 `true`。

完整 JSON 在 `/tmp/opencode/verify-final.json`。

新增行内代码需要人工确认的只有两处，均有出处：

- `40-ops.md` 的 `permission denied ... /var/run/docker.sock`：`docs/SETUP-FROM-SCRATCH.md` §3 已记录。
- `40-ops.md` 的 `healthy`：本文件 §2 表、§3、§4 已多次以纯文本出现，本次首次加反引号。

## 10. 边界

- 没有提交 git。`git status` 仍是上一轮留下的 `M README.md`、5 个 `M docs/*.md` 和 `?? design/`。
- 只改了六个章节和 `design/skills/book-voice-reference.md`；源码、契约、`docs/`、`README.md`、图文件均未动。
- 没有把《调试九法》的案例、引语、人物或时间线搬进书稿。
- 没有新增项目事故；所有开场都来自书稿、`facts.md` 或 `docs/` 里已有的事实。

## 11. 后续：`10-s0-s4.md` 的教材化重写（2026-10-30）

本节之后，`10-s0-s4.md` 已不再适用 §2「只增不改」的约束。该章按 `textbook-authoring` skill 做了整章重写（v2），事实锁替代了 `verify-voice.py` 的「只允许插入」检查。

- skill：`~/.agents/skills/textbook-authoring/`，项目内副本 `design/skills/textbook-authoring/`（上游 commit `d38616f0f090abf39b6922661a965feaeaa2afdc`）。
- 样板章：`design/book/chapters/10-s0-s4.md`，46,661 字符，基线 34,746 字符的 1.343 倍（上限 1.35）。
- 事实锁：`/tmp/opencode/verify-textbook.py` 十项全绿；数字、硬行内 token、代码块、表格行、图链接、标题顺序、✅/🟡/⚪ 数量零差异。
- 盲审：三份 v1 盲审 → v2 定向复审 → 第三轮 delta 复核；结论分别为「论证密度可交付」「可以当讲义底稿」「可以独立读完 S0–S4」。
- 交付记录：`/tmp/opencode/textbook-pilot/` 下的 `draft-v2.md`、`change-summary-v2.md`、`revision-notes-v2.md`、`review-v2-*.md`、`review-v3-*.md`、`verify-v2-final.json`。
- 构建：`design/book/book.html` 与 `design/book/pdf/dsws-design-atlas.pdf` 已用重写稿重建，PDF 169 页、4.81 MB（旧版 161 页）。
- 其余五章未动，仍按 §2 的「只增不改」约束；是否推广到其余五章待定。
