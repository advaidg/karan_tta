"""Tunable configuration for the segmentation engine.

ALL knobs live here so the fine-tuning passes are just edits to DEFAULT_CONFIG
(and are captured in docs/RESULTS.md). No magic numbers in the logic files.
Pure stdlib.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List


# --------------------------------------------------------------------------
# DEFAULT_CONFIG — the live, tuned parameter set.
# Every value is documented; the eval harness drives how we move them.
# --------------------------------------------------------------------------
DEFAULT_CONFIG: Dict[str, float] = {
    # ---- header-zone extraction -----------------------------------------
    "header_ratio": 0.34,        # top fraction of lines treated as the header
    "header_min_lines": 3,       # but always at least this many lines

    # ---- per-type keyword scoring ---------------------------------------
    "w_strong_header": 46.0,     # a strong/start keyword found in the header (tuned P8:
                                 # set just above min_type_score so ONE distinctive title
                                 # clears the Unknown bar -> fixes false-unknown on
                                 # legitimate single-keyword document starts)
    "w_strong_body": 8.0,        # a strong/start keyword found only in the body
    "w_any": 12.0,               # an any-page keyword found anywhere
    "w_negative": -30.0,         # a negative keyword found (penalty)
    "min_type_score": 44.0,      # best type score below this => page is "Unknown"
                                 # (tuned P5: one strong header (35) alone is NOT enough;
                                 #  needs corroboration -> kills single-word false positives)
    "type_conf_denom": 70.0,     # divisor mapping raw score -> 0..1 confidence
    "ambig_margin": 22.0,        # best-minus-second below this => ambiguous (review) (tuned P6)

    # ---- start-page signals (additive into start_score) ------------------
    "w_type_change": 75.0,       # effective type changed vs the open segment (tuned P6)
    "w_id_change": 55.0,         # same type but a different business identifier
    "w_strong_start": 48.0,      # a strong/start keyword sits in the header (tuned P5)
    "w_pagenum_one": 45.0,       # this page parses as "page 1"
    "w_reset": 50.0,             # page number went backwards (e.g. 3 -> 1)
    "w_prev_terminal": 25.0,     # previous page was "page N of N" (terminal)
    "w_lowsim": 25.0,            # same type but low similarity to previous page

    # ---- continuation evidence (subtracts from start_score) -------------
    "w_cont_pagenum": 40.0,      # parsed page number > 1 and not a reset
    "w_cont_id_same": 18.0,      # same business id as the open segment

    # ---- similarity ------------------------------------------------------
    "sim_low": 0.24,             # Jaccard below this counts as "low similarity" (tuned P5)

    # ---- decision thresholds --------------------------------------------
    "start_threshold": 44.0,     # start_score >= this => new document (tuned P5)
    "start_low": 25.0,           # [start_low, start_threshold) => gray zone (review)

    # ---- behaviour -------------------------------------------------------
    # "ContiguousRuns" (recommended) or "MergeAll" (collapse every unknown page
    # into one document; reorders pages).
    "unknown_mode": "ContiguousRuns",
}


def get_config(overrides: Dict[str, float] = None) -> Dict[str, float]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update(overrides)
    return cfg


def load_profiles(path: str = None) -> Dict:
    """Load the document-type profiles JSON and pre-normalise its keywords."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "profiles.json")
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw
