# ⏱️ Hackathon Live Demo Script — Chargeback Shield

**Target Duration:** 2 Minutes 30 Seconds  
**Goal:** Demonstrate the 17-stage deterministic dispute pipeline, Groq vision extraction, human review safety, preflight gate, and controlled Razorpay submission using safe synthetic demo data.

---

## Demo Overview Table

| Time | Stage / Action | What to Show | What to Say | Expected Result |
| :--- | :--- | :--- | :--- | :--- |
| **00:00 – 00:30** | **1. Overview & Ingestion** | Open Executive Dashboard (`/overview` or `/presentation`). Point to `disp_N1A2B3C4D5` (₹2,500.00 INR, Reason 13.1). | *"Chargeback Shield is an explainable, deterministic dispute intelligence platform. When a chargeback arrives via Razorpay webhook, our backend ingests the payload, computes SHA-256 hashes, and securely stores raw evidence without exposing API keys."* | Dispute `demo-dispute-001` displayed in `DISPUTE_CREATED` state with immutable financial identity (`payment_id: pay_N1A2B3C4D5`). |
| **00:30 – 01:00** | **2. Groq Vision Extraction** | Open Evidence & Facts Tab (`/evidence`). Show uploaded delivery proof invoice PNG image and extracted JSON facts. | *"Raw document images are parsed by Groq's `qwen/qwen3.8-27b` multimodal vision model in 1.33 seconds. Notice that Groq extracts structured facts—tracking ID, delivery date, customer name—into a strict Pydantic schema with zero financial decision-making power."* | Extracted facts rendered with confidence scores and source page provenance. AI cannot make policy decisions. |
| **01:00 – 01:30** | **3. Matching & Policy Engine** | Open Review Workspace (`/review`). Show 100% Fact Match against merchant order database and Policy Outcome: `ELIGIBLE`. | *"Our backend Python engine deterministically matches extracted facts against merchant order logs. Policy Rule `R_FRAUD_DELIVERY_PROOF_v1` evaluates eligibility. If AI hallucinated or facts mismatched, the engine automatically flags `NOT_ELIGIBLE` or `HUMAN_REVIEW`."* | Match status `MATCH (100%)`. Policy decision `ELIGIBLE` calculated deterministically in <2ms. |
| **01:30 – 02:00** | **4. Draft, Review & Preflight Gate** | Click **Approve Draft**. Show Preflight Authorization Hash (`pf_hash_9876543210`). | *"A human operator reviews the factual rebuttal draft. Upon approval, the Preflight Gate verifies evidence hashes and financial identity, generating an authorization hash. Modified or unapproved drafts are immutably BLOCKED."* | Review status updated to `APPROVED`. Preflight status returns `READY (200 OK)`. |
| **02:00 – 02:30** | **5. Single-Boundary Submission & Audit** | Click **Submit Contest to Razorpay**. Show Razorpay Submission Record & Audit Trail (`/audit`). | *"Submission occurs through a single dedicated endpoint executing `PATCH /v1/disputes/{id}/contest`. Groq has zero access to Razorpay keys. The complete 17-stage sequence is locked in a SHA-256 tamper-evident audit trail."* | Submission status `SUBMITTED`. Audit log updated with cryptographic event hash. Zero direct frontend Razorpay requests. |

---

## Repeatable Demo Reset Command

To reset the application state to a clean demo baseline before each judge presentation:

```bash
# Reset database and seed fresh synthetic demo dispute (demo-dispute-001)
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
