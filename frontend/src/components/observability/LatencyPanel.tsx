import React from 'react';
import { Zap } from 'lucide-react';
import { ObservabilityMetricsResponse } from '../../api/types';

interface LatencyPanelProps {
  metrics: ObservabilityMetricsResponse;
}

export const LatencyPanel: React.FC<LatencyPanelProps> = ({ metrics }) => {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
        <Zap className="w-4 h-4 text-purple-400" />
        Request Latency Distribution
      </h3>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">P50 (MEDIAN)</span>
          <div className="text-lg font-bold text-slate-100">{metrics.latency_p50_ms} ms</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">P95 (TAIL)</span>
          <div className="text-lg font-bold text-slate-100">{metrics.latency_p95_ms} ms</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
          <span className="text-slate-400 font-mono">P99 (WORST)</span>
          <div className="text-lg font-bold text-slate-100">{metrics.latency_p99_ms} ms</div>
        </div>
      </div>
    </div>
  );
};
