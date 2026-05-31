"""Rigid evaluation metrics for the segmenter.

We score the things that actually matter for this problem:
  - boundary detection (where docs start)         -> precision / recall / F1
  - segment exact match (start AND end correct)   -> P / R / F1
  - A->A split rate (the headline failure mode)   -> recall on same-type boundaries
  - document-type accuracy (on matched segments)
  - unknown leakage (unknown pages landing in a known doc, and vice-versa)
  - review-routing quality (does needs_review flag the wrong segments)

Pure stdlib.
"""
from __future__ import annotations

from typing import Dict, List

from segmenter.models import DocumentSegment


def truth_to_segments(truth: List[dict]) -> List[Dict]:
    """Convert per-page ground truth into segments [{start,end,type}]."""
    segs: List[Dict] = []
    cur = None
    for i, t in enumerate(truth):
        if t["is_start"] or cur is None:
            if cur is not None:
                segs.append(cur)
            cur = {"start": i, "end": i, "type": t["type"]}
        else:
            cur["end"] = i
    if cur is not None:
        segs.append(cur)
    return segs


def _page_type_map(segs, n_pages, get):
    m = ["?"] * n_pages
    for s in segs:
        a, b, ty = get(s)
        for i in range(a, b + 1):
            if 0 <= i < n_pages:
                m[i] = ty
    return m


def evaluate_batch(pred: List[DocumentSegment], truth: List[dict]) -> Dict[str, float]:
    n_pages = len(truth)
    true_segs = truth_to_segments(truth)

    pred_starts = {s.start_page for s in pred}
    true_starts = {s["start"] for s in true_segs}

    tp_b = len(pred_starts & true_starts)
    fp_b = len(pred_starts - true_starts)
    fn_b = len(true_starts - pred_starts)

    # segment exact match (start AND end)
    pred_se = {(s.start_page, s.end_page) for s in pred}
    true_se = {(s["start"], s["end"]) for s in true_segs}
    seg_tp = len(pred_se & true_se)
    seg_fp = len(pred_se - true_se)
    seg_fn = len(true_se - pred_se)

    # type accuracy on exactly-matched segments
    pred_by_se = {(s.start_page, s.end_page): s.doc_type for s in pred}
    true_by_se = {(s["start"], s["end"]): s["type"] for s in true_segs}
    type_ok = type_tot = 0
    for se in (pred_se & true_se):
        type_tot += 1
        if pred_by_se[se] == true_by_se[se]:
            type_ok += 1

    # A->A: true adjacent same-(known)-type boundaries correctly split
    aa_tot = aa_hit = 0
    for a, b in zip(true_segs, true_segs[1:]):
        if a["type"] == b["type"] and a["type"] != "Unknown":
            aa_tot += 1
            if b["start"] in pred_starts:
                aa_hit += 1

    # page-level type accuracy + unknown leakage
    pred_pt = _page_type_map(pred, n_pages, lambda s: (s.start_page, s.end_page, s.doc_type))
    true_pt = _page_type_map(true_segs, n_pages, lambda s: (s["start"], s["end"], s["type"]))
    page_ok = sum(1 for i in range(n_pages) if pred_pt[i] == true_pt[i])
    unk_total = sum(1 for i in range(n_pages) if true_pt[i] == "Unknown")
    unk_leak = sum(1 for i in range(n_pages) if true_pt[i] == "Unknown" and pred_pt[i] != "Unknown")
    known_total = n_pages - unk_total
    false_unk = sum(1 for i in range(n_pages) if true_pt[i] != "Unknown" and pred_pt[i] == "Unknown")

    # review routing: a predicted segment is "wrong" if not an exact-correct-type match
    wrong = flagged = wrong_and_flagged = 0
    for s in pred:
        se = (s.start_page, s.end_page)
        is_correct = se in true_se and true_by_se.get(se) == s.doc_type
        if not is_correct:
            wrong += 1
        if s.needs_review:
            flagged += 1
        if (not is_correct) and s.needs_review:
            wrong_and_flagged += 1

    return {
        "n_pages": n_pages, "n_true_segs": len(true_segs), "n_pred_segs": len(pred),
        "b_tp": tp_b, "b_fp": fp_b, "b_fn": fn_b,
        "seg_tp": seg_tp, "seg_fp": seg_fp, "seg_fn": seg_fn,
        "type_ok": type_ok, "type_tot": type_tot,
        "aa_hit": aa_hit, "aa_tot": aa_tot,
        "page_ok": page_ok,
        "unk_leak": unk_leak, "unk_total": unk_total,
        "false_unk": false_unk, "known_total": known_total,
        "wrong": wrong, "flagged": flagged, "wrong_and_flagged": wrong_and_flagged,
    }


def aggregate(rows: List[Dict[str, float]]) -> Dict[str, float]:
    s: Dict[str, float] = {}
    for r in rows:
        for k, v in r.items():
            s[k] = s.get(k, 0) + v

    def pr(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        return p, r, f

    bp, br, bf = pr(s.get("b_tp", 0), s.get("b_fp", 0), s.get("b_fn", 0))
    sp, sr, sf = pr(s.get("seg_tp", 0), s.get("seg_fp", 0), s.get("seg_fn", 0))
    return {
        "boundary_precision": bp, "boundary_recall": br, "boundary_f1": bf,
        "segment_precision": sp, "segment_recall": sr, "segment_f1": sf,
        "type_accuracy_matched": _safe(s.get("type_ok", 0), s.get("type_tot", 0)),
        "page_type_accuracy": _safe(s.get("page_ok", 0), s.get("n_pages", 0)),
        "aa_split_rate": _safe(s.get("aa_hit", 0), s.get("aa_tot", 0)),
        "unknown_leakage": _safe(s.get("unk_leak", 0), s.get("unk_total", 0)),
        "false_unknown_rate": _safe(s.get("false_unk", 0), s.get("known_total", 0)),
        "review_recall": _safe(s.get("wrong_and_flagged", 0), s.get("wrong", 0)),
        "review_precision": _safe(s.get("wrong_and_flagged", 0), s.get("flagged", 0)),
        "_totals": {k: s.get(k, 0) for k in
                    ("aa_tot", "n_true_segs", "n_pred_segs", "wrong", "unk_total")},
    }


def _safe(num, den):
    return num / den if den else 1.0
