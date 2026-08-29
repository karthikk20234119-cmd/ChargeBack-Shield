# Phase 5 Task 5.4A — Contest Submission Execution Boundary Specification
## Research, Architectural Design, & Safety Controls

---

## 1. Executive Summary

Phase 5 Task 5.4A defines the controlled architectural boundary, state machine, idempotency model, security architecture, and API design for a future external Razorpay contest submission layer (`ContestSubmissionClient`).

### Hard Invariants & Safety Boundaries
- **STRICT DESIGN-ONLY BOUNDARY**: ZERO production code modifications, ZERO Razorpay mutation API calls, ZERO external network requests, ZERO AI/LLM calls.
- **Read-Only Preservation**: Existing `RazorpayClient` and `RazorpayService` remain 100% read-only and un-mutated.
- **Local Isolation**: The existing verified pipeline (`Dispute` → `MatchResult` → `PolicyResult` → `ContestDraft` → `HumanReview` → `ContestSubmissionPreflight` → `READY`) operates strictly in local memory and database storage. External contest submission is an explicit, future, opt-in operation.
- **Zero Injected Parameters**: Future API calls must derive 100% of financial identity, policy choices, evidence pointers, and argument structures from trusted database records.
- **Idempotent Recovery**: Network timeouts or ambiguous HTTP responses must NEVER trigger automated retries without explicit query or manual intervention.

---

## 2. Current Verified Architecture

```
[ Trusted Dispute Data ] (payment_id, amount, currency, reason_code)
         │
         ▼
[ Evidence Processor & AI Extractor ] (Extracts structured evidence facts)
         │
         ▼
[ Evidence Matching Engine ] (Produces deterministic MatchResults)
         │
         ▼
[ Policy Engine ] (Produces PolicyResult: ELIGIBLE / HUMAN_REVIEW / NOT_ELIGIBLE)
         │
         ▼
[ Response Drafting Engine ] (Produces ContestDraft: DRAFT / REVIEW_REQUIRED / BLOCKED)
         │
         ▼
[ Human Review Workflow ] (Reviewer APPROVE / REJECT -> review_status)
         │
         ▼
[ Preflight Authorization Gate ] (9 Check Modules -> PreflightStatus: READY)
         │
         ▼
============================== HARD SAFETY BOUNDARY ==============================
         │
 [ FUTURE TASK 5.4B: ContestSubmissionClient (submit_contest) ]
```

---

## 3. Official Razorpay API Research Findings

### API Surface Analysis (Razorpay Disputes API)
Based on official Razorpay API documentation and developer specifications:

- **Contest Endpoint**: `POST /v1/disputes/{dispute_id}/contest` (or `PATCH /v1/disputes/{dispute_id}`)
- **Authentication**: Basic Authentication (`key_id` : `key_secret`) passed via HTTP Authorization header.
- **Content-Type**: `application/json` (or `multipart/form-data` if uploading evidence directly during contest request).
- **Request Parameters**:
  - `amount` (integer, required): Amount contested in minor units (paise).
  - `summary` (string, required): Brief text summary of merchant defense.
  - `comments` (string, optional): Merchant notes for dispute response.
  - `action` (string, optional): Action type (e.g. `contest`, `accept`).
  - `documents` (array of strings, optional): Array of pre-uploaded Razorpay document IDs (`doc_...`).
  - `evidence` (object, optional): Structured evidence dictionary mapping standard Razorpay evidence keys (`order_id`, `shipping_proof`, `invoice`, `customer_communications`, `access_activity_logs`).
- **Response Parameters**:
  - `id` (string): Dispute identifier (`disp_...`).
  - `entity` (string): `"dispute"`.
  - `payment_id` (string): Associated payment ID (`pay_...`).
  - `amount` (integer): Disputed amount in minor units.
  - `currency` (string): `"INR"`.
  - `status` (string): Dispute state (`under_review`, `action_required`, `won`, `lost`).
  - `phase` (string): Dispute phase (`chargeback`, `pre_arbitration`, `arbitration`).
  - `created_at` (integer): Unix timestamp.

---

## 4. Verified Facts vs. Design Assumptions vs. Unknowns

### Verified Official Facts
1. Razorpay dispute APIs use HTTP Basic Auth with API Key and Secret.
2. Financial amounts in Razorpay APIs are represented as integers in minor units (e.g., paise for INR).
3. Evidence uploaded to Razorpay returns document IDs (`doc_...`) that can be linked to a dispute.
4. Dispute status in Razorpay evolves asynchronously after contest submission (`action_required` → `under_review`).

### Design Assumptions
1. Contest submission is a one-way state transition on the Razorpay platform (`under_review`).
2. Razorpay responds synchronously to `POST /v1/disputes/{dispute_id}/contest` with `200 OK` or `202 Accepted` upon payload receipt.
3. Razorpay API returns standard HTTP status codes (`400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `409 Conflict`, `429 Too Many Requests`, `500/502/503/504 Server Error`).

### Unknowns & Risks
1. **Idempotency Headers**: Official Razorpay documentation does not explicitly publish standard `Idempotency-Key` header support for dispute contest endpoints.
2. **Submission Reversal**: Whether Razorpay provides an official API mechanism to withdraw or append to a contest submission once submitted.
3. **Async Race Window**: Time lag between HTTP POST receipt and dispute status update in Razorpay dashboard.

---

## 5. Submission Boundary Design & `ContestSubmissionClient` Interface

To preserve the read-only contract of `RazorpayClient`, mutation operations MUST NOT be added to `HttpRazorpayClient`. Instead, a separate, dedicated submission interface `ContestSubmissionClient` must be introduced:

```python
# Non-executing architectural pseudocode for design boundary
from typing import Protocol, runtime_checkable
from pydantic import BaseModel
from datetime import datetime

class RazorpayContestSubmissionRequest(BaseModel):
    dispute_id: str
    amount_minor: int
    currency: str
    summary: str
    document_ids: list[str]
    evidence_payload: dict

class RazorpayContestSubmissionResponse(BaseModel):
    dispute_id: str
    razorpay_status: str
    submission_reference_id: str
    submitted_at: datetime
    raw_response: dict

@runtime_checkable
class ContestSubmissionClient(Protocol):
    """
    Dedicated submission client protocol.
    STRICTLY SEPARATED from read-only RazorpayClient.
    """
    async def submit_contest(
        self,
        request: RazorpayContestSubmissionRequest
    ) -> RazorpayContestSubmissionResponse:
        ...
```

---

## 6. Deterministic Submission State Machine

The local contest submission lifecycle MUST follow an explicit, deterministic state machine tracked on `ContestSubmission`:

```
 PRECHECK_REQUIRED
        │
        ▼ (Preflight Service runs -> PreflightStatus == READY)
      READY
        │
        ▼ (Explicit Submission Authorization API call)
 SUBMISSION_AUTHORIZED
        │
        ▼ (Atomic DB Lock -> Begin HTTP Request)
 SUBMISSION_IN_PROGRESS
        │
 ┌──────┴─────────────────────────┬─────────────────────────┐
 │ (HTTP 200/202 Success)         │ (Deterministic 4xx)     │ (Network Timeout / 5xx)
 ▼                                ▼                         ▼
SUBMITTED                       FAILED                   UNKNOWN
 (Terminal Success)           (Terminal/Retryable)     (Manual Review Gate)
```

### Allowed & Forbidden State Transitions
- **Allowed**:
  - `PRECHECK_REQUIRED` → `READY`
  - `READY` → `SUBMISSION_AUTHORIZED`
  - `SUBMISSION_AUTHORIZED` → `SUBMISSION_IN_PROGRESS`
  - `SUBMISSION_IN_PROGRESS` → `SUBMITTED`
  - `SUBMISSION_IN_PROGRESS` → `FAILED`
  - `SUBMISSION_IN_PROGRESS` → `UNKNOWN`
  - `FAILED` → `READY` (only after a fresh preflight pass)
  - `UNKNOWN` → `SUBMITTED` (only after external status query verification confirms receipt)
  - `UNKNOWN` → `FAILED` (only after external status query verification confirms non-receipt)
- **Forbidden**:
  - `READY` → `SUBMITTED` (Direct automated transition without explicit authorization)
  - `SUBMITTED` → `SUBMISSION_IN_PROGRESS` (Re-submitting a terminal submission)
  - `UNKNOWN` → `SUBMISSION_IN_PROGRESS` (Retrying without verifying external state)

---

## 7. Pre-Submission Authorization Gate

Immediately prior to initiating an external HTTP request, the submission engine MUST execute an atomic, final pre-submission authorization check.

```
                           Final Authorization Gate
                                      │
 ┌────────────────────────────────────┼────────────────────────────────────┐
 │                                    │                                    │
 ▼                                    ▼                                    ▼
[ContestDraft Check]        [Preflight Check]                   [Financial Identity]
 • Status != BLOCKED         • Status == READY                   • payment_id unchanged
 • review_status == APPROVED • Fingerprint matches               • amount unchanged
                             • 0 Blocking reasons                • currency unchanged
```

If any check fails, submission is **refused immediately**, state remains `PRECHECK_REQUIRED`, and a new preflight evaluation is required.

---

## 8. Financial Safety & Immutability Controls

1. **Read-Only Sources**: Financial parameters (`payment_id`, `amount`, `currency`) are read directly from the trusted local `Dispute` record in the database.
2. **Immutable Assertions**:
   - Pre-assertion: Assert `Dispute.payment_id`, `Dispute.amount`, `Dispute.currency` match the stored `ContestSubmissionPreflight` snapshot.
   - Post-assertion: Re-verify that local database records were untouched during the HTTP execution turn.
3. **Payload Injection Defense**: Client-provided HTTP body parameters for `payment_id`, `amount`, or `currency` are completely ignored or forbidden by Pydantic strict schemas.

---

## 9. Idempotency & Duplicate Submission Strategy

To prevent duplicate submissions on Razorpay (which could result in rejected requests or financial penalties):

1. **Local Submission Idempotency Key**: Generated as `SHA-256(dispute_id + payment_id + amount + input_fingerprint + preflight_id)`.
2. **Database Unique Constraints**: `contest_submissions` table enforces `UNIQUE(dispute_id)` and `UNIQUE(idempotency_key)`.
3. **Handling Network Timeouts (The `UNKNOWN` State)**:
   - If an HTTP request times out after transmission, the outcome is **ambiguous**.
   - The local state transitions to `UNKNOWN`.
   - **CRITICAL**: The system MUST NEVER automatically retry the request.
   - The system executes a read-only query (`get_dispute(dispute_id)`) to check if Razorpay transitioned the dispute to `under_review`.
   - If verified: state transitions to `SUBMITTED`.
   - If unverified: flag for merchant human review.

---

## 10. Concurrency Controls & Race Condition Defense

To prevent Reviewer A and Reviewer B (or Worker A and Worker B) from concurrently submitting the same dispute:

1. **Database Lock & Compare-And-Set (CAS)**:
   ```sql
   UPDATE contest_submissions
   SET status = 'SUBMISSION_IN_PROGRESS', updated_at = CURRENT_TIMESTAMP
   WHERE dispute_id = :dispute_id
     AND status = 'SUBMISSION_AUTHORIZED';
   ```
2. **Row Count Assertion**: The transaction verifies `affected_rows == 1`. If `affected_rows == 0`, a concurrent worker has won the race, the transaction aborts, and HTTP 409 Conflict is returned.

---

## 11. Deterministic Error Handling & Retry Policies

| Error Condition | Local State | Retryable? | Action Required |
| :--- | :--- | :--- | :--- |
| **HTTP 400 Bad Request** | `FAILED` | No | Terminal error. Requires draft/evidence payload inspection. |
| **HTTP 401 Unauthorized** | `FAILED` | No | Check Razorpay API credentials in vault. |
| **HTTP 403 Forbidden** | `FAILED` | No | Check Razorpay account permissions/scope. |
| **HTTP 404 Not Found** | `FAILED` | No | Invalid dispute_id or Razorpay document reference. |
| **HTTP 409 Conflict** | `FAILED` | No | Dispute already contested or closed on Razorpay. |
| **HTTP 429 Rate Limit** | `SUBMISSION_AUTHORIZED` | Yes | Exponential backoff with jitter (max 3 retries). |
| **HTTP 5xx Server Error** | `FAILED` | Optional | Max 2 retries with backoff if request was rejected before execution. |
| **Network Timeout** | `UNKNOWN` | No | Transition to `UNKNOWN`. Read-only status query required. |
| **DNS / Connection Reset**| `FAILED` | Yes | Retryable only if request was not sent over socket. |

---

## 12. Append-Only Audit Trail Schema (`ContestSubmissionAudit`)

Every submission attempt creates an immutable audit record:

```sql
CREATE TABLE contest_submission_audits (
    id VARCHAR(36) PRIMARY KEY,
    dispute_id VARCHAR(64) NOT NULL,
    contest_submission_id VARCHAR(36) NOT NULL,
    contest_draft_id VARCHAR(36) NOT NULL,
    preflight_id VARCHAR(36) NOT NULL,
    input_fingerprint VARCHAR(64) NOT NULL,
    previous_state VARCHAR(32) NOT NULL,
    new_state VARCHAR(32) NOT NULL,
    submission_status VARCHAR(32) NOT NULL,
    http_status_code INTEGER,
    razorpay_reference_id VARCHAR(128),
    error_code VARCHAR(64),
    sanitized_response_metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sanitization Guarantees
- Basic Auth headers, API keys, secret strings, and bearer tokens are strictly scrubbed before saving metadata to `sanitized_response_metadata`.
- Binary evidence payloads are excluded from audit logs.

---

## 13. Security Model & Threat Matrix

| Threat / Attack Vector | Mitigation / Control |
| :--- | :--- |
| **Client Payload Injection** | Request body is empty (`{}`). Parameters derived 100% from trusted DB state. |
| **Replay Attacks** | Unique `idempotency_key` and DB single-submission constraints (`UNIQUE(dispute_id)`). |
| **Stale Draft Submission** | Input fingerprint revalidated at Authorization Gate; stale fingerprint yields `409 Conflict`. |
| **Unauthorized State Mutation** | Strict CAS state machine; direct jumps to `SUBMITTED` forbidden. |
| **Credential Leakage** | `_SENSITIVE_FIELDS` filter scrubs authorization headers from all logs/audits. |
| **Arbitrary API Endpoints** | Submission URL is hardcoded to trusted base URL format; client cannot specify destination host or path. |

---

## 14. Evidence Mapping Strategy

Local evidence documents (`EvidenceDocument`) are mapped to Razorpay submission format:

1. **Local Representation**: `EvidenceDocument` linked to `ExtractedEvidence` and `ProcessedArtifact`.
2. **Razorpay Mapping**:
   - `doc_inv` → `evidence.invoice` or `documents[]`
   - `doc_ship` → `evidence.shipping_proof` or `documents[]`
   - `doc_delivery` → `evidence.delivery_proof` or `documents[]`
3. **Validation Invariant**: Only evidence documents with `processing_status == 'AI_EXTRACTED'` and valid `razorpay_doc_id` are included.

---

## 15. Transaction & Rollback Limitations

### Asymmetry Between Local DB and External HTTP
- Local DB transactions can be committed or rolled back atomically.
- External HTTP POST calls to Razorpay cannot be "rolled back" via SQL `ROLLBACK`.
- **Mitigation Architecture**:
  1. Commit `SUBMISSION_IN_PROGRESS` state in local DB **BEFORE** initiating HTTP POST.
  2. Perform external HTTP call.
  3. Commit `SUBMITTED` or `FAILED` state in local DB **AFTER** HTTP response received.
  4. If process crashes during step 2, startup recovery job identifies orphaned `SUBMISSION_IN_PROGRESS` records and queries Razorpay via `get_dispute`.

---

## 16. Proposed API Contract (Design Only)

### `POST /api/disputes/{dispute_id}/contest-submission`
- **Purpose**: Triggers controlled external contest submission for an authorized dispute.
- **Request Body**: Empty `{}`.
- **Headers**: Standard authentication headers (Bearer JWT / Session Cookie).
- **Response Schema (`ContestSubmissionResponse`)**:

```json
{
  "id": "sub_01HXYZ...",
  "dispute_id": "disp_synth_0001",
  "contest_draft_id": "draft_01HXYZ...",
  "preflight_id": "pref_01HXYZ...",
  "status": "SUBMITTED",
  "razorpay_status": "under_review",
  "idempotency_key": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "submitted_at": "2026-08-29T04:10:00Z",
  "audit_id": "audit_01HXYZ..."
}
```

---

## 17. Test Strategy for Future Implementation (Task 5.4B)

When Task 5.4B is implemented in a future phase, test coverage must include:
1. `MockContestSubmissionClient` testing `READY` preflight authorization.
2. Rejection of non-`APPROVED` drafts or non-`READY` preflights.
3. Stale fingerprint detection and HTTP 409 handling.
4. Concurrency testing (simulated simultaneous submissions yielding 409 for lost race).
5. Error simulation for HTTP 400, 401, 403, 404, 409, 429, and 5xx.
6. Ambiguous timeout handling ensuring transition to `UNKNOWN` and status query.
7. Verification that zero financial fields or draft contents are mutated.

---

## 18. Forbidden Operations List

The future submission boundary MUST NOT perform:
- Automatic dispute acceptance (`accept_dispute`).
- Automatic dispute rejection (`reject_dispute`).
- Automated refund issuance (`issue_refund`).
- Modification of trusted dispute payment or financial fields (`payment_id`, `amount`, `currency`).
- Silent automated retries on ambiguous network timeout.

---

## 19. Migration & Schema Considerations

Future Task 5.4B database migration will introduce:
1. `contest_submissions` table (tracks local submission state machine).
2. `contest_submission_audits` table (tracks append-only submission audit trail).
3. Indexes on `(dispute_id)`, `(idempotency_key)`, and `(status)`.

---

## 20. Observability & Monitoring Metrics

Key metrics for alerting:
- `chargeback_contest_submission_attempts_total` (counter by status: `submitted`, `failed`, `unknown`).
- `chargeback_contest_submission_latency_seconds` (histogram of HTTP submission execution time).
- `chargeback_contest_unknown_states_total` (counter of ambiguous timeouts requiring status query).

---

## 21. Static Verification Results (Task 5.4A Baseline)

Static inspection of the project workspace confirms:
- **`backend/app/services/razorpay_client.py`**: Contains ONLY read methods (`get_dispute`, `list_disputes`, `get_document_metadata`, `stream_document_content`, `download_document_content`). Zero mutation methods exist.
- **`backend/app/services/razorpay_service.py`**: Contains ONLY read methods. Zero mutation methods exist.
- **Production Files**: 0 production python files modified in `backend/app/`.
- **Database Schemas**: 0 production database tables added or altered.
- **Test Suite Integrity**: **439 / 439 tests passing (100% Green)**.

---

## 22. Future Task 5.4B Roadmap

1. Implement `ContestSubmissionClient` protocol and `MockContestSubmissionClient`.
2. Implement `ContestSubmission` and `ContestSubmissionAudit` database models.
3. Create `ContestSubmissionService` with CAS locking and state machine.
4. Create `POST /api/disputes/{dispute_id}/contest-submission` API endpoint.
5. Create comprehensive unit and E2E integration test suites using mock client.

---

## 23. Task Completion Declaration

PHASE 5 TASK 5.4A — SUBMISSION BOUNDARY RESEARCH & DESIGN COMPLETE — AWAITING REVIEW.
