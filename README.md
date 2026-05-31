# karan_tta — Mortgage Document Segmenter for Tungsten TotalAgility (TTA/KTA)

Split a large mixed **US Home Banking Mortgage** OCR package (120–200 pages, ~45 of
62 document types, in any order) into one file per logical document **inside
TotalAgility** — including the hard case where the **same document type repeats
back-to-back (A, A)** and must become **separate** documents, with anything
unrecognized going to **Unknown** for review.

Proven first in **pure Python (stdlib only, zero dependencies)** against a rigid
evaluation on realistic synthetic mortgage OCR, then ported 1:1 to a **single C#
script node** for KTA.

## Why the old approach failed, and the fix

"Separate when the document class changes" **cannot** split `A, A` (the class never
changes). This engine instead detects the **first page of every document** using
five deterministic signals tuned for mortgage reality (loan numbers are usually
absent, so it keys on titles, **page-1-only signatures**, page-number resets, and
**per-type page caps** — not IDs).

## Accuracy (reproduced, mean of 5 seeds — see `docs/RESULTS.md`)

| Metric | Value |
|---|---|
| **A→A split rate** (headline) | **92.2%** |
| Boundary recall / precision / F1 | 96.4% / 90.3% / 93.2% |
| Type accuracy (matched) | 91.7% |
| **Unknown leakage** (↓) | **0.7%** |
| Review recall (mistakes auto-flagged) | 72.9% |
| Page-split accuracy (trap-resistant) | 98.1% |

The previous "split on class change" baseline scores **0%** on A→A.

## What to do with it

**`docs/TTA_DEPLOYMENT.md`** is the step-by-step guide: create variables, paste
`csharp/KtaSingleNodeScript.cs` into one KTA C# script node, map
`OcrText`/`ProfilesJson` in and `SplitIndexes`/`SplitTypes`/`ReviewFlags` out, then
feed `SplitIndexes` to `SplitDocumentAndClassify`. Tune live via the `ProfilesJson`
input variable — no recompile.

## Layout

```
python/                 Proof + rigid eval (stdlib only — the source of truth)
  segmenter/            engine, ocr_utils, page_splitter, config, profiles.json (43 mortgage types)
  evalkit/              gen_documents (synthetic mortgage OCR + ground truth), metrics
  run_eval.py           single-seed metric table
  multi_seed_eval.py    mean across 5 seeds
  diag_aa.py            A->A miss diagnostic
  demo.py               readable end-to-end demo
csharp/
  KtaSingleNodeScript.cs   ← THE DELIVERABLE: one self-contained KTA C# node
                             (engine + 43 profiles + JSON override parser)
  SegmentationEngine/      multi-file version of the same engine (optional)
  TtaSplitActivity.cs      SplitDocumentAndClassify binding (commented)
docs/
  TTA_DEPLOYMENT.md     how to plug into TTA  (start here)
  RESULTS.md            accuracy + tuning passes + honest caveats
  EVAL_METHODOLOGY.md   how the proof works
GenAI-classification-prompt.md   native GenAI node prompt for gray-zone pages
```

## Run the proof locally

```bash
cd python
python3 -B demo.py                 # readable end-to-end demo
python3 -B run_eval.py final 300 1234   # full metric table (one seed)
python3 -B multi_seed_eval.py      # mean across 5 seeds
```

## C# port verification

No .NET toolchain was used to author this, so the C# was verified by transliterating
its exact algorithms to Python and diffing against the proven engine:
- JSON profile parser → **byte-identical** to `json.loads`;
- segmenter control flow → **0 mismatches** over 120 packages.

It must still be **compiled once** in your KTA/VS environment (the only place to
confirm the `ScriptParameters` binding).

## Before production

These numbers are on realistic **synthetic** data. Run one calibration pass on a
labelled sample of YOUR real OCR (tune titles / first_page signatures / max_pages
via `ProfilesJson`). Real titles are usually more distinctive than synthetic, so
accuracy typically goes **up**.

## License

MIT — see `LICENSE`.
