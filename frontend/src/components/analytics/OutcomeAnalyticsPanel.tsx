import React from 'react';
import { StatusBadge } from '../ui/StatusBadge';
import { PieChart, Trophy } from 'lucide-react';

interface OutcomeAnalyticsPanelProps {
  data?: any;
}

export const OutcomeAnalyticsPanel: React.FC<OutcomeAnalyticsPanelProps> = ({ data }) => {
  if (!data) {
    return (
      <div className="glass-panel p-6 text-center text-xs text-slate-400 font-mono">
        Loading Dispute Outcome Analytics...
      </div>
    );
  }

  const outcomes = [
    { key: 'WON', label: 'Won Disputes', count: data.won || 0, color: 'text-emerald-400', bg: 'bg-emerald-950/40 border-emerald-800' },
    { key: 'LOST', label: 'Lost Disputes', count: data.lost || 0, color: 'text-rose-400', bg: 'bg-rose-950/40 border-rose-800' },
    { key: 'UNDER_REVIEW', label: 'Under Review', count: data.under_review || 0, color: 'text-indigo-400', bg: 'bg-indigo-950/40 border-indigo-800' },
    { key: 'ACTION_REQUIRED', label: 'Action Required', count: data.action_required || 0, color: 'text-amber-400', bg: 'bg-amber-950/40 border-amber-800' },
    { key: 'PENDING', label: 'Pending Processing', count: data.pending || 0, color: 'text-slate-300', bg: 'bg-slate-900/60 border-slate-800' },
    { key: 'UNKNOWN', label: 'Unknown Outcome', count: data.unknown || 0, color: 'text-slate-500', bg: 'bg-slate-950 border-slate-900' },
  ];

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <PieChart className="w-4 h-4 text-brand-400" />
          <span>Dispute Outcome Distribution Analytics</span>
        </h3>
        <span className="text-[10px] font-mono text-emerald-400 font-bold">Win Rate: {data.win_rate || 0}%</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
        {outcomes.map((o) => (
          <div key={o.key} className={`p-3.5 rounded-xl border ${o.bg} space-y-1`}>
            <div className="flex items-center justify-between">
              <StatusBadge status={o.key} size="sm" />
            </div>
            <p className={`text-xl font-bold ${o.color}`}>{o.count}</p>
            <span className="text-[10px] text-slate-400 font-sans block">{o.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
