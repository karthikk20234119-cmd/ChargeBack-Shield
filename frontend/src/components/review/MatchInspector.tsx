import React, { useState } from 'react';
import { MatchingRunResult } from '../../api/types';
import { MatchStatusBadge } from '../ui/MatchStatusBadge';
import { GitCompare, Filter } from 'lucide-react';

interface MatchInspectorProps {
  matching?: MatchingRunResult;
}

const STATUS_FILTERS = ['ALL', 'MATCH', 'MISMATCH', 'MISSING', 'AMBIGUOUS', 'CROSS_DOCUMENT_CONFLICT'];

export const MatchInspector: React.FC<MatchInspectorProps> = ({ matching }) => {
  const [filter, setFilter] = useState('ALL');

  if (!matching || !matching.results || matching.results.length === 0) {
    return (
      <div className="glass-panel p-5 text-center text-xs text-slate-400 font-mono">
        No deterministic match results available for this dispute.
      </div>
    );
  }

  const results = matching.results;
  const filtered = results.filter(
    (r) => filter === 'ALL' || r.status === filter
  );

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-indigo-400" />
          <span>Match Result Inspector ({filtered.length})</span>
        </h3>

        {/* Filter Buttons */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 font-mono text-[11px]">
          <Filter className="w-3 h-3 text-slate-400 shrink-0" />
          {STATUS_FILTERS.map((st) => (
            <button
              key={st}
              onClick={() => setFilter(st)}
              className={`px-2 py-0.5 rounded font-semibold transition-all ${
                filter === st
                  ? 'bg-indigo-950 text-indigo-300 border border-indigo-800'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 text-[11px]">
            <tr>
              <th className="py-2.5 px-3">Fact Name</th>
              <th className="py-2.5 px-3">Expected</th>
              <th className="py-2.5 px-3">Observed</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Confidence</th>
              <th className="py-2.5 px-3">Explanation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filtered.map((m, i) => (
              <tr key={i} className="hover:bg-slate-900/50">
                <td className="py-2.5 px-3 font-bold text-slate-200">{m.field_name}</td>
                <td className="py-2.5 px-3 text-emerald-400">{String(m.expected_value)}</td>
                <td className="py-2.5 px-3 text-indigo-400">{String(m.observed_value)}</td>
                <td className="py-2.5 px-3">
                  <MatchStatusBadge status={m.status} />
                </td>
                <td className="py-2.5 px-3 font-bold text-brand-400">{(m.confidence * 100).toFixed(0)}%</td>
                <td className="py-2.5 px-3 text-slate-300 font-sans text-[11px]">{m.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
