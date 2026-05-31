using System.Collections.Generic;

namespace SegmentationEngine
{
    /// <summary>
    /// US Home Banking Mortgage (KS_DocType_USHBM) profiles — mirror of
    /// python/segmenter/profiles.json. Built in code so NO JSON parser is needed
    /// (sandbox-safe). 45 configured types; anything else -> "Unknown".
    ///
    /// StrongStart = distinctive page-1 titles.
    /// FirstPage   = page-1-ONLY signature phrases (used to split adjacent same-type
    ///               repeated-title docs that have no page numbers — the A,A case).
    /// AnyPage     = supporting terms. Negative = other types' titles.
    /// IdRegex     = mostly empty by design: mortgage loan numbers are usually
    ///               absent and, when present, CONSTANT across the package.
    /// </summary>
    public static class ProfilesData
    {
        public static List<string> GenericIdRegex() => new List<string>();

        public static List<TypeProfile> Default()
        {
            var L = new List<TypeProfile>();

            L.Add(P("ACHAuthorization",
                S("ach authorization", "automatic draft payment program", "automatic payment authorization"),
                null, S("routing number", "account number", "draft", "authorization"),
                S("closing disclosure", "deed of trust", "note")));

            L.Add(P("AddendumToNote",
                S("addendum to note", "note addendum"), null,
                S("addendum", "promissory note", "rider"),
                S("deed of trust", "closing disclosure")));

            L.Add(P("AddressConfidentialityProgram",
                S("address confidentiality program"), null,
                S("confidentiality", "substitute address", "participant"),
                S("note", "appraisal")));

            L.Add(P("AppraisalAcknowledgment",
                S("appraisal acknowledgment", "appraisal confidentiality program"), null,
                S("appraisal", "acknowledgment", "valuation"),
                S("closing disclosure", "deed of trust")));

            L.Add(P("AppraisalUpdateCompletion",
                S("appraisal update and or completion", "estimate report appraisal valuation", "appraisal update"),
                null, S("appraised value", "completion", "inspection", "valuation"),
                S("note", "closing disclosure")));

            L.Add(P("AutomatedValuationModelNotice",
                S("automated valuation model notice", "customer new freddie bpo appraisal", "automated valuation model"),
                null, S("avm", "valuation model", "estimated value"),
                S("note", "deed of trust")));

            L.Add(P("BuydownAgreement",
                S("buydown agreement", "buydown end date adjustment worksheet", "buydown"),
                null, S("buydown", "subsidy", "temporary rate", "adjustment worksheet"),
                S("closing disclosure", "note")));

            L.Add(P("ClosingDisclosure",
                S("closing disclosure"),
                S("this form is a statement of final loan terms", "closing information transaction information", "date issued"),
                S("closing disclosure", "gtridcdns", "closing cost details", "loan information",
                  "transaction information", "disbursement date", "settlement agent", "loan id",
                  "sale price", "loan terms", "projected payments", "loan calculations",
                  "loan disclosures", "calculating cash to close", "total loan costs",
                  "origination charges", "escrow account"),
                S("deed of trust", "promissory note", "note addendum", "cover sheet and manifest")));

            L.Add(P("ClosingInstructions",
                S("closing instructions", "instructions specific closing instructions", "specific closing instructions"),
                null, S("settlement agent", "disbursement", "closing", "instructions"),
                S("closing disclosure", "deed of trust")));

            L.Add(P("FamilyHousingLoanGuarantee",
                S("family housing loan guarantee", "commitment sfh guaranteed loan", "sfh guaranteed loan"),
                null, S("rural development", "guaranteed loan", "single family housing"),
                S("va loan", "fha")));

            L.Add(P("CreditReport",
                S("credit report", "summary"),
                S("merged credit report", "repository equifax experian transunion"),
                S("fico", "credit score", "tradelines", "inquiries", "equifax", "experian", "transunion"),
                S("credit score disclosure", "appraisal")));

            L.Add(P("ConsumerPrivacyPledge",
                S("consumer privacy pledge", "privacy disclosure", "privacy policy notice"),
                null, S("privacy", "nonpublic personal information", "opt out"),
                S("patriot act", "closing disclosure")));

            L.Add(P("CreditScoreDisclosure",
                S("credit score disclosure"), null,
                S("credit score", "score range", "key factors", "scoring model"),
                S("credit report", "appraisal")));

            L.Add(P("CustomerIdentificationNotice",
                S("customer identification notice", "identification verification usa patriot act information", "customer identification"),
                null, S("usa patriot act", "identity", "identification"),
                S("patriot act disclosure", "privacy pledge")));

            L.Add(P("DeedOfTrust",
                S("deed of trust", "security instrument", "deed of trust security instrument"),
                S("this deed of trust is made", "recording requested by", "definitions words used in multiple sections"),
                S("borrower", "lender", "trustee", "property", "covenants", "recording"),
                S("closing disclosure", "promissory note", "appraisal")));

            L.Add(P("VALoanAnalysis",
                S("va loan analysis", "department of veterans affairs loan analysis"),
                null, S("veterans affairs", "residual income", "va", "entitlement"),
                S("fha", "guaranty certificate")));

            L.Add(P("GuarantyCertificate",
                S("guaranty certificate", "loan guaranty certificate", "guaranty certificate 26 1889"),
                null, S("guaranty", "26 1889", "veterans affairs", "certificate"),
                S("va loan analysis", "closing disclosure")));

            L.Add(P("DriversLicense",
                S("drivers license", "driver s license", "personal identification"),
                null, S("date of birth", "expiration", "license", "class", "dl no"),
                S("note", "deed of trust")));

            L.Add(P("DUUnderwritingFindings",
                S("du underwriting findings", "du underwriting"),
                S("recommendation approve eligible", "casefile id"),
                S("desktop underwriter", "findings", "recommendation", "casefile"),
                S("gus underwriting", "loan product advisor")));

            L.Add(P("EscrowAccountDisclosure",
                S("escrow account disclosure statement", "escrow account disclosure"),
                S("escrow account projection for the coming year", "initial escrow statement"),
                S("escrow", "cushion", "aggregate adjustment", "disbursement"),
                S("closing disclosure", "note")));

            L.Add(P("SupplementalConsumerInfo",
                S("supplemental consumer information form", "supplemental consumer information"),
                null, S("demographic", "supplemental", "consumer information"),
                S("closing disclosure", "appraisal")));

            L.Add(P("FirstPaymentLetter",
                S("first payment letter"), null,
                S("first payment", "payment due", "monthly payment", "remittance"),
                S("closing disclosure", "escrow")));

            L.Add(P("FloodInsuranceIntentToCancel",
                S("flood insurance intent to cancel edi", "electronic image generated for edi data", "flood insurance intent to cancel"),
                null, S("flood", "intent to cancel", "edi"),
                S("flood policy declarations", "homeowner")));

            L.Add(P("FloodInsuranceCancellation",
                S("flood insurance cancellation letter"), null,
                S("flood", "cancellation", "policy"),
                S("flood policy declarations", "flood insurance intent")));

            L.Add(P("FloodPolicyDeclarations",
                S("flood policy declarations", "insurance flood policy declarations flood insurance", "flood policy"),
                null, S("flood zone", "declarations", "coverage", "premium"),
                S("flood insurance cancellation", "homeowner")));

            L.Add(P("GUSUnderwritingFindings",
                S("gus underwriting findings report", "gus underwriting findings", "gus underwriting"),
                S("gus recommendation accept", "submission summary"),
                S("gus", "guaranteed underwriting system", "findings"),
                S("du underwriting", "loan product advisor")));

            L.Add(P("HoldHarmlessAgreement",
                S("hold harmless agreement"), null,
                S("hold harmless", "indemnify", "release"),
                S("closing disclosure", "note")));

            L.Add(P("HomeownerPolicyChange",
                S("homeowner policy change", "homeowner s policy change"), null,
                S("homeowner", "hazard insurance", "policy change", "endorsement"),
                S("flood policy", "mortgage insurance")));

            L.Add(P("HUDAddendumURLA",
                S("hud addendum to uniform residential", "fha va addendum", "1004c 70b", "hud addendum"),
                null, S("uniform residential", "addendum", "hud", "fha va"),
                S("hud fha loan underwriting", "note")));

            L.Add(P("HUDFHALoanUnderwriting",
                S("hud fha loan underwriting and", "luts 92900 lt", "hud fha loan underwriting"),
                null, S("fha", "underwriting", "92900", "mortgage credit analysis"),
                S("hud addendum", "du underwriting")));

            L.Add(P("LoanProductAdvisorFeedback",
                S("loan product advisor feedback", "loan product advisor full feedback certificate", "lp findings"),
                S("risk class accept", "loan product advisor evaluation"),
                S("loan product advisor", "freddie mac", "feedback certificate", "lpa"),
                S("du underwriting", "gus underwriting")));

            L.Add(P("MortgageInsuranceCertificate",
                S("mortgage insurance certificate", "insurance certificate certificate of liability"),
                null, S("mortgage insurance", "mi certificate", "coverage", "certificate"),
                S("mortgage insurance disclosure", "flood policy")));

            L.Add(P("MortgageInsuranceDisclosure",
                S("mortgage insurance disclosure", "concerning private mortgage insurance"),
                null, S("private mortgage insurance", "pmi", "disclosure", "cancellation"),
                S("mortgage insurance certificate", "notice concerning private mortgage")));

            L.Add(P("MortgageInsuranceQuote",
                S("mortgage insurance quote"), null,
                S("mortgage insurance", "quote", "premium rate"),
                S("mortgage insurance certificate", "mortgage insurance disclosure")));

            L.Add(P("Note",
                S("note", "promissory note"),
                S("borrower s promise to pay", "in return for a loan i have received"),
                S("promise to pay", "principal", "interest rate", "maturity", "borrower"),
                S("addendum to note", "deed of trust", "first payment letter")));

            L.Add(P("NoticeConcerningPrivateMortgage",
                S("notice concerning private mortgage"), null,
                S("private mortgage insurance", "notice", "cancellation rights"),
                S("mortgage insurance disclosure", "mortgage insurance certificate")));

            L.Add(P("NoticeToSettlementAgents",
                S("notice to settlement agents"), null,
                S("settlement agent", "notice", "closing"),
                S("closing instructions", "closing disclosure")));

            L.Add(P("OccupancyAffidavit",
                S("occupancy affidavit"), null,
                S("occupancy", "primary residence", "affidavit", "occupy"),
                S("occupancy and use certificate", "financial status affidavit")));

            L.Add(P("OccupancyAndUseCertificate",
                S("occupancy and use certificate"), null,
                S("occupancy", "use certificate", "veterans affairs"),
                S("occupancy affidavit", "financial status affidavit")));

            L.Add(P("FinancialStatusAffidavit",
                S("financial status affidavit", "status affidavit"), null,
                S("financial status", "affidavit", "assets", "liabilities"),
                S("occupancy affidavit", "occupancy and use certificate")));

            L.Add(P("PatriotActDisclosure",
                S("patriot act disclosure", "usa patriot act information disclosure"),
                null, S("usa patriot act", "disclosure", "anti money laundering"),
                S("customer identification notice", "patriot act information form")));

            L.Add(P("PatriotActInformationForm",
                S("patriot act information form", "usa patriot act information form"),
                null, S("usa patriot act", "information form", "identity verification"),
                S("patriot act disclosure", "customer identification notice")));

            L.Add(P("PaymentDeferralRepaymentPlan",
                S("payment deferral and repayment plan", "payment deferral and repayment plan agreement"),
                null, S("deferral", "repayment plan", "delinquent", "modification"),
                S("first payment letter", "note")));

            return L;
        }

        private static TypeProfile P(string name, List<string> strong, List<string> firstPage,
                                     List<string> any, List<string> neg)
        {
            return new TypeProfile
            {
                Name = name,
                StrongStart = strong ?? new List<string>(),
                FirstPage = firstPage ?? new List<string>(),
                AnyPage = any ?? new List<string>(),
                Negative = neg ?? new List<string>(),
                IdRegex = new List<string>(),
            };
        }

        private static List<string> S(params string[] items) => new List<string>(items);
    }
}
