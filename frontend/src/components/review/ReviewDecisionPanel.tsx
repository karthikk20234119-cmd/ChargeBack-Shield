import React, { useState } from 'react';
import { UserCheck, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

interface ReviewDecisionPanelProps {
  draftStatus?: string;
  reviewStatus?: string;
  submitting?: boolean;
  onOpenConfirmation: (decision: 'APPROVE' | 'REJECT', reviewerRef: string, comment: string) => void;
}

export const ReviewDecisionPanel: React.FC<ReviewDecisionPanelProps> = ({
  draftStatus,
  reviewStatus,
  submitting,
  onOpenConfirmation,
}) => {
  const [reviewerRef, setReviewerRef] = useState('merchant_admin');
  const [comment, setComment] = useState('');

  const isBlocked = draftStatus === 'BLOCKED';
  const isTerminal = reviewStatus === 'APPROVED' || reviewStatus === 'REJECTED';

  return (
    <div className="glass-panel p-5 space-y-4 border-l-4 border-l-brand-500">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-brand-400" />
          <span>Human Review Decision Panel</span>
        </h3>
        {isTerminal && (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700">
            TERMINAL STATE LOCKED ({reviewStatus})
          </span>
        )}
      </div>

      {isTerminal ? (
        <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 text-xs font-mono text-slate-300 space-y-1">
          <p className="font-bold text-emerald-400">Review Decision Executed: {reviewStatus}</p>
          <p className="text-slate-400">Review decision controls are locked for terminal states. Re-evaluations require generating a new contest draft.</p>
        </div>
      ) : (
        <div className="space-y-4 font-mono text-xs">
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Reviewer Reference ID</label>
            <input
              type="text"
              value={reviewerRef}
              onChange={(e) => setReviewerRef(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500"
            />
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Optional Merchant Feedback / Notes</label>
            <textarea
              rows={3}
              placeholder="Enter reviewer feedback or audit notes..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 font-sans focus:outline-none focus:border-brand-500"
            />
          </div>

          {isBlocked && (
            <div className="p-3 bg-rose-950/80 border border-rose-800 rounded-lg text-xs text-rose-300 flex items-center gap-2 font-mono">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>Approval unavailable because this draft is blocked by policy.</span>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              disabled={isBlocked || submitting}
              onClick={() => onOpenConfirmation('APPROVE', reviewerRef, comment)}
              className="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-30 text-white text-xs font-bold rounded-xl shadow-lg glow-emerald transition-all flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>APPROVE CONTEST DRAFT</span>
            </button>

            <button
              disabled={submitting}
              onClick={() => onOpenConfirmation('REJECT', reviewerRef, comment)}
              className="flex-1 py-3 bg-rose-950 hover:bg-rose-900 border border-rose-800 text-rose-300 text-xs font-bold rounded-xl shadow-lg glow-rose transition-all flex items-center justify-center gap-2"
            >
              <XCircle className="w-4 h-4" />
              <span>REJECT CONTEST DRAFT</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
