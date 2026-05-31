"""Realistic synthetic OCR generator for US Home Banking Mortgage packages.

Tuned to the user's confirmed reality:
  - SAME type repeats COMMONLY within one package (A,A is frequent).
  - Loan numbers are MOSTLY ABSENT (so ID-change cannot be the A,A splitter).
  - ~50% of documents have page numbers; ~10% of those pages drop them.
  - Multi-page docs (Note, Deed of Trust, Closing Disclosure, underwriting
    findings) often REPEAT their title/header on every page -> the engine must
    NOT over-split these into one-page documents.
  - OCR noise (l/1, O/0, S/5, dropped chars).
  - Foreign-keyword pressure: another type's title appears in a body page.
  - The page-marker trap: stray bracketed [PAGE n] inside a document body.

Authored INDEPENDENTLY of profiles.json wording where possible (titles overlap
because that's realistic, but bodies add lots of independent text). Deterministic
given a seed. Pure stdlib.
"""
from __future__ import annotations

import random
from typing import Dict, List, Tuple

# title : the page-1 (and, if repeat_title, every-page) header
# body  : independent body lines
# pages : (min,max) physical pages
# repeat_title : title reprinted on continuation pages (the over-split trap)
# multipage    : commonly spans several pages
TYPES: Dict[str, Dict] = {
    "ACHAuthorization": {"title": ["ACH AUTHORIZATION", "AUTOMATIC DRAFT PAYMENT PROGRAM"],
        "body": ["Routing Number 0{n8}", "Account Number {n8}", "I authorize automatic drafts",
                 "Draft date: the 1st of each month"], "pages": (1, 1)},
    "AddendumToNote": {"title": ["ADDENDUM TO NOTE", "NOTE ADDENDUM"],
        "body": ["This addendum modifies the promissory note", "Adjustable rate rider",
                 "Borrower initials ____"], "pages": (1, 2)},
    "ClosingDisclosure": {"title": ["CLOSING DISCLOSURE"],
        "first_page_body": ["Loan Terms", "Projected Payments", "This form is a statement of final loan terms"],
        "body": ["Costs at Closing", "Cash to Close",
                 "Monthly Principal and Interest", "Loan Amount $ {amt}", "Closing Costs $ {amt}",
                 "Summaries of Transactions", "Lender Credits"], "pages": (3, 5),
        "repeat_title": True, "multipage": True},
    "ClosingInstructions": {"title": ["CLOSING INSTRUCTIONS", "SPECIFIC CLOSING INSTRUCTIONS"],
        "body": ["To the settlement agent", "Disbursement of funds", "Return executed documents",
                 "Funding conditions"], "pages": (1, 3), "multipage": True},
    "DeedOfTrust": {"title": ["DEED OF TRUST", "DEED OF TRUST SECURITY INSTRUMENT"],
        "first_page_body": ["THIS DEED OF TRUST is made", "Recording requested by",
                            "DEFINITIONS Words used in multiple sections"],
        "body": ["Borrower owes Lender the principal sum",
                 "Trustee", "covenants and agrees", "the Property is located in the County of",
                 "Uniform Covenants", "Transfer of the Property"],
        "pages": (8, 18), "repeat_title": False, "multipage": True},
    "Note": {"title": ["NOTE", "PROMISSORY NOTE"],
        "first_page_body": ["BORROWER S PROMISE TO PAY", "in return for a loan I have received"],
        "body": ["principal sum of $ {amt}",
                 "interest will be charged", "I will pay principal and interest",
                 "Maturity Date", "BORROWER S RIGHT TO PREPAY"], "pages": (2, 5), "multipage": True},
    "CreditReport": {"title": ["CREDIT REPORT", "CREDIT REPORT SUMMARY"],
        "first_page_body": ["Merged Credit Report", "Repository Equifax Experian TransUnion"],
        "body": ["FICO Score {n3}", "Tradelines", "Inquiries",
                 "Account status current", "Revolving balance $ {amt}"], "pages": (2, 6),
        "repeat_title": True, "multipage": True},
    "CreditScoreDisclosure": {"title": ["CREDIT SCORE DISCLOSURE"],
        "body": ["Your credit score {n3}", "Score range 300 to 850", "Key factors",
                 "Scoring model used"], "pages": (1, 2)},
    "ConsumerPrivacyPledge": {"title": ["CONSUMER PRIVACY PLEDGE", "PRIVACY DISCLOSURE"],
        "body": ["We protect nonpublic personal information", "Your right to opt out",
                 "Information we collect"], "pages": (1, 2)},
    "CustomerIdentificationNotice": {"title": ["CUSTOMER IDENTIFICATION NOTICE",
                 "IDENTIFICATION VERIFICATION USA PATRIOT ACT INFORMATION"],
        "body": ["To help the government fight terrorism", "we collect your name address",
                 "USA PATRIOT ACT"], "pages": (1, 1)},
    "AppraisalUpdateCompletion": {"title": ["APPRAISAL UPDATE AND OR COMPLETION",
                 "ESTIMATE REPORT APPRAISAL VALUATION"],
        "body": ["Appraised value $ {amt}", "Completion certificate", "Subject property inspection",
                 "Comparable sales"], "pages": (1, 4), "multipage": True},
    "AutomatedValuationModelNotice": {"title": ["AUTOMATED VALUATION MODEL NOTICE",
                 "CUSTOMER NEW FREDDIE BPO APPRAISAL"],
        "body": ["AVM estimated value $ {amt}", "valuation model", "confidence score"], "pages": (1, 2)},
    "BuydownAgreement": {"title": ["BUYDOWN AGREEMENT", "BUYDOWN END DATE ADJUSTMENT WORKSHEET"],
        "body": ["Temporary buydown", "subsidy schedule", "Year 1 rate", "adjustment worksheet"],
        "pages": (1, 3), "multipage": True},
    "EscrowAccountDisclosure": {"title": ["ESCROW ACCOUNT DISCLOSURE STATEMENT"],
        "first_page_body": ["Escrow account projection for the coming year", "Initial escrow statement"],
        "body": ["Cushion", "Aggregate adjustment",
                 "Anticipated disbursements", "Monthly escrow payment $ {amt}"], "pages": (1, 3),
        "repeat_title": True, "multipage": True},
    "FirstPaymentLetter": {"title": ["FIRST PAYMENT LETTER"],
        "body": ["Your first payment is due", "Monthly payment $ {amt}", "Remit to",
                 "Payment due date"], "pages": (1, 1)},
    "DUUnderwritingFindings": {"title": ["DU UNDERWRITING FINDINGS"],
        "first_page_body": ["Recommendation Approve Eligible", "Casefile ID {n8} Submission"],
        "body": ["Desktop Underwriter",
                 "Verification messages", "Findings"], "pages": (3, 7), "repeat_title": True, "multipage": True},
    "GUSUnderwritingFindings": {"title": ["GUS UNDERWRITING FINDINGS REPORT"],
        "first_page_body": ["GUS recommendation Accept", "Submission summary"],
        "body": ["Guaranteed Underwriting System", "Findings report",
                 "Property eligibility"], "pages": (2, 6), "repeat_title": True, "multipage": True},
    "LoanProductAdvisorFeedback": {"title": ["LOAN PRODUCT ADVISOR FEEDBACK",
                 "LOAN PRODUCT ADVISOR FULL FEEDBACK CERTIFICATE"],
        "first_page_body": ["Risk class Accept", "Freddie Mac Loan Product Advisor Evaluation"],
        "body": ["Feedback certificate",
                 "Purchase eligibility"], "pages": (2, 5), "repeat_title": True, "multipage": True},
    "HUDFHALoanUnderwriting": {"title": ["HUD FHA LOAN UNDERWRITING AND", "LUTS 92900 LT"],
        "body": ["Mortgage Credit Analysis Worksheet", "FHA case number", "92900 LT",
                 "Qualifying ratios"], "pages": (2, 4), "multipage": True},
    "HUDAddendumURLA": {"title": ["HUD ADDENDUM TO UNIFORM RESIDENTIAL", "FHA VA ADDENDUM"],
        "body": ["Addendum to the Uniform Residential Loan Application", "Direct endorsement",
                 "Borrower certification"], "pages": (1, 3), "multipage": True},
    "VALoanAnalysis": {"title": ["VA LOAN ANALYSIS", "DEPARTMENT OF VETERANS AFFAIRS LOAN ANALYSIS"],
        "body": ["Residual income", "Veterans Affairs", "Entitlement", "Debt to income"], "pages": (1, 2)},
    "GuarantyCertificate": {"title": ["GUARANTY CERTIFICATE", "LOAN GUARANTY CERTIFICATE"],
        "body": ["VA Form 26 1889", "guaranty", "percentage of guaranty", "Veterans Affairs"],
        "pages": (1, 1)},
    "FamilyHousingLoanGuarantee": {"title": ["FAMILY HOUSING LOAN GUARANTEE",
                 "COMMITMENT SFH GUARANTEED LOAN"],
        "body": ["Rural Development", "Single Family Housing", "Guaranteed loan",
                 "Conditional commitment"], "pages": (1, 3), "multipage": True},
    "MortgageInsuranceCertificate": {"title": ["MORTGAGE INSURANCE CERTIFICATE",
                 "INSURANCE CERTIFICATE CERTIFICATE OF LIABILITY"],
        "body": ["Mortgage insurance", "Certificate number {n8}", "Coverage percentage",
                 "Premium"], "pages": (1, 2)},
    "MortgageInsuranceDisclosure": {"title": ["MORTGAGE INSURANCE DISCLOSURE",
                 "CONCERNING PRIVATE MORTGAGE INSURANCE"],
        "body": ["Private mortgage insurance", "PMI", "Cancellation rights", "Disclosure"], "pages": (1, 2)},
    "OccupancyAffidavit": {"title": ["OCCUPANCY AFFIDAVIT"],
        "body": ["I will occupy the property as my primary residence", "Affidavit", "within 60 days"],
        "pages": (1, 1)},
    "OccupancyAndUseCertificate": {"title": ["OCCUPANCY AND USE CERTIFICATE"],
        "body": ["Veterans Affairs occupancy", "use certificate", "I certify occupancy"], "pages": (1, 1)},
    "FinancialStatusAffidavit": {"title": ["FINANCIAL STATUS AFFIDAVIT"],
        "body": ["Statement of assets and liabilities", "Financial status", "Net worth $ {amt}"],
        "pages": (1, 2)},
    "PatriotActDisclosure": {"title": ["PATRIOT ACT DISCLOSURE", "USA PATRIOT ACT INFORMATION DISCLOSURE"],
        "body": ["USA PATRIOT ACT", "anti money laundering", "Disclosure"], "pages": (1, 1)},
    "PatriotActInformationForm": {"title": ["PATRIOT ACT INFORMATION FORM", "USA PATRIOT ACT INFORMATION FORM"],
        "body": ["USA PATRIOT ACT", "identity verification", "Information form"], "pages": (1, 1)},
    "FloodPolicyDeclarations": {"title": ["FLOOD POLICY DECLARATIONS",
                 "INSURANCE FLOOD POLICY DECLARATIONS FLOOD INSURANCE"],
        "body": ["Flood zone AE", "Declarations page", "Coverage $ {amt}", "Premium $ {amt}"],
        "pages": (1, 2)},
    "FloodInsuranceCancellation": {"title": ["FLOOD INSURANCE CANCELLATION LETTER"],
        "body": ["This letter confirms cancellation", "flood policy", "effective date"], "pages": (1, 1)},
    "FloodInsuranceIntentToCancel": {"title": ["FLOOD INSURANCE INTENT TO CANCEL EDI",
                 "ELECTRONIC IMAGE GENERATED FOR EDI DATA"],
        "body": ["Intent to cancel", "flood", "EDI data"], "pages": (1, 1)},
    "HomeownerPolicyChange": {"title": ["HOMEOWNER POLICY CHANGE"],
        "body": ["Hazard insurance", "policy change", "endorsement", "Coverage $ {amt}"], "pages": (1, 2)},
    "NoticeConcerningPrivateMortgage": {"title": ["NOTICE CONCERNING PRIVATE MORTGAGE"],
        "body": ["Private mortgage insurance", "cancellation rights", "Notice"], "pages": (1, 1)},
    "NoticeToSettlementAgents": {"title": ["NOTICE TO SETTLEMENT AGENTS"],
        "body": ["To all settlement agents", "closing requirements", "Notice"], "pages": (1, 1)},
    "DriversLicense": {"title": ["DRIVERS LICENSE", "PERSONAL IDENTIFICATION"],
        "body": ["DOB 0{m} {d} 19{n2}", "EXP 0{m} {d} 20{y}", "CLASS C", "DL NO {n8}"], "pages": (1, 1)},
    "AddressConfidentialityProgram": {"title": ["ADDRESS CONFIDENTIALITY PROGRAM"],
        "body": ["Substitute address", "Program participant", "Confidentiality"], "pages": (1, 1)},
    "AppraisalAcknowledgment": {"title": ["APPRAISAL ACKNOWLEDGMENT"],
        "body": ["I acknowledge receipt of the appraisal", "Valuation", "Acknowledgment"], "pages": (1, 1)},
    "ConsumerPrivacyPledgeAlt": {"title": ["INFORMATION PRIVACY POLICY NOTICE"],
        "body": ["Privacy policy", "what does the company do", "nonpublic information"], "pages": (1, 2)},
    "SupplementalConsumerInfo": {"title": ["SUPPLEMENTAL CONSUMER INFORMATION FORM"],
        "body": ["Demographic information", "Supplemental consumer information", "ethnicity race sex"],
        "pages": (1, 1)},
    "HoldHarmlessAgreement": {"title": ["HOLD HARMLESS AGREEMENT"],
        "body": ["The borrower agrees to hold harmless", "indemnify", "release"], "pages": (1, 1)},
    "PaymentDeferralRepaymentPlan": {"title": ["PAYMENT DEFERRAL AND REPAYMENT PLAN",
                 "PAYMENT DEFERRAL AND REPAYMENT PLAN AGREEMENT"],
        "body": ["Deferral of past due amounts", "Repayment plan", "Modified payment $ {amt}"],
        "pages": (1, 2)},
}

# Types that legitimately repeat their title on continuation pages.
REPEAT_TITLE = {k for k, v in TYPES.items() if v.get("repeat_title")}

UNKNOWN_TITLES = ["MISCELLANEOUS CORRESPONDENCE", "FAX COVER SHEET", "INTERNAL ROUTING SLIP",
                  "TO WHOM IT MAY CONCERN", "BLANK SEPARATOR PAGE", "HANDWRITTEN NOTES",
                  "EMAIL PRINTOUT", "DELIVERY RECEIPT", "SCRATCH NOTES"]
UNKNOWN_BODY = ["Please find the attached items.", "Per our discussion.", "See file for details.",
                "This page left intentionally informal.", "Regards, processing team.",
                "Follow up required.", "Reference prior correspondence."]

NAMES = ["JOHN SMITH", "MARIA GARCIA", "WEI CHEN", "AISHA KHAN", "ROBERT BROWN",
         "PRIYA PATEL", "LIAM OBRIEN", "SOFIA ROSSI"]

_OCR_NOISE = {"l": "1", "1": "l", "O": "0", "0": "O", "S": "5", "5": "S"}


def _fmt(t: str, rnd: random.Random, name: str) -> str:
    return t.format(
        name=name, amt=f"{rnd.randint(500, 999999):,}",
        m=rnd.randint(1, 9), d=rnd.randint(10, 28), y=rnd.randint(10, 24),
        n2=rnd.randint(10, 99), n3=rnd.randint(500, 850),
        n8=rnd.randint(10000000, 99999999))


def _noise(text: str, rnd: random.Random, rate: float) -> str:
    if rate <= 0:
        return text
    out = []
    for ch in text:
        if ch in _OCR_NOISE and rnd.random() < rate:
            out.append(_OCR_NOISE[ch])
        elif ch.isalpha() and rnd.random() < rate * 0.12:
            continue
        else:
            out.append(ch)
    return "".join(out)


def _make_document(type_name: str, rnd: random.Random,
                   foreign_kw: str = None) -> Tuple[List[str], List[dict]]:
    spec = TYPES[type_name]
    name = rnd.choice(NAMES)
    n_pages = rnd.randint(spec["pages"][0], spec["pages"][1])
    has_pn = rnd.random() < 0.5
    noisy = rnd.random() < 0.5
    rate = rnd.uniform(0.02, 0.07) if noisy else 0.0
    repeat_title = spec.get("repeat_title", False)
    title = rnd.choice(spec["title"])

    pages, truth = [], []
    for pi in range(n_pages):
        lines = []
        if pi == 0 or repeat_title:
            lines.append(title)
            lines.append("")
        # page-1-only signature content (realistic: a doc's first page differs)
        if pi == 0:
            for tmpl in spec.get("first_page_body", []):
                lines.append(_fmt(tmpl, rnd, name))
        pool = list(spec["body"])
        rnd.shuffle(pool)
        take = pool if pi == 0 else pool[: max(2, len(pool) // 2)]
        for tmpl in take:
            lines.append(_fmt(tmpl, rnd, name))
        if foreign_kw and pi > 0 and rnd.random() < 0.15:
            lines.append("see also: " + foreign_kw)
        if has_pn and rnd.random() > 0.1:
            lines.append(f"Page {pi + 1} of {n_pages}")
        pages.append(_noise("\n".join(lines), rnd, rate))
        truth.append({"type": type_name, "is_start": pi == 0})
    return pages, truth


def _make_unknown(rnd: random.Random) -> Tuple[List[str], List[dict]]:
    n_pages = rnd.randint(1, 3)
    pages, truth = [], []
    for pi in range(n_pages):
        lines = [rnd.choice(UNKNOWN_TITLES), ""]
        for _ in range(rnd.randint(2, 5)):
            lines.append(rnd.choice(UNKNOWN_BODY))
        pages.append("\n".join(lines))
        truth.append({"type": "Unknown", "is_start": pi == 0})
    return pages, truth


def make_batch(rnd: random.Random, min_docs: int = 20, max_docs: int = 45) -> Dict:
    """A mortgage package: many documents, frequent same-type repeats."""
    names = list(TYPES.keys())
    n_docs = rnd.randint(min_docs, max_docs)
    seq: List[str] = []
    for _ in range(n_docs):
        if rnd.random() < 0.12:
            seq.append("__UNKNOWN__")
        else:
            seq.append(rnd.choice(names))
    # A,A is COMMON: force several adjacent same-type repeats
    for _ in range(rnd.randint(3, 7)):
        t = rnd.choice(names)
        pos = rnd.randint(0, len(seq))
        seq[pos:pos] = [t, t]

    pages: List[str] = []
    truth: List[dict] = []
    for nm in seq:
        if nm == "__UNKNOWN__":
            p, t = _make_unknown(rnd)
        else:
            foreign = (rnd.choice(TYPES[rnd.choice(names)]["title"])
                       if rnd.random() < 0.3 else None)
            p, t = _make_document(nm, rnd, foreign)
        pages.extend(p)
        truth.extend(t)

    # page-marker trap: stray bracketed marker inside some bodies
    for i in range(len(pages)):
        if rnd.random() < 0.05:
            pages[i] = pages[i] + "\n[PAGE " + str(rnd.randint(1, 3)) + "]\n(stamp inside document)"

    parts = []
    for i, ptext in enumerate(pages, start=1):
        parts.append(f"[PAGE {i}]")
        parts.append(ptext)
    return {"pages": pages, "truth": truth, "ocr": "\n".join(parts)}


def make_dataset(n_batches: int, seed: int = 1234,
                 min_docs: int = 20, max_docs: int = 45) -> List[Dict]:
    rnd = random.Random(seed)
    return [make_batch(rnd, min_docs, max_docs) for _ in range(n_batches)]
