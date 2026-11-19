# 附录 · 真 LLM 端点配置（`REBUILD_LLM_*`，可选支线）

> **附录，不算 24 页。** 主线不配 key 也能全绿；本附录只给"想跑真模型支线"的同学：怎么配、怎么自检、怎么降级。

## 1. 这页解决什么 / 不解决什么

- **解决**：把 `.env` 里四个 `REBUILD_LLM_*` 填对 → 用 `scripts/llm_check.py` 自检 → 重启 backend 确认切换生效；失败时按状态码定位。
- **不解决判据**：主线判定用确定性生成器 + 录制夹具（p15 基线、p17 纠错、ACCEPTANCE 全清单）。配 key 不改变任何一条判据；真模型成功态不可复现（见 §7）。
- **不配 key 时一切照旧**：`backend/app/main.py` 的 `_build_generator()` 拿不到三个非空变量就返回 `DeterministicGenerator`，页面、基线、验收都不变。
- 一个例外要知道：**配了坏 key 不会自动退回确定性生成器**——每个请求会以有名字的失败结束（见 §6），所以先自检再重启。

## 2. 四个变量 + 放哪

| 变量 | 必填 | 作用 |
|---|---|---|
| `REBUILD_LLM_BASE_URL` | 是 | 端点根地址；代码自动拼 `/chat/completions`（§3） |
| `REBUILD_LLM_API_KEY` | 是 | Bearer 认证的 key |
| `REBUILD_LLM_MODEL` | 是 | 模型名；不同厂商不能混用，先 `--models` 看清单（§4） |
| `REBUILD_LLM_TIMEOUT` | 否 | 超时秒数，默认 30；本机轻量请求 0.26–0.57s、带长提示词的生成 2.6s，30 够用 |

- **只写进仓库根 `.env`**（`make docker-env` 从 `.env.example` 生成，已被 `.gitignore`）。**不要**写进命令、页面、截图、提交、聊天记录——key 只该出现在 `.env` 里。
- 容器读 `.env`：Compose 每次重新读；改完 `docker compose up -d --force-recreate backend`（或 `make docker-up`）。
- 宿主 shell 读 `.env`：`source scripts/export-docker-env.sh`（会把 `REBUILD_LLM_*` 导出到当前 shell）；最小做法 `set -a; . ./.env; set +a`（值里有 `$` 时优先用脚本）。
- 读取点：`backend/app/generate/provider.py` 的 `HttpLlmGenerator.from_env()`，**三个非空才启用**，`TIMEOUT` 缺省 30。

## 3. 端点形状（OpenAI 兼容）

代码发的是 `POST {base_url}/chat/completions`，body `{model, temperature, messages}`，头 `Authorization: Bearer <key>`。所以 `base_url` 要带版本段（`/v1` 或 `/api/v3`），**不要再带 `/chat/completions`**（会拼成两份）。下面四类是示例，以你账号实际为准：

| 厂商 / 本地服务 | `REBUILD_LLM_BASE_URL` 示例 | `REBUILD_LLM_MODEL` 示例 |
|---|---|---|
| 火山方舟 Ark | `https://ark.cn-beijing.volces.com/api/v3` | 接入点 `ep-xxx` 或模型名 |
| DeepSeek（**本机实测**） | `https://api.deepseek.com/v1` | `deepseek-flash`（先 `--models` 确认） |
| 本地 Ollama | `http://127.0.0.1:11434/v1` | `llama3.1` |
| 本地 vLLM | `http://127.0.0.1:8000/v1` | 按 vLLM 启动参数里的模型名 |

- 本地两例用于 **`make dev-backend` 在宿主机直跑 backend** 时；`make docker-up` 的 backend 在容器里，容器内的 `127.0.0.1` 是容器自己——要么换成容器可达的地址（Docker Desktop 可试 `host.docker.internal`；Linux 默认没有这个名字），要么先在宿主机这一侧用本附录验证。
- Ark / Ollama / vLLM 三类**未在本机验证**（本机只实测了 DeepSeek）；形状对不代表你的账号/网关一定通，跑完 §4 才算数。

## 4. 连通性自检（先跑它，再跑页面）

**第 0 步：先列模型，再填 `REBUILD_LLM_MODEL`。** 模型名不要猜：

```bash
source scripts/export-docker-env.sh
python3 scripts/llm_check.py --models
```

本机实测（2026-11-19，DeepSeek；两次运行）：`status=200 latency=0.27–0.31s models=deepseek-flash, deepseek-v4-pro`。清单里没有的名字别填——换厂商要同时换 base_url 和 model，**不同厂商的模型名不能混用**。

**第 1 步：dry-run（默认；不联网、不花钱）**——只查四个变量、URL 形状、超时数字，缺什么就打印"怎么补"：

```bash
python3 scripts/llm_check.py
```

全齐且形状合法时末行是 `READY：…（dry-run 没有发请求）`，退出码 0；否则退出码 1 并列出缺哪个变量、怎么补。

**第 2 步：`--live`（真的发 1 条，会计费）**——POST 最小请求 `messages:[{"role":"user","content":"ping"}]`、`max_tokens=1`，打印状态码 / 模型 / 耗时 / 字节数 / 返回字符数；401、404、超时、DNS 各自分类并给排查步骤。**任何路径都不打印完整 key，只显示前 4 位**：

```bash
python3 scripts/llm_check.py --live
```

本机实测（DeepSeek；两次运行）：`status=200 latency=0.57s / 0.87s bytes=531 model=deepseek-flash reply_chars=0`。`reply_chars=0` 不是失败：推理型模型把预算花在 `reasoning_content` 上，本检查只看连通与认证，不看内容。

## 5. 如何确认生效

先重启 backend，再在容器里看生成器是否真的切成 `http-llm`（只打印名字，不打印 key）：

```bash
docker compose up -d --force-recreate backend
docker compose exec backend python -c "from app.generate.provider import HttpLlmGenerator; print(HttpLlmGenerator.from_env().name)"
```

打印 `http-llm` = 三个变量都进了容器；报 `ValueError` = 还缺变量，回 `.env` 补齐再重启。

> 别在 `/api/query` 的结果里找生成器名字：当前版本没有把 `generator.name` 写进结果。要更硬的证据，用"坏 key 一定会犯的错"：把 `_API_KEY` 改成坏值、重启、问一句，应看到 `生成阶段失败：…` 的 `INTERNAL_ERROR`（有名字的失败，不会静默放行）；换回真 key 再问，恢复。

真跑一次（本机，2026-11-19，`deepseek-flash`）：用书架里的 `HttpLlmGenerator` 走 `generate("华北销售额")` → `outcome=sql`、`guard_ok=True`、2.57s；同一实现问「平均客单价」0.79s。两题都只是**一次采样**，不是"稳定成功"（§7）。

## 6. 降级与排错（自检已经替你分类）

| 现象 | 多半是 | 怎么办 |
|---|---|---|
| `401` / `403` | key 错、过期、没权限 | 重新生成 key，只改 `.env` 的 `_API_KEY`；确认没把模型名填进 key |
| `404` | base_url 少了 `/v1` / `/api/v3`；或模型名不存在 | 对齐 §3；先 `--models` 看清单 |
| 请求超时 | 网络慢、本地模型加载中、代理拦截 | 调大 `REBUILD_LLM_TIMEOUT` 再试一次；`curl -sS -m 5 <base>` 看通不通（别带 key） |
| DNS 失败 / 连接被拒 | 主机名错；本地服务没起；容器内 `127.0.0.1` 不是宿主机 | 按 `--live` 打印的排查项走；本地模型先确认端口和监听地址 |
| 限流 / `429` | 调用太密集 | 等一会儿，**不要连点**：每次 `--live`、每次提问都发一次请求 |

- **运行期失败不是"悄悄换回模板"**：模型返回非 JSON / 不合 `sql_or_refusal` → 降级为**拒答**（`INVALID_OUTPUT`）；连不上 / 401 / 超时 → 生成阶段 `INTERNAL_ERROR`。两种都是有名字的失败，`check_sql` 与策略闸照样在。
- 不配 key 时 `DeterministicGenerator`，一切照旧；`REBUILD_LLM_TIMEOUT` 只管真模型请求，超时后该请求按上面的 `INTERNAL_ERROR` 收尾。

## 7. 诚实边界

- 真模型成功态**不可复现**：本机这一次出了能过 `check_sql` 的 SQL，不代表每次、每台机器都行。结论只能写「多次采样（`trials>=3`）+ 成功率 + 失败分类」，不许写「已修复」（p17 对账；`eval/live_probe.py` 是采样探针，要跑着的服务 + 真 key）。
- **本附录不改变 ACCEPTANCE 任何判据**：真模型仍不在验收清单里；主线回归仍用确定性一侧 + 录制夹具。
- 本机只实测了 DeepSeek + `deepseek-flash`；Ark / Ollama / vLLM 是形状示例，未在本机验证。
- 真模型纠错实测证据（2026-11-20，隔离栈，8 题 × 3 次 = 24 次真实请求）：[`llm-live-probe.md`](llm-live-probe.md)。

## 8. 成本提示

- `--live` 一次只发 1 条 `ping`（`max_tokens=1`），花费很小；但**不要在页面、CI、回归脚本里反复跑**，也别写成"每次提问前先跑"。
- 真模型支线跑通即可；日常验证回到 `make stage4` / `make baseline` 的确定性一侧。
