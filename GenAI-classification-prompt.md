# GenAI node — gray-zone tie-break (L3)

Runs in the process map **after** TS Step 1, and **only** on pages flagged
`AC_CSS_PAGE<n>_Review = "1"`. Do **not** send all 200 pages — that is slow and
expensive and unnecessary. Typical gray-zone is <10% of pages.

## Node input mapping

Feed the GenAI node these variables per flagged page:

| Variable | Source |
|----------|--------|
| `page_text` | OCR text of the flagged page (top ~40 lines is enough) |
| `prev_tail` | last ~10 lines of the previous page (context for "continuation vs new doc") |
| `known_types` | the list of your 60 type names + a one-line description each |

## Prompt

```
You are a document-boundary classifier inside a document-splitting pipeline.

You are given the OCR text of ONE page, the tail of the PREVIOUS page, and a
list of known document types. Decide whether THIS page is the FIRST PAGE of a
new document, and if so, which type.

Rules:
- "is_start" = true ONLY if this page begins a new document (a new form/letter/
  statement starts here). A page that continues the previous document is false.
- Two documents of the SAME type can be adjacent. If this page starts a new
  instance of the same type as the previous document, is_start is STILL true.
- If it is a start page but matches none of the known types, set type="Unknown".
- If it is a continuation page, set type="" and is_start=false.
- Judge from headers, titles, form numbers, addressee/date blocks, and resets
  in internal page numbering. Do not rely on page numbers alone (often absent).

Known types:
{{known_types}}

Previous page tail:
"""
{{prev_tail}}
"""

This page:
"""
{{page_text}}
"""

Return ONLY JSON, no prose:
{"is_start": <true|false>, "type": "<one known type | Unknown | empty>", "confidence": <0..1>, "reason": "<short>"}
```

## Node output handling

Parse the JSON and write back to the document/page so TS Step 2 (or a small
correction node) can act on it:

- `is_start = true`  → set that page's `SplitPage` (via `AC_CSS_PAGE<n>_Split`
  CustomStorageString, consumed in `Document_AfterSeparatePages`, or apply a
  Batch split in a C#/VB node) and set `_DetType` = `type`.
- `is_start = false` → clear the tentative boundary (merge into previous doc).
- Low `confidence` (< 0.6) → leave for **Document Review** (human) rather than
  trusting it.

## Why this stays cheap

- Only gray-zone pages reach the model (deterministic L1+L2 handle the rest).
- Page text only (no images) → small tokens.
- One call per flagged page; batch them if your node supports it.
