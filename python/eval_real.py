"""Evaluate the segmenter against the REAL labelled sample (actual_Sample.txt +
expected.txt). Run from repo root: python3 -B python/eval_real.py [profiles.json]
"""
import json, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from segmenter.engine import Segmenter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Map engine type names -> the label words used in expected.txt
LABEL = {
    "ClosingDisclosure": "Closing Disclosure",
    "ClosingInstructions": "Closing Instruction",
    "DeedOfTrust": "Deed of Trust",
    "FirstPaymentLetter": "First Page Letter",
    "IRSW9": "IRS W-9",
    "EscrowAccountDisclosure": "Initial Escrow",
    "UniformResidentialLoanApplication": "Uniform Residential Loan Application",
    "SupplementalConsumerInfo": "Supplemental Consumer Information Form",
    "DriversLicense": "Driver License",
    "Unknown": "Unknown",
}


def parse_expected(path):
    """Return dict page(1-based) -> label."""
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"(\d+)\s*(?:-\s*(\d+))?\s*-?\s*(.+)", line)
        if not m:
            continue
        a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
        label = m.group(3).strip().lstrip("- ").strip()
        for p in range(a, b + 1):
            out[p] = label
    return out


def load_profiles(path):
    raw = json.load(open(path))
    return {"types": raw["types"], "generic_id_regex": raw.get("generic_id_regex", [])}, raw.get("config")


def main():
    prof_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "ProfilesJson.sample.json")
    profiles, cfg = load_profiles(prof_path)
    txt = open(os.path.join(ROOT, "actual_Sample.txt"), encoding="utf-8", errors="replace").read()
    expected = parse_expected(os.path.join(ROOT, "expected.txt"))

    seg = Segmenter(profiles=profiles, config=cfg)
    segs, dec, pages = seg.segment_ocr(txt)

    # predicted page -> label
    pred = {}
    for s in segs:
        for p in range(s.start_page, s.end_page + 1):
            pred[p + 1] = LABEL.get(s.doc_type, s.doc_type)

    n = len(pages)
    correct = sum(1 for p in range(1, n + 1) if pred.get(p) == expected.get(p))
    print(f"profiles: {os.path.basename(prof_path)}  | pages={n}  segments={len(segs)}")
    print(f"PAGE-LABEL ACCURACY: {correct}/{n} = {correct/n*100:.1f}%\n")

    # show every page mismatch
    print("MISMATCHES (page: expected | predicted):")
    for p in range(1, n + 1):
        e = expected.get(p, "?"); pr = pred.get(p, "?")
        if e != pr:
            print(f"  p{p:>3}: {e:42s} | {pr}")

    # segment-level expected vs predicted
    print("\nPREDICTED SEGMENTS:")
    for s in segs:
        rng = f"{s.start_page+1}-{s.end_page+1}" if s.page_count > 1 else f"{s.start_page+1}"
        print(f"  {rng:>9}  {LABEL.get(s.doc_type, s.doc_type)}")


if __name__ == "__main__":
    main()
