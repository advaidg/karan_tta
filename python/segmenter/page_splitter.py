"""Split TTA's single-variable OCR string into ordered per-page texts.

TTA emits the whole document as ONE OCR string with page separators it inserts,
e.g. `[PAGE 1]`, `[PAGE 2]`, ... The hard part: a document's own body can ALSO
contain text like "Page 1" or even a literal "[PAGE 1]" in its content. So we
must split on the *real* TTA separators only.

Robustness strategy (all heuristics, no external deps):
  1. The TTA marker is bracketed and sits effectively on its own line:
     ^\\s*\\[\\s*PAGE\\s+N\\s*\\]\\s*$   (case-insensitive)
  2. We accept a marker only if it keeps a (mostly) increasing sequence
     1,2,3,... Stray in-body "[PAGE 1]" that breaks monotonicity is ignored
     and folded into the current page's text instead of starting a new page.
  3. Loose, non-bracketed "Page 1 of 5" is NEVER treated as a separator
     (that's document content, handled later by the page-number layer).

Configurable marker regex so you can match your exact TTA format.
Pure stdlib.
"""
from __future__ import annotations

import re
from typing import List, Optional

# Default: a bracketed PAGE marker alone on a line. Tolerates [PAGE 1], [ Page 12 ],
# and common OCR bracket noise. Adjust to your TTA output if it differs.
DEFAULT_MARKER = re.compile(r"(?im)^[\s>*]*[\[\(<]\s*page\s+(\d{1,4})\s*[\]\)>]\s*$")


def split_pages(ocr_text: str, marker: re.Pattern = DEFAULT_MARKER,
                enforce_sequence: bool = True) -> List[str]:
    """Return ordered per-page text. If no markers are found, returns [ocr_text]."""
    matches = list(marker.finditer(ocr_text))
    if not matches:
        return [ocr_text] if ocr_text.strip() else []

    accepted = _filter_sequence(matches, enforce_sequence)
    if not accepted:
        return [ocr_text]

    pages: List[str] = []
    # text before the first accepted marker (cover text) becomes part of page 1
    first = accepted[0]
    preamble = ocr_text[:first.start()].strip()
    for idx, m in enumerate(accepted):
        body_start = m.end()
        body_end = accepted[idx + 1].start() if idx + 1 < len(accepted) else len(ocr_text)
        body = ocr_text[body_start:body_end].strip("\n")
        if idx == 0 and preamble:
            body = preamble + "\n" + body
        pages.append(body)
    return pages


def _filter_sequence(matches, enforce_sequence: bool):
    """Keep only markers that form a sensible increasing page sequence.

    A marker whose number is not strictly greater than the last accepted one is
    treated as in-document text (the trap) and dropped as a separator.
    """
    if not enforce_sequence:
        return matches
    accepted = []
    last_num: Optional[int] = None
    for m in matches:
        try:
            num = int(m.group(1))
        except (TypeError, ValueError):
            continue
        if last_num is None:
            # accept the first marker only if it starts the sequence low (1 or 2)
            if num <= 2:
                accepted.append(m)
                last_num = num
            # else: likely an in-body "[PAGE 7]" before any real separator -> skip
        else:
            if num > last_num:
                accepted.append(m)
                last_num = num
            # else non-increasing -> in-document text, ignore as a separator
    # Fallback: if sequence filtering rejected everything but markers exist,
    # accept them all (better to over-split than to lose the document).
    return accepted if accepted else matches


def join_pages_with_markers(pages: List[str]) -> str:
    """Inverse helper (used by the generator/tests) — emit TTA-style single string."""
    out = []
    for i, p in enumerate(pages, start=1):
        out.append(f"[PAGE {i}]")
        out.append(p)
    return "\n".join(out)
