import React from 'react';
import { AnalyticsSummary } from '../../api/types';
import { Lightbulb, CheckCircle2 } from 'lucide-react';

interface ManagementInsightsProps {
  summary?: AnalyticsSummary | null;
}

export const ManagementInsights: React.FC<ManagementInsightsProps> = ({ summary }) => {
  if (!summary) return null;

  const insights = [
    `Human review workload is currently ${summary.policy_review_rate || 0}% of all processed disputes.`,
    `${summary.submission_success_rate || 0}% of eligible contest submissions successfully reached Razorpay.`,
    `${summary.unknown_submission_count || 0} disputes require read-only status reconciliation.`,
    `Platform dispute win rate stands at ${summary.win_rate || 0}% based on verified lifecycle outcomes.`,
  ];

  return (
    <div className="glass-panel p-6 space-y-4 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Lightbulb className="w-4 h-4 text-amber-400" />
          <span>Deterministic Management Insights</span>
        </h3>
        <span className="text-[10px] text-emerald-400">100% Non-LLM Fact-Based</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {insights.map((insight, idx) => (
          <div key={idx} className="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
            <p className="text-slate-200 font-sans text-xs leading-relaxed">{insight}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
