import React from 'react';

interface SeverityBadgeProps {
  severity: string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  const norm = (severity || 'LOW').toUpperCase();

  let style = 'bg-slate-800 text-slate-300 border-slate-700';

  if (norm === 'CRITICAL') {
    style = 'bg-red-950 text-red-300 border-red-700 font-semibold animate-pulse-subtle glow-rose';
  } else if (norm === 'HIGH') {
    style = 'bg-amber-950 text-amber-300 border-amber-700 font-medium';
  } else if (norm === 'MEDIUM') {
    style = 'bg-yellow-950 text-yellow-300 border-yellow-800';
  } else if (norm === 'LOW' || norm === 'INFO') {
    style = 'bg-sky-950 text-sky-300 border-sky-800';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${style}`}>
      {norm}
    </span>
  );
};
