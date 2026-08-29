import React, { useEffect, useState } from 'react';
import { operationsApi, SLAReport, ExceptionsReport, ActionRequiredDispute, ReconciliationRequiredDispute } from '../api/operations';
import { OperationalAlert, OperationalHealthResponse, AlertSummaryResponse } from '../api/types';
import { SkeletonLoader } from '../components/ui/SkeletonLoader';

import { OperationsHeader } from '../components/operations/OperationsHeader';
import { OperationalAlertQueue } from '../components/operations/OperationalAlertQueue';
import { AlertDetailDrawer } from '../components/operations/AlertDetailDrawer';
import { AcknowledgeAlertModal } from '../components/operations/AcknowledgeAlertModal';
import { SLACommandCenter } from '../components/operations/SLACommandCenter';
import { ExceptionPanel } from '../components/operations/ExceptionPanel';
import { ActionRequiredQueue } from '../components/operations/ActionRequiredQueue';
import { ReconciliationQueue } from '../components/operations/ReconciliationQueue';
import { OperationsRefreshBar } from '../components/operations/OperationsRefreshBar';

interface OperationsPageProps {
  onShowToast: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const OperationsPage: React.FC<OperationsPageProps> = ({ onShowToast }) => {
  const [health, setHealth] = useState<OperationalHealthResponse | null>(null);
  const [alertsSummary, setAlertsSummary] = useState<AlertSummaryResponse | null>(null);
  const [alerts, setAlerts] = useState<OperationalAlert[]>([]);
  const [slaReport, setSlaReport] = useState<SLAReport | null>(null);
  const [exceptionsReport, setExceptionsReport] = useState<ExceptionsReport | null>(null);
  const [actionRequired, setActionRequired] = useState<ActionRequiredDispute[]>([]);
  const [reconciliationRequired, setReconciliationRequired] = useState<ReconciliationRequiredDispute[]>([]);

  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [submittingAck, setSubmittingAck] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<string>(new Date().toLocaleTimeString());

  // Modal / Drawer States
  const [selectedAlert, setSelectedAlert] = useState<OperationalAlert | null>(null);
  const [ackAlertModalItem, setAckAlertModalItem] = useState<OperationalAlert | null>(null);

  const fetchAllOperationsData = async () => {
    setLoading(true);
    try {
      const [hRes, sRes, aRes, slaRes, excRes, actRes, recRes] = await Promise.all([
        operationsApi.getHealth().catch(() => null),
        operationsApi.getAlertsSummary().catch(() => null),
        operationsApi.getAlerts().catch(() => []),
        operationsApi.getSLA().catch(() => null),
        operationsApi.getExceptions().catch(() => null),
        operationsApi.getActionRequired().catch(() => []),
        operationsApi.getReconciliationRequired().catch(() => []),
      ]);

      setHealth(hRes);
      setAlertsSummary(sRes);
      setAlerts(aRes || []);
      setSlaReport(slaRes);
      setExceptionsReport(excRes);
      setActionRequired(actRes || []);
      setReconciliationRequired(recRes || []);
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch {
      // safe fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllOperationsData();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchAllOperationsData();
    }, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleDetectAlerts = async () => {
    setDetecting(true);
    try {
      // SECURITY GUARANTEE: Body is strictly empty JSON `{}`
      const res = await operationsApi.detectAlerts();
      onShowToast(
        'success',
        'Alert Detection Complete',
        `Evaluated local database state. Detected ${res.detected_count} new alerts.`
      );
      await fetchAllOperationsData();
    } catch (err: any) {
      onShowToast('error', 'Detection Failed', err.message);
    } finally {
      setDetecting(false);
    }
  };

  const handleConfirmAcknowledge = async () => {
    if (!ackAlertModalItem) return;
    setSubmittingAck(true);
    try {
      await operationsApi.acknowledgeAlert(ackAlertModalItem.id);
      onShowToast(
        'success',
        'Alert Acknowledged',
        `Alert #${ackAlertModalItem.id} marked as ACKNOWLEDGED`
      );
      setAckAlertModalItem(null);
      await fetchAllOperationsData();
    } catch (err: any) {
      onShowToast('error', 'Acknowledgment Failed', err.message);
    } finally {
      setSubmittingAck(false);
    }
  };

  if (loading && !health) {
    return <SkeletonLoader type="dashboard" />;
  }

  return (
    <div className="space-y-6">
      {/* Executive Header */}
      <OperationsHeader
        health={health}
        alertsSummary={alertsSummary}
        slaReport={slaReport}
        lastRefreshed={lastRefreshed}
        loading={loading}
        onRefresh={fetchAllOperationsData}
        onDetectAlerts={handleDetectAlerts}
        detecting={detecting}
      />

      {/* SLA & Deadline Monitoring Center */}
      <SLACommandCenter slaReport={slaReport} />

      {/* Main Operations Work Queue Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Action Required & Reconciliation (1 col) */}
        <div className="space-y-6">
          <ActionRequiredQueue disputes={actionRequired} />

          <ReconciliationQueue disputes={reconciliationRequired} />

          <ExceptionPanel exceptionsReport={exceptionsReport} />
        </div>

        {/* Right Column: Operational Alert Queue (2 cols) */}
        <div className="lg:col-span-2">
          <OperationalAlertQueue
            alerts={alerts}
            onSelectAlert={setSelectedAlert}
            onOpenAcknowledgeModal={setAckAlertModalItem}
          />
        </div>
      </div>

      {/* Refresh Bar */}
      <OperationsRefreshBar
        lastRefreshed={lastRefreshed}
        loading={loading}
        onRefresh={fetchAllOperationsData}
        autoRefreshEnabled={autoRefresh}
        onToggleAutoRefresh={() => setAutoRefresh(!autoRefresh)}
      />

      {/* Alert Detail Drawer */}
      <AlertDetailDrawer
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />

      {/* Acknowledge Alert Modal */}
      <AcknowledgeAlertModal
        alert={ackAlertModalItem}
        isOpen={!!ackAlertModalItem}
        submitting={submittingAck}
        onConfirm={handleConfirmAcknowledge}
        onClose={() => setAckAlertModalItem(null)}
      />
    </div>
  );
};
