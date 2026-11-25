#!/usr/bin/env bash
# read-serve.sh — 阅读版 HTML 的 livereload 服务（13 文档 Q6 第 2 轮落定口径）
#
# 用 `uv run --with livereload` 起服务：零仓库依赖、不污染 backend/uv.lock。
# 监听 assets/*.css 与 manual/read/*.html，浏览器自动刷新；live_css=True 时
# 改样式只热替换 CSS、不整页刷（devtools 调样式即时可见）。
#
# 服务仓库根，故页面 URL = http://HOST:PORT/manual/read/page-NN.html，
# 阅读版 HTML 的相对链接 ../../assets/*.css 正确解析到 /assets/*.css。
#
# 用法：
#   scripts/read-serve.sh [PORT]             # 默认 5500，host 127.0.0.1
#   HOST=0.0.0.0 scripts/read-serve.sh 5500  # 浏览器在宿主机（VM-Share）时绑全网卡
#
# 迭代闭环：浏览器 devtools 调样式 → 满意后把改动抄回 assets/read.css →
#   python3 manual/shots/render_read.py --all 重生成（阅读版 HTML 永不手改）。
# 注意：需默认相对链接渲染（非 --embed）；--embed 把 CSS 内联进 HTML，
#   live_css 热替换失效（那时只监听 manual/read/*.html 的整页刷新）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PORT="${1:-${PORT:-5500}}"
export HOST="${HOST:-127.0.0.1}"

if ! command -v uv >/dev/null 2>&1; then
  echo "缺 uv：read-serve 用 \`uv run --with livereload\` 起服务（零仓库依赖）。" >&2
  echo "装 uv：https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

exec uv run --with livereload python -c '
import os
from livereload import Server

port = int(os.environ["PORT"])
host = os.environ["HOST"]
server = Server()
server.watch("assets/*.css")
server.watch("manual/read/*.html")
print(f"阅读版 livereload → http://{host}:{port}/manual/read/page-17.html")
print(f"  另：http://{host}:{port}/manual/read/page-21.html")
print("监听 assets/*.css + manual/read/*.html（live_css 热替换样式）；Ctrl+C 停")
server.serve(root=".", port=port, host=host, live_css=True)
'