# ProfilesJson — how to use and edit it

You **always pass `ProfilesJson`** — it is the ONLY source of profiles. That means you
can tune the splitter forever without touching/recompiling the C# script. This file
explains the ready-made `ProfilesJson.sample.json` and how to change it.

> The C# node reads the `ProfilesJson` input variable. There are **no built-in
> profiles** — `ProfilesJson` is **required**. If it's empty the node throws a clear
> error; if the JSON is malformed it throws a parse error naming the problem. (Keep a
> known-good copy of `ProfilesJson.sample.json` so a bad paste is easy to restore.)

## Structure

```jsonc
{
  "config": { ...global thresholds... },   // optional; omit to use defaults
  "types": {
    "TypeName": {
      "strong_start": [ ... ],   // distinctive PAGE-1 titles for this doc
      "first_page":   [ ... ],   // phrases that appear ONLY on page 1 (optional)
      "any_page":     [ ... ],   // supporting keywords (anywhere in the doc)
      "negative":     [ ... ],   // phrases that mean it's a DIFFERENT type
      "max_pages":    1          // 1 = single-page form; n = cap; 0 = unbounded
    }
  }
}
```

## What each field does (this is where accuracy comes from)

| Field | Effect | How to choose |
|---|---|---|
| `strong_start` | Big score when found **in the page header**; this is the main "what type is this / is this a first page" signal. | Use the exact title text as it prints on page 1 (e.g. `"closing disclosure"`, `"deed of trust"`). Lowercase; punctuation is ignored by the engine. |
| `first_page` | Lets the engine **split two of the SAME type in a row** when there are no page numbers: a page-1-only phrase reappearing = a new instance starts. | Pick a phrase that appears on page 1 but NOT on later pages (e.g. CD: `"statement of final loan terms"`). Optional but powerful for multi-page types. |
| `any_page` | Smaller score, raises confidence the doc really is this type. | Field labels / terms common to the doc (`"loan terms"`, `"escrow"`). |
| `negative` | **Subtracts** score — stops a look-alike type from winning. | Titles/phrases of the type most often confused with this one. |
| `max_pages` | Caps a document's length so a same-type page beyond the cap starts a new doc. **The key A,A lever for forms.** | `1` for one-page forms (affidavits, notices, certificates, ID, letters); `2`–`4` for short forms; `0` for long docs (Note, Deed of Trust, underwriting findings). |

## The `config` block (global dials — all optional)

| Key | Default | Raise it to… | Lower it to… |
|---|---|---|---|
| `min_type_score` | 44 | mark more pages **Unknown** (stricter) | recognize more as known types |
| `start_threshold` | 44 | split **less** (fewer boundaries) | split **more** |
| `sim_low` | 0.24 | treat more pages as "different content" → more splits | fewer splits |
| `w_strong_header` | 46 | trust titles more | trust titles less |
| `w_strong_start` | 48 | weight a new title as a start more | less |
| `w_type_change` | 75 | split harder when type changes | softer |
| `ambig_margin` | 22 | flag more near-ties for review | flag fewer |
| `unknown_mode` | `"ContiguousRuns"` | — | `"MergeAll"` = collapse ALL unknown pages into one doc (reorders pages) |

## Editing recipes

- **A real document is being over-split** (one doc → several): it's probably a
  multi-page type with `max_pages` too low, or its title repeats every page — set a
  realistic `max_pages` (or `0`) and make sure it has a `first_page` phrase.
- **Two same-type docs are NOT being split**: add a `first_page` phrase that only
  appears on page 1, and/or set `max_pages` to the real page count of one instance.
- **Two types get confused**: add the other type's title to this type's `negative`.
- **Too many pages going to Unknown**: lower `min_type_score`, or add more
  `strong_start` / `any_page` phrases for that type.
- **Adding the remaining 17 types (to reach 62)**: copy a block, set the title(s),
  `max_pages`, done. No code change.

## Validate before you paste (optional but recommended)

Any JSON validator works. To test it actually segments well, drop your labelled OCR
into the Python harness (`python/`) which reads the same fields, or just paste into
the KTA node and run the quick test in `TTA_DEPLOYMENT.md` §9.

## Note on the 45 vs 43

Your sheet listed ~45 types; this sample ships **43** distinct profiles (a couple of
sheet rows are variants/aliases folded into one type, e.g. the two Patriot Act rows
and the privacy-notice variants). Add or split any of them freely — it's just JSON.
