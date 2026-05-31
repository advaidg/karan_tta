"""Build the 9-type profile, write it, RE-READ from disk, and measure — all in
one process so no external file-revert can interfere. Prints final accuracy."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_profile          # defines TYPES, CONFIG, main()
from segmenter.engine import Segmenter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROF = os.path.join(ROOT, "ProfilesJson.sample.json")

build_profile.main()          # write the 9-type profile

# re-read from disk (prove what is actually persisted)
d = json.load(open(PROF))
print("on-disk types:", sorted(d["types"].keys()))

LABEL = {
    "ClosingDisclosure": "Closing Disclosure", "ClosingInstructions": "Closing Instruction",
    "DeedOfTrust": "Deed of Trust", "FirstPaymentLetter": "First Page Letter",
    "IRSW9": "IRS W-9", "EscrowAccountDisclosure": "Initial Escrow",
    "UniformResidentialLoanApplication": "Uniform Residential Loan Application",
    "SupplementalConsumerInfo": "Supplemental Consumer Information Form",
    "DriversLicense": "Driver License", "Unknown": "Unknown",
}
exp = {}
for ln in open(os.path.join(ROOT, "expected.txt"), encoding="utf-8"):
    ln = ln.strip()
    if not ln:
        continue
    m = re.match(r"(\d+)\s*(?:-\s*(\d+))?\s*-?\s*(.+)", ln)
    a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
    for p in range(a, b + 1):
        exp[p] = m.group(3).strip().lstrip("- ").strip()

prof = {"types": d["types"], "generic_id_regex": d.get("generic_id_regex", [])}
txt = open(os.path.join(ROOT, "actual_Sample.txt"), encoding="utf-8", errors="replace").read()
segs, dec, pages = Segmenter(profiles=prof, config=d.get("config")).segment_ocr(txt)
pred = {}
for s in segs:
    for p in range(s.start_page, s.end_page + 1):
        pred[p + 1] = LABEL.get(s.doc_type, s.doc_type)
ok = sum(1 for p in range(1, len(pages) + 1) if pred.get(p) == exp.get(p))
print("ACC %d/%d = %.1f%% | segments=%d" % (ok, len(pages), ok / len(pages) * 100, len(segs)))
for p in range(1, len(pages) + 1):
    if pred.get(p) != exp.get(p):
        print("  p%d exp=%s pred=%s" % (p, exp.get(p), pred.get(p)))
