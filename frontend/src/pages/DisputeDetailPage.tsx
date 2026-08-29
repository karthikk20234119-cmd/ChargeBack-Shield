import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { FullDisputeDetailResponse } from '../api/types';
import { SkeletonLoader } from '../components/ui/SkeletonLoader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { PolicyDecisionBadge } from '../components/ui/PolicyDecisionBadge';
import { MatchStatusBadge } from '../components/ui/MatchStatusBadge';
import { PreflightGate } from '../components/ui/PreflightGate';
import { SeverityBadge } from '../components/ui/SeverityBadge';
import {
  FileText,
  FileCheck,
  CheckCircle2,
  AlertTriangle,
  Send,
  UserCheck,
  ShieldCheck,
  History,
  ArrowLeft,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';

const stages = [
  'Dispute Ingestion',
  'Evidence Collection',
  'Artifact Processing',
  'Fact Extraction',
  'Evidence Matching',
  'Policy Evaluation',
  'Draft Generation',
  'Human Review',
  'Preflight Gate',
  'Contest Submission',
  'Reconciliation',
  'Lifecycle Sync',
  'Final Outcome',
];

export const DisputeDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<FullDisputeDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'summary' | 'evidence' | 'matching' | 'policy' | 'draft' | 'preflight' | 'submission' | 'audit'>('summary');

  const fetchDetail = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await api.getDisputeDetail(id);
      setDetail(res);
    } catch {
      // safe fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  if (loading || !detail) {
    return <SkeletonLoader type="dashboard" />;
  }

  const dispute = detail.dispute;
  const docs = detail.documents || [];
  const matching = detail.match_results;
  const policy = detail.policy_result;
  const draft = detail.contest_draft;
  const preflight = detail.preflight;
  const submission = detail.submission;

  return (
    <div className="space-y-6">
      {/* Back Navigation & Breadcrumb */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/disputes"
            className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-xl font-extrabold text-slate-100 flex items-center gap-2 font-mono">
              <span>Dispute #{dispute.id}</span>
              <StatusBadge status={dispute.status} />
            </h1>
            <p className="text-xs text-slate-400 font-mono">
              Payment ID: {dispute.payment_id} • Amount: ₹{(dispute.amount / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })} {dispute.currency}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to={`/review`}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-md glow-indigo transition-all flex items-center gap-1.5"
          >
            <UserCheck className="w-4 h-4" />
            <span>Human Review Queue</span>
          </Link>
        </div>
      </div>

      {/* 17-Stage Visual Progress Lifecycle Tracker */}
      <div className="glass-panel p-6 space-y-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">
          360° End-to-End Lifecycle Pipeline Progress
        </h3>

        <div className="overflow-x-auto pb-2">
          <div className="flex items-center min-w-max space-x-1">
            {stages.map((stg, i) => {
              const isCurrent = (
                (i === 0) ||
                (i === 1 && docs.length > 0) ||
                (i === 4 && matching) ||
                (i === 5 && policy) ||
                (i === 6 && draft) ||
                (i === 7 && draft?.review_status === 'APPROVED') ||
                (i === 8 && preflight?.status === 'READY') ||
                (i === 9 && submission?.status === 'SUBMITTED')
              );

              return (
                <React.Fragment key={i}>
                  <div className={`px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-all ${
                    isCurrent
                      ? 'bg-brand-950 text-brand-300 border-brand-700 font-semibold glow-blue'
                      : 'bg-slate-900/60 text-slate-500 border-slate-800/80'
                  }`}>
                    <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                    <span>{stg}</span>
                  </div>
                  {i < stages.length - 1 && <ChevronRight className="w-3.5 h-3.5 text-slate-700 shrink-0" />}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800 overflow-x-auto pb-1 font-mono text-xs">
        {[
          { key: 'summary', label: 'Summary' },
          { key: 'evidence', label: `Evidence (${docs.length})` },
          { key: 'matching', label: 'Matching' },
          { key: 'policy', label: 'Policy' },
          { key: 'draft', label: 'Contest Draft' },
          { key: 'preflight', label: 'Preflight Gate' },
          { key: 'submission', label: 'Submission & Sync' },
          { key: 'audit', label: 'Audit Trail' },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key as any)}
            className={`px-4 py-2.5 rounded-t-lg border-b-2 font-semibold transition-all ${
              activeTab === t.key
                ? 'border-brand-500 text-brand-400 bg-slate-900/80'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Summary Overview */}
      {activeTab === 'summary' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 glass-panel p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <FileText className="w-5 h-5 text-brand-400" />
              <span>Dispute Financial & Context Metadata</span>
            </h3>

            <div className="grid grid-cols-2 gap-4 font-mono text-xs">
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
                <span className="text-slate-500">Trusted Dispute ID</span>
                <p className="font-bold text-slate-200">{dispute.id}</p>
              </div>
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
                <span className="text-slate-500">Trusted Payment ID</span>
                <p className="font-bold text-slate-200">{dispute.payment_id}</p>
              </div>
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
                <span className="text-slate-500">Dispute Amount</span>
                <p className="font-bold text-emerald-400">
                  ₹{(dispute.amount / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })} {dispute.currency}
                </p>
              </div>
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-1">
                <span className="text-slate-500">Reason Code</span>
                <p className="font-bold text-indigo-400">{dispute.reason_code}</p>
              </div>
            </div>
          </div>

          <div className="glass-panel p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-100 border-b border-slate-800 pb-3">
              Policy & Review Summary
            </h3>

            {policy && (
              <div className="space-y-2">
                <span className="text-xs text-slate-400">Policy Outcome:</span>
                <div>
                  <PolicyDecisionBadge decision={policy.decision} />
                </div>
                <p className="text-xs text-slate-300 mt-2">{policy.summary}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Evidence Section */}
      {activeTab === 'evidence' && (
        <div className="glass-panel p-6 space-y-4">
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-indigo-400" />
            <span>Uploaded Evidence Documents & Extracted Facts</span>
          </h3>

          <div className="space-y-4">
            {docs.map((doc) => (
              <div key={doc.id} className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">{doc.original_filename}</span>
                  <StatusBadge status={doc.processing_status} size="sm" />
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-slate-400 bg-slate-950/60 p-2.5 rounded-lg border border-slate-900">
                  <div>Document ID: <span className="text-slate-200">{doc.id}</span></div>
                  <div>MIME: <span className="text-slate-200">{doc.mime_type}</span></div>
                  <div>Size: <span className="text-slate-200">{(doc.file_size_bytes / 1024).toFixed(1)} KB</span></div>
                  <div>SHA-256: <span className="text-slate-200 text-[10px] truncate">{doc.file_hash?.substring(0, 16)}...</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Matching Section */}
      {activeTab === 'matching' && matching && (
        <div className="glass-panel p-6 space-y-4">
          <h3 className="text-base font-bold text-slate-100">
            Deterministic Fact Matching Details
          </h3>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Fact Name</th>
                  <th className="py-3 px-4">Expected Value</th>
                  <th className="py-3 px-4">Observed Value</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Explanation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {matching?.results?.map((m, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/50">
                    <td className="py-3 px-4 font-bold text-slate-200">{m.field_name}</td>
                    <td className="py-3 px-4 text-emerald-400">{String(m.expected_value)}</td>
                    <td className="py-3 px-4 text-indigo-400">{String(m.observed_value)}</td>
                    <td className="py-3 px-4">
                      <MatchStatusBadge status={m.status} />
                    </td>
                    <td className="py-3 px-4 text-slate-300 font-sans">{m.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Policy Section */}
      {activeTab === 'policy' && policy && (
        <div className="glass-panel p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-100">Deterministic Policy Engine Results</h3>
              <p className="text-xs text-slate-400">Version: {policy.policy_version}</p>
            </div>
            <PolicyDecisionBadge decision={policy.decision} />
          </div>

          <div className="space-y-3">
            {policy?.rules_evaluated?.map((r) => (
              <div key={r.rule_id} className={`p-4 rounded-xl border text-xs font-mono ${
                r.passed ? 'bg-emerald-950/30 border-emerald-800/60' : 'bg-rose-950/30 border-rose-800/60'
              }`}>
                <div className="flex items-center justify-between font-bold">
                  <span>{r.name} ({r.rule_id})</span>
                  <span className={r.passed ? 'text-emerald-400' : 'text-rose-400'}>
                    {r.passed ? 'PASSED' : 'FAILED'}
                  </span>
                </div>
                <p className="text-slate-300 font-sans mt-1">{r.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 5: Contest Draft Section */}
      {activeTab === 'draft' && draft && (
        <div className="glass-panel p-6 space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-100 font-sans">{draft.title}</h3>
              <p className="text-slate-400">Fingerprint: {draft.input_fingerprint}</p>
            </div>
            <StatusBadge status={draft.review_status} />
          </div>

          <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-2">
            <h4 className="font-bold text-slate-200 font-sans">Draft Summary:</h4>
            <p className="text-slate-300 font-sans leading-relaxed">{draft.summary}</p>
          </div>
        </div>
      )}

      {/* Tab 6: Preflight Gate */}
      {activeTab === 'preflight' && preflight && (
        <PreflightGate
          status={preflight.status}
          checks={preflight.checks}
          blockingReasons={preflight.blocking_reasons}
        />
      )}

      {/* Tab 7: Submission & Sync */}
      {activeTab === 'submission' && (
        <div className="glass-panel p-6 space-y-4 font-mono text-xs">
          <h3 className="text-base font-bold text-slate-100 font-sans">Contest Submission & Status Synchronization</h3>

          {submission ? (
            <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Submission Status:</span>
                <StatusBadge status={submission.status} />
              </div>
              <div>Idempotency Key: <span className="text-indigo-400">{submission.idempotency_key}</span></div>
            </div>
          ) : (
            <p className="text-slate-400">No contest submission executed yet.</p>
          )}
        </div>
      )}

      {/* Tab 8: Audit Trail */}
      {activeTab === 'audit' && (
        <div className="glass-panel p-6 space-y-4">
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <History className="w-5 h-5 text-brand-400" />
            <span>Dispute Lifecycle Audit Event History</span>
          </h3>

          <div className="space-y-3">
            {detail.alerts?.map((a) => (
              <div key={a.id} className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 text-xs font-mono flex items-center justify-between">
                <div>
                  <span className="text-slate-400">{a.code}</span> — <span className="text-slate-200">{a.message}</span>
                </div>
                <SeverityBadge severity={a.severity} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
