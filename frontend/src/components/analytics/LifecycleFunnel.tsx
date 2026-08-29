import React from 'react';
import { FunnelStageItem } from '../../api/types';
import { BarChart3, ArrowDown } from 'lucide-react';

interface LifecycleFunnelProps {
  funnel?: FunnelStageItem[];
}

export const LifecycleFunnel: React.FC<LifecycleFunnelProps> = ({ funnel = [] }) => {
  if (funnel.length === 0) return null;

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-brand-400" />
          <span>12-Stage Dispute Lifecycle Conversion Funnel</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">100% Deterministic Backend Sequence</span>
      </div>

      <div className="space-y-2">
        {funnel.map((item, idx) => (
          <div key={idx} className="p-3 bg-slate-900/60 rounded-xl border border-slate-800/80 font-mono text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <span className="text-slate-500 text-[10px] font-bold">#{idx + 1}</span>
              <span className="font-bold text-slate-100">{item.stage_name}</span>
            </div>

            <div className="flex items-center gap-6 text-right">
              <div>Count: <span className="text-emerald-400 font-bold">{item.count}</span></div>
              <div>Conversion: <span className="text-brand-400 font-bold">{item.conversion_rate}%</span></div>
              {item.drop_off_count > 0 && (
                <div className="text-rose-400 text-[11px] flex items-center gap-1">
                  <ArrowDown className="w-3 h-3 text-rose-400" />
                  <span>Drop: {item.drop_off_count}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
