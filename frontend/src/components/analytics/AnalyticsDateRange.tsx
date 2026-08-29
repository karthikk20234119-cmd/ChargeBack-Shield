import React, { useState } from 'react';
import { TimeRangeOption } from '../../api/analytics';
import { Calendar, Filter } from 'lucide-react';

interface AnalyticsDateRangeProps {
  selectedRange: TimeRangeOption;
  dateFrom?: string;
  dateTo?: string;
  onRangeChange: (range: TimeRangeOption, from?: string, to?: string) => void;
}

export const AnalyticsDateRange: React.FC<AnalyticsDateRangeProps> = ({
  selectedRange,
  dateFrom,
  dateTo,
  onRangeChange,
}) => {
  const [customFrom, setCustomFrom] = useState(dateFrom || '');
  const [customTo, setCustomTo] = useState(dateTo || '');

  const RANGES: { key: TimeRangeOption; label: string }[] = [
    { key: 'TODAY', label: 'Today' },
    { key: 'LAST_7_DAYS', label: 'Last 7 Days' },
    { key: 'LAST_30_DAYS', label: 'Last 30 Days' },
    { key: 'LAST_90_DAYS', label: 'Last 90 Days' },
    { key: 'THIS_YEAR', label: 'This Year' },
    { key: 'CUSTOM', label: 'Custom' },
  ];

  const handleApplyCustom = (e: React.FormEvent) => {
    e.preventDefault();
    onRangeChange('CUSTOM', customFrom, customTo);
  };

  return (
    <div className="glass-panel p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex items-center gap-2 font-mono text-xs text-slate-300">
        <Calendar className="w-4 h-4 text-brand-400" />
        <span className="font-bold">Reporting Period:</span>
        <span className="text-slate-400">{selectedRange}</span>
      </div>

      <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
        {RANGES.map((r) => (
          <button
            key={r.key}
            onClick={() => onRangeChange(r.key)}
            className={`px-3 py-1.5 rounded-lg border font-semibold transition-all ${
              selectedRange === r.key
                ? 'bg-brand-600 border-brand-500 text-white shadow glow-blue'
                : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      {selectedRange === 'CUSTOM' && (
        <form onSubmit={handleApplyCustom} className="flex items-center gap-2 font-mono text-xs">
          <input
            type="date"
            value={customFrom}
            onChange={(e) => setCustomFrom(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 px-2 py-1 rounded focus:outline-none focus:border-brand-500"
          />
          <span className="text-slate-500">to</span>
          <input
            type="date"
            value={customTo}
            onChange={(e) => setCustomTo(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 px-2 py-1 rounded focus:outline-none focus:border-brand-500"
          />
          <button
            type="submit"
            className="px-3 py-1 bg-indigo-600 text-white rounded font-bold hover:bg-indigo-500 transition-colors"
          >
            Apply
          </button>
        </form>
      )}
    </div>
  );
};
