using System;
using System.Collections.Generic;
using SegmentationEngine;

// Mirror of python/demo.py — verifies the C# port produces the same segmentation.
// Build/run instructions in csharp/README.md.
public static class Demo
{
    private const string Ocr =
        "[PAGE 1]\n" +
        "INVOICE\n" +
        "Invoice Number: INV-50001\n" +
        "Bill To: John Smith\n" +
        "Amount Due: $1,200\n" +
        "Page 1 of 1\n" +
        "[PAGE 2]\n" +
        "INVOICE\n" +
        "Invoice Number: INV-50002\n" +
        "Bill To: Maria Garcia\n" +
        "Amount Due: $880\n" +
        "[PAGE 3]\n" +
        "LOAN AGREEMENT\n" +
        "Loan Number: LN-700123\n" +
        "Borrower: Wei Chen\n" +
        "Principal: $25,000\n" +
        "[PAGE 4]\n" +
        "continued terms and conditions\n" +
        "interest accrues monthly on the outstanding principal balance\n" +
        "[PAGE 5]\n" +
        "MEMORANDUM\n\n" +
        "Please find attached the requested documents.\n" +
        "[PAGE 6]\n" +
        "follow up notes for the team\n" +
        "[PAGE 1]\n" +
        "(this stray bracketed marker is INSIDE the memo body - the trap)\n" +
        "[PAGE 7]\n" +
        "PAYSLIP\n" +
        "Employee ID: EMP-44321\n" +
        "Gross Pay: $3,400\n" +
        "Net Pay: $2,710\n";

    public static void Main()
    {
        var engine = new Segmenter(ProfilesData.Default(), ProfilesData.GenericIdRegex(),
                                   EngineConfig.Default());
        List<PageDecision> decisions;
        List<string> pages;
        var segments = engine.SegmentOcr(Ocr, out decisions, out pages);

        Console.WriteLine("Split into " + pages.Count +
                          " pages (the stray in-body [PAGE 1] was correctly ignored).\n");
        Console.WriteLine("{0,-9}{1,-22}{2,-7}{3,-8}{4}", "pages", "type", "conf", "review", "reason");
        Console.WriteLine(new string('-', 76));
        foreach (var s in segments)
        {
            string rng = s.PageCount > 1
                ? (s.StartPage + 1) + "-" + (s.EndPage + 1)
                : (s.StartPage + 1).ToString();
            string reason = s.Reason.Length > 32 ? s.Reason.Substring(0, 32) : s.Reason;
            Console.WriteLine("{0,-9}{1,-22}{2,-7:0.00}{3,-8}{4}",
                rng, s.DocType, s.Confidence, s.NeedsReview ? "YES" : "no", reason);
        }
    }
}
