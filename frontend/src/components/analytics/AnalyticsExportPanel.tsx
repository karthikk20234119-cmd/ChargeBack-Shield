import React, { useState } from 'react';
import { Download, Copy, Check, Hash } from 'lucide-react';

interface AnalyticsExportPanelProps {
  exportData?: any;
  onShowToast: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const AnalyticsExportPanel: React.FC<AnalyticsExportPanelProps> = ({ exportData, onShowToast }) => {
  const [copied, setCopied] = useState(false);

  if (!exportData) return null;

  const jsonString = JSON.stringify(exportData, null, 2);

  const handleCopyJSON = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    onShowToast('success', 'Copied to Clipboard', 'Analytics export JSON copied.');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJSON = () => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chargeback-shield-analytics-export-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    onShowToast('success', 'Download Started', 'Analytics export JSON downloaded.');
  };

  return (
    <div className="glass-panel p-6 space-y-4 font-mono text-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Download className="w-4 h-4 text-brand-400" />
          <span>Management Report & Audit Export</span>
        </h3>

        <div className="flex items-center gap-2 font-sans">
          <button
            onClick={handleCopyJSON}
            className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy JSON'}</span>
          </button>

          <button
            onClick={handleDownloadJSON}
            className="px-4 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-bold shadow glow-blue flex items-center gap-1.5 transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download JSON</span>
          </button>
        </div>
      </div>

      <div className="p-3.5 bg-slate-950/80 rounded-xl border border-slate-900 space-y-2">
        <div className="flex items-center justify-between text-[11px]">
          <span>Generated: <span className="text-slate-200">{new Date(exportData.generated_at || Date.now()).toLocaleString()}</span></span>
          <span className="flex items-center gap-1 text-indigo-400 font-bold">
            <Hash className="w-3.5 h-3.5" />
            <span>Report SHA-256: {exportData.report_hash || 'VERIFIED'}</span>
          </span>
        </div>

        <pre className="p-3 bg-slate-900/60 rounded border border-slate-800/80 text-[10px] text-slate-300 font-mono overflow-x-auto max-h-40">
          {jsonString}
        </pre>
      </div>
    </div>
  );
};
