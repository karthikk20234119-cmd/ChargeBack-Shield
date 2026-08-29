import React from 'react';
import { MatchStatusBadge } from '../ui/MatchStatusBadge';
import { GitCompare } from 'lucide-react';

interface MatchingAnalyticsPanelProps {
  data?: any;
}

export const MatchingAnalyticsPanel: React.FC<MatchingAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  const matchTypes = [
    { key: 'MATCH', label: 'Match', count: data.match_count || 0 },
    { key: 'MISMATCH', label: 'Mismatch', count: data.mismatch_count || 0 },
    { key: 'MISSING', label: 'Missing', count: data.missing_count || 0 },
    { key: 'AMBIGUOUS', label: 'Ambiguous', count: data.ambiguous_count || 0 },
    { key: 'UNVERIFIABLE', label: 'Unverifiable', count: data.unverifiable_count || 0 },
    { key: 'CROSS_DOCUMENT_CONFLICT', label: 'Conflicts', count: data.conflict_count || 0 },
  ];

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-brand-400" />
          <span>Deterministic Matching Analytics</span>
        </h3>
        <span className="text-[10px] font-mono text-indigo-400">Match Quality: {data.match_rate || 0}%</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
        {matchTypes.map((m) => (
          <div key={m.key} className="p-3 bg-slate-950/60 rounded-xl border border-slate-900 space-y-1">
            <MatchStatusBadge status={m.key} />
            <p className="text-lg font-bold text-slate-100 mt-1">{m.count}</p>
            <span className="text-[10px] text-slate-400 font-sans block">{m.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
