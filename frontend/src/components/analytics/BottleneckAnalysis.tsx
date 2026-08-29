import React from 'react';
import { BottleneckItem } from '../../api/types';
import { SeverityBadge } from '../ui/SeverityBadge';
import { AlertCircle, Clock } from 'lucide-react';

interface BottleneckAnalysisProps {
  bottlenecks?: BottleneckItem[];
}

export const BottleneckAnalysis: React.FC<BottleneckAnalysisProps> = ({ bottlenecks = [] }) => {
  if (bottlenecks.length === 0) return null;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-400" />
          <span>Stage Bottleneck & Velocity Analysis</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">Analytical Stage Observability</span>
      </div>

      <div className="space-y-3 font-mono text-xs">
        {bottlenecks.map((item, idx) => (
          <div key={idx} className="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <SeverityBadge severity={item.severity} />
                <span className="font-bold text-slate-100">{item.stage_name || item.stage}</span>
              </div>
              <span className="text-amber-400 text-[11px] font-bold">Metric: {item.metric_value}</span>
            </div>

            <p className="text-slate-300 font-sans text-xs">{item.details}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
