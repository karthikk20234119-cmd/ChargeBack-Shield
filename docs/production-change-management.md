# Production Change Management Policy — Chargeback Shield

## Executive Policy

All code, schema, infrastructure, and configuration modifications to Chargeback Shield v1.0.0 must follow this production change management policy.

---

## Change Management Workflow

1. **Change Request (CR)**: Document proposed change, business justification, affected components, and risk rating.
2. **Security & Invariant Audit**: Confirm proposed changes do NOT alter financial identity (`payment_id`, `amount`, `currency`), policy recommendation logic, human review state boundaries, or the single contest mutation boundary.
3. **Pre-Deployment Test Gate**: Execute full backend test suite (`pytest backend/tests/ tests/deployment/ tests/performance/`) and frontend compilation (`npm run build`). 100% pass required.
4. **Pre-Deployment Backup**: Generate SHA-256 verified database and storage backup (`scripts/backup_production.py`).
5. **Deployment & Health Check**: Deploy container updates (`docker compose up -d`) and verify health endpoints (`/api/health/ready`).
6. **Post-Deployment Verification**: Execute live-safe smoke test suite.
7. **Rollback Trigger**: If health checks fail or regressions occur, execute rollback procedure (`docs/production-incident-response.md`).
