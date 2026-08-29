# Phase 7 Task 7.2 — Human Review & Evidence Investigation Workspace

## Executive Summary

Phase 7 Task 7.2 delivers a merchant-facing, production-grade **Human Review & Evidence Investigation Workspace** (`/review`) built on top of the Phase 7.1 Chargeback Shield React + TypeScript + Vite frontend platform. The workspace provides an explainable, safe, and auditable merchant review environment.

> **PRIMARY ARCHITECTURAL INVARIANT**:
> `"INVESTIGATE → VERIFY → REVIEW → APPROVE/REJECT → AUDIT"`

---

## 1. Review Workspace Architecture (`/review`)

The workspace is organized into a 3-column layout:
- **Left Column**: Prioritized Review Queue Sidebar (`ReviewQueue.tsx`) with tabbed filtering (`Pending Review`, `Review Required`, `Approved`, `Rejected`, `Blocked`), search bar, and risk priority badges.
- **Center-Left Column**: Evidence Document Explorer (`EvidenceExplorer.tsx`), Safe Document Preview Renderer (`EvidencePreview.tsx`), and Extracted Fact Viewer (`FactViewer.tsx`).
- **Center-Right Column**: Deterministic Match Inspector (`MatchInspector.tsx`), Policy Explanation Breakdown (`PolicyExplanation.tsx`), Contest Draft Viewer (`ContestDraftViewer.tsx`), and Expandable Claim Provenance Inspector (`ProvenanceInspector.tsx`).
- **Full-Width Bottom Panel**: Persistent Context Header (`ReviewHeader.tsx`), High-Visibility Warning Flags (`ReviewFlags.tsx`), Interactive Decision Panel (`ReviewDecisionPanel.tsx`), Confirmation Modal (`ReviewConfirmationModal.tsx`), Audit History Log (`ReviewAuditHistory.tsx`), and Stale Draft Banner (`StaleDraftBanner.tsx`).

---

## 2. Review Component Hierarchy (`src/components/review/`)

1. `ReviewHeader.tsx`: Persistent dispute context header displaying Dispute ID, Payment ID, Amount, Currency, Reason Code, Policy Outcome, Draft Status, Review Status, Preflight, Submission, and Pre-submission handoff link to `/disputes/{dispute_id}/preflight`.
2. `ReviewQueue.tsx`: Work queue sidebar with search, tabbed filters, amount metrics, and risk tags.
3. `EvidenceExplorer.tsx`: Document navigation panel with SHA-256 hashes, MIME types, file sizes, processing status, and document type badges.
4. `EvidencePreview.tsx`: Safe document preview for PDF, PNG, and JPEG via existing backend endpoints with fallback notice if preview is unavailable.
5. `FactViewer.tsx`: Extracted fact viewer categorized by `TRANSACTION`, `CUSTOMER`, `SHIPPING`, `INVOICE`, `REFUND`, `COMMUNICATION`, `SERVICE`, `POLICY`, showing observed values, confidence scores, and extraction sources.
6. `ProvenanceInspector.tsx`: Expandable provenance tree tracing Claim $\rightarrow$ MatchResult $\rightarrow$ ExtractedEvidence $\rightarrow$ ProcessedArtifact $\rightarrow$ EvidenceDocument.
7. `MatchInspector.tsx`: Side-by-side expected vs observed fact comparison inspector with status filtering (`All`, `Match`, `Mismatch`, `Missing`, `Ambiguous`, `Conflict`).
8. `PolicyExplanation.tsx`: Rule evaluation breakdown card explaining rule IDs, versions, priority, pass/fail status, supporting MatchResult IDs, and final policy decision (`ELIGIBLE`, `HUMAN_REVIEW`, `NOT_ELIGIBLE`).
9. `ContestDraftViewer.tsx`: Contest draft viewer rendering draft title, summary, generator version, input fingerprint, and factual argument cards with support levels and evidence references.
10. `ReviewFlags.tsx`: High-visibility warning presentation for review flags (`AMOUNT_MISMATCH`, `CROSS_DOCUMENT_CONFLICT`, `MISSING_EVIDENCE`, `LOW_CONFIDENCE_SOURCE`, `PROMPT_INJECTION_DEFENSE`, `POLICY_DISQUALIFICATION`).
11. `ReviewDecisionPanel.tsx`: Interactive decision panel with Approve / Reject buttons, reviewer reference input, comment textarea, BLOCKED draft protection, and terminal state locking.
12. `ReviewConfirmationModal.tsx`: Confirmation dialog modal displayed prior to Approve/Reject action showing dispute summary, decision, reviewer ref, and unresolved flags.
13. `ReviewAuditHistory.tsx`: Audit log rendering review decision history, previous vs new review status, reviewer ref, comments, fingerprint, and timestamps.
14. `StaleDraftBanner.tsx`: Prominent HTTP 409 stale state notification banner offering explicit draft refresh action.

---

## 3. Security & Safety Contracts

1. **Payload Strictness**: Request body sent to `POST /api/disputes/{dispute_id}/contest-draft/review` contains **ONLY**:
   ```json
   {
     "decision": "APPROVE" | "REJECT",
     "comment": "Optional reviewer notes",
     "reviewer_reference": "merchant_admin"
   }
   ```
   Financial fields (`payment_id`, `amount`, `currency`), policy decisions, evidence IDs, and factual claims are **NEVER** sent in request bodies.
2. **Blocked Draft Protection**: If `ContestDraft.status == BLOCKED`, the Approve button is disabled with message *"Approval unavailable because this draft is blocked by policy."*
3. **Terminal State Locking**: If `review_status == APPROVED` or `REJECTED`, review controls are disabled. Conflicting decision attempts return HTTP 409.
4. **Stale Draft Protection**: On HTTP 409, current UI state is preserved with a prominent stale draft banner (`StaleDraftBanner.tsx`) and manual refresh prompt. No automatic retries or silent overwrites.
5. **Pre-Submission Handoff**: Approved drafts display a manual link to `/disputes/{dispute_id}/preflight`. Preflight or submission is **NEVER** executed automatically.

---

## 4. Verification & Audit Results

### 1. Frontend Production Build
```powershell
cd frontend
npm run build
```
- **Result**: **Clean production bundle created in `frontend/dist/`** in 30.77s.
- `dist/index.html` (0.92 kB)
- `dist/assets/index.css` (29.96 kB)
- `dist/assets/index.js` (275.61 kB)
- **TypeScript Errors**: 0 errors.

### 2. Frontend Security & E2E Test Suite
```powershell
npx tsx tests/security/review-workspace-security.test.ts
npx tsx tests/e2e/human-review-workspace.spec.ts
```
- **Review Workspace Security Audit**: `[REVIEW WORKSPACE SECURITY AUDIT PASSED]: All 22 security assertions verified cleanly.`
- **Human Review E2E Simulation**: `[HUMAN REVIEW E2E SIMULATION PASSED]: All 17 review workflow steps verified.`

### 3. Backend Full Regression Test Suite
```powershell
.\venv\Scripts\python.exe -m pytest backend/tests/ -v
```
- **Result**: **`633 / 633 passed (100% Green)`** across the entire Chargeback Shield platform.

---

## 5. Final Status Declaration

"PHASE 7 TASK 7.2 — HUMAN REVIEW & EVIDENCE INVESTIGATION WORKSPACE COMPLETE — VERIFIED."
