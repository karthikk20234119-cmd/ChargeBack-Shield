import React from 'react';
import { ContestDraft } from '../../api/types';
import { StatusBadge } from '../ui/StatusBadge';
import { FileText, CheckCircle2, AlertCircle } from 'lucide-react';

interface ContestDraftViewerProps {
  draft?: ContestDraft;
}

export const ContestDraftViewer: React.FC<ContestDraftViewerProps> = ({ draft }) => {
  if (!draft) {
    return (
      <div className="glass-panel p-5 text-center text-xs text-slate-400 font-mono">
        No contest draft available for this dispute.
      </div>
    );
  }

  const args = draft.factual_arguments?.arguments || [];

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-base font-bold text-slate-100 font-sans">{draft.title}</h3>
          <p className="text-[10px] font-mono text-slate-400 mt-0.5">
            Fingerprint: <span className="text-indigo-400">{draft.input_fingerprint}</span> • Version: {draft.draft_version}
          </p>
        </div>

        <StatusBadge status={draft.status} />
      </div>

      {/* Executive Summary */}
      <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-1.5">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Executive Summary</h4>
        <p className="text-xs text-slate-200 leading-relaxed font-sans">{draft.summary}</p>
      </div>

      {/* Factual Arguments */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono">
          Factual Argument Cards ({args.length})
        </h4>

        {args.map((arg, i) => (
          <div key={i} className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2 font-mono text-xs">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-100 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                {arg.claim}
              </span>
              <span className="px-2 py-0.5 rounded bg-brand-950 text-brand-300 text-[10px] border border-brand-800">
                Fact: {arg.fact_name}
              </span>
            </div>

            <p className="text-slate-300 font-sans text-xs leading-relaxed">{arg.explanation}</p>

            <div className="pt-2 border-t border-slate-800/60 flex items-center gap-4 text-[10px] text-slate-400">
              <div>Evidence IDs: <span className="text-slate-200">{arg.evidence_ids?.join(', ') || 'N/A'}</span></div>
              <div>Match IDs: <span className="text-slate-200">{arg.match_result_ids?.join(', ') || 'N/A'}</span></div>
            </div>
          </div>
        ))}
      </div>

      {/* Draft Limitations */}
      {draft.limitations?.limitations?.length > 0 && (
        <div className="p-3.5 bg-amber-950/40 rounded-xl border border-amber-800/60 space-y-1 text-xs font-mono text-amber-200">
          <h5 className="font-bold flex items-center gap-1.5 text-amber-300">
            <AlertCircle className="w-4 h-4 text-amber-400" />
            Unsupported Claims / Limitations:
          </h5>
          <ul className="list-disc list-inside space-y-1 text-[11px] text-amber-300/80">
            {draft.limitations.limitations.map((lim, idx) => (
              <li key={idx}>{lim}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
