import React from 'react';
import { DemoStage, DEMO_DATA_TAG } from '../../data/demoFixtures';
import { ShieldCheck, Lock, Code, Database, ArrowRight, AlertTriangle } from 'lucide-react';

interface DemoStageViewerProps {
  stage: DemoStage;
}

export const DemoStageViewer: React.FC<DemoStageViewerProps> = ({ stage }) => {
  return (
    <div className="glass-panel p-6 space-y-5 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <span className="text-[10px] text-amber-400 font-bold uppercase tracking-wider block">
            Stage {stage.id} of 17 • {DEMO_DATA_TAG}
          </span>
          <h2 className="text-xl font-bold text-slate-100 mt-0.5">{stage.name}</h2>
        </div>

        <span className="px-3 py-1 bg-amber-950/80 text-amber-300 border border-amber-800 rounded-full font-bold text-xs">
          State: {stage.state}
        </span>
      </div>

      {/* Input / Output Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-900 space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400 font-bold uppercase">Stage Input</span>
            <Code className="w-3.5 h-3.5 text-indigo-400" />
          </div>
          <p className="text-slate-200 font-sans text-xs leading-relaxed">{stage.input}</p>
        </div>

        <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-900 space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400 font-bold uppercase">Stage Output</span>
            <Database className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <p className="text-emerald-300 font-sans text-xs leading-relaxed">{stage.output}</p>
        </div>
      </div>

      {/* Security Boundary & Provenance */}
      <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-3">
        <div className="flex items-center gap-2 text-amber-300">
          <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0" />
          <span className="font-bold text-xs uppercase">Security Boundary Contract</span>
        </div>
        <p className="text-slate-300 font-sans text-xs">{stage.security_boundary}</p>

        {stage.id === 12 && (
          <div className="p-3 bg-amber-950/60 border border-amber-800 rounded-lg text-amber-200 text-xs flex items-center gap-2 font-mono">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>Notice: Submission state is ambiguous. Reconciliation is required before any further action. (Zero Retry Buttons)</span>
          </div>
        )}
      </div>

      {/* Provenance & API Source */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] pt-1">
        <div className="p-3 bg-slate-950/40 rounded-lg border border-slate-900 space-y-0.5">
          <span className="text-slate-500">Explainability / Provenance:</span>
          <p className="text-brand-400 font-bold">{stage.provenance}</p>
        </div>

        <div className="p-3 bg-slate-950/40 rounded-lg border border-slate-900 space-y-0.5">
          <span className="text-slate-500">Backend API Source:</span>
          <p className="text-indigo-400 font-bold">{stage.backend_api}</p>
        </div>
      </div>
    </div>
  );
};
