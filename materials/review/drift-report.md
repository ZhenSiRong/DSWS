# 断层汇总报告（drift-report）· 24 页教程 × 源码

> 目标 2（可复现/跟随性测试）产物。断层五类见 GLOSSARY「断层」：①命令/路径失效 ②预期输出对不上 ③代码改页面没改 ④证据/截图过期假绿 ⑤跨页前置断裂。
> 数据来源：`replay-static-p00-11.md`（12 页静态重放）、`replay-static-p12-23.md`（12 页静态重放）、`replay-stack.md`（栈测+拆一刀，进行中）。
> 生成：2026-11-27。状态机：静态线已收工 → 栈测进行中 → 修复 → 独立复验。

## 总览

| 类别 | blocker | should | 合计 |
|---|---:|---:|---:|
| ① 命令/路径失效 | 3 | 0 | 3 |
| ② 预期输出对不上 | 0 | 2 | 2 |
| ③ 代码改页面没改 | 0（根因并入①） | 0 | 0 |
| ④ 证据/截图过期假绿 | 0（待栈测比对内容新鲜度） | 0 | 0 |
| ⑤ 跨页前置断裂 | 0 | 0 | 0 |
| **静态线小计** | **3** | **2** | **5** |
| 栈测线 | 待补 | 待补 | 待补 |

## 断层清单（静态线，已复现）

| # | 页 | 类 | 级 | 现象 | 期望 | 建议修法 |
|---|---|---|---|---|---|---|
| D1 | p11 | ①/③ | blocker | 贴片 `(ROOT/"contracts"/"schema.contract.yaml")` 指向已删除的根目录兼容软链（d19565c 移除），照抄 `lab/app.py` 真跑 `FileNotFoundError` 退出 1，主线全断 | 路径可达 `system/contracts/schema.contract.yaml` | 贴片改 `ROOT/"system"/"contracts"`（修法已实测可用） |
| D2 | p12 | ①/③ | blocker | `lab/db.py` 贴片读 `ROOT/contracts/sql.policy.yaml`（page-12.md:42），同根因；page-12.yaml `coverage: static` 未覆盖该路径，T0 假绿盲区 | 同上 | 贴片路径加 `system/` 段；page-12.yaml 补贴片路径静态断言 |
| D3 | p23 | ① | blocker | `docker run -v $PWD/deliverable/v2/original-frontend/...`（page-23.md:47-48）漏 `materials/` 前缀，照敲挂空目录，8088 对照实验不可达 | `-v $PWD/materials/deliverable/v2/original-frontend/...`（同页表格与契约均为真实路径） | 补 `materials/` 前缀 ×2 |
| D4 | p08 | ② | should | 页面 `result` 只发对象数组 `rows`；契约还要求必带 `columns`、rows 为「数组的数组」，页面只披露了 columns 差异 | 与 `sse.schema.json` 全形状一致或显式声明差异 | 页面补齐 rows 形状说明 |
| D5 | p18 | ② | should | 对 `.env.example` 的描述不准确（详见 replay-static-p12-23.md p18 节） | 描述与 `.env.example` 实际键位一致 | 按源文件改写描述 |

## 共性根因

- **D1/D2 同源**：d19565c「移除全部兼容软链」只改了仓库布局，未同步页面贴片 → 典型③（代码改页面没改），现象表现为①。**建议**：全书 grep 一次 `ROOT/"contracts"` / `ROOT/contracts` 类旧路径（修复者执行）。
- **T0 盲区**：page-12.yaml `coverage: static` 只查 `system/contracts/sql.policy.yaml` 存在，没查页面贴片里的路径——verify 契约层面防不住贴片路径漂移。

## 栈测线（待补）

（范围：p01/p02 docker 观察、p07–p09 curl 链、p10 manual+拆一刀、p11/p17 拆一刀红法、灌库/smoke/stage3/stage5-live、p22 级考核窗口、p17-viztracer。报告：replay-stack.md。）

## 修复与复验记录

（待修复者与复验者回填。）
