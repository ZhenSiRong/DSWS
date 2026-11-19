# 重放报告索引（review/）

> 每份报告 = 一页的学生视角独立重放；新报告一律复制 [REPLAY-TEMPLATE](REPLAY-TEMPLATE.md)（六段：结论 / 范围声明 / 环节表 / 问题清单 / 真输出摘录 / 清理确认，外加 8 类必查清单），命名为 `replay-page-XX.md`。
> 阅读顺序：先看「结论」判断本页能不能跟做，再看「问题清单」里严重度「高」的条目，最后照「真输出摘录」复跑。

| 报告 | 一句话结论 |
|:--|:--|
| [orca-review-01](orca-review-01.md)（跨模型评审） | Orca worker · codebuddy 只读评审 SPEC/AGENTS：4 条对 23 页现状的漂移已全部修复。 |
| [orca-review-02](orca-review-02.md)（跨模型评审） | Orca worker · codebuddy + opencode2 各 10 条只读评审：去重 18 个唯一问题——16 条文档已修、1 条证伪不改、1 条转并行脚本修复；另复核新增 1 条已修。 |
| [page-10](replay-page-10.md) | 核心实验全部复现；先修前置阅读顺序自相矛盾、对账时序写错、拆一刀还原被写成可选 3 条。 |
| [page-11](replay-page-11.md) | 能独立跟做；1 处 cwd 卡点（`cd backend` 后没提示回仓库根）+ 第 8 页交接事实错误。 |
| [page-12](replay-page-12.md) | 指令链可照抄；`1144735.50` 口径与第 10 页冲突、拆一刀 `max_limit` 说明有歧义、第 10 页白名单过时。 |
| [page-13](replay-page-13.md) | 文字审计 + 配置级离线验证（未整栈）；smoke 的 too-fast 判据写错、前置理由与事实相反、拆一刀依赖未提交改动。 |
| [page-14](replay-page-14.md) | 主线命令全部可执行、核心判据复现；检索候选数写死且与实测不符（10/6、8/6），恢复 ES 缺等待判据。 |
| [page-15](replay-page-15.md) | 主线可完整重放、四组判据逐字命中；先修 uv.lock 静默重写、拆一刀防全局替换、契约自检缺命令。 |
| [page-16](replay-page-16.md) | 可完整离线重放、判据全复现；6 处小瑕疵，PYTHONPATH 旧注释与 policy.py 同名行最该先补。 |
| [page-17](replay-page-17.md) | 可整段照做、核心判据全复现；1 条高优先：成功态「至今未复现」与 v2 证据冲突。 |
| [page-18](replay-page-18.md) | 核心判据全部复现；问题集中在前置依赖没写全、拆一刀新开终端的误导报错。 |
| [page-19](replay-page-19.md) | 判据与拆一刀逐字复现；最大问题是 uv run 改 uv.lock 而 reset 救不回，其次管道退出码矛盾。 |
| [page-20](replay-page-20.md) | 核心判据全逐字复现；缺「先还原第 19 页拆一刀」前置检查，重录假绿缺后果说明。 |
| [page-21](replay-page-21.md) | 第 1–3 步与拆一刀逐字复现；最该先修 stage7 的 uv.lock 副作用、拆一刀两处定位按字面搜不到。 |

> 旧格式：`replay-03-05.md`、`replay-06-09.md`、`walkthrough.md` 属 L1，未套本模板，仍可参照。
