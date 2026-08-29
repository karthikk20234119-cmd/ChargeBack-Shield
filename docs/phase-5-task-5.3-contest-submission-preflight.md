# Phase 5 Task 5.3 — Contest Submission Preflight & Local Authorization Gate

## Executive Summary

Phase 5 Task 5.3 implements the **Contest Submission Preflight & Local Authorization Gate** (`ContestSubmissionPreflightService`). The service provides a deterministic local verification gate that checks whether an `APPROVED` contest response draft is completely safe, consistent, and factual before proceeding to any future submission task.

### Strict Safety Boundaries
- **HARD STOP / LOCAL ONLY**: ZERO Razorpay mutation API calls (`POST` contest, `PATCH` dispute, `PUT` dispute, `DELETE` dispute, dispute acceptance, dispute rejection, evidence submission, payment modification).
- ZERO external network calls, zero AI/LLM calls, zero embeddings.
- Core invariant: `"Generate locally → Review locally → Authorize locally → Never mutate Razorpay."`
- ZERO modification of `Dispute` financial fields (`payment_id`, `amount`, `currency`), `PolicyResult`, `MatchResult`, `ContestDraft.status`, `ContestDraft.review_status`, `ContestDraft.factual_arguments`, `ContestDraft.evidence_references`, `ExtractedEvidence`, `EvidenceDocument`, `ProcessedArtifact`.

---

## 1. System Architecture

```
                                Trusted Dispute Data
                                        │
                                        ├── payment_id, amount, currency
                                        ▼
                                [Policy Engine] ──> PolicyResult
                                        │
                                        ▼
                            [Drafting Engine Task 5.1] ──> ContestDraft
                                        │
                                        ▼
                        [Human Review Task 5.2] ──> ContestDraft.review_status = APPROVED
                                        │
                                        ▼
                     [Preflight Authorization Gate Task 5.3]
                                        │
 ┌──────────────────────────────────────┼──────────────────────────────────────┐
 │                                      │                                      │
 ▼                                      ▼                                      ▼
[FINANCIAL IDENTITY]          [FINGERPRINT MATCH]                  [9 CHECK MODULES]
 • payment_id check            • current SHA-256                    • Financial identity
 • amount check                • stored draft SHA-256               • Fingerprint check
 • currency check              • mismatch -> STALE (409)            • Policy status check
                                                                    • Review status check
                                                                    • Policy consistency
                                                                    • Match consistency
                                                                    • Evidence provenance
                                                                    • Factual completeness
                                                                    • Unresolved conflicts
                                        │
                                        ▼
                    Local Snapshot: ContestSubmissionPreflight
                                        │
                            PreflightStatus Outcome
                    (READY / BLOCKED / STALE / REVIEW_REQUIRED)
```

---

## 2. Preflight Status & Decision Matrix

| PreflightStatus | Condition / Trigger | HTTP Code | Actions Allowed |
| :--- | :--- | :--- | :--- |
| **READY** | Draft `review_status == APPROVED`, `draft_status != BLOCKED`, input fingerprint matches 100%, financial identity verified, evidence provenance 100% verified, 0 blocking findings. | `200 OK` | Safe for future local preview/submission pipeline. |
| **REVIEW_REQUIRED** | Draft `review_status != APPROVED` (`PENDING_REVIEW` or `REJECTED`), and no critical structural/financial failures. | `200 OK` | Requires merchant human review approval (Task 5.2). |
| **BLOCKED** | Draft `status == BLOCKED`, financial identity modified, missing/inconsistent `PolicyResult`, unresolved critical mismatches, broken evidence provenance, or empty factual arguments. | `200 OK` | Cannot proceed. Must regenerate draft or fix evidence mismatch. |
| **STALE** | `compute_contest_draft_input_fingerprint()` differs from `ContestDraft.input_fingerprint`. Raised via `StaleDraftException`. | `409 Conflict` | Draft stale due to underlying dispute/match/policy changes. |
| **INVALID** | Dispute ID not found or malformed payload. | `404 / 422` | Invalid request. |

---

## 3. Preflight Check Sequence (9 Modules)

1. **`FINANCIAL_IDENTITY_CHECK`**: Verifies trusted dispute `payment_id`, `amount`, `currency` against stored values.
2. **`FINGERPRINT_CHECK`**: Re-computes SHA-256 input fingerprint using shared helper `compute_contest_draft_input_fingerprint`.
3. **`POLICY_STATUS_CHECK`**: Verifies `ContestDraft.status` is not `BLOCKED`.
4. **`REVIEW_APPROVAL_CHECK`**: Checks whether `ContestDraft.review_status` is `APPROVED`.
5. **`POLICY_CONSISTENCY_CHECK`**: Ensures `PolicyResult` outcome matches stored draft policy state (`ELIGIBLE` / `HUMAN_REVIEW`).
6. **`MATCH_CONSISTENCY_CHECK`**: Verifies no unresolved critical field mismatches (`status == MISMATCH` & `is_critical == True`) exist.
7. **`EVIDENCE_PROVENANCE_CHECK`**: Validates 100% of `source_evidence_ids` and `source_match_result_ids` against database records.
8. **`FACTUAL_ARGUMENT_CHECK`**: Ensures `factual_arguments` contains valid factual sections.
9. **`UNRESOLVED_CONFLICT_CHECK`**: Checks for unresolved review flags on draft.

---

## 4. API Specification

### `POST /api/disputes/{dispute_id}/contest-submission/preflight`
- **Request Body**: Empty (`{}`). All parameters are derived directly from the database to prevent client injection.
- **Response**: `ContestSubmissionPreflightResult` schema.

```json
{
  "id": "36cbba1d-9e4d-4d80-a776-030f92da9f63",
  "dispute_id": "disp_synth_0001",
  "contest_draft_id": "2d70ae55-907d-4f1b-8a82-de6b1565f30d",
  "policy_result_id": "pol_synth_0001",
  "status": "READY",
  "draft_status": "DRAFT",
  "review_status": "APPROVED",
  "input_fingerprint": "460de2a0a7a9...",
  "draft_version": "1.0",
  "generator_version": "contest-draft-v1.0.0",
  "checks": [
    {
      "check_code": "FINANCIAL_IDENTITY_CHECK",
      "status": "PASS",
      "message": "Financial identity verified: payment_id=pay_synth_0001, amount=9030000, currency=INR",
      "severity": "INFO",
      "source_ids": ["disp_synth_0001"]
    }
  ],
  "blocking_reasons": [],
  "warnings": [],
  "verified_financial_identity": {
    "payment_id": "pay_synth_0001",
    "amount": 9030000,
    "currency": "INR"
  },
  "verified_evidence_count": 2,
  "generated_at": "2026-08-28T16:36:42.510000"
}
```

---

## 5. Test Suite Verification

Full regression baseline: **439 / 439 tests passing (100%)**.
- Task 5.3 Unit Tests (`test_contest_submission_preflight.py`): 30 tests passing.
- Task 5.3 E2E Integration Tests (`test_contest_submission_preflight_e2e.py`): 2 tests passing.
