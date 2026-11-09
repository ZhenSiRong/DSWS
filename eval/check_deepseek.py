#!/usr/bin/env python3
"""WBS 1.5 · 验证 DeepSeek 连通性，不打印 Key。

Key 来源优先级：
1. 环境变量 DEEPSEEK_API_KEY
2. ~/.bashrc 里的 `DEEPSEEK_API_KEY:sk-...`（历史写法，冒号分隔）

输出只包含状态、模型名、返回长度；任何情况下不输出 Key。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


def load_key() -> str | None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key.strip()
    rc = Path.home() / ".bashrc"
    if rc.is_file():
        for line in rc.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*(?:export\s+)?DEEPSEEK_API_KEY\s*[:=]\s*(\S+)\s*$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return None


def main() -> int:
    key = load_key()
    if not key:
        print(json.dumps({"ok": False, "error": "no key found"}))
        return 2

    payload = json.dumps({
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": [{"role": "user", "content": "只回复 OK"}],
        "max_tokens": 8,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read())
        content = body["choices"][0]["message"]["content"]
        print(json.dumps({
            "ok": True,
            "status": 200,
            "model": body.get("model"),
            "reply": content[:20],
            "key": f"{key[:6]}…{key[-4:]}",
        }, ensure_ascii=False))
        return 0
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        print(json.dumps({"ok": False, "status": exc.code, "error": detail}, ensure_ascii=False))
        return 1
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
