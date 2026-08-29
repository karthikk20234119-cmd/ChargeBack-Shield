import React from 'react';
import { AlertSummaryResponse, OperationalHealthResponse } from '../../api/types';
import { SLAReport } from '../../api/operations';
import { ShieldCheck, Bell, AlertTriangle, Activity, Clock, RefreshCw, Zap } from 'lucide-react';

interface OperationsHeaderProps {
  health?: OperationalHealthResponse | null;
  alertsSummary?: AlertSummaryResponse | null;
  slaReport?: SLAReport | null;
  lastRefreshed: string;
  loading: boolean;
  onRefresh: () => void;
  onDetectAlerts: () => void;
  detecting: boolean;
}

export const OperationsHeader: React.FC<OperationsHeaderProps> = ({
  health,
  alertsSummary,
  slaReport,
  lastRefreshed,
  loading,
  onRefresh,
  onDetectAlerts,
  detecting,
}) => {
  const healthStatus = health?.status || 'HEALTHY';
  const openAlerts = alertsSummary?.open_count || 0;
  const criticalAlerts = alertsSummary?.critical_count || 0;
  const slaBreaches = slaReport?.overdue_count || 0;

  return (
    <div className="glass-panel p-6 space-y-5 border-l-4 border-l-brand-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>OPERATIONS COMMAND CENTER</span>
            <span>•</span>
            <span className="text-emerald-400">REST AGNOSTIC ENGINE</span>
            <span>•</span>
            <span>Refreshed: {lastRefreshed}</span>
          </div>

          <h1 className="text-2xl font-extrabold text-slate-100 font-mono mt-1 flex items-center gap-3">
            <span>SLA & Operational Command Center</span>
            <span className={`px-3 py-1 rounded-full text-xs font-bold border ${
              healthStatus === 'HEALTHY' ? 'bg-emerald-950 text-emerald-300 border-emerald-800 glow-emerald' : 'bg-amber-950 text-amber-300 border-amber-800'
            }`}>
              {healthStatus}
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <button
            disabled={detecting}
            onClick={onDetectAlerts}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-lg glow-indigo transition-all flex items-center gap-1.5"
          >
            <Zap className={`w-4 h-4 ${detecting ? 'animate-bounce' : ''}`} />
            <span>{detecting ? 'Detecting Alerts...' : 'Run Alert Detection'}</span>
          </button>

          <button
            disabled={loading}
            onClick={onRefresh}
            className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Open Alerts</span>
          <p className="text-lg font-bold text-slate-100">{openAlerts}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Critical Severity</span>
          <p className={`text-lg font-bold ${criticalAlerts > 0 ? 'text-rose-400' : 'text-slate-300'}`}>{criticalAlerts}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">SLA Breaches</span>
          <p className={`text-lg font-bold ${slaBreaches > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>{slaBreaches}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Active Disputes</span>
          <p className="text-lg font-bold text-brand-400">{health?.active_disputes || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Unknown Submissions</span>
          <p className="text-lg font-bold text-indigo-400">{health?.unknown_submissions || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-950 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase">Stale Preflights</span>
          <p className="text-lg font-bold text-amber-400">{health?.stale_preflights || 0}</p>
        </div>
      </div>
    </div>
  );
};
