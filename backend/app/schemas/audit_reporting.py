"""
Audit & Compliance Reporting Schemas — Chargeback Shield Task 6.2

Defines strict Pydantic schemas for unified audit events, chronological dispute timelines,
end-to-end traceability graphs, evidence provenance, policy compliance, human review audit,
submission audit, financial integrity verification, security audit, compliance exports, and tamper detection.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """Unified read-only representation of a single lifecycle audit event."""
    event_id: str
    dispute_id: str
    event_type: str
    event_category: str  # DISPUTE, EVIDENCE, PROCESSING, EXTRACTION, MATCHING, POLICY, DRAFT, REVIEW, PREFLIGHT, SUBMISSION, RECONCILIATION, LIFECYCLE, OUTCOME, SECURITY
    source_type: str
    source_id: str
    actor_type: str  # SYSTEM, AI_MODEL, HUMAN_REVIEWER, RAZORPAY_GATEWAY
    actor_reference: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    event_timestamp: datetime
    explanation: str
    source_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    integrity_hash: Optional[str] = None


class DisputeAuditTimeline(BaseModel):
    """Chronological, paginated audit timeline for a dispute."""
    dispute_id: str
    events: List[AuditEvent]
    total_events: int
    first_event_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None
    current_state: str
    final_outcome: Optional[str] = None
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


class TraceabilityNode(BaseModel):
    """Node in the end-to-end dispute traceability DAG."""
    node_id: str
    node_type: str  # Dispute, EvidenceDocument, ProcessedArtifact, ExtractedEvidence, MatchResult, PolicyResult, ContestDraft, ContestDraftReviewAudit, ContestSubmission, ContestSubmissionAudit, DisputeLifecycleSnapshot
    label: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TraceabilityEdge(BaseModel):
    """Edge in the end-to-end dispute traceability DAG."""
    source_node_id: str
    target_node_id: str
    relationship: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DisputeTraceabilityReport(BaseModel):
    """Complete directed acyclic graph (DAG) traceability report for a dispute."""
    dispute_id: str
    nodes: List[TraceabilityNode]
    edges: List[TraceabilityEdge]
    node_count: int
    edge_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceProvenance(BaseModel):
    """Provenance metadata for an extracted evidence fact."""
    source_page: int = 1
    source_region: Optional[Dict[str, Any]] = None
    extraction_method: str = "ai_vision"
    extractor_version: str = "1.0"
    matcher_version: str = "1.0"


class EvidenceTraceabilityItem(BaseModel):
    """Traceability breakdown for an evidence document."""
    evidence_id: str
    razorpay_doc_id: Optional[str] = None
    document_type: str
    file_hash: str
    file_size_bytes: int
    processing_status: str
    extraction_status: str
    extracted_fact_count: int
    processed_artifact_count: int
    match_result_count: int
    supporting_policy_rules: List[str] = Field(default_factory=list)
    supporting_draft_arguments: List[str] = Field(default_factory=list)
    provenance: List[EvidenceProvenance] = Field(default_factory=list)


class FactToDecisionTraceability(BaseModel):
    """Fact-to-decision lineage mapping for factual arguments."""
    argument_id: str
    statement: str
    support_level: str  # HIGH, MEDIUM, LOW, UNSUPPORTED
    source_fact_names: List[str] = Field(default_factory=list)
    source_evidence_ids: List[str] = Field(default_factory=list)
    source_match_result_ids: List[str] = Field(default_factory=list)
    policy_rule_ids: List[str] = Field(default_factory=list)
    explanation: str


class PolicyComplianceReport(BaseModel):
    """Policy compliance audit report for a dispute."""
    policy_result_id: Optional[str] = None
    policy_version: str = "cb13.1-v1.0"
    outcome: str = "PENDING"
    evaluated_at: Optional[datetime] = None
    rule_results: Dict[str, Any] = Field(default_factory=dict)
    evidence_coverage: Dict[str, Any] = Field(default_factory=dict)
    mandatory_rules: List[str] = Field(default_factory=list)
    failed_rules: List[str] = Field(default_factory=list)
    blocking_rules: List[str] = Field(default_factory=list)
    review_required_rules: List[str] = Field(default_factory=list)
    supporting_match_results: List[str] = Field(default_factory=list)


class HumanReviewAuditReport(BaseModel):
    """Human review audit history report."""
    draft_id: Optional[str] = None
    draft_status: Optional[str] = None
    review_status: Optional[str] = None
    reviewer_reference: Optional[str] = None
    decision: Optional[str] = None
    comment: Optional[str] = None
    previous_review_status: Optional[str] = None
    new_review_status: Optional[str] = None
    input_fingerprint: Optional[str] = None
    generator_version: Optional[str] = None
    created_at: Optional[datetime] = None
    review_history: List[Dict[str, Any]] = Field(default_factory=list)


class SubmissionAuditReport(BaseModel):
    """Contest submission audit report."""
    submission_id: Optional[str] = None
    draft_id: Optional[str] = None
    preflight_id: Optional[str] = None
    submission_status: str = "NONE"
    idempotency_key: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reconciled_at: Optional[datetime] = None
    failure_category: Optional[str] = None
    razorpay_status_observed: Optional[str] = None
    audit_events: List[Dict[str, Any]] = Field(default_factory=list)


class FinancialIntegrityReport(BaseModel):
    """Financial integrity verification report."""
    dispute_id: str
    payment_id: str
    amount: int
    currency: str
    trusted_payment_id: str
    trusted_amount: int
    trusted_currency: str
    observed_lifecycle_values: Dict[str, Any] = Field(default_factory=dict)
    mutation_detected: bool = False
    verification_status: str = "VERIFIED"  # VERIFIED, FINANCIAL_INTEGRITY_VIOLATION
    verification_events: List[str] = Field(default_factory=list)


class SecurityAuditReport(BaseModel):
    """Aggregated security audit findings report."""
    dispute_id: str
    prompt_injection_findings: List[Dict[str, Any]] = Field(default_factory=list)
    path_traversal_rejections: List[Dict[str, Any]] = Field(default_factory=list)
    mime_mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    sha256_mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    stale_fingerprints: List[Dict[str, Any]] = Field(default_factory=list)
    credential_sanitizations: List[Dict[str, Any]] = Field(default_factory=list)
    unauthorized_transitions: List[Dict[str, Any]] = Field(default_factory=list)
    total_findings: int = 0


class ComplianceExport(BaseModel):
    """Complete, canonical JSON compliance export for regulatory auditing."""
    dispute_id: str
    dispute: Dict[str, Any]
    financial_identity: Dict[str, Any]
    evidence_inventory: List[Dict[str, Any]]
    processing_history: List[Dict[str, Any]]
    extracted_facts: List[Dict[str, Any]]
    matching_results: List[Dict[str, Any]]
    policy_result: Dict[str, Any]
    contest_draft: Dict[str, Any]
    human_review: Dict[str, Any]
    preflight: Dict[str, Any]
    submission: Dict[str, Any]
    reconciliation: Dict[str, Any]
    lifecycle_snapshots: List[Dict[str, Any]]
    final_outcome: Dict[str, Any]
    security_findings: List[Dict[str, Any]]
    audit_timeline: List[Dict[str, Any]]
    report_hash: str  # SHA-256 canonical report hash
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    schema_version: str = "1.0.0"


class TamperDetectionReport(BaseModel):
    """Audit tamper detection report."""
    dispute_id: str
    audit_status: str  # VALID, INVALID, INCOMPLETE, TAMPER_SUSPECTED
    verified_event_count: int = 0
    anomaly_count: int = 0
    anomalies: List[str] = Field(default_factory=list)
