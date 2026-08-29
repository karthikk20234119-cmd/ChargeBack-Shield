import React from 'react';
import { Send, AlertTriangle } from 'lucide-react';

export const SubmissionPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Controlled Contest Submission & Reconciliation
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Single-submission boundary execution, idempotency key enforcement & read-only status reconciliation
        </p>
      </div>

      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center gap-3 p-4 bg-amber-950/60 border border-amber-800/80 rounded-xl">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          <div className="text-xs">
            <h4 className="font-bold text-amber-200">No Blind Retries Guarantee</h4>
            <p className="text-amber-300/80">If a submission outcome is UNKNOWN, the system NEVER performs automated retry submissions. Resolution requires read-only status reconciliation.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
