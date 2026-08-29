# Phase 5 Task 5.1 — Explainable Contest Response Drafting Engine

## 1. Architecture
The Explainable Contest Response Drafting Engine consumes trusted `Dispute` data, `ExtractedEvidence` facts, `MatchResult` records, and `PolicyResult` records to construct a human-reviewable, structured, and explainable `ContestDraft`.

```
┌──────────────────────────────────────┐
│        Trusted Dispute Data          │ (Level 1 Source of Truth)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│      Extracted Evidence Facts        │ (Level 2 Source of Truth)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             MatchResult              │ (Level 3 Source of Truth)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│            PolicyResult              │ (Level 4 Source of Truth)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Contest Response Drafting Engine     │ (Task 5.1 Engine)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             ContestDraft             │ (DRAFT ONLY - ZERO Razorpay calls)
│ (DRAFT, REVIEW_REQUIRED, BLOCKED)    │
└──────────────────────────────────────┘
```

---

## 2. Source-of-Truth Hierarchy
- **Level 1 — Trusted Dispute Data**: `payment_id`, `amount`, `currency`, `reason_code`, `status`, `phase`. Authoritative for financial identity.
- **Level 2 — Verified Evidence Facts**: Extracted facts that passed PDF/OCR processing.
- **Level 3 — Match Results**: `MATCH`, `MISMATCH`, `MISSING`, `AMBIGUOUS`, `UNVERIFIABLE`, `NOT_COMPARABLE`, `CROSS_DOCUMENT_CONFLICT`.
- **Level 4 — Policy Result**: Authoritative policy outcome (`ELIGIBLE`, `HUMAN_REVIEW`, `NOT_ELIGIBLE`).

---

## 3. Draft Schema
Implemented in `backend/app/schemas/contest_draft.py`:
- `ContestDraftStatus`: `DRAFT`, `REVIEW_REQUIRED`, `BLOCKED`.
- `FactualArgument`: `argument_id`, `heading`, `statement`, `support_level`, `source_match_result_ids`, `source_evidence_ids`, `source_fact_names`, `explanation`.
- `EvidenceReference`: `evidence_id`, `evidence_type`, `document_name`, `source_page`, `description`.
- `ReviewFlag`: `flag_code`, `severity`, `message`, `source_ids`.
- `ContestDraft`: `id`, `dispute_id`, `policy_result_id`, `draft_version`, `generator_version`, `status`, `title`, `summary`, `dispute_context`, `factual_arguments`, `evidence_references`, `limitations`, `review_flags`, `input_fingerprint`, `generated_at`.

---

## 4. Argument Generation
Factual arguments are generated exclusively from deterministic templates (`backend/app/services/contest_templates.py`). Zero LLM calls. Zero fact fabrication. Unsupported fields output safe statements: `"Supporting evidence was not available for this field."`

---

## 5. Template System
Templates cover:
- Transaction Identity (`payment_id`)
- Amount Verification (Paise minor units rendered cleanly into ₹ symbol e.g., `149900` -> `"₹1,499.00"`)
- Currency Verification
- Merchant Order Relationship (`order_id`)
- Logistics & Tracking (`awb_number`)
- Delivery & Fulfillment Proof (`delivery_date`)
- Recipient Signature Verification
- Discrepancy Warnings & Disqualification Notices

---

## 6. Evidence Grounding
Every `FactualArgument` links directly to:
- `source_match_result_ids`
- `source_evidence_ids`
- `source_fact_names`

---

## 7. Provenance
Reviewers can trace any argument statement back to its source `MatchResult`, `ExtractedEvidence`, `ProcessedArtifact`, and raw `EvidenceDocument`.

---

## 8. Mismatch Handling
`MISMATCH` statuses are never omitted or converted into positive claims. They generate `ReviewFlag` entries and explicit discrepancy notices.

---

## 9. Missing Evidence
Missing evidence produces `MISSING_EVIDENCE` review flags and non-fabricated safe placeholder statements.

---

## 10. Ambiguity
`AMBIGUOUS` and `CROSS_DOCUMENT_CONFLICT` statuses elevate draft status to `REVIEW_REQUIRED` and generate explicit conflict flags exposing both values.

---

## 11. Confidence Preservation
OCR confidence scores below threshold generate `UNVERIFIABLE_FIELD` review flags and are never promoted from `LOW` to `HIGH`.

---

## 12. Financial Safety
Dispute financial fields (`payment_id`, `amount`, `currency`) are captured before draft generation and asserted identical after generation.

---

## 13. Policy Boundary
`PolicyResult` remains authoritative. The drafting engine does not recalculate or override eligibility:
- `NOT_ELIGIBLE` -> `ContestDraftStatus.BLOCKED`
- `HUMAN_REVIEW` -> `ContestDraftStatus.REVIEW_REQUIRED`
- `ELIGIBLE` -> `ContestDraftStatus.DRAFT`

---

## 14. Versioning
Drafts record `generator_version` (`contest-draft-v1.0.0`) and `draft_version` (`1.0`).

---

## 15. Idempotency
Identical inputs generate identical draft content. Draft updates overwrite prior draft records cleanly without primary key collisions.

---

## 16. Audit Trail
Logs audit entries for draft generation lifecycle without exposing API secrets or document contents.

---

## 17. API Endpoint
`POST /api/disputes/{dispute_id}/generate-contest-draft` accepts strictly `dispute_id` path identifier and returns typed `ContestDraft`.

---

## 18. Security Controls
quarantines prompt injection text inside document payloads into `PROMPT_INJECTION_DEFENSE` review flags. Zero network mutation calls.

---

## 19. Test Strategy
- 12 unit tests in `backend/tests/unit/test_contest_draft.py`.
- 3 end-to-end integration tests in `backend/tests/integration/test_contest_draft_e2e.py`.

---

## 20. Performance
Execution time: ~2ms per draft. 100% deterministic memory execution.

---

## 21. Known Limitations
Templates currently target Visa Reason Code 13.1 (Product Not Delivered).

---

## 22. Future Human-Review Workflow
In future tasks, human reviewers will inspect `REVIEW_REQUIRED` and `DRAFT` objects, edit arguments if desired, and perform explicit manual submission.

---

## 23. Explicit No-Submission Boundary
This engine produces ONLY `ContestDraft` objects. It DOES NOT call Razorpay `POST`, `PATCH`, `PUT`, or `DELETE` endpoints, upload evidence, or submit contest responses.
