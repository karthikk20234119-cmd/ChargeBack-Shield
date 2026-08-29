import React from 'react';
import { AlertCircle } from 'lucide-react';
import { ObservabilityMetricsResponse } from '../../api/types';

interface ErrorRatePanelProps {
  metrics: ObservabilityMetricsResponse;
}

export const ErrorRatePanel: React.FC<ErrorRatePanelProps> = ({ metrics }) => {
  const { errors_by_category } = metrics;
  const categories = Object.entries(errors_by_category || {});

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
        <AlertCircle className="w-4 h-4 text-rose-400" />
        Error Distribution by Category
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 text-xs font-mono">
        {categories.map(([cat, count]) => (
          <div key={cat} className="p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg flex items-center justify-between">
            <span className="text-slate-400 text-[10px] truncate max-w-[120px]">{cat}</span>
            <span className={`font-bold ${count > 0 ? 'text-rose-400' : 'text-slate-500'}`}>{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
