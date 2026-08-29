import React from 'react';
import { AlertTriangle, ShieldAlert } from 'lucide-react';

interface ReviewFlagsProps {
  flags?: string[];
  isBlocked?: boolean;
}

export const ReviewFlags: React.FC<ReviewFlagsProps> = ({ flags = [], isBlocked }) => {
  if (flags.length === 0 && !isBlocked) {
    return null;
  }

  return (
    <div className="glass-panel p-5 space-y-3 border-l-4 border-l-rose-500 bg-rose-950/20">
      <h3 className="text-xs font-bold text-rose-300 uppercase tracking-wider font-mono flex items-center gap-2">
        <ShieldAlert className="w-4 h-4 text-rose-400" />
        <span>Active Review Flags & Risk Warnings ({flags.length + (isBlocked ? 1 : 0)})</span>
      </h3>

      <div className="space-y-2">
        {isBlocked && (
          <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-700 text-rose-200 text-xs font-mono flex items-start gap-2 glow-rose">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">POLICY_DISQUALIFICATION:</span> Policy evaluation result is NOT_ELIGIBLE or draft status is BLOCKED. Approval action is disabled.
            </div>
          </div>
        )}

        {flags.map((flag, idx) => (
          <div key={idx} className="p-3 rounded-lg bg-amber-950/80 border border-amber-700 text-amber-200 text-xs font-mono flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">{flag}:</span> High priority investigation flag requiring merchant verification before proceeding.
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
