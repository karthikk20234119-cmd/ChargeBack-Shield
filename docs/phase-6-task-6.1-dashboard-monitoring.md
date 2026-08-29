# Phase 6 Task 6.1 — Dispute Lifecycle Dashboard & Operational Monitoring Specification

---

## 1. Objective

Phase 6 Task 6.1 builds a read-only operational dashboard for Chargeback Shield. It provides a unified 360-degree view of the complete dispute lifecycle:

Dispute $\rightarrow$ Evidence $\rightarrow$ Processing $\rightarrow$ Extraction $\rightarrow$ Matching $\rightarrow$ Policy $\rightarrow$ Contest Draft $\rightarrow$ Human Review $\rightarrow$ Preflight $\rightarrow$ Submission $\rightarrow$ Reconciliation $\rightarrow$ Razorpay Lifecycle $\rightarrow$ Final Outcome.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> "THE DASHBOARD IS AN OBSERVABILITY LAYER ONLY. IT NEVER TRIGGERS MUTATIONS OR BUSINESS DECISIONS."

---

## 2. Architecture Diagram

```
[ Local Database (Postgres/SQLite) ]
  ├── disputes
  ├── evidence_documents & extracted_evidence
  ├── match_results
  ├── policy_results
  ├── contest_drafts & contest_draft_review_audits
  ├── contest_submission_preflights
  ├── contest_submissions & contest_submission_audits
  └── dispute_lifecycle_snapshots
          │
          ▼ (Strictly Read-Only Queries — AsyncSession)
[ DashboardService (backend/app/services/dashboard_service.py) ]
  ├── Summary Aggregations
  ├── Paginated Dispute List & Safe Filtering
  ├── 360-Degree Detail & Timeline Builder
  ├── Operational Alert Detection
  ├── Reconciliation Required Monitoring
  ├── Action Required Monitoring
  └── Outcome Summaries
          │
          ▼ (Typed Pydantic Response Schemas)
[ Dashboard API Router (backend/app/api/dashboard.py) ]
  ├── GET /api/dashboard/summary
  ├── GET /api/dashboard/disputes
  ├── GET /api/dashboard/disputes/{dispute_id}
  ├── GET /api/dashboard/alerts
  ├── GET /api/dashboard/reconciliation-required
  ├── GET /api/dashboard/action-required
  └── GET /api/dashboard/outcomes
```

---

## 3. Dashboard Summary Metrics (`DashboardSummary`)

- `total_disputes`: Total disputes ingested into local database.
- `evidence_uploaded`: Total evidence documents uploaded.
- `evidence_processing`: Documents currently being processed.
- `evidence_ready`: Documents with completed extraction (`AI_EXTRACTED`).
- `extraction_completed`: Distinct documents with extracted evidence.
- `matching_completed`: Disputes with evaluated match results.
- `eligible_count`: Policy decisions evaluated as `ELIGIBLE`.
- `human_review_count`: Policy decisions evaluated as `HUMAN_REVIEW`.
- `not_eligible_count`: Policy decisions evaluated as `NOT_ELIGIBLE`.
- `drafts_pending_review`: Drafts in `PENDING_REVIEW` state.
- `drafts_approved`: Drafts in `APPROVED` review state.
- `drafts_rejected`: Drafts in `REJECTED` review state.
- `preflight_ready`: Preflights in `READY` state.
- `preflight_blocked`: Preflights in `BLOCKED` state.
- `submissions_in_progress`: Submissions locked in `SUBMISSION_IN_PROGRESS`.
- `submissions_submitted`: Submissions in `SUBMITTED` state.
- `submissions_unknown`: Submissions in `UNKNOWN` state.
- `reconciliation_required`: Count of `UNKNOWN` submissions needing reconciliation.
- `under_review_count`: Disputes currently under Razorpay review (`UNDER_REVIEW`).
- `action_required_count`: Disputes requiring merchant action (`ACTION_REQUIRED`).
- `won_count`: Final merchant victory count (`WON`).
- `lost_count`: Final dispute loss count (`LOST`).
- `failed_operations`: Submissions in `FAILED` state.
- `generated_at`: UTC timestamp of metric calculation.

---

## 4. Dispute List & Safe Filtering (`GET /api/dashboard/disputes`)

- **Supported Filters**: `status`, `policy_outcome`, `review_status`, `preflight_status`, `submission_status`, `lifecycle_status`, `outcome`, `created_from`, `created_to`.
- **Bounded Pagination**: `page` (default 1), `page_size` (default 20, min 1, max 100).
- **SQL Injection Defense**: Reject arbitrary sorting expressions or raw SQL fragments; query parameters map to explicit typed model fields.

---

## 5. Dispute Detail Observability View (`GET /api/dashboard/disputes/{dispute_id}`)

Provides a complete 360-degree detail representation combining 10 distinct sections:
1. `dispute`: Core financial identity (`dispute_id`, `payment_id`, `amount`, `currency`, `status`, `phase`, `respond_by`).
2. `evidence`: Document counts, document types, file sizes, hashes, processing states, failure messages.
3. `matching`: Total match counts, status breakdown (`MATCH`, `MISMATCH`, `MISSING`, `AMBIGUOUS`, `UNVERIFIABLE`, `CROSS_DOCUMENT_CONFLICT`).
4. `policy`: Decision (`ELIGIBLE`, `HUMAN_REVIEW`, `NOT_ELIGIBLE`), policy version, critical findings.
5. `contest_draft`: Draft ID, status, review status (`PENDING_REVIEW`, `APPROVED`, `REJECTED`), input fingerprint.
6. `preflight`: Preflight status (`READY`, `BLOCKED`), blocking reasons, warnings.
7. `submission`: Submission ID, state (`SUBMITTED`, `FAILED`, `UNKNOWN`), timestamps, failure category.
8. `razorpay_lifecycle`: Latest Razorpay status, phase, local lifecycle status, final outcome (`WON`, `LOST`).
9. `timeline`: Chronological event log of dispute lifecycle events.
10. `alerts`: Active operational alerts detected for this dispute.

---

## 6. Evidence Monitoring

- Tracks evidence upload and processing status across `INGESTED`, `RUST_PARSED`, `AI_EXTRACTED`, and `FAILED`.
- Does NOT expose raw file binaries or trigger re-extraction.

---

## 7. Matching Monitoring

- Displays evaluation results per fact rule without re-running matcher.

---

## 8. Policy Monitoring

- Displays existing `PolicyResult` decision and findings without re-executing policy rules.

---

## 9. Draft Monitoring

- Observes `ContestDraft` status and human review status (`PENDING_REVIEW`, `APPROVED`, `REJECTED`).

---

## 10. Preflight Monitoring

- Observes preflight gate state (`READY` vs. `BLOCKED`) and blocking reasons.

---

## 11. Submission Monitoring

- Displays transmission state (`SUBMITTED`, `FAILED`, `UNKNOWN`) and submission attempt metadata.

---

## 12. Reconciliation Required Monitoring (`GET /api/dashboard/reconciliation-required`)

- Dedicated view listing submissions in `UNKNOWN` state that require status reconciliation.
- **Informational only**: Dashboard does NOT auto-trigger reconciliation.

---

## 13. Lifecycle Monitoring & Action Required (`GET /api/dashboard/action-required`)

- Dedicated view listing disputes in Razorpay `action_required` state.
- Highlights response deadlines (`respond_by`) and current evidence availability.

---

## 14. Outcome Monitoring (`GET /api/dashboard/outcomes`)

- Breakdown of `WON`, `LOST`, `UNDER_REVIEW`, `PENDING`, `UNKNOWN` outcomes.
- Treats `WON` and `LOST` as terminal outcomes per Task 5.5.

---

## 15. Operational Alert System (`GET /api/dashboard/alerts`)

Deterministic alert codes:
- `SUBMISSION_UNKNOWN`: Submissions stuck in `UNKNOWN` state.
- `SUBMISSION_IN_PROGRESS_TOO_LONG`: Submissions locked in `SUBMISSION_IN_PROGRESS`.
- `PENDING_HUMAN_REVIEW`: Drafts awaiting merchant review.
- `PRECHECK_BLOCKED`: Preflights in `BLOCKED` state.
- `EVIDENCE_PROCESSING_FAILED`: Document processing failures.
- `POLICY_NOT_ELIGIBLE`: Policy evaluated as ineligible.
- `RAZORPAY_ACTION_REQUIRED`: Razorpay action requested.

---

## 16. Security & Credential Safety

- All responses are passed through `_sanitize_metadata` to scrub any API keys, secrets, authorization headers, or credentials.

---

## 17. Financial Safety Invariant

- Pre-execution and post-execution assertions verify `Dispute.payment_id`, `amount`, and `currency` are 100% untouched.

---

## 18. Performance Optimization

- Uses eager loading (`selectinload` / `joinedload`) and aggregate SQL queries (`COUNT(DISTINCT ...)`) to eliminate N+1 queries.
- Bounded page sizes prevent memory exhaustion.

---

## 19. API Contracts Summary

- `GET /api/dashboard/summary` $\rightarrow$ `DashboardSummary`
- `GET /api/dashboard/disputes` $\rightarrow$ `DisputeListResponse`
- `GET /api/dashboard/disputes/{dispute_id}` $\rightarrow$ `DisputeDashboardDetail`
- `GET /api/dashboard/alerts` $\rightarrow$ `List[OperationalAlert]`
- `GET /api/dashboard/reconciliation-required` $\rightarrow$ `List[ReconciliationRequiredItem]`
- `GET /api/dashboard/action-required` $\rightarrow$ `List[ActionRequiredItem]`
- `GET /api/dashboard/outcomes` $\rightarrow$ `OutcomeSummary`

---

## 20. Static Architectural Audit Verification

- [x] ZERO `POST`, `PATCH`, `PUT`, `DELETE` Razorpay calls.
- [x] ZERO `submit_contest()`, `accept_dispute()`, `reject_dispute()`, `issue_refund()`.
- [x] `dashboard_service.py` does NOT import `RazorpayClient` or `HttpContestSubmissionClient`.
- [x] Zero direct network calls from dashboard.

---

## 21. Read-Only Guarantees

- All dashboard endpoints are `GET` only.
- Local DB records are queried read-only without state mutations.

---

## 22. Testing Summary

- **Task 6.1 Unit Tests**: 17 test methods (covering 38 required scenarios) passed.
- **Task 6.1 E2E Integration Tests**: 2 test methods passed.
- **Full Project Regression Suite**: **550 / 550 tests passed (100% Green)**.

---

## 23. Known Limitations & Future Extensions

1. **Mock Setup in Tests**: E2E tests use local test DB and mock clients; production utilizes live database connections.
2. **Real-Time WebSockets**: Future frontend iterations can stream dashboard metrics via WebSockets or Server-Sent Events.

---

## 24. Final Task Status Declaration

PHASE 6 TASK 6.1 — DISPUTE LIFECYCLE DASHBOARD & OPERATIONAL MONITORING COMPLETE — VERIFIED.
