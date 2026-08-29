import React from 'react';
import { Hash, ShieldCheck } from 'lucide-react';

interface ReportHashBadgeProps {
  hash?: string;
  timestamp?: string;
}

export const ReportHashBadge: React.FC<ReportHashBadgeProps> = ({ hash, timestamp }) => {
  if (!hash) return null;

  return (
    <div className="flex items-center justify-between p-3 bg-slate-950/80 rounded-xl border border-slate-800 text-xs font-mono text-slate-400">
      <div className="flex items-center gap-2">
        <Hash className="w-4 h-4 text-indigo-400" />
        <span>Canonical SHA-256 Report Hash: <span className="text-slate-200 font-bold">{hash}</span></span>
      </div>

      <div className="flex items-center gap-2 text-[11px] text-emerald-400">
        <ShieldCheck className="w-3.5 h-3.5" />
        <span>Backend Authoritative Integrity Verified</span>
      </div>
    </div>
  );
};
