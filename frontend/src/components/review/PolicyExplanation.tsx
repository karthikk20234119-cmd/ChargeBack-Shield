import React from 'react';
import { PolicyResult } from '../../api/types';
import { PolicyDecisionBadge } from '../ui/PolicyDecisionBadge';
import { ShieldCheck, CheckCircle, XCircle } from 'lucide-react';

interface PolicyExplanationProps {
  policy?: PolicyResult;
}

export const PolicyExplanation: React.FC<PolicyExplanationProps> = ({ policy }) => {
  if (!policy) {
    return (
      <div className="glass-panel p-5 text-center text-xs text-slate-400 font-mono">
        No policy evaluation results available for this dispute.
      </div>
    );
  }

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Policy Rule Evaluation Breakdown</span>
          </h3>
          <p className="text-[10px] font-mono text-slate-400 mt-0.5">Policy Version: {policy.policy_version}</p>
        </div>

        <PolicyDecisionBadge decision={policy.decision} />
      </div>

      <div className="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800 space-y-1">
        <h4 className="text-xs font-bold text-slate-200 font-sans">Summary Explanation</h4>
        <p className="text-xs text-slate-300 font-sans leading-relaxed">{policy.summary}</p>
      </div>

      <div className="space-y-2">
        <h4 className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider">
          Evaluated Rules ({policy.rules_evaluated?.length || 0})
        </h4>

        {policy.rules_evaluated?.map((rule) => {
          const isPassed = rule.passed;
          return (
            <div
              key={rule.rule_id}
              className={`p-3.5 rounded-xl border text-xs font-mono transition-all ${
                isPassed
                  ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-200'
                  : 'bg-rose-950/30 border-rose-800/60 text-rose-200'
              }`}
            >
              <div className="flex items-center justify-between font-bold">
                <span className="flex items-center gap-2">
                  {isPassed ? (
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400" />
                  )}
                  <span>{rule.name} ({rule.rule_id})</span>
                </span>
                <span className={isPassed ? 'text-emerald-400' : 'text-rose-400'}>
                  {isPassed ? 'PASSED' : 'FAILED'}
                </span>
              </div>

              <p className="text-slate-300 font-sans text-xs mt-1.5 leading-relaxed">{rule.explanation}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
