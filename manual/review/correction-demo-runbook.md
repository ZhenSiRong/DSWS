# 第 17 页 · 自动纠错被触发并成功（真 LLM · 成熟版原版前端）runbook
> 补「校正节点真的亮起来」的动态证据：SSE 原始帧 + 校正中/成功两张图 + 7.5s GIF；只描述现场，不改页面/判据。
> 隔离栈 `p17corr`：mysql 13387 / ES 19287 / Qdrant 16387 / backend 18187 / 教学版 18087；成熟版 nginx 18097。真模型 deepseek-flash（`.env` 注入，勿打印 key）。
## 1. 触发原理（契约，不是玄学）
- `contracts/errors.yaml`：`correction: {max_attempts: 1, revalidate: true, revalidate_with: [guard, policy]}`——只重试一次，且校正后两道关重跑。
- 只对 `retryable: true` 的 6 码触发：SQL_SYNTAX / SQL_UNKNOWN_COLUMN / SQL_UNKNOWN_TABLE / SQL_CONSTANT_PROJECTION / SQL_MISSING_ORDER_BY / SQL_MISSING_LIMIT；SQL_REJECTED 等不可重试码只报错。
- 期望帧序（本次实测 27 帧）：9 个上下文节点各 running/success → generate_sql 2 帧 → validate_sql running+error → correct_sql running+success → validate_sql running+success → run_sql running+success → result。
## 2. 起隔离栈 + 成熟版入口
```bash
export COMPOSE_PROJECT_NAME=p17corr MYSQL_HOST_PORT=13387 ES_HOST_PORT=19287 QDRANT_HOST_PORT=16387 BACKEND_HOST_PORT=18187 FRONTEND_HOST_PORT=18087 FRONTEND_BIND=127.0.0.1
docker compose -p p17corr up -d --no-build mysql elasticsearch qdrant    # 等 3 个 healthy
curl -s -X PUT http://127.0.0.1:19287/_cluster/settings -H 'Content-Type: application/json' -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false}}'
docker compose -p p17corr up -d --no-build init backend                 # init Exited(0) → backend healthy
docker exec p17corr-backend-1 python -c "from app.generate.provider import HttpLlmGenerator; print(HttpLlmGenerator.from_env().name)"  # 必须 http-llm
docker run -d --name p17-mature --network p17corr_default -p 127.0.0.1:18097:80 \
  -v "$PWD/deliverable/v2/original-frontend/dist:/usr/share/nginx/html:ro" \
  -v "$PWD/deliverable/v2/original-frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  "$(grep '^NGINX_IMAGE=' .env | cut -d= -f2)" && curl -s http://127.0.0.1:18097/api/health
```
## 3. 真跑与现场（实测第 1 次尝试即触发，未重试）
- 打开 http://127.0.0.1:18097 → 输入「查询销售额大于平均销售额的商品」→ 发送。
- SSE 旁证：`curl -sN -X POST http://127.0.0.1:18097/api/query -H 'Content-Type: application/json' -d '{"query":"查询销售额大于平均销售额的商品"}'`。
- 原始 SSE：`manual/review/correction-live-trigger.sse`（27 帧 / 2766 B，逐帧保留、无注释行）；generate_sql 13.1s、correct_sql 11.0s、二次 validate_sql 5.9ms、run_sql 18.6ms、全程 25.7s。
- 成功判据：`validate_sql:error` 后出现 `correct_sql:running→success`，其后 `validate_sql:success` + `run_sql:success` + `result`；correct_sql 只 1 轮（=重试 1 次）。
## 4. 界面节点序列与产物
- DOM 实测（同一跑）：生成SQL 执行中 1.5→14.4s → 「校验SQL 红叉(有误) + 校正SQL 转圈(执行中)」14.7→25.6s → 「校验SQL 绿 + 校正SQL 绿 + 执行SQL 绿」25.7s → 结果表 5 行。
- 注意：二次 `validate_sql:running` 仅 5.9ms（<16.7ms 一帧），浏览器从未单独绘制该状态；GIF 以「校验红→校验绿」表达重新校验通过，SSE 第 23–24 帧是硬证据。
- `manual/images/page-17-live-correct.png` 1440×1720：校正成功后（校正SQL 实心绿勾，不是「未触发」）+ 结果表。
- `manual/images/page-17-live-correct-mid.png` 1440×1720（补充）：校验SQL 红「有误」+ 校正SQL 转圈「执行中」+ 执行SQL 灰待。
- `manual/images/page-17-live-correct.gif` 1440×1720 / 50 帧 / 150ms / 7.5s / 0.29MB：逐帧真截图（时间压缩），末帧停结果表。
## 5. 离线兜底（无模型/无网时仍可证明闭环）
```bash
(cd backend && .venv/bin/python -m pytest tests/agent/test_correct.py -q)   # 14 passed
(cd backend && .venv/bin/python -m app.scripts.failures --check)            # only corrected 期望 result 实际 result，S6 PASS
```
## 6. 清理
```bash
docker rm -f p17-mature && docker compose -p p17corr down -v --remove-orphans   # 0 容器/0 卷/0 网络
git checkout -- backend/uv.lock 2>/dev/null; docker ps -aq | sort | wc -l      # 用户栈 24 容器 ID 集合不变
```
