import React from 'react';

interface SLAStatusBadgeProps {
  status: string;
}

export const SLAStatusBadge: React.FC<SLAStatusBadgeProps> = ({ status }) => {
  const norm = (status || 'UNKNOWN').toUpperCase();

  let style = 'bg-slate-800 text-slate-300 border-slate-700';

  if (norm === 'ON_TRACK') {
    style = 'bg-emerald-950/80 text-emerald-300 border-emerald-800 font-semibold';
  } else if (norm === 'DUE_SOON') {
    style = 'bg-amber-950/80 text-amber-300 border-amber-800 font-semibold';
  } else if (norm === 'OVERDUE') {
    style = 'bg-rose-950/80 text-rose-300 border-rose-800 font-bold animate-pulse-subtle glow-rose';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] border font-mono ${style}`}>
      {norm}
    </span>
  );
};
