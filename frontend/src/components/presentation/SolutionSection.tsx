import React from 'react';
import { ShieldCheck, CheckCircle2, Zap } from 'lucide-react';

export const SolutionSection: React.FC = () => {
  const pillars = [
    { title: 'Automated Ingestion', desc: 'Secure PDF/Image parsing with magic-byte validation and SHA-256 hash isolation.' },
    { title: 'Deterministic Matching', desc: 'Rule-based fact matching mapping evidence attributes to order database records.' },
    { title: 'Human-in-the-Loop Review', desc: 'Merchant approval checkpoint with BLOCKED draft protection and HTTP 409 conflict checks.' },
    { title: 'Controlled API Submission', desc: 'Single authorized POST submission route with preflight verification and UNKNOWN recovery.' },
  ];

  return (
    <div className="glass-panel p-6 space-y-4 border-l-4 border-l-emerald-500 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>B. The Solution</span>
        </h2>
        <span className="text-[10px] text-emerald-400 font-bold">CHARGEBACK SHIELD PLATFORM</span>
      </div>

      <div className="p-4 bg-emerald-950/40 border border-emerald-800/60 rounded-xl text-emerald-200 text-sm font-sans font-semibold leading-relaxed">
        "Chargeback Shield creates a deterministic, explainable dispute lifecycle."
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {pillars.map((p, idx) => (
          <div key={idx} className="p-4 bg-slate-950/60 rounded-xl border border-slate-900 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-emerald-400 text-xs font-mono">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{p.title}</span>
            </div>
            <p className="text-slate-300 font-sans text-xs leading-relaxed">{p.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
