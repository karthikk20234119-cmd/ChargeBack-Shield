import React from 'react';
import { ShieldCheck, Database, HardDrive, Lock } from 'lucide-react';
import { ObservabilitySummaryResponse } from '../../api/types';

interface SystemHealthPanelProps {
  summary: ObservabilitySummaryResponse;
}

export const SystemHealthPanel: React.FC<SystemHealthPanelProps> = ({ summary }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>SERVICE STATUS</span>
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="text-2xl font-extrabold text-slate-100">{summary.service}</div>
        <p className="text-xs text-emerald-400 font-mono">Environment: {summary.environment}</p>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>DATABASE DEPENDENCY</span>
          <Database className="w-4 h-4 text-brand-400" />
        </div>
        <div className="text-2xl font-extrabold text-slate-100">{summary.dependencies.database.status}</div>
        <p className="text-xs text-slate-400">{summary.dependencies.database.details}</p>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>EVIDENCE STORAGE</span>
          <HardDrive className="w-4 h-4 text-purple-400" />
        </div>
        <div className="text-2xl font-extrabold text-slate-100">{summary.dependencies.storage.status}</div>
        <p className="text-xs text-slate-400">{summary.dependencies.storage.details}</p>
      </div>
    </div>
  );
};
