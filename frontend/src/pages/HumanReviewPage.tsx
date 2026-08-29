import React, { useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import { DisputeSummaryItem, ContestDraft, EvidenceDocument } from '../api/types';
import { SkeletonLoader } from '../components/ui/SkeletonLoader';

import { ReviewHeader } from '../components/review/ReviewHeader';
import { ReviewQueue } from '../components/review/ReviewQueue';
import { EvidenceExplorer } from '../components/review/EvidenceExplorer';
import { EvidencePreview } from '../components/review/EvidencePreview';
import { FactViewer } from '../components/review/FactViewer';
import { ProvenanceInspector } from '../components/review/ProvenanceInspector';
import { MatchInspector } from '../components/review/MatchInspector';
import { PolicyExplanation } from '../components/review/PolicyExplanation';
import { ContestDraftViewer } from '../components/review/ContestDraftViewer';
import { ReviewFlags } from '../components/review/ReviewFlags';
import { ReviewDecisionPanel } from '../components/review/ReviewDecisionPanel';
import { ReviewConfirmationModal } from '../components/review/ReviewConfirmationModal';
import { ReviewAuditHistory } from '../components/review/ReviewAuditHistory';
import { StaleDraftBanner } from '../components/review/StaleDraftBanner';

interface HumanReviewPageProps {
  onShowToast: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const HumanReviewPage: React.FC<HumanReviewPageProps> = ({ onShowToast }) => {
  const [disputes, setDisputes] = useState<DisputeSummaryItem[]>([]);
  const [selectedDisputeId, setSelectedDisputeId] = useState<string>('');
  const [disputeDetail, setDisputeDetail] = useState<any | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<EvidenceDocument | null>(null);
  const [reviewHistory, setReviewHistory] = useState<any[]>([]);

  const [loadingQueue, setLoadingQueue] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isStale, setIsStale] = useState(false);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<'APPROVE' | 'REJECT' | null>(null);
  const [pendingReviewerRef, setPendingReviewerRef] = useState('merchant_admin');
  const [pendingComment, setPendingComment] = useState('');

  const loadQueue = async () => {
    setLoadingQueue(true);
    try {
      const res = await api.getDisputes({ page: 1, page_size: 50 });
      const items = res.disputes || [];
      setDisputes(items);
      if (items.length > 0 && !selectedDisputeId) {
        setSelectedDisputeId(items[0].id);
      }
    } catch {
      // safe fallback
    } finally {
      setLoadingQueue(false);
    }
  };

  const loadDisputeDetail = async (id: string) => {
    if (!id) return;
    setLoadingDetail(true);
    setIsStale(false);
    try {
      const det = await api.getDisputeDetail(id);
      setDisputeDetail(det);
      if (det.documents && det.documents.length > 0) {
        setSelectedDoc(det.documents[0]);
      } else {
        setSelectedDoc(null);
      }
    } catch (err: any) {
      onShowToast('error', 'Detail Load Failed', err.message);
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  useEffect(() => {
    if (selectedDisputeId) {
      loadDisputeDetail(selectedDisputeId);
    }
  }, [selectedDisputeId]);

  const handleOpenConfirmation = (decision: 'APPROVE' | 'REJECT', reviewerRef: string, comment: string) => {
    setPendingDecision(decision);
    setPendingReviewerRef(reviewerRef);
    setPendingComment(comment);
    setModalOpen(true);
  };

  const handleConfirmDecision = async () => {
    if (!selectedDisputeId || !pendingDecision) return;
    setModalOpen(false);
    setSubmitting(true);
    try {
      // SECURITY CONTRACT GUARANTEE: Send ONLY decision, comment, and reviewer_reference.
      const res = await api.submitDraftReview(selectedDisputeId, {
        decision: pendingDecision,
        comment: pendingComment.trim() || undefined,
        reviewer_reference: pendingReviewerRef.trim() || 'merchant_admin',
      });

      onShowToast(
        'success',
        `Draft Review ${res.decision}`,
        `Review decision recorded. New Status: ${res.new_review_status}`
      );

      // Record in local audit history
      setReviewHistory((prev) => [res, ...prev]);

      // Refresh data from authoritative backend
      await loadDisputeDetail(selectedDisputeId);
      await loadQueue();
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 409) {
        setIsStale(true);
        onShowToast(
          'warning',
          'Draft Changed (409 Conflict)',
          'Evidence or policy inputs changed since review page opened. Please refresh latest draft.'
        );
      } else {
        onShowToast('error', 'Review Submission Failed', err.message || 'Error communicating with review server');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingQueue) return <SkeletonLoader type="dashboard" />;

  const currentDispute = disputeDetail?.dispute || disputes.find((d) => d.id === selectedDisputeId);
  const docs = disputeDetail?.documents || [];
  const extracted = disputeDetail?.extracted_evidence || [];
  const matching = disputeDetail?.match_results;
  const policy = disputeDetail?.policy_result;
  const draft = disputeDetail?.contest_draft;
  const flags = draft?.review_flags?.flags || [];

  const isApproved = currentDispute?.review_status === 'APPROVED';
  const isBlocked = draft?.status === 'BLOCKED' || policy?.decision === 'NOT_ELIGIBLE';

  return (
    <div className="space-y-6">
      {/* Title & Page Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Human Review & Evidence Investigation Workspace
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Investigate facts, verify provenance, inspect rule evaluation & submit safe merchant review decisions
        </p>
      </div>

      {/* HTTP 409 Stale Draft Banner */}
      {isStale && <StaleDraftBanner onRefresh={() => loadDisputeDetail(selectedDisputeId)} />}

      {/* Main 3-Column Layout Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Column 1: Review Queue Sidebar (3 cols) */}
        <div className="lg:col-span-3">
          <ReviewQueue
            disputes={disputes}
            selectedId={selectedDisputeId}
            onSelect={setSelectedDisputeId}
          />
        </div>

        {/* Column 2 & 3: Main Investigation & Decision Area (9 cols) */}
        <div className="lg:col-span-9 space-y-6">
          {loadingDetail || !currentDispute ? (
            <SkeletonLoader type="card" />
          ) : (
            <>
              {/* Persistent Header */}
              <ReviewHeader
                dispute={currentDispute}
                policyDecision={policy?.decision}
                isApproved={isApproved}
              />

              {/* Review Flags & Warnings */}
              <ReviewFlags flags={flags} isBlocked={isBlocked} />

              {/* 2-Column Sub-Layout: Evidence vs Contest Draft */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {/* Left Sub-Column: Evidence Explorer, Preview & Facts */}
                <div className="space-y-6">
                  <EvidenceExplorer
                    documents={docs}
                    selectedDocId={selectedDoc?.id}
                    onSelectDoc={setSelectedDoc}
                  />

                  <EvidencePreview document={selectedDoc} />

                  <FactViewer evidenceList={extracted} />
                </div>

                {/* Right Sub-Column: Matcher, Policy, Draft & Provenance */}
                <div className="space-y-6">
                  <PolicyExplanation policy={policy} />

                  <MatchInspector matching={matching} />

                  <ContestDraftViewer draft={draft} />

                  <ProvenanceInspector argumentsList={draft?.factual_arguments?.arguments || []} />
                </div>
              </div>

              {/* Decision Panel & Audit Log */}
              <ReviewDecisionPanel
                draftStatus={draft?.status}
                reviewStatus={currentDispute.review_status}
                submitting={submitting}
                onOpenConfirmation={handleOpenConfirmation}
              />

              <ReviewAuditHistory history={reviewHistory} />
            </>
          )}
        </div>
      </div>

      {/* Confirmation Modal */}
      <ReviewConfirmationModal
        isOpen={modalOpen}
        decision={pendingDecision}
        disputeId={selectedDisputeId}
        reviewerRef={pendingReviewerRef}
        comment={pendingComment}
        onConfirm={handleConfirmDecision}
        onCancel={() => setModalOpen(false)}
      />
    </div>
  );
};
