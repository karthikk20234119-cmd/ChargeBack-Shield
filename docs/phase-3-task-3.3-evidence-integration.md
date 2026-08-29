# Phase 3 Task 3.3 — Razorpay Evidence/Document Integration
## Research & Design Specification (READ ONLY)

> [!CAUTION]
> **READ-ONLY / DESIGN ONLY BOUNDARY**: This document specifies the architecture, security models, data flows, and future task breakdowns for integrating Razorpay evidence documents into Chargeback Shield. It contains **ZERO production code changes** and introduces **ZERO Razorpay API mutations** (no POST/PATCH/PUT/DELETE to Razorpay, no contest creation, no accept/reject).

---

## 1. Objective & Scope

The goal of Phase 3 Task 3.3 is to establish a secure, deterministic design for discovering, downloading, validating, and ingesting evidence documents associated with Razorpay disputes.

### Primary Goals
1. **Evidence Reference Extraction**: Parse the `evidence` object inside Razorpay dispute responses.
2. **Metadata & Content Fetching**: Design read-only retrieval via Razorpay Documents APIs (`GET /v1/documents/:id` and `GET /v1/documents/:id/content`).
3. **Local Security Pipeline**: Subject downloaded external documents to local security controls (MIME check, magic bytes, SHA-256 integrity, size ceilings, decompression bomb defense, path safety).
4. **Local Pipeline Ingestion**: Connect downloaded documents to existing Chargeback Shield processing pipelines (`EvidenceDocument` → `ProcessedArtifact` → `ExtractedEvidence` → `MatchResult` → `PolicyResult`).
5. **Zero Mutation Guarantee**: Maintain strict read-only interaction with Razorpay APIs.

---

## 2. Official Documentation Research & API Endpoints

Official Razorpay API Reference Sources:
- Dispute API: `https://razorpay.com/docs/api/disputes/`
- Entity Specs: `https://razorpay.com/docs/api/disputes/#fetch-a-dispute-with-id`
- Documents API: `https://razorpay.com/docs/api/documents/`

### Verified Razorpay Endpoints

| Endpoint | HTTP Method | Authentication | Description |
|:---|:---|:---|:---|
| `/v1/disputes/:id` | `GET` | Basic Auth (`key_id:key_secret`) | Fetches full dispute entity including `evidence` object |
| `/v1/documents/:id` | `GET` | Basic Auth (`key_id:key_secret`) | Fetches metadata for a specific document ID |
| `/v1/documents/:id/content` | `GET` | Basic Auth (`key_id:key_secret`) | Downloads binary content of a specific document |

### Detailed Endpoint Contracts

#### A. Fetch Document Metadata
- **URL**: `GET https://api.razorpay.com/v1/documents/:id`
- **Headers**: `Authorization: Basic <base64(key_id:key_secret)>`
- **Response Schema** (JSON):
  ```json
  {
    "id": "doc_AHfqOvkldwsbqt",
    "entity": "document",
    "purpose": "dispute_evidence",
    "name": "shipping_receipt.pdf",
    "size": 524288,
    "mime_type": "application/pdf",
    "created_at": 1735603200
  }
  ```
- **Error Responses**: `401 Unauthorized`, `404 Not Found`, `429 Rate Limit Exceeded`, `500 Internal Server Error`.

#### B. Fetch Document Content (Download)
- **URL**: `GET https://api.razorpay.com/v1/documents/:id/content`
- **Headers**: `Authorization: Basic <base64(key_id:key_secret)>`
- **Response**: Binary stream (`application/octet-stream`, `application/pdf`, `image/jpeg`, `image/png`).
- **Response Headers**:
  - `Content-Type`: MIME type of file.
  - `Content-Length`: Size in bytes.
  - `Content-Disposition`: e.g. `attachment; filename="shipping_receipt.pdf"`.

---

## 3. Razorpay Dispute `evidence` Object Structure

The Razorpay Dispute Entity (`GET /v1/disputes/:id`) includes an `evidence` object representing attached representment documents.

### Verified Structure

```json
{
  "id": "disp_AHfqOvkldwsbqt",
  "entity": "dispute",
  "evidence": {
    "summary": "Customer received the order on 2026-08-15 verified via AWB 987654321.",
    "shipping_proof": ["doc_AHfqOvkldwsbqt", "doc_BHfqOvkldwsbqt"],
    "billing_proof": ["doc_CHfqOvkldwsbqt"],
    "cancellation_proof": [],
    "explanation_letter": ["doc_DHfqOvkldwsbqt"],
    "refund_proof": [],
    "access_activity_log": [],
    "terms_conditions": [],
    "others": []
  }
}
```

### Field Definitions & Document Types

| Evidence Category Key | Description | Internal `document_type` Mapping |
|:---|:---|:---|
| `shipping_proof` | Array of `doc_id` strings for delivery/shipping proof | `shipping_proof` |
| `billing_proof` | Array of `doc_id` strings for invoice/receipt | `billing_proof` / `invoice` |
| `cancellation_proof` | Array of `doc_id` strings for cancellation terms/logs | `cancellation_proof` |
| `explanation_letter` | Array of `doc_id` strings for merchant response letter | `explanation_letter` |
| `refund_proof` | Array of `doc_id` strings showing prior refund transactions | `refund_proof` |
| `access_activity_log` | Array of `doc_id` strings for digital download/access logs | `access_activity_log` |
| `terms_conditions` | Array of `doc_id` strings for store policy / T&C | `terms_conditions` |
| `others` | Array of `doc_id` strings or custom objects | `other_evidence` |

---

## 4. Local Model Mapping & Ingestion Pipeline

### Complete Data Flow Architecture

```
Razorpay Dispute (GET /v1/disputes/:id)
      │
      ├── Extract Evidence Document IDs (e.g. "doc_AHfqOvkldwsbqt")
      ▼
Razorpay Documents API (GET /v1/documents/:id & :id/content)
      │
      ├── Download Binary Stream + Fetch Metadata
      ▼
Local Security Pipeline
      ├── Verify MIME type & Magic Bytes (%PDF-, JPEG, PNG)
      ├── Compute SHA-256 Hash
      ├── Validate File Size Ceilings (2MB PDF, 4MB Image)
      └── Check Duplicate Hash / razorpay_doc_id
      │
      ▼
Storage & DB Ingestion
      ├── Write file to ./storage/evidence/{internal_filename}
      └── Create EvidenceDocument record (processing_status="READY_FOR_PROCESSING")
      │
      ▼
Image Processing Pipeline (processing_service.py)
      ├── Rasterize PDF to PNG / Normalize Image
      └── Create ProcessedArtifact records (processing_status="READY_FOR_AI")
      │
      ▼
AI Fact Extraction (ai_extraction_service.py)
      ├── Call OpenAI / Vision Provider
      └── Create ExtractedEvidence record
      │
      ▼
Deterministic Matching (matching_service.py)
      ├── Run zero-LLM deterministic field rules
      └── Create MatchResult records
      │
      ▼
Deterministic Policy Engine (policy_engine_service.py)
      ├── Evaluate Visa 13.1 Representment rules
      └── Create PolicyResult record
```

### Schema Field Mapping Matrix

#### `Razorpay Document` → `EvidenceDocument`

| Source Field (Razorpay API / Security Check) | Target Field (`EvidenceDocument`) | Mapping Rule |
|:---|:---|:---|
| Generated UUID | `id` | `uuid.uuid4()` |
| `dispute_id` | `dispute_id` | Foreign Key to local `Dispute.id` |
| `doc_id` (e.g., `doc_AHfqOvkldwsbqt`) | `razorpay_doc_id` | Direct String |
| Metadata `name` / `Content-Disposition` | `original_filename` | Sanitized original filename |
| Local Generator | `internal_filename` | `uuid_hash.ext` (Path Traversal Safe) |
| Local Storage Path | `file_path` | `./storage/evidence/{internal_filename}` |
| Downloaded Byte Stream | `file_hash` | SHA-256 hex digest of raw stream |
| Downloaded Byte Stream Size | `file_size_bytes` | `len(content_bytes)` |
| Validated Magic-Byte Type | `mime_type` | `application/pdf`, `image/jpeg`, `image/png` |
| Evidence Category Key | `document_type` | `shipping_proof`, `billing_proof`, etc. |
| Pipeline Initial State | `processing_status` | Set to `"READY_FOR_PROCESSING"` |
| Local Timestamp | `created_at` | `datetime.utcnow()` |

---

## 5. Security Architecture & Safeguards

The evidence synchronization pipeline reuses all existing Phase 1 security controls:

### Security Controls Matrix

| Security Threat | Safeguard Mechanism | Enforcement Rule |
|:---|:---|:---|
| **Path Traversal Attacks** | Unique Internal Filename Generation | Storage filename is strictly `uuid.uuid4() + ext`. Original filename is sanitized and stored only as text. |
| **Spoofed MIME Types** | Magic-Byte Inspection | Must match header bytes:<br>• PDF: `%PDF-` (`0x25 0x50 0x44 0x46 0x2D`)<br>• PNG: `\x89PNG\r\n\x1a\n`<br>• JPEG: `\xFF\xD8\xFF` |
| **Oversized Uploads / DoS** | Stream Size Ceilings | • PDF Max: `2,097,152` bytes (2 MB)<br>• Image Max: `4,194,304` bytes (4 MB) |
| **Decompression Bomb DoS** | Image Pixel Bounds | Max `25,000,000` pixels (25 Megapixels) for image decompression |
| **Excessive Page Count DoS** | Page Count Ceiling | Max `10` pages per PDF document |
| **Encrypted / Password PDF** | PyPDF Encryption Inspection | Rejects encrypted/password-protected PDFs before rasterization |
| **Hash Tampering** | Stream-Level SHA-256 Calculation | Hash calculated immediately from in-memory response bytes before disk write |
| **Credential Leakage** | Log & Response Sanitization | Basic Auth headers & API keys excluded from log calls, DB records, and audit tables |

---

## 6. Duplicate Prevention Strategy

To ensure zero duplicate records or redundant file processing:

### Two-Tier Duplicate Check
1. **Tier 1: `razorpay_doc_id` Check**
   - Query `EvidenceDocument` where `dispute_id = :dispute_id AND razorpay_doc_id = :razorpay_doc_id`.
   - If found → Return `DUPLICATE` action, skip download.
2. **Tier 2: SHA-256 File Hash Check**
   - After download, compute `SHA-256(content_bytes)`.
   - Query `EvidenceDocument` where `dispute_id = :dispute_id AND file_hash = :file_hash`.
   - If found → Delete temporary stream, return `DUPLICATE` action, link or skip creation.

---

## 7. Failure Handling Matrix

| Failure Mode | Cause | System Action | Audit Log Action |
|:---|:---|:---|:---|
| **Dispute Not Found** | Invalid `dispute_id` | Return `404 Not Found` | `DOCUMENT_SYNC_FAILED` |
| **Document 404** | Document deleted on Razorpay | Skip document, continue sync | `DOCUMENT_NOT_FOUND` |
| **Auth Failure (401)** | Invalid API credentials | Raise `502 Bad Gateway` | Log alert (credentials masked) |
| **Rate Limit (429)** | Exceeded API quota | Exponential backoff (respect `Retry-After`) | `DOCUMENT_RATE_LIMITED` |
| **Network Timeout** | Connection drop | Retry up to 3 times, then skip | `DOCUMENT_TIMEOUT` |
| **Magic-Byte Mismatch** | Executable/malicious binary | Reject document | `DOCUMENT_REJECTED_SECURITY` |
| **Oversized File** | File > ceiling | Reject document | `DOCUMENT_REJECTED_OVERSIZED` |
| **Encrypted PDF** | Password protected PDF | Mark status `UNPROCESSABLE` | `DOCUMENT_REJECTED_ENCRYPTED` |
| **Corrupted Binary** | Partial download | Verify length & SHA-256; fail fast | `DOCUMENT_CORRUPTED` |

---

## 8. Audit Trail Design

New audit actions added to `DisputeSyncAudit` (`dispute_sync_audits` table):

- `DOCUMENT_DISCOVERED`: Discovered `doc_id` in dispute evidence object.
- `DOCUMENT_DOWNLOADED`: Successfully fetched, validated, and saved document locally.
- `DOCUMENT_DUPLICATE`: Document already exists locally; skipped re-ingestion.
- `DOCUMENT_REJECTED`: Document failed security, size, or magic-byte checks.
- `DOCUMENT_PROCESSING_FAILED`: Document failed PDF rasterization or vision AI extraction.

> [!IMPORTANT]
> **Audit Privacy Invariant**: `raw_razorpay_data` and audit parameters MUST be passed through JSON sanitizers to strip any `key_id`, `key_secret`, or authorization tokens before persistence.

---

## 9. Proposed Local Sync API Contract (DESIGN ONLY)

### Endpoint
`POST /api/disputes/{dispute_id}/sync-evidence`

### Operational Guarantee
Modifies **ONLY** local storage (`./storage/evidence`, `./storage/processed`) and local database tables (`evidence_documents`, `processed_artifacts`, `extracted_evidence`, `match_results`, `policy_results`, `dispute_sync_audits`). Performs **ZERO** Razorpay API mutations.

### Request Parameters
- Path: `dispute_id` (string, required)
- Query: `auto_process` (boolean, optional, default `true` — triggers automated rasterization & AI extraction)

### Response Schema (`DisputeEvidenceSyncResult`)

```json
{
  "dispute_id": "disp_AHfqOvkldwsbqt",
  "documents_discovered": 3,
  "documents_downloaded": 2,
  "documents_duplicate": 1,
  "documents_failed": 0,
  "synced_documents": [
    {
      "razorpay_doc_id": "doc_AHfqOvkldwsbqt",
      "local_evidence_id": "550e8400-e29b-41d4-a716-446655440000",
      "document_type": "shipping_proof",
      "original_filename": "shipping_receipt.pdf",
      "file_size_bytes": 524288,
      "mime_type": "application/pdf",
      "status": "READY_FOR_AI"
    }
  ],
  "synchronized_at": "2026-08-27T19:40:00Z"
}
```

---

## 10. Representment / Contest Workflow Compatibility

Retrieved evidence documents directly feed into the future Representment pipeline:

```
Synced Evidence Documents
      │
      ▼
Policy Result (cb13.1-v1.0)
      │
      ├── IF ELIGIBLE: Assemble Representment Package
      ▼
Contest Draft (Local Schema)
      ├── Aggregates shipping_proof, billing_proof, explanation_letter
      ▼
Merchant Review & Human Approval (Manual Action)
      │
      ├── Merchant verifies draft and documents
      ▼
[FUTURE PHASE 3.4] Explicit Contest Submission (POST /v1/disputes/:id/contest)
```

---

## 11. Verified Facts, Assumptions, and Unknowns

### Verified Facts
- ✅ Endpoint `GET /v1/disputes/:id` returns the full dispute entity containing the `evidence` object.
- ✅ Endpoint `GET /v1/documents/:id` fetches document metadata.
- ✅ Endpoint `GET /v1/documents/:id/content` streams the raw binary file.
- ✅ Local model `EvidenceDocument` already possesses a `razorpay_doc_id` field.
- ✅ Existing local security pipeline (magic bytes, SHA-256, Poppler rasterizer) supports seamless ingestion.

### Assumptions
- 💡 `GET /v1/documents/:id/content` sends standard `Content-Disposition` header with file extension if metadata endpoint is omitted.
- 💡 Most Razorpay merchants upload standard single/multi-page PDFs or JPEG/PNG images for dispute representment.

### Unknowns & Documentation Gaps
- ❓ `others` evidence array: Official docs state `others` can contain strings or custom key-value metadata objects. Must handle polymorphic items safely.
- ❓ Document Retention Policy: Razorpay documentation does not specify how long historical dispute documents remain accessible via `GET /v1/documents/:id/content`.

---

## 12. Implementation Roadmap (Sub-tasks 3.3A - 3.3F)

*Note: The following tasks are planned for future execution and are NOT implemented in Task 3.3.*

- **Task 3.3A: Evidence Reference Extraction**: Implement helper functions to parse dispute `evidence` objects into typed document references (`RazorpayEvidenceReference`).
- **Task 3.3B: Document Metadata Retrieval**: Add `get_document_metadata(doc_id)` to `HttpRazorpayClient` and `MockRazorpayClient`.
- **Task 3.3C: Document Content Download Engine**: Add `download_document_content(doc_id)` to `HttpRazorpayClient` with streaming response handling and memory-safe chunking.
- **Task 3.3D: Secure Local Ingestion Pipeline**: Wire downloaded byte streams into `EvidenceDocument` creation, SHA-256 hashing, magic-byte checking, and file storage.
- **Task 3.3E: Evidence Synchronization Service**: Build `RazorpayEvidenceSyncService` to orchestrate multi-document fetching, duplicate prevention, and automatic trigger of image processing & AI extraction.
- **Task 3.3F: Integration & Safety Test Suite**: Write comprehensive tests validating end-to-end evidence sync using `MockRazorpayClient`, security boundary checks, and zero-mutation assertions.
