import React from 'react';

interface SkeletonLoaderProps {
  rows?: number;
  type?: 'card' | 'table' | 'dashboard';
}

export const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({ rows = 5, type = 'table' }) => {
  if (type === 'card') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 animate-pulse">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 bg-slate-900/80 border border-slate-800 rounded-xl"></div>
        ))}
      </div>
    );
  }

  return (
    <div className="glass-panel p-6 space-y-4 animate-pulse">
      <div className="h-6 w-1/4 bg-slate-800 rounded"></div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="h-10 bg-slate-900/60 rounded border border-slate-800/60"></div>
        ))}
      </div>
    </div>
  );
};
