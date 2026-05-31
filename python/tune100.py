"""One-shot deterministic tuner: apply candidate profile fixes, measure vs
expected.txt, print accuracy + remaining errors. Run from repo root:
    python3 -B python/tune100.py
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from segmenter.engine import Segmenter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROF = os.path.join(ROOT, "ProfilesJson.sample.json")

LABEL = {
    "ClosingDisclosure": "Closing Disclosure", "ClosingInstructions": "Closing Instruction",
    "DeedOfTrust": "Deed of Trust", "FirstPaymentLetter": "First Page Letter",
    "IRSW9": "IRS W-9", "EscrowAccountDisclosure": "Initial Escrow",
    "UniformResidentialLoanApplication": "Uniform Residential Loan Application",
    "SupplementalConsumerInfo": "Supplemental Consumer Information Form",
    "DriversLicense": "Driver License", "Unknown": "Unknown",
}


def parse_expected():
    out = {}
    for ln in open(os.path.join(ROOT, "expected.txt"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r"(\d+)\s*(?:-\s*(\d+))?\s*-?\s*(.+)", ln)
        a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
        for p in range(a, b + 1):
            out[p] = m.group(3).strip().lstrip("- ").strip()
    return out


def measure(d):
    prof = {"types": d["types"], "generic_id_regex": d.get("generic_id_regex", [])}
    txt = open(os.path.join(ROOT, "actual_Sample.txt"), encoding="utf-8", errors="replace").read()
    seg = Segmenter(profiles=prof, config=d.get("config"))
    segs, dec, pages = seg.segment_ocr(txt)
    pred = {}
    for s in segs:
        for p in range(s.start_page, s.end_page + 1):
            pred[p + 1] = LABEL.get(s.doc_type, s.doc_type)
    exp = parse_expected()
    ok = sum(1 for p in range(1, len(pages) + 1) if pred.get(p) == exp.get(p))
    errs = [(p, exp.get(p), pred.get(p)) for p in range(1, len(pages) + 1)
            if pred.get(p) != exp.get(p)]
    return ok, len(pages), errs, segs


def add(lst, *items):
    for it in items:
        if it not in lst:
            lst.append(it)


def main():
    d = json.load(open(PROF))
    T = d["types"]

    # FIX p52-53: a Planned Unit Development / Condominium / 1-4 Family RIDER shares
    # all Deed-of-Trust legal vocabulary but is a SEPARATE doc (ground truth=Unknown).
    # Add rider-specific negatives so DoT score drops below the Unknown floor.
    add(T["DeedOfTrust"]["negative"],
        "planned unit development rider", "this planned unit development rider",
        "condominium rider", "1-4 family rider", "is incorporated into and amends",
        "supplements the mortgage", "security deed", "master or blanket policy",
        "in lieu of restoration", "property insurance proceeds", "rider is made this")

    # FIX p28: escrow Closing Instructions tail page (legal-description / buyer-seller
    # roles continuation). Add its body anchors so it still reads as CI and stays
    # attached to the open CI document.
    add(T["ClosingInstructions"]["any_page"],
        "buyer and seller roles", "roles and acknowledgments", "approval of sale",
        "seller s disclosure", "agreement to furnish", "acknowledgment of review",
        "hoa dues", "legal description of subject property", "subject property",
        "old republic national title insurance company")

    ok, n, errs, segs = measure(d)
    print("ACC %d/%d = %.1f%%" % (ok, n, ok / n * 100))
    for p, e, pr in errs:
        print("  p%d exp=%s pred=%s" % (p, e, pr))

    if not errs:
        json.dump(d, open(PROF, "w"), indent=2)
        print("\n100% — wrote ProfilesJson.sample.json")
    else:
        print("\n(not 100% — NOT saved; inspect errors above)")


if __name__ == "__main__":
    main()
