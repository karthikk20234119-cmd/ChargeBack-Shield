import React from 'react';
import { DisputeSummaryItem } from '../../api/types';
import { StatusBadge } from '../ui/StatusBadge';
import { PolicyDecisionBadge } from '../ui/PolicyDecisionBadge';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

interface ReviewHeaderProps {
  dispute: DisputeSummaryItem;
  policyDecision?: string;
  isApproved?: boolean;
}

export const ReviewHeader: React.FC<ReviewHeaderProps> = ({ dispute, policyDecision, isApproved }) => {
  return (
    <div className="glass-panel p-5 space-y-4 border-l-4 border-l-brand-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 font-mono text-xs text-slate-400">
            <span>Dispute #{dispute.id}</span>
            <span>•</span>
            <span>Payment: {dispute.payment_id}</span>
            <span>•</span>
            <span>Reason Code: {dispute.reason_code}</span>
          </div>

          <h2 className="text-xl font-extrabold text-slate-100 font-mono mt-1 flex items-center gap-3">
            <span>₹{(dispute.amount / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })} {dispute.currency}</span>
            <StatusBadge status={dispute.status} />
          </h2>
        </div>

        <div className="flex items-center gap-3">
          {policyDecision && <PolicyDecisionBadge decision={policyDecision} />}

          {isApproved && (
            <Link
              to={`/disputes/${dispute.id}`}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg shadow-lg glow-emerald transition-all flex items-center gap-1.5"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Proceed to Preflight Authorization →</span>
            </Link>
          )}
        </div>
      </div>

      {/* Lifecycle Stage Status Pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-[11px] font-mono">
        <div className="p-2 bg-slate-950/60 rounded border border-slate-900 flex justify-between items-center">
          <span className="text-slate-400">Draft Status:</span>
          <StatusBadge status={dispute.draft_status} size="sm" />
        </div>
        <div className="p-2 bg-slate-950/60 rounded border border-slate-900 flex justify-between items-center">
          <span className="text-slate-400">Review Status:</span>
          <StatusBadge status={dispute.review_status} size="sm" />
        </div>
        <div className="p-2 bg-slate-950/60 rounded border border-slate-900 flex justify-between items-center">
          <span className="text-slate-400">Preflight:</span>
          <StatusBadge status={dispute.preflight_status} size="sm" />
        </div>
        <div className="p-2 bg-slate-950/60 rounded border border-slate-900 flex justify-between items-center">
          <span className="text-slate-400">Submission:</span>
          <StatusBadge status={dispute.submission_status} size="sm" />
        </div>
      </div>
    </div>
  );
};
