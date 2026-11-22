# 重放报告索引（review/）

> 每份报告 = 一页的学生视角独立重放；新报告一律复制 [REPLAY-TEMPLATE](REPLAY-TEMPLATE.md)（六段：结论 / 范围声明 / 环节表 / 问题清单 / 真输出摘录 / 清理确认，外加 8 类必查清单），命名为 `replay-page-XX.md`。
> 阅读顺序：先看「结论」判断本页能不能跟做，再看「问题清单」里严重度「高」的条目，最后照「真输出摘录」复跑。
> `review/` 下的生成脚本是教师/CI 夹具，学生入口看 [附录工具卡](../appendix/gui-debugging.md)。

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
| [page-17](replay-page-17-v2.md) | v2（D54 原子工具版，2026-11-22）：第 1–5 步 + 拆一刀/还原全复现（14 passed、S6 PASS、5 failed/9 passed、probe mismatch 0），viztracer trace 3505 条 + pdb 断点 183 真跑；0 高 / 4 中 / 8 低——先修 pdb `q` 后 BdbQuit 未预告、ACCEPTANCE「成功态不可复现」与页内 v2 成功证据冲突、附录 scalene `--html` 非自包含。v1 见 [replay-page-17](replay-page-17.md)（已过时，保留）。 |
| [page-17 v2 修复](fix-page-17-v2.md)（R3） | 修 R2 重放的 12 条：pdb `q` 后 BdbQuit 预告、成功态「单次复现过/不当判据」口径、scalene `--standalone`、page-00 pipx 前置；行数 134 不变。 |
| [page-17 v2 对抗审查](adversarial-page-17-v2.md)（R4） | 不采信 R2/R3 结论、自己重跑：0 高 / 3 中 / 8 低——第 6 步缺真模型前置且端口指路混、py-spy 卡 `-- your_script.py` 照抄失败、`eval/live_probe.py` 实为五类口径；另找 8 条低优先。 |
| [page-17 v3 收口](fix-page-17-v3.md)（R5） | 修完 R4 全部 11 条 + 发布前终验：结构 24/24、`make audit` 4/4、p17 离线三判据复跑、附录 9 张工具卡逐卡自检；未改实现代码、未起容器/栈、未提交。 |
| [page-18](replay-page-18.md) | 核心判据全部复现；问题集中在前置依赖没写全、拆一刀新开终端的误导报错。 |
| [page-19](replay-page-19.md) | 判据与拆一刀逐字复现；最大问题是 uv run 改 uv.lock 而 reset 救不回，其次管道退出码矛盾。 |
| [page-20](replay-page-20.md) | 核心判据全逐字复现；缺「先还原第 19 页拆一刀」前置检查，重录假绿缺后果说明。 |
| [page-21](replay-page-21.md) | 第 1–3 步与拆一刀逐字复现；最该先修 stage7 的 uv.lock 副作用、拆一刀两处定位按字面搜不到。 |
| [page-23](replay-page-23-v2.md) | 成熟版重放（v2，2026-11-20）：成熟版 `41099.5`+12 节点 11✓/1 未触发、教学版同数 `41,099.5`、`npm test` 40 passed、拆一刀 29 行 HTML `41099.5` + 还原干净全复现；先修 :128/:52 把成熟版数值写成 `41,099.5`、:23 `make docker-up` 恒 `--build` 与前置相反、:35 取 `.env.example` 未读 `.env`。v1 见 [replay-page-23](replay-page-23.md)（已过时，保留）。 |

> 旧格式：`replay-03-05.md`、`replay-06-09.md`、`walkthrough.md` 属 L1，未套本模板，仍可参照。
