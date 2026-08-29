import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import { ToastMessage } from './components/ui/ToastContainer';
import { ErrorBoundary } from './components/ui/ErrorBoundary';

import {
  OverviewPage,
  DisputeListPage,
  DisputeDetailPage,
  EvidencePage,
  MatchingPage,
  PolicyPage,
  ContestDraftPage,
  HumanReviewPage,
  PreflightPage,
  SubmissionPage,
  LifecyclePage,
  OperationsPage,
  AnalyticsPage,
  AuditPage,
  DemoPage,
  PresentationPage,
  ObservabilityPage,
  NotFoundPage,
} from './pages';

export const App: React.FC = () => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <Router>
      <MainLayout toasts={toasts} onDismissToast={dismissToast}>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/disputes" element={<DisputeListPage />} />
            <Route path="/disputes/:id" element={<DisputeDetailPage />} />
            <Route path="/evidence" element={<EvidencePage />} />
            <Route path="/matching" element={<MatchingPage />} />
            <Route path="/policy" element={<PolicyPage />} />
            <Route path="/draft" element={<ContestDraftPage />} />
            <Route path="/review" element={<HumanReviewPage onShowToast={addToast} />} />
            <Route path="/preflight" element={<PreflightPage />} />
            <Route path="/submission" element={<SubmissionPage />} />
            <Route path="/lifecycle" element={<LifecyclePage />} />
            <Route path="/operations" element={<OperationsPage onShowToast={addToast} />} />
            <Route path="/alerts" element={<Navigate to="/operations" replace />} />
            <Route path="/analytics" element={<AnalyticsPage onShowToast={addToast} />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/observability" element={<ObservabilityPage />} />
            <Route path="/demo" element={<DemoPage />} />
            <Route path="/presentation" element={<PresentationPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </MainLayout>
    </Router>
  );
};
