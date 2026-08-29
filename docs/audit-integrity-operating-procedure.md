# Audit Integrity Operating Procedure — Chargeback Shield

## Executive Compliance Policy

This operating procedure defines controls for ensuring that all audit records, human review logs, submission histories, and compliance exports in Chargeback Shield remain strictly append-only, tamper-evident, and reproducible.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> `"RECORD → HASH → VERIFY → PRESERVE → NEVER MUTATE OR DELETE"`

---

## 1. Compliance Audit Trail Controls

1. **Append-Only Semantics**:
   - Tables `contest_draft_review_audits`, `contest_submission_audits`, `dispute_lifecycle_snapshots`, and `operational_alerts` permit `INSERT` actions only.
   - Zero `UPDATE` or `DELETE` API endpoints exist for audit records.

2. **Deterministic Compliance SHA-256 Hash**:
   - Compliance reports generated via `/api/audit/disputes/{id}/export` include a SHA-256 hash computed over sorted audit fields.
   - Identical database state produces identical export hashes.

3. **Credential Sanitization in Audit Metadata**:
   - Audit event payloads strip `Authorization`, `Cookie`, `X-Razorpay-Signature`, and `key_secret` strings prior to serialization.

---

## 2. Monthly Audit Verification Routine

1. Run compliance verification script across active disputes.
2. Verify export hash reproducibility for a sample of closed disputes.
3. Confirm `PRAGMA integrity_check;` on database files.
