import React from 'react';
import { ShieldAlert, CheckCircle2, AlertTriangle, HelpCircle } from 'lucide-react';
import { ObservabilitySummaryResponse } from '../../api/types';

interface SubmissionReliabilityPanelProps {
  summary: ObservabilitySummaryResponse;
}

export const SubmissionReliabilityPanel: React.FC<SubmissionReliabilityPanelProps> = ({ summary }) => {
  const { submission_reliability } = summary;
  const hasUnknown = submission_reliability.unknown_count > 0;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-brand-400" />
          Contest Submission Reliability
        </h3>
        <span className="text-[11px] font-mono text-slate-500">SINGLE BOUNDARY ENFORCED</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 bg-slate-950/60 border border-emerald-800/40 rounded-lg space-y-1">
          <div className="flex items-center justify-between text-[11px] text-emerald-400 font-mono">
            <span>SUBMITTED</span>
            <CheckCircle2 className="w-3.5 h-3.5" />
          </div>
          <div className="text-xl font-bold text-slate-100">{submission_reliability.submitted_count}</div>
        </div>

        <div className="p-3 bg-slate-950/60 border border-rose-800/40 rounded-lg space-y-1">
          <div className="flex items-center justify-between text-[11px] text-rose-400 font-mono">
            <span>FAILED</span>
            <AlertTriangle className="w-3.5 h-3.5" />
          </div>
          <div className="text-xl font-bold text-slate-100">{submission_reliability.failed_count}</div>
        </div>

        <div className={`p-3 bg-slate-950/60 border rounded-lg space-y-1 ${hasUnknown ? 'border-amber-500/80 bg-amber-950/20' : 'border-slate-800'}`}>
          <div className="flex items-center justify-between text-[11px] text-amber-400 font-mono">
            <span>UNKNOWN</span>
            <HelpCircle className="w-3.5 h-3.5" />
          </div>
          <div className="text-xl font-bold text-amber-400">{submission_reliability.unknown_count}</div>
        </div>
      </div>

      {hasUnknown && (
        <div className="p-4 bg-amber-950/40 border border-amber-500/50 rounded-xl space-y-2">
          <div className="flex items-center gap-2 text-amber-400 font-bold text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            UNKNOWN SUBMISSION STATE DETECTED
          </div>
          <p className="text-xs text-amber-200/90 font-mono">
            {submission_reliability.reconciliation_required_notice || "Submission state is ambiguous. Reconciliation is required before any further action."}
          </p>
          <div className="pt-1 flex items-center justify-between text-[11px] text-slate-400">
            <span>Reconciliation workflow mandated before retry.</span>
            <a href="/operations" className="text-brand-400 hover:text-brand-300 font-mono underline">
              View Operations Command Center →
            </a>
          </div>
        </div>
      )}
    </div>
  );
};
