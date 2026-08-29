import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { EvidenceDocument } from '../api/types';
import { SkeletonLoader } from '../components/ui/SkeletonLoader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { FileSearch, FileText, Lock } from 'lucide-react';

export const EvidencePage: React.FC = () => {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Evidence collection view
    const timer = setTimeout(() => setLoading(false), 300);
    return () => clearTimeout(timer);
  }, []);

  if (loading) return <SkeletonLoader type="table" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          Evidence Collection & Ingestion Vault
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Bounded stream ingestion, SHA-256 integrity verification, magic-byte validation & secure artifact storage
        </p>
      </div>

      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center gap-3 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
          <Lock className="w-5 h-5 text-emerald-400" />
          <div className="text-xs">
            <h4 className="font-bold text-slate-200">Security & Privacy Protection Active</h4>
            <p className="text-slate-400">Zero sensitive header exposure, atomic temp file cleanup, and strict path containment verification.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
