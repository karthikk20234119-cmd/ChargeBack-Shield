import React from 'react';
import { AlertCircle, Clock, ShieldX, FileX } from 'lucide-react';

export const ProblemSection: React.FC = () => {
  const painPoints = [
    { title: 'Fragmented Evidence', desc: 'Delivery proofs, IP logs, customer chats, and order receipts scattered across disconnected merchant tools.' },
    { title: 'Manual & Error-Prone', desc: 'Merchant operations teams spend 45+ minutes manually parsing evidence files per dispute.' },
    { title: 'Uncertain SLA Deadlines', desc: 'Strict Razorpay dispute response windows missed due to lack of operational alert tracking.' },
    { title: 'Blind Retry Risk', desc: 'Repeated network retries on ambiguous submission states trigger duplicate submission errors.' },
  ];

  return (
    <div className="glass-panel p-6 space-y-4 border-l-4 border-l-rose-500 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400" />
          <span>A. The Problem</span>
        </h2>
        <span className="text-[10px] text-rose-400 font-bold">LEGACY CHARGEBACK DISPUTE MANAGEMENT</span>
      </div>

      <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-200 text-sm font-sans font-semibold leading-relaxed">
        "Chargeback evidence is fragmented, manual, slow, and difficult to audit."
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {painPoints.map((p, idx) => (
          <div key={idx} className="p-4 bg-slate-950/60 rounded-xl border border-slate-900 space-y-1.5">
            <h4 className="font-bold text-slate-200 text-xs font-mono">{p.title}</h4>
            <p className="text-slate-400 font-sans text-xs leading-relaxed">{p.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
