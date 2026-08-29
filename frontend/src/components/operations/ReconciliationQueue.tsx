import React from 'react';
import { ReconciliationRequiredDispute } from '../../api/operations';
import { AlertTriangle, ArrowRight, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

interface ReconciliationQueueProps {
  disputes: ReconciliationRequiredDispute[];
}

export const ReconciliationQueue: React.FC<ReconciliationQueueProps> = ({ disputes }) => {
  return (
    <div className="glass-panel p-6 space-y-4 border-l-4 border-l-amber-500">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          <span>Reconciliation Work Queue ({disputes.length})</span>
        </h3>
        <span className="text-[10px] font-mono text-amber-300">Read-Only Status Resolution</span>
      </div>

      <div className="p-3.5 bg-amber-950/60 border border-amber-800/80 rounded-xl text-amber-200 text-xs font-mono flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold">No Retry Submission Guarantee:</span> For UNKNOWN submissions, submission state is ambiguous. Reconciliation is required before any further action.
        </div>
      </div>

      {disputes.length === 0 ? (
        <div className="p-6 text-center text-xs text-slate-500 font-mono">
          No UNKNOWN submission states awaiting reconciliation.
        </div>
      ) : (
        <div className="space-y-3 font-mono text-xs">
          {disputes.map((item, idx) => (
            <div key={idx} className="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between font-bold">
                <span className="text-brand-400">Dispute #{item.dispute_id}</span>
                <span className="text-amber-400 text-[10px]">{item.submission_status}</span>
              </div>

              <div className="text-[11px] text-slate-400 font-sans">{item.required_action}</div>

              <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                <span className="text-slate-500 text-[10px]">Age: {item.age_hours.toFixed(1)}h</span>
                <Link
                  to={`/submission`}
                  className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline font-semibold font-sans"
                >
                  <span>Reconcile Status</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
