import React, { useState } from 'react';
import { OperationalAlert } from '../../api/types';
import { SeverityBadge } from '../ui/SeverityBadge';
import { StatusBadge } from '../ui/StatusBadge';
import { Bell, Filter, Search, CheckCircle2, Eye } from 'lucide-react';

interface OperationalAlertQueueProps {
  alerts: OperationalAlert[];
  onSelectAlert: (alert: OperationalAlert) => void;
  onOpenAcknowledgeModal: (alert: OperationalAlert) => void;
}

const CATEGORIES = [
  'ALL',
  'SLA',
  'HUMAN_REVIEW',
  'SUBMISSION',
  'RECONCILIATION',
  'LIFECYCLE',
  'EVIDENCE',
  'PROCESSING',
  'POLICY',
  'SECURITY',
  'DATA_INTEGRITY',
  'COMPLIANCE',
  'SYSTEM',
];

export const OperationalAlertQueue: React.FC<OperationalAlertQueueProps> = ({
  alerts,
  onSelectAlert,
  onOpenAcknowledgeModal,
}) => {
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  const filtered = alerts.filter((a) => {
    if (severityFilter !== 'ALL' && a.severity !== severityFilter) return false;
    if (categoryFilter !== 'ALL' && a.category !== categoryFilter) return false;
    if (statusFilter !== 'ALL' && a.status !== statusFilter) return false;

    if (search) {
      const q = search.toLowerCase();
      return (
        a.id.toLowerCase().includes(q) ||
        a.code.toLowerCase().includes(q) ||
        a.dispute_id.toLowerCase().includes(q) ||
        a.message.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <Bell className="w-4 h-4 text-amber-400" />
          <span>Operational Alert Queue ({filtered.length})</span>
        </h3>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 rounded px-2 py-1 focus:outline-none focus:border-brand-500"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 rounded px-2 py-1 focus:outline-none focus:border-brand-500"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 rounded px-2 py-1 focus:outline-none focus:border-brand-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="RESOLVED">Resolved</option>
          </select>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
        <input
          type="text"
          placeholder="Filter alerts by code, dispute ID, message..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-brand-500"
        />
      </div>

      {/* Alert Table */}
      {filtered.length === 0 ? (
        <div className="p-8 text-center text-xs text-slate-500 font-mono">
          No operational alerts matching filter criteria.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 text-[11px]">
              <tr>
                <th className="py-3 px-3">Severity</th>
                <th className="py-3 px-3">Code</th>
                <th className="py-3 px-3">Category</th>
                <th className="py-3 px-3">Dispute ID</th>
                <th className="py-3 px-3">Message</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((a) => (
                <tr key={a.id} className="hover:bg-slate-900/40 transition-colors">
                  <td className="py-3 px-3">
                    <SeverityBadge severity={a.severity} />
                  </td>
                  <td className="py-3 px-3 font-bold text-slate-100">{a.code}</td>
                  <td className="py-3 px-3">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px]">
                      {a.category}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-brand-400">{a.dispute_id}</td>
                  <td className="py-3 px-3 text-slate-300 font-sans text-xs max-w-xs truncate">{a.message}</td>
                  <td className="py-3 px-3">
                    <StatusBadge status={a.status} size="sm" />
                  </td>
                  <td className="py-3 px-3 text-right">
                    <div className="flex items-center justify-end gap-1.5 font-sans">
                      <button
                        onClick={() => onSelectAlert(a)}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition-colors flex items-center gap-1"
                        title="View Alert Details"
                      >
                        <Eye className="w-3.5 h-3.5 text-brand-400" />
                        <span>Inspect</span>
                      </button>

                      {a.status === 'OPEN' && (
                        <button
                          onClick={() => onOpenAcknowledgeModal(a)}
                          className="px-2.5 py-1 bg-emerald-950 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 rounded text-xs transition-colors flex items-center gap-1 font-semibold"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Ack</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
