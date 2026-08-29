import React from 'react';
import { Presentation, ShieldAlert, Award } from 'lucide-react';

interface PresentationHeaderProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
}

export const PresentationHeader: React.FC<PresentationHeaderProps> = ({
  activeTab,
  onSelectTab,
}) => {
  const tabs = [
    { key: 'ALL', label: 'Complete Overview' },
    { key: 'PROBLEM', label: 'A. Problem' },
    { key: 'SOLUTION', label: 'B. Solution' },
    { key: 'ARCHITECTURE', label: 'C. Architecture' },
    { key: 'SECURITY', label: 'D. Security' },
    { key: 'INTELLIGENCE', label: 'E. Intelligence' },
    { key: 'VALUE', label: 'F. Value Proposition' },
  ];

  return (
    <div className="glass-panel p-6 space-y-4 border-l-4 border-l-purple-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>EXECUTIVE PRESENTATION VIEW</span>
            <span>•</span>
            <span className="text-purple-400 font-bold">3–5 MINUTE MANAGEMENT STORY</span>
            <span>•</span>
            <span className="text-emerald-400">READ-ONLY PRESENTATION</span>
          </div>

          <h1 className="text-2xl font-extrabold text-slate-100 font-mono mt-1 flex items-center gap-3">
            <span>Chargeback Shield — Executive Intelligence Story</span>
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-purple-950 text-purple-300 border border-purple-800 glow-purple">
              MANAGEMENT BRIEF
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-slate-950/80 px-3.5 py-2 rounded-lg border border-slate-800">
          <Award className="w-4 h-4 text-purple-400" />
          <span>Hackathon & Production Demo Ready</span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex flex-wrap items-center gap-2 font-mono text-xs pt-1 border-t border-slate-800/80">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => onSelectTab(t.key)}
            className={`px-3 py-1.5 rounded-lg border font-semibold transition-all ${
              activeTab === t.key
                ? 'bg-purple-600 border-purple-500 text-white shadow glow-purple'
                : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
};
