# 真模型纠错实测证据（`deepseek-flash` · 隔离栈 · 24 次真实请求）

> 日期：2026-11-20 07:05:26–07:08:41（Asia/Shanghai）。探针 `system/eval/live_probe.py` + `system/eval/correction_live.jsonl`（8 题 × `--trials 3` = **24 次真实 `POST /api/query`**），exit 0，总耗时 **194.78s**。
> 环境：仓库根起隔离栈 `-p p17live`，端口 mysql `13317` / ES `19217` / qdrant `16317` / backend `18117` / frontend `18097`（额外 `FRONTEND_BIND=127.0.0.1`）。容器内 `HttpLlmGenerator.from_env().name` = **`http-llm`**，模型 `deepseek-flash`（`https://api.deepseek.com/v1`）。
> 栈状态：init `Exited (0)`（日志末行 `DOCKER INIT PASS`）；`curl /api/health` → `200 {"status":"ok","stage":"S7"}`；backend healthy。原始报告：`tutorial/review/llm-live-report.json`。

## 8 题 × 3 次分类

| 题号 | 问法 | 3 次分类 | error_code | 实测细节 |
|---|---|---|---|---|
| live-01 | 查询销售额大于平均销售额的商品 | 校正成功 ×3 | — | 每次 1 次 validate error → `correct_sql=success` → 再 validate 成功 → `run_sql` 成功，5 行 |
| live-02 | 哪个商品品类卖得最好 | 无需校正 ×3 | — | 1 行结果；历史「曾触发校正失败」，本次 3/3 validate 一次过 |
| live-03 | 统计 2025 年第一季度各大区的 GMV | 无需校正 ×3 | — | 5 行结果 |
| live-04 | 各省 GMV 排名 | 无需校正 ×3 | — | 6 行；排名拦截未触发（SQL 原文未采集） |
| live-05 | 品牌销售额 Top 3 | 无需校正 ×3 | — | 3 行；Top-N 拦截未触发（SQL 原文未采集） |
| live-06 | 用 UNION 把两个品类的销售额拼起来 | 无需校正 ×3（拒答） | `LLM_REFUSAL` ×3 | 策略拒绝，不出 SQL |
| live-07 | 各城市销售额 | 无需校正 ×3（拒答） | `LLM_REFUSAL` ×3 | 无 city 粒度，显式拒答 |
| live-08 | 2024 年销售额 | 无需校正 ×3（拒答） | `LLM_REFUSAL` ×3 | 越界时间，显式拒答 |

## totals 与成功率（分母口径）

- `totals = {"correction_success": 3, "no_correction_needed": 21}`；`correction_opportunities = 3`；**`correction_success_rate = 1.0`（3/3）**。
- **分母只在「触发校正」的样本里算**（`correction_success + correction_fail`），**不是 24 次提问全算**：24 次里只有 live-01 的 3 次触发校正，其余 21 次 validate 一次过——12 次正常结果 + 9 次 `LLM_REFUSAL` 拒答（拒答是契约内显式结局，不是 SQL 失败；探针分类器按 `validate_errors=0` 把它归入 `no_correction_needed`）。
- 本次**没有** `correction_fail` / `transport_error` / 401 / 超时；失败类别分母为 0，故**不能**说「失败率 0%」，只能说本次采样没出现。

## 成本

- 24 次真实 `/api/query`；模型生成调用按路径 ≥27 次（live-01 每次多 1 次 `correct_sql` 生成）。**未采集 token 用量**（探针不读 usage），只按请求数计；单次实验，不可当预算基线。

## 可复现命令（本机原样顺序）

```bash
export COMPOSE_PROJECT_NAME=p17live MYSQL_HOST_PORT=13317 ES_HOST_PORT=19217 \
       QDRANT_HOST_PORT=16317 BACKEND_HOST_PORT=18117 FRONTEND_HOST_PORT=18097 FRONTEND_BIND=127.0.0.1
docker compose -p p17live up -d mysql elasticsearch qdrant       # 等三者 healthy
docker compose -p p17live exec -T elasticsearch curl -s -XPUT 'http://127.0.0.1:9200/_cluster/settings' \
  -H 'Content-Type: application/json' -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false}}'
docker compose -p p17live up -d init backend frontend            # init 须 Exited (0)，backend 须 healthy
system/backend/.venv/bin/python system/eval/live_probe.py --target http://127.0.0.1:18117 --trials 3
cp system/eval/live-report.json tutorial/review/llm-live-report.json && git checkout -- system/eval/live-report.json
docker compose -p p17live down -v
```

> 为什么先只起依赖：本机 `/` 已用 90%，ES 默认 low/high watermark 85/90% 会让 init 建索引失败；所以顺序 = 依赖 → 关阈值 → init/backend/frontend。

## 诚实边界

- **单次采样**：8 题 ×3 只是一次实验；换时间/温度/prompt 结果可能变——不许据此写「已修复」「稳定成功」。
- **不可复现**：模型输出有随机性（live-01 三次结果列名 1 次英文、2 次中文），成功率只在本次 194.78s 窗口内成立。
- **不能外推**：只测 DeepSeek `deepseek-flash` + 本机网络/隔离栈；不外推到其它模型、其它机器或页面长时间运行。
- **本证据不等于 ACCEPTANCE 判据**：ACCEPTANCE 与页级考核都不验真模型（见 [`llm-endpoint.md`](llm-endpoint.md) §7）；真模型仍不入验收清单，主线回归仍走确定性一侧 + 录制夹具。
