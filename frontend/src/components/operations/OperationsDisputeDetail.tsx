import React from 'react';
import { ExternalLink, FileSpreadsheet } from 'lucide-react';
import { Link } from 'react-router-dom';

interface OperationsDisputeDetailProps {
  disputeId: string;
  alerts?: any[];
  slaState?: string;
}

export const OperationsDisputeDetail: React.FC<OperationsDisputeDetailProps> = ({
  disputeId,
  alerts = [],
  slaState = 'ON_TRACK',
}) => {
  return (
    <div className="glass-panel p-5 space-y-3 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h4 className="font-bold text-slate-200 flex items-center gap-2">
          <FileSpreadsheet className="w-4 h-4 text-brand-400" />
          <span>Operational Context: Dispute #{disputeId}</span>
        </h4>
        <span className="text-slate-400">SLA: {slaState}</span>
      </div>

      <p className="text-slate-300 font-sans text-xs">
        Dispute has {alerts.length} active operational alerts logged.
      </p>

      <div className="flex items-center gap-2 pt-2">
        <Link
          to={`/disputes/${disputeId}`}
          className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded text-[11px] font-sans font-semibold transition-colors flex items-center gap-1"
        >
          <span>360° Detail</span>
          <ExternalLink className="w-3 h-3" />
        </Link>
        <Link
          to={`/review`}
          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[11px] font-sans font-semibold transition-colors"
        >
          Human Review
        </Link>
        <Link
          to={`/submission`}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] font-sans transition-colors"
        >
          Submission
        </Link>
      </div>
    </div>
  );
};
