using System.Collections.Generic;

namespace SegmentationEngine
{
    /// <summary>
    /// The engine's per-page verdict. 1:1 port of the Python PageDecision.
    /// </summary>
    public sealed class PageDecision
    {
        public int PageIndex;                 // 0-based position in the batch
        public string BestDocType;            // best matching known type
        public double DocTypeConfidence;      // 0..1
        public string EffectiveType;          // BestDocType, or "Unknown" if below threshold
        public bool IsStartPage;
        public double StartScore;             // raw additive start score
        public bool IsUnknown;
        public bool NeedsReview;
        public List<string> ExtractedIds = new List<string>();
        public int? PageNumber;               // parsed "current" page number
        public int? TotalPages;               // parsed "of N"
        public List<string> Signals = new List<string>();
        public Dictionary<string, double> TypeScores = new Dictionary<string, double>();

        // internal scratch (mirrors the Python dynamic attributes)
        internal bool StrongInHeader;
        internal bool FirstPageSig;
        internal double BestMinusSecond;
        internal List<string> NormTokens = new List<string>();
    }

    /// <summary>
    /// A contiguous run of pages forming one logical document.
    /// StartPage/EndPage inclusive, 0-based. Maps onto a TTA SplitDocumentInfo
    /// (SplitIndex = StartPage). 1:1 port of the Python DocumentSegment.
    /// </summary>
    public sealed class DocumentSegment
    {
        public int StartPage;
        public int EndPage;
        public string DocType;
        public double Confidence;
        public bool NeedsReview;
        public string Reason = "";
        public List<string> Ids = new List<string>();

        public int PageCount { get { return EndPage - StartPage + 1; } }
    }
}
