import React from 'react';
import { Activity } from 'lucide-react';

export const LifecyclePage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Dispute Lifecycle Synchronization
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Read-only Razorpay dispute lifecycle synchronization and terminal outcome tracking (WON / LOST)
        </p>
      </div>

      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center gap-3 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
          <Activity className="w-5 h-5 text-emerald-400" />
          <div className="text-xs">
            <h4 className="font-bold text-slate-200">Terminal Outcome Protection</h4>
            <p className="text-slate-400">Terminal dispute states (WON, LOST) are locked and immutable.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
