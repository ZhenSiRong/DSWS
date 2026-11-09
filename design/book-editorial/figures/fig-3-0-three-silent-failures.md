# fig-3-0-three-silent-failures

**一顿『成功』的晚餐**

_生活类比 · 界面说上齐了，桌上却没有一道能吃的菜。_

## 1. 来源

- 教材：*DSWS 从零到一*，第一部分 · 先读这一页，3. 三个根因：为什么要重建
- 原稿：`design/book/chapters/00-front.md`，行 63–117
- 代码/契约：`contracts/errors.yaml`, `backend/app/main.py`, `frontend/src/lib/result.ts`, `fixtures/sse/pseudo_row.json`, `fixtures/sse/empty_rows.json`, `docs/S7-HANDOFF.md`
- 旧书：`design/book/book.html` 与 `design/book/pdf/dsws-design-atlas.pdf`（本轮未重建）

## 2. 事实核对

| # | 事实 | 原文摘录（≤50 字） | 出处 | 核对 |
|---|---|---|---|---|
| 1 | 旧系统有三类静默失败：界面显示成功，语义已经错了；用户没有任何线索发现。 | “旧系统不是「架构不漂亮」才被替换，而是有三类静默失败：界面显示成功，语义已经错了；用户没有任何线索发现。” | 00-front.md §3 开头<br>`00-front.md:65` | ✅ |
| 2 | 生成失败时，错误说明被塞进一行一列的结果，前端按表格渲染；用户看到「查询成功」加一句话。 | “生成失败时，旧系统把一段错误说明塞进「一行一列」的结果里……用户看到的是「查询成功」加一句话，而不是一次失败。” | 00-front.md §3.1；fixtures/sse/pseudo_row.json；frontend/src/lib/result.ts；docs/S7-HANDOFF.md F5<br>`00-front.md:69–71; pseudo_row.json; result.ts:103–112; S7-HANDOFF.md:167,193–198,302` | ✅ |
| 3 | 旧系统把空数组 data: [] 当成正常结果；新系统用 EMPTY_RESULT（类别 empty）把「没有数据」和「失败」分开。 | “旧系统把空数组 `data: []` 当成一次正常结果……审计把这条记为 FP-8：空数组是合法语义，不是失败，但也不是成功的数据。” | 00-front.md §3.2；contracts/errors.yaml EMPTY_RESULT；fixtures/sse/empty_rows.json；docs/S7-HANDOFF.md FP-8<br>`00-front.md:83–90; errors.yaml:70–74; empty_rows.json; S7-HANDOFF.md:26,301` | ✅ |
| 4 | SSE 序列化传 default=str，Decimal("10") 变成字符串 "10"；新系统 _sse() 不传 default=str，未知类型变成 INTERNAL_ERROR。 | “SSE 序列化传了 `default=str`，MySQL 的 `Decimal("10")` 悄悄变成字符串 `"10"`。” | 00-front.md §3.3；backend/app/main.py _sse()<br>`00-front.md:98–107; main.py:250–259` | ✅ |
| 5 | 三个根因分别由 S5/S6/S7、S3/S6/S7、S4/S5/S6/S7 承担。 | “伪 SQL 被当成数据 → S5 拒绝 → S6 错误事件 → S7 展示层止损；召回为空也算 success → S3 trace → S6 EMPTY_RESULT → S7 空态卡；错误被吞掉 → S4 形状 → S5 执行 → S6 分类 → S7 映射。” | 00-front.md §3.4 根因与阶段的对应关系表<br>`00-front.md:113–117` | ✅ |

## 3. 读图路径

1. 第一幕：服务员端来一张『查询成功』的账单，盘子里却是一张『错误说明』——形状合法，语义错了。
2. 第二幕：盘子空了，服务员仍说『上齐了』——空、召回失败、系统失败被同一种界面吞掉。
3. 第三幕：后厨冒烟，红框亮了，但服务员只说『后厨出问题了』——错误没有步骤归属。
4. 底部：三盘都上了，但没有一盘能吃；新系统的对策是让失败有名字、有位置、有通道。

## 4. 风格卡

- 画布：1600×900，纸色 `#FFFDF8`
- 墨色 `#111111`；次级 `#5B5B5B`；分隔线 `#D9D3C7`
- 钴蓝 `#1F4E9C`；锈红 `#B24A2E`；森林绿 `#2F5D46`；芥末 `#C58B1B`
- 字体：`Noto Sans CJK SC`；字号：42 / 30 / 26 / 24 / 22 / 18
- 三格漫画，每格：餐厅场景 → 用户看到 → 实际发生 → 新系统挡住
- 图注由书里的 `figcaption` 生成，图内不重复图号

## 5. 门禁

| 门 | 结果 | 证据 |
|---|---|---|
| spelling | pass | spelling_manifest=True; spelling_expected=True; 31/31 manifest strings found in hy4free review; missing=[] |
| layout | pass | layout_text_overlap=True; layout_rect_overlap=True; layout_bounds=True |
| color | manual | no automated check |
| typography | pass | typography_sizes=True; typography_title=True; typography_section=True; typography_label=True; typography_note=True; typography_small=True |
| uniqueness | pass | uniqueness=True |
| style_card | pass | typography_sizes=True |
| teaching_5s | manual | 5 秒读懂：三盘都上了，但没有一盘能吃；每幕底部给出新系统的止损点。 |
| no_figure_needed | manual | 删图门：§3 是 3 个小节 + 1 张表，读者要在脑内把三种失败并排比较；餐厅三幕用同一个故事把三种失败串起来，保留。 |

## 6. hy4free 逐字复核

```text
一顿『成功』的晚餐
生活类比 · 界面说上齐了，桌上却没有一道能吃的菜。
生活类比
第一幕 · 纸条当菜
根因 01 · 伪 SQL 被当成数据
这是菜？
您的菜来了
错误说明
查询成功
用户看到：一张『查询成功』的账单
实际：盘子里是一张『错误说明』
S5 拒单 · S6 报错 · S7 止损
第二幕 · 空盘上齐
根因 02 · 召回为空也算 success
是没有，还是没找到？
上齐了
用户看到：表格消失，像跑完了
实际：空、召回失败、系统失败混在一起
S3 trace · S6 空态 · S7 空态卡
第三幕 · 糊菜指不到灶台
根因 03 · 错误被吞掉
哪个灶？
后厨
后厨出问题了
用户看到：红框亮了，却指不到灶台
实际：错误没有步骤归属
S4 形状 · S6 分类 · S7 映射
共同点：三盘都上了，但没有一盘能吃。
新系统：让失败有名字、有位置、有通道。
生活类比：餐厅三幕 · 事实来源：00-front.md § 3.1–3.4 · contracts/errors.yaml · docs/S7-HANDOFF.md
```

_OCR 旁证：`fig-3-0-three-silent-failures-review-hy4free-tesseract.txt`（本机 tesseract 仅装 eng，中文不可用，不参与门禁）。_

## 7. 版面验收

- 新书 PDF：`design/book-editorial/pdf/dsws-design-editorial.pdf`（207 页）
- §3 起始页：新书第 7 页；旧书第 6 页
- 改前页：`pilot/before-6.png`
- 改后页：`pilot/after-7.png`

## 8. 产物

- `figures/fig-3-0-three-silent-failures.svg` — sha256 `8ab58440dea454146ed179fa386176c2b43f830e4ae1383a86049538fdb081a0`
- `figures/fig-3-0-three-silent-failures.png` — sha256 `fc66731f4d84a7777a62d717e74913b8ea8e4c4b95d52b90db6eb94627d4b778`
- `figures/fig-3-0-three-silent-failures.layout.json` — sha256 `4e4895fade76376f288f779e67d3368f8027444670ec58409cfa7a7af5fbdc06`
- `figures/fig-3-0-three-silent-failures.text-manifest.json` — sha256 `f57ccc614ced04244fafb026dbc5deb71c00170444521f5f495ab82cdbc55fec`
- `figures/fig-3-0-three-silent-failures.checks.json` — sha256 `158746acb15e8aa24d9bbede465018bb29108974dc77c68a1ecfd622f7430aa8`

## 9. 未决问题

- 自动门禁全部通过；`teaching_5s` 与 `no_figure_needed` 待人工确认。
- 旧书 PDF 未重建；新书 PDF 的 §3 版面是本轮验收对象。
