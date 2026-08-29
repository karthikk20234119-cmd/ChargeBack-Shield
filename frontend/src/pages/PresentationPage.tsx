import React, { useState } from 'react';
import { PresentationHeader } from '../components/presentation/PresentationHeader';
import { ProblemSection } from '../components/presentation/ProblemSection';
import { SolutionSection } from '../components/presentation/SolutionSection';
import { ArchitectureFlowSection } from '../components/presentation/ArchitectureFlowSection';
import { SecurityBoundariesSection } from '../components/presentation/SecurityBoundariesSection';
import { IntelligenceMetricsSection } from '../components/presentation/IntelligenceMetricsSection';
import { ValuePropositionSection } from '../components/presentation/ValuePropositionSection';

export const PresentationPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('ALL');

  const showAll = activeTab === 'ALL';

  return (
    <div className="space-y-6">
      {/* Header */}
      <PresentationHeader activeTab={activeTab} onSelectTab={setActiveTab} />

      {/* Sections based on tab selection */}
      {(showAll || activeTab === 'PROBLEM') && <ProblemSection />}
      {(showAll || activeTab === 'SOLUTION') && <SolutionSection />}
      {(showAll || activeTab === 'ARCHITECTURE') && <ArchitectureFlowSection />}
      {(showAll || activeTab === 'SECURITY') && <SecurityBoundariesSection />}
      {(showAll || activeTab === 'INTELLIGENCE') && <IntelligenceMetricsSection />}
      {(showAll || activeTab === 'VALUE') && <ValuePropositionSection />}
    </div>
  );
};
