import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

interface PolicyDecisionBadgeProps {
  decision: string;
}

export const PolicyDecisionBadge: React.FC<PolicyDecisionBadgeProps> = ({ decision }) => {
  const norm = (decision || 'NOT_ELIGIBLE').toUpperCase();

  if (norm === 'ELIGIBLE') {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/90 text-emerald-300 border border-emerald-700 glow-emerald">
        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        ELIGIBLE
      </span>
    );
  }

  if (norm === 'HUMAN_REVIEW') {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/90 text-amber-300 border border-amber-700">
        <AlertTriangle className="w-4 h-4 text-amber-400" />
        HUMAN REVIEW REQUIRED
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-950/90 text-rose-300 border border-rose-700 glow-rose">
      <XCircle className="w-4 h-4 text-rose-400" />
      NOT ELIGIBLE
    </span>
  );
};
