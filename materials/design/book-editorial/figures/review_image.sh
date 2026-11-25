#!/usr/bin/env bash
# OCR + vision review for a rendered figure.
# Usage: review_image.sh <png> [out.txt]
# Env:   REVIEW_MODEL (default deepseek-v4.1-flash; set to hy4free for the old lane)
set -euo pipefail

PNG="${1:?usage: review_image.sh <png> [out.txt]}"
MODEL="${REVIEW_MODEL:-hy4free}"
OUT="${2:-$(dirname "$PNG")/review-$MODEL.txt}"
TESS="${OUT%.txt}-tesseract.txt"
mkdir -p "$(dirname "$OUT")"

# Fast deterministic OCR for Latin/numerals. Chinese needs the vision pass.
if command -v tesseract >/dev/null 2>&1; then
  tesseract "$PNG" stdout -l eng 2>/dev/null > "$TESS" || true
else
  echo "tesseract not found" > "$TESS"
fi

PROMPT="Use the Read tool to open the image at $PNG. Then quote every text string you can see, one per line, exactly as written, including Chinese characters. Do not explain. If you cannot see images, output NO_VISION."

echo "$MODEL" > "${OUT}.model"

if command -v codebuddy >/dev/null 2>&1; then
  timeout 240 codebuddy -p -y --model "$MODEL" --effort minimal --max-turns 10 "$PROMPT" > "$OUT" 2>&1 || true
else
  echo "codebuddy not found" > "$OUT"
fi

echo "review: $OUT"
echo "ocr: $TESS"
