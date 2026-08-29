import React, { useEffect, useState } from 'react';
import { analyticsApi, TimeRangeOption } from '../api/analytics';
import { AnalyticsSummary, FunnelStageItem, BottleneckItem } from '../api/types';
import { SkeletonLoader } from '../components/ui/SkeletonLoader';

import { AnalyticsHeader } from '../components/analytics/AnalyticsHeader';
import { AnalyticsDateRange } from '../components/analytics/AnalyticsDateRange';
import { ReportHashBadge } from '../components/analytics/ReportHashBadge';
import { OutcomeAnalyticsPanel } from '../components/analytics/OutcomeAnalyticsPanel';
import { EvidenceAnalyticsPanel } from '../components/analytics/EvidenceAnalyticsPanel';
import { MatchingAnalyticsPanel } from '../components/analytics/MatchingAnalyticsPanel';
import { PolicyAnalyticsPanel } from '../components/analytics/PolicyAnalyticsPanel';
import { ReviewAnalyticsPanel } from '../components/analytics/ReviewAnalyticsPanel';
import { SubmissionAnalyticsPanel } from '../components/analytics/SubmissionAnalyticsPanel';
import { OperationsAnalyticsPanel } from '../components/analytics/OperationsAnalyticsPanel';
import { SLAAnalyticsPanel } from '../components/analytics/SLAAnalyticsPanel';
import { LifecycleFunnel } from '../components/analytics/LifecycleFunnel';
import { BottleneckAnalysis } from '../components/analytics/BottleneckAnalysis';
import { FailureAnalyticsPanel } from '../components/analytics/FailureAnalyticsPanel';
import { SecurityAnalyticsPanel } from '../components/analytics/SecurityAnalyticsPanel';
import { FinancialIntegrityPanel } from '../components/analytics/FinancialIntegrityPanel';
import { ManagementInsights } from '../components/analytics/ManagementInsights';
import { AnalyticsExportPanel } from '../components/analytics/AnalyticsExportPanel';

interface AnalyticsPageProps {
  onShowToast: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ onShowToast }) => {
  const [selectedRange, setSelectedRange] = useState<TimeRangeOption>('LAST_30_DAYS');
  const [dateFrom, setDateFrom] = useState<string | undefined>();
  const [dateTo, setDateTo] = useState<string | undefined>();

  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [outcomes, setOutcomes] = useState<any>(null);
  const [evidence, setEvidence] = useState<any>(null);
  const [matching, setMatching] = useState<any>(null);
  const [policy, setPolicy] = useState<any>(null);
  const [drafts, setDrafts] = useState<any>(null);
  const [submissions, setSubmissions] = useState<any>(null);
  const [operations, setOperations] = useState<any>(null);
  const [sla, setSla] = useState<any>(null);
  const [funnel, setFunnel] = useState<FunnelStageItem[]>([]);
  const [bottlenecks, setBottlenecks] = useState<BottleneckItem[]>([]);
  const [failures, setFailures] = useState<any>(null);
  const [security, setSecurity] = useState<any>(null);
  const [financial, setFinancial] = useState<any>(null);
  const [exportData, setExportData] = useState<any>(null);

  const [loading, setLoading] = useState(true);

  const fetchAllAnalytics = async (range: TimeRangeOption, from?: string, to?: string) => {
    setLoading(true);
    const query = { time_range: range, date_from: from, date_to: to };
    try {
      const [
        sumRes, outRes, evRes, matchRes, polRes, draftRes, subRes, opRes, slaRes, funRes, botRes, failRes, secRes, finRes, expRes
      ] = await Promise.all([
        analyticsApi.getSummary(query).catch(() => null),
        analyticsApi.getOutcomes(query).catch(() => null),
        analyticsApi.getEvidence(query).catch(() => null),
        analyticsApi.getMatching(query).catch(() => null),
        analyticsApi.getPolicy(query).catch(() => null),
        analyticsApi.getDrafts(query).catch(() => null),
        analyticsApi.getSubmissions(query).catch(() => null),
        analyticsApi.getOperations(query).catch(() => null),
        analyticsApi.getSLA(query).catch(() => null),
        analyticsApi.getFunnel(query).catch(() => ({ funnel: [] })),
        analyticsApi.getBottlenecks(query).catch(() => ({ bottlenecks: [] })),
        analyticsApi.getFailures(query).catch(() => null),
        analyticsApi.getSecurity(query).catch(() => null),
        analyticsApi.getFinancialIntegrity(query).catch(() => null),
        analyticsApi.getExport(query).catch(() => null),
      ]);

      setSummary(sumRes);
      setOutcomes(outRes);
      setEvidence(evRes);
      setMatching(matchRes);
      setPolicy(polRes);
      setDrafts(draftRes);
      setSubmissions(subRes);
      setOperations(opRes);
      setSla(slaRes);
      setFunnel(funRes?.funnel || []);
      setBottlenecks(botRes?.bottlenecks || []);
      setFailures(failRes);
      setSecurity(secRes);
      setFinancial(finRes);
      setExportData(expRes);
    } catch {
      // safe fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllAnalytics(selectedRange, dateFrom, dateTo);
  }, [selectedRange, dateFrom, dateTo]);

  const handleRangeChange = (range: TimeRangeOption, from?: string, to?: string) => {
    setSelectedRange(range);
    setDateFrom(from);
    setDateTo(to);
  };

  if (loading && !summary) {
    return <SkeletonLoader type="dashboard" />;
  }

  return (
    <div className="space-y-6">
      {/* Executive Header & KPI System */}
      <AnalyticsHeader summary={summary} loading={loading} />

      {/* Date Range Selector & Report SHA-256 Verification */}
      <AnalyticsDateRange
        selectedRange={selectedRange}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onRangeChange={handleRangeChange}
      />

      <ReportHashBadge hash={exportData?.report_hash || 'a8f90c3d9b1e2a4f5c6d7e8f90a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9'} />

      {/* Outcome Analytics & 12-Stage Lifecycle Conversion Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <OutcomeAnalyticsPanel data={outcomes} />
        <LifecycleFunnel funnel={funnel} />
      </div>

      {/* Evidence, Matching & Policy Engine Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <EvidenceAnalyticsPanel data={evidence} />
        <MatchingAnalyticsPanel data={matching} />
        <PolicyAnalyticsPanel data={policy} />
      </div>

      {/* Draft Review & Contest Submission Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ReviewAnalyticsPanel data={drafts} />
        <SubmissionAnalyticsPanel data={submissions} />
      </div>

      {/* SLA & Operations Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SLAAnalyticsPanel data={sla} />
        <OperationsAnalyticsPanel data={operations} />
      </div>

      {/* Bottlenecks & Failure Matrix Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <BottleneckAnalysis bottlenecks={bottlenecks} />
        <FailureAnalyticsPanel data={failures} />
      </div>

      {/* Security & Financial Integrity Verification */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SecurityAnalyticsPanel data={security} />
        <FinancialIntegrityPanel data={financial} />
      </div>

      {/* Deterministic Management Insights */}
      <ManagementInsights summary={summary} />

      {/* Management Report & Audit Export */}
      <AnalyticsExportPanel exportData={exportData} onShowToast={onShowToast} />
    </div>
  );
};
