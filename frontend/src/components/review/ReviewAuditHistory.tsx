import React from 'react';
import { History, CheckCircle2, UserCheck } from 'lucide-react';

interface ReviewAuditHistoryProps {
  history?: any[];
}

export const ReviewAuditHistory: React.FC<ReviewAuditHistoryProps> = ({ history = [] }) => {
  if (history.length === 0) {
    return (
      <div className="glass-panel p-5 text-center text-xs text-slate-400 font-mono">
        No previous review audit records found for this dispute.
      </div>
    );
  }

  return (
    <div className="glass-panel p-5 space-y-4 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
          <History className="w-4 h-4 text-brand-400" />
          <span>Human Review Audit Log History ({history.length})</span>
        </h3>
      </div>

      <div className="space-y-3">
        {history.map((h, i) => (
          <div key={i} className="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-1 text-xs">
            <div className="flex items-center justify-between font-bold">
              <span className="text-emerald-400">Decision: {h.decision || 'REVIEW_RECORDED'}</span>
              <span className="text-slate-500 text-[10px]">{h.timestamp || new Date().toLocaleString()}</span>
            </div>
            <div className="text-[11px] text-slate-400">
              Reviewer: <span className="text-slate-200">{h.reviewer_reference || 'merchant_admin'}</span> • Previous: <span className="text-slate-300">{h.previous_review_status || 'PENDING_REVIEW'}</span> ➔ New: <span className="text-indigo-400">{h.new_review_status || 'APPROVED'}</span>
            </div>
            {h.comment && <p className="text-slate-300 font-sans text-xs pt-1">{h.comment}</p>}
          </div>
        ))}
      </div>
    </div>
  );
};
