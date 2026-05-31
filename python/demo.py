"""Readable end-to-end demo on a MORTGAGE package (US Home Banking Mortgage).

One TTA-style OCR string with [PAGE n] separators in -> segments out. Shows:
  - two Closing Disclosures back-to-back (A,A), repeated title every page,
    split by page-number reset + page-1 signature
  - a multi-page Deed of Trust kept whole despite no page numbers
  - an Unknown cover page routed to review
  - in-body stray [PAGE 1] trap ignored

Run:  python3 -B demo.py
"""
from segmenter.engine import Segmenter

OCR = """[PAGE 1]
CLOSING DISCLOSURE
This form is a statement of final loan terms
Loan Terms
Projected Payments
Loan Amount $ 320,000
Page 1 of 2
[PAGE 2]
CLOSING DISCLOSURE
Costs at Closing
Cash to Close
Lender Credits
Page 2 of 2
[PAGE 3]
CLOSING DISCLOSURE
This form is a statement of final loan terms
Loan Terms
Projected Payments
Loan Amount $ 415,000
Page 1 of 2
[PAGE 4]
CLOSING DISCLOSURE
Summaries of Transactions
Page 2 of 2
[PAGE 5]
DEED OF TRUST
THIS DEED OF TRUST is made
Recording requested by
Borrower owes Lender the principal sum
[PAGE 6]
Uniform Covenants
Transfer of the Property
the Property is located in the County of
[PAGE 7]
MISCELLANEOUS CORRESPONDENCE

Please find the attached items.
[PAGE 1]
(stray in-body marker - the trap)
[PAGE 8]
NOTE
BORROWER S PROMISE TO PAY
in return for a loan I have received
principal sum of $ 415,000
"""


def main() -> None:
    seg = Segmenter()
    segments, decisions, pages = seg.segment_ocr(OCR)
    print(f"Split into {len(pages)} pages (stray in-body [PAGE 1] ignored).\n")
    print(f"{'pages':<9}{'type':<24}{'conf':<7}{'review':<8}reason")
    print("-" * 86)
    for s in segments:
        rng = (f"{s.start_page + 1}-{s.end_page + 1}"
               if s.page_count > 1 else f"{s.start_page + 1}")
        print(f"{rng:<9}{s.doc_type:<24}{s.confidence:<7.2f}"
              f"{'YES' if s.needs_review else 'no':<8}{s.reason[:38]}")


if __name__ == "__main__":
    main()
