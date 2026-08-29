import React from 'react';
import { FileText } from 'lucide-react';

export const ContestDraftPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Contest Draft Generation & Provenance
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Grounded factual claim synthesis with expandable evidence document provenance
        </p>
      </div>

      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center gap-3 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
          <FileText className="w-5 h-5 text-indigo-400" />
          <div className="text-xs">
            <h4 className="font-bold text-slate-200">Grounding Guarantee</h4>
            <p className="text-slate-400">All factual arguments link explicitly to verified MatchResult and EvidenceDocument IDs.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
