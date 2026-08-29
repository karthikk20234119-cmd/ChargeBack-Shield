import React from 'react';
import { Clock, AlertTriangle, CheckCircle } from 'lucide-react';
import { ObservabilitySummaryResponse } from '../../api/types';

interface SLAHealthPanelProps {
  summary: ObservabilitySummaryResponse;
}

export const SLAHealthPanel: React.FC<SLAHealthPanelProps> = ({ summary }) => {
  const { sla_health } = summary;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
        <Clock className="w-4 h-4 text-brand-400" />
        SLA Health & Operational Timelines
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">MONITORED SLAS</span>
          <div className="text-lg font-bold text-slate-100">{sla_health.total_monitored}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-emerald-800/40 rounded-lg space-y-1">
          <span className="text-emerald-400 font-mono">ON TRACK</span>
          <div className="text-lg font-bold text-emerald-400">{sla_health.on_track}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-amber-800/40 rounded-lg space-y-1">
          <span className="text-amber-400 font-mono">DUE SOON</span>
          <div className="text-lg font-bold text-amber-400">{sla_health.due_soon}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-rose-800/40 rounded-lg space-y-1">
          <span className="text-rose-400 font-mono">OVERDUE</span>
          <div className="text-lg font-bold text-rose-400">{sla_health.overdue}</div>
        </div>
      </div>
    </div>
  );
};
