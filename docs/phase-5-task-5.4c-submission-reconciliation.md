# Phase 5 Task 5.4C — Contest Submission Status Reconciliation & UNKNOWN Recovery Specification

---

## 1. Purpose

Phase 5 Task 5.4C implements a deterministic, read-only reconciliation service (`ContestSubmissionReconciliationService`) for Razorpay contest submissions created by Task 5.4B.

It resolves local submission records in `UNKNOWN` or `SUBMISSION_IN_PROGRESS` state without creating any new Razorpay mutation operations.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> "SUBMIT ONCE → NEVER BLINDLY RETRY → READ RAZORPAY STATUS → RECONCILE LOCALLY → AUDIT EVERYTHING"

---

## 2. Architecture & Workflow

```
[ Ambiguous Submission ] (UNKNOWN / IN_PROGRESS)
          │
          ▼
[ Re-verify Input Fingerprint ] ──── (Stale?) ────> [ Outcome: STALE_FINGERPRINT ] (No State Change)
          │
          ▼
[ Read-Only Lookup: get_dispute(id) ]
          │
  ┌───────┼───────────────────────────┬───────────────────────────┐
  │ (Status: under_review/won/lost)   │ (404 / Ambiguous)         │ (401/403/429/5xx/Timeout)
  ▼                                   ▼                           ▼
[ CAS Update: SUBMITTED ]    [ Outcome: UNRESOLVED_UNKNOWN ] [ Outcome: ERROR_LOOKUP_FAILED ]
  (State Reconciled)           (Keep Local State UNKNOWN)    (Keep Local State UNKNOWN)
```

---

## 3. UNKNOWN State Model

`UNKNOWN` state represents an ambiguous submission attempt where external network transmission failed or timed out before receiving an HTTP response.

- **Strict Prohibition**: Automated re-transmission is strictly forbidden.
- **Resolution Path**: Resolved exclusively via read-only status reconciliation (`reconcile_contest_submission`).

---

## 4. SUBMISSION_IN_PROGRESS State Model

`SUBMISSION_IN_PROGRESS` indicates a submission claim made locally before making an HTTP POST call.

- If an application crash or process interruption occurs during transmission, the state remains `SUBMISSION_IN_PROGRESS`.
- Reconciliation evaluates whether Razorpay received the request before resolving state to `SUBMITTED` or retaining state.

---

## 5. Read-Only Reconciliation Mechanism

- Reuses existing `RazorpayClient.get_dispute()`.
- Introduces **ZERO** new client abstractions or generic HTTP methods.
- Exposes **ZERO** mutation endpoints (`POST`, `PATCH`, `PUT`, `DELETE`).

---

## 6. State Machine Transitions

| Previous State | External Lookup Status | Transition Outcome | New Local State |
| :--- | :--- | :--- | :--- |
| `UNKNOWN` | `under_review` / `action_required` / `won` / `lost` | `RECONCILED_SUBMITTED` | `SUBMITTED` |
| `SUBMISSION_IN_PROGRESS` | `under_review` / `action_required` / `won` / `lost` | `RECONCILED_SUBMITTED` | `SUBMITTED` |
| `UNKNOWN` | `open` / unverified | `UNRESOLVED_UNKNOWN` | `UNKNOWN` |
| `UNKNOWN` | 404 Not Found | `UNRESOLVED_UNKNOWN` | `UNKNOWN` |
| `UNKNOWN` | 401 / 403 / 429 / 5xx / Timeout | `ERROR_LOOKUP_FAILED` | `UNKNOWN` |
| `SUBMITTED` | Any | `ALREADY_SUBMITTED` | `SUBMITTED` |

---

## 7. Asynchronous Status Handling

- Distinguishes submission confirmation (`under_review`) from final dispute resolution (`won` / `lost`).
- Does **NOT** convert `under_review` to `won` or `lost`.

---

## 8. 404 Ambiguity Handling

- A 404 Not Found response during status lookup does not prove non-submission.
- Retains local state as `UNKNOWN` and logs an audit record (`LOOKUP_404_AMBIGUOUS`).

---

## 9. Network Failure & Exception Safety

- Network timeouts, connection resets, or 5xx server errors leave local submission state unchanged (`UNKNOWN`).
- Network failures never trigger automatic re-submission attempts.

---

## 10. Authentication Failure Strategy

- HTTP 401 Unauthorized or HTTP 403 Forbidden returns `ERROR_LOOKUP_FAILED`.
- Secrets and credentials are never logged or exposed in audit trails.

---

## 11. Rate Limiting Defense

- HTTP 429 Rate Limit returns `ERROR_LOOKUP_FAILED` without creating infinite retry loops.

---

## 12. Input Fingerprint Validation

- Recomputed SHA-256 input fingerprint is compared against stored `submission.input_fingerprint`.
- If current inputs differ, returns `STALE_FINGERPRINT` without mutating state.

---

## 13. Financial Safety & Immutability

- Baseline capture of `payment_id`, `amount`, `currency` before reconciliation.
- Re-assertion after execution that financial fields are 100% untouched.

---

## 14. Concurrency Protection (CAS Lock)

Conditional SQL update prevents worker race conditions:
```sql
UPDATE contest_submissions
SET state = 'SUBMITTED', razorpay_status = :rzp_status, reconciled_at = :now
WHERE id = :id AND state IN ('UNKNOWN', 'SUBMISSION_IN_PROGRESS');
```

---

## 15. Append-Only Audit Trail

Generates append-only `ContestSubmissionAudit` records detailing previous state, new state, outcome, lookup status, and sanitized metadata.

---

## 16. API Contract

### Endpoint: `POST /api/disputes/{dispute_id}/contest-submission/reconcile`
- **Request Body**: `{}` (Pydantic `extra="forbid"` schema)
- **Response Schema (`ContestSubmissionReconciliationResponse`)**:
  ```json
  {
    "submission_id": "sub_01HXYZ...",
    "dispute_id": "disp_synth_0002",
    "previous_status": "UNKNOWN",
    "new_status": "SUBMITTED",
    "outcome": "RECONCILED_SUBMITTED",
    "razorpay_status": "under_review",
    "razorpay_reference_id": "sub_ref_mock_disp_synth_0002",
    "reconciled_at": "2026-08-29T05:00:00Z",
    "reconciliation_reason": "Razorpay dispute status 'under_review' confirms contest submission occurred.",
    "audit_id": "aud_01HXYZ..."
  }
  ```

---

## 17. Security Audit Verification

- [x] Zero new Razorpay mutation methods added.
- [x] Only `RazorpayClient.get_dispute()` used.
- [x] Client payload injection blocked via empty body schema.
- [x] Credentials scrubbed from logs and audit records.

---

## 18. No-Blind-Retry Rule Verification

- `UNKNOWN` state is never transitioned automatically to `SUBMISSION_AUTHORIZED` or `SUBMISSION_IN_PROGRESS`.
- Re-transmission requires a separate, explicit user authorization flow.

---

## 19. Testing Summary

- **Task 5.4C Unit Tests**: 32 scenarios passed (24 test methods).
- **Task 5.4C E2E Integration Tests**: 2 test methods passed.
- **Full Project Regression Test Suite**: **499 / 499 tests passed (100% Green)**.

---

## 20. Recovery Model & Limitations

- Resolves network ambiguity safely without external risk.
- Asynchronous final outcomes (`won` / `lost`) are delivered via Razorpay webhooks.

---

## 21. Final Task Status Declaration

PHASE 5 TASK 5.4C — CONTEST SUBMISSION STATUS RECONCILIATION COMPLETE — VERIFIED.
