import React from 'react';
import { AnalyticsSummary } from '../../api/types';
import { BarChart3, Trophy, FileText, Send, ShieldCheck, AlertTriangle, Lock } from 'lucide-react';

interface AnalyticsHeaderProps {
  summary?: AnalyticsSummary | null;
  loading: boolean;
}

export const AnalyticsHeader: React.FC<AnalyticsHeaderProps> = ({ summary, loading }) => {
  return (
    <div className="glass-panel p-6 space-y-5 border-l-4 border-l-indigo-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>EXECUTIVE INTELLIGENCE DASHBOARD</span>
            <span>•</span>
            <span className="text-emerald-400">STRICTLY READ-ONLY</span>
            <span>•</span>
            <span>REST AGNOSTIC</span>
          </div>

          <h1 className="text-2xl font-extrabold text-slate-100 font-mono mt-1 flex items-center gap-3">
            <span>Executive Analytics & Dispute Metrics</span>
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-950 text-indigo-300 border border-indigo-800 glow-indigo">
              PROD INTELLIGENCE
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800">
          <Lock className="w-4 h-4 text-emerald-400" />
          <span>Financial Identity & Policy Decision Immutability Active</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Total Disputes</span>
          <p className="text-lg font-bold text-slate-100">{summary?.total_disputes || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Win Rate</span>
          <p className="text-lg font-bold text-emerald-400">{summary?.win_rate || 0}%</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Policy Review Rate</span>
          <p className="text-lg font-bold text-amber-400">{summary?.policy_review_rate || 0}%</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Draft Approval</span>
          <p className="text-lg font-bold text-indigo-400">{summary?.draft_approval_rate || 0}%</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Submission Success</span>
          <p className="text-lg font-bold text-brand-400">{summary?.submission_success_rate || 0}%</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Unknown Submissions</span>
          <p className={`text-lg font-bold ${(summary?.unknown_submission_count || 0) > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
            {summary?.unknown_submission_count || 0}
          </p>
        </div>
      </div>
    </div>
  );
};
