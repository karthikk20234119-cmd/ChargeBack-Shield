import React, { useState } from 'react';
import { api } from '../api/client';
import { DisputeAuditTimeline } from '../api/types';
import { ShieldCheck, Search, Hash } from 'lucide-react';

export const AuditPage: React.FC = () => {
  const [disputeId, setDisputeId] = useState('');
  const [timeline, setTimeline] = useState<DisputeAuditTimeline | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFetchAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disputeId) return;
    setLoading(true);
    try {
      const res = await api.getDisputeAuditTimeline(disputeId);
      setTimeline(res);
    } catch {
      // safe fallback
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Audit, Compliance & Traceability Center
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Complete lifecycle traceability, append-only event logs & canonical SHA-256 integrity verification
        </p>
      </div>

      <div className="glass-panel p-4">
        <form onSubmit={handleFetchAudit} className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Enter Dispute ID to query complete audit timeline & provenance..."
              value={disputeId}
              onChange={(e) => setDisputeId(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-xs text-slate-100 placeholder-slate-500 font-mono focus:outline-none focus:border-brand-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-lg shadow-md glow-blue transition-all"
          >
            Query Audit Trail
          </button>
        </form>
      </div>

      {timeline && (
        <div className="glass-panel p-6 space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-base font-bold text-slate-100 font-sans">
                Audit Timeline for Dispute #{timeline.dispute_id}
              </h3>
              <p className="text-slate-400 text-xs mt-0.5">
                Timeline Hash: <span className="text-indigo-400">{timeline.timeline_hash}</span>
              </p>
            </div>
            <span className="px-3 py-1 bg-emerald-950 text-emerald-300 border border-emerald-800 rounded-full text-xs font-bold">
              {timeline.total_events} EVENTS LOGGED
            </span>
          </div>

          <div className="space-y-3">
            {timeline.events?.map((e) => (
              <div key={e.event_id} className="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-brand-400">{e.event_type}</span>
                  <span className="text-[10px] text-slate-500">{new Date(e.event_timestamp).toLocaleString()}</span>
                </div>
                <p className="text-slate-300 font-sans text-xs">{e.explanation}</p>
                <div className="text-[10px] text-slate-500 pt-1">
                  Integrity Hash: <span className="text-slate-400">{e.integrity_hash}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
