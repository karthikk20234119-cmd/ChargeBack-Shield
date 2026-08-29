import React from 'react';
import { Activity, AlertCircle, Clock, Zap } from 'lucide-react';
import { ObservabilityMetricsResponse } from '../../api/types';

interface RequestMetricsPanelProps {
  metrics: ObservabilityMetricsResponse;
}

export const RequestMetricsPanel: React.FC<RequestMetricsPanelProps> = ({ metrics }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>TOTAL REQUESTS</span>
          <Activity className="w-4 h-4 text-brand-400" />
        </div>
        <div className="text-2xl font-extrabold text-slate-100">{metrics.request_count}</div>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>REQUEST ERRORS</span>
          <AlertCircle className="w-4 h-4 text-rose-400" />
        </div>
        <div className="text-2xl font-extrabold text-slate-100">{metrics.request_error_count}</div>
        <p className="text-xs text-slate-400 font-mono">Error Rate: {metrics.error_rate_pct}%</p>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>AVG LATENCY</span>
          <Clock className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="text-2xl font-extrabold text-slate-100">{metrics.average_latency_ms} ms</div>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>P95 LATENCY</span>
          <Zap className="w-4 h-4 text-purple-400" />
        </div>
        <div className="text-2xl font-extrabold text-slate-100">{metrics.latency_p95_ms} ms</div>
      </div>
    </div>
  );
};
