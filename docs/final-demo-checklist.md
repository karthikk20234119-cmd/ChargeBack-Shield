# 📋 Final Hackathon Demo Checklist — Chargeback Shield

**Date:** September 4, 2026  
**Status:** Frozen & Verified for Presentation

---

## Pre-Demo Verification Checklist

### 1. Environment & Dependencies
- [x] Python 3.11 environment active (`.\venv\Scripts\Activate.ps1`).
- [x] Node.js environment active (Node v20+ / npm 10+).
- [x] `.env` file present with valid `GROQ_API_KEY` and `GROQ_MODEL=qwen/qwen3.8-27b`.
- [x] `.env` contains safe test credentials for Razorpay (`RAZORPAY_KEY_ID=rzp_test_...`).

### 2. Services & Servers
- [x] **Backend Server:** Running FastAPI on `http://127.0.0.1:8000` (`uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload`).
- [x] **Frontend Server:** Running Vite React dev server on `http://localhost:3000` (`npm run dev`).
- [x] Health check returning `200 OK` at `http://127.0.0.1:8000/api/health`.

### 3. Database & Demo Data Reset
- [x] Executed database reset command to restore clean `demo-dispute-001` fixture.
- [x] Synthetic demo dispute (`demo-dispute-001`, ₹2,500.00 INR) loaded in clean `DISPUTE_CREATED` initial state.

### 4. Browser & Display
- [x] Chrome browser open in fullscreen mode (100% zoom).
- [x] Navigated to `http://localhost:3000/overview` or `http://localhost:3000/presentation`.
- [x] Browser developer console cleared (0 errors).

### 5. Network & API Connectivity
- [x] Groq Cloud API connectivity verified (1.33s latency on `qwen/qwen3.8-27b`).
- [x] Razorpay client operating in isolated mock/test environment mode.

### 6. Security Safeguards
- [x] Verified zero secret keys printed in terminal logs.
- [x] Verified zero API keys rendered in browser inspect element / frontend bundle.
- [x] Webhook signature verification active.

---

## Application State Reset Procedure (Before Each Presentation)

```powershell
# Run in PowerShell from workspace root to restore clean demo database state
$env:PYTHONPATH='.'; .\venv\Scripts\python.exe -c "
import asyncio
from backend.app.database import engine, Base
async def reset():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print('DATABASE RESET COMPLETE: Clean demo state restored.')
asyncio.run(reset())
"
```

---

## Backup Artifact Locations
- Audit & Consistency Report: `brain/8e824414-4cd8-46fb-a51a-67ae49fd4ca9/repository_audit_report.md`
- Evidence Verification Report: `brain/8e824414-4cd8-46fb-a51a-67ae49fd4ca9/final_evidence_verification_report.md`
- Judge Readiness Audit: `brain/8e824414-4cd8-46fb-a51a-67ae49fd4ca9/final_judge_readiness_audit.md`
- Evaluation Harness Report: `evaluation/report.md`
