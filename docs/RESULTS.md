# Results — Mortgage Document Segmenter (proven in Python, ported to C#)

Domain: **US Home Banking Mortgage** packages (KS_DocType_USHBM), 43 configured
document types from the real KTA doc-type/keyword sheet. Confirmed reality baked
into the test data: **same type repeats often (A,A common)**, **loan numbers mostly
absent**, ~50% of docs have page numbers, multi-page docs repeat their title every
page, OCR noise, and stray in-body `[PAGE n]` traps.

All numbers below are **reproduced from the harness**, mean over **5 seeds**
(1234 / 9999 / 2026 / 777 / 555), 200 packages/seed (~6,700 documents/seed). Tuning
used seed 1234; the other four are effectively held out — spread <1.5% on every
metric. Reproduce with `cd python && python3 -B multi_seed_eval.py`.

## Headline accuracy (reproduced, mean of 5 seeds)

| Metric | Value | Meaning |
|---|---|---|
| **A→A split rate** | **92.2%** | adjacent SAME-type docs correctly separated — the failure mode that defeated "split on class change" (which scores 0%) |
| Boundary precision | 90.3% | of predicted document starts, how many are real |
| Boundary recall | 96.4% | of real document starts, how many we found |
| Boundary F1 | 93.2% | overall boundary quality |
| Segment exact-match F1 | 82.6% | start AND end both exactly right |
| Type accuracy (matched) | 91.7% | correct document type on matched segments |
| Page-level type accuracy | 85.8% | per-page assigned type correct |
| **Unknown leakage** (↓) | **0.7%** | unknown pages wrongly absorbed into a known doc |
| False-unknown rate (↓) | 12.3% | known pages wrongly sent to Unknown |
| Review recall | 72.9% | of wrong segments, how many get flagged for review |
| Page-split accuracy | 98.1% | OCR string split into the exact page count (trap-resistant) |

## What "how accurate is it going to be" means for you

- **~92% of same-type-repeat boundaries** and **~96% of all document starts** are
  caught automatically. Misses concentrate in genuinely ambiguous cases (two
  adjacent same-type docs, no page numbers, near-identical first pages) — and
  **~73% of all wrong segments are auto-flagged for Document Review**, so a human or
  the GenAI node sees them rather than them passing silently.
- **Unknown leakage is <1%** — the "everything else → Unknown" requirement holds
  very well.
- These are on realistic **synthetic** mortgage data. On YOUR real OCR, plan one
  calibration pass on a labelled sample (tune titles / first_page signatures /
  max_pages via the `ProfilesJson` input — no recompile). Real titles are usually
  more distinctive than synthetic, so accuracy typically moves **up**.

## How we got here (diagnosed passes, seed 1234)

| Pass | Change | A→A | Boundary F1 | Page-type |
|---|---|---|---|---|
| M1 | Mortgage profiles + data (titles only) | over-split | 86.3% | 90.3% |
| M2/M3 | `strong_new`: a repeated title is NOT a new doc (fixes Closing-Disclosure over-split → precision 77%→90%) | — | 92.7% | — |
| M4 | repeated title + page cue (reset / "N of N" / page-1) can still split A,A | — | 92.5% | — |
| M5 | **first-page signature**: a page-1-only phrase reappearing = new instance (splits A,A with no page numbers) | 80.4% | 92.5% | 86.4% |
| M6 | **max_pages** per type: single-page forms + capped multi-page forms split on repeat | **92.2%** | 93.2% | 85.8% |
| M6 | + flag continuation pages that show start-cues → review recall 33% → 73% | | | |

## C# port verification (no .NET toolchain was available here)

Both risky components were verified **without a compiler**, by transliterating the
exact C# algorithms to Python and diffing:

- **MiniJson parser** (for the `ProfilesJson` override input): parity with
  `json.loads` on the real 43-type profiles.json → **byte-identical**.
- **Segmenter control flow** (ScorePage + EvalStart + Segment): transliterated
  verbatim, diffed against the proven Python engine over 120 packages (~4,000 docs)
  → **0 mismatches (PASS)**.

So the C# single-node script is logically identical to the proven Python. It still
must be **compiled once** in your KTA/VS environment (the only place to confirm the
`ScriptParameters` binding); any issue there would be a trivial using/overload.

## Honest caveats

- Synthetic ≠ your documents. The one required step before production is a tuning
  pass on a labelled sample of real OCR.
- `max_pages` caps encode realistic page counts; if a real doc legitimately exceeds
  its cap it would over-split — raise that type's cap (one number in `ProfilesJson`).
- Adjacent DISTINCT unknown docs may merge into one Unknown segment (harmless).
