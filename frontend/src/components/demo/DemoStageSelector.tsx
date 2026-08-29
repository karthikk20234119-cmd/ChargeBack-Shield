import React from 'react';
import { DemoStage } from '../../data/demoFixtures';
import { CheckCircle2, PlayCircle, Circle } from 'lucide-react';

interface DemoStageSelectorProps {
  stages: DemoStage[];
  currentStageId: number;
  onSelectStage: (id: number) => void;
}

export const DemoStageSelector: React.FC<DemoStageSelectorProps> = ({
  stages,
  currentStageId,
  onSelectStage,
}) => {
  return (
    <div className="glass-panel p-4 space-y-3 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <span className="font-bold text-slate-200 uppercase tracking-wider text-[11px]">Lifecycle Stages</span>
        <span className="text-slate-400 text-[10px]">{currentStageId} / {stages.length}</span>
      </div>

      <div className="space-y-1.5 max-h-[600px] overflow-y-auto pr-1">
        {stages.map((stage) => {
          const isCurrent = stage.id === currentStageId;
          const isPassed = stage.id < currentStageId;

          return (
            <button
              key={stage.id}
              onClick={() => onSelectStage(stage.id)}
              className={`w-full text-left p-2.5 rounded-lg border transition-all flex items-center justify-between gap-2 ${
                isCurrent
                  ? 'bg-amber-950/60 border-amber-500/80 text-amber-200 shadow-md font-bold'
                  : isPassed
                  ? 'bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-800/60'
                  : 'bg-slate-950/40 border-slate-900 text-slate-500 hover:text-slate-400'
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                {isPassed ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                ) : isCurrent ? (
                  <PlayCircle className="w-3.5 h-3.5 text-amber-400 shrink-0 animate-pulse" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                )}
                <span className="truncate text-[11px]">#{stage.id}. {stage.name}</span>
              </div>

              <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                isCurrent ? 'bg-amber-900 text-amber-200' : 'bg-slate-800 text-slate-400'
              }`}>
                {stage.state}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
