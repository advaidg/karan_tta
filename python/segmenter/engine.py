"""The segmentation engine: per-page scoring (5 layers) + boundary assembly.

Input  : ordered list of per-page OCR text (one string per page) — exactly what
         TTA can hand us.
Output : list[DocumentSegment] + list[PageDecision] (audit trail).

Pure stdlib. Mirrors the structure the C# port will use.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .config import get_config, load_profiles
from .models import DocumentSegment, PageDecision
from . import ocr_utils as ou
from .page_splitter import split_pages


class Segmenter:
    def __init__(self, profiles: Dict = None, config: Dict = None):
        self.profiles = profiles if profiles is not None else load_profiles()
        self.cfg = get_config(config) if not (config and "header_ratio" in config) else config
        if config and "header_ratio" not in config:
            self.cfg = get_config(config)
        # Pre-normalise keyword phrases and compile regexes once.
        self.types = {}
        for name, prof in self.profiles.get("types", {}).items():
            self.types[name] = {
                "strong_start": [ou.normalize(k) for k in prof.get("strong_start", [])],
                "first_page": [ou.normalize(k) for k in prof.get("first_page", [])],
                "any_page": [ou.normalize(k) for k in prof.get("any_page", [])],
                "negative": [ou.normalize(k) for k in prof.get("negative", [])],
                "id_regex": ou.compile_list(prof.get("id_regex", [])),
                "max_pages": int(prof.get("max_pages", 0)),
            }
        self.generic_id_regex = ou.compile_list(self.profiles.get("generic_id_regex", []))

    # ----------------------------------------------------------------- scoring
    def score_page(self, raw_text: str) -> PageDecision:
        cfg = self.cfg
        norm_full = ou.normalize(raw_text)
        header = ou.header_text(raw_text, cfg["header_ratio"], int(cfg["header_min_lines"]))
        norm_header = ou.normalize(header)

        type_scores: Dict[str, float] = {}
        strong_in_header: Dict[str, bool] = {}
        for name, prof in self.types.items():
            s = 0.0
            hit_strong_header = False
            for kw in prof["strong_start"]:
                if ou.contains_phrase(norm_header, kw):
                    s += cfg["w_strong_header"]
                    hit_strong_header = True
                elif ou.contains_phrase(norm_full, kw):
                    s += cfg["w_strong_body"]
            for kw in prof["any_page"]:
                if ou.contains_phrase(norm_full, kw):
                    s += cfg["w_any"]
            for kw in prof["negative"]:
                if ou.contains_phrase(norm_full, kw):
                    s += cfg["w_negative"]
            type_scores[name] = s
            strong_in_header[name] = hit_strong_header

        best_type, best_score, second_score = _top2(type_scores)
        is_unknown = best_score < cfg["min_type_score"]
        effective_type = "Unknown" if is_unknown else best_type
        type_conf = _clamp(best_score / cfg["type_conf_denom"], 0.0, 1.0)

        cur, tot = ou.parse_page_number(raw_text)
        id_regexes = self.types.get(best_type, {}).get("id_regex", []) if best_type else []
        ids = ou.extract_ids(raw_text, id_regexes, self.generic_id_regex)

        # page-1 signature: phrases that appear ONLY on the first page of the best
        # type. A reappearance mid-document signals a new instance even when there
        # is no page number (the key A,A signal for repeated-title mortgage docs).
        first_page_sig = False
        if best_type and not is_unknown:
            for kw in self.types[best_type].get("first_page", []):
                if ou.contains_phrase(norm_full, kw):
                    first_page_sig = True
                    break

        dec = PageDecision(
            page_index=-1,
            best_doc_type=best_type or "Unknown",
            doc_type_confidence=type_conf,
            effective_type=effective_type,
            is_start_page=False,
            start_score=0.0,
            is_unknown=is_unknown,
            needs_review=False,
            extracted_ids=ids,
            page_number=cur,
            total_pages=tot,
            type_scores=type_scores,
        )
        dec._strong_in_header = strong_in_header.get(best_type, False)  # type: ignore[attr-defined]
        dec._best_minus_second = best_score - second_score              # type: ignore[attr-defined]
        dec._norm_tokens = ou.tokenize(norm_full)                       # type: ignore[attr-defined]
        dec._first_page_sig = first_page_sig                            # type: ignore[attr-defined]
        return dec

    # ------------------------------------------------------------ start decision
    def _evaluate_start(self, dec: PageDecision, prev: Optional[PageDecision],
                        seg_type: Optional[str], seg_ids: List[str],
                        seg_len: int = 0) -> Tuple[float, List[str]]:
        cfg = self.cfg
        score = 0.0
        sig: List[str] = []

        type_changed = seg_type is not None and dec.effective_type != seg_type
        same_type = seg_type is not None and dec.effective_type == seg_type

        # per-type page-count cap. For single-page forms (max_pages=1) a repeated
        # title is necessarily a NEW instance; for any capped type, a same-type
        # page beyond the cap must start a new document. Key for A,A on the many
        # single-page mortgage forms (affidavits, notices, certificates).
        max_pages = self.types.get(dec.effective_type, {}).get("max_pages", 0) if not dec.is_unknown else 0
        over_cap = bool(same_type and max_pages > 0 and seg_len >= max_pages)
        single_page_type = (max_pages == 1)
        sim = 1.0
        if prev is not None:
            sim = ou.jaccard(getattr(prev, "_norm_tokens", []), getattr(dec, "_norm_tokens", []))
        low_sim = (prev is not None) and (sim < cfg["sim_low"])

        # --- header title state ------------------------------------------------
        # In mortgage packets, multi-page docs (Closing Disclosure, Deed of Trust,
        # underwriting findings) REPEAT their title on every page. So a raw title
        # is NOT a reliable start signal. The reliable signal `strong_new` is a
        # title that REAPPEARS after being absent, or a title for a DIFFERENT type
        # than the open segment -> a genuine new document begins here.
        strong = bool(getattr(dec, "_strong_in_header", False))
        prev_strong = bool(getattr(prev, "_strong_in_header", False)) if prev is not None else False
        prev_type = prev.effective_type if prev is not None else None

        page_one = dec.page_number == 1
        reset = (dec.page_number is not None and dec.page_number > 1 and prev is not None
                 and prev.page_number is not None and dec.page_number < prev.page_number)
        prev_terminal = (prev is not None and prev.page_number is not None
                         and prev.total_pages is not None and prev.page_number == prev.total_pages)

        # A title is a NEW-document signal when it newly appears / is a different
        # type than the open segment, OR when the SAME repeated title reappears
        # together with a hard page cue (page reset, or previous page was the last
        # page "N of N", or this page is page 1). The page cue is what lets us
        # split two adjacent same-type repeated-title docs (the A,A case) without
        # over-splitting a single multi-page doc whose title repeats every page.
        # page-1 signature: a "first page only" phrase present here but NOT on the
        # previous page -> a new instance begins, even without a page number. This
        # is the key A,A signal for repeated-title multi-page mortgage docs.
        fp_sig = bool(getattr(dec, "_first_page_sig", False))
        prev_fp_sig = bool(getattr(prev, "_first_page_sig", False)) if prev is not None else False
        first_page_signature = fp_sig and not prev_fp_sig

        title_repeats_open = strong and prev_strong and prev_type == dec.effective_type
        strong_new = strong and (
            not title_repeats_open or reset or prev_terminal or page_one
            or first_page_signature or single_page_type or over_cap
        )
        id_change = bool(same_type and not dec.is_unknown and seg_ids and dec.extracted_ids
                         and not (set(dec.extracted_ids) & set(seg_ids)))

        # type change is real evidence only when corroborated: a NEW title,
        # a fresh page-1, a reset, or genuinely different content (low similarity).
        type_change_evidenced = type_changed and (strong_new or page_one or reset or low_sim)

        # known -> unknown is a boundary ONLY when the page is genuinely different
        # content (low similarity).
        known_to_unknown = (seg_type is not None and seg_type != "Unknown"
                            and dec.is_unknown and low_sim)

        # same-type new instance via page-1 signature (no page number needed)
        same_type_new_instance = same_type and not dec.is_unknown and first_page_signature

        has_evidence = (strong_new or page_one or reset or prev_terminal or id_change
                        or type_change_evidenced or known_to_unknown
                        or same_type_new_instance or over_cap)

        # --- accumulate weighted signals ---
        if over_cap:
            score += cfg["w_strong_start"]
            sig.append("over_max_pages")
        if same_type_new_instance:
            score += cfg["w_strong_start"]
            sig.append("first_page_signature")
        if type_changed:
            score += cfg["w_type_change"]
            sig.append("type_change")
        if id_change:
            score += cfg["w_id_change"]
            sig.append("id_change")
        elif same_type and seg_ids and dec.extracted_ids and (set(dec.extracted_ids) & set(seg_ids)):
            score -= cfg["w_cont_id_same"]
            sig.append("id_same")
        if strong_new:
            score += cfg["w_strong_start"]
            sig.append("strong_start_header")
        elif strong:
            # title present but it repeats the open doc's title -> CONTINUATION.
            score -= cfg["w_cont_id_same"]
            sig.append("title_repeat")
        if page_one:
            score += cfg["w_pagenum_one"]
            sig.append("pagenum_one")
        elif dec.page_number is not None and dec.page_number > 1:
            if reset:
                score += cfg["w_reset"]
                sig.append("pagenum_reset")
            else:
                score -= cfg["w_cont_pagenum"]
                sig.append("pagenum_continuation")
        if prev_terminal:
            score += cfg["w_prev_terminal"]
            sig.append("prev_terminal")
        if same_type and not dec.is_unknown and low_sim:
            score += cfg["w_lowsim"]
            sig.append("low_similarity")

        # --- CONTINUATION GATE -------------------------------------------------
        # A low-signal page with no real start evidence belongs to the open
        # document (handles keyword-less continuation pages and noisy scans).
        if seg_type is not None and not has_evidence:
            score = min(score, cfg["start_low"] - 1.0)
            sig.append("continuation_gate")

        return score, sig

    # ------------------------------------------------------------------ assemble
    def segment(self, pages_text: List[str]) -> Tuple[List[DocumentSegment], List[PageDecision]]:
        cfg = self.cfg
        decisions: List[PageDecision] = []
        segments: List[DocumentSegment] = []

        cur_seg: Optional[DocumentSegment] = None
        cur_ids: List[str] = []
        prev: Optional[PageDecision] = None

        for i, raw in enumerate(pages_text):
            dec = self.score_page(raw)
            dec.page_index = i

            seg_type = cur_seg.doc_type if cur_seg else None
            seg_len = (i - cur_seg.start_page) if cur_seg else 0  # pages already in open seg
            start_score, sig = self._evaluate_start(dec, prev, seg_type, cur_ids, seg_len)
            dec.start_score = start_score
            dec.signals = sig

            forced = (i == 0)
            is_start = forced or (start_score >= cfg["start_threshold"])
            gray = (not is_start) and (start_score >= cfg["start_low"])
            ambiguous = getattr(dec, "_best_minus_second", 99) < cfg["ambig_margin"] and not dec.is_unknown
            dec.is_start_page = is_start
            dec.needs_review = bool(gray or ambiguous or dec.is_unknown)
            if forced:
                dec.signals = ["batch_first_page"] + dec.signals

            if is_start or cur_seg is None:
                if cur_seg is not None:
                    segments.append(cur_seg)
                cur_seg = DocumentSegment(
                    start_page=i, end_page=i, doc_type=dec.effective_type,
                    confidence=dec.doc_type_confidence, needs_review=dec.needs_review,
                    reason=",".join(dec.signals), ids=list(dec.extracted_ids),
                )
                cur_ids = list(dec.extracted_ids)
            else:
                cur_seg.end_page = i
                # accumulate ids and keep the lowest confidence / OR review flag
                for _id in dec.extracted_ids:
                    if _id not in cur_ids:
                        cur_ids.append(_id)
                cur_seg.ids = list(cur_ids)
                cur_seg.needs_review = cur_seg.needs_review or dec.needs_review
                cur_seg.confidence = min(cur_seg.confidence, dec.doc_type_confidence)
                # A continuation page that still shows START-LIKE cues (a title of
                # this type, or a page-1 signature) is a likely MISSED boundary
                # (e.g. an adjacent same-type doc with no page number). Flag the
                # segment so the GenAI node / Document Review can re-check it.
                if getattr(dec, "_strong_in_header", False) or getattr(dec, "_first_page_sig", False):
                    cur_seg.needs_review = True
                    if "possible_missed_boundary" not in cur_seg.reason:
                        cur_seg.reason += ",possible_missed_boundary"

            decisions.append(dec)
            prev = dec

        if cur_seg is not None:
            segments.append(cur_seg)

        if str(cfg.get("unknown_mode", "ContiguousRuns")) == "MergeAll":
            segments = _merge_all_unknown(segments)

        return segments, decisions

    def segment_ocr(self, ocr_text: str):
        """Entry point for TTA: one OCR string with [PAGE n] separators.
        Splits into pages (robust to in-document 'Page 1' text), then segments."""
        pages = split_pages(ocr_text)
        segs, decs = self.segment(pages)
        return segs, decs, pages


def _merge_all_unknown(segments: List[DocumentSegment]) -> List[DocumentSegment]:
    """Collapse every Unknown segment into ONE document (reorders pages)."""
    unknown_pages: List[int] = []
    kept: List[DocumentSegment] = []
    review = False
    for s in segments:
        if s.doc_type == "Unknown":
            unknown_pages.extend(range(s.start_page, s.end_page + 1))
            review = review or s.needs_review
        else:
            kept.append(s)
    if unknown_pages:
        kept.append(DocumentSegment(
            start_page=min(unknown_pages), end_page=max(unknown_pages),
            doc_type="Unknown", confidence=0.0, needs_review=True,
            reason="merged_all_unknown(reordered)", ids=[],
        ))
    kept.sort(key=lambda s: s.start_page)
    return kept


def _top2(scores: Dict[str, float]) -> Tuple[Optional[str], float, float]:
    if not scores:
        return None, 0.0, 0.0
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_name, best = ordered[0]
    second = ordered[1][1] if len(ordered) > 1 else 0.0
    return best_name, best, second


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def segment_pages(pages_text: List[str], profiles: Dict = None,
                  config: Dict = None) -> Tuple[List[DocumentSegment], List[PageDecision]]:
    return Segmenter(profiles, config).segment(pages_text)
