import React from 'react';
import { Send, AlertTriangle } from 'lucide-react';

interface SubmissionAnalyticsPanelProps {
  data?: any;
}

export const SubmissionAnalyticsPanel: React.FC<SubmissionAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  const unknownCount = data.unknown_count || 0;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <Send className="w-4 h-4 text-indigo-400" />
          <span>Contest Submission & Reconciliation Analytics</span>
        </h3>
        <span className="text-[10px] font-mono text-brand-400">Success Rate: {data.success_rate || 0}%</span>
      </div>

      {unknownCount > 0 && (
        <div className="p-3.5 bg-amber-950/60 border border-amber-800/80 rounded-xl text-amber-200 text-xs font-mono flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">UNKNOWN Submissions Notice ({unknownCount}):</span> Reconciliation required — submission state must be verified before further action. Automated retry submissions are strictly prohibited.
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Preflight Authorized</span>
          <p className="font-bold text-emerald-400">{data.ready_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Submitted to Razorpay</span>
          <p className="font-bold text-brand-400">{data.submitted_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Submission Failures</span>
          <p className="font-bold text-rose-400">{data.failed_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Unknown / Reconciling</span>
          <p className={`font-bold ${unknownCount > 0 ? 'text-amber-400' : 'text-slate-400'}`}>{unknownCount}</p>
        </div>
      </div>
    </div>
  );
};
