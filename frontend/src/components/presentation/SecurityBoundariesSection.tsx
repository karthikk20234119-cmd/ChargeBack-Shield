import React from 'react';
import { Lock, ShieldAlert, CheckCircle2 } from 'lucide-react';

export const SecurityBoundariesSection: React.FC = () => {
  const securityPillars = [
    { name: 'Deterministic Engine', detail: 'Zero non-deterministic AI decisions; 100% Python policy & matching rules.' },
    { name: 'Evidence Provenance', detail: 'SHA-256 hash tracking from raw upload to submitted rebuttal document.' },
    { name: 'Financial Immutability', detail: 'Payment ID, dispute amount, and currency are strictly read-only and immutable.' },
    { name: 'Human Approval Gate', desc: 'Required human approval checkpoint for REVIEW_REQUIRED policy outcomes.' },
    { name: 'Preflight Authorization', detail: 'Cryptographic preflight hash verification blocks modified/stale contest drafts.' },
    { name: 'Controlled Mutation Boundary', detail: 'Single authorized POST submission endpoint; zero direct Razorpay frontend requests.' },
    { name: 'No Blind Retries', detail: 'UNKNOWN submission states render a strict reconciliation notice without retry buttons.' },
    { name: 'Full Auditability', detail: 'Chronological audit log with canonical SHA-256 report hash verification.' },
  ];

  return (
    <div className="glass-panel p-6 space-y-4 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
          <Lock className="w-4 h-4 text-emerald-400" />
          <span>D. Production Security & Isolation Invariants</span>
        </h2>
        <span className="text-[10px] text-emerald-400 font-bold">100% ENFORCED INVARIANTS</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {securityPillars.map((s, idx) => (
          <div key={idx} className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-900 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-slate-100 text-xs">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>{s.name}</span>
            </div>
            <p className="text-slate-400 font-sans text-[11px] leading-relaxed">{s.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
