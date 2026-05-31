"""Pure-stdlib OCR text utilities: normalisation, header zone, page-number and
business-identifier parsing, and similarity. Everything here ports cleanly to
C# (System.Text.RegularExpressions + simple string ops).
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")

# Common OCR digit confusions, applied only to numeric-looking contexts.
_OCR_DIGIT_MAP = str.maketrans({"l": "1", "i": "1", "I": "1", "o": "0",
                                "O": "0", "s": "5", "S": "5", "B": "8", "|": "1"})


def normalize(text: str) -> str:
    """Lowercase, strip punctuation to spaces, collapse whitespace.
    Padded with spaces so phrase matching can use ' phrase ' word boundaries."""
    low = text.lower()
    low = _NON_ALNUM.sub(" ", low)
    low = _WS.sub(" ", low).strip()
    return " " + low + " "


def header_text(text: str, ratio: float, min_lines: int,
                header_words: int = 55) -> str:
    """Return the 'header zone' (the start of the page) — LINE-INDEPENDENT.

    TTA may deliver a page as normal multi-line text OR as one long flattened line
    with no newlines. To make both behave identically, the header zone is defined
    as the first `header_words` whitespace-delimited tokens of the page (not the
    first N lines). This way single-line and multi-line OCR of the same page yield
    the same header and therefore the same classification. (ratio / min_lines are
    accepted for backward compatibility but no longer used.)
    """
    if not text:
        return text
    parts = text.split()
    if len(parts) <= header_words:
        return text
    return " ".join(parts[:header_words])


def contains_phrase(normalized_haystack: str, normalized_phrase: str) -> bool:
    """Word-boundary-safe substring test on already-normalized strings."""
    return normalized_phrase in normalized_haystack


def tokenize(normalized_text: str) -> List[str]:
    return [t for t in normalized_text.split() if t]


def jaccard(a_tokens: List[str], b_tokens: List[str]) -> float:
    if not a_tokens and not b_tokens:
        return 1.0
    sa, sb = set(a_tokens), set(b_tokens)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


# --------------------------------------------------------------------------
# Page number parsing (fuzzy, OCR-noise tolerant). Returns (current, total).
# --------------------------------------------------------------------------
_PN_PATTERNS = [
    re.compile(r"page\s+(\d{1,3})\s+of\s+(\d{1,3})"),
    re.compile(r"pg\.?\s*(\d{1,3})\s*/\s*(\d{1,3})"),
    re.compile(r"\bpage\s*[:#]?\s*(\d{1,3})\s*/\s*(\d{1,3})"),
    re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b"),
    re.compile(r"\bpage\s*[:#]?\s*(\d{1,3})\b"),
]


def parse_page_number(text: str) -> Tuple[Optional[int], Optional[int]]:
    low = text.lower()
    # light denoise of obvious "page l of S" style only around the word 'page'
    candidates = [low]
    if "page" in low or "/" in low:
        candidates.append(low.translate(_OCR_DIGIT_MAP))
    for cand in candidates:
        for i, pat in enumerate(_PN_PATTERNS):
            m = pat.search(cand)
            if m:
                cur = _safe_int(m.group(1))
                tot = _safe_int(m.group(2)) if m.lastindex and m.lastindex >= 2 else None
                if cur is not None and 0 < cur < 500 and (tot is None or 0 < tot < 500):
                    if tot is not None and cur > tot:
                        continue
                    return cur, tot
    return None, None


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Business identifier extraction.
# --------------------------------------------------------------------------
def extract_ids(text: str, type_id_regexes: List[re.Pattern],
                generic_regexes: List[re.Pattern]) -> List[str]:
    low = text.lower()
    found: List[str] = []
    for pat in type_id_regexes:
        for m in pat.findall(low):
            found.append(_canon_id(m))
    if not found:  # only fall back to generic IDs if no typed id matched
        for pat in generic_regexes:
            for m in pat.findall(low):
                found.append(_canon_id(m))
    # de-dup, preserve order
    seen, out = set(), []
    for f in found:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _canon_id(match) -> str:
    if isinstance(match, tuple):
        match = "".join(match)
    return re.sub(r"[^a-z0-9]", "", str(match)).upper()


def compile_list(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p) for p in patterns]
