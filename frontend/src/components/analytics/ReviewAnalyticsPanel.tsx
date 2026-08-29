import React from 'react';
import { UserCheck } from 'lucide-react';

interface ReviewAnalyticsPanelProps {
  data?: any;
}

export const ReviewAnalyticsPanel: React.FC<ReviewAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-brand-400" />
          <span>Contest Draft & Human Review Workload Analytics</span>
        </h3>
        <span className="text-[10px] font-mono text-emerald-400">Approval Rate: {data.approval_rate || 0}%</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Drafts Generated</span>
          <p className="font-bold text-slate-200">{data.generated_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Pending Review</span>
          <p className="font-bold text-amber-400">{data.pending_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Approved Drafts</span>
          <p className="font-bold text-emerald-400">{data.approved_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Rejected Drafts</span>
          <p className="font-bold text-rose-400">{data.rejected_count || 0}</p>
        </div>
      </div>
    </div>
  );
};
