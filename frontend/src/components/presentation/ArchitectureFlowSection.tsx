import React from 'react';
import { GitCommit, ArrowRight } from 'lucide-react';

export const ArchitectureFlowSection: React.FC = () => {
  const stages = [
    'Dispute Ingestion',
    'Evidence Integration',
    'Processing',
    'Extraction',
    'Matching',
    'Policy Evaluation',
    'Draft Generation',
    'Human Review',
    'Preflight Authorization',
    'Contest Submission',
    'Reconciliation',
    'Lifecycle Sync',
    'Operations Monitor',
    'Audit Traceability',
    'Analytics Reporting',
  ];

  return (
    <div className="glass-panel p-6 space-y-4 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
          <GitCommit className="w-4 h-4 text-indigo-400" />
          <span>C. End-to-End Architecture Flow</span>
        </h2>
        <span className="text-[10px] text-indigo-400 font-bold">15-STAGE DETERMINISTIC PIPELINE</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {stages.map((stg, i) => (
          <div key={i} className="p-3 bg-slate-950/60 rounded-xl border border-slate-900 space-y-1 text-center relative group">
            <span className="text-[9px] text-slate-500 font-bold block">STAGE {i + 1}</span>
            <span className="font-bold text-slate-200 text-[11px] block truncate">{stg}</span>
            {i < stages.length - 1 && (
              <ArrowRight className="w-3.5 h-3.5 text-slate-700 absolute -right-2 top-4 hidden lg:block z-10" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
