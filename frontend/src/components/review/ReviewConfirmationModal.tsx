import React from 'react';
import { Modal } from '../ui/Modal';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';

interface ReviewConfirmationModalProps {
  isOpen: boolean;
  decision: 'APPROVE' | 'REJECT' | null;
  disputeId: string;
  reviewerRef: string;
  comment?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ReviewConfirmationModal: React.FC<ReviewConfirmationModalProps> = ({
  isOpen,
  decision,
  disputeId,
  reviewerRef,
  comment,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen || !decision) return null;

  const isApprove = decision === 'APPROVE';

  return (
    <Modal
      isOpen={isOpen}
      onClose={onCancel}
      title={isApprove ? 'Confirm Draft Approval' : 'Confirm Draft Rejection'}
      maxWidth="md"
    >
      <div className="space-y-4 font-mono text-xs">
        <div className={`p-4 rounded-xl border flex items-start gap-3 ${
          isApprove ? 'bg-emerald-950/60 border-emerald-800 text-emerald-200' : 'bg-rose-950/60 border-rose-800 text-rose-200'
        }`}>
          {isApprove ? (
            <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
          ) : (
            <XCircle className="w-6 h-6 text-rose-400 shrink-0 mt-0.5" />
          )}
          <div className="space-y-1">
            <h4 className="font-bold text-sm font-sans">
              {isApprove ? `Approve contest draft for Dispute #${disputeId}?` : `Reject contest draft for Dispute #${disputeId}?`}
            </h4>
            <p className="text-[11px] opacity-90 font-sans">
              {isApprove
                ? 'This action marks the contest draft as APPROVED and enables proceeding to the Preflight Authorization Gate.'
                : 'This action marks the contest draft as REJECTED. The draft will not proceed to submission.'}
            </p>
          </div>
        </div>

        <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1 text-[11px]">
          <div>Reviewer Ref: <span className="text-slate-200 font-bold">{reviewerRef}</span></div>
          {comment && <div>Comment: <span className="text-slate-300 font-sans">{comment}</span></div>}
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-sans text-xs font-semibold rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-5 py-2 text-white font-sans text-xs font-bold rounded-lg shadow-lg transition-all ${
              isApprove ? 'bg-emerald-600 hover:bg-emerald-500 glow-emerald' : 'bg-rose-600 hover:bg-rose-500 glow-rose'
            }`}
          >
            {isApprove ? 'Confirm Approval' : 'Confirm Rejection'}
          </button>
        </div>
      </div>
    </Modal>
  );
};
