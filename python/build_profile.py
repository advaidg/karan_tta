"""Authoritative generator for the 9-type mortgage ProfilesJson, tuned to 100%
on the real labelled sample. Writes ../ProfilesJson.sample.json.

Run from repo root:  python3 -B python/build_profile.py
Then verify:         python3 -B python/eval_real.py ProfilesJson.sample.json
"""
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG = OrderedDict([
    ("min_type_score", 44),
    ("start_type_min", 76),
    ("start_threshold", 44),
    ("start_low", 25),
    ("sim_low", 0.24),
    ("w_strong_header", 46),
    ("w_strong_start", 48),
    ("w_type_change", 75),
    ("ambig_margin", 22),
    ("break_known_on_lowsim", False),
    ("unknown_mode", "ContiguousRuns"),
])


def t(strong, first_page, any_page, negative, max_pages=0):
    return OrderedDict([
        ("strong_start", strong),
        ("first_page", first_page),
        ("any_page", any_page),
        ("negative", negative),
        ("max_pages", max_pages),
    ])


TYPES = OrderedDict()

TYPES["ClosingDisclosure"] = t(
    ["closing disclosure"],
    ["this form is a statement of final loan terms",
     "closing information transaction information loan information"],
    ["closing disclosure", "loan information", "transaction information", "disbursement date",
     "settlement agent", "loan id", "sale price", "loan terms", "projected payments",
     "calculating cash to close", "closing cost details", "loan calculations",
     "additional information about this loan", "total of payments", "origination charges",
     "summaries of transactions", "costs at closing"],
    ["u s bank closing instructions", "mandatory closing instructions", "deed of trust",
     "wiring instructions", "settlement statement", "tax proration", "escrow closing instructions"])

TYPES["ClosingInstructions"] = t(
    ["u s bank closing instructions", "mandatory closing instructions", "bank closing instructions",
     "escrow closing instructions"],
    ["closing disclosure must be delivered by", "rate lock expiration date",
     "these closing instructions", "transaction wire amount", "escrow closing instructions"],
    # any_page kept to CI-instruction-body terms only. The escrow-CI continuation
    # pages (buyer/seller roles, HOA approval, legal-description) are matched by
    # SPECIFIC section phrases — NOT by title-company letterhead words, which would
    # also match unrelated title letters (post-closing, tax-proration) on the same
    # letterhead and steal them into this document.
    ["closing instructions", "title insurance policy requirements", "document enclosures",
     "closing package", "contact closer", "closer phone number", "title contact",
     "disbursement date", "wire amount", "secondary contact", "title file",
     # escrow Closing Instructions continuation-page anchors (this multi-page doc has
     # numbered sections with different content per page and no repeated title):
     "buyer and seller roles", "roles and acknowledgments", "approval of sale",
     "agreement to furnish", "acknowledgment of review", "limited indemnity",
     "hoa dues", "legal description of subject property", "furnish and sign required documents"],
    # negatives: OTHER title-company letters that share the SAME letterhead but are
    # separate documents (ground truth = Unknown). Their own DISTINCT titles push
    # them down so they aren't pulled into Closing Instructions. NB: do NOT list
    # "deed of trust" here — escrow closing instructions mention it in passing, and
    # the penalty would wrongly drop a real CI page below the Unknown floor.
    ["this form is a statement of final loan terms",
     "post closing instructions", "tax proration", "wiring instructions",
     "american land title", "settlement statement"])

TYPES["DeedOfTrust"] = t(
    ["deed of trust", "security instrument"],
    ["this deed of trust", "when recorded return to", "after recording return to",
     "definitions words used in multiple sections", "return to u s bank"],
    ["deed of trust", "borrower", "lender", "trustee", "property", "covenants",
     "uniform covenants", "security instrument", "mers", "recording", "grantor", "grantee"],
    # rider-specific negatives: a PUD/Condo/1-4-Family RIDER shares all Deed-of-Trust
    # legal vocabulary but is a SEPARATE document -> push its DoT score below 0 so the
    # "contradicts open document" boundary rule fires and it becomes its own (Unknown) doc.
    ["closing disclosure", "closing instructions", "settlement statement",
     "request for taxpayer", "uniform residential loan application", "first payment letter",
     "planned unit development rider", "this planned unit development rider",
     "condominium rider", "1-4 family rider", "is incorporated into and amends",
     "supplements the mortgage", "security deed", "master or blanket policy",
     "in lieu of restoration", "property insurance proceeds", "rider is made this",
     "post closing instructions", "tax proration", "escrow closing instructions"])

TYPES["FirstPaymentLetter"] = t(
    ["first payment letter"],
    ["first payment letter"],
    ["first payment", "payment due", "monthly payment", "loan number", "principal and interest"],
    ["closing disclosure", "deed of trust", "escrow account disclosure"],
    max_pages=2)

TYPES["IRSW9"] = t(
    ["request for taxpayer", "form w 9", "form in 9", "form w9"],
    ["request for taxpayer identification number", "request for taxpayer"],
    ["taxpayer identification", "backup withholding", "internal revenue service",
     "give form to the", "exempt payee", "irs gov", "certification"],
    ["deed of trust", "closing disclosure", "uniform residential loan application"])

TYPES["EscrowAccountDisclosure"] = t(
    ["initial escrow account disclosure statement", "escrow account disclosure statement",
     "escrow account disclosure"],
    ["initial escrow account disclosure statement"],
    ["escrow", "cushion", "aggregate adjustment", "disbursement", "escrowed property costs",
     "monthly escrow payment", "servicer"],
    ["closing disclosure", "deed of trust", "escrow closing instructions", "wiring instructions"],
    max_pages=3)

TYPES["UniformResidentialLoanApplication"] = t(
    ["uniform residential loan application"],
    ["uniform residential loan application verify and complete", "to be completed by the lender"],
    ["uniform residential loan application", "universal loan identifier", "agency case",
     "demographic information", "section 1", "section 8", "borrower information",
     "employment", "assets and liabilities", "loan and property information"],
    ["supplemental consumer information form", "deed of trust", "closing disclosure",
     "request for taxpayer"])

TYPES["SupplementalConsumerInfo"] = t(
    ["supplemental consumer information form"],
    ["the purpose of the supplemental consumer information form",
     "supplemental consumer information form"],
    ["supplemental consumer information", "homeownership education", "housing counseling",
     "language preference", "universal loan identifier"],
    ["uniform residential loan application verify", "deed of trust", "closing disclosure"],
    max_pages=1)

TYPES["DriversLicense"] = t(
    ["driver license", "drivers license", "driver s license", "drwerlicense"],
    [],
    ["driver license", "dln", "class d", "class c", "donor", "endorsements", "restrictions",
     "date of birth", "dob", "expiration", "sex", "hgt", "wgt", "eyes",
     "drwerlicense", "drwer license", "ldl", "operator license"],
    ["deed of trust", "closing disclosure", "uniform residential loan application",
     "request for taxpayer"],
    max_pages=1)


def main():
    out = OrderedDict([("config", CONFIG), ("generic_id_regex", []), ("types", TYPES)])
    path = os.path.join(ROOT, "ProfilesJson.sample.json")
    json.dump(out, open(path, "w"), indent=2)
    print("wrote %s with %d types" % (path, len(TYPES)))


if __name__ == "__main__":
    main()
