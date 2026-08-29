import React from 'react';
import { SLAReport, SLAItem } from '../../api/operations';
import { SLAStatusBadge } from './SLAStatusBadge';
import { Clock, ShieldAlert, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface SLACommandCenterProps {
  slaReport: SLAReport | null;
}

export const SLACommandCenter: React.FC<SLACommandCenterProps> = ({ slaReport }) => {
  if (!slaReport) {
    return (
      <div className="glass-panel p-6 text-center text-xs text-slate-400 font-mono">
        Loading SLA Monitoring metrics...
      </div>
    );
  }

  const items = slaReport.items || [];

  return (
    <div className="glass-panel p-6 space-y-5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <Clock className="w-4 h-4 text-brand-400" />
          <span>SLA Monitoring & Deadline Command Center</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">Total Tracked: {slaReport.total_tracked}</span>
      </div>

      {/* SLA Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-xl space-y-1">
          <span className="text-slate-400 text-[10px]">ON TRACK</span>
          <p className="text-xl font-extrabold text-emerald-400">{slaReport.on_track_count}</p>
        </div>
        <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-xl space-y-1">
          <span className="text-slate-400 text-[10px]">DUE SOON</span>
          <p className="text-xl font-extrabold text-amber-400">{slaReport.due_soon_count}</p>
        </div>
        <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-xl space-y-1 glow-rose">
          <span className="text-slate-400 text-[10px]">OVERDUE / BREACHED</span>
          <p className="text-xl font-extrabold text-rose-400">{slaReport.overdue_count}</p>
        </div>
        <div className="p-3 bg-slate-950/60 border border-slate-900 rounded-xl space-y-1">
          <span className="text-slate-400 text-[10px]">UNKNOWN SLA</span>
          <p className="text-xl font-extrabold text-slate-400">{slaReport.unknown_count}</p>
        </div>
      </div>

      {/* SLA Tracked Items Table */}
      {items.length === 0 ? (
        <div className="p-6 text-center text-xs text-slate-500 font-mono">
          No SLA deadline items currently tracked.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 text-[11px]">
              <tr>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Dispute ID</th>
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3">Due Time</th>
                <th className="py-2.5 px-3">Elapsed</th>
                <th className="py-2.5 px-3">Remaining</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-900/40">
                  <td className="py-2.5 px-3">
                    <SLAStatusBadge status={item.status} />
                  </td>
                  <td className="py-2.5 px-3 font-bold text-brand-400">{item.dispute_id}</td>
                  <td className="py-2.5 px-3 text-slate-300">{item.category}</td>
                  <td className="py-2.5 px-3 text-slate-400 text-[11px]">{new Date(item.due_time).toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-slate-300">{item.elapsed_hours.toFixed(1)}h</td>
                  <td className={`py-2.5 px-3 font-bold ${item.remaining_hours < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {item.remaining_hours.toFixed(1)}h
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <Link
                      to={`/disputes/${item.dispute_id}`}
                      className="inline-flex items-center gap-1 text-[11px] text-brand-400 hover:text-brand-300 font-sans font-semibold"
                    >
                      <span>Investigate</span>
                      <ArrowRight className="w-3 h-3" />
                    </Link>
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
