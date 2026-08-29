import React from 'react';

interface StatusBadgeProps {
  status: string;
  type?: 'general' | 'evidence' | 'draft' | 'review' | 'submission' | 'lifecycle';
  size?: 'sm' | 'md' | 'lg';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const norm = (status || 'UNKNOWN').toUpperCase();

  let style = 'bg-slate-800 text-slate-300 border-slate-700';

  if (['APPROVED', 'ELIGIBLE', 'READY', 'SUBMITTED', 'WON', 'MATCH', 'SUCCESS', 'PROCESSED', 'AI_EXTRACTED'].includes(norm)) {
    style = 'bg-emerald-950/80 text-emerald-300 border-emerald-800/80 glow-emerald';
  } else if (['HUMAN_REVIEW', 'PENDING_REVIEW', 'REVIEW_REQUIRED', 'UNDER_REVIEW', 'ACTION_REQUIRED', 'UNKNOWN'].includes(norm)) {
    style = 'bg-amber-950/80 text-amber-300 border-amber-800/80';
  } else if (['REJECTED', 'BLOCKED', 'FAILED', 'LOST', 'MISMATCH', 'STALE', 'NOT_ELIGIBLE'].includes(norm)) {
    style = 'bg-rose-950/80 text-rose-300 border-rose-800/80 glow-rose';
  } else if (['DRAFT', 'UPLOADED', 'PROCESSING', 'READY_FOR_AI'].includes(norm)) {
    style = 'bg-indigo-950/80 text-indigo-300 border-indigo-800/80 glow-indigo';
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm font-medium' : 'px-2.5 py-1 text-xs font-medium';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${style} ${sizeClasses} transition-all`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-75"></span>
      {norm}
    </span>
  );
};
