# Chargeback Shield — Judging Value Proposition & Key Differentiators

## Executive Summary

Chargeback Shield is a production-grade, human-in-the-loop dispute intelligence and automated contest defense platform built for merchants processing payments on payment gateways like Razorpay.

---

## The Problem
- **Revenue Loss**: Merchants lose 100% of disputed transaction amounts plus chargeback penalty fees when disputes are left uncontested or submitted late.
- **Manual Overhead**: Gathering invoices, shipping tracking logs, customer emails, and gateway payloads manually takes hours per dispute.
- **Human Error & Missed Deadlines**: Disjointed review flows lead to missed submission windows and inconsistent contest responses.

---

## The Chargeback Shield Solution
1. **Automated Evidence Ingestion**: Validates MIME/magic-bytes, extracts structured facts, and indexes documents with SHA-256 hashes.
2. **Deterministic Matching & Policy Engine**: Rule-based matching links evidence to reason codes, producing policy recommendations (`CONTEST`, `ACCEPT`, `NEED_MORE_INFO`).
3. **Explainable Draft Generation**: Generates structured contest drafts linking claims to source evidence documents.
4. **Human Review & CAS Locking**: Human-in-the-loop review workspace enforces approval gates with Compare-And-Swap (CAS) locking.
5. **Controlled Single Mutation Boundary**: `ContestSubmissionClient.submit_contest` is the single submission boundary, preventing unauthorized gateway mutations.
6. **UNKNOWN State Safety**: Network timeouts leave state as `UNKNOWN` for manual read-only reconciliation. Zero blind retries exist.
7. **Operations & SLA Command Center**: Realtime SLA status tracking (`ON_TRACK`, `OVERDUE`) and alert management.
8. **Compliance & Audit Traceability**: Append-only audit logs with reproducible SHA-256 report export hashes.

---

## 10 Key Architectural Differentiators

| Differentiator | Implementation Highlight |
|---|---|
| **1. Deterministic Architecture** | 100% rule-based matching and policy engine. Zero non-deterministic LLM decision risks. |
| **2. Evidence Grounding** | All contest draft factual arguments cite specific extracted evidence document IDs. |
| **3. Human-in-the-Loop** | Clear separation between operational status and human review status (`status` vs `review_status`). |
| **4. Single Mutation Boundary** | `ContestSubmissionClient.submit_contest` verified by AST code parser as the ONLY Razorpay mutation path. |
| **5. UNKNOWN Safety Rule** | Timeout handling requires read-only status reconciliation. Zero automated resubmission retries. |
| **6. Financial Immutability** | `payment_id`, `amount`, and `currency` attributes are strictly immutable across all stages. |
| **7. Complete Provenance** | Every extracted fact maintains source document reference, MIME type, and extraction confidence. |
| **8. Audit Reproducibility** | Compliance reports produce deterministic SHA-256 export hashes over unchanged state. |
| **9. Realtime Observability** | In-memory metric tracking capturing P50/P95/P99 latency percentiles and error categories. |
| **10. Production Readiness** | Multi-stage Docker build, NGINX reverse proxy, automated backup/restore scripts, 698/698 passing tests. |
