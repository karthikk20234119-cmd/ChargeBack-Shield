import React from 'react';
import { ExceptionsReport } from '../../api/operations';
import { SeverityBadge } from '../ui/SeverityBadge';
import { AlertCircle, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

interface ExceptionPanelProps {
  exceptionsReport: ExceptionsReport | null;
}

export const ExceptionPanel: React.FC<ExceptionPanelProps> = ({ exceptionsReport }) => {
  if (!exceptionsReport) return null;

  const list = exceptionsReport.exceptions || [];

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400" />
          <span>Operational Exceptions Panel ({exceptionsReport.total_exceptions})</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">
          Critical: {exceptionsReport.critical_exceptions} • High: {exceptionsReport.high_exceptions}
        </span>
      </div>

      <div className="p-3 bg-indigo-950/40 border border-indigo-800/60 rounded-lg text-indigo-300 text-xs font-mono">
        <span className="font-bold">Architectural Distinction:</span> Operational exceptions represent infrastructure or pipeline issues (e.g. timeout, extraction error). Policy disqualifications represent business eligibility decisions. Policy outcomes remain untouched.
      </div>

      {list.length === 0 ? (
        <p className="text-xs text-slate-400 font-mono">No operational exceptions recorded.</p>
      ) : (
        <div className="space-y-3 font-mono text-xs">
          {list.map((ex) => (
            <div key={ex.id} className="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={ex.severity} />
                  <span className="font-bold text-slate-100">{ex.category}</span>
                </div>
                <Link to={`/disputes/${ex.dispute_id}`} className="text-brand-400 text-[11px] hover:underline font-sans">
                  Dispute #{ex.dispute_id}
                </Link>
              </div>

              <p className="text-slate-300 font-sans text-xs">{ex.reason}</p>

              <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-800/60">
                <div>State: <span className="text-slate-200">{ex.current_state}</span></div>
                <div>Action: <span className="text-amber-300 font-bold">{ex.required_action}</span></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
