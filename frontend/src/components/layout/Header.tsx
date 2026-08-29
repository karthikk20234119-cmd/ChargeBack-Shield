import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { OperationalHealthResponse, AlertSummaryResponse } from '../../api/types';
import { Bell, ShieldCheck, AlertTriangle, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Header: React.FC = () => {
  const [health, setHealth] = useState<OperationalHealthResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchHeaderMetrics = async () => {
    setLoading(true);
    try {
      const [hRes, aRes] = await Promise.all([
        api.getOperationalHealth().catch(() => null),
        api.getAlertsSummary().catch(() => null),
      ]);
      setHealth(hRes);
      setAlerts(aRes);
    } catch {
      // safe error handling
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHeaderMetrics();
    const interval = setInterval(fetchHeaderMetrics, 30000);
    return () => clearInterval(interval);
  }, []);

  const healthStatus = health?.status || 'HEALTHY';
  const openAlerts = alerts?.open_count || 0;
  const criticalAlerts = alerts?.critical_count || 0;

  return (
    <header className="h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800/80 px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <span>Operational Dispute Control Center</span>
          <span className="text-slate-600">•</span>
          <span className="text-xs font-mono text-slate-400">READ-ONLY REST LAYER</span>
        </h2>
      </div>

      <div className="flex items-center gap-4">
        {/* System Health Badge */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-950/80 border border-slate-800 text-xs">
          <ShieldCheck className={`w-4 h-4 ${healthStatus === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400'}`} />
          <span className="text-slate-400 font-mono">SYSTEM:</span>
          <span className={`font-semibold font-mono ${healthStatus === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400'}`}>
            {healthStatus}
          </span>
        </div>

        {/* Operational Alerts Counter Link */}
        <Link
          to="/operations"
          className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-950/80 border border-slate-800 text-xs hover:border-slate-700 transition-colors"
        >
          <Bell className={`w-4 h-4 ${criticalAlerts > 0 ? 'text-rose-400 animate-pulse' : 'text-slate-400'}`} />
          <span className="text-slate-400 font-mono">ALERTS:</span>
          <span className={`font-bold font-mono ${criticalAlerts > 0 ? 'text-rose-400' : 'text-slate-200'}`}>
            {openAlerts}
          </span>
          {criticalAlerts > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-rose-950 text-rose-300 text-[10px] border border-rose-800 font-mono">
              {criticalAlerts} CRITICAL
            </span>
          )}
        </Link>

        {/* Refresh Button */}
        <button
          onClick={fetchHeaderMetrics}
          disabled={loading}
          className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 rounded-lg transition-colors disabled:opacity-50"
          title="Refresh Operational Metrics"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>
    </header>
  );
};
