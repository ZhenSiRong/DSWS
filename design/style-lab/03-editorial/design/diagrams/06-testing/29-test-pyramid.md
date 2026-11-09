# 29 · 测试金字塔与三存储依赖

**一句话**：绝大多数测试离线可跑；需要三存储的只有 S2 构建、S3 召回和 Docker 全栈 smoke，S5 实战只要 MySQL。

**这张图回答**：五层测试各自覆盖什么？哪一层开始需要 MySQL / ES / Qdrant？哪些是「本机就能重复」的门禁？

**图例**：绿色=无需三存储；青色=需要三存储；橙色=夹具驱动的场景测试；蓝色=契约；灰色=浏览器 / 全栈端到端边界。

**关键元素**：
- 单元：`tests/generate`、`tests/security`、`tests/agent`（不含 scenarios）、`tests/recall` 的纯逻辑测试、顶层脚本测试（`test_docker_*`、`test_smoke_checks` 等）——用假连接或纯函数，不连存储。
- 契约：`tests/test_s0_contract.py`、`tests/test_s1_schema_contract.py`、`tests/frontend/` 的生成物 / SSE 夹具 / 类型保真，以及 `test_contract_alignment`、`test_error_alignment`。
- 场景：`tests/agent/test_scenarios.py` 跑 `fixtures/failures/scenarios.yaml`；只替换模型与数据库，校验、策略、校正、SSE 都是真代码。
- 集成：`tests/recall/test_golden.py` 的真实检索用例必须 `REBUILD_INTEGRATION=1`；否则跳过（文档口径：31 条跳过里 23 条是 S3 真实存储集成）。
- 端到端：`stage0-ui` / `stage6-ui` / `stage7-ui` 自起临时后端与前端（8101/5274、8102/5275、8103/5276），不需要三存储；`docker-smoke` 需要整套 Compose。
- S5 实战：`make stage5-live` 只要 MySQL，用于开通并验证 `dw_reader`。

**证据**：
- `README.md` L28–L29：`stage2` / `stage3` 需要三存储；`stage4`–`stage7` 完全离线；UI 门禁需要 Chrome 或 Edge。
- `Makefile` L38–L64（S2 / S3 前置）、L67–L76（S4 明确不需要三存储）、L83–L106（S5 离线门禁与 `stage5-live`）。
- `backend/tests/recall/test_golden.py` L111–L125：`REBUILD_INTEGRATION=1` 才跑真实 ES/Qdrant/Meta。
- `scripts/stage0-ui.sh` L10–L12、`scripts/stage6-ui.sh` L21–L23、`scripts/stage7-ui.sh` L21–L23：临时端口，避开 dev 服务。
- `docs/SETUP-FROM-SCRATCH.md` §3 表 L835–L847：每阶段是否需要三存储。
- `backend/tests/` 目录结构（本次 `find` 实际读取）。

**边界**：本工作树只做了图源与渲染，没有跑任何测试；「782 passed / 31 skipped」来自 README / HANDOFF（🟡），`SETUP-FROM-SCRATCH.md` §3 另写「665 passed / 31 skipped」（🟡，已过期，两处口径不一致）。真实三存储集成与 Docker smoke 在本机标 ⚪。
