using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace SegmentationEngine
{
    /// <summary>
    /// Split TTA's single OCR variable into ordered per-page texts.
    /// 1:1 port of python/segmenter/page_splitter.py.
    ///
    /// TTA inserts page separators like [PAGE 1], [PAGE 2], ... A document's own
    /// body can ALSO contain "Page 1" or even a literal "[PAGE 1]" — so we only
    /// accept bracketed markers, alone on a line, that form an increasing sequence.
    /// Loose "Page 1 of 5" is never a separator (handled by the page-number layer).
    /// </summary>
    public static class PageSplitter
    {
        // Bracketed PAGE marker alone on a line. Adjust to your exact TTA format.
        public static readonly Regex DefaultMarker = new Regex(
            @"^[\s>*]*[\[\(<]\s*page\s+(\d{1,4})\s*[\]\)>]\s*$",
            RegexOptions.IgnoreCase | RegexOptions.Multiline | RegexOptions.Compiled);

        public static List<string> SplitPages(string ocrText)
        {
            return SplitPages(ocrText, DefaultMarker, true);
        }

        public static List<string> SplitPages(string ocrText, Regex marker, bool enforceSequence)
        {
            var pages = new List<string>();
            if (string.IsNullOrEmpty(ocrText)) return pages;

            var matches = new List<Match>();
            foreach (Match m in marker.Matches(ocrText)) matches.Add(m);
            if (matches.Count == 0)
            {
                if (ocrText.Trim().Length > 0) pages.Add(ocrText);
                return pages;
            }

            var accepted = FilterSequence(matches, enforceSequence);
            if (accepted.Count == 0) { pages.Add(ocrText); return pages; }

            string preamble = ocrText.Substring(0, accepted[0].Index).Trim();
            for (int idx = 0; idx < accepted.Count; idx++)
            {
                int bodyStart = accepted[idx].Index + accepted[idx].Length;
                int bodyEnd = (idx + 1 < accepted.Count) ? accepted[idx + 1].Index : ocrText.Length;
                string body = ocrText.Substring(bodyStart, bodyEnd - bodyStart).Trim('\n', '\r');
                if (idx == 0 && preamble.Length > 0) body = preamble + "\n" + body;
                pages.Add(body);
            }
            return pages;
        }

        private static List<Match> FilterSequence(List<Match> matches, bool enforce)
        {
            if (!enforce) return matches;
            var accepted = new List<Match>();
            int? last = null;
            foreach (var m in matches)
            {
                int num;
                if (!int.TryParse(m.Groups[1].Value, out num)) continue;
                if (last == null)
                {
                    if (num <= 2) { accepted.Add(m); last = num; }
                }
                else if (num > last.Value)
                {
                    accepted.Add(m); last = num;
                }
            }
            return accepted.Count > 0 ? accepted : matches;
        }

        public static string JoinPagesWithMarkers(List<string> pages)
        {
            var sb = new StringBuilder();
            for (int i = 0; i < pages.Count; i++)
            {
                if (i > 0) sb.Append('\n');
                sb.Append("[PAGE ").Append(i + 1).Append("]\n").Append(pages[i]);
            }
            return sb.ToString();
        }
    }
}
