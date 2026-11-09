#!/usr/bin/env python3
"""Write a tiny progress heartbeat for the fixed figure pipeline.

Usage:
    python3 status.py <status.json> <step> [extra-json]

The coordinator can poll this file instead of scraping an agent terminal.
"""
from __future__ import annotations

import json
import os
import sys
import time

if len(sys.argv) < 3:
    print("usage: status.py <status.json> <step> [extra-json]", file=sys.stderr)
    raise SystemExit(2)

path, step = sys.argv[1], sys.argv[2]
extra = {}
if len(sys.argv) > 3 and sys.argv[3].strip():
    extra = json.loads(sys.argv[3])

data = {
    "figure": os.path.basename(path).removesuffix(".status.json"),
    "step": step,
    "ts": time.time(),
    **extra,
}
os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(path)
