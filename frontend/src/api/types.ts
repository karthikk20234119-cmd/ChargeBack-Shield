// TypeScript interfaces matching backend Chargeback Shield schemas

export type DisputeOutcome = 'won' | 'lost' | 'pending' | 'under_review' | 'action_required' | 'unknown';

export interface DashboardSummaryResponse {
  total_disputes: number;
  open_disputes: number;
  won_disputes: number;
  lost_disputes: number;
  win_rate_percentage: number;
  total_evidence_documents: number;
  processed_evidence_documents: number;
  policy_eligible_count: number;
  policy_human_review_count: number;
  policy_not_eligible_count: number;
  drafts_generated_count: number;
  drafts_approved_count: number;
  drafts_rejected_count: number;
  preflight_ready_count: number;
  submissions_total_count: number;
  submissions_submitted_count: number;
  submissions_unknown_count: number;
  submissions_failed_count: number;
  active_alerts_count: number;
  critical_alerts_count: number;
  reconciliation_required_count: number;
  timestamp: string;
}

export interface DisputeSummaryItem {
  id: string;
  payment_id: string;
  amount: number;
  currency: string;
  reason_code: string;
  status: string;
  evidence_status: string;
  policy_status: string;
  draft_status: string;
  review_status: string;
  preflight_status: string;
  submission_status: string;
  lifecycle_outcome: string;
  operational_status: string;
  created_at: string;
}

export interface DisputeListResponse {
  disputes: DisputeSummaryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface EvidenceDocument {
  id: string;
  dispute_id: string;
  razorpay_doc_id?: string;
  original_filename: string;
  internal_filename: string;
  file_path: string;
  file_hash: string;
  file_size_bytes: number;
  mime_type: string;
  document_type: string;
  processing_status: string;
  created_at: string;
  extracted_evidence?: ExtractedEvidence;
}

export interface ExtractedEvidence {
  id: string;
  document_id: string;
  document_type?: string;
  payment_id?: string;
  order_id?: string;
  amount_minor?: number;
  currency?: string;
  customer_name?: string;
  awb_number?: string;
  delivery_date?: string;
  signature_present?: boolean;
  confidence_score: number;
  extracted_data: Record<string, any>;
  model_name?: string;
  schema_version: string;
}

export interface MatchDetail {
  field_name: string;
  expected_value: any;
  observed_value: any;
  status: 'MATCH' | 'MISMATCH' | 'MISSING' | 'AMBIGUOUS' | 'UNVERIFIABLE' | 'NOT_COMPARABLE' | 'CROSS_DOCUMENT_CONFLICT';
  confidence: number;
  explanation: string;
  evidence_id?: string;
}

export interface MatchingRunResult {
  dispute_id: string;
  status: string;
  total_facts: number;
  match_count: number;
  mismatches_count: number;
  missing_count: number;
  ambiguous_count: number;
  results: MatchDetail[];
}

export interface RuleResult {
  rule_id: string;
  name: string;
  passed: boolean;
  explanation: string;
  is_blocking: boolean;
  facts_used: string[];
}

export interface PolicyResult {
  id: string;
  dispute_id: string;
  policy_version: string;
  decision: 'ELIGIBLE' | 'HUMAN_REVIEW' | 'NOT_ELIGIBLE';
  outcome: string;
  requires_human_review: boolean;
  summary: string;
  rules_evaluated: RuleResult[];
  created_at: string;
}

export interface FactualArgument {
  claim: string;
  fact_name: string;
  evidence_ids: string[];
  match_result_ids: string[];
  explanation: string;
}

export interface ContestDraft {
  id: string;
  dispute_id: string;
  status: 'DRAFT' | 'REVIEW_REQUIRED' | 'BLOCKED';
  review_status: 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';
  title: string;
  summary: string;
  dispute_context: Record<string, any>;
  factual_arguments: { arguments: FactualArgument[] };
  evidence_references: { references: any[] };
  limitations: { limitations: string[] };
  review_flags: { flags: string[] };
  input_fingerprint: string;
  draft_version: string;
  generator_version: string;
  created_at: string;
}

export interface ContestDraftReviewRequest {
  decision: 'APPROVE' | 'REJECT';
  comment?: string;
  reviewer_reference?: string;
}

export interface ContestDraftReviewResponse {
  audit_id: string;
  draft_id: string;
  dispute_id: string;
  previous_review_status: string;
  new_review_status: string;
  decision: 'APPROVE' | 'REJECT';
  reviewer_reference: string;
  comment?: string;
  input_fingerprint: string;
  timestamp: string;
}

export interface PreflightCheck {
  check_code: string;
  status: 'PASS' | 'FAIL' | 'WARN';
  message: string;
  severity: 'BLOCKING' | 'WARN' | 'INFO';
  source_ids?: string[];
}

export interface ContestSubmissionPreflight {
  id: string;
  dispute_id: string;
  contest_draft_id: string;
  status: 'READY' | 'BLOCKED' | 'STALE' | 'INVALID' | 'REVIEW_REQUIRED';
  draft_status: string;
  review_status: string;
  checks: PreflightCheck[];
  blocking_reasons: string[];
  verified_financial_identity: Record<string, any>;
  created_at: string;
}

export interface ContestSubmissionResponse {
  id: string;
  dispute_id: string;
  contest_draft_id: string;
  preflight_id: string;
  status: 'PRECHECK_REQUIRED' | 'READY' | 'SUBMISSION_AUTHORIZED' | 'SUBMISSION_IN_PROGRESS' | 'SUBMITTED' | 'FAILED' | 'UNKNOWN';
  razorpay_status?: string;
  razorpay_reference_id?: string;
  idempotency_key: string;
  submitted_at?: string;
  failure_category: string;
  failure_reason?: string;
  created_at: string;
}

export interface ReconciliationResponse {
  dispute_id: string;
  submission_id?: string;
  previous_state: string;
  reconciled_state: string;
  outcome: string;
  razorpay_status: string;
  action_taken: string;
  reconciled_at: string;
}

export interface DisputeLifecycleSnapshot {
  id: string;
  dispute_id: string;
  razorpay_dispute_id: string;
  razorpay_status: string;
  previous_status?: string;
  local_submission_status?: string;
  dispute_outcome: string;
  synced_at: string;
}

export interface OperationalAlert {
  id: string;
  dispute_id: string;
  code: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  category: string;
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
  message: string;
  due_at?: string;
  is_sla_breached: boolean;
  acknowledged_by?: string;
  created_at: string;
}

export interface AlertSummaryResponse {
  total_alerts: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  open_count: number;
  acknowledged_count: number;
  sla_breached_count: number;
  alerts: OperationalAlert[];
}

export interface OperationalHealthResponse {
  status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  active_disputes: number;
  open_alerts: number;
  critical_alerts: number;
  unknown_submissions: number;
  stale_preflights: number;
  timestamp: string;
}

export interface FunnelStageItem {
  stage: string;
  stage_name: string;
  count: number;
  conversion_rate: number;
  drop_off_count: number;
}

export interface BottleneckItem {
  stage: string;
  stage_name: string;
  metric_value: number;
  severity: string;
  details: string;
}

export interface AnalyticsSummary {
  total_disputes: number;
  active_disputes: number;
  won: number;
  lost: number;
  pending: number;
  win_rate: number;
  total_evidence_documents: number;
  policy_review_rate: number;
  draft_approval_rate: number;
  submission_success_rate: number;
  unknown_submission_count: number;
  critical_alert_count: number;
  reconciliation_required_count: number;
}

export interface AuditEvent {
  event_id: string;
  dispute_id: string;
  event_type: string;
  event_category: string;
  source_type: string;
  source_id: string;
  actor_type: string;
  actor_reference: string;
  new_state: string;
  event_timestamp: string;
  explanation: string;
  source_ids: string[];
  metadata: Record<string, any>;
  integrity_hash: string;
}

export interface DisputeAuditTimeline {
  dispute_id: string;
  total_events: number;
  events: AuditEvent[];
  timeline_hash: string;
}

export interface FullDisputeDetailResponse {
  dispute: DisputeSummaryItem;
  documents: EvidenceDocument[];
  extracted_evidence: ExtractedEvidence[];
  match_results?: MatchingRunResult;
  policy_result?: PolicyResult;
  contest_draft?: ContestDraft;
  preflight?: ContestSubmissionPreflight;
  submission?: ContestSubmissionResponse;
  lifecycle_snapshots: DisputeLifecycleSnapshot[];
  alerts: OperationalAlert[];
}
