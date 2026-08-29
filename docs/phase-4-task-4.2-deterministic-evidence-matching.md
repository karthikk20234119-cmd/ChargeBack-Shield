# Phase 4 Task 4.2 — Deterministic Evidence Matching Engine

## 1. Architecture
The Deterministic Evidence Matching Engine compares trusted dispute/payment data against `ExtractedEvidence` facts to produce typed, auditable `MatchResult` records.

```
┌──────────────────────────────────────┐
│        Trusted Dispute Data          │
│ (payment_id, amount, currency, etc.) │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Deterministic Evidence Matcher       │ (Task 4.2 Engine)
└──────────────────▲───────────────────┘
                   │
┌──────────────────┴───────────────────┐
│          ExtractedEvidence           │
│ (facts across all dispute documents) │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             MatchResult              │
│ (MATCH, MISMATCH, MISSING, AMBIGUOUS)│
└──────────────────────────────────────┘
```

---

## 2. Source-of-Truth Rules
- Trusted financial identity fields (`payment_id`, `amount`, `currency`) MUST come from the trusted local `Dispute` record.
- `ExtractedEvidence` is NEVER authoritative for financial identity fields.
- Financial Identity Assertion: Dispute financial identity fields are strictly read-only and cannot be mutated by matching logic.

---

## 3. MatchResult Schema
Each `MatchResult` database record captures:
- `id`: Primary key UUID
- `dispute_id`: Foreign key to `disputes.id`
- `evidence_id`: Foreign key to `evidence_documents.id`
- `processed_artifact_id`: Foreign key to `processed_artifacts.id`
- `fact_name`: Evaluated fact name (e.g. `amount_minor`, `payment_id`, `currency`, `awb_number`)
- `expected_value`: Trusted reference value at match time
- `observed_value`: Extracted value at match time
- `normalized_expected_value`: Normalized expected snapshot
- `normalized_observed_value`: Normalized observed snapshot
- `status`: `MATCH`, `MISMATCH`, `MISSING`, `AMBIGUOUS`, `NOT_COMPARABLE`, `CROSS_DOCUMENT_CONFLICT`
- `confidence`: `HIGH`, `MEDIUM`, `LOW`
- `source_page`: 1-indexed page number
- `source_region`: Bounding box coordinates
- `extraction_method`: Extraction technique (`vision`, `ocr`, `text`)
- `matcher_version`: `"1.0"`
- `explanation`: Deterministic templated explanation text

---

## 4. Matching Algorithms & Comparison Functions
1. `compare_exact`: Compares exact normalized string identifiers.
2. `compare_amount`: Compares amounts in integer minor units (paise/cents).
3. `compare_currency`: Compares uppercase ISO currency codes (`INR` == `inr`).
4. `compare_date`: Compares ISO `YYYY-MM-DD` date strings.
5. `compare_email`: Compares normalized lowercase email addresses.
6. `compare_phone`: Compares normalized phone numbers.
7. `compare_tracking_id`: Compares normalized tracking numbers.

---

## 5. Amount Comparison
Amounts are strictly compared using integer minor units (paise).
- Expected: `149900`
- Observed: `"₹1,499.00"` -> `149900`
- Result: `MATCH`
Floating-point equality and raw string comparisons are strictly forbidden.

---

## 6. Currency Comparison
Currencies are normalized to uppercase ISO 4217 codes.
- Expected: `"INR"`
- Observed: `"inr"` -> `"INR"`
- Result: `MATCH`
Currency conversion is never performed.

---

## 7. Date Comparison
Dates are parsed into ISO `YYYY-MM-DD` representation.
- Expected: `"2026-08-15"`
- Observed: `"15 Aug 2026"` -> `"2026-08-15"`
- Result: `MATCH`
Partial or unparseable dates result in `AMBIGUOUS`.

---

## 8. String & Identifier Comparison
Identifiers (payment ID, order ID, AWB, invoice number) preserve exact normalized identifier semantics after trimming leading/trailing whitespace.

---

## 9. Missing Data Handling
- Trusted value exists but evidence fact is missing -> `MISSING`.
- Evidence fact exists but no trusted reference exists -> `NOT_COMPARABLE`.

---

## 10. Ambiguity & Conflict Handling
- Unclear, unparseable, or low-confidence OCR facts -> `AMBIGUOUS`.
- Conflicting facts across documents -> `CROSS_DOCUMENT_CONFLICT`.

---

## 11. Confidence Handling
Carries forward extraction confidence levels (`HIGH`, `MEDIUM`, `LOW`). Confidence is never artificially inflated by the matcher.

---

## 12. Provenance & Auditability
Every `MatchResult` tracks its `source_page`, `processed_artifact_id`, `extraction_method`, and `matcher_version`, enabling 100% visual highlighting and auditability.

---

## 13. Deterministic Explainability
Explanations are generated via string templates (e.g. `"Amount matches trusted dispute amount: 149900 paise"`, `"Amount mismatch: trusted dispute amount is 149900 paise, evidence amount is 99900 paise"`). Zero LLM calls are used.

---

## 14. Financial Safety Invariants
Dispute financial fields (`payment_id`, `amount`, `currency`) are asserted untouched before and after every matching run.

---

## 15. Idempotency & Snapshot Integrity
Re-running matching on the same dispute replaces previous `MatchResult` rows cleanly without duplicate primary key collisions. Historical snapshot values are preserved in `normalized_expected_value` and `normalized_observed_value`.

---

## 16. Database Model
Mapped to `match_results` database table with foreign keys to `disputes`, `evidence_documents`, and `processed_artifacts`.

---

## 17. API Endpoint
`POST /api/disputes/{dispute_id}/match-evidence` accepts strictly `dispute_id` path identifier and returns typed `MatchingRunResult`.

---

## 18. Security Controls
- Read-only against financial identity.
- Client cannot supply expected amounts or match decisions in HTTP request body.

---

## 19. Test Strategy
- 13 unit tests in `backend/tests/unit/test_evidence_matching.py`.
- 3 end-to-end integration tests in `backend/tests/integration/test_evidence_matching_e2e.py`.

---

## 20. Performance Metrics
- Execution time: ~5ms per dispute.
- Pure deterministic logic with 0 network/LLM calls.

---

## 21. Known Limitations & Future Scope
- The matching engine produces evidence match facts. Final eligibility decisions and policy evaluations belong strictly to Task 4.3 (Policy Engine).
