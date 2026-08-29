import React from 'react';
import { GitCompare } from 'lucide-react';

export const MatchingPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Deterministic Evidence Matching Engine
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Zero-AI deterministic comparison between trusted transaction data and extracted evidence facts
        </p>
      </div>

      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center gap-3 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
          <GitCompare className="w-5 h-5 text-indigo-400" />
          <div className="text-xs">
            <h4 className="font-bold text-slate-200">Matching Status Taxonomy</h4>
            <p className="text-slate-400">MATCH, MISMATCH, MISSING, AMBIGUOUS, UNVERIFIABLE, NOT_COMPARABLE, CROSS_DOCUMENT_CONFLICT</p>
          </div>
        </div>
      </div>
    </div>
  );
};
