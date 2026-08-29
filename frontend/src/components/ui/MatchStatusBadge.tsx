import React from 'react';

interface MatchStatusBadgeProps {
  status: string;
}

export const MatchStatusBadge: React.FC<MatchStatusBadgeProps> = ({ status }) => {
  const norm = (status || 'UNVERIFIABLE').toUpperCase();

  let style = 'bg-slate-800 text-slate-300 border-slate-700';

  if (norm === 'MATCH') {
    style = 'bg-emerald-950/80 text-emerald-300 border-emerald-800 font-semibold';
  } else if (norm === 'MISMATCH' || norm === 'CROSS_DOCUMENT_CONFLICT') {
    style = 'bg-rose-950/80 text-rose-300 border-rose-800 font-semibold';
  } else if (norm === 'MISSING') {
    style = 'bg-amber-950/80 text-amber-300 border-amber-800';
  } else if (norm === 'AMBIGUOUS' || norm === 'NOT_COMPARABLE') {
    style = 'bg-indigo-950/80 text-indigo-300 border-indigo-800';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border font-mono ${style}`}>
      {norm}
    </span>
  );
};
