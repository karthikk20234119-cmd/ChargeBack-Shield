import React from 'react';
import { PolicyDecisionBadge } from '../ui/PolicyDecisionBadge';
import { ShieldCheck } from 'lucide-react';

interface PolicyAnalyticsPanelProps {
  data?: any;
}

export const PolicyAnalyticsPanel: React.FC<PolicyAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Deterministic Policy Engine Analytics</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">Policy Version: {data.policy_version || 'v1.0'}</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
        <div className="p-4 bg-emerald-950/40 border border-emerald-800/60 rounded-xl space-y-2">
          <PolicyDecisionBadge decision="ELIGIBLE" />
          <p className="text-2xl font-bold text-emerald-400">{data.eligible_count || 0}</p>
          <span className="text-[11px] text-slate-400 block font-sans">Automated Contest Eligible</span>
        </div>

        <div className="p-4 bg-amber-950/40 border border-amber-800/60 rounded-xl space-y-2">
          <PolicyDecisionBadge decision="HUMAN_REVIEW" />
          <p className="text-2xl font-bold text-amber-400">{data.human_review_count || 0}</p>
          <span className="text-[11px] text-slate-400 block font-sans">Human Investigation Required</span>
        </div>

        <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-xl space-y-2">
          <PolicyDecisionBadge decision="NOT_ELIGIBLE" />
          <p className="text-2xl font-bold text-rose-400">{data.not_eligible_count || 0}</p>
          <span className="text-[11px] text-slate-400 block font-sans">Policy Disqualified</span>
        </div>
      </div>
    </div>
  );
};
