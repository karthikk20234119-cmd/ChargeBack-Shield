import React, { useState } from 'react';
import { DisputeSummaryItem } from '../../api/types';
import { StatusBadge } from '../ui/StatusBadge';
import { Search, Filter, AlertTriangle, ShieldAlert } from 'lucide-react';

interface ReviewQueueProps {
  disputes: DisputeSummaryItem[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export const ReviewQueue: React.FC<ReviewQueueProps> = ({ disputes, selectedId, onSelect }) => {
  const [filterTab, setFilterTab] = useState<'PENDING' | 'APPROVED' | 'REJECTED' | 'BLOCKED' | 'ALL'>('PENDING');
  const [search, setSearch] = useState('');

  const filtered = disputes.filter((d) => {
    const normSearch = search.toLowerCase();
    const matchesSearch = !search || d.id.toLowerCase().includes(normSearch) || d.payment_id.toLowerCase().includes(normSearch);

    if (!matchesSearch) return false;

    if (filterTab === 'PENDING') {
      return d.review_status === 'PENDING_REVIEW' || d.draft_status === 'REVIEW_REQUIRED';
    }
    if (filterTab === 'APPROVED') {
      return d.review_status === 'APPROVED';
    }
    if (filterTab === 'REJECTED') {
      return d.review_status === 'REJECTED';
    }
    if (filterTab === 'BLOCKED') {
      return d.draft_status === 'BLOCKED' || d.policy_status === 'NOT_ELIGIBLE';
    }
    return true;
  });

  return (
    <div className="glass-panel p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-brand-400" />
          <span>Review Work Queue ({filtered.length})</span>
        </h3>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 bg-slate-950/80 p-1 rounded-lg border border-slate-800 text-[11px] font-mono overflow-x-auto">
        {[
          { key: 'PENDING', label: 'Pending' },
          { key: 'APPROVED', label: 'Approved' },
          { key: 'REJECTED', label: 'Rejected' },
          { key: 'BLOCKED', label: 'Blocked' },
          { key: 'ALL', label: 'All' },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setFilterTab(t.key as any)}
            className={`px-2.5 py-1 rounded font-semibold transition-all ${
              filterTab === t.key
                ? 'bg-brand-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
        <input
          type="text"
          placeholder="Filter queue..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-brand-500"
        />
      </div>

      {/* Queue List */}
      <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
        {filtered.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500 font-mono">
            No disputes found matching filter.
          </div>
        ) : (
          filtered.map((d) => {
            const isSelected = selectedId === d.id;
            const isBlocked = d.draft_status === 'BLOCKED';

            return (
              <button
                key={d.id}
                onClick={() => onSelect(d.id)}
                className={`w-full p-3 rounded-xl border text-left font-mono text-xs transition-all ${
                  isSelected
                    ? 'bg-brand-950/80 border-brand-600 text-brand-200 shadow-md glow-blue font-semibold'
                    : 'bg-slate-900/60 border-slate-800/80 text-slate-300 hover:bg-slate-900'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-100">#{d.id}</span>
                  <StatusBadge status={d.review_status} size="sm" />
                </div>

                <div className="flex items-center justify-between mt-1 text-[11px]">
                  <span className="text-emerald-400 font-bold">
                    ₹{(d.amount / 100).toLocaleString('en-IN')} {d.currency}
                  </span>
                  <span className="text-slate-500 text-[10px]">{d.reason_code}</span>
                </div>

                {isBlocked && (
                  <div className="mt-2 text-[10px] text-rose-300 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-900/60 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3 text-rose-400" />
                    <span>POLICY BLOCKED</span>
                  </div>
                )}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};
