using System.Collections.Generic;

namespace SegmentationEngine
{
    /// <summary>
    /// All tunable knobs. Values are the tuned set proven in the Python harness
    /// (see docs/RESULTS.md). Keep this in sync with python/segmenter/config.py.
    /// </summary>
    public sealed class EngineConfig
    {
        // header-zone extraction
        public double HeaderRatio = 0.34;
        public int HeaderMinLines = 3;

        // per-type keyword scoring
        public double WStrongHeader = 46.0;   // tuned P8: >= MinTypeScore so one title clears Unknown
        public double WStrongBody = 8.0;
        public double WAny = 12.0;
        public double WNegative = -30.0;
        public double MinTypeScore = 44.0;    // tuned P5
        public double StartTypeMin = 76.0;    // type-change needs new type score >= this (or page cue)
        public double TypeConfDenom = 70.0;
        public double AmbigMargin = 22.0;     // tuned P6

        // start-page signals
        public double WTypeChange = 75.0;     // tuned P6
        public double WIdChange = 55.0;
        public double WStrongStart = 48.0;    // tuned P5
        public double WPagenumOne = 45.0;
        public double WReset = 50.0;
        public double WPrevTerminal = 25.0;
        public double WLowSim = 25.0;

        // continuation evidence
        public double WContPagenum = 40.0;
        public double WContIdSame = 18.0;

        // similarity
        public double SimLow = 0.24;          // tuned P5

        // decision thresholds
        public double StartThreshold = 44.0;  // tuned P5
        public double StartLow = 25.0;

        // behaviour: "ContiguousRuns" (recommended) or "MergeAll"
        public string UnknownMode = "ContiguousRuns";

        public static EngineConfig Default()
        {
            return new EngineConfig();
        }
    }

    /// <summary>One document type's matching profile.</summary>
    public sealed class TypeProfile
    {
        public string Name;
        public List<string> StrongStart = new List<string>();   // distinctive page-1 titles
        public List<string> FirstPage = new List<string>();     // page-1-only signature phrases
        public List<string> AnyPage = new List<string>();
        public List<string> Negative = new List<string>();
        public List<string> IdRegex = new List<string>();       // raw regex strings
    }
}
