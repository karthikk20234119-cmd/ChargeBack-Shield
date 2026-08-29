import React from 'react';
import { DEMO_DATA_TAG } from '../../data/demoFixtures';
import { Play, ShieldAlert, ArrowLeft, ArrowRight, RefreshCw } from 'lucide-react';

interface DemoHeaderProps {
  currentStageId: number;
  totalStages: number;
  onPrevStage: () => void;
  onNextStage: () => void;
  onReset: () => void;
}

export const DemoHeader: React.FC<DemoHeaderProps> = ({
  currentStageId,
  totalStages,
  onPrevStage,
  onNextStage,
  onReset,
}) => {
  return (
    <div className="glass-panel p-6 space-y-4 border-l-4 border-l-amber-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>GUIDED DEMO MODE</span>
            <span>•</span>
            <span className="text-amber-400 font-bold">{DEMO_DATA_TAG}</span>
            <span>•</span>
            <span>Stage {currentStageId} of {totalStages}</span>
          </div>

          <h1 className="text-2xl font-extrabold text-slate-100 font-mono mt-1 flex items-center gap-3">
            <span>17-Stage Chargeback Lifecycle Simulation</span>
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-950 text-amber-300 border border-amber-800 glow-amber">
              INTERACTIVE DEMO
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-3 font-sans">
          <button
            onClick={onPrevStage}
            disabled={currentStageId === 1}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Previous</span>
          </button>

          <button
            onClick={onNextStage}
            disabled={currentStageId === totalStages}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-xs font-bold rounded-lg shadow-lg glow-amber flex items-center gap-1.5 transition-all"
          >
            <span>Next Stage</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <button
            onClick={onReset}
            className="px-3 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 text-xs font-semibold rounded-lg transition-colors"
            title="Reset to Stage 1"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
