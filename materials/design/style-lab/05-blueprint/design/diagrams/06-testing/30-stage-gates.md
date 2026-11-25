# 30 · S0–S7 阶段门禁

**一句话**：每个阶段都有一条 `make stageN` 硬命令；命令最后打印 `S0 PASS`…`S7 PASS` 才算过，PASS 后才允许进入下一阶段。

**这张图回答**：每个阶段跑什么？「通过」的判据是什么？哪两个阶段需要先起三存储？

**图例**：蓝色=离线门禁；青色=需要三存储（S2 / S3）。

**关键元素**：

| 阶段 | 硬验收命令 | 「通过」判据 |
|---|---|---|
| S0 | `make stage0` | 契约测试 + 前端单测 + 前端构建全绿，打印 `S0 PASS` |
| S1 | `make stage1` | 契约 ↔ DDL ↔ 数据全绿；旧系统负向夹具必须红；打印 `S1 PASS` |
| S2 | `make stage2` | `--dry-run` → `--fresh` → `--verify` 通过；`--assert-idempotent` 输出 `NOOP: 0 writes`；打印 `S2 PASS` |
| S3 | `make stage3` | S2 目标 `--verify` 通过；20 题黄金集集成测试通过；CLI 产出 YAML；打印 `S3 PASS` |
| S4 | `make stage4` | 10 题基线全过 + 静态校验；生成层测试全绿；打印 `S4 PASS` |
| S5 | `make stage5` | 注入语料 100% 拒绝 + 零误杀；安全层测试全绿；打印 `S5 PASS` |
| S6 | `make stage6` | 16 个错误码 + 6 类失败 + 取消；失败层与前端 SSE / 构建全绿；打印 `S6 PASS` |
| S7 | `make stage7` | 生成物新鲜度 + SSE 夹具逐字对账 + 前端契约 / 单测 / 构建全绿；打印 `S7 PASS` |

- 可选变体：`stage0-ui` / `stage6-ui` / `stage7-ui` 需要 Chrome 或 Edge；`stage5-live` 只需要 MySQL 与 `REBUILD_DW_RO_PASSWORD`。
- S2 / S3 之外的阶段都可以在没有任何存储的机器上重复；S2 / S3 的前置写在 `Makefile` 注释里。

**证据**：
- `Makefile` L14–L25（S0）、L28–L35（S1）、L38–L50（S2）、L53–L64（S3）、L67–L76（S4）、L83–L106（S5 与 live）、L112–L133（S6 与 UI）、L138–L157（S7 与 UI）。
- `docs/SETUP-FROM-SCRATCH.md` §3 L835–L847：阶段 / 命令 / 是否需要三存储 / 核心验收。
- `README.md` L15–L23：S0–S7 的验收摘要；L25：当前测试口径。
- `backend/tests/` 的子目录与 `scripts/stage*-ui.sh` 的实际端口。

**边界**：所有 `stageN` 目标与判据都能在 `Makefile` 里逐字指认（✅ 文件事实）；但「某次运行打印了 S0 PASS」属于他机记录，本工作树**没有**重跑，标 🟡。测试计数存在口径冲突：`README.md` / `docs/DOCKER-HANDOFF.md` 说 782 passed，`docs/SETUP-FROM-SCRATCH.md` §3 说 665 passed——图里因而不写死总测试数，只写判据。S8 尚未实现（⚪）。
