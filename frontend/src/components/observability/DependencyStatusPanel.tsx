import React from 'react';
import { Database, HardDrive, ShieldCheck } from 'lucide-react';
import { ObservabilitySummaryResponse } from '../../api/types';

interface DependencyStatusPanelProps {
  summary: ObservabilitySummaryResponse;
}

export const DependencyStatusPanel: React.FC<DependencyStatusPanelProps> = ({ summary }) => {
  const { dependencies } = summary;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
        <Database className="w-4 h-4 text-brand-400" />
        Local Dependency & Subsystem Health
      </h3>

      <div className="space-y-3 text-xs">
        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="w-4 h-4 text-brand-400" />
            <div>
              <div className="font-bold text-slate-200">SQLite / Database Engine</div>
              <div className="text-[11px] text-slate-400">{dependencies.database.details}</div>
            </div>
          </div>
          <span className="px-2.5 py-1 bg-emerald-950/80 text-emerald-400 border border-emerald-700/60 rounded font-mono text-[11px]">
            {dependencies.database.status}
          </span>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HardDrive className="w-4 h-4 text-purple-400" />
            <div>
              <div className="font-bold text-slate-200">Evidence File Storage</div>
              <div className="text-[11px] text-slate-400">{dependencies.storage.details}</div>
            </div>
          </div>
          <span className="px-2.5 py-1 bg-emerald-950/80 text-emerald-400 border border-emerald-700/60 rounded font-mono text-[11px]">
            {dependencies.storage.status}
          </span>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <div>
              <div className="font-bold text-slate-200">Razorpay Integration Gateway</div>
              <div className="text-[11px] text-slate-400">{dependencies.razorpay_gateway.details}</div>
            </div>
          </div>
          <span className="px-2.5 py-1 bg-emerald-950/80 text-emerald-400 border border-emerald-700/60 rounded font-mono text-[11px]">
            {dependencies.razorpay_gateway.status}
          </span>
        </div>
      </div>
    </div>
  );
};
