#!/usr/bin/env python3
"""llm_check.py —— OpenAI 兼容端点自检；任何路径都不打印完整 Key。

默认 dry-run：只查环境变量与 URL 形状，不联网、不花钱。
--models：GET {base}/models 列模型名（先列模型，再填 REBUILD_LLM_MODEL）；
--live：POST 1 条最小 chat 请求（通常 ~1 token，会计费）。
读环境变量、不读 .env：先 source toolbox/scripts/export-docker-env.sh 再跑；退出码 0 通过、1 失败。
为什么不用 requests：跟 toolbox/scripts/find-python.sh 一样，宿主机脚本只用标准库——先保证任何一台
能跑 make docker-env 的机器都跑得动，自检本身不能变成新依赖。
"""
from __future__ import annotations

import json, os, socket, ssl, sys, time
import urllib.error, urllib.parse, urllib.request

REQUIRED = ("REBUILD_LLM_BASE_URL", "REBUILD_LLM_API_KEY", "REBUILD_LLM_MODEL")
FIX_HINT = """怎么补（只改 .env，别写进命令 / 页面 / 截图 / 提交）：
  1) 没有 .env 先 make docker-env；2) 在 .env 填 REBUILD_LLM_BASE_URL / _API_KEY / _MODEL（可加 _TIMEOUT）
  3) source toolbox/scripts/export-docker-env.sh（最小做法：set -a; . ./.env; set +a）；4) 重跑本脚本"""
NET = {
    "timeout": ("请求超时", "端点太慢或网络不通：把 REBUILD_LLM_TIMEOUT 调到 60 再试；本地模型可能还在加载；用 curl -sS -m 5 <base> 看宿主机到端点通不通（别带 key）"),
    "dns": ("DNS 解析失败", "主机名拼错，或当前网络/DNS 解析不了；检查 http_proxy / https_proxy——代理配错也会表现成解析失败"),
    "network": ("网络层失败（含连接被拒/TLS）", "本地服务没起或端口不对（Ollama 默认 11434、vLLM 默认 8000）；backend 在容器里时，容器内的 127.0.0.1 是容器自己；自签证书的网关要客户端信任它"),
}
HTTP = {
    400: ("请求被拒（400）", "多半是 model 名不对 / 参数不被支持 / 余额问题——先跑 --models 看清单"),
    401: ("认证失败（401）", "key 拼错、过期或被删；也确认没把 model 名填进 key（改完要重新 source）"),
    404: ("路径或模型不存在（404）", "base_url 少了 /v1 或 /api/v3；也可能 model 名不对"),
}

def hide(text: str, secret: str) -> str:  # 打印前脱敏：只露前 4 位；短于 12 位一律 ***
    return text.replace(secret, secret[:4] + "…" if len(secret) >= 12 else "***") if secret else text

def call(url: str, key: str, timeout: float, payload: dict | None = None):
    """发一个请求。返回 (status, body, latency, reason)；没拿到 HTTP 响应时 status=None。"""
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), time.perf_counter() - started, None
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), time.perf_counter() - started, None
    except Exception as exc:  # noqa: BLE001 - URLError（超时/DNS/拒连）等：分类比堆栈有用
        return None, b"", time.perf_counter() - started, getattr(exc, "reason", exc)

def net_kind(reason: object) -> str:
    text = str(reason).lower()
    if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in text: return "timeout"
    return "dns" if isinstance(reason, socket.gaierror) or "getaddrinfo" in text else "network"

def check(cfg: dict[str, str], need_model: bool) -> list[str]:
    """只做形状检查（不发请求），返回 problems。"""
    problems: list[str] = []
    for key in REQUIRED if need_model else REQUIRED[:2]:
        if not cfg[key]:
            problems.append(f"{key} 未设置")
        elif cfg[key] != cfg[key].strip():
            problems.append(f"{key} 首尾有空白——.env 之外的 shell 不会 strip，去 .env 删掉")
    base = cfg["REBUILD_LLM_BASE_URL"].strip()
    parts = urllib.parse.urlsplit(base)
    if base and (parts.scheme not in ("http", "https") or not parts.netloc):
        problems.append(f"REBUILD_LLM_BASE_URL 不是 http(s)://主机… 的形状：{base}")
    elif base.rstrip("/").endswith("/chat/completions"):
        problems.append("REBUILD_LLM_BASE_URL 不要再带 /chat/completions：代码会自动拼一次")
    elif base and parts.path in ("", "/"):
        print("  ! base_url 没有版本段：多数端点要带 /v1 或 /api/v3（代码会在后面拼 /chat/completions）")
    try:
        seconds = float(cfg["REBUILD_LLM_TIMEOUT"])
    except ValueError:
        seconds = 0.0
    if seconds <= 0:
        problems.append(f"REBUILD_LLM_TIMEOUT 不是正数（或不是数字）：{cfg['REBUILD_LLM_TIMEOUT']}")
    return problems

def report_failure(status, latency: float, body: bytes, reason, cfg: dict[str, str]) -> int:
    key = cfg["REBUILD_LLM_API_KEY"].strip()
    print(f"  status={status if status is not None else '—'} latency={latency:.2f}s bytes={len(body)}")
    if reason is not None:
        label, hint = NET[net_kind(reason)]
        print(f"  ✗ 分类：{label}\n  排查：{hint}")
        print(f"  原始错误（已脱敏）：{hide(str(reason), key)[:200]}")
    else:
        label, hint = HTTP.get(status, (f"未预期的 HTTP {status}", "把状态码和返回摘要发给助教 / 查端点文档"))
        print(f"  ✗ 分类：{label}\n  排查：{hint}")
        if body:
            print(f"  返回摘要（已脱敏）：{hide(body[:200].decode('utf-8', 'replace'), key)}")
    print("  改完 .env 记得重新 source toolbox/scripts/export-docker-env.sh 再跑一次")
    return 1

def run_models(cfg: dict[str, str]) -> int:
    base = cfg["REBUILD_LLM_BASE_URL"].strip().rstrip("/")
    print(f"== 模型清单（GET /models：只读，不花 token）==\n  GET {base}/models")
    status, body, latency, reason = call(base + "/models", cfg["REBUILD_LLM_API_KEY"].strip(), float(cfg["REBUILD_LLM_TIMEOUT"]))
    if reason is not None or status != 200:
        return report_failure(status, latency, body, reason, cfg)
    try:
        ids = [str(item.get("id")) for item in json.loads(body).get("data", [])]
    except (ValueError, AttributeError, TypeError):
        ids = []
    print(f"  status=200 latency={latency:.2f}s models={', '.join(ids) or '（响应里没有 data[].id：网关可能不支持 /models，直接 --live 验 model）'}")
    chosen = cfg["REBUILD_LLM_MODEL"].strip()
    if ids and chosen not in ids:
        print(f"  ! REBUILD_LLM_MODEL={chosen or '（未填）'} 不在清单里：先换成清单里的名字——不同厂商的模型名不能混用")
    elif ids:
        print(f"  ✓ REBUILD_LLM_MODEL={chosen} 在清单里")
    return 0

def run_live(cfg: dict[str, str]) -> int:
    base = cfg["REBUILD_LLM_BASE_URL"].strip().rstrip("/")
    key, model = cfg["REBUILD_LLM_API_KEY"].strip(), cfg["REBUILD_LLM_MODEL"].strip()
    timeout = float(cfg["REBUILD_LLM_TIMEOUT"])
    payload = {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1, "temperature": 0}
    print(f"== 连通性自检（--live：发 1 条最小请求，可能计费）==\n  POST {base}/chat/completions  model={model}  max_tokens=1  timeout={timeout:g}s")
    status, body, latency, reason = call(base + "/chat/completions", key, timeout, payload)
    if reason is not None or status != 200:
        return report_failure(status, latency, body, reason, cfg)
    try:
        data = json.loads(body)
        reply = data["choices"][0]["message"].get("content") or ""
        served = data.get("model") or model
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        print(f"  status={status} latency={latency:.2f}s bytes={len(body)}")
        print(f"  ✗ 分类：响应不是 OpenAI 兼容 JSON（可能被代理/网关拦截，或 base_url 指错了服务）\n  返回摘要（已脱敏）：{hide(body[:200].decode('utf-8', 'replace'), key)}")
        return 1
    print(f"  status=200 latency={latency:.2f}s bytes={len(body)} model={served} reply_chars={len(reply)}")
    print(f"  ✓ 端点可达、认证通过；Key={hide(key, key)}（只显示前 4 位，完整值任何时候都不打印）")
    print("  提示：推理型模型 max_tokens=1 时 content 可能为空——本检查只看连通与认证，不看内容。")
    print("  下一步：docker compose up -d --force-recreate backend，让容器读到同一份 .env")
    return 0

def main() -> int:
    args = set(sys.argv[1:])
    if args - {"--live", "--models"}:
        print("用法：python3 toolbox/scripts/llm_check.py [--models] [--live]", file=sys.stderr)
        return 2
    live, models = "--live" in args, "--models" in args
    cfg = {key: os.environ.get(key, "") for key in (*REQUIRED, "REBUILD_LLM_TIMEOUT")}
    cfg["REBUILD_LLM_TIMEOUT"] = cfg["REBUILD_LLM_TIMEOUT"] or "30"
    key = cfg["REBUILD_LLM_API_KEY"]
    print("== 配置（本地检查：不联网、不打印完整 Key）==")
    print(f"  REBUILD_LLM_BASE_URL = {cfg['REBUILD_LLM_BASE_URL'] or '（未设置）'}")
    print(f"  REBUILD_LLM_API_KEY  = {hide(key, key) if key else '（未设置）'}{f'（{len(key)} 字符，只显示前 4 位）' if key else ''}")
    print(f"  REBUILD_LLM_MODEL    = {cfg['REBUILD_LLM_MODEL'] or '（未设置）'}")
    print(f"  REBUILD_LLM_TIMEOUT  = {cfg['REBUILD_LLM_TIMEOUT']}s")
    problems = check(cfg, need_model=not models)
    if problems:
        print("  ✗ 配置不完整：\n" + "\n".join(f"    - {problem}" for problem in problems))
        print(FIX_HINT)
        return 1
    if models:
        return run_models(cfg)
    if not live:
        print("READY：三个变量齐全、URL 形状合法（dry-run 没有发请求；加 --live 才联网）")
        return 0
    return run_live(cfg)

if __name__ == "__main__":
    raise SystemExit(main())
