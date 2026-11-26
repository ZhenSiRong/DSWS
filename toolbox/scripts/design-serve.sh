#!/usr/bin/env bash
# 页首图编辑器本地服务：在仓库根启动静态服务器，浏览器打开 /manual/designs/
# 用法：toolbox/scripts/design-serve.sh [PORT]   # 默认 8788
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="${1:-8788}"
cd "$ROOT"
echo "页首图编辑入口： http://127.0.0.1:${PORT}/manual/designs/"
echo "可直接编辑： page-00 / page-01 / page-02 的 editor.html"
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory "$ROOT"
