import React from 'react';
import { OperationalHealthResponse } from '../../api/types';
import { ShieldCheck, Activity } from 'lucide-react';

interface OperationalHealthPanelProps {
  health?: OperationalHealthResponse | null;
}

export const OperationalHealthPanel: React.FC<OperationalHealthPanelProps> = ({ health }) => {
  if (!health) return null;

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>System Health Monitor</span>
        </h3>
        <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
          {health.status}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Active Disputes</span>
          <p className="font-bold text-slate-200">{health.active_disputes}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Open Alerts</span>
          <p className="font-bold text-amber-400">{health.open_alerts}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Critical Alerts</span>
          <p className="font-bold text-rose-400">{health.critical_alerts}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Unknown Submissions</span>
          <p className="font-bold text-indigo-400">{health.unknown_submissions}</p>
        </div>
      </div>
    </div>
  );
};
