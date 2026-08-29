# Phase 8 Task 8.2 — Docker, Reverse Proxy & Production Deployment Architecture

## Executive Summary

Phase 8 Task 8.2 containerizes the completed Chargeback Shield platform and establishes a production-grade deployment architecture for the React frontend, FastAPI backend, SQLite database, evidence storage, and NGINX reverse proxy.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> `"CONTAINERIZE → ISOLATE → SECURE → HEALTH-CHECK → DEPLOY → NEVER BYPASS APPLICATION CONTROLS"`

---

## 1. Deployment Architecture & Network Topology

```
Internet
   | (HTTP / HTTPS: Port 80/443)
   v
Reverse Proxy (NGINX: chargeback-shield-proxy)
   |
   +-------------------+-------------------+
   | (Internal Port 80)| (Internal Port 8000)
   v                   v
Frontend            Backend API
React/Vite          FastAPI (chargeback-shield-backend)
                       |
              +--------+--------+
              |                 |
              v                 v
           Database       Evidence Storage
         (Volume: db-data) (Volume: evidence-data)
```

- **Network Isolation**: All services operate on the internal `chargeback-shield-network` (bridge).
- **Zero Host Exposure**: Backend (port 8000) and frontend (port 80) internal ports are NOT published to the host network. Only the NGINX reverse proxy exposes public ports.

---

## 2. Container Specifications

### Backend Container (`backend/Dockerfile`)
- **Base Image**: `python:3.11-slim` with system processing libraries (`poppler-utils`, `tesseract-ocr`, `curl`).
- **Non-Root Runtime**: Operates under system user `appuser` (UID 1000).
- **ASGI Server**: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 2`.
- **Healthcheck**: `curl -f http://localhost:8000/api/health || exit 1`.

### Frontend Container (`frontend/Dockerfile`)
- **Multi-Stage Build**:
  - Stage 1 (Builder): `node:20-alpine`, runs `npm run build`.
  - Stage 2 (Runner): `nginx:alpine-slim`, serves static assets via unprivileged NGINX (`frontend/nginx.conf`).
- **Healthcheck**: `wget -qO- http://localhost:80/ || exit 1`.

### Reverse Proxy (`deploy/nginx/nginx.conf`)
- Routes static SPA `/` to `frontend:80` and API `/api/` to `backend:8000`.
- Propagates `X-Request-ID`, `X-Real-IP`, and `X-Forwarded-For`.
- Enforces `client_max_body_size 15M` upload limit.
- Enforces security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`).

---

## 3. Persistent Volumes & Data Strategy

- **`chargeback-shield-evidence`**: Mounted at `/app/storage/evidence` for evidence document uploads.
- **`chargeback-shield-processed`**: Mounted at `/app/storage/processed` for OCR/extracted evidence artifacts.
- **`chargeback-shield-db`**: Mounted at `/app/data` for persistent SQLite database files.

---

## 4. Verification & Audit Results

### 1. Docker CLI & Compose Config Validation
```powershell
docker --version
docker compose config
```
- **Result**: `Docker version 29.5.2` verified. Compose configuration validated cleanly with 0 syntax or YAML errors.

### 2. Frontend Production Build
```powershell
cd frontend
npm run build
```
- **Result**: `dist/` production bundle compiled in 4.58s with **0 TypeScript errors**.

### 3. Container Security & Deployment Smoke Test Suites
```powershell
.\venv\Scripts\python.exe -m pytest backend/tests/security/test_container_security.py tests/deployment/test_deployment_smoke.py -v
```
- **Result**: **8 / 8 PASSED**.

### 4. Full Backend Regression Suite
```powershell
.\venv\Scripts\python.exe -m pytest backend/tests/ tests/deployment/ -v
```
- **Result**: **`648 / 648 passed (100% Green)`** (640 baseline + 8 new deployment security tests).

---

## 5. Final Status Declaration

"PHASE 8 TASK 8.2 — DOCKER, REVERSE PROXY & PRODUCTION DEPLOYMENT ARCHITECTURE COMPLETE — VERIFIED."
