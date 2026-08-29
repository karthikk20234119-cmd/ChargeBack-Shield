import React from 'react';
import { RefreshCw } from 'lucide-react';

interface ObservabilityRefreshBarProps {
  autoRefreshInterval: number;
  setAutoRefreshInterval: (interval: number) => void;
}

export const ObservabilityRefreshBar: React.FC<ObservabilityRefreshBarProps> = ({
  autoRefreshInterval,
  setAutoRefreshInterval,
}) => {
  return (
    <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 flex items-center justify-between text-xs">
      <div className="flex items-center gap-2 text-slate-400 font-mono">
        <RefreshCw className="w-3.5 h-3.5" />
        <span>Auto-Refresh Interval:</span>
      </div>

      <div className="flex items-center gap-2 font-mono">
        {[5, 10, 30, 0].map((sec) => (
          <button
            key={sec}
            onClick={() => setAutoRefreshInterval(sec)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
              autoRefreshInterval === sec
                ? 'bg-brand-600/30 text-brand-400 border-brand-500/50'
                : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800'
            }`}
          >
            {sec === 0 ? 'OFF' : `${sec}s`}
          </button>
        ))}
      </div>
    </div>
  );
};
