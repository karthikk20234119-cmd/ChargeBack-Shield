# Phase 6 Task 6.4 — Dispute Analytics, Management Reporting & Performance Insights Specification

---

## 1. Objective

Phase 6 Task 6.4 builds a deterministic, read-only analytics and management reporting layer for Chargeback Shield. It transforms persisted dispute, evidence, processing, extraction, matching, policy, draft, review, preflight, submission, reconciliation, lifecycle snapshot, and operational alert records into management-level insights.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> "MEASURE → ANALYZE → REPORT → NEVER MUTATE"

---

## 2. Architecture Diagram

```
[ Persisted Database Records (Read-Only Queries) ]
  ├── disputes
  ├── evidence_documents & processed_artifacts & extracted_evidence
  ├── match_results
  ├── policy_results
  ├── contest_drafts & contest_draft_review_audits
  ├── contest_submission_preflights
  ├── contest_submissions & contest_submission_audits
  ├── dispute_lifecycle_snapshots
  └── operational_alerts
          │
          ▼ (Strictly Read-Only Queries & Aggregation)
[ AnalyticsService (backend/app/services/analytics_service.py) ]
  ├── Date Range Resolver (TODAY, LAST_7_DAYS, LAST_30_DAYS, LAST_90_DAYS, THIS_YEAR, CUSTOM)
  ├── 14 Domain Analytical Functions
  ├── 12-Stage Lifecycle Funnel Analyzer
  ├── Stage Bottleneck Identification Engine
  ├── Failure Matrix Aggregator
  └── Canonical JSON SHA-256 Report Hasher
          │
          ▼ (Typed Pydantic Response Schemas)
[ Analytics REST API Router (backend/app/api/analytics.py) ]
  ├── GET /api/analytics/summary
  ├── GET /api/analytics/outcomes
  ├── GET /api/analytics/evidence
  ├── GET /api/analytics/matching
  ├── GET /api/analytics/policy
  ├── GET /api/analytics/drafts
  ├── GET /api/analytics/submissions
  ├── GET /api/analytics/operations
  ├── GET /api/analytics/sla
  ├── GET /api/analytics/funnel
  ├── GET /api/analytics/bottlenecks
  ├── GET /api/analytics/failures
  ├── GET /api/analytics/security
  ├── GET /api/analytics/financial-integrity
  └── GET /api/analytics/export
```

---

## 3. Data Sources & Read-Only Invariant

- Queries local database tables exclusively.
- **ZERO Razorpay API Calls**: Does NOT import `RazorpayClient`, `ContestSubmissionClient`, or `HttpContestSubmissionClient`.
- **ZERO AI/LLM Calls**: Executes zero model extractions or embeddings.
- **ZERO Database Mutations**: All source entities remain 100% untouched.

---

## 4. Management Summary (`GET /api/analytics/summary`)

Provides executive-level KPI metrics:
- `total_disputes`: Total count of disputes.
- `active_disputes`: Count of open, under review, or action required disputes.
- `won`: Count of won disputes.
- `lost`: Count of lost disputes.
- `pending`: Count of open pending disputes.
- `win_rate`: Percentage of won disputes out of decided disputes (`round((won / (won + lost)) * 100, 2)`).
- `total_evidence_documents`: Count of uploaded evidence files.
- `policy_review_rate`: Percentage of policy evaluations triggering human review.
- `draft_approval_rate`: Percentage of contest drafts approved by merchant reviewers.
- `submission_success_rate`: Percentage of contest submissions successfully submitted to gateway.
- `unknown_submission_count`: Count of contest submissions in `UNKNOWN` state needing reconciliation.
- `critical_alert_count`: Count of active critical operational alerts.
- `reconciliation_required_count`: Count of disputes awaiting status reconciliation.

---

## 5. Outcome Analytics (`GET /api/analytics/outcomes`)

- Breakdown by dispute outcome: `won`, `lost`, `pending`, `under_review`, `action_required`, `unknown`.
- Rates: `win_rate`, `loss_rate`.
- Period Aggregation: Grouped trend breakdown (`daily`, `weekly`, `monthly`).

---

## 6. Evidence Analytics (`GET /api/analytics/evidence`)

- Document counts by processing status (`PROCESSED`, `AI_EXTRACTED`, `FAILED`, `SECURITY_REJECTED`).
- Metrics: `average_documents_per_dispute`, `evidence_completeness_rate`, `processing_success_rate`, `rejection_rate`.

---

## 7. Matching Analytics (`GET /api/analytics/matching`)

- Fact match breakdown across all evaluated fields (`MATCH`, `MISMATCH`, `MISSING`, `AMBIGUOUS`, `CROSS_DOCUMENT_CONFLICT`, `UNVERIFIABLE`, `NOT_COMPARABLE`).
- Rates: `match_success_rate`, `mismatch_rate`, `conflict_rate`.

---

## 8. Policy Analytics (`GET /api/analytics/policy`)

- Decision breakdown (`ELIGIBLE`, `HUMAN_REVIEW`, `NOT_ELIGIBLE`).
- Metrics: `review_rate`, `eligibility_rate`, `policy_failure_rate`, and `rule_failure_distribution`.

---

## 9. Draft & Review Analytics (`GET /api/analytics/drafts`)

- Draft status breakdown (`DRAFT`, `REVIEW_REQUIRED`, `BLOCKED`).
- Human review status breakdown (`PENDING_REVIEW`, `APPROVED`, `REJECTED`).
- Rates: `approval_rate`, `rejection_rate`, `review_pending_rate`.

---

## 10. Submission Analytics (`GET /api/analytics/submissions`)

- State breakdown (`SUBMITTED`, `FAILED`, `UNKNOWN`).
- Rates: `submission_success_rate`, `unknown_rate`, `reconciliation_rate`, and `failure_distribution`.

---

## 11. Operational Alert Analytics (`GET /api/analytics/operations`)

- Alert status & severity breakdown (`OPEN`, `ACKNOWLEDGED`, `CRITICAL`, `HIGH`, `MEDIUM`).
- Counts: `security_alerts`, `compliance_alerts`, `reconciliation_required`.
- Distribution: `alerts_by_category`, `alerts_by_code`.

---

## 12. SLA Performance Analytics (`GET /api/analytics/sla`)

- Metrics: `total_tracked`, `on_time`, `overdue`, `sla_compliance_percentage`, `average_resolution_hours`.

---

## 13. 12-Stage Lifecycle Funnel (`GET /api/analytics/funnel`)

Tracks dispute progression and drop-off count across 12 sequential stages:
1. `disputes_created`
2. `evidence_available`
3. `evidence_processed`
4. `facts_extracted`
5. `matching_completed`
6. `policy_evaluated`
7. `drafts_generated`
8. `drafts_approved`
9. `preflight_ready`
10. `submissions_started`
11. `submissions_confirmed`
12. `outcomes_recorded`

---

## 14. Bottleneck Analysis (`GET /api/analytics/bottlenecks`)

- Identifies stages with highest drop-off counts or pending items.
- Surfaces `primary_bottleneck_stage`, metric value, severity, and explanatory details.

---

## 15. Failure & Security Analytics (`GET /api/analytics/failures`, `GET /api/analytics/security`)

- Stage failure matrix: evidence, extraction, matching conflicts, policy, preflight, submission, reconciliation, and security failures.
- Security findings: prompt injection findings, path traversal attempts, MIME violations, magic-byte failures, hash mismatches, stale fingerprint events, and credential security findings.

---

## 16. Financial Integrity & Export Hashes (`GET /api/analytics/financial-integrity`, `GET /api/analytics/export`)

- Financial checks: Verifies `amount > 0`, `payment_id`, and `currency` consistency across disputes.
- Canonical JSON Export: Combines all analytical domain payloads into a single report and computes a deterministic SHA-256 report hash (`report_hash`). Excludes volatile timestamps to guarantee identical hashes on unchanged DB states.

---

## 17. Static Architectural Audit Verification

- [x] ZERO `POST`, `PATCH`, `PUT`, `DELETE` Razorpay calls.
- [x] ZERO `submit_contest()`, `accept_dispute()`, `reject_dispute()`, `issue_refund()`.
- [x] `analytics_service.py` does NOT import `RazorpayClient`, `ContestSubmissionClient`, or `HttpContestSubmissionClient`.
- [x] Zero direct network calls or AI/LLM invocations from analytics layer.
- [x] Zero source entity mutations (all 13 local database tables 100% untouched).

---

## 18. Testing & Regression Summary

- **Task 6.4 Unit Tests**: 20 test methods (covering 50 required scenarios) passed.
- **Task 6.4 E2E Integration Test**: 1 test method passed.
- **Full Project Regression Suite**: **608 / 608 tests passed (100% Green)**.

---

## 19. Known Limitations

1. **Local Analytics Queries**: Aggregates local SQLite/PostgreSQL tables directly; high-volume production datasets can leverage read-replica databases.
2. **Read-Only Reporting**: The analytics layer surfaces metrics and bottlenecks; automated or manual actions remain strictly separated.

---

## 20. Final Task Status Declaration

PHASE 6 TASK 6.4 — DISPUTE ANALYTICS, MANAGEMENT REPORTING & PERFORMANCE INSIGHTS COMPLETE — VERIFIED.
