import React from 'react';
import { PreflightCheck } from '../../api/types';
import { ShieldCheck, ShieldAlert, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

interface PreflightGateProps {
  status: string;
  checks: PreflightCheck[];
  blockingReasons?: string[];
}

export const PreflightGate: React.FC<PreflightGateProps> = ({ status, checks, blockingReasons = [] }) => {
  const isReady = status === 'READY';

  return (
    <div className="glass-panel p-6 border-l-4 border-l-brand-500 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isReady ? (
            <div className="p-2.5 bg-emerald-950/80 border border-emerald-700/80 rounded-lg text-emerald-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
          ) : (
            <div className="p-2.5 bg-rose-950/80 border border-rose-700/80 rounded-lg text-rose-400">
              <ShieldAlert className="w-6 h-6" />
            </div>
          )}
          <div>
            <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              Submission Preflight Gate
            </h3>
            <p className="text-xs text-slate-400">Deterministic Local Authorization & Security Verification</p>
          </div>
        </div>

        <div className="text-right">
          <span className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold border ${
            isReady ? 'bg-emerald-950 text-emerald-300 border-emerald-700 glow-emerald' : 'bg-rose-950 text-rose-300 border-rose-700 glow-rose'
          }`}>
            {isReady ? '✓ AUTHORIZATION GATE READY' : '✕ AUTHORIZATION GATE BLOCKED'}
          </span>
        </div>
      </div>

      {blockingReasons.length > 0 && (
        <div className="p-4 bg-rose-950/60 border border-rose-800/80 rounded-lg space-y-1.5">
          <h4 className="text-xs font-semibold text-rose-300 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            Blocking Authorization Reasons ({blockingReasons.length})
          </h4>
          <ul className="list-disc list-inside text-xs text-rose-200 space-y-1 font-mono">
            {blockingReasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Grid of 17 Authorization Checks */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {checks.map((chk, i) => {
          const isPass = chk.status === 'PASS';
          return (
            <div key={i} className={`p-3 rounded-lg border flex items-start gap-3 transition-colors ${
              isPass ? 'bg-slate-900/50 border-slate-800/80' : 'bg-rose-950/30 border-rose-900/80'
            }`}>
              <div className="mt-0.5">
                {isPass ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                ) : chk.severity === 'BLOCKING' ? (
                  <XCircle className="w-4 h-4 text-rose-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                )}
              </div>
              <div className="space-y-0.5 flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-semibold text-slate-200 truncate">
                    {chk.check_code}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                    chk.severity === 'BLOCKING' ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {chk.severity}
                  </span>
                </div>
                <p className="text-xs text-slate-400 line-clamp-2">{chk.message}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
