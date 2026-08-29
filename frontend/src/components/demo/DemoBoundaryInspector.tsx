import React from 'react';
import { Lock, ShieldAlert, CheckCircle2 } from 'lucide-react';

export const DemoBoundaryInspector: React.FC = () => {
  const boundaries = [
    { title: 'Zero Silent Mutation', desc: 'No direct Razorpay mutation HTTP verb (POST/PATCH/PUT/DELETE) is called during demo simulation.' },
    { title: 'Human Review Approval Gate', desc: 'Contest drafts in BLOCKED policy state CANNOT be approved by reviewers or submitted.' },
    { title: 'Submission Preflight Hash', desc: 'Preflight generates a SHA-256 hash preventing submission of stale or modified drafts.' },
    { title: 'NO Retry Submission', desc: 'UNKNOWN submission states render a strict reconciliation notice without automated retry buttons.' },
  ];

  return (
    <div className="glass-panel p-5 space-y-4 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h3 className="font-bold text-slate-200 uppercase tracking-wider text-[11px] flex items-center gap-2">
          <Lock className="w-3.5 h-3.5 text-emerald-400" />
          <span>Active Security Boundaries</span>
        </h3>
        <span className="text-[10px] text-emerald-400 font-bold">100% ENFORCED</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {boundaries.map((b, idx) => (
          <div key={idx} className="p-3 bg-slate-950/60 rounded-lg border border-slate-900 space-y-1">
            <div className="flex items-center gap-1.5 font-bold text-slate-100">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>{b.title}</span>
            </div>
            <p className="text-slate-400 font-sans text-[11px] leading-relaxed">{b.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
