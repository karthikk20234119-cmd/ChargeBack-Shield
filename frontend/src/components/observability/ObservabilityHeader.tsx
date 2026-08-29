import React from 'react';
import { Activity, ShieldCheck, RefreshCw } from 'lucide-react';

interface ObservabilityHeaderProps {
  status: 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN';
  lastUpdated: string;
  onRefresh: () => void;
}

export const ObservabilityHeader: React.FC<ObservabilityHeaderProps> = ({
  status,
  lastUpdated,
  onRefresh,
}) => {
  const getStatusBadge = () => {
    switch (status) {
      case 'HEALTHY':
        return <span className="px-3 py-1 bg-emerald-950/80 text-emerald-400 border border-emerald-700/60 rounded-full text-xs font-mono font-semibold">● HEALTHY</span>;
      case 'DEGRADED':
        return <span className="px-3 py-1 bg-amber-950/80 text-amber-400 border border-amber-700/60 rounded-full text-xs font-mono font-semibold">▲ DEGRADED</span>;
      default:
        return <span className="px-3 py-1 bg-rose-950/80 text-rose-400 border border-rose-700/60 rounded-full text-xs font-mono font-semibold">✖ CRITICAL</span>;
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <div className="p-3 bg-brand-600/20 border border-brand-500/30 rounded-xl text-brand-400">
          <Activity className="w-8 h-8" />
        </div>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white tracking-tight">System Health & Reliability Command Center</h1>
            {getStatusBadge()}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Real-time request performance, submission reliability, error rates, SLA tracking, and local dependency monitoring.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 self-end md:self-center">
        <span className="text-[11px] font-mono text-slate-400">Last updated: {lastUpdated}</span>
        <button
          onClick={onRefresh}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>
    </div>
  );
};
