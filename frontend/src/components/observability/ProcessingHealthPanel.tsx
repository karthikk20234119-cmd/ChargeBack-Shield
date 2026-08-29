import React from 'react';
import { FileText, Cpu, CheckCircle } from 'lucide-react';
import { ObservabilityMetricsResponse } from '../../api/types';

interface ProcessingHealthPanelProps {
  metrics: ObservabilityMetricsResponse;
}

export const ProcessingHealthPanel: React.FC<ProcessingHealthPanelProps> = ({ metrics }) => {
  const { evidence_processing, policy_matching } = metrics;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
        <Cpu className="w-4 h-4 text-purple-400" />
        Evidence Processing & Policy Engine Metrics
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">EVIDENCE PROCESSED</span>
          <div className="text-lg font-bold text-slate-100">{evidence_processing.total}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">FACT EXTRACTIONS</span>
          <div className="text-lg font-bold text-slate-100">{evidence_processing.extractions}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">FACT MATCHES</span>
          <div className="text-lg font-bold text-slate-100">{policy_matching.matches}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">POLICY EVALUATIONS</span>
          <div className="text-lg font-bold text-slate-100">{policy_matching.policy_evaluations}</div>
        </div>
      </div>
    </div>
  );
};
