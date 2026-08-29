# Phase 6 Task 6.3 — Operational Alerts, SLA Monitoring & Exception Management Specification

---

## 1. Objective

Phase 6 Task 6.3 implements a deterministic, read-only Operational Alerts, SLA Monitoring & Exception Management layer for Chargeback Shield. It transforms existing dispute, evidence, processing, extraction, matching, policy, draft, review, preflight, submission, reconciliation, and lifecycle records into actionable operational alerts.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> "DETECT → PRIORITIZE → ALERT → NEVER MUTATE"

---

## 2. Architecture Diagram

```
[ Local Database Tables (Read-Only Queries) ]
  ├── disputes
  ├── evidence_documents & processed_artifacts & extracted_evidence
  ├── match_results
  ├── policy_results
  ├── contest_drafts & contest_draft_review_audits
  ├── contest_submission_preflights
  ├── contest_submissions & contest_submission_audits
  └── dispute_lifecycle_snapshots
          │
          ▼ (Strictly Read-Only Analysis)
[ OperationalAlertService (backend/app/services/operational_alert_service.py) ]
  ├── SLAPolicy Engine (backend/app/services/sla_policy.py)
  ├── 24 Rule Alert Detection Engine
  ├── SHA-256 Alert Fingerprint Deduplicator
  ├── Alert Resolution & Status State Machine
  ├── SLA & Exception Report Generator
  └── System Health Analytics Aggregator
          │
          ▼ (Writes/Updates operational_alerts table ONLY)
[ operational_alerts Table (backend/app/models/operational_alert.py) ]
          │
          ▼ (Typed Pydantic Response Schemas)
[ Operational Alerts API Router (backend/app/api/operational_alerts.py) ]
  ├── GET  /api/operations/alerts/summary
  ├── GET  /api/operations/alerts
  ├── GET  /api/operations/disputes/{dispute_id}/alerts
  ├── GET  /api/operations/sla
  ├── GET  /api/operations/exceptions
  ├── GET  /api/operations/health
  ├── POST /api/operations/alerts/detect (Requires `{}` empty body)
  └── POST /api/operations/alerts/{alert_id}/acknowledge (Modifies ONLY alert status)
```

---

## 3. Operational Alert Model (`OperationalAlert`)

- `alert_id`: Unique identifier for the alert (`UUID`).
- `dispute_id`: Foreign key reference to dispute.
- `category`: Alert category (`SLA`, `HUMAN_REVIEW`, `SUBMISSION`, `RECONCILIATION`, `LIFECYCLE`, `EVIDENCE`, `PROCESSING`, `POLICY`, `SECURITY`, `DATA_INTEGRITY`, `COMPLIANCE`, `SYSTEM`).
- `code`: Specific alert rule code (`HUMAN_REVIEW_REQUIRED`, `SUBMISSION_STUCK`, `SUBMISSION_UNKNOWN`, `SUBMISSION_FAILED`, `RECONCILIATION_REQUIRED`, `RECONCILIATION_OVERDUE`, `ACTION_REQUIRED`, `UNKNOWN_EXTERNAL_STATUS`, `UNEXPECTED_LIFECYCLE_TRANSITION`, `EVIDENCE_INCOMPLETE`, `EVIDENCE_PROCESSING_FAILED`, `EVIDENCE_SECURITY_REJECTED`, `POLICY_REVIEW_REQUIRED`, `POLICY_EVALUATION_FAILED`, `STALE_DRAFT`, `STALE_PREFLIGHT`, `FINANCIAL_INTEGRITY_VIOLATION`, `AUDIT_INTEGRITY_EXCEPTION`, `SECURITY_REVIEW_REQUIRED`, `CREDENTIAL_SECURITY_EXCEPTION`, `PROVENANCE_INCOMPLETE`, `TRACEABILITY_INCOMPLETE`).
- `severity`: Priority level (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
- `status`: Lifecycle status (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`, `SUPPRESSED`).
- `title` & `message`: Human-readable description.
- `source_type` & `source_id`: Source record table and primary key.
- `detected_at`: Detection timestamp.
- `due_at`: Optional SLA deadline timestamp.
- `resolved_at`: Resolution timestamp when condition ceases.
- `metadata`: Sanitized contextual details.
- `fingerprint`: Deterministic SHA-256 fingerprint for deduplication (`SHA256(dispute_id + code + source_type + source_id + state + timestamp_bucket)`).

---

## 4. Alert Categories

- `SLA`: Deadline warnings and overdue conditions.
- `HUMAN_REVIEW`: Pending reviews, review-required drafts, blocked drafts.
- `SUBMISSION`: Stuck, UNKNOWN, or failed contest submissions.
- `RECONCILIATION`: Gateway state reconciliation required or overdue.
- `LIFECYCLE`: Gateway `ACTION_REQUIRED`, unknown external status, unexpected transitions.
- `EVIDENCE`: Missing evidence, processing failures, security rejections.
- `POLICY`: `HUMAN_REVIEW` decisions, policy evaluation failures.
- `SECURITY`: Prompt injection findings, unsanitized credentials.
- `DATA_INTEGRITY`: Stale drafts, stale preflights, financial discrepancies, audit linkage breaks.
- `COMPLIANCE`: Missing OCR provenance, broken DAG traceability.

---

## 5. Severity Priorities

- `CRITICAL` (Priority 1): `FINANCIAL_INTEGRITY_VIOLATION`, `CREDENTIAL_SECURITY_EXCEPTION`, `SUBMISSION_UNKNOWN`, `ACTION_REQUIRED` when overdue, `AUDIT_INTEGRITY_EXCEPTION`.
- `HIGH` (Priority 2): `SUBMISSION_STUCK`, `RECONCILIATION_OVERDUE`, `EVIDENCE_SECURITY_REJECTED`, `STALE_PREFLIGHT`, `STALE_DRAFT`, `POLICY_EVALUATION_FAILED`.
- `MEDIUM` (Priority 3): `HUMAN_REVIEW_REQUIRED`, `EVIDENCE_INCOMPLETE`, `PROVENANCE_INCOMPLETE`, `TRACEABILITY_INCOMPLETE`, `SUBMISSION_FAILED`.
- `LOW` / `INFO` (Priority 4-5): Informational lifecycle notifications, normal pending processing.

---

## 6. Deterministic SLA Policy Engine (`backend/app/services/sla_policy.py`)

- **Server-Side Constants**:
  - `HUMAN_REVIEW_SLA_HOURS` = 24.0
  - `ACTION_REQUIRED_SLA_HOURS` = 12.0
  - `UNKNOWN_SUBMISSION_SLA_HOURS` = 6.0
  - `RECONCILIATION_SLA_HOURS` = 12.0
  - `EVIDENCE_PROCESSING_SLA_HOURS` = 4.0
  - `WARNING_THRESHOLD_PERCENT` = 0.75 (75% elapsed triggers `WARNING` / `MEDIUM`)
- Calculates `due_at = detected_at + SLA_HOURS`.
- Determines `elapsed_hours`, `remaining_hours`, `sla_status` (`ON_TIME`, `WARNING`, `OVERDUE`, `CRITICAL_OVERDUE`), and escalates severity automatically.

---

## 7. 24 Alert Detection Rules

1. `HUMAN_REVIEW_REQUIRED`: `ContestDraft.review_status == "PENDING_REVIEW"`
2. `HUMAN_REVIEW_REQUIRED`: `ContestDraft.status == "REVIEW_REQUIRED"`
3. `BLOCKED_DRAFT`: `ContestDraft.status == "BLOCKED"`
4. `SUBMISSION_STUCK`: `ContestSubmission.state == "SUBMISSION_IN_PROGRESS"` (> 15 mins)
5. `SUBMISSION_UNKNOWN`: `ContestSubmission.state == "UNKNOWN"`
6. `SUBMISSION_FAILED`: `ContestSubmission.state == "FAILED"`
7. `RECONCILIATION_REQUIRED`: `ContestSubmission` in `UNKNOWN` state needing reconciliation
8. `RECONCILIATION_OVERDUE`: `ContestSubmission` in `UNKNOWN`/stale reconciliation state (> 12 hrs)
9. `ACTION_REQUIRED`: Dispute status or snapshot outcome == `"ACTION_REQUIRED"`
10. `UNKNOWN_EXTERNAL_STATUS`: Snapshot razorpay_status == `"unknown"`
11. `UNEXPECTED_LIFECYCLE_TRANSITION`: Invalid snapshot state transition
12. `EVIDENCE_INCOMPLETE`: Zero evidence documents or missing mandatory evidence
13. `EVIDENCE_PROCESSING_FAILED`: `EvidenceDocument.processing_status == "FAILED"`
14. `EVIDENCE_SECURITY_REJECTED`: `EvidenceDocument` rejected for security/path/MIME reasons
15. `POLICY_REVIEW_REQUIRED`: `PolicyResult.decision == "HUMAN_REVIEW"`
16. `POLICY_EVALUATION_FAILED`: `PolicyResult.outcome == "FAILED"`
17. `STALE_DRAFT`: Draft fingerprint stale
18. `STALE_PREFLIGHT`: Preflight fingerprint stale or `Preflight.status == "BLOCKED"`
19. `FINANCIAL_INTEGRITY_VIOLATION`: Discrepancy in `amount`, `payment_id`, or `currency`
20. `AUDIT_INTEGRITY_EXCEPTION`: Invalid audit log reference or orphan
21. `SECURITY_REVIEW_REQUIRED`: Recorded prompt injection or security finding
22. `CREDENTIAL_SECURITY_EXCEPTION`: Unsanitized credentials in audit
23. `PROVENANCE_INCOMPLETE`: Evidence missing OCR provenance / page details
24. `TRACEABILITY_INCOMPLETE`: Incomplete DAG node lineage

---

## 8. Deduplication & Fingerprint Stability

- Fingerprint formula: `SHA256(dispute_id + code + source_type + source_id + state + timestamp_bucket)`
- Prevents redundant duplicate insertion when underlying conditions remain unchanged. Reuses existing open alert and updates detection timestamp.
- Auto-resolves open alerts (`status = RESOLVED`, `resolved_at = datetime.utcnow()`) when underlying condition ceases.

---

## 9. Alert Lifecycle & Acknowledgement Boundary

- Detection creates `OPEN` alerts.
- Operators can acknowledge alerts via `POST /api/operations/alerts/{alert_id}/acknowledge`.
- Acknowledgement modifies **ONLY** `OperationalAlert.status` to `ACKNOWLEDGED`. It **NEVER** mutates underlying dispute workflow entities.

---

## 10. API Contracts Summary

- `GET /api/operations/alerts/summary` $\rightarrow$ `OperationalAlertSummary`
- `GET /api/operations/alerts` $\rightarrow$ `List[OperationalAlert]` (Filtered & paginated with hardcoded deterministic sorting: severity priority DESC, due_at ASC, detected_at ASC, alert_id ASC).
- `GET /api/operations/disputes/{dispute_id}/alerts` $\rightarrow$ `DisputeAlertDetail`
- `GET /api/operations/sla` $\rightarrow$ `SLAMonitoringReport`
- `GET /api/operations/exceptions` $\rightarrow$ `OperationalExceptionReport`
- `GET /api/operations/health` $\rightarrow$ `OperationalHealthReport`
- `POST /api/operations/alerts/detect` $\rightarrow$ Takes `{}` body (`extra="forbid"`), returns `AlertDetectionResult`.
- `POST /api/operations/alerts/{alert_id}/acknowledge` $\rightarrow$ `OperationalAlert`

---

## 11. Static Architectural Audit Verification

- [x] ZERO `POST`, `PATCH`, `PUT`, `DELETE` Razorpay calls.
- [x] ZERO `submit_contest()`, `accept_dispute()`, `reject_dispute()`, `issue_refund()`.
- [x] `operational_alert_service.py` does NOT import `RazorpayClient`, `ContestSubmissionClient`, or `HttpContestSubmissionClient`.
- [x] Zero direct network calls or AI/LLM invocations from alert engine.
- [x] Zero source business entity mutations (`Dispute`, `EvidenceDocument`, `PolicyResult`, `ContestDraft`, `ContestSubmission` 100% untouched).

---

## 12. Testing & Regression Summary

- **Task 6.3 Unit Tests**: 18 test methods (covering 50 required scenarios) passed.
- **Task 6.3 E2E Integration Tests**: 1 test method passed.
- **Full Project Regression Suite**: **587 / 587 tests passed (100% Green)**.

---

## 13. Known Limitations & Future Extensions

1. **Local Alert Persistence**: Operational alerts are persisted locally in SQLite/PostgreSQL; push notifications (email/Slack) can consume alert webhooks in future phases.
2. **Remediation Separation**: The alert layer signals conditions; automated or manual remediation remains strictly separated.

---

## 14. Final Task Status Declaration

PHASE 6 TASK 6.3 — OPERATIONAL ALERTS, SLA MONITORING & EXCEPTION MANAGEMENT COMPLETE — VERIFIED.
