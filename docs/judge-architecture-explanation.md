# 🏛️ Architecture Explanation for Judges — Chargeback Shield

**Core Architecture Philosophy:**  
> **"AI extracts facts → Python evaluates policy → Human approves draft → Preflight validates safety → Single boundary submits → System reconciles & audits."**

---

## Simple 5-Layer Component Breakdown

```
[ Unstructured Evidence Image ]
           │
           ▼
┌─────────────────────────────────────────┐
│ 1. AI Fact Extractor (Groq Multimodal)   │ ── Extracts raw facts into Pydantic schema
└─────────────────────────────────────────┘    (Zero decision or financial power)
           │
           ▼
┌─────────────────────────────────────────┐
│ 2. Deterministic Engine (Backend Python)│ ── Matches facts vs merchant DB & evaluates
└─────────────────────────────────────────┘    policy rules (R_FRAUD_DELIVERY_PROOF_v1)
           │
           ▼
┌─────────────────────────────────────────┐
│ 3. Human Review Checkpoint              │ ── Merchant operator inspects factual rebuttal
└─────────────────────────────────────────┘    & approves draft
           │
           ▼
┌─────────────────────────────────────────┐
│ 4. Preflight Authorization Gate          │ ── Verifies SHA-256 preflight hash & blocks
└─────────────────────────────────────────┘    stale/duplicate/unapproved submissions
           │
           ▼
┌─────────────────────────────────────────┐
│ 5. Isolated Submission Boundary         │ ── Executes PATCH /v1/disputes/{id}/contest
└─────────────────────────────────────────┘    (Single dedicated mutation client)
```

---

## 1. Groq Vision Layer = Fact Extraction Only
- **Role:** Converts visual evidence page images (PDFs, PNGs, JPEGs) into structured JSON data.
- **Model:** `qwen/qwen3.8-27b` on Groq Cloud.
- **Safety Boundary:** AI has **zero** access to Razorpay credentials, payment endpoints, or database mutation methods. AI outputs are sanitized before entering the matching pipeline.

## 2. Deterministic Engine = Policy & Eligibility Decision
- **Role:** Compares extracted facts against merchant database records (order ID, buyer IP, delivery timestamp, AWB tracking) and evaluates policy rules.
- **Language:** Pure 100% Python code (`policy_engine_service.py`, `matching_service.py`).
- **Safety Boundary:** If AI fails or data mismatches, decision defaults deterministically to `NOT_ELIGIBLE` or `HUMAN_REVIEW`. AI cannot force an `ELIGIBLE` outcome.

## 3. Human Review = Mandatory Review Checkpoint
- **Role:** Human operator inspects generated rebuttal draft text, factual provenance, and source evidence images.
- **Safety Boundary:** Drafts in `BLOCKED` status cannot be overridden. Operator must explicitly authorize submission.

## 4. Preflight Gate = Cryptographic Safety Gate
- **Role:** Calculates SHA-256 authorization hash over draft ID, financial identity (`payment_id`, `amount`, `currency`), and evidence hashes.
- **Safety Boundary:** Rejects stale, modified, or duplicate submission attempts.

## 5. Razorpay Client = Isolated Mutation Boundary
- **Role:** Executes single approved external API operation: `PATCH /v1/disputes/{dispute_id}/contest`.
- **Safety Boundary:** Implemented in dedicated `ContestSubmissionClient` class. Generic HTTP methods (`post`, `patch`, `put`, `delete`) are strictly forbidden elsewhere in the codebase.
