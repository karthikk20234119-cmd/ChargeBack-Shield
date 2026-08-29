import React from 'react';
import { ShieldCheck } from 'lucide-react';

export const PolicyPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Deterministic Policy Engine
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Rule-based policy evaluation for chargeback reason code CB13.1
        </p>
      </div>

      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center gap-3 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          <div className="text-xs">
            <h4 className="font-bold text-slate-200">Policy Evaluation Outcomes</h4>
            <p className="text-slate-400">ELIGIBLE, HUMAN_REVIEW, NOT_ELIGIBLE</p>
          </div>
        </div>
      </div>
    </div>
  );
};
