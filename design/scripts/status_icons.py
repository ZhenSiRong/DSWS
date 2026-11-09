#!/usr/bin/env python3
"""Inline SVG icons for the evidence markers ✅ / 🟡 / ⚪.

The three markers are replaced in the generated HTML by Lucide (MIT) icons so
the print PDF shows drawn line art instead of colour emoji glyphs:

    ✅ 已验证 -> circle-check  #15803D
    🟡 推断   -> circle-alert  #B45309
    ⚪ 未验证 -> circle-help   #6B7280

Every icon is a 24x24 viewBox, stroke-width 2, single colour, no fill, with
class="status-icon status-ok|status-warn|status-unknown", role="img" and an
aria-label in Chinese. Size and baseline come from book.css.

WeasyPrint 70 does not resolve currentColor inside inline SVG (checked
2026-11-03: it paints the stroke black), so the stroke colour is written into
each SVG; the CSS colour classes stay for browser preview and for a future
renderer that does support currentColor.
"""
from __future__ import annotations

import re

OK_MARKER = "✅"
WARN_MARKER = "🟡"
UNKNOWN_MARKER = "⚪"

_COLORS = {"ok": "#15803D", "warn": "#B45309", "unknown": "#6B7280"}
_LABELS = {"ok": "已验证", "warn": "推断", "unknown": "未验证"}


def _icon(kind: str, body: str) -> str:
    return (
        f'<svg class="status-icon status-{kind}" viewBox="0 0 24 24"'
        f' width="3.2mm" height="3.2mm" fill="none"'
        f' stroke="{_COLORS[kind]}" stroke-width="2"'
        f' stroke-linecap="round" stroke-linejoin="round"'
        f' role="img" aria-label="{_LABELS[kind]}">{body}</svg>'
    )


STATUS_OK_SVG = _icon(
    "ok",
    '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
)
STATUS_WARN_SVG = _icon(
    "warn",
    '<circle cx="12" cy="12" r="10"/>'
    '<line x1="12" y1="8" x2="12" y2="12"/>'
    '<line x1="12" y1="16" x2="12.01" y2="16"/>',
)
STATUS_UNKNOWN_SVG = _icon(
    "unknown",
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
    '<path d="M12 17h.01"/>',
)

STATUS_ICONS = {
    OK_MARKER: STATUS_OK_SVG,
    WARN_MARKER: STATUS_WARN_SVG,
    UNKNOWN_MARKER: STATUS_UNKNOWN_SVG,
}

# <pre> / <code> content is code, not prose: leave the markers alone there.
_PROTECTED = re.compile(r"<(pre|code)\b[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"(<[^>]*>)")
_MARKER = re.compile("|".join(re.escape(m) for m in STATUS_ICONS))


def _replace_outside_tags(chunk: str) -> str:
    """Swap markers in text only, never inside a tag or attribute value."""
    pieces = _TAG.split(chunk)
    return "".join(
        piece
        if piece.startswith("<")
        else _MARKER.sub(lambda m: STATUS_ICONS[m.group(0)], piece)
        for piece in pieces
    )


def replace_status_markers(html_text: str) -> str:
    """Replace ✅ / 🟡 / ⚪ with inline SVG icons in prose HTML.

    Regions inside <pre> or <code> are copied through untouched.
    """
    out: list[str] = []
    pos = 0
    for match in _PROTECTED.finditer(html_text):
        out.append(_replace_outside_tags(html_text[pos:match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(_replace_outside_tags(html_text[pos:]))
    return "".join(out)
