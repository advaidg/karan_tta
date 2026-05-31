// ============================================================================
//  TTA / KTA binding — C# SCRIPT ACTIVITY body
// ============================================================================
//  Azure / On-prem Multi-Tenant note (from the TotalAgility SDK docs):
//    - Custom .NET *assemblies* run in a non-trusted sandbox and may NOT call the
//      TotalAgility SDK. So keep the SegmentationEngine assembly PURE LOGIC
//      (it has zero SDK references — safe to reference from anywhere).
//    - You MAY call the SDK directly from a C#/VB.NET SCRIPT ACTIVITY. So the
//      SplitDocumentAndClassify call lives HERE, in the script activity, not in
//      the engine assembly.
//
//  Flow:
//    1. TTA gives you the whole OCR as ONE string variable (with [PAGE n] markers).
//    2. The pure SegmentationEngine turns it into a list of DocumentSegment.
//    3. We translate segments -> SplitDocumentInfoCollection and call
//       CaptureDocumentService.SplitDocumentAndClassify on the source document.
//
//  CaptureDocumentService.SplitDocumentAndClassify(
//      sessionId, reportingData, documentId, SplitDocumentInfoCollection)
//    - splits the source doc at each SplitIndex (0-based page where a NEW doc
//      begins), assigns DocumentTypeIdentity, ConfidenceLevel, ReviewValid.
//
//  This is a TEMPLATE. Confirm exact type names / overloads against your installed
//  SDK help (Designer > Help) — they are stable across KTA 7.7 -> 2026.1 but
//  namespaces/property casing can vary slightly by version.
// ============================================================================

using System.Collections.Generic;
using SegmentationEngine;
// using Agility.Sdk.Model.Capture;            // SplitDocumentInfo, SplitDocumentInfoCollection
// using TotalAgility.Sdk;                      // CaptureDocumentService
// using Agility.Sdk.Model.Params;             // ReportingData, DocumentTypeIdentity

public class TtaSplitActivity
{
    // Map our engine type names -> your TTA document type IDs (GUIDs/names).
    // Fill this from your project's document types. "Unknown" -> your Unknown type.
    private static readonly Dictionary<string, string> TypeToDocTypeId =
        new Dictionary<string, string>
        {
            // { "Invoice", "<Invoice document type id>" },
            // { "Unknown", "<Unknown document type id>" },
        };

    private const double AutoThreshold = 0.85;   // >= -> no review; else ReviewValid=false

    /// <summary>
    /// Script-activity entry point. Wire your TTA variables to the parameters.
    /// </summary>
    /// <param name="sessionId">TTA session id (available in script activities).</param>
    /// <param name="documentId">The source (whole-batch) document instance id.</param>
    /// <param name="ocrText">The single OCR string variable from TTA (with [PAGE n]).</param>
    public static void Run(string sessionId, string documentId, string ocrText)
    {
        // 1) PURE LOGIC — no SDK here.
        var engine = new Segmenter(ProfilesData.Default(), ProfilesData.GenericIdRegex(),
                                   EngineConfig.Default());
        List<PageDecision> decisions;
        List<string> pages;
        List<DocumentSegment> segments = engine.SegmentOcr(ocrText, out decisions, out pages);

        // 2) Build the split info. SplitIndex = the 0-based page where a NEW document
        //    begins. The FIRST segment starts at page 0 and is the source document
        //    remainder, so we add split points for segments[1..].
        /*
        var infoCollection = new SplitDocumentInfoCollection();
        for (int i = 1; i < segments.Count; i++)
        {
            var seg = segments[i];
            var info = new SplitDocumentInfo
            {
                SplitIndex = seg.StartPage,                       // 0-based
                DocumentTypeIdentity = ResolveDocType(seg.DocType),
                ConfidenceLevel = seg.Confidence,
                ClassificationConfident = seg.Confidence >= AutoThreshold && !seg.NeedsReview,
                ReviewValid = !(seg.NeedsReview || seg.Confidence < AutoThreshold),
            };
            infoCollection.Add(info);
        }

        // Also set the type/review of the FIRST (source) segment if your flow needs it,
        // e.g. via UpdateDocumentTypeWithConfidence2 on documentId.

        var svc = new CaptureDocumentService();
        ReportingData reporting = null;
        DocumentIdentityCollection newDocs =
            svc.SplitDocumentAndClassify(sessionId, reporting, documentId, infoCollection);
        */

        // 3) Until the SDK lines above are enabled, you can surface the plan for
        //    debugging by writing `segments` to a TTA variable / log.
        //    Each segment -> one output document; NeedsReview -> route to Document Review.
    }

    /*
    private static DocumentTypeIdentity ResolveDocType(string engineType)
    {
        string id;
        if (!TypeToDocTypeId.TryGetValue(engineType, out id))
            TypeToDocTypeId.TryGetValue("Unknown", out id);
        return new DocumentTypeIdentity { Id = id };
    }
    */
}
