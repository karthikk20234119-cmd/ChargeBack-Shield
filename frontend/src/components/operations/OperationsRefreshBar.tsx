import React from 'react';
import { RefreshCw, Clock } from 'lucide-react';

interface OperationsRefreshBarProps {
  lastRefreshed: string;
  loading: boolean;
  onRefresh: () => void;
  autoRefreshEnabled: boolean;
  onToggleAutoRefresh: () => void;
}

export const OperationsRefreshBar: React.FC<OperationsRefreshBarProps> = ({
  lastRefreshed,
  loading,
  onRefresh,
  autoRefreshEnabled,
  onToggleAutoRefresh,
}) => {
  return (
    <div className="flex items-center justify-between p-3 bg-slate-900/60 rounded-xl border border-slate-800 text-xs font-mono text-slate-400">
      <div className="flex items-center gap-2">
        <Clock className="w-3.5 h-3.5 text-slate-500" />
        <span>Last Refreshed: <span className="text-slate-200">{lastRefreshed}</span></span>
      </div>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoRefreshEnabled}
            onChange={onToggleAutoRefresh}
            className="rounded border-slate-800 bg-slate-950 text-brand-500 focus:ring-0"
          />
          <span className="text-[11px]">Auto-Refresh (30s)</span>
        </label>

        <button
          disabled={loading}
          onClick={onRefresh}
          className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs transition-colors flex items-center gap-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Now</span>
        </button>
      </div>
    </div>
  );
};
