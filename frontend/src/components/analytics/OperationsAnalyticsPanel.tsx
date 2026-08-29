import React from 'react';
import { Activity, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

interface OperationsAnalyticsPanelProps {
  data?: any;
}

export const OperationsAnalyticsPanel: React.FC<OperationsAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span>Operational Alert & Workload Analytics</span>
        </h3>

        <Link
          to="/operations"
          className="inline-flex items-center gap-1 text-[11px] text-brand-400 hover:underline font-mono font-semibold"
        >
          <span>Open Operations Command Center</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Open Alerts</span>
          <p className="font-bold text-amber-400">{data.open_alerts || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Critical Alerts</span>
          <p className="font-bold text-rose-400">{data.critical_alerts || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Acknowledged Alerts</span>
          <p className="font-bold text-emerald-400">{data.acknowledged_alerts || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Action Required Workload</span>
          <p className="font-bold text-indigo-400">{data.action_required_count || 0}</p>
        </div>
      </div>
    </div>
  );
};
