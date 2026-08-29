import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface StaleDraftBannerProps {
  onRefresh: () => void;
}

export const StaleDraftBanner: React.FC<StaleDraftBannerProps> = ({ onRefresh }) => {
  return (
    <div className="p-4 bg-amber-950/90 border border-amber-700 rounded-xl text-amber-100 flex items-center justify-between gap-4 font-mono text-xs shadow-xl animate-fade-in">
      <div className="flex items-center gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
        <div>
          <h4 className="font-bold text-amber-200">Draft Changed (HTTP 409 Stale Conflict)</h4>
          <p className="text-[11px] text-amber-200/80 font-sans mt-0.5">
            Evidence or policy inputs have changed since this review page was opened. Current state is preserved. Please refresh to load the latest contest draft.
          </p>
        </div>
      </div>

      <button
        onClick={onRefresh}
        className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-sans font-bold text-xs rounded-lg transition-colors flex items-center gap-1.5 shrink-0"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>Refresh Latest Draft</span>
      </button>
    </div>
  );
};
