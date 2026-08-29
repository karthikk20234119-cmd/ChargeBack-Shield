import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface FailureAnalyticsPanelProps {
  data?: any;
}

export const FailureAnalyticsPanel: React.FC<FailureAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  const categories = [
    { label: 'Evidence Extraction Failures', count: data.evidence_failures || 0 },
    { label: 'Fact Matching Conflicts', count: data.matching_failures || 0 },
    { label: 'Policy Disqualifications', count: data.policy_disqualifications || 0 },
    { label: 'Submission Failures', count: data.submission_failures || 0 },
    { label: 'Reconciliation Ambiguities', count: data.reconciliation_ambiguities || 0 },
  ];

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400" />
          <span>Lifecycle Failure & Disqualification Categorization</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">Read-Only Observation Matrix</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3 font-mono text-xs">
        {categories.map((c, i) => (
          <div key={i} className="p-3 bg-slate-950/60 rounded-xl border border-slate-900 space-y-1">
            <span className="text-[10px] text-slate-400 font-sans block">{c.label}</span>
            <p className={`text-xl font-bold ${c.count > 0 ? 'text-rose-400' : 'text-slate-300'}`}>{c.count}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
