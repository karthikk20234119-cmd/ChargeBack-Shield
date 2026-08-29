import React from 'react';
import { RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { ObservabilityMetricsResponse } from '../../api/types';

interface ReconciliationHealthPanelProps {
  metrics: ObservabilityMetricsResponse;
}

export const ReconciliationHealthPanel: React.FC<ReconciliationHealthPanelProps> = ({ metrics }) => {
  const { reconciliation } = metrics;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
        <RefreshCw className="w-4 h-4 text-emerald-400" />
        Reconciliation & Lifecycle Sync Health
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">RECONCILIATION SUCCESS</span>
          <div className="text-lg font-bold text-emerald-400">{reconciliation.success}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">PENDING UNKNOWN</span>
          <div className="text-lg font-bold text-amber-400">{reconciliation.unknown}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">LIFECYCLE SYNCS</span>
          <div className="text-lg font-bold text-slate-100">{reconciliation.lifecycle_syncs}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">SYNC FAILURES</span>
          <div className="text-lg font-bold text-slate-100">{reconciliation.sync_failed}</div>
        </div>
      </div>
    </div>
  );
};
