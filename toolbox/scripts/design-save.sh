#!/usr/bin/env bash
# 把 editor.html 导出的 HTML 保存回项目（另存/覆盖）
# 用法：toolbox/scripts/design-save.sh 00 ~/Downloads/index.edited.html
#       toolbox/scripts/design-save.sh 00          # 只重建当前 index.html 的 PNG/WebP
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAGE="${1:?页号，如 00}"
SRC="${2:-}"
PAGE=$(printf '%02d' "$PAGE" 2>/dev/null || echo "$PAGE")
DIR="$ROOT/manual/designs/page-$PAGE"
[ -d "$DIR" ] || { echo "找不到 $DIR" >&2; exit 1; }

if [ -n "$SRC" ]; then
  [ -f "$SRC" ] || { echo "找不到下载的 HTML：$SRC" >&2; exit 1; }
  STAMP=$(date +%Y%m%d-%H%M%S)
  mkdir -p "$DIR/out"
  cp "$DIR/index.html" "$DIR/out/index.$STAMP.bak.html"
  cp "$SRC" "$DIR/index.html"
  echo "已保存编辑版：$DIR/index.html（旧版备份 out/index.$STAMP.bak.html）"
  node "$HOME/.agents/skills/editable-design/scripts/wire-editor.mjs" "$DIR/index.html"
  python3 "$ROOT/manual/designs/inject_save_ui.py" "$PAGE"
fi

python3 "$ROOT/manual/designs/render_existing.py" "$PAGE"
python3 "$ROOT/manual/shots/render_read.py" "$PAGE" >/dev/null
python3 "$ROOT/manual/shots/audit_book.py" | tail -1
