import React from 'react';
import { FileCheck, Lock } from 'lucide-react';

interface EvidenceAnalyticsPanelProps {
  data?: any;
}

export const EvidenceAnalyticsPanel: React.FC<EvidenceAnalyticsPanelProps> = ({ data }) => {
  if (!data) return null;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-indigo-400" />
          <span>Evidence Collection & Fact Extraction Analytics</span>
        </h3>
        <span className="text-[10px] font-mono text-emerald-400">Processing Success: {data.processing_success_rate || 100}%</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Total Evidence Documents</span>
          <p className="font-bold text-slate-200">{data.total_documents || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Processed Documents</span>
          <p className="font-bold text-emerald-400">{data.processed_documents || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Extracted Facts</span>
          <p className="font-bold text-indigo-400">{data.total_extracted_facts || 0}</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
          <span className="text-slate-500 text-[10px]">Evidence Coverage Rate</span>
          <p className="font-bold text-brand-400">{data.evidence_coverage_rate || 0}%</p>
        </div>
      </div>
    </div>
  );
};
