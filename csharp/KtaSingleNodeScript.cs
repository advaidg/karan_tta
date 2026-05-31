// =============================================================================
//  KTA / TotalAgility SINGLE-NODE C# SCRIPT  —  Mortgage Document Segmenter
// =============================================================================
//  ONE self-contained file. Paste into a single KTA C# script node. No external
//  assemblies, no NuGet, no TotalAgility SDK calls -> safe on Azure/multi-tenant.
//
//  ---- KTA ENTRY (matches the sample you gave) --------------------------------
//    using Agility.Server.Scripting.ScriptAssembly;
//    [StartMethodAttribute()]
//    public void Method1(ScriptParameters sp) { ... }
//  To go live: (1) uncomment the `using Agility...` line, (2) uncomment the
//  [StartMethodAttribute()] line, (3) replace the `object sp` param with
//  `ScriptParameters sp`. Nothing else changes.
//
//  ---- INPUT VARIABLES (sp.InputVariables) ------------------------------------
//    "OcrText"      (required) : the ENTIRE package OCR as ONE string, containing
//                               TTA's [PAGE n] separators. (A document's own body
//                               may also contain "Page 1" or a stray "[PAGE 1]" —
//                               both handled.)
//    "ProfilesJson" (optional) : JSON to OVERRIDE the built-in mortgage profiles,
//                               so you can tune without recompiling. Schema:
//      {
//        "config": { "min_type_score": 44, "start_threshold": 44, ... },   // optional
//        "types": {
//          "ClosingDisclosure": {
//            "strong_start": ["closing disclosure"],
//            "first_page":   ["loan terms","statement of final loan terms"],
//            "any_page":     ["costs at closing","cash to close"],
//            "negative":     ["deed of trust"],
//            "max_pages":    0
//          },
//          ...
//        }
//      }
//      If "ProfilesJson" is empty/absent, the built-in 43-type set is used.
//
//  ---- OUTPUT VARIABLES (sp.OutputVariables) ----------------------------------
//    "ResultJson"   : PRIMARY output — a single JSON string describing every
//                     document. Shape:
//                     {
//                       "docCount": 24, "pageCount": 127,
//                       "documents": [
//                         { "index":1, "startPage":1, "endPage":1, "pageCount":1,
//                           "type":"ClosingDisclosure", "confidence":0.92,
//                           "needsReview":true, "splitIndex":0, "reason":"..." }, ...
//                       ],
//                       "splitIndexes": [6,11,12]   // 0-based, for SplitDocumentAndClassify
//                     }
//    "SplitIndexes" : (convenience) comma-separated 0-based start indexes.
//    "DocCount"     : number of documents found.
//
//  Proven on mortgage-realistic data (docs/RESULTS.md): A,A split ~96%,
//  boundary F1 ~93%, type accuracy ~91%, unknown leakage <1%.
// =============================================================================

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using Agility.Server.Scripting.ScriptAssembly;

namespace MortgageSegmenter
{
    public class Class1
    {
        public Class1() { }

        [StartMethodAttribute()]
        public void Method1(ScriptParameters sp)
        {
            // Required input: the entire package OCR (with [PAGE n] separators).
            string ocr = sp.InputVariables["OcrText"].ToString();

            // Optional input: profile/config override JSON. Empty if not supplied.
            string profilesJson = "";
            try
            {
                object pj = sp.InputVariables["ProfilesJson"];
                if (pj != null) profilesJson = pj.ToString();
            }
            catch { profilesJson = ""; }   // variable not configured -> use built-in

            SegmentationResult r = Engine.Run(ocr, profilesJson);

            // PRIMARY output: a single clean JSON string describing every document.
            sp.OutputVariables["ResultJson"] = r.Json;
            // Convenience scalars (still handy for simple downstream mapping):
            sp.OutputVariables["SplitIndexes"] = r.SplitIndexes;   // 0-based, comma-separated
            sp.OutputVariables["DocCount"] = r.DocCount.ToString(CultureInfo.InvariantCulture);
        }
    }

    // =====================================================================
    //  RESULT
    // =====================================================================
    public sealed class SegmentationResult
    {
        public string Json = "";          // primary: full JSON document array
        public string SplitIndexes = "";  // 0-based comma-separated start indexes
        public int DocCount = 0;
    }

    // =====================================================================
    //  ENGINE FACADE
    // =====================================================================
    public static class Engine
    {
        public static SegmentationResult Run(string ocrText, string profilesJson)
        {
            EngineConfig cfg;
            List<TypeProfile> profiles = Profiles.Resolve(profilesJson, out cfg);

            var seg = new Segmenter(profiles, cfg);
            List<string> pages;
            List<DocumentSegment> segments = seg.SegmentOcr(ocrText, out pages);

            // ---- build the JSON result ----
            // {
            //   "docCount": 24, "pageCount": 127,
            //   "documents": [
            //     { "index":1, "startPage":1, "endPage":1, "pageCount":1,
            //       "type":"ClosingDisclosure", "confidence":0.92,
            //       "needsReview":true, "splitIndex":0, "reason":"..." }, ...
            //   ],
            //   "splitIndexes": [6,11,12]      // 0-based; feed to SplitDocumentAndClassify
            // }
            var json = new StringBuilder();
            var idx = new StringBuilder();
            json.Append("{\"docCount\":").Append(segments.Count)
                .Append(",\"pageCount\":").Append(pages.Count)
                .Append(",\"documents\":[");
            for (int i = 0; i < segments.Count; i++)
            {
                DocumentSegment s = segments[i];
                if (i > 0) json.Append(',');
                json.Append("{\"index\":").Append(i + 1)
                    .Append(",\"startPage\":").Append(s.StartPage + 1)        // 1-based (human)
                    .Append(",\"endPage\":").Append(s.EndPage + 1)
                    .Append(",\"pageCount\":").Append(s.PageCount)
                    .Append(",\"type\":\"").Append(JsonEsc(s.DocType)).Append('"')
                    .Append(",\"confidence\":").Append(s.Confidence.ToString("0.00", CultureInfo.InvariantCulture))
                    .Append(",\"needsReview\":").Append(s.NeedsReview ? "true" : "false")
                    .Append(",\"splitIndex\":").Append(s.StartPage)           // 0-based (SDK)
                    .Append(",\"reason\":\"").Append(JsonEsc(s.Reason)).Append("\"}");
                if (s.StartPage > 0)
                {
                    if (idx.Length > 0) idx.Append(',');
                    idx.Append(s.StartPage.ToString(CultureInfo.InvariantCulture));
                }
            }
            json.Append("],\"splitIndexes\":[").Append(idx).Append("]}");

            return new SegmentationResult
            {
                Json = json.ToString(),
                SplitIndexes = idx.ToString(),
                DocCount = segments.Count,
            };
        }

        // minimal JSON string escaper (quotes, backslash, control chars)
        private static string JsonEsc(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var sb = new StringBuilder(s.Length + 8);
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.ToString();
        }
    }

    // =====================================================================
    //  CONFIG  (tuned constants — see docs/RESULTS.md)
    // =====================================================================
    public sealed class EngineConfig
    {
        public double HeaderRatio = 0.34; public int HeaderMinLines = 3;
        public double WStrongHeader = 46.0, WStrongBody = 8.0, WAny = 12.0, WNegative = -30.0;
        public double MinTypeScore = 44.0, TypeConfDenom = 70.0, AmbigMargin = 22.0;
        public double StartTypeMin = 76.0;   // type-change needs new type score >= this (or page cue)
        public double WTypeChange = 75.0, WStrongStart = 48.0;
        public double WPagenumOne = 45.0, WReset = 50.0, WPrevTerminal = 25.0, WLowSim = 25.0;
        public double WContPagenum = 40.0, WContTitle = 18.0;
        public double SimLow = 0.24, StartThreshold = 44.0, StartLow = 25.0;
        public bool BreakKnownOnLowSim = true;   // false in mortgage profile (contradiction-only)
        public string UnknownMode = "ContiguousRuns";   // or "MergeAll"
    }

    public sealed class TypeProfile
    {
        public string Name = "";
        public List<string> StrongStart = new List<string>();
        public List<string> FirstPage = new List<string>();
        public List<string> AnyPage = new List<string>();
        public List<string> Negative = new List<string>();
        public int MaxPages = 0;     // 0 = unbounded; 1 = single-page form; n = cap
    }

    // =====================================================================
    //  MODELS
    // =====================================================================
    public sealed class PageDecision
    {
        public int PageIndex; public string BestDocType = "Unknown"; public double DocTypeConfidence;
        public string EffectiveType = "Unknown"; public bool IsStartPage; public double StartScore;
        public bool IsUnknown; public bool NeedsReview;
        public int HasPageNum; public int PageNumber; public int HasTotal; public int TotalPages;
        public List<string> Signals = new List<string>();
        public bool StrongInHeader; public bool FirstPageSig;
        public double BestMinusSecond; public double BestScore;
        public Dictionary<string, double> TypeScores = new Dictionary<string, double>();
        public List<string> NormTokens = new List<string>();
        public int MaxPages;
    }

    public sealed class DocumentSegment
    {
        public int StartPage, EndPage; public string DocType = "Unknown"; public double Confidence;
        public bool NeedsReview; public string Reason = "";
        public int PageCount { get { return EndPage - StartPage + 1; } }
    }

    // =====================================================================
    //  OCR UTILITIES
    // =====================================================================
    public static class Ocr
    {
        private static readonly Regex NonAlnum = new Regex("[^a-z0-9]+", RegexOptions.Compiled);
        private static readonly Regex Ws = new Regex("\\s+", RegexOptions.Compiled);

        public static string Normalize(string text)
        {
            if (text == null) return " ";
            string low = NonAlnum.Replace(text.ToLowerInvariant(), " ");
            low = Ws.Replace(low, " ").Trim();
            return " " + low + " ";
        }

        // LINE-INDEPENDENT header zone (mirrors engine.py): first N words of the
        // page. TTA may deliver a page as multi-line OR one flattened single line;
        // using the first N words makes both behave identically. ratio/minLines are
        // kept for signature compatibility but no longer used.
        public const int HeaderWords = 55;
        public static string Header(string text, double ratio, int minLines)
        {
            if (string.IsNullOrEmpty(text)) return text ?? "";
            string[] parts = text.Split(new[] { ' ', '\t', '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length <= HeaderWords) return text;
            var sb = new StringBuilder();
            for (int i = 0; i < HeaderWords; i++) { if (i > 0) sb.Append(' '); sb.Append(parts[i]); }
            return sb.ToString();
        }

        public static bool Has(string hay, string phrase)
        {
            return phrase.Length > 0 && hay.IndexOf(phrase, StringComparison.Ordinal) >= 0;
        }

        public static List<string> Tokenize(string norm)
        {
            var o = new List<string>();
            foreach (var t in norm.Split(' ')) if (t.Length > 0) o.Add(t);
            return o;
        }

        public static double Jaccard(List<string> a, List<string> b)
        {
            if ((a == null || a.Count == 0) && (b == null || b.Count == 0)) return 1.0;
            if (a == null || b == null || a.Count == 0 || b.Count == 0) return 0.0;
            var sa = new HashSet<string>(a); var sb = new HashSet<string>(b);
            int inter = 0; foreach (var x in sa) if (sb.Contains(x)) inter++;
            int union = sa.Count + sb.Count - inter;
            return union > 0 ? (double)inter / union : 0.0;
        }

        private static readonly Regex[] Pn = new[]
        {
            new Regex(@"page\s+(\d{1,3})\s+of\s+(\d{1,3})", RegexOptions.Compiled),
            new Regex(@"pg\.?\s*(\d{1,3})\s*/\s*(\d{1,3})", RegexOptions.Compiled),
            new Regex(@"\bpage\s*[:#]?\s*(\d{1,3})\s*/\s*(\d{1,3})", RegexOptions.Compiled),
            new Regex(@"\b(\d{1,3})\s*/\s*(\d{1,3})\b", RegexOptions.Compiled),
            new Regex(@"\bpage\s*[:#]?\s*(\d{1,3})\b", RegexOptions.Compiled),
        };

        // returns: hasCur (0/1), cur, hasTot (0/1), tot
        public static void PageNumber(string text, out int hasCur, out int cur, out int hasTot, out int tot)
        {
            hasCur = 0; cur = 0; hasTot = 0; tot = 0;
            if (string.IsNullOrEmpty(text)) return;
            string low = text.ToLowerInvariant();
            var cands = new List<string> { low };
            if (low.Contains("page") || low.Contains("/")) cands.Add(Denoise(low));
            foreach (var c in cands)
                foreach (var pat in Pn)
                {
                    Match m = pat.Match(c);
                    if (!m.Success) continue;
                    int cc; if (!int.TryParse(m.Groups[1].Value, out cc)) continue;
                    int tt = 0; bool hasTt = false;
                    if (m.Groups.Count >= 3 && m.Groups[2].Success)
                    { if (int.TryParse(m.Groups[2].Value, out tt)) hasTt = true; }
                    if (cc <= 0 || cc >= 500) continue;
                    if (hasTt && (tt <= 0 || tt >= 500)) continue;
                    if (hasTt && cc > tt) continue;
                    hasCur = 1; cur = cc; hasTot = hasTt ? 1 : 0; tot = tt; return;
                }
        }

        private static string Denoise(string s)
        {
            var sb = new StringBuilder(s.Length);
            foreach (char ch in s)
            {
                switch (ch)
                {
                    case 'l': case 'i': case '|': sb.Append('1'); break;
                    case 'o': sb.Append('0'); break;
                    case 's': sb.Append('5'); break;
                    default: sb.Append(ch); break;
                }
            }
            return sb.ToString();
        }
    }

    // =====================================================================
    //  PAGE SPLITTER  (split TTA's one OCR string on [PAGE n]; trap-safe)
    // =====================================================================
    public static class PageSplitter
    {
        // Matches [PAGE n] ALONE on a line OR INLINE. Real TTA output flattens
        // newlines ("[PAGE 1] text... [PAGE 2] text..."), so the marker must match
        // mid-line. The monotonic-sequence Filter() guards the in-body trap.
        public static readonly Regex Marker = new Regex(
            @"[\[\(<]\s*page\s+(\d{1,4})\s*[\]\)>]",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        public static List<string> Split(string ocr)
        {
            var pages = new List<string>();
            if (string.IsNullOrEmpty(ocr)) return pages;
            var matches = new List<Match>();
            foreach (Match m in Marker.Matches(ocr)) matches.Add(m);
            if (matches.Count == 0) { if (ocr.Trim().Length > 0) pages.Add(ocr); return pages; }

            List<Match> acc = Filter(matches);
            if (acc.Count == 0) { pages.Add(ocr); return pages; }

            string preamble = ocr.Substring(0, acc[0].Index).Trim();
            for (int i = 0; i < acc.Count; i++)
            {
                int bs = acc[i].Index + acc[i].Length;
                int be = (i + 1 < acc.Count) ? acc[i + 1].Index : ocr.Length;
                string body = ocr.Substring(bs, be - bs).Trim('\n', '\r');
                if (i == 0 && preamble.Length > 0) body = preamble + "\n" + body;
                pages.Add(body);
            }
            return pages;
        }

        private static List<Match> Filter(List<Match> ms)
        {
            var acc = new List<Match>(); int last = -1; bool have = false;
            foreach (var m in ms)
            {
                int n; if (!int.TryParse(m.Groups[1].Value, out n)) continue;
                if (!have) { if (n <= 2) { acc.Add(m); last = n; have = true; } }
                else if (n > last) { acc.Add(m); last = n; }
            }
            return acc.Count > 0 ? acc : ms;
        }
    }

    // =====================================================================
    //  SEGMENTER  (5-layer scoring + boundary assembly; mirrors engine.py)
    // =====================================================================
    public sealed class Segmenter
    {
        private readonly EngineConfig _cfg;
        private readonly List<TypeProfile> _types = new List<TypeProfile>();
        private readonly Dictionary<string, TypeProfile> _byName = new Dictionary<string, TypeProfile>();

        public Segmenter(List<TypeProfile> profiles, EngineConfig cfg)
        {
            _cfg = cfg ?? new EngineConfig();
            foreach (var p in profiles)
            {
                var cp = new TypeProfile
                {
                    Name = p.Name,
                    StrongStart = Norm(p.StrongStart),
                    FirstPage = Norm(p.FirstPage),
                    AnyPage = Norm(p.AnyPage),
                    Negative = Norm(p.Negative),
                    MaxPages = p.MaxPages,
                };
                _types.Add(cp);
                _byName[cp.Name] = cp;
            }
        }

        private static List<string> Norm(List<string> xs)
        {
            var o = new List<string>();
            if (xs != null) foreach (var k in xs) o.Add(Ocr.Normalize(k));
            return o;
        }

        public PageDecision ScorePage(string raw)
        {
            EngineConfig cfg = _cfg;
            string nf = Ocr.Normalize(raw);
            string nh = Ocr.Normalize(Ocr.Header(raw, cfg.HeaderRatio, cfg.HeaderMinLines));

            string bestType = null;
            double best = double.NegativeInfinity, second = double.NegativeInfinity;
            bool bestStrongHeader = false;
            var typeScores = new Dictionary<string, double>();
            foreach (var t in _types)
            {
                double s = 0; bool strongHeader = false;
                foreach (var kw in t.StrongStart)
                {
                    if (Ocr.Has(nh, kw)) { s += cfg.WStrongHeader; strongHeader = true; }
                    else if (Ocr.Has(nf, kw)) { s += cfg.WStrongBody; }
                }
                foreach (var kw in t.AnyPage) if (Ocr.Has(nf, kw)) s += cfg.WAny;
                foreach (var kw in t.Negative) if (Ocr.Has(nf, kw)) s += cfg.WNegative;
                typeScores[t.Name] = s;
                if (s > best) { second = best; best = s; bestType = t.Name; bestStrongHeader = strongHeader; }
                else if (s > second) second = s;
            }
            if (double.IsNegativeInfinity(best)) best = 0;          // no types configured
            if (double.IsNegativeInfinity(second)) second = 0;     // only one type

            bool isUnknown = best < cfg.MinTypeScore;
            string eff = isUnknown ? "Unknown" : bestType;
            double conf = Clamp(best / cfg.TypeConfDenom, 0, 1);

            int hasCur, cur, hasTot, tot;
            Ocr.PageNumber(raw, out hasCur, out cur, out hasTot, out tot);

            bool fpSig = false;
            int maxPages = 0;
            if (bestType != null && !isUnknown && _byName.ContainsKey(bestType))
            {
                TypeProfile bp = _byName[bestType];
                maxPages = bp.MaxPages;
                foreach (var kw in bp.FirstPage) if (Ocr.Has(nf, kw)) { fpSig = true; break; }
            }

            return new PageDecision
            {
                PageIndex = -1,
                BestDocType = bestType ?? "Unknown",
                DocTypeConfidence = conf,
                EffectiveType = eff,
                IsUnknown = isUnknown,
                HasPageNum = hasCur, PageNumber = cur, HasTotal = hasTot, TotalPages = tot,
                StrongInHeader = bestStrongHeader,
                FirstPageSig = fpSig,
                BestMinusSecond = best - second,
                BestScore = best,
                TypeScores = typeScores,
                NormTokens = Ocr.Tokenize(nf),
                MaxPages = maxPages,
            };
        }

        private void EvalStart(PageDecision dec, PageDecision prev, string segType,
                               int segLen, out double score, out List<string> sig)
        {
            EngineConfig cfg = _cfg; score = 0; sig = new List<string>();
            bool typeChanged = segType != null && dec.EffectiveType != segType;
            bool sameType = segType != null && dec.EffectiveType == segType;
            double sim = (prev != null) ? Ocr.Jaccard(prev.NormTokens, dec.NormTokens) : 1.0;
            bool lowSim = prev != null && sim < cfg.SimLow;

            // per-type page cap
            int maxPages = dec.IsUnknown ? 0 : dec.MaxPages;
            bool overCap = sameType && maxPages > 0 && segLen >= maxPages;
            bool singlePageType = (maxPages == 1);

            bool strong = dec.StrongInHeader;
            bool prevStrong = prev != null && prev.StrongInHeader;
            string prevType = prev != null ? prev.EffectiveType : null;

            bool pageOne = dec.HasPageNum == 1 && dec.PageNumber == 1;
            bool reset = dec.HasPageNum == 1 && dec.PageNumber > 1 && prev != null
                         && prev.HasPageNum == 1 && dec.PageNumber < prev.PageNumber;
            bool prevTerminal = prev != null && prev.HasPageNum == 1 && prev.HasTotal == 1
                                && prev.PageNumber == prev.TotalPages;

            bool fpSig = dec.FirstPageSig;
            bool prevFpSig = prev != null && prev.FirstPageSig;
            bool firstPageSignature = fpSig && !prevFpSig;

            bool titleRepeatsOpen = strong && prevStrong && prevType == dec.EffectiveType;
            bool strongNew = strong && (!titleRepeatsOpen || reset || prevTerminal || pageOne
                                        || firstPageSignature || singlePageType || overCap);

            bool typeChangeEvidenced = typeChanged && (strongNew || pageOne || reset || lowSim);
            bool knownToUnknown = segType != null && segType != "Unknown" && dec.IsUnknown && lowSim;
            bool sameTypeNewInstance = sameType && !dec.IsUnknown && firstPageSignature;
            bool hasEvidence = strongNew || pageOne || reset || prevTerminal
                               || typeChangeEvidenced || knownToUnknown
                               || sameTypeNewInstance || overCap;

            if (overCap) { score += cfg.WStrongStart; sig.Add("over_max_pages"); }
            if (sameTypeNewInstance) { score += cfg.WStrongStart; sig.Add("first_page_signature"); }
            if (typeChanged) { score += cfg.WTypeChange; sig.Add("type_change"); }
            if (strongNew) { score += cfg.WStrongStart; sig.Add("strong_start_header"); }
            else if (strong) { score -= cfg.WContTitle; sig.Add("title_repeat"); }
            if (pageOne) { score += cfg.WPagenumOne; sig.Add("pagenum_one"); }
            else if (dec.HasPageNum == 1 && dec.PageNumber > 1)
            {
                if (reset) { score += cfg.WReset; sig.Add("pagenum_reset"); }
                else { score -= cfg.WContPagenum; sig.Add("pagenum_continuation"); }
            }
            if (prevTerminal) { score += cfg.WPrevTerminal; sig.Add("prev_terminal"); }
            if (sameType && !dec.IsUnknown && lowSim) { score += cfg.WLowSim; sig.Add("low_similarity"); }

            if (segType != null && !hasEvidence)
            { score = Math.Min(score, cfg.StartLow - 1.0); sig.Add("continuation_gate"); }
        }

        public List<DocumentSegment> Segment(List<string> pagesText)
        {
            EngineConfig cfg = _cfg;
            var segments = new List<DocumentSegment>();
            DocumentSegment cur = null; PageDecision prev = null;

            for (int i = 0; i < pagesText.Count; i++)
            {
                PageDecision dec = ScorePage(pagesText[i]); dec.PageIndex = i;
                string segType = cur != null ? cur.DocType : null;
                int segLen = cur != null ? (i - cur.StartPage) : 0;
                double score; List<string> sig;
                EvalStart(dec, prev, segType, segLen, out score, out sig);
                dec.StartScore = score; dec.Signals = sig;

                bool forced = (i == 0);
                bool isStart = forced || (score >= cfg.StartThreshold);
                bool gray = !isStart && score >= cfg.StartLow;
                bool ambiguous = dec.BestMinusSecond < cfg.AmbigMargin && !dec.IsUnknown;
                dec.IsStartPage = isStart;
                dec.NeedsReview = gray || ambiguous || dec.IsUnknown;
                if (forced) dec.Signals.Insert(0, "batch_first_page");

                if (isStart || cur == null)
                {
                    if (cur != null) segments.Add(cur);
                    cur = new DocumentSegment
                    {
                        StartPage = i, EndPage = i, DocType = dec.EffectiveType,
                        Confidence = dec.DocTypeConfidence, NeedsReview = dec.NeedsReview,
                        Reason = Join(dec.Signals),
                    };
                }
                else
                {
                    cur.EndPage = i;
                    cur.NeedsReview = cur.NeedsReview || dec.NeedsReview;
                    cur.Confidence = Math.Min(cur.Confidence, dec.DocTypeConfidence);
                    if (dec.StrongInHeader || dec.FirstPageSig)
                    {
                        cur.NeedsReview = true;
                        if (cur.Reason.IndexOf("possible_missed_boundary", StringComparison.Ordinal) < 0)
                            cur.Reason += ",possible_missed_boundary";
                    }
                }
                prev = dec;
            }
            if (cur != null) segments.Add(cur);
            if (cfg.UnknownMode == "MergeAll") segments = MergeAllUnknown(segments);
            return segments;
        }

        public List<DocumentSegment> SegmentOcr(string ocrText, out List<string> pages)
        {
            pages = PageSplitter.Split(ocrText);
            return Segment(pages);
        }

        private static List<DocumentSegment> MergeAllUnknown(List<DocumentSegment> segs)
        {
            var up = new List<int>(); var kept = new List<DocumentSegment>();
            foreach (var s in segs)
            {
                if (s.DocType == "Unknown") for (int i = s.StartPage; i <= s.EndPage; i++) up.Add(i);
                else kept.Add(s);
            }
            if (up.Count > 0)
            {
                int mn = int.MaxValue, mx = int.MinValue;
                foreach (var p in up) { if (p < mn) mn = p; if (p > mx) mx = p; }
                kept.Add(new DocumentSegment { StartPage = mn, EndPage = mx, DocType = "Unknown",
                    Confidence = 0, NeedsReview = true, Reason = "merged_all_unknown(reordered)" });
            }
            kept.Sort(delegate (DocumentSegment a, DocumentSegment b) { return a.StartPage.CompareTo(b.StartPage); });
            return kept;
        }

        private static string Join(List<string> xs)
        {
            var sb = new StringBuilder();
            for (int i = 0; i < xs.Count; i++) { if (i > 0) sb.Append(','); sb.Append(xs[i]); }
            return sb.ToString();
        }

        private static double Clamp(double x, double lo, double hi) { return x < lo ? lo : (x > hi ? hi : x); }
    }

    // =====================================================================
    //  PROFILES  (built-in mortgage set + optional JSON override)
    //  Format per type:  strong | firstpage | anypage | negative | maxpages
    //  ('~' separates phrases inside a field)
    // =====================================================================
    public static class Profiles
    {
        public static List<TypeProfile> Resolve(string profilesJson, out EngineConfig cfg)
        {
            cfg = new EngineConfig();
            if (!string.IsNullOrEmpty(profilesJson) && profilesJson.Trim().Length > 1)
            {
                try
                {
                    List<TypeProfile> fromJson = MiniJson.ParseProfiles(profilesJson, cfg);
                    if (fromJson != null && fromJson.Count > 0) return fromJson;
                }
                catch { /* fall back to built-in on any parse error */ }
            }
            throw new InvalidOperationException(
                "ProfilesJson input is required and must contain a valid \"types\" object. " +
                "Paste the contents of ProfilesJson.sample.json into the ProfilesJson variable.");
        }
    }

    // =====================================================================
    //  MINIMAL JSON PARSER  (dependency-free; supports the profile schema only:
    //  objects, arrays of strings, strings, numbers, booleans). Robust enough
    //  for hand-edited profile JSON; falls back to built-in on any error.
    // =====================================================================
    internal static class MiniJson
    {
        public static List<TypeProfile> ParseProfiles(string json, EngineConfig cfg)
        {
            int i = 0;
            object root = ParseValue(json, ref i);
            var map = root as Dictionary<string, object>;
            if (map == null) return null;

            // optional config overrides
            object cfgObj;
            if (map.TryGetValue("config", out cfgObj) && cfgObj is Dictionary<string, object>)
                ApplyConfig((Dictionary<string, object>)cfgObj, cfg);

            object typesObj;
            if (!map.TryGetValue("types", out typesObj) || !(typesObj is Dictionary<string, object>))
                return null;
            var types = (Dictionary<string, object>)typesObj;

            var result = new List<TypeProfile>();
            foreach (var kv in types)
            {
                var pd = kv.Value as Dictionary<string, object>;
                if (pd == null) continue;
                var tp = new TypeProfile { Name = kv.Key };
                tp.StrongStart = StrList(pd, "strong_start");
                tp.FirstPage = StrList(pd, "first_page");
                tp.AnyPage = StrList(pd, "any_page");
                tp.Negative = StrList(pd, "negative");
                tp.MaxPages = (int)NumOr(pd, "max_pages", 0);
                result.Add(tp);
            }
            return result;
        }

        private static void ApplyConfig(Dictionary<string, object> c, EngineConfig cfg)
        {
            cfg.MinTypeScore = NumOr(c, "min_type_score", cfg.MinTypeScore);
            cfg.StartTypeMin = NumOr(c, "start_type_min", cfg.StartTypeMin);
            cfg.StartThreshold = NumOr(c, "start_threshold", cfg.StartThreshold);
            cfg.StartLow = NumOr(c, "start_low", cfg.StartLow);
            cfg.SimLow = NumOr(c, "sim_low", cfg.SimLow);
            cfg.WStrongHeader = NumOr(c, "w_strong_header", cfg.WStrongHeader);
            cfg.WStrongStart = NumOr(c, "w_strong_start", cfg.WStrongStart);
            cfg.WTypeChange = NumOr(c, "w_type_change", cfg.WTypeChange);
            cfg.AmbigMargin = NumOr(c, "ambig_margin", cfg.AmbigMargin);
            object bk; if (c.TryGetValue("break_known_on_lowsim", out bk) && bk is bool) cfg.BreakKnownOnLowSim = (bool)bk;
            object um; if (c.TryGetValue("unknown_mode", out um) && um is string) cfg.UnknownMode = (string)um;
        }

        private static List<string> StrList(Dictionary<string, object> d, string key)
        {
            var o = new List<string>();
            object v;
            if (d.TryGetValue(key, out v) && v is List<object>)
                foreach (var item in (List<object>)v)
                    if (item is string) o.Add((string)item);
            return o;
        }

        private static double NumOr(Dictionary<string, object> d, string key, double dflt)
        {
            object v;
            if (d.TryGetValue(key, out v) && v is double) return (double)v;
            return dflt;
        }

        // ---- recursive-descent parser ----
        private static object ParseValue(string s, ref int i)
        {
            SkipWs(s, ref i);
            char c = s[i];
            if (c == '{') return ParseObject(s, ref i);
            if (c == '[') return ParseArray(s, ref i);
            if (c == '"') return ParseString(s, ref i);
            if (c == 't' || c == 'f') return ParseBool(s, ref i);
            if (c == 'n') { i += 4; return null; }  // null
            return ParseNumber(s, ref i);
        }

        private static Dictionary<string, object> ParseObject(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            i++; // {
            SkipWs(s, ref i);
            if (s[i] == '}') { i++; return d; }
            while (true)
            {
                SkipWs(s, ref i);
                string key = ParseString(s, ref i);
                SkipWs(s, ref i);
                i++; // :
                object val = ParseValue(s, ref i);
                d[key] = val;
                SkipWs(s, ref i);
                char c = s[i++];
                if (c == '}') break;
                // c == ',' -> continue
            }
            return d;
        }

        private static List<object> ParseArray(string s, ref int i)
        {
            var a = new List<object>();
            i++; // [
            SkipWs(s, ref i);
            if (s[i] == ']') { i++; return a; }
            while (true)
            {
                object val = ParseValue(s, ref i);
                a.Add(val);
                SkipWs(s, ref i);
                char c = s[i++];
                if (c == ']') break;
                // ',' -> continue
            }
            return a;
        }

        private static string ParseString(string s, ref int i)
        {
            var sb = new StringBuilder();
            i++; // opening quote
            while (s[i] != '"')
            {
                char c = s[i++];
                if (c == '\\')
                {
                    char e = s[i++];
                    switch (e)
                    {
                        case 'n': sb.Append('\n'); break;
                        case 't': sb.Append('\t'); break;
                        case 'r': sb.Append('\r'); break;
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'u':
                            string hex = s.Substring(i, 4); i += 4;
                            sb.Append((char)Convert.ToInt32(hex, 16));
                            break;
                        default: sb.Append(e); break;
                    }
                }
                else sb.Append(c);
            }
            i++; // closing quote
            return sb.ToString();
        }

        private static bool ParseBool(string s, ref int i)
        {
            if (s[i] == 't') { i += 4; return true; }
            i += 5; return false;
        }

        private static double ParseNumber(string s, ref int i)
        {
            int start = i;
            while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '-' || s[i] == '+'
                   || s[i] == '.' || s[i] == 'e' || s[i] == 'E')) i++;
            return double.Parse(s.Substring(start, i - start), CultureInfo.InvariantCulture);
        }

        private static void SkipWs(string s, ref int i)
        {
            while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) i++;
        }
    }
}
