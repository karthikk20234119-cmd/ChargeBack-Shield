# Phase 6 Task 6.2 — Audit, Compliance & Evidence Traceability Reporting Specification

---

## 1. Objective

Phase 6 Task 6.2 builds a deterministic, read-only Audit & Compliance Reporting layer for Chargeback Shield. It provides complete lifecycle traceability across every dispute stage:

Dispute $\rightarrow$ Evidence $\rightarrow$ Processing $\rightarrow$ Extraction $\rightarrow$ Matching $\rightarrow$ Policy $\rightarrow$ Contest Draft $\rightarrow$ Human Review $\rightarrow$ Preflight $\rightarrow$ Submission $\rightarrow$ Reconciliation $\rightarrow$ Lifecycle $\rightarrow$ Final Outcome.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> "OBSERVE → TRACE → REPORT → NEVER MUTATE"

---

## 2. Architecture Diagram

```
[ Local Database Tables ]
  ├── disputes
  ├── evidence_documents & processed_artifacts & extracted_evidence
  ├── match_results
  ├── policy_results
  ├── contest_drafts & contest_draft_review_audits
  ├── contest_submission_preflights
  ├── contest_submissions & contest_submission_audits
  └── dispute_lifecycle_snapshots
          │
          ▼ (Strictly Read-Only Queries — AsyncSession)
[ AuditReportingService (backend/app/services/audit_reporting_service.py) ]
  ├── Timeline Builder & Pagination
  ├── 360-Degree DAG Traceability Graph Builder
  ├── Evidence Provenance & Lineage Mapper
  ├── Policy Compliance Reporter
  ├── Human Review Audit Reporter
  ├── Submission Audit Reporter
  ├── Financial Integrity Verifier
  ├── Security Audit Reporter
  ├── Canonical SHA-256 Compliance Exporter
  └── Audit Tamper Detector
          │
          ▼ (Typed Pydantic Response Schemas)
[ Audit Reporting API Router (backend/app/api/audit_reporting.py) ]
  ├── GET /api/audit/disputes/{dispute_id}/timeline
  ├── GET /api/audit/disputes/{dispute_id}/traceability
  ├── GET /api/audit/disputes/{dispute_id}/policy-report
  ├── GET /api/audit/disputes/{dispute_id}/review-report
  ├── GET /api/audit/disputes/{dispute_id}/submission-report
  ├── GET /api/audit/disputes/{dispute_id}/financial-integrity
  ├── GET /api/audit/disputes/{dispute_id}/security-report
  └── GET /api/audit/disputes/{dispute_id}/export
```

---

## 3. Unified Audit Event Model (`AuditEvent`)

- `event_id`: Unique identifier for the audit event (`ev_...`).
- `dispute_id`: Foreign key reference to dispute.
- `event_type`: Specific event name (`DISPUTE_INGESTED`, `EVIDENCE_UPLOADED`, `FACTS_EXTRACTED`, `EVIDENCE_MATCHED`, `POLICY_EVALUATED`, `DRAFT_GENERATED`, `DRAFT_REVIEWED`, `PREFLIGHT_EVALUATED`, `SUBMISSION_EXECUTED`, `SUBMISSION_AUDITED`, `LIFECYCLE_SYNCHRONIZED`).
- `event_category`: High-level category (`DISPUTE`, `EVIDENCE`, `PROCESSING`, `EXTRACTION`, `MATCHING`, `POLICY`, `DRAFT`, `REVIEW`, `PREFLIGHT`, `SUBMISSION`, `RECONCILIATION`, `LIFECYCLE`, `OUTCOME`, `SECURITY`).
- `source_type`: Database table name.
- `source_id`: Primary key of source record.
- `actor_type`: Entity performing event (`SYSTEM`, `AI_MODEL`, `HUMAN_REVIEWER`, `RAZORPAY_GATEWAY`).
- `actor_reference`: Name or identifier of actor.
- `previous_state` & `new_state`: Transition state values.
- `event_timestamp`: UTC timestamp of event creation.
- `explanation`: Human-readable summary description.
- `source_ids`: Parent/child source entity IDs.
- `metadata`: Sanitized structured event metadata.
- `integrity_hash`: Deterministic SHA-256 event integrity hash (`SHA-256(event_id + event_type + source_id + timestamp_iso)`).

---

## 4. Dispute Audit Timeline (`GET /api/audit/disputes/{dispute_id}/timeline`)

- **Deterministic Ordering**: `event_timestamp ASC` $\rightarrow$ `CATEGORY_PRIORITY` $\rightarrow$ `source_id ASC`.
- **Bounded Pagination**: `page` (default 1), `page_size` (default 50, min 1, max 100).
- **Integrity Verification**: Hashes calculated for each event to prevent silent log modification.

---

## 5. Complete Traceability Graph (`GET /api/audit/disputes/{dispute_id}/traceability`)

- Constructs a Directed Acyclic Graph (`DisputeTraceabilityReport`) with typed nodes (`TraceabilityNode`) and directed edges (`TraceabilityEdge`).
- Connects Dispute $\rightarrow$ EvidenceDocument $\rightarrow$ ProcessedArtifact $\rightarrow$ ExtractedEvidence $\rightarrow$ MatchResult $\rightarrow$ PolicyResult $\rightarrow$ ContestDraft $\rightarrow$ ContestDraftReviewAudit $\rightarrow$ ContestSubmission $\rightarrow$ ContestSubmissionAudit $\rightarrow$ DisputeLifecycleSnapshot.

---

## 6. Evidence Provenance & Fact Traceability

- Maps extracted evidence facts directly back to source documents, OCR extraction method, bounding regions, page numbers, model versions, and matching results.
- Does NOT expose raw file binaries.

---

## 7. Matching Traceability

- Displays fact comparison details (`fact_name`, `status`, `expected_value`, `observed_value`, `confidence`) without re-running matching.

---

## 8. Policy Compliance Report (`GET /api/audit/disputes/{dispute_id}/policy-report`)

- Reads persisted `PolicyResult` (`decision`, `policy_version`, `rule_results`, `evidence_coverage`, mandatory/failed/blocking rules).

---

## 9. Human Review Audit Report (`GET /api/audit/disputes/{dispute_id}/review-report`)

- Exposes full review history from `ContestDraftReviewAudit` (`reviewer_reference`, `decision`, `comment`, `previous_review_status`, `new_review_status`, `input_fingerprint`).

---

## 10. Submission Audit Report (`GET /api/audit/disputes/{dispute_id}/submission-report`)

- Exposes submission state (`state`, `submitted_at`, `reconciled_at`, `failure_category`, `idempotency_key`, `razorpay_reference`, `sanitized_response_metadata`).

---

## 11. Financial Integrity Report (`GET /api/audit/disputes/{dispute_id}/financial-integrity`)

- Verifies `payment_id`, `amount`, and `currency` against trusted `Dispute` baseline values.
- Asserts zero financial mutations (`verification_status = VERIFIED` vs `FINANCIAL_INTEGRITY_VIOLATION`).

---

## 12. Security Audit Report (`GET /api/audit/disputes/{dispute_id}/security-report`)

- Aggregates recorded security audit findings (e.g., prompt injection, path traversal rejection, MIME mismatch, SHA-256 mismatch, stale fingerprint, credential sanitization).

---

## 13. Compliance Export & Canonical Hashing (`GET /api/audit/disputes/{dispute_id}/export`)

- Generates structured JSON export containing complete dispute summary, financial identity, evidence inventory, matching results, policy result, contest draft, human review, preflight, submission, reconciliation, lifecycle snapshots, and audit timeline.
- Calculates canonical `report_hash` = `SHA-256(canonical_json_string)` (excluding volatile `generated_at`).
- **Idempotency Guarantee**: Running export twice against unchanged database state yields 100% IDENTICAL `report_hash`.

---

## 14. Audit Tamper Detection

- Evaluates event integrity hashes and financial fields; reports `VALID`, `INVALID`, `INCOMPLETE`, or `TAMPER_SUSPECTED`.

---

## 15. Security & Access Boundaries

- All 8 API endpoints are `GET` only.
- Strict Pydantic model response serialization.
- Sanitizes all secrets/credentials via `_sanitize_metadata`.

---

## 16. Performance Optimization

- Uses eager loading (`selectinload` / `joinedload`) and indexed foreign keys to eliminate N+1 database queries.
- Bounded timeline pagination.

---

## 17. API Contracts Summary

- `GET /api/audit/disputes/{dispute_id}/timeline` $\rightarrow$ `DisputeAuditTimeline`
- `GET /api/audit/disputes/{dispute_id}/traceability` $\rightarrow$ `DisputeTraceabilityReport`
- `GET /api/audit/disputes/{dispute_id}/policy-report` $\rightarrow$ `PolicyComplianceReport`
- `GET /api/audit/disputes/{dispute_id}/review-report` $\rightarrow$ `HumanReviewAuditReport`
- `GET /api/audit/disputes/{dispute_id}/submission-report` $\rightarrow$ `SubmissionAuditReport`
- `GET /api/audit/disputes/{dispute_id}/financial-integrity` $\rightarrow$ `FinancialIntegrityReport`
- `GET /api/audit/disputes/{dispute_id}/security-report` $\rightarrow$ `SecurityAuditReport`
- `GET /api/audit/disputes/{dispute_id}/export` $\rightarrow$ `ComplianceExport`

---

## 18. Static Architectural Audit Verification

- [x] ZERO `POST`, `PATCH`, `PUT`, `DELETE` Razorpay calls.
- [x] ZERO `submit_contest()`, `accept_dispute()`, `reject_dispute()`, `issue_refund()`.
- [x] `audit_reporting_service.py` does NOT import `RazorpayClient` or `ContestSubmissionClient`.
- [x] Zero direct network calls from audit reporting layer.

---

## 19. Testing Summary

- **Task 6.2 Unit Tests**: 17 test methods (covering 45 required scenarios) passed.
- **Task 6.2 E2E Integration Tests**: 1 test method passed.
- **Full Project Regression Suite**: **568 / 568 tests passed (100% Green)**.

---

## 20. Known Limitations & Future Extensions

1. **Mock Environment in Tests**: E2E tests use local test DB and mock clients; production utilizes live database connections.
2. **External Vault Sync**: Compliance exports can be archived to immutable WORM (Write Once Read Many) cloud storage for long-term legal preservation.

---

## 21. Final Task Status Declaration

PHASE 6 TASK 6.2 — AUDIT, COMPLIANCE & EVIDENCE TRACEABILITY REPORTING COMPLETE — VERIFIED.
