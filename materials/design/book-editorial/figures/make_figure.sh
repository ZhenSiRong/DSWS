#!/usr/bin/env bash
# One-command figure build: content JSON -> SVG -> PNG -> gates -> audit -> preview.
# Usage: ./make_figure.sh fig-3-0-three-silent-failures [--no-review]
#
# If the content JSON sets "render": "hybrid", the SVG/PNG pair becomes
# AI raster (render_source) + exact SVG text overlay. The vector master is kept
# alongside as <id>-vector.svg/.png as a fallback.
set -euo pipefail
cd "$(dirname "$0")"

ID="${1:?usage: make_figure.sh <fig-id> [--no-review]}"
CONTENT="content/$ID.json"
[[ -f "$CONTENT" ]] || { echo "missing $CONTENT" >&2; exit 1; }
STATUS="$PWD/$ID.status.json"
RENDER=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8")).get("render","vector"))' "$CONTENT")
RENDER_SOURCE=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8")).get("render_source",""))' "$CONTENT")

render_png() {
  local svg="$1" png="$2"
  local profile="/tmp/opencode/chrome-figure-$$-$RANDOM"
  google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --allow-file-access-from-files \
    --user-data-dir="$profile" \
    --force-device-scale-factor=1 --window-size=1600,900 \
    --screenshot="$png" "file://$svg" >/dev/null 2>&1 || true
  rm -rf "$profile"
}

python3 status.py "$STATUS" start "{\"content\":\"$CONTENT\",\"render\":\"$RENDER\"}"
python3 gen_figure.py "$CONTENT"
python3 status.py "$STATUS" generated

# Always keep the pure-vector master reproducible.
cp "$PWD/$ID.svg" "$PWD/$ID-vector.svg"
render_png "$PWD/$ID-vector.svg" "$PWD/$ID-vector.png"

if [[ "$RENDER" == "hybrid" ]]; then
  [[ -n "$RENDER_SOURCE" && -f "$PWD/$RENDER_SOURCE" ]] || {
    echo "missing render_source: $RENDER_SOURCE" >&2
    python3 status.py "$STATUS" failed '{"stage":"hybrid_source"}'
    exit 1
  }
  python3 make_overlay.py \
    --layout "$PWD/$ID.layout.json" \
    --image "$PWD/$RENDER_SOURCE" \
    --out "$PWD/$ID"
  python3 status.py "$STATUS" overlaid
fi

render_png "$PWD/$ID.svg" "$PWD/$ID.png"

[[ -f "$PWD/$ID.png" ]] || {
  python3 status.py "$STATUS" failed '{"stage":"render"}'
  echo "render failed: $PWD/$ID.png" >&2
  exit 1
}
python3 status.py "$STATUS" rendered

if ! python3 check_figure.py "$CONTENT"; then
  python3 status.py "$STATUS" failed '{"stage":"check"}'
  exit 1
fi
python3 status.py "$STATUS" checked '{"all_pass":true}'

if [[ "${2:-}" != "--no-review" ]]; then
  bash review_image.sh "$PWD/$ID.png" "$PWD/$ID-review-hy4free.txt"
  python3 status.py "$STATUS" reviewed
fi

python3 write_audit.py "$CONTENT"
python3 status.py "$STATUS" done '{"all_pass":true}'
echo "OK: $PWD/$ID.png"
echo "preview: $PWD/../pilot/$ID-preview.html"
