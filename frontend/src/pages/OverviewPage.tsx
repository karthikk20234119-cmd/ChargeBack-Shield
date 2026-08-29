import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { DashboardSummaryResponse, OperationalHealthResponse, AlertSummaryResponse } from '../api/types';
import { SkeletonLoader } from '../components/ui/SkeletonLoader';
import { SeverityBadge } from '../components/ui/SeverityBadge';
import {
  FileSpreadsheet,
  Trophy,
  AlertTriangle,
  Send,
  FileCheck,
  Activity,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const OverviewPage: React.FC = () => {
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, number>>({});
  const [health, setHealth] = useState<OperationalHealthResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [sumRes, outRes, healthRes, alertsRes] = await Promise.all([
          api.getDashboardSummary(),
          api.getDashboardOutcomes(),
          api.getOperationalHealth(),
          api.getAlertsSummary(),
        ]);
        setSummary(sumRes);
        setOutcomes(outRes);
        setHealth(healthRes);
        setAlerts(alertsRes);
      } catch {
        // Safe error fallback
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return <SkeletonLoader type="card" />;
  }

  const kpis = [
    {
      title: 'Total Disputes',
      value: summary?.total_disputes || 0,
      sub: `${summary?.open_disputes || 0} active / pending`,
      icon: FileSpreadsheet,
      color: 'text-brand-400',
      bg: 'bg-brand-950/40 border-brand-800/60',
    },
    {
      title: 'Win Rate',
      value: `${summary?.win_rate_percentage || 0}%`,
      sub: `${summary?.won_disputes || 0} won / ${summary?.lost_disputes || 0} lost`,
      icon: Trophy,
      color: 'text-emerald-400',
      bg: 'bg-emerald-950/40 border-emerald-800/60',
    },
    {
      title: 'Submissions',
      value: summary?.submissions_submitted_count || 0,
      sub: `${summary?.submissions_unknown_count || 0} unknown / reconciliation`,
      icon: Send,
      color: 'text-indigo-400',
      bg: 'bg-indigo-950/40 border-indigo-800/60',
    },
    {
      title: 'Active Alerts',
      value: summary?.active_alerts_count || 0,
      sub: `${summary?.critical_alerts_count || 0} critical severity`,
      icon: AlertTriangle,
      color: summary?.critical_alerts_count ? 'text-rose-400' : 'text-amber-400',
      bg: summary?.critical_alerts_count ? 'bg-rose-950/40 border-rose-800/60' : 'bg-amber-950/40 border-amber-800/60',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Title & System Status Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
            360° Operational Control Center
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time dispute lifecycle monitoring & deterministic evidence processing
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/disputes"
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-lg shadow-lg glow-blue transition-all flex items-center gap-1.5"
          >
            <span>View All Disputes</span>
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div key={idx} className={`p-5 rounded-xl border ${kpi.bg} backdrop-blur-md shadow-xl flex items-start justify-between`}>
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{kpi.title}</p>
                <h3 className="text-2xl font-black text-slate-100 font-mono">{kpi.value}</h3>
                <p className="text-xs text-slate-400">{kpi.sub}</p>
              </div>
              <div className={`p-3 rounded-lg bg-slate-900/80 border border-slate-800 ${kpi.color}`}>
                <Icon className="w-6 h-6" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Lifecycle Stage Breakdown & Health Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stage Progress Summary */}
        <div className="lg:col-span-2 glass-panel p-6 space-y-4">
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
            <Activity className="w-5 h-5 text-brand-400" />
            <span>Dispute Pipeline Stage Metrics</span>
          </h3>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div className="p-3.5 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400">Evidence Ingested</span>
              <p className="text-lg font-bold font-mono text-slate-200">{summary?.total_evidence_documents || 0}</p>
              <p className="text-[10px] text-emerald-400">{summary?.processed_evidence_documents || 0} processed</p>
            </div>

            <div className="p-3.5 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400">Policy Eligible</span>
              <p className="text-lg font-bold font-mono text-emerald-400">{summary?.policy_eligible_count || 0}</p>
              <p className="text-[10px] text-amber-400">{summary?.policy_human_review_count || 0} review required</p>
            </div>

            <div className="p-3.5 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400">Drafts Generated</span>
              <p className="text-lg font-bold font-mono text-indigo-400">{summary?.drafts_generated_count || 0}</p>
              <p className="text-[10px] text-emerald-400">{summary?.drafts_approved_count || 0} approved</p>
            </div>

            <div className="p-3.5 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400">Preflight Authorized</span>
              <p className="text-lg font-bold font-mono text-emerald-400">{summary?.preflight_ready_count || 0}</p>
              <p className="text-[10px] text-slate-400">Gate checks passed</p>
            </div>

            <div className="p-3.5 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400">Submissions</span>
              <p className="text-lg font-bold font-mono text-brand-400">{summary?.submissions_submitted_count || 0}</p>
              <p className="text-[10px] text-rose-400">{summary?.submissions_failed_count || 0} failed</p>
            </div>

            <div className="p-3.5 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400">Reconciliation Req.</span>
              <p className="text-lg font-bold font-mono text-amber-400">{summary?.reconciliation_required_count || 0}</p>
              <p className="text-[10px] text-slate-400">Read-only sync</p>
            </div>
          </div>
        </div>

        {/* Operational Alerts & System Health Widget */}
        <div className="glass-panel p-6 space-y-4">
          <h3 className="text-base font-bold text-slate-100 flex items-center justify-between border-b border-slate-800 pb-3">
            <span className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <span>Operational Health</span>
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
              {health?.status || 'HEALTHY'}
            </span>
          </h3>

          <div className="space-y-3">
            {alerts?.alerts.slice(0, 4).map((a) => (
              <div key={a.id} className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <SeverityBadge severity={a.severity} />
                  <span className="text-[10px] font-mono text-slate-500">{a.code}</span>
                </div>
                <p className="text-xs text-slate-300 line-clamp-2">{a.message}</p>
              </div>
            ))}
          </div>

          <Link
            to="/operations"
            className="block text-center w-full py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-lg transition-colors"
          >
            Manage Operations & Alerts →
          </Link>
        </div>
      </div>
    </div>
  );
};
