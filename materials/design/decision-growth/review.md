# 独立审查记录（design-doc-growth）

日期：2026-11-27 · 对象：correction / security / contract / runtime / journey 五链渐进稿与配套件
（审查以 spread.html 文本为准；审查者看不了图片，视觉裁切由 `check_spread.py` 程序化兜底。）

## 第 1 轮 · 对抗式事实审查

**FINAL: BLOCKER(7)**。逐链：

- **correction — blocker**：①spread unknown 框截断（止于「（PRD」）；②E3 证据行截断（「14 passed · S6 PASS · PRD」）；③claims.md/final-brief 仍称图 12 源料未修（实际已修复：graph.py `_route_after_validate`、10 个 retryable=false 码）。
- **security — pass**：S1–S7 全部可核可跑；参数全标 [当前值]。should：813 passed 宜写「813 passed / 30 skipped」；术语白话偏弱。
- **contract — blocker**：claims.md C5 与 final-brief 称「工作树没有 lab/app.py」（已从快照恢复，probe 现在即可跑）。should：「1540×1600」应为 1540×1120。
- **runtime — blocker**：RUN1 写「4 处 condition」，compose.yaml 实为 5 处。should：2s/180s 页内加 [当前值]；同上画布尺寸笔误。
- **journey — blocker**：①E2 渲染出 Python dict 乱码（data.yaml 未引号）；②curl 命令被解析成 dict 全毁。should：3024/1205/1317 三码口径统一；≤1 次标 [当前值]。

跨链一致性全过（SQL_REJECTED 不重试、max_attempts=1、16 码分类、12 节点/10 步均一致）；D57 版式合规（4 版本/v4=当前/编撰声明/未知框）；34 条 claims schema 全合法。

## 第 1 轮 · 学生视角（三问 + 愿学/爱学/能学）

**STUDENT-VERDICT: 勉强**。Top5 必改：①旅程 curl 修复；②「今天怎么验」去伪存真（可敲命令+预期）；③删 h1/answer 重复、生产元话、「今晚」时间状语、截断文本；④数字关系句（16 码=6+10、N=correction.max_attempts=1、12 节点 vs 10 步、阈值 1000 语义、16.31s 主语、6 码指路）；⑤术语首现白话 + 安全/运行/旅程补拆一刀或标 [未知]。
三问答题面：N 参数 4/5 链能答；「不能重试」仅纠错/安全/旅程能答（契约/运行本就无重试语义）；「拆掉什么会红」仅纠错/契约能答——安全/运行/旅程缺消融证据。

## probe 补验（真栈，2026-11-27）

主栈实跑（保留运行：init Exited(0) + 5 healthy；dsws-lab-ui 旧栈已 stop、卷保留可恢复）：

- **可转正 6 条**：security S6（SHOW GRANTS 仅 SELECT + UPDATE/INSERT 1142 实证）、S7（真库缺口关闭）、contract C7（S2 fresh 写三存储 VERIFY PASS + 幂等 NOOP）、C5（lab/app.py REGIONS/METRICS grep 实证）、runtime RUN5（180s/2s 常量 + 注入实测）、RUN6（失败停点注入：mysql=0 → init 等待超时 Exited(1)、backend/frontend 从未启动）。
- **维持 verified**：RUN2–RUN4 由 page-13 记录升级为本轮真跑时序（+5s/+22s/+27s/+34s/+39s，docker-smoke 8/8）；纠错 C1/C2/C3 复跑绿。
- **仍缺 4 条**：纠错 C5（需真模型）、C6（N sweep）、契约 C3（隔离消融）、旅程 J8 部分（1205/1317 未真触发、真并发竞态无测试）。
- **抓出矛盾**：J8「2 skipped = 真库用例」不成立——实为 `test_zero_false_positive.py` 两道拒答题的 runtime skip；但 3024→TIMEOUT 真库实测转正。
- **RUN6 nuance**：`--scale mysql=0` 时 compose 把 `service_healthy` 当空满足放行 init，「停在 init 前」由 docker_init 自身 180s 超时兜底（init Exited(1)）——已列入 RUN6 证据说明。

## 修复动作（第 1 轮后）

- 生成器：右页 h1 改问句钩子（`answer_title`），删除「学生可读性：待复核」生产元话。
- `check_spread.py` 加固：BAD-REPR（dict 乱码）/BAD-PARENS（括号未闭合）/BAD-CUT（疑似截断），单测判定正确。
- 批量修订代理按 A（7 blocker）/B（should）/C（学生 Top5）/D（拆一刀缺口如实处理）清单修 data.yaml 与配套件。

## 第 2 轮复审（2026-11-27）

- **学生视角**：**STUDENT-VERDICT: 能学**（上轮「勉强」）。三问五链全答出；Top5 全核实落地；三轴分全面提升（能学 3/3/3/2/2 → 4.5/4/4/4/4）。残余 10 项措辞级（假绿括注串味、12→10 算术、6 码名单、自动 LIMIT 值、命令口径、curl 括注、速查页 foot、前向引用、措辞晦涩）——当轮即修。
- **对抗式**：旧 7 blocker 全部核实修复；但 **FINAL: BLOCKER(10)**——根因单一：probe 转正回填只改 claims.yaml，claim 正文与姊妹件（claims.md/spread 未知框/final-brief）仍写「未跑/待验」，同日相反事实；另 journey E1 由修订引入「界面收敛成 10 步」新错（实为 12 步 + 1 条件步标注，10 是 stage 分组）。
- **处置**：口径同步交回原修订写手（含 E1 改正）；完成后进第 3 轮复审——判据「连续两轮 0 blocker」自此轮起算。

## 第 3 轮复审（2026-11-27）

- **学生终验**：**STUDENT-VERDICT: 能学**（三轮轨迹：勉强 → 能学 → 能学）。三问五链无一卡壳（6 码名单、12/10 算术、自动 LIMIT=1000、curl、阈值语义、16.31s 主语全部消失）；三轴终评：能学 5/4.5/4.5/4.5/4.5，爱学最高 4.5，愿学稳定 3.5–4；速查页 **5/5**。信任感亮点：「[记录]/[代码可证]/[已实证]/[未知]」四档标注体系。残余 7 项措辞级当轮清零。
- **对抗式 R3**：**FINAL: PASS**（R2 十条 blocker 全销账；3 条 should 不阻断）。

## 第 4–6 轮（零阻断计数与锁线）

- **R4**：FINAL: BLOCKER(1)——E3 smoke「8/8 真栈实测」未贯通 runtime 姊妹件（转正只落 spread 侧）。当轮修复六处（claims.md 头注/RUN4 行/§RUN4、final-brief 两行+后续动作、claims.yaml RUN4 probe_note）。
- **R5**：**FINAL: PASS**——smoke 口径六处互恰销账；五链 status 零偏差；每链新抽 1 条 claim 全对；命令实跑一致。（连续零阻断第 1 轮）
- **R6**：**FINAL: PASS**——无改动确认（内容指纹复核）+ 快核全绿 + 实跑 9 passed。（连续零阻断第 2 轮，**锁线**）

**终态**：对抗线 R5+R6 连续两轮 0 blocker；学生线三轮复审「能学」；probe 真栈 6 条转正、4 条缺口如实保留。
