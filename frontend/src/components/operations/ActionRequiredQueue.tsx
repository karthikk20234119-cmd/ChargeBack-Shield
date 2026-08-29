import React from 'react';
import { ActionRequiredDispute } from '../../api/operations';
import { SeverityBadge } from '../ui/SeverityBadge';
import { AlertTriangle, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface ActionRequiredQueueProps {
  disputes: ActionRequiredDispute[];
}

export const ActionRequiredQueue: React.FC<ActionRequiredQueueProps> = ({ disputes }) => {
  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>Action Required Queue ({disputes.length})</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">Manual Operational Follow-up</span>
      </div>

      {disputes.length === 0 ? (
        <div className="p-8 text-center text-xs text-slate-500 font-mono">
          No disputes currently requiring operational action.
        </div>
      ) : (
        <div className="space-y-3 font-mono text-xs">
          {disputes.map((item, i) => (
            <div key={i} className="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={item.severity} />
                  <span className="font-bold text-brand-400">#{item.dispute_id}</span>
                </div>
                <span className="text-slate-400 text-[10px]">{item.action_type}</span>
              </div>

              <div className="text-[11px] text-slate-300 font-sans">{item.description}</div>

              <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-800/60 font-sans">
                <span className="text-emerald-400 font-mono font-bold">
                  ₹{(item.amount / 100).toLocaleString('en-IN')} {item.currency}
                </span>
                <Link
                  to={`/disputes/${item.dispute_id}`}
                  className="inline-flex items-center gap-1 text-xs text-brand-400 hover:underline font-semibold"
                >
                  <span>Resolve Action</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
