.PHONY: install doctor doctor-v dev-backend dev-frontend stage0 stage0-ui stage1 stage2 stage3 stage4 stage5 stage5-live stage6 stage6-ui stage7 stage7-ui baseline audit verify verify-fast accept-l1 accept-l2 accept-l3 accept-l4 accept-l5 install-hooks docker-env docker-env-require docker-up docker-down docker-logs docker-smoke docker-reset book book-html book-pdf deliverables

install:
	cd system/backend && uv sync --frozen
	cd system/frontend && npm ci

# 第 0 页的完成判据：工具 / 依赖 / 端口一次判完，全 ✓ 才算环境就绪。
# 输出可直接贴进 issue 或截图进手册；失败时逐条给修法。
doctor:
	@bash toolbox/scripts/doctor.sh

doctor-v:
	@bash toolbox/scripts/doctor.sh -v

dev-backend:
	cd system/backend && uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8100 --reload

dev-frontend:
	cd system/frontend && npm run dev

# S0 硬验收：契约测试 + 前端协议单测 + 类型检查/构建（不需要浏览器）
stage0:
	@sh toolbox/scripts/say.sh s0-backend-contract
	cd system/backend && uv run --frozen pytest -q tests/test_s0_contract.py
	@sh toolbox/scripts/say.sh s0-frontend-sse
	cd system/frontend && npm run test
	@sh toolbox/scripts/say.sh s0-frontend-build
	cd system/frontend && npm run build
	@echo "S0 PASS"

# 可选：真实 Chrome 冒烟（自起临时端口 8101/5274，跑完清理）
stage0-ui:
	./toolbox/scripts/stage0-ui.sh

# S1 硬验收：契约 ↔ DDL/数据全绿；旧系统负向夹具必须红；文档必须新鲜
stage1:
	@sh toolbox/scripts/say.sh s1-contract-ddl
	cd system/backend && uv run --frozen python -m app.schema_contract --check
	@sh toolbox/scripts/say.sh s1-negative-fixture
	cd system/backend && uv run --frozen python -m app.schema_contract --expect-legacy-red
	@sh toolbox/scripts/say.sh s1-backend-tests
	cd system/backend && uv run --frozen pytest -q tests/test_s0_contract.py tests/test_s1_schema_contract.py
	@echo "S1 PASS"

# S2 硬验收：dry-run 计划 → --fresh 重建 → --verify 对账 → 第二次构建零写入
# 前置：MySQL/ES/Qdrant 已启动（旧系统 docker compose）；只操作 *_rebuild 目标。
stage2:
	@sh toolbox/scripts/say.sh s2-dry-run
	cd system/backend && uv run --frozen python -m app.build_meta_knowledge --dry-run
	@sh toolbox/scripts/say.sh s2-rebuild
	cd system/backend && uv run --frozen python -m app.build_meta_knowledge --fresh
	@sh toolbox/scripts/say.sh s2-verify
	cd system/backend && uv run --frozen python -m app.build_meta_knowledge --verify
	@sh toolbox/scripts/say.sh s2-idempotent
	cd system/backend && uv run --frozen python -m app.build_meta_knowledge --assert-idempotent
	@sh toolbox/scripts/say.sh s2-backend-tests
	cd system/backend && uv run --frozen pytest -q
	@echo "S2 PASS"

# S3 硬验收：S2 三存储对账 → 20 题真实检索 → CLI YAML → 全量回归
# 前置：MySQL/ES/Qdrant 已启动，且 S2 的 *_rebuild 目标已构建；不执行 stage2 / --fresh。
stage3:
	@sh toolbox/scripts/say.sh s3-verify
	cd system/backend && uv run --frozen python -m app.build_meta_knowledge --verify
	@sh toolbox/scripts/say.sh s3-golden-set
	cd system/backend && REBUILD_INTEGRATION=1 uv run --frozen pytest -q tests/recall
	@sh toolbox/scripts/say.sh s3-cli-yaml
	@sh toolbox/scripts/recall-demo.sh /tmp/rebuild-s3-recall.yaml
	@head -n 40 /tmp/rebuild-s3-recall.yaml
	@sh toolbox/scripts/say.sh s3-backend-tests
	cd system/backend && uv run --frozen pytest -q
	@echo "S3 PASS"

# S4 硬验收：10 题基线（确定性生成 + 静态校验）→ 生成层测试 → 全量回归
# 前置：**不需要** MySQL/ES/Qdrant。S4 只到「生成 + 静态校验」，不执行 SQL；
# 上下文由契约离线裁剪，基线因此可以在任何一台机器上复现。
stage4:
	@sh toolbox/scripts/say.sh s4-baseline
	cd system/backend && uv run --frozen python -m app.scripts.generate --baseline
	@sh toolbox/scripts/say.sh s4-generate-tests
	cd system/backend && uv run --frozen pytest -q tests/generate
	@sh toolbox/scripts/say.sh s4-backend-tests
	cd system/backend && uv run --frozen pytest -q
	@echo "S4 PASS"

# 单独看基线表格（路线图里的 Demo：问题 / SQL / 判定）
baseline:
	cd system/backend && uv run --frozen python -m app.scripts.generate --baseline

# S5 硬验收：AST 级安全策略 + 注入语料 100% 拒绝 + 零误杀
# 前置：**不需要** MySQL。策略只依赖契约与 sqlglot，因此门禁可以在任何
# 一台机器上复现。只读账号与两屏对比需要 MySQL，见 stage5-live。
stage5:
	@sh toolbox/scripts/say.sh s5-policy-gate
	cd system/backend && uv run --frozen python -m app.scripts.security --check
	@sh toolbox/scripts/say.sh s5-corpus-table
	cd system/backend && uv run --frozen python -m app.scripts.security --corpus
	@sh toolbox/scripts/say.sh s5-security-tests
	cd system/backend && uv run --frozen pytest -q tests/security
	@sh toolbox/scripts/say.sh s5-backend-tests
	cd system/backend && uv run --frozen pytest -q
	@echo "S5 PASS"

# S5 实战验收：需要 MySQL —— 开通只读账号、验证它真的写不了、两屏对比
# 前置：MySQL 已启动，dw 库已由 system/fixtures/dw.sql 装载；
#      环境变量 REBUILD_DW_RO_PASSWORD 给出只读账号的密码（不在仓库里）。
stage5-live:
	@sh toolbox/scripts/say.sh s5-provision-ro
	cd system/backend && uv run --frozen python -m app.scripts.security --provision-ro-account
	@sh toolbox/scripts/say.sh s5-verify-ro
	cd system/backend && uv run --frozen python -m app.scripts.security --verify-ro-account
	@sh toolbox/scripts/say.sh s5-two-screen
	cd system/backend && uv run --frozen python -m app.scripts.security --demo
	@echo "S5 LIVE PASS"

# S6 硬验收：错误码表 + 6 类失败场景 + 校正闭环 + 取消
# 前置：**不需要** MySQL / LLM。失败场景由 system/fixtures/failures/scenarios.yaml
# 驱动，校验、安全策略、校正闭环、SSE 协议全都是真代码——只替换了模型与
# 数据库这两个外部依赖，所以 6 类失败既真实又可复现。
stage6:
	@sh toolbox/scripts/say.sh s6-failure-gate
	cd system/backend && uv run --frozen python -m app.scripts.failures --check
	@sh toolbox/scripts/say.sh s6-error-table
	cd system/backend && uv run --frozen python -m app.scripts.failures --table
	@sh toolbox/scripts/say.sh s6-scenario-table
	cd system/backend && uv run --frozen python -m app.scripts.failures --scenarios
	@sh toolbox/scripts/say.sh s6-failure-tests
	cd system/backend && uv run --frozen pytest -q tests/agent
	@sh toolbox/scripts/say.sh s6-frontend-sse
	cd system/frontend && npm run test
	@sh toolbox/scripts/say.sh s6-frontend-build
	cd system/frontend && npm run build
	@sh toolbox/scripts/say.sh s6-backend-tests
	cd system/backend && uv run --frozen pytest -q
	@echo "S6 PASS"

# S6 浏览器验收：6 类失败各一个用例 + 取消
# 前置：需要 Chrome / Edge（Windows 上用 Edge 也行）。
# 场景应用与生产应用共用同一套 HTTP / SSE 管道，只替换模型与数据库。
stage6-ui:
	./toolbox/scripts/stage6-ui.sh

# S7 硬验收：契约生成物新鲜度 + SSE 夹具对账 + 前端契约测试 + 类型检查/构建
# 前置：**不需要** MySQL / LLM / 浏览器。浏览器用例拆到 stage7-ui（沿用
# stageN / stageN-ui 的既有惯例，S0 / S6 都是这么做的）。
stage7:
	@sh toolbox/scripts/say.sh s7-contract-freshness
	cd system/backend && uv run --frozen python -m app.scripts.contracts_gen --check
	@sh toolbox/scripts/say.sh s7-sse-fixture
	cd system/backend && uv run --frozen python -m app.scripts.record_sse --check
	@sh toolbox/scripts/say.sh s7-frontend-contract
	cd system/backend && uv run --frozen pytest -q tests/frontend
	@sh toolbox/scripts/say.sh s7-frontend-sse
	cd system/frontend && npm run test
	@sh toolbox/scripts/say.sh s7-frontend-build
	cd system/frontend && npm run build
	@sh toolbox/scripts/say.sh s7-backend-tests
	cd system/backend && uv run --frozen pytest -q
	@echo "S7 PASS"

# S7 浏览器验收：13 条 F 缺陷各一个用例（回放服务器 + 隔离前端）
# 前置：需要 Chrome / Edge（Windows 上用 Edge 也行）。
stage7-ui:
	./toolbox/scripts/stage7-ui.sh

# ---------------------------------------------------------------------------
# Docker 部署（单机 Compose；详见 materials/docs/DOCKER-DEPLOY.md）
# ---------------------------------------------------------------------------

# 生成 .env：解释器名字在平台之间不一样（Linux/macOS 常见 python3，
# 某些 Windows 环境只有 python）。判定标准是"真的能跑"而不是"名字在 PATH 上"——
# Windows 上 Microsoft Store 的 python3 转发器就属于"存在但一执行就退 49"，
# 挑中它只会以 Error 49 收场。详见 toolbox/scripts/find-python.sh。
docker-env:
	@test -f .env || { \
		PY="$$(sh toolbox/scripts/find-python.sh)" || exit 1; \
		"$$PY" toolbox/scripts/generate_docker_env.py; \
	}

# 只读栈 / 收尾的动作不许顺手生成一份新的 .env。
#
# 生成器写进的是**新的随机密码**：数据卷里 MySQL 的账号还是老密码，
# 容器按新的 .env 连库就是 Access denied，栈起不来——而且没人看得出
# .env 是什么时候被换掉的。缺 .env 就该直接报错。
docker-env-require:
	@test -f .env || { \
		echo "missing .env: run 'make docker-env' first" >&2; \
		exit 1; \
	}

docker-up: docker-env
	docker compose up -d --build

# compose 的变量全部来自 .env，缺了它连 down / logs 都跑不起来。
docker-down: docker-env-require
	docker compose down

docker-logs: docker-env-require
	docker compose logs -f --tail=100

docker-smoke: docker-env-require
	./toolbox/scripts/docker-smoke.sh

docker-reset: docker-env-require
	@sh toolbox/scripts/docker-reset.sh

# ---------------------------------------------------------------------------
# 自动化护栏（retro 决议）：一条命令查完手册 + 工作区卫生
# 详见 materials/docs/checks.md；提交前护栏见 .githooks/pre-commit
# ---------------------------------------------------------------------------

# `make audit`：5 项聚合检查，任一失败即中断并以非 0 退出
# （子命令自身退出码 1；GNU make 对 recipe 失败统一返回 2）。
# 1) 24 页结构 / 图引用 / README 坏链（audit_book.py）
# 2) git diff --check 空白错误
# 3) system/backend/uv.lock 必须与仓库一致（本机 uv 镜像源会按 index 重写 registry URL，
#    而 toolbox/scripts/lab 快照白名单不含它，所以只能靠 git 还原）
# 4) tutorial/ 不得泄露用户名 / 家目录（排除 materials/review/ 证据报告与 *.py 校验脚本）
# 5) 任务台账准确性：done 钉证据 + 依赖/review/甘特身份（task.py check）
audit:
	@echo "== 1/5 structure: 24 pages / images / README links =="
	@python3 toolbox/shots/audit_book.py || { echo "AUDIT FAIL: structural audit failed (see above)"; exit 1; }
	@echo "== 2/5 whitespace: git diff --check =="
	@git diff --check; rc=$$?; \
		if [ $$rc -ne 0 ]; then echo "AUDIT FAIL: git diff --check found whitespace errors (fix and rerun)"; exit 1; fi; \
		echo "  OK: no whitespace errors"
	@echo "== 3/5 uv.lock: not rewritten by uv =="
	@if ! git diff --quiet -- system/backend/uv.lock || ! git diff --cached --quiet -- system/backend/uv.lock; then \
		echo "AUDIT FAIL: system/backend/uv.lock was rewritten (uv rewrites registry URLs; lab snapshots do not cover it)"; \
		echo "  Fix: git checkout -- system/backend/uv.lock"; \
		echo "  (if staged: git restore --staged --worktree system/backend/uv.lock)"; \
		exit 1; \
	else echo "  OK: system/backend/uv.lock matches the repository"; fi
	@echo "== 4/5 secrets: tutorial/ must not contain zhensirong or /home/ =="
	@hits=$$(grep -rnIE 'zhensirong|/home/' tutorial --exclude='*.py' 2>/dev/null); rc=$$?; \
		if [ $$rc -eq 0 ]; then \
			echo "AUDIT FAIL: tutorial/ contains local username or home path (student material must not ship it)"; \
			echo "$$hits"; \
			echo "  Note: materials/review/ reports and *.py checker/generator scripts are excluded (see materials/docs/checks.md)"; \
			exit 1; \
		elif [ $$rc -ne 1 ]; then \
			echo "AUDIT ERROR: secret scan failed (grep rc=$$rc)"; exit 1; \
		fi; \
		staged=$$(git diff --cached --name-only --diff-filter=ACMR -- tutorial | grep -Ev '\.py$$'); \
		for f in $$staged; do \
			hit=$$(git show ":$$f" 2>/dev/null | grep -nIE 'zhensirong|/home/'); \
			if [ -n "$$hit" ]; then \
				echo "AUDIT FAIL: staged manual file contains a secret: $$f"; \
				echo "$$hit"; exit 1; \
			fi; \
		done; \
		echo "  OK: tutorial/ has no secrets"
	@echo "== 5/5 task ledger: done evidence + dependencies/review/gantt identity =="
	@python3 toolbox/scripts/task.py check --quick || { echo "AUDIT FAIL: task ledger drift (done without evidence/review, or stale gantt; see above)"; exit 1; }
	@echo "AUDIT PASS: 5/5 green (structure / whitespace / uv.lock / secrets / ledger)"

# 新手册：tutorial/ 正典 → 自包含 HTML + A4 PDF（管线在 toolbox/book/）
BOOK_OUT := materials/deliverable/tutorial-book

book: book-plates book-pdf book-html

book-plates:
	@python3 toolbox/book/build_city_stages.py
	@python3 toolbox/book/build_city_plates.py

book-visuals:
	@python3 toolbox/book/build_book_visuals.py

book-html: book-plates book-visuals
	@if [ -f $(BOOK_OUT)/page-map.json ]; then \
		python3 toolbox/book/build_manual.py --html --page-map $(BOOK_OUT)/page-map.json --out $(BOOK_OUT); \
	else \
		python3 toolbox/book/build_manual.py --html --out $(BOOK_OUT); \
	fi

book-pdf: book-plates book-visuals
	@python3 toolbox/book/build_manual.py --print-html --out $(BOOK_OUT)
	@uv run --offline --with weasyprint python3 toolbox/book/render_pdf.py $(BOOK_OUT)/.print.html $(BOOK_OUT)/tutorial-book.pdf
	@python3 toolbox/book/extract_page_map.py $(BOOK_OUT)/tutorial-book.pdf $(BOOK_OUT)/page-map.json
	@python3 toolbox/book/build_manual.py --print-html --page-map $(BOOK_OUT)/page-map.json --out $(BOOK_OUT)
	@uv run --offline --with weasyprint python3 toolbox/book/render_pdf.py $(BOOK_OUT)/.print.html $(BOOK_OUT)/tutorial-book.pdf
	@python3 toolbox/book/extract_page_map.py $(BOOK_OUT)/tutorial-book.pdf $(BOOK_OUT)/page-map.json
	@rm -f $(BOOK_OUT)/.print.html
	@rm -rf $(BOOK_OUT)/assets

# 教材可跟随性验收线（ADR 0002 / materials/docs/verify-line.md）
# T0：静态，不执行页面命令（pre-commit 调）；T1：加跑 kind: offline 命令。
verify:
	@python3 toolbox/scripts/verify.py

verify-fast:
	@python3 toolbox/scripts/verify.py --fast

# T2：级考核（复用 ACCEPTANCE.md；需整栈已起，破坏性步骤打印 MANUAL，不自动执行）
accept-l1:
	@bash toolbox/scripts/acceptance/level-l1.sh
accept-l2:
	@bash toolbox/scripts/acceptance/level-l2.sh
accept-l3:
	@bash toolbox/scripts/acceptance/level-l3.sh
accept-l4:
	@bash toolbox/scripts/acceptance/level-l4.sh
accept-l5:
	@bash toolbox/scripts/acceptance/level-l5.sh

# 启用仓库级 pre-commit 护栏：只写本仓库 git 局部配置，不动全局配置。
install-hooks:
	@test -x .githooks/pre-commit || { echo "Missing executable .githooks/pre-commit: git checkout -- .githooks/ or chmod +x .githooks/pre-commit" >&2; exit 1; }
	@git config core.hooksPath .githooks
	@echo "Enabled: core.hooksPath=.githooks (this repository only)"
	@echo "  pre-commit checks: 24-page structure / system/backend/uv.lock / staged manual secrets / task ledger / page contract T0 (verify.py --fast)"
	@echo "  Temporary bypass (not recommended): git commit --no-verify"
	@echo "  Disable: git config --unset core.hooksPath"

# PRD 三类交付物：设计文档 / 源码 / 教程文档，各自打包
deliverables:
	@python3 toolbox/scripts/build_deliverables.py
