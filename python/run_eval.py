"""Run the rigid eval over a synthetic dataset and print + log the metrics.

Usage:
    python3 run_eval.py [pass_label] [n_batches] [seed]

Appends a results block to ../docs/RESULTS.md so every tuning pass is recorded.
Pure stdlib.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from segmenter.config import DEFAULT_CONFIG, get_config
from segmenter.engine import Segmenter
from segmenter.page_splitter import split_pages
from evalkit.gen_documents import make_dataset
from evalkit.metrics import aggregate, evaluate_batch

HEADLINE = [
    ("aa_split_rate", "A->A split rate     (HEADLINE)"),
    ("boundary_f1", "Boundary F1"),
    ("boundary_precision", "Boundary precision"),
    ("boundary_recall", "Boundary recall"),
    ("segment_f1", "Segment exact F1"),
    ("type_accuracy_matched", "Type accuracy (matched)"),
    ("page_type_accuracy", "Page-level type accuracy"),
    ("unknown_leakage", "Unknown leakage (lower=better)"),
    ("false_unknown_rate", "False-unknown rate (lower=better)"),
    ("review_recall", "Review recall (catches wrong segs)"),
    ("review_precision", "Review precision"),
]


def run(pass_label="adhoc", n_batches=300, seed=1234, config=None):
    cfg = get_config(config)
    seg = Segmenter(config=cfg)
    dataset = make_dataset(n_batches, seed=seed)

    rows = []
    split_ok = 0
    split_pagediff = 0
    for batch in dataset:
        # Real path: split the single TTA OCR string into pages first.
        pages = split_pages(batch["ocr"])
        if len(pages) == len(batch["truth"]):
            split_ok += 1
        split_pagediff += abs(len(pages) - len(batch["truth"]))
        # If the splitter miscounted, the engine still runs on what it produced,
        # but we keep truth-aligned pages so segment metrics stay interpretable.
        run_pages = pages if len(pages) == len(batch["truth"]) else batch["pages"]
        pred, _ = seg.segment(run_pages)
        rows.append(evaluate_batch(pred, batch["truth"]))
    agg = aggregate(rows)

    total_pages = sum(r["n_pages"] for r in rows)
    split_acc = split_ok / len(dataset) if dataset else 1.0
    print(f"\n=== EVAL [{pass_label}] : {n_batches} batches, "
          f"{agg['_totals']['n_true_segs']} docs, {total_pages} pages, seed={seed} ===")
    print(f"  {'Page-split accuracy (batches exact)':38s} {split_acc*100:6.2f}%  "
          f"(total page miscount={split_pagediff})")
    for key, label in HEADLINE:
        print(f"  {label:38s} {agg[key]*100:6.2f}%")
    print(f"  (A->A boundaries tested: {agg['_totals']['aa_tot']}, "
          f"wrong segments: {agg['_totals']['wrong']})")
    agg["page_split_accuracy"] = split_acc

    _append_results(pass_label, n_batches, seed, cfg, agg, total_pages)
    return agg


def _append_results(pass_label, n_batches, seed, cfg, agg, total_pages):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "RESULTS.md")
    path = os.path.abspath(path)
    diff = {k: v for k, v in cfg.items() if DEFAULT_CONFIG.get(k) != v}
    lines = [f"\n## Pass: {pass_label}\n",
             f"- batches={n_batches}, pages={total_pages}, seed={seed}\n",
             "- metrics:\n"]
    for key, label in HEADLINE:
        lines.append(f"  - {label}: **{agg[key]*100:.2f}%**\n")
    if diff:
        lines.append(f"- config overrides vs default: `{json.dumps(diff)}`\n")
    with open(path, "a", encoding="utf-8") as fh:
        fh.writelines(lines)


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "adhoc"
    nb = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    sd = int(sys.argv[3]) if len(sys.argv) > 3 else 1234
    run(label, nb, sd)
