import React from 'react';
import { BarChart3, Trophy, Activity, Clock, ShieldCheck } from 'lucide-react';

export const IntelligenceMetricsSection: React.FC = () => {
  const metrics = [
    { label: 'Dispute Win Rate', value: '78.5%', color: 'text-emerald-400', icon: Trophy },
    { label: 'Draft Approval Rate', value: '92.4%', color: 'text-indigo-400', icon: ShieldCheck },
    { label: 'Submission Success', value: '98.1%', color: 'text-brand-400', icon: Activity },
    { label: 'SLA Compliance', value: '99.2%', color: 'text-amber-400', icon: Clock },
  ];

  return (
    <div className="glass-panel p-6 space-y-4 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-brand-400" />
          <span>E. Platform Intelligence & SLA Metrics</span>
        </h2>
        <span className="text-[10px] text-brand-400 font-bold">REAL-TIME OBSERVABILITY</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {metrics.map((m, idx) => {
          const Icon = m.icon;
          return (
            <div key={idx} className="p-4 bg-slate-950/60 rounded-xl border border-slate-900 space-y-2 text-center">
              <Icon className="w-5 h-5 mx-auto text-slate-400" />
              <p className={`text-2xl font-extrabold ${m.color}`}>{m.value}</p>
              <span className="text-[10px] text-slate-400 font-sans block">{m.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
