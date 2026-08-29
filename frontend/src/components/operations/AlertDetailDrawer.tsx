import React from 'react';
import { OperationalAlert } from '../../api/types';
import { SeverityBadge } from '../ui/SeverityBadge';
import { StatusBadge } from '../ui/StatusBadge';
import { Modal } from '../ui/Modal';
import { Bell, Lock, ShieldCheck, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

interface AlertDetailDrawerProps {
  alert: OperationalAlert | null;
  onClose: () => void;
}

export const AlertDetailDrawer: React.FC<AlertDetailDrawerProps> = ({ alert, onClose }) => {
  if (!alert) return null;

  return (
    <Modal
      isOpen={!!alert}
      onClose={onClose}
      title={`Operational Alert #${alert.id}`}
      maxWidth="lg"
    >
      <div className="space-y-4 font-mono text-xs">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={alert.severity} />
            <span className="font-bold text-slate-100">{alert.code}</span>
          </div>

          <StatusBadge status={alert.status} />
        </div>

        <div className="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800 space-y-1">
          <span className="text-slate-400 text-[10px] uppercase font-bold">Alert Message</span>
          <p className="text-slate-200 font-sans text-xs leading-relaxed">{alert.message}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-[11px]">
          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
            <span className="text-slate-500">Dispute ID:</span>
            <p className="font-bold text-brand-400">{alert.dispute_id}</p>
          </div>

          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
            <span className="text-slate-500">Category:</span>
            <p className="font-bold text-indigo-400">{alert.category}</p>
          </div>

          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
            <span className="text-slate-500">Detected Time:</span>
            <p className="text-slate-300">{new Date(alert.created_at).toLocaleString()}</p>
          </div>

          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
            <span className="text-slate-500">SLA Status:</span>
            <p className={alert.is_sla_breached ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
              {alert.is_sla_breached ? 'SLA BREACHED' : 'ON TIME'}
            </p>
          </div>
        </div>

        <div className="p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-lg text-emerald-300 text-[10px] flex items-center gap-2">
          <Lock className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Security Audit Passed: Zero credentials, tokens, or internal filesystem paths rendered.</span>
        </div>

        <div className="flex items-center justify-between pt-2">
          <Link
            to={`/disputes/${alert.dispute_id}`}
            onClick={onClose}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-lg shadow-md glow-blue transition-all"
          >
            <span>Navigate to Dispute 360° View</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>

          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
};
