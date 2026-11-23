VERDICT: pass

# v1 核心复验（第三轮）· 教材可跟随性验收线（T0/T1）

- 基线：`continue-iterate` @ 75529ba（工作区脏）。复验目标 sha256 审查前后不变：verify.py `04e0ad6d…`、contract `fc3e4265…`、README `131d44cc…`、page-17 `77a6851c…`、test `a19268f2…`、docs `ca829385…`。只改本报告；未提交、未启 docker；临时副本已清理。
- 结论：② 的原始假绿已闭合，①③ 维持已修状态；T0/T1 真跑全绿、文档/单测同步，本轮判 **pass**。

## 关键复验（每项自己跑）

1. **② 原始复现（定向）**：页内别处仍有 `14 passed`/`S6 PASS` 的前提下，只改「你应该看到」`text` 围栏（`14 passed in 0.11s`→`15 passed…`、`S6 PASS`→`S7 PASS`，/tmp 副本）→ `python3 scripts/verify.py --fast` **exit 1**：`✗ [out] 契约块 p17-pytest-correct：verify-out 围栏里找不到关键输出 '14 passed'…`（共 4 条 [out] 失败）。旧假绿已闭合。
2. **verify-out 机制负向**：删掉注解中单个 marker → `--fast` exit 1，报「页面缺少 `<!-- verify-out: p17-pytest-correct -->` 注解」；T1 要求 token 在真实输出（单测 + temp 复现，输出不一致 exit 1 并打印真实输出）。`verify-out` 只在 `text` 围栏内容里匹配，页面别处出现不算——与 README 新增小节一致。
3. **注解版提交候选**：按 `HEAD + 8 verify + 2 verify-out` 生成（main 输出围栏 4 marker，拆一刀围栏 1 marker）→ 与 HEAD diff **恰好 +10 行**，temp 内 `--fast` exit 0、默认 T1 `4/4 offline` PASS。当前 `git diff --cached` 为空（未暂存），提交时按此暂存即可；工作区 `131/17` 的 reading-layer 改写不进本 commit。
4. **正常线**：`--fast` → `T0 PASS` 0.01s exit 0；默认 → `T1 PASS` 10.57s，4/4 offline，证据 WARN×2，exit 0；`--strict` → 9.98s exit 1（WARN 2 条、`strict` 标签各一次）；`--list` 显示 `page_contains=N` 与 ablation note；`--json` 纯 JSON；`--page 17/page-17` exit 0、`page-99` exit 2。
5. **单测**：`python3 scripts/tests/test_verify.py` → `Ran 33 tests … OK`，0.296s（新增 verify-out 缺失/锚定/围栏改动/T1 输出不一致用例）。

## 残余非阻塞（建议后续，不影响 v1 done）

- 证据 WARN/CI mtime：默认 2 条 warn、`--strict` 才 fail；CI 新 clone 的 mtime 会被 checkout 抹平（README 已写明，未接 strict）。
- symbols pattern 未锚定：`def propose_correction` 改名 `propose_correction_v2` 仍 PASS；建议加 `\(` 或锚点。
- Ctrl+C 不杀子进程：仅超时走 killpg（超时杀进程组已验证）；打断长块可能留子进程。
- 文档小口径：docs「单块超时上限 60s」未在代码强制（`DEFAULT_TIMEOUT_SEC=120`）；T1 `--strict` 也升「证据缺失」，docs L28 只写 T0 缺失/T1 过期；README `page_contains` 行「页面里必须可见」宜改为「verify-out 围栏内可见」。
- 死 verify-out 注解（marker 不在契约）会被静默忽略，无告警；不影响判定，可按需加校验。

## 真跑清单

- `python3 scripts/verify.py --fast` → exit 0（脚本 0.01s / wall 0.10s，不执行命令）。
- `python3 scripts/verify.py` → exit 0（10.57s，4/4 offline：1.4/3.1/1.3/4.8s，WARN×2）；`--strict` → exit 1（9.98s）。
- `python3 scripts/tests/test_verify.py` → 33 tests OK 0.296s；`--json` 纯 JSON；`--list`、`--page` 变体按预期。
- 负向（/tmp）：定向 text-fence 改词 → exit 1；删 verify-out marker → exit 1；T1 输出不一致 → exit 1；全绿路径经三份临时副本复现。
- 未跑：T2 级考核、pre-commit 实调、GitHub Actions；p17 4 个 manual 块与真实拆一刀消融（按设计不跑）；未提交、未启 docker。
