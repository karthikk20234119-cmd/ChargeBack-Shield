import React from 'react';
import { Clock } from 'lucide-react';

interface SLAAnalyticsPanelProps {
  data?: any;
}

export const SLAAnalyticsPanel: React.FC<SLAAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <Clock className="w-4 h-4 text-brand-400" />
          <span>SLA Deadline & Compliance Analytics</span>
        </h3>
        <span className="text-[10px] font-mono text-emerald-400">Compliance Rate: {data.compliance_rate || 100}%</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Tracked Items</span>
          <p className="font-bold text-slate-200">{data.total_tracked || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">On Track</span>
          <p className="font-bold text-emerald-400">{data.on_track_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Due Soon</span>
          <p className="font-bold text-amber-400">{data.due_soon_count || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">SLA Breaches</span>
          <p className={`font-bold ${(data.overdue_count || 0) > 0 ? 'text-rose-400' : 'text-slate-300'}`}>{data.overdue_count || 0}</p>
        </div>
      </div>
    </div>
  );
};
