using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace SegmentationEngine
{
    /// <summary>
    /// Pure OCR text utilities. 1:1 port of python/segmenter/ocr_utils.py.
    /// Only System.Text.RegularExpressions — no external dependencies.
    /// </summary>
    public static class OcrUtils
    {
        private static readonly Regex NonAlnum = new Regex("[^a-z0-9]+", RegexOptions.Compiled);
        private static readonly Regex Ws = new Regex("\\s+", RegexOptions.Compiled);

        public static string Normalize(string text)
        {
            if (text == null) return " ";
            string low = text.ToLowerInvariant();
            low = NonAlnum.Replace(low, " ");
            low = Ws.Replace(low, " ").Trim();
            return " " + low + " ";
        }

        public static string HeaderText(string text, double ratio, int minLines)
        {
            if (string.IsNullOrEmpty(text)) return text ?? "";
            string[] lines = text.Replace("\r\n", "\n").Split('\n');
            if (lines.Length == 0) return text;
            int k = Math.Max(minLines, (int)Math.Ceiling(lines.Length * ratio));
            if (k > lines.Length) k = lines.Length;
            var sb = new StringBuilder();
            for (int i = 0; i < k; i++)
            {
                if (i > 0) sb.Append('\n');
                sb.Append(lines[i]);
            }
            return sb.ToString();
        }

        public static bool ContainsPhrase(string normalizedHaystack, string normalizedPhrase)
        {
            return normalizedHaystack.IndexOf(normalizedPhrase, StringComparison.Ordinal) >= 0;
        }

        public static List<string> Tokenize(string normalizedText)
        {
            var outList = new List<string>();
            foreach (var t in normalizedText.Split(' '))
                if (t.Length > 0) outList.Add(t);
            return outList;
        }

        public static double Jaccard(List<string> a, List<string> b)
        {
            if ((a == null || a.Count == 0) && (b == null || b.Count == 0)) return 1.0;
            if (a == null || b == null || a.Count == 0 || b.Count == 0) return 0.0;
            var sa = new HashSet<string>(a);
            var sb = new HashSet<string>(b);
            int inter = 0;
            foreach (var x in sa) if (sb.Contains(x)) inter++;
            int union = sa.Count + sb.Count - inter;
            return union > 0 ? (double)inter / union : 0.0;
        }

        // ---- page number parsing (fuzzy, OCR-noise tolerant) ----
        private static readonly Regex[] PnPatterns = new[]
        {
            new Regex(@"page\s+(\d{1,3})\s+of\s+(\d{1,3})", RegexOptions.Compiled),
            new Regex(@"pg\.?\s*(\d{1,3})\s*/\s*(\d{1,3})", RegexOptions.Compiled),
            new Regex(@"\bpage\s*[:#]?\s*(\d{1,3})\s*/\s*(\d{1,3})", RegexOptions.Compiled),
            new Regex(@"\b(\d{1,3})\s*/\s*(\d{1,3})\b", RegexOptions.Compiled),
            new Regex(@"\bpage\s*[:#]?\s*(\d{1,3})\b", RegexOptions.Compiled),
        };

        public static void ParsePageNumber(string text, out int? current, out int? total)
        {
            current = null; total = null;
            if (string.IsNullOrEmpty(text)) return;
            string low = text.ToLowerInvariant();
            var candidates = new List<string> { low };
            if (low.Contains("page") || low.Contains("/"))
                candidates.Add(DenoiseDigits(low));

            foreach (var cand in candidates)
            {
                foreach (var pat in PnPatterns)
                {
                    var m = pat.Match(cand);
                    if (m.Success)
                    {
                        int cur;
                        if (!int.TryParse(m.Groups[1].Value, out cur)) continue;
                        int? tot = null;
                        if (m.Groups.Count >= 3 && m.Groups[2].Success)
                        {
                            int t;
                            if (int.TryParse(m.Groups[2].Value, out t)) tot = t;
                        }
                        if (cur <= 0 || cur >= 500) continue;
                        if (tot.HasValue && (tot.Value <= 0 || tot.Value >= 500)) continue;
                        if (tot.HasValue && cur > tot.Value) continue;
                        current = cur; total = tot; return;
                    }
                }
            }
        }

        private static string DenoiseDigits(string s)
        {
            // only obvious confusions: l/i/I->1, o/O->0, s/S->5, B->8, |->1
            var sb = new StringBuilder(s.Length);
            foreach (char c in s)
            {
                switch (c)
                {
                    case 'l': case 'i': case 'I': case '|': sb.Append('1'); break;
                    case 'o': case 'O': sb.Append('0'); break;
                    case 's': case 'S': sb.Append('5'); break;
                    case 'B': sb.Append('8'); break;
                    default: sb.Append(c); break;
                }
            }
            return sb.ToString();
        }

        // ---- business identifier extraction ----
        public static List<string> ExtractIds(string text, List<Regex> typeIdRegexes, List<Regex> genericRegexes)
        {
            var found = new List<string>();
            string low = (text ?? "").ToLowerInvariant();
            foreach (var pat in typeIdRegexes)
                foreach (Match m in pat.Matches(low))
                    found.Add(CanonId(m.Value));
            if (found.Count == 0)
                foreach (var pat in genericRegexes)
                    foreach (Match m in pat.Matches(low))
                        found.Add(CanonId(m.Value));

            var seen = new HashSet<string>();
            var outList = new List<string>();
            foreach (var f in found)
                if (f.Length > 0 && seen.Add(f)) outList.Add(f);
            return outList;
        }

        private static string CanonId(string match)
        {
            var sb = new StringBuilder();
            foreach (char c in match.ToLowerInvariant())
                if (char.IsLetterOrDigit(c)) sb.Append(char.ToUpperInvariant(c));
            return sb.ToString();
        }

        public static List<Regex> CompileList(IEnumerable<string> patterns)
        {
            var outList = new List<Regex>();
            foreach (var p in patterns) outList.Add(new Regex(p, RegexOptions.Compiled));
            return outList;
        }
    }
}
