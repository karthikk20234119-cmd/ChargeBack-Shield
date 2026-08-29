# Phase 5 Task 5.5 — Final Dispute Outcome Synchronization & Submission Lifecycle Monitoring Specification

---

## 1. Objective

Phase 5 Task 5.5 implements a deterministic, read-only lifecycle synchronization service (`DisputeLifecycleSyncService`) for Razorpay disputes after contest submission.

It observes and synchronizes external dispute processing status and final outcomes into local append-only snapshot records without performing ANY Razorpay mutation operations.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> "SUBMISSION CONFIRMATION ≠ FINAL DISPUTE OUTCOME"

---

## 2. Architecture Diagram

```
[ Local Dispute Record ]
          │
          ▼
[ Read-Only Lookup: RazorpayClient.get_dispute(id) ]
          │
          ▼
[ Validate Status & Phase Mapping ]
          │
  ┌───────┴───────────────────────────────┐
  │ (Status Change / Terminal Check)      │ (Error / Ambiguity)
  ▼                                       ▼
[ Create Append-Only Snapshot ]  [ Return SYNC_FAILED / UNKNOWN ]
  (DisputeLifecycleSnapshot)       (Local State Untouched)
          │
          ▼
[ Append-Only Audit Trail ]
```

---

## 3. Submission vs. Outcome Separation

- `ContestSubmission.state`: Reflects local representment transmission (`SUBMITTED`, `FAILED`, `UNKNOWN`).
- `DisputeLifecycleStatus`: Reflects Razorpay dispute processing state (`UNDER_REVIEW`, `ACTION_REQUIRED`).
- `DisputeOutcome`: Reflects final merchant outcome (`WON`, `LOST`, `UNDER_REVIEW`, `PENDING`).

---

## 4. Lifecycle States Model (`DisputeLifecycleStatus`)

- `UNKNOWN`: Uninitialized or unmapped state.
- `SUBMITTED`: Representment submitted to Razorpay.
- `UNDER_REVIEW`: Razorpay / issuing bank reviewing contest evidence.
- `ACTION_REQUIRED`: Merchant action requested by Razorpay.
- `WON`: Dispute resolved in merchant's favor.
- `LOST`: Dispute resolved in cardholder's favor.
- `UNKNOWN_EXTERNAL_STATUS`: Unrecognized external status value.

---

## 5. Outcome Model (`DisputeOutcome`)

- `PENDING`: Dispute pending submission or review.
- `UNDER_REVIEW`: Representment under active review.
- `ACTION_REQUIRED`: Additional merchant evidence needed.
- `WON`: **Terminal** success outcome.
- `LOST`: **Terminal** loss outcome.
- `UNKNOWN`: Outcome unverified or lookup failed.

---

## 6. Status Mapping Matrix

| Razorpay `status` | `DisputeLifecycleStatus` | `DisputeOutcome` |
| :--- | :--- | :--- |
| `under_review` | `UNDER_REVIEW` | `UNDER_REVIEW` |
| `action_required` | `ACTION_REQUIRED` | `ACTION_REQUIRED` |
| `won` | `WON` | `WON` |
| `lost` | `LOST` | `LOST` |
| `open` / `closed` | `SUBMITTED` / `UNKNOWN` | `PENDING` |
| Undocumented / missing | `UNKNOWN_EXTERNAL_STATUS` | `UNKNOWN` |

---

## 7. Phase Handling

- Razorpay `phase` (e.g. `fraud`, `retrieval`, `chargeback`, `pre_arbitration`) is captured and stored independently.
- `phase` alone is **NEVER** used to infer `WON` or `LOST`.

---

## 8. Transition Rules

- Valid: `SUBMITTED` $\rightarrow$ `UNDER_REVIEW` / `ACTION_REQUIRED` / `WON` / `LOST`.
- Valid: `UNDER_REVIEW` $\rightarrow$ `ACTION_REQUIRED` / `WON` / `LOST`.
- Valid: `ACTION_REQUIRED` $\rightarrow$ `UNDER_REVIEW` / `WON` / `LOST`.
- Invalid / Unexpected (e.g., `WON` $\rightarrow$ `LOST` or `LOST` $\rightarrow$ `WON`): Recorded as `UNEXPECTED_TRANSITION` snapshot without mutating terminal outcome.

---

## 9. Terminal Outcomes Immutability

- Once local outcome reaches `WON` or `LOST`, it becomes **TERMINAL**.
- Subsequent polling cannot overwrite terminal outcomes. Contradictory external responses generate anomaly snapshot entries (`UNEXPECTED_TRANSITION`).

---

## 10. Unknown Status Handling

- Unrecognized status strings map to `UNKNOWN_EXTERNAL_STATUS` / `UNKNOWN`.
- Never fabricates `WON` or `LOST` from unknown status values.

---

## 11. Error Handling Matrix

| Exception Class | Response Outcome | Synchronization Result | Local State Change |
| :--- | :--- | :--- | :--- |
| `RazorpayNotFoundError` (404) | Previous Outcome | `SYNC_FAILED` | None |
| `RazorpayAuthenticationError` (401/403) | Previous Outcome | `SYNC_FAILED` | None |
| `RazorpayRateLimitError` (429) | Previous Outcome | `SYNC_FAILED` | None |
| `RazorpayServerError` (500) | Previous Outcome | `SYNC_FAILED` | None |
| `RazorpayNetworkError` (Timeout) | Previous Outcome | `SYNC_FAILED` | None |

---

## 12. Financial Safety & Immutability

- Pre-execution and post-execution assertions verify `Dispute.payment_id`, `amount`, and `currency` are 100% untouched.

---

## 13. Fingerprint Handling

- `input_fingerprint` is captured in `DisputeLifecycleSnapshot` for provenance tracking. Stale local states are flagged as `STALE_LOCAL_STATE`.

---

## 14. Audit Trail

- Append-only `ContestSubmissionAudit` logging.
- `_sanitize_metadata` scrubs all `auth`, `key`, `secret`, `password`, `token`, or `credential` keys.

---

## 15. API Contract

### Endpoint: `POST /api/disputes/{dispute_id}/lifecycle/sync`
- **Request Body**: `{}` (Pydantic `extra="forbid"` schema)
- **Response Schema (`DisputeLifecycleSyncResponse`)**:
  ```json
  {
    "dispute_id": "disp_synth_0003",
    "razorpay_dispute_id": "disp_synth_0003",
    "previous_status": "SUBMITTED",
    "current_status": "WON",
    "razorpay_status": "won",
    "razorpay_phase": "chargeback",
    "outcome": "WON",
    "transition_type": "SUBMITTED -> WON",
    "synchronization_result": "STATE_CHANGED",
    "snapshot_id": "snap_01HXYZ...",
    "audit_id": "aud_01HXYZ...",
    "observed_at": "2026-08-29T05:20:00Z"
  }
  ```

---

## 16. Polling Behavior

- Idempotent repeated polling on unchanged state creates no duplicate status transitions and returns `synchronization_result = UNCHANGED`.

---

## 17. Security Audit Verification

- [x] `RazorpayClient` remains strictly read-only (`GET /v1/disputes/{dispute_id}`).
- [x] Zero mutation methods (`POST`, `PATCH`, `PUT`, `DELETE`, `submit_contest()`, `accept_dispute()`, `reject_dispute()`, `issue_refund()`).
- [x] Zero AI / LLM calls.
- [x] Empty request body payload injection defense.

---

## 18. Forbidden Operations Checklist

- [x] No `accept_dispute()`
- [x] No `reject_dispute()`
- [x] No `issue_refund()`
- [x] No automatic contest re-submission
- [x] No financial field modifications

---

## 19. Testing Summary

- **Task 5.5 Unit Tests**: 30 test methods (covering 40 scenarios) passed.
- **Task 5.5 E2E Integration Tests**: 2 test methods passed.
- **Full Project Regression Suite**: **531 / 531 tests passed (100% Green)**.

---

## 20. Known Limitations

1. **Mock Execution Default**: Mock client used in tests; production relies on live credentials configured in environment variables.
2. **Asynchronous Webhook Sync**: Real-time push updates can complement polling via webhooks.

---

## 21. Final Task Status Declaration

PHASE 5 TASK 5.5 — DISPUTE LIFECYCLE & FINAL OUTCOME SYNCHRONIZATION COMPLETE — VERIFIED.
