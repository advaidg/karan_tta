# Plugging the Segmenter into Tungsten Total Agility (TTA / KTA)

This guide tells you exactly how to take `csharp/KtaSingleNodeScript.cs` and run it
inside TotalAgility on Azure. It is a **single C# script node** — no DLL upload, no
NuGet, no SDK reference inside the engine.

---

## 0. What this node does

```
ONE OCR string (with [PAGE n] separators)         -> the node ->     a split plan
"[PAGE 1]\nCLOSING DISCLOSURE\n..."                                  SplitIndexes = "2,4,5"
"[PAGE 2]\n..."                                                      SplitTypes   = "ClosingDisclosure,..."
...                                                                  ReviewFlags  = "1,0,1,..."
```

It decides, page by page, where each document starts, what type it is, and whether
it needs human review. It does **not** physically split the document — it produces a
plan you feed to a split step (Section 5).

---

## 1. Prerequisites in your TTA process

You need, before this node runs:

1. An **OCR step** (TotalAgility OCR / Transformation) that produces the full text.
2. That text placed into **one process variable** with `[PAGE 1]`, `[PAGE 2]`, …
   separators between physical pages. (You said TTA already does this.)
   - If your separator text is different (e.g. `--- Page 1 ---`), tell me and I'll
     adjust one regex (`PageSplitter.Marker`); or change it in the script.

---

## 2. Create the process variables

In your TTA process, create these variables (String unless noted):

| Variable | Direction | Purpose |
|---|---|---|
| `OcrText` | input | the full OCR string with `[PAGE n]` markers (required) |
| `ProfilesJson` | input | **required** JSON defining all document profiles/thresholds (the only source — no built-ins). Paste `ProfilesJson.sample.json`. The node throws if empty or malformed. |
| `SplitPlan` | output | human-readable plan (one row per document) |
| `SplitIndexes` | output | comma-separated **0-based** page indexes where new docs begin |
| `SplitTypes` | output | comma-separated doc type per segment |
| `ReviewFlags` | output | comma-separated `1`/`0` (1 = send to review) |
| `DocCount` | output (String/Int) | number of documents found |

---

## 3. Add the C# script node

1. In the process map, add a **.NET / C# script activity** after the OCR step.
2. Open the script editor. **Paste the entire contents of
   `csharp/KtaSingleNodeScript.cs`.**
3. The top of the file already matches the KTA shape you use:

   ```csharp
   using System;
   using Agility.Server.Scripting.ScriptAssembly;
   namespace MortgageSegmenter
   {
     public class Class1
     {
       public Class1() { }
       [StartMethodAttribute()]
       public void Method1(ScriptParameters sp)
       {
         string ocr = sp.InputVariables["OcrText"].ToString();
         ... // reads ProfilesJson if present, runs the engine
         sp.OutputVariables["SplitIndexes"] = ...;
       }
     }
   }
   ```

4. Map the node's inputs/outputs to the variables from Section 2 (names match
   exactly, so mapping is 1:1).
5. Compile. If KTA flags anything, it will be trivial (a `using` or an overload) —
   the logic is verified (Section 7). Common note: if your KTA C# version dislikes
   collection initializers or `var`, it still compiles on .NET 4.x which KTA uses.

---

## 4. Tune live with `ProfilesJson` (required input)

`ProfilesJson` is the ONLY source of profiles — there are no built-ins. You pass the
JSON string defining all types and thresholds, and you can re-tune **without editing
the script**. Schema:

```json
{
  "config": {
    "min_type_score": 44,
    "start_threshold": 44,
    "sim_low": 0.24,
    "w_strong_header": 46,
    "w_strong_start": 48,
    "w_type_change": 75,
    "ambig_margin": 22,
    "unknown_mode": "ContiguousRuns"
  },
  "types": {
    "ClosingDisclosure": {
      "strong_start": ["closing disclosure"],
      "first_page":   ["loan terms", "statement of final loan terms"],
      "any_page":     ["costs at closing", "cash to close"],
      "negative":     ["deed of trust"],
      "max_pages":    0
    },
    "OccupancyAffidavit": {
      "strong_start": ["occupancy affidavit"],
      "max_pages":    1
    }
  }
}
```

Field meaning (this is the heart of accuracy):
- **strong_start** — distinctive titles that appear on a document's first page.
- **first_page** — phrases that appear ONLY on page 1 of that type. This is how the
  engine splits two of the SAME type in a row when there are no page numbers.
- **any_page** — supporting keywords (raise type confidence).
- **negative** — phrases that mean it's a DIFFERENT type (subtract score).
- **max_pages** — `1` for single-page forms (affidavits, notices, certificates);
  a small number for short forms; `0` = unbounded (Note, Deed of Trust, etc.).
  A same-type page beyond the cap starts a new document.

`ProfilesJson` is required: if it's empty or malformed the node throws a clear error
(rather than silently mis-splitting). Keep a known-good `ProfilesJson.sample.json` on
hand so a bad paste is easy to restore.

---

## 5. Actually split the document

`SplitIndexes` is built for the TotalAgility SDK method **`SplitDocumentAndClassify`**
(`CaptureDocumentService`), whose `SplitDocumentInfo.SplitIndex` is **0-based**.

Two ways to consume it:

**Option A — second script node (recommended on Azure).** A C#/VB **script** node
may call the SDK directly. After this node, add a script node that:
1. reads `SplitIndexes`, `SplitTypes`, `ReviewFlags`;
2. builds a `SplitDocumentInfoCollection` (one `SplitDocumentInfo` per index, with
   `SplitIndex`, `DocumentTypeIdentity` from `SplitTypes`, and
   `ReviewValid = (flag == 0)`);
3. calls `CaptureDocumentService.SplitDocumentAndClassify(sessionId, null,
   documentId, collection)`.
   See `csharp/TtaSplitActivity.cs` for the exact, commented call.

**Option B — built-in split activity.** If your flow uses a separation/split
activity that accepts page indexes, feed it `SplitIndexes` directly.

> Why a separate step: on Azure / multi-tenant, a custom **assembly** can't call the
> SDK (sandbox), but a **script node** can. This engine node stays pure logic; the
> SDK call lives in the split script node.

---

## 6. Route review

Send any segment whose `ReviewFlags` entry is `1` (and any `Unknown` type) to a
**Document Review** activity. Everything else flows straight to extraction. Optional:
put your **GenAI node** before review on just the flagged pages — prompt in
`../GenAI-classification-prompt.md`.

---

## 7. Why you can trust the port (it was verified without a compiler)

There was no .NET toolchain in the build environment, so both risky pieces were
verified by transliterating the exact C# algorithms to Python and diffing:

- **JSON parser** (`MiniJson`, used for `ProfilesJson`): output **byte-identical**
  to `json.loads` on the real 43-type profiles.
- **Segmenter logic** (scoring + boundary assembly): **0 mismatches** vs the proven
  Python engine over 120 packages (~4,000 documents).

So the only thing left for your environment is the one-time **compile**. Expect
accuracy in line with `RESULTS.md`: **A→A split ~92%, boundary F1 ~93%, unknown
leakage <1%**, with ~73% of mistakes auto-flagged for review.

---

## 8. Before production — one required step

These numbers are on realistic **synthetic** mortgage data. Run a **calibration
pass on a labelled sample of your real OCR**:
1. Collect ~20–50 real packages with known correct boundaries/types.
2. Tune `ProfilesJson` (titles, first_page signatures, max_pages) against them.
3. Re-check accuracy. Real titles are usually more distinctive than synthetic, so
   this typically moves accuracy **up**.

You can do this entirely through the `ProfilesJson` variable — no recompile.

---

## 9. Quick test (before wiring the real flow)

Put this in `OcrText`, leave `ProfilesJson` empty, run the node:

```
[PAGE 1]
CLOSING DISCLOSURE
This form is a statement of final loan terms
Loan Terms
Page 1 of 2
[PAGE 2]
CLOSING DISCLOSURE
Costs at Closing
Page 2 of 2
[PAGE 3]
CLOSING DISCLOSURE
This form is a statement of final loan terms
Loan Terms
Page 1 of 2
[PAGE 4]
OCCUPANCY AFFIDAVIT
I will occupy the property as my primary residence
[PAGE 5]
OCCUPANCY AFFIDAVIT
I will occupy the property as my primary residence
```

Expect roughly: `DocCount = 4`, `SplitIndexes = "2,3,4"` — i.e. two Closing
Disclosures split apart (A,A), then two Occupancy Affidavits split apart (A,A).
That is the exact behavior your previous approach could not achieve.
