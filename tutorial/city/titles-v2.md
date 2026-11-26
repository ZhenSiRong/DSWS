# 23 页「问题 + 方案」标题草案（D45 · 城市隐喻）

> 这是**标题草案**：确认后再改十页正文 H1；正文、SPEC、completeness、maturity 一律不动。
> 依据：`materials/humen-desicions/09-ablation-course.md` D44（造 → 换 → 审 → 守，10+4+4+5 = 23 页）与 D45（标题统一「问题 + 方案」，先出样例再全量替换）；设施 / 道路单源见 [data.json](data.json)，城市地图见 [city-map.html](city-map.html) 与 [成图](../images/city-map-l1.png)。
> 级的口径：L1 造 = 从无到有；L2 换 = 真的假不了；L3 审 = 机器靠不靠谱；L4 守 = 出了事兜不兜得住。本表由 `python3 tutorial/shots/render_city_map.py` 从 data.json 生成，改标题只改 data.json。

| 页码 | 级 | 问题 | 方案 | 判据摘要 |
|---|---|---|---|---|
| P0 | L1 造 | 没工具、没依赖、端口还被占，怎么开工？ | 装齐工具依赖，腾出 3307 / 8000 / 8081 | `make doctor` 末行 `12/12 通过`，三个端口行全 ✓ |
| P1 | L1 造 | 连仓库都还没有，数据往哪儿放？ | 起一个只开给本机 3307 的空库容器 | `SELECT VERSION()` 回 8.0 开头；`SHOW DATABASES` 只有 4 个系统库，没有 `dw` |
| P2 | L1 造 | 空库空空如也，来了问题无货可取？ | 导入 dw.sql：隔 5 个分区、灌 115 行库存 | `SHOW TABLES` 5 张齐；`COUNT(*) = 115`；华北 19 单 |
| P3 | L1 造 | 货备好了，谁来常驻值班接问题？ | 把 uvicorn 跑在 8000，先让 /health 回 ok | `curl /health` 回 `{"ok":true}`，进程停在 `Uvicorn running` |
| P4 | L1 造 | 问题从哪儿递进系统？ | 开一个窗口收 JSON，先把收发修通 | 两次 `POST` 回同一串固定 JSON（`question` 写死也不变） |
| P5 | L1 造 | 一句话里哪几个词才算数？ | 纯字符串规则抽出「地区 + 指标」 | 「华北销售额」→ `["华北","销售额"]`；「的 / 多少」不进词表 |
| P6 | L1 造 | 凭什么规矩把关键词拼成 SQL？ | 照契约拼出带 JOIN 的 SELECT（只 print） | 指标 `SUM(order_amount)`、带 `JOIN`、地区 `'华北'`、有 `GROUP BY` |
| P7 | L1 造 | SQL 拼好了，谁去仓库真取货？ | pymysql 把 SQL 交给 MySQL:3307 执行 | `rows[0].sales` 是不带引号的数字 `41099.5` |
| P8 | L1 造 | 答案一口气砸下来，中间在干什么看不见？ | 12 条 progress 一条条推，最后 1 条 result | `curl -N` 数到 12 条 `progress` + 1 条 `result`，`sales = 41099.5` |
| P9 | L1 造 | 市民怎么从城门口走到服务中心？ | 8081 反代 8000，页面用 EventSource 接流 | 浏览器 8081 点「问一句」停在 `41099.5`；删掉 nginx 主干仍活 |
| P10 | L2 换 | 只有演示数据，凭什么说真的假不了？ | 把自己的数据域换进 system/fixtures/dw.sql，同步契约的行数 / 总额 / 日期域，再重建元知识 | `make stage1` → `S1 PASS`；`make stage2` → `S2 PASS`（dry-run→fresh→verify→幂等） |
| P11 | L2 换 | 契约内联在页面里，改一处别处不知道，真的假不了吗？ | 换成 system/contracts/ 四份契约当唯一事实源：改契约 → 重生成 → 查新鲜度 | `contracts_gen --check` → `S7 CONTRACT GEN PASS`（3 个文件与契约一致） |
| P12 | L2 换 | root 直连的 pymysql 太裸，真的假不了吗？ | 换成只读执行器：策略先行 → 执行 → DECIMAL / DATE 归一化 → 自动 LIMIT / 超时 | `pytest -q tests/security/test_executor.py tests/agent/test_values.py` → `31 passed` |
| P13 | L2 换 | 手工 docker run 换台机器就散了，真的假不了吗？ | 换成 compose 六服务 + 一键 smoke：健康门控、一次性 init、nginx 关缓冲 | `make docker-up` → `make docker-smoke` → `DOCKER SMOKE PASS`（8 步 + init 幂等） |
| P14 | L3 审 | 召回空了，机器靠不靠谱凭什么由它说了算？ | 用 20 题检索黄金集预注册三条判据（该命中 / 不该出现 / 规模上限），再停 ES 看哪些题变红 | `make stage3` → `S3 PASS`；离线 `pytest -q tests/recall` → `18 passed, 23 skipped`；停 ES 后线上答案照旧 |
| P15 | L3 审 | 确定性生成器和 LLM 同题不同答，机器靠不靠谱怎么量？ | 同一组 10 题基线先确定性跑、再切 LLM 跑，写清哪个可复现、哪个必须多次采样 | `make stage4` → `S4 PASS`；`generate --baseline` → `基线：10/10 通过（拒答 2）` |
| P16 | L3 审 | 错误的 SQL 会不会直接执行，机器靠不靠谱谁来拦？ | 摊开生成与执行之间的闸：单语句 / 只读 / 白名单 / 常量投影 / ORDER BY / LIMIT，16 个错误码配「该给谁看」 | `make stage5` → `S5 PASS`；`failures --check` → `S6 PASS`（9 场景 + 16 码） |
| P17 | L3 审 | 重试一次就信了，机器靠不靠谱？ | 把纠错当一次有上限的赌博审：只重试 1 次、必须重新校验、只对可重试错误生效 | `make stage6` → `S6 PASS`；`test_correct.py` → `14 passed`；拆检索后结局变 `SQL_UNKNOWN_COLUMN` |
| P18 | L4 守 | 谁都能进仓库拿货，出了事兜不兜得住？ | 开通只读账号 dw_reader，把「只读」从提示词搬进数据库权限，亲手验证它写不了 | `make stage5-live` → `S5 LIVE PASS`；`--verify-ro-account` 写操作被拒 |
| P19 | L4 守 | 36 条注入要全拒、11 条正常要零误杀，出了事兜不兜得住？ | 用注入语料审六道 AST 拦截，理解 UNION / 可执行注释为什么要整类拒 | `security --check` → `36/36 拒绝 + 11/11 放行 + 8/8 基线` |
| P20 | L4 守 | 点了停止系统还在跑，出了事兜不兜得住？ | 让取消成为独立状态（不是 done、不是 failure）：服务端真停下、发 CANCELLED、界面标已取消 | `make stage6-ui` 浏览器 6 类失败 + 取消；离线 `pytest` → `40 passed` |
| P21 | L4 守 | 出了事不知道错在哪一步，兜不兜得住？ | 把 12 条 progress、/api/steps + /api/errors 目录、14 条录制夹具当观测面，划清应用层观测 ≠ 运维可观测 | `make stage7` → `S7 PASS`；`record_sse --check` → `S7 SSE RECORD PASS（14 个夹具）`；`npm test` → `40 passed` |
| P22 | L4 守 | 一套门禁真的能替你值班、兜住退化吗？ | 把 8 步 smoke + stage0–7 当值班网，逐条说清每条防哪类退化；拆只读账号看第 7 步是否红 | `make docker-smoke` → `DOCKER SMOKE PASS`；`pytest -q` → `813 passed, 30 skipped`；`npm test` → `40 passed` |
