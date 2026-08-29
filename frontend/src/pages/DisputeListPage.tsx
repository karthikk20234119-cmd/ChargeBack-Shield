import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { DisputeSummaryItem } from '../api/types';
import { SkeletonLoader } from '../components/ui/SkeletonLoader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Search, Filter, ArrowRight, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';

export const DisputeListPage: React.FC = () => {
  const [disputes, setDisputes] = useState<DisputeSummaryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchDisputes = async () => {
    setLoading(true);
    try {
      const res = await api.getDisputes({ page, page_size: 20, search, status: statusFilter });
      setDisputes(res.disputes || []);
      setTotal(res.total || 0);
    } catch {
      // safe fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDisputes();
  }, [page, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchDisputes();
  };

  return (
    <div className="space-y-6">
      {/* Title & Filter Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
            Dispute Records Management
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Search, filter, and inspect dispute lifecycle states & preflight readiness ({total} records)
          </p>
        </div>

        <button
          onClick={fetchDisputes}
          className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 rounded-lg flex items-center gap-2 transition-colors self-start md:self-auto"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="glass-panel p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
        <form onSubmit={handleSearchSubmit} className="flex-1 w-full relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by Dispute ID, Payment ID, Order ID, Customer Name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
          />
        </form>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-slate-950/80 border border-slate-800 text-xs text-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          >
            <option value="">All Dispute Statuses</option>
            <option value="open">Open / Under Review</option>
            <option value="won">Won</option>
            <option value="lost">Lost</option>
            <option value="action_required">Action Required</option>
          </select>
        </div>
      </div>

      {/* Disputes Table */}
      {loading ? (
        <SkeletonLoader rows={10} />
      ) : disputes.length === 0 ? (
        <div className="glass-panel p-12 text-center space-y-3">
          <p className="text-sm text-slate-400">No dispute records found matching query criteria.</p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/90 text-slate-400 uppercase font-mono text-[11px] border-b border-slate-800/80 sticky top-0">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Dispute ID</th>
                  <th className="py-3.5 px-4 font-semibold">Payment ID</th>
                  <th className="py-3.5 px-4 font-semibold">Amount</th>
                  <th className="py-3.5 px-4 font-semibold">Policy</th>
                  <th className="py-3.5 px-4 font-semibold">Review</th>
                  <th className="py-3.5 px-4 font-semibold">Preflight</th>
                  <th className="py-3.5 px-4 font-semibold">Submission</th>
                  <th className="py-3.5 px-4 font-semibold">Outcome</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {disputes.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-900/40 transition-colors group">
                    <td className="py-3 px-4 font-bold text-slate-100">{d.id}</td>
                    <td className="py-3 px-4 text-slate-400">{d.payment_id}</td>
                    <td className="py-3 px-4 font-bold text-emerald-400">
                      ₹{(d.amount / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })} {d.currency}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={d.policy_status} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={d.review_status} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={d.preflight_status} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={d.submission_status} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={d.lifecycle_outcome || d.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/disputes/${d.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 group-hover:bg-brand-600 group-hover:text-white text-slate-300 font-sans font-semibold transition-all text-xs"
                      >
                        <span>360° View</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="p-4 bg-slate-900/80 border-t border-slate-800/80 flex items-center justify-between">
            <span className="text-xs text-slate-400 font-mono">
              Showing page {page} of {Math.ceil(total / 20) || 1}
            </span>

            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1 bg-slate-800 disabled:opacity-40 text-xs text-slate-200 rounded hover:bg-slate-700 transition-colors"
              >
                Previous
              </button>
              <button
                disabled={page * 20 >= total}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 bg-slate-800 disabled:opacity-40 text-xs text-slate-200 rounded hover:bg-slate-700 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
