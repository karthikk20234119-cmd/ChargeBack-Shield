import React, { useState } from 'react';
import { DEMO_STAGES } from '../data/demoFixtures';
import { DemoHeader } from '../components/demo/DemoHeader';
import { DemoStageSelector } from '../components/demo/DemoStageSelector';
import { DemoStageViewer } from '../components/demo/DemoStageViewer';
import { DemoBoundaryInspector } from '../components/demo/DemoBoundaryInspector';

export const DemoPage: React.FC = () => {
  const [currentStageId, setCurrentStageId] = useState(1);

  const currentStage = DEMO_STAGES.find((s) => s.id === currentStageId) || DEMO_STAGES[0];

  const handlePrevStage = () => {
    if (currentStageId > 1) setCurrentStageId(currentStageId - 1);
  };

  const handleNextStage = () => {
    if (currentStageId < DEMO_STAGES.length) setCurrentStageId(currentStageId + 1);
  };

  const handleReset = () => {
    setCurrentStageId(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <DemoHeader
        currentStageId={currentStageId}
        totalStages={DEMO_STAGES.length}
        onPrevStage={handlePrevStage}
        onNextStage={handleNextStage}
        onReset={handleReset}
      />

      {/* Main Demo Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Stage Selector (1 col) */}
        <div>
          <DemoStageSelector
            stages={DEMO_STAGES}
            currentStageId={currentStageId}
            onSelectStage={setCurrentStageId}
          />
        </div>

        {/* Right Column: Stage Inspector & Boundaries (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <DemoStageViewer stage={currentStage} />

          <DemoBoundaryInspector />
        </div>
      </div>
    </div>
  );
};
