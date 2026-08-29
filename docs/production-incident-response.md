# Production Incident Response Runbook — Chargeback Shield

## Executive Emergency Procedure

This runbook documents operational procedures for responding to system outages, database degradation, evidence store anomalies, submission timeouts, and UNKNOWN submission states in Chargeback Shield.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> `"OBSERVE → CORRELATE → ISOLATE → RECOVER SAFELY → NEVER MUTATE UNEXPECTEDLY"`

---

## 1. UNKNOWN Contest Submission State Handling

> [!CAUTION]
> **CRITICAL RULE**: `"DO NOT BLINDLY RETRY UNKNOWN SUBMISSIONS"`
> Under network timeouts or gateway connectivity drops, a submission request state remains `UNKNOWN`.
> **DO NOT** click resubmit or issue automatic retry calls.

### Procedure for UNKNOWN State:
1. **Isolate Dispute ID**: Note the `dispute_id` and idempotency key from audit logs.
2. **Execute Read-Only Reconciliation**:
   ```bash
   curl -X POST http://localhost:8000/api/disputes/{dispute_id}/reconcile
   ```
3. **Verify Status**:
   - If Razorpay returned `under_review` or `action_required`, state automatically transitions to `SUBMITTED`.
   - If Razorpay returns 404 / dispute not found, state may be safely set back to `APPROVED` for manual re-attempt.

---

## 2. System Outages & Service Failures

### Scenario A: Backend FastAPI Outage
1. Check Docker logs: `docker compose logs -f backend`
2. Verify container status: `docker compose ps`
3. Restart container: `docker compose restart backend`
4. Verify health gates: `curl http://localhost:8000/api/health/ready`

### Scenario B: Database Connectivity Loss
1. Inspect database file permissions and locks.
2. Run SQLite integrity check:
   ```bash
   sqlite3 /app/data/chargeback_shield.db "PRAGMA integrity_check;"
   ```
3. Restore from latest backup if database corruption is reported (`scripts/verify_backup.py`).

### Scenario C: Evidence Storage Corruption
1. **STOP GO-LIVE / STOP INGESTION**. Do NOT silently touch or repair evidence files.
2. Run hash verification over `storage/evidence/` against stored `sha256_hash` in `evidence_documents`.
3. Restore corrupted evidence artifacts from primary Cloud Storage / offline backup.

---

## 3. Rollback Sequence

1. **Stop Traffic**: Pause NGINX reverse proxy or ingress traffic.
2. **Preserve Current State**: Create instant snapshot of database and log files.
3. **Deploy Previous Release**:
   ```bash
   docker compose down
   docker compose up -d --build
   ```
4. **Verify Health**: Confirm `/api/health/live` returns HTTP 200 OK.
5. **Verify Audit Trail**: Confirm audit records remain 100% intact.
6. **Resume Traffic**: Re-enable NGINX routing.
