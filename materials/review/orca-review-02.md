# Orca 跨模型独立评审记录 02（codebuddy + opencode2，各 10 条）

> 来源：Orca worker 两份**只读**评审，各 10 条——codebuddy 评「评审 B」、opencode2 评「评审 A」；对象 = `manual/` 23 页与 `SPEC / README / ACCEPTANCE / TRAPS`。
> 时点：2026-11-19（仓库 HEAD `e3ce2c2`）。性质：跨模型独立评审（与 DSH 内置 subagent 不同源）。
> 恢复方式：评审结果从 Orca `messages` 表恢复（`~/.config/orca/orchestration.db`，按 `from_handle` 对应 worker），再逐条 `grep` / 真跑复核——下表「核实」以复核为准。

## 去重后的发现（20 条 → 18 个唯一问题；另复核新增 1 条）

| # | 发现（文件:行） | 来源 | 核实结论 |
|:--:|:--|:--:|:--|
| 1 | `TRAPS.md` 第 1 条把 uv.lock 变脏归因于 `make stage4/5/6-ui/7` | 双份 | 属实-已修：Makefile 已 33 处 `uv run --frozen`；裸 `uv run` 在 `recall-demo.sh:31`（`make stage3`）、`stage0-ui.sh:51`、`stage6-ui.sh:68` 与手敲时才会脏（复核补了评审漏掉的前两处） |
| 2 | `ACCEPTANCE.md` §0 同款 uv.lock 归因；p15/p19/p21 的「跑完 checkout」提示 | opencode2 | 属实-已修：统一为「变脏再 checkout；Makefile 直接调的 `stage*` 已 `--frozen`；脚本里的裸 `uv run` 会脏」 |
| 3 | `page-01.md:38` `MYSQL_USER/MYSQL_PASSWORD` 因果写反 | codebuddy | 属实-已修：官方 mysql 镜像用这两个变量建用户；`dw.sql` 的 GRANT 只补 `dw` 权限 |
| 4 | `page-10.md:105` 称「第 12 页假定库已回 115 行」 | 双份 | 属实-已修：`page-12.md:16` 第 1 步自己重灌 `dw-real`；改为「回 L1 演示态才重灌」 |
| 5 | `TRAPS.md` 第 4 条「85%+ 不跑整栈」与 `ACCEPTANCE.md:9` 口径矛盾 | codebuddy | 属实-已修：85–89% 只告警、写入/验收可跑；≥90% 高水位才危险；≥95% 只读 |
| 6 | `page-09.md:99` 拆一刀 curl 写死 `127.0.0.1:8000`，与本页「端口按实际」冲突 | opencode2 | 属实-已修：行内补「8000 换成你实际用的端口」 |
| 7 | `page-12.md:16` 第 1 步命令含 `<` 重定向却塞在正文段落（违反 SPEC:16） | codebuddy | 属实-已修：提为 fenced bash 块，正文留一句 |
| 8 | `page-17.md:3` 前置只有文字判据，缺可执行自查 | codebuddy | 属实-已修：补 `failures --check \| tail -2` → `S6 PASS` 自查 |
| 9 | `page-13.md:95` 未解释 `sse_chunks=24` 与 12 条 progress 的关系 | codebuddy | 属实-已修：补「客户端收到的 SSE 分片数，不是 progress 事件数」 |
| 10 | `page-00.md:13` 工具「五样」与 `12/12` 对不上 | codebuddy | 属实-已修：`make doctor` 把 daemon 单列 → 工具行 6 项 |
| 11 | `page-00.md:108` 回滚表「退回第 6 页版本」没有命令 | opencode2 | 属实-已修：补「重抄第 6 页代码；或先 `lab save` 再 `reset`（p10 起介绍）」 |
| 12 | `page-22.md:79` 「B 无限静默空等」与代码块 60 秒超时矛盾 | codebuddy | 属实-已修：改为「最多空等 60 秒后报错退出（`SECONDS+60`）」 |
| 13 | `page-22.md:69` 「README 写待做」指代不明 | opencode2 | 属实-已修：写明根 `../README.md` 的 S8 性能行 |
| 14 | `manual/README.md:3` 参考书 `dev-book.pdf` 无仓库内路径 | opencode2 | 属实-已修（评审称「不在仓库」有误）：`git ls-files` 显示已跟踪、`pdfinfo` 162 页；改为仓库内真实路径 |
| 15 | `manual/README.md:59` p01 判据漏「看不到 `dw`」 | opencode2 | 属实-已修：与 ACCEPTANCE/SPEC 三处统一 |
| 16 | `manual/README.md:12` 「每级最后一页拆一刀」与 L1 无拆一刀矛盾 | opencode2 | 属实-已修：改成「L2–L4 每级最后一页（L1 用海报对账）」 |
| 17 | `manual/SPEC.md:5` 「L1 九页 + p10–p22」隐含全书 22 页 | opencode2 | 属实-已修：注明 p00 前置页另计、全书 23 页 |
| 18 | `ACCEPTANCE.md` §7 L4 行仍写「p22 暂无独立重放报告」 | 复核新增 | 属实-已修：`replay-page-18` … `replay-page-22` 五份都在，列全 |
| 19 | `page-07.md:81` 称 500 第二类应为 `StopIteration` 而非 `RuntimeError: coroutine raised StopIteration` | codebuddy | **证伪-不改**：我方此前真跑实测即 `RuntimeError: coroutine raised StopIteration`，保留原文 |
| 20 | 宿主机 Python ≥3.8 未进第 0 页清单（`docker-smoke.sh:34` / `make docker-env` 要用，`make doctor` 不查） | opencode2 | 属实-已修：不在本轮 20 条文档清单内，由并行修复处理（`scripts/find-python.sh` + p00 注意行） |

## 结论与边界

- 修复 18 条（#1–#18）；证伪 1 条（#19，保留原文）；#20 由并行修复处理（本记录不动脚本）。
- 只改文档：`manual/`（含本记录与索引）；图、截图、页面代码逻辑与脚本均未改。
- 验证：`python3 manual/shots/audit_book.py` → `页面：23/23 通过；README 坏链：0`；`make audit` → `AUDIT PASS：4/4`。
- 评审方法：`orca-ide orchestration worker-start --agent codebuddy|opencode2`，只读、≤600 字、10 条，按 `文件:行 — 问题 → 建议` 输出；主 agent 逐条复核实后再改。
