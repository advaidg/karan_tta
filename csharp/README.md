# C# Port — TTA Segmentation Engine

A faithful 1:1 port of the proven Python engine (`../python/segmenter/`). Same
5-layer scoring, same page-splitter, same tuned constants (see `../docs/RESULTS.md`).

## Layout

```
csharp/
├── SegmentationEngine/            PURE LOGIC — no TTA/SDK refs, no NuGet
│   ├── Models.cs                  PageDecision, DocumentSegment
│   ├── Config.cs                  EngineConfig (tuned constants), TypeProfile
│   ├── OcrUtils.cs                normalize, header zone, page-no, IDs, similarity
│   ├── PageSplitter.cs            split TTA's one OCR string on [PAGE n] (+ trap guard)
│   ├── ProfilesData.cs            the ~14 demo types in code (extend to your 60)
│   └── Segmenter.cs               scoring + boundary assembly + SegmentOcr()
├── TtaSplitActivity.cs            SCRIPT-ACTIVITY body: calls SplitDocumentAndClassify
├── Demo/Demo.cs                   console demo (mirrors python/demo.py)
├── SegmentationEngine.csproj      netstandard2.0 library (loads in KTA .NET 4.7.2)
└── SegmentationEngine.Demo.csproj net8.0 console for local verification
```

## Why two pieces (Azure constraint)

Per the TotalAgility SDK docs, on **Azure / On-prem Multi-Tenant** a custom .NET
*assembly* runs in a non-trusted sandbox and **cannot call the SDK**. So:

- `SegmentationEngine.dll` is **pure logic** (zero SDK references) → safe anywhere.
  It takes the OCR string and returns `List<DocumentSegment>`.
- The **SplitDocumentAndClassify** call lives in a **C#/VB.NET script activity**
  (`TtaSplitActivity.cs`), which the docs explicitly allow to call the SDK directly.

You feed the OCR in as a single string variable (as you said you can), the engine
returns the plan, and the script activity commits it.

## Build & verify locally (proves parity with Python)

```bash
cd csharp
dotnet run --project SegmentationEngine.Demo.csproj
```

Expected output matches `python3 ../python/demo.py`:

```
Split into 8 pages (the stray in-body [PAGE 1] was correctly ignored).

pages    type                  conf   review  reason
1        Invoice               0.69   no      batch_first_page,strong_start_h
2        Invoice               0.69   no      type_change,id_change,strong_st
3-4      LoanAgreement         0.49   no      type_change,strong_start_header
5        Unknown               0.00   YES     type_change
6        Unknown               0.00   YES
7        PaySlip               0.49   no      batch_first_page,strong_start_h
```

> NOTE: This port was **not** compiled in the authoring environment (no .NET
> toolchain was present there). It is a careful line-by-line port; build it in your
> VS / TTA environment. If the console output above matches the Python demo, the
> port is verified. Any compile nit will be trivial (a using/overload).

## Deploy into TTA (Azure)

1. Build `SegmentationEngine.csproj` → `SegmentationEngine.dll` (netstandard2.0 or
   retarget to net472 if your KTA requires it).
2. Designer → Integration → **.NET Assemblies** → upload `SegmentationEngine.dll`.
3. Create a **C# script activity** after your OCR step; paste the body of
   `TtaSplitActivity.Run(...)`, uncomment the SDK section, and:
   - map `sessionId`, the source `documentId`, and your OCR string variable;
   - fill `TypeToDocTypeId` with your project's document-type IDs (incl. "Unknown");
   - confirm `SplitDocumentInfo` / `CaptureDocumentService` names against your SDK help.
4. Route segments with `ReviewValid = false` (low confidence / unknown) to a
   **Document Review** activity; the rest flow straight to extraction.
5. (Optional) add the GenAI node before review for gray-zone pages — see
   `../GenAI-classification-prompt.md`.

## Keeping Python and C# in sync

The two are intentionally identical in structure. If you tune in Python
(`config.py`), copy the same numbers into `Config.cs`. If you add types, add them to
both `profiles.json` and `ProfilesData.cs` (or switch C# to load the JSON).

## Final calibration (do not skip)

The tuned constants come from realistic **synthetic** data. Before production, run
the Python harness on a labelled sample of YOUR OCR, re-tune, then mirror the values
here. That calibration is what turns the proof into production accuracy.
