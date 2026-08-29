# Chargeback Shield — Hackathon Demo Operational Checklist

## Pre-Demo Preparation Checklist

- [x] Docker containers active: `docker compose ps` (Backend, Frontend, Proxy all `healthy`).
- [x] Health checks passing: `curl http://localhost:8000/api/health/ready` returns `HEALTHY`.
- [x] Browser tabs opened:
  - Presentation Deck: `http://localhost:5173/presentation`
  - Demo Guide: `http://localhost:5173/demo`
  - Human Review Workspace: `http://localhost:5173/review`
  - Operations & SLA Center: `http://localhost:5173/operations`
  - Executive Analytics: `http://localhost:5173/analytics`
  - System Observability: `http://localhost:5173/observability`
- [x] Zero live credentials or secrets displayed in UI or browser console.

---

## Live Demonstration Steps

1. **Slide Deck Intro (`/presentation`)**: Present problem (manual dispute handling latency, revenue loss) and architecture.
2. **Dispute & Evidence Ingestion (`/demo` - Stages 1-4)**: Demonstrate secure document upload, magic-byte validation, and fact extraction.
3. **Deterministic Matching & Policy Engine (`/demo` - Stages 5-7)**: Show evidence-to-reason-code matching and policy recommendations.
4. **Explainable Contest Draft (`/demo` - Stage 8)**: Show generated draft with factual arguments and evidence citations.
5. **Human Review Workspace (`/review`)**: Demonstrate reviewer approval/rejection with CAS locking.
6. **Preflight Authorization & Controlled Submission Boundary (`/demo` - Stages 10-12)**: Show preflight READY checks and mock submission.
7. **UNKNOWN State Safety (`/demo` - Stage 13)**: Explain timeout handling and non-retry rule.
8. **Operations & SLA Command Center (`/operations`)**: Show SLA deadlines, exception queues, and non-mutating alert acknowledgements.
9. **Executive Analytics & Compliance Audit (`/analytics`, `/audit`)**: Show outcome funnels and SHA-256 export hash.
10. **System Observability (`/observability`)**: Highlight realtime P50/P95/P99 latency metrics and zero secret exposure.

---

## SAFETY MANDATE — NEVER DEMONSTRATE:
- Live unauthorized Razorpay contest submissions.
- Automatic dispute acceptance/rejection or refunds.
- Unsanitized credentials or secret keys.
- Blind UNKNOWN state retries.
