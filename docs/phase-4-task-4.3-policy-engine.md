# Phase 4 Task 4.3 — Deterministic Policy Engine & Eligibility Evaluation

## 1. Architecture
The Policy Engine evaluates versioned policy rules against trusted dispute data, Phase 4.2 `MatchResult` records, and extracted evidence facts to produce typed, explainable `PolicyResult` records.

```
┌──────────────────────────────────────┐
│        Trusted Dispute Data          │
│ (payment_id, amount, currency, etc.) │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Deterministic Policy Engine          │ (Task 4.3 Engine)
└──────────────────▲───────────────────┘
                   │
┌──────────────────┴───────────────────┐
│             MatchResult              │
│ (MATCH, MISMATCH, MISSING, AMBIGUOUS)│
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             PolicyResult             │
│ (ELIGIBLE, HUMAN_REVIEW, NOT_ELIGIBLE)│
└──────────────────────────────────────┘
```

---

## 2. Policy Decision Model
The Policy Engine evaluates disputes into exactly one of three deterministic outcomes:
- **ELIGIBLE**: All mandatory deterministic evidence requirements are satisfied, and no disqualifying contradictions exist.
- **NOT_ELIGIBLE**: Deterministic evidence establishes a disqualifying condition (e.g., amount mismatch, payment ID mismatch, invalid timeline).
- **HUMAN_REVIEW**: Evidence is incomplete, ambiguous, unverifiable, conflicting across documents, or contains adversarial text.

**Safety Default**: Any uncertainty or ambiguity defaults strictly to `HUMAN_REVIEW`. Never `UNCERTAINTY -> ELIGIBLE`.

---

## 3. Rule Registry
Rules are discoverable via `PolicyRegistry` (`backend/app/policies/registry.py`) and implemented in `backend/app/policies/dispute_rules.py`:
1. `CB13.1-001` (Priority 10): Critical Identity Matching (Payment ID, Order ID & AWB)
2. `CB13.1-002` (Priority 20): Monetary & Currency Verification (Amount minor units & ISO currency)
3. `CB13.1-003` (Priority 30): Cross-Document Consistency (No conflicting Order IDs or AWBs)
4. `CB13.1-004` (Priority 40): Delivery Timeline & Temporal Plausibility (Delivery date <= reference date & >= shipment date)
5. `CB13.1-005` (Priority 50): Evidence Completeness & Unverifiable Fields
6. `CB13.1-006` (Priority 60): Evidence Document Presence Ceiling
7. `CB13.1-007` (Priority 70): Prompt Injection & Adversarial Defense Safeguard

---

## 4. Rule Precedence
Rule priority is deterministic:
1. Safety & Financial Integrity Rules (Priority 10-20, Critical Mismatches -> `NOT_ELIGIBLE`)
2. Cross-Document Consistency & Timeline Rules (Priority 30-40)
3. Evidence Completeness & Safeguard Rules (Priority 50-70, Warnings -> `HUMAN_REVIEW`)

---

## 5. Source-of-Truth Rules
- Dispute financial identity (`payment_id`, `amount`, `currency`) comes exclusively from the trusted local `Dispute` record.
- Evidence extractions are never authoritative for financial identity fields.

---

## 6. MatchResult Interpretation
- `MATCH`: Satisfies rule requirement.
- `MISMATCH`: Fails rule requirement (triggers `NOT_ELIGIBLE` for critical fields).
- `MISSING`: Triggers `HUMAN_REVIEW` or `NOT_ELIGIBLE` based on field criticality.
- `AMBIGUOUS` / `UNVERIFIABLE`: Triggers `HUMAN_REVIEW`.
- `CROSS_DOCUMENT_CONFLICT`: Triggers `HUMAN_REVIEW`.

---

## 7. Evidence Coverage
Coverage is calculated deterministically without AI scoring:
- `required_fact_count` (e.g. 5)
- `satisfied_fact_count`
- `missing_fact_count`
- `ambiguous_fact_count`
- `conflicting_fact_count`
- `coverage_percentage` (`satisfied / required * 100`)

---

## 8. Financial Safety
Dispute financial fields (`payment_id`, `amount`, `currency`) are captured before evaluation and asserted identical after evaluation.

---

## 9. Policy Versioning
Evaluations record `policy_version` (e.g. `cb13.1-v1.0`). Historical evaluations remain immutable when policy rules evolve.

---

## 10. Rule Versioning
Every rule evaluation records `rule_id` and `rule_version` (e.g. `1.0`).

---

## 11. Explainability
Deterministic Templated Explanations:
- **ELIGIBLE**: `"Dispute evidence is DETERMINISTICALLY ELIGIBLE for representment. All critical identity and financial fields match cleanly."`
- **HUMAN_REVIEW**: `"Dispute evidence requires HUMAN REVIEW due to incomplete evidence, cross-document conflicts, or unverifiable fields."`
- **NOT_ELIGIBLE**: `"Dispute evidence is NOT ELIGIBLE for representment due to critical field contradictions or invalid timeline."`

---

## 12. Audit Trail
Persists `dispute_id`, `policy_version`, `outcome`, `decision`, `evaluated_at`, `rule_results`, `reason_codes`, `evidence_coverage`, and `financial_safety_verified` to `policy_results` table.

---

## 13. Idempotency
Evaluating the same dispute multiple times produces identical, deterministic outcomes and cleanly updates stored `PolicyResult` records without primary key conflicts.

---

## 14. API Endpoint
`POST /api/disputes/{dispute_id}/evaluate-policy` accepts strictly `dispute_id` path identifier and returns typed `PolicyResultSchema`.

---

## 15. Security Controls
- Read-only against financial identity.
- Zero LLM calls. Zero embedding calls. Zero Razorpay API mutation calls.

---

## 16. Test Strategy
- 24 unit tests in `backend/tests/unit/test_policy_engine.py`.
- 3 end-to-end integration tests in `backend/tests/integration/test_policy_engine_e2e.py`.

---

## 17. Performance
- Execution time: ~3ms per dispute.
- Lightweight deterministic memory evaluation with 0 network IO.

---

## 18. Known Limitations
- Evaluates Visa Reason Code 13.1 (Product Not Delivered). Future policy versions will extend additional reason codes.

---

## 19. Boundary to Contest Generation
The Policy Engine strictly ends at producing a `PolicyResult` (`ELIGIBLE`, `HUMAN_REVIEW`, or `NOT_ELIGIBLE`). It DOES NOT draft contest responses, upload documents, or submit representment to Razorpay.
