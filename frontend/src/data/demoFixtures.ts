/**
 * Deterministic Demo Fixtures — Chargeback Shield Task 7.5
 * 
 * Explicitly labeled: "DEMO DATA — NOT LIVE RAZORPAY DATA"
 * Contains 17-stage lifecycle fixture data for demo-dispute-001.
 */

export interface DemoStage {
  id: number;
  name: string;
  state: string;
  input: string;
  output: string;
  security_boundary: string;
  provenance: string;
  backend_api: string;
}

export const DEMO_DISPUTE_ID = 'demo-dispute-001';
export const DEMO_DATA_TAG = 'DEMO DATA — NOT LIVE RAZORPAY DATA';

export const DEMO_STAGES: DemoStage[] = [
  {
    id: 1,
    name: 'Dispute Ingestion',
    state: 'DISPUTE_CREATED',
    input: 'Webhook payload: disp_N1A2B3C4D5, amount: ₹2,500.00 INR, reason: Fraudulent Chargeback',
    output: 'Persisted local Dispute record (ID: demo-dispute-001, payment_id: pay_N1A2B3C4D5)',
    security_boundary: 'HMAC-SHA256 signature verification over raw request body',
    provenance: 'Source: Razorpay Webhook Event (disp_N1A2B3C4D5)',
    backend_api: 'GET /api/dashboard/disputes/demo-dispute-001',
  },
  {
    id: 2,
    name: 'Razorpay Evidence Integration',
    state: 'EVIDENCE_FETCHED',
    input: 'Dispute ID: disp_N1A2B3C4D5',
    output: 'Retrieved 3 official evidence document metadata descriptors from Razorpay API',
    security_boundary: 'Read-only GET /v1/disputes/{id} client call with zero mutation routes',
    provenance: 'Source: Razorpay API Evidence Metadata',
    backend_api: 'GET /api/evidence/disputes/demo-dispute-001',
  },
  {
    id: 3,
    name: 'Secure Evidence Ingestion',
    state: 'EVIDENCE_INGESTED',
    input: 'Binary streams for delivery_proof.pdf, buyer_ip_log.json, customer_sign.png',
    output: 'Valid SHA-256 hashes generated, MIME types verified, storage paths cryptographically isolated',
    security_boundary: 'Magic byte validation, file size bounds, random UUID path storage (no user filenames)',
    provenance: 'SHA-256: 7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a',
    backend_api: 'GET /api/evidence/disputes/demo-dispute-001/documents',
  },
  {
    id: 4,
    name: 'Evidence File Processing',
    state: 'PROCESSING_COMPLETE',
    input: 'Ingested documents in sandbox storage',
    output: 'Clean text content extracted, PDF/Image OCR normalized, zero executable code stored',
    security_boundary: 'Isolated parsing sandbox, execution privileges revoked, zero script execution',
    provenance: 'Processor: Tesseract OCR + PyPDF Sanitized Parser',
    backend_api: 'GET /api/evidence/documents/doc-demo-001',
  },
  {
    id: 5,
    name: 'Structured Fact Extraction',
    state: 'FACTS_EXTRACTED',
    input: 'Normalized evidence text stream',
    output: 'Extracted facts: { tracking_number: "TRK99887766", buyer_ip: "198.51.100.42", delivery_date: "2026-08-20" }',
    security_boundary: 'Strict PII/credential sanitization over extracted fact attributes',
    provenance: 'Extractor Engine v1.4.2',
    backend_api: 'GET /api/evidence/disputes/demo-dispute-001/facts',
  },
  {
    id: 6,
    name: 'Deterministic Fact Matching',
    state: 'MATCHING_COMPLETE',
    input: 'Extracted evidence facts vs merchant order database facts',
    output: 'Match status: MATCH (Confidence: 100%, 0 cross-document conflicts)',
    security_boundary: 'Strict equality & taxonomy check (MATCH, MISMATCH, MISSING, AMBIGUOUS)',
    provenance: 'Matching Algorithm v2.1.0',
    backend_api: 'GET /api/matching/disputes/demo-dispute-001',
  },
  {
    id: 7,
    name: 'Deterministic Policy Evaluation',
    state: 'POLICY_EVALUATED',
    input: 'Matched facts & dispute reason code (Fraudulent Chargeback)',
    output: 'Policy decision: ELIGIBLE (Rule: R_FRAUD_DELIVERY_PROOF_v1, disqualification_reasons: [])',
    security_boundary: 'Policy rules executed strictly in backend Python engine (frontend cannot alter outcome)',
    provenance: 'Policy Rule Version: R_FRAUD_DELIVERY_PROOF_v1',
    backend_api: 'GET /api/policy/disputes/demo-dispute-001',
  },
  {
    id: 8,
    name: 'Contest Draft Generation',
    state: 'DRAFT_GENERATED',
    input: 'Policy evaluation result & matched evidence facts',
    output: 'Generated Contest Draft (Title: "Fraudulent Chargeback Rebuttal", Summary: 3 factual arguments)',
    security_boundary: 'Draft generated locally in database; zero Razorpay mutation executed',
    provenance: 'Draft Engine ID: draft-demo-001',
    backend_api: 'GET /api/drafts/disputes/demo-dispute-001',
  },
  {
    id: 9,
    name: 'Human Review Checkpoint',
    state: 'APPROVED',
    input: 'Contest draft & evidence provenance tree',
    output: 'Review decision: APPROVED (Reviewer: merchant_admin_01, comment: "Verified delivery proof")',
    security_boundary: 'BLOCKED drafts cannot be approved; reviewer reference strictly logged in audit trail',
    provenance: 'Human Reviewer ID: merchant_admin_01',
    backend_api: 'GET /api/review/disputes/demo-dispute-001',
  },
  {
    id: 10,
    name: 'Submission Preflight Gate',
    state: 'PREFLIGHT_PASSED',
    input: 'Approved contest draft, dispute metadata, evidence hashes',
    output: 'Preflight status: READY (Authorization Hash: pf_hash_9876543210)',
    security_boundary: 'Calculates cryptographic preflight hash; blocks modified/stale drafts',
    provenance: 'Preflight Validator v1.0',
    backend_api: 'GET /api/preflight/disputes/demo-dispute-001',
  },
  {
    id: 11,
    name: 'Controlled Contest Submission',
    state: 'SUBMITTED',
    input: 'Preflight authorized payload & merchant credentials',
    output: 'Razorpay Submission Record (Submission ID: sub_razorpay_998877, status: SUBMITTED)',
    security_boundary: 'Single controlled POST endpoint; zero direct frontend Razorpay requests',
    provenance: 'Razorpay API Endpoint: PATCH /v1/disputes/disp_N1A2B3C4D5/contest',
    backend_api: 'GET /api/submission/disputes/demo-dispute-001',
  },
  {
    id: 12,
    name: 'UNKNOWN State Simulation',
    state: 'SUBMISSION_UNKNOWN',
    input: 'Simulated network timeout during external Razorpay HTTP request',
    output: 'Local submission status: UNKNOWN (Flag: reconciliation_required = True)',
    security_boundary: 'NO retry submission button allowed; prevents double submission',
    provenance: 'Safety Invariant: SUBMIT ONCE -> NEVER BLINDLY RETRY',
    backend_api: 'GET /api/operations/reconciliation-required',
  },
  {
    id: 13,
    name: 'Status Reconciliation',
    state: 'RECONCILED',
    input: 'UNKNOWN submission record (ID: sub_razorpay_998877)',
    output: 'Reconciled local state: SUBMITTED (Razorpay Reported Status: under_review)',
    security_boundary: 'Read-only GET /v1/disputes/{id} lookup; zero external mutations',
    provenance: 'Reconciliation Engine Task 5.4C',
    backend_api: 'GET /api/submission/reconciliation/disputes/demo-dispute-001',
  },
  {
    id: 14,
    name: 'Dispute Lifecycle Synchronization',
    state: 'SYNCHRONIZED',
    input: 'Razorpay asynchronous dispute status change',
    output: 'Persisted DisputeLifecycleSnapshot (Outcome: WON, synced_at: 2026-08-25T14:30:00Z)',
    security_boundary: 'Read-only GET polling; updates local snapshot tables only',
    provenance: 'Lifecycle Sync Service Task 5.5',
    backend_api: 'GET /api/lifecycle/disputes/demo-dispute-001/history',
  },
  {
    id: 15,
    name: 'Operational Dashboard',
    state: 'MONITORED',
    input: 'Aggregated local dispute, alert, and SLA records',
    output: '360° Dispute Lifecycle Dashboard metrics & operational queue',
    security_boundary: 'Observability layer only; zero business mutations executed',
    provenance: 'Dashboard Router Task 6.1',
    backend_api: 'GET /api/dashboard/summary',
  },
  {
    id: 16,
    name: 'Audit & Compliance Traceability',
    state: 'AUDITED',
    input: 'Chronological timeline of all 15 lifecycle stage events',
    output: 'Full Audit Trail Report (Canonical SHA-256 Hash: a8f90c3d9b1e2a4f5c6d7e8f90a1b2c3d4e5f6a7)',
    security_boundary: 'Cryptographic hash verification; tamper-evident event log',
    provenance: 'Audit & Compliance Engine Task 6.2',
    backend_api: 'GET /api/audit/disputes/demo-dispute-001/traceability',
  },
  {
    id: 17,
    name: 'Analytics & Management Reporting',
    state: 'ANALYZED',
    input: 'Platform-wide dispute metrics & stage performance numbers',
    output: 'Executive Intelligence Summary (Win Rate: 78.5%, SLA Compliance: 99.2%)',
    security_boundary: 'Strictly read-only GET analytics endpoints; zero mutation controls',
    provenance: 'Analytics Service Task 6.4 & 7.4',
    backend_api: 'GET /api/analytics/summary',
  },
];
