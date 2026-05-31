using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace SegmentationEngine
{
    /// <summary>
    /// The segmentation engine: per-page 5-layer scoring + boundary assembly.
    /// 1:1 port of python/segmenter/engine.py. Pure logic, no TTA/SDK references,
    /// so it is safe to run inside the Azure sandbox as a referenced assembly.
    /// </summary>
    public sealed class Segmenter
    {
        private readonly EngineConfig _cfg;
        private readonly Dictionary<string, CompiledProfile> _types =
            new Dictionary<string, CompiledProfile>();
        private readonly List<Regex> _genericIdRegex;

        private sealed class CompiledProfile
        {
            public List<string> StrongStart;   // normalized
            public List<string> FirstPage;     // normalized
            public List<string> AnyPage;
            public List<string> Negative;
            public List<Regex> IdRegex;
        }

        public Segmenter(IEnumerable<TypeProfile> profiles, List<string> genericIdRegex, EngineConfig cfg)
        {
            _cfg = cfg ?? EngineConfig.Default();
            foreach (var p in profiles)
            {
                var cp = new CompiledProfile
                {
                    StrongStart = NormalizeAll(p.StrongStart),
                    FirstPage = NormalizeAll(p.FirstPage),
                    AnyPage = NormalizeAll(p.AnyPage),
                    Negative = NormalizeAll(p.Negative),
                    IdRegex = OcrUtils.CompileList(p.IdRegex),
                };
                _types[p.Name] = cp;
            }
            _genericIdRegex = OcrUtils.CompileList(genericIdRegex ?? new List<string>());
        }

        private static List<string> NormalizeAll(List<string> phrases)
        {
            var outList = new List<string>();
            foreach (var k in phrases) outList.Add(OcrUtils.Normalize(k));
            return outList;
        }

        // ----------------------------------------------------------- scoring
        public PageDecision ScorePage(string rawText)
        {
            var cfg = _cfg;
            string normFull = OcrUtils.Normalize(rawText);
            string header = OcrUtils.HeaderText(rawText, cfg.HeaderRatio, cfg.HeaderMinLines);
            string normHeader = OcrUtils.Normalize(header);

            var typeScores = new Dictionary<string, double>();
            var strongInHeader = new Dictionary<string, bool>();
            foreach (var kv in _types)
            {
                double s = 0.0;
                bool hitStrongHeader = false;
                foreach (var kw in kv.Value.StrongStart)
                {
                    if (OcrUtils.ContainsPhrase(normHeader, kw)) { s += cfg.WStrongHeader; hitStrongHeader = true; }
                    else if (OcrUtils.ContainsPhrase(normFull, kw)) { s += cfg.WStrongBody; }
                }
                foreach (var kw in kv.Value.AnyPage)
                    if (OcrUtils.ContainsPhrase(normFull, kw)) s += cfg.WAny;
                foreach (var kw in kv.Value.Negative)
                    if (OcrUtils.ContainsPhrase(normFull, kw)) s += cfg.WNegative;
                typeScores[kv.Key] = s;
                strongInHeader[kv.Key] = hitStrongHeader;
            }

            string bestType; double bestScore, secondScore;
            Top2(typeScores, out bestType, out bestScore, out secondScore);
            bool isUnknown = bestScore < cfg.MinTypeScore;
            string effectiveType = isUnknown ? "Unknown" : bestType;
            double typeConf = Clamp(bestScore / cfg.TypeConfDenom, 0.0, 1.0);

            int? cur, tot;
            OcrUtils.ParsePageNumber(rawText, out cur, out tot);
            List<Regex> idRegexes = (bestType != null && _types.ContainsKey(bestType))
                ? _types[bestType].IdRegex : new List<Regex>();
            var ids = OcrUtils.ExtractIds(rawText, idRegexes, _genericIdRegex);

            // page-1 signature: a "first page only" phrase of the best type present
            // here. A reappearance mid-document => a new instance (key A,A signal
            // for repeated-title multi-page docs with no page numbers).
            bool firstPageSig = false;
            if (bestType != null && !isUnknown)
            {
                foreach (var kw in _types[bestType].FirstPage)
                    if (OcrUtils.ContainsPhrase(normFull, kw)) { firstPageSig = true; break; }
            }

            var dec = new PageDecision
            {
                PageIndex = -1,
                BestDocType = bestType ?? "Unknown",
                DocTypeConfidence = typeConf,
                EffectiveType = effectiveType,
                IsStartPage = false,
                StartScore = 0.0,
                IsUnknown = isUnknown,
                NeedsReview = false,
                ExtractedIds = ids,
                PageNumber = cur,
                TotalPages = tot,
                TypeScores = typeScores,
                StrongInHeader = (bestType != null && strongInHeader.ContainsKey(bestType)) && strongInHeader[bestType],
                BestMinusSecond = bestScore - secondScore,
                NormTokens = OcrUtils.Tokenize(normFull),
                FirstPageSig = firstPageSig,
            };
            return dec;
        }

        // ----------------------------------------------- start-page evaluation
        private void EvaluateStart(PageDecision dec, PageDecision prev, string segType,
                                   List<string> segIds, out double score, out List<string> sig)
        {
            var cfg = _cfg;
            score = 0.0;
            sig = new List<string>();

            bool typeChanged = segType != null && dec.EffectiveType != segType;
            bool sameType = segType != null && dec.EffectiveType == segType;
            double sim = 1.0;
            if (prev != null) sim = OcrUtils.Jaccard(prev.NormTokens, dec.NormTokens);
            bool lowSim = prev != null && sim < cfg.SimLow;

            bool strong = dec.StrongInHeader;
            bool prevStrong = prev != null && prev.StrongInHeader;
            string prevType = prev != null ? prev.EffectiveType : null;

            bool pageOne = dec.PageNumber.HasValue && dec.PageNumber.Value == 1;
            bool reset = dec.PageNumber.HasValue && dec.PageNumber.Value > 1 && prev != null
                         && prev.PageNumber.HasValue && dec.PageNumber.Value < prev.PageNumber.Value;
            bool prevTerminal = prev != null && prev.PageNumber.HasValue && prev.TotalPages.HasValue
                                && prev.PageNumber.Value == prev.TotalPages.Value;
            bool idChange = sameType && !dec.IsUnknown && segIds.Count > 0 && dec.ExtractedIds.Count > 0
                            && !Intersects(dec.ExtractedIds, segIds);

            // page-1 signature appearing here but NOT on the previous page => new instance
            bool fpSig = dec.FirstPageSig;
            bool prevFpSig = prev != null && prev.FirstPageSig;
            bool firstPageSignature = fpSig && !prevFpSig;

            // A title is a NEW-document signal when it is newly present / a different
            // type than the open segment, OR when the SAME repeated title reappears
            // with a hard page cue (reset / prev terminal / page 1 / page-1 signature).
            bool titleRepeatsOpen = strong && prevStrong && prevType == dec.EffectiveType;
            bool strongNew = strong && (!titleRepeatsOpen || reset || prevTerminal || pageOne || firstPageSignature);

            bool typeChangeEvidenced = typeChanged && (strongNew || pageOne || reset || lowSim);
            bool knownToUnknown = segType != null && segType != "Unknown" && dec.IsUnknown && lowSim;
            bool sameTypeNewInstance = sameType && !dec.IsUnknown && firstPageSignature;
            bool hasEvidence = strongNew || pageOne || reset || prevTerminal || idChange
                               || typeChangeEvidenced || knownToUnknown || sameTypeNewInstance;

            if (typeChanged) { score += cfg.WTypeChange; sig.Add("type_change"); }
            if (idChange) { score += cfg.WIdChange; sig.Add("id_change"); }
            else if (sameType && segIds.Count > 0 && dec.ExtractedIds.Count > 0 && Intersects(dec.ExtractedIds, segIds))
            { score -= cfg.WContIdSame; sig.Add("id_same"); }
            if (strongNew) { score += cfg.WStrongStart; sig.Add("strong_start_header"); }
            else if (strong) { score -= cfg.WContIdSame; sig.Add("title_repeat"); }
            if (sameTypeNewInstance) { score += cfg.WStrongStart; sig.Add("first_page_signature"); }
            if (pageOne) { score += cfg.WPagenumOne; sig.Add("pagenum_one"); }
            else if (dec.PageNumber.HasValue && dec.PageNumber.Value > 1)
            {
                if (reset) { score += cfg.WReset; sig.Add("pagenum_reset"); }
                else { score -= cfg.WContPagenum; sig.Add("pagenum_continuation"); }
            }
            if (prevTerminal) { score += cfg.WPrevTerminal; sig.Add("prev_terminal"); }
            if (sameType && !dec.IsUnknown && lowSim) { score += cfg.WLowSim; sig.Add("low_similarity"); }

            // continuation gate: low-signal page with no real evidence sticks to open doc
            if (segType != null && !hasEvidence)
            {
                score = Math.Min(score, cfg.StartLow - 1.0);
                sig.Add("continuation_gate");
            }
        }

        // ------------------------------------------------------------ assemble
        public List<DocumentSegment> Segment(List<string> pagesText, out List<PageDecision> decisions)
        {
            var cfg = _cfg;
            decisions = new List<PageDecision>();
            var segments = new List<DocumentSegment>();

            DocumentSegment curSeg = null;
            var curIds = new List<string>();
            PageDecision prev = null;

            for (int i = 0; i < pagesText.Count; i++)
            {
                var dec = ScorePage(pagesText[i]);
                dec.PageIndex = i;

                string segType = curSeg != null ? curSeg.DocType : null;
                double startScore; List<string> sig;
                EvaluateStart(dec, prev, segType, curIds, out startScore, out sig);
                dec.StartScore = startScore;
                dec.Signals = sig;

                bool forced = (i == 0);
                bool isStart = forced || (startScore >= cfg.StartThreshold);
                bool gray = !isStart && startScore >= cfg.StartLow;
                bool ambiguous = dec.BestMinusSecond < cfg.AmbigMargin && !dec.IsUnknown;
                dec.IsStartPage = isStart;
                dec.NeedsReview = gray || ambiguous || dec.IsUnknown;
                if (forced) dec.Signals.Insert(0, "batch_first_page");

                if (isStart || curSeg == null)
                {
                    if (curSeg != null) segments.Add(curSeg);
                    curSeg = new DocumentSegment
                    {
                        StartPage = i, EndPage = i, DocType = dec.EffectiveType,
                        Confidence = dec.DocTypeConfidence, NeedsReview = dec.NeedsReview,
                        Reason = string.Join(",", dec.Signals), Ids = new List<string>(dec.ExtractedIds),
                    };
                    curIds = new List<string>(dec.ExtractedIds);
                }
                else
                {
                    curSeg.EndPage = i;
                    foreach (var id in dec.ExtractedIds)
                        if (!curIds.Contains(id)) curIds.Add(id);
                    curSeg.Ids = new List<string>(curIds);
                    curSeg.NeedsReview = curSeg.NeedsReview || dec.NeedsReview;
                    curSeg.Confidence = Math.Min(curSeg.Confidence, dec.DocTypeConfidence);
                    // continuation page with START-LIKE cues => likely missed boundary
                    if (dec.StrongInHeader || dec.FirstPageSig)
                    {
                        curSeg.NeedsReview = true;
                        if (curSeg.Reason.IndexOf("possible_missed_boundary", StringComparison.Ordinal) < 0)
                            curSeg.Reason += ",possible_missed_boundary";
                    }
                }

                decisions.Add(dec);
                prev = dec;
            }

            if (curSeg != null) segments.Add(curSeg);

            if (cfg.UnknownMode == "MergeAll")
                segments = MergeAllUnknown(segments);

            return segments;
        }

        /// <summary>Entry point for TTA: one OCR string with [PAGE n] separators.</summary>
        public List<DocumentSegment> SegmentOcr(string ocrText, out List<PageDecision> decisions, out List<string> pages)
        {
            pages = PageSplitter.SplitPages(ocrText);
            return Segment(pages, out decisions);
        }

        private static List<DocumentSegment> MergeAllUnknown(List<DocumentSegment> segments)
        {
            var unknownPages = new List<int>();
            var kept = new List<DocumentSegment>();
            foreach (var s in segments)
            {
                if (s.DocType == "Unknown")
                    for (int i = s.StartPage; i <= s.EndPage; i++) unknownPages.Add(i);
                else
                    kept.Add(s);
            }
            if (unknownPages.Count > 0)
            {
                int min = int.MaxValue, max = int.MinValue;
                foreach (var p in unknownPages) { if (p < min) min = p; if (p > max) max = p; }
                kept.Add(new DocumentSegment
                {
                    StartPage = min, EndPage = max, DocType = "Unknown",
                    Confidence = 0.0, NeedsReview = true, Reason = "merged_all_unknown(reordered)",
                });
            }
            kept.Sort((a, b) => a.StartPage.CompareTo(b.StartPage));
            return kept;
        }

        private static bool Intersects(List<string> a, List<string> b)
        {
            var set = new HashSet<string>(b);
            foreach (var x in a) if (set.Contains(x)) return true;
            return false;
        }

        private static void Top2(Dictionary<string, double> scores, out string bestName, out double best, out double second)
        {
            bestName = null; best = 0.0; second = 0.0;
            bool first = true;
            foreach (var kv in scores)
            {
                if (first || kv.Value > best)
                {
                    if (!first) second = best;
                    best = kv.Value; bestName = kv.Key; first = false;
                }
                else if (kv.Value > second) second = kv.Value;
            }
        }

        private static double Clamp(double x, double lo, double hi)
        {
            return x < lo ? lo : (x > hi ? hi : x);
        }
    }
}
