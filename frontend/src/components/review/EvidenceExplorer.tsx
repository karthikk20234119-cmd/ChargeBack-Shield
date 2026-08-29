import React from 'react';
import { EvidenceDocument } from '../../api/types';
import { StatusBadge } from '../ui/StatusBadge';
import { FileText, FileCheck, Lock, Eye } from 'lucide-react';

interface EvidenceExplorerProps {
  documents: EvidenceDocument[];
  selectedDocId?: string;
  onSelectDoc?: (doc: EvidenceDocument) => void;
}

export const EvidenceExplorer: React.FC<EvidenceExplorerProps> = ({
  documents,
  selectedDocId,
  onSelectDoc,
}) => {
  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-indigo-400" />
          <span>Evidence Document Explorer ({documents.length})</span>
        </h3>
        <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
          <Lock className="w-3 h-3" />
          SHA-256 Verified
        </span>
      </div>

      {documents.length === 0 ? (
        <p className="text-xs text-slate-400 font-mono">No evidence documents associated with this dispute.</p>
      ) : (
        <div className="space-y-3">
          {documents.map((doc) => {
            const isSelected = selectedDocId === doc.id;
            return (
              <div
                key={doc.id}
                onClick={() => onSelectDoc && onSelectDoc(doc)}
                className={`p-3.5 rounded-xl border text-xs font-mono transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-indigo-950/80 border-indigo-600 text-indigo-200 glow-indigo'
                    : 'bg-slate-900/60 border-slate-800/80 text-slate-300 hover:bg-slate-900'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-100 flex items-center gap-2 truncate">
                    <FileText className="w-4 h-4 text-brand-400 shrink-0" />
                    {doc.original_filename}
                  </span>
                  <StatusBadge status={doc.processing_status} size="sm" />
                </div>

                <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-slate-800/60 text-[10px] text-slate-400">
                  <div>Type: <span className="text-slate-200">{doc.document_type || 'PDF'}</span></div>
                  <div>MIME: <span className="text-slate-200">{doc.mime_type}</span></div>
                  <div>Size: <span className="text-slate-200">{(doc.file_size_bytes / 1024).toFixed(1)} KB</span></div>
                  <div>Hash: <span className="text-slate-200 text-[9px]">{doc.file_hash?.substring(0, 12)}...</span></div>
                </div>

                <div className="mt-2 text-right">
                  <button className="inline-flex items-center gap-1 text-[10px] text-brand-400 hover:text-brand-300 font-sans font-semibold">
                    <Eye className="w-3 h-3" />
                    <span>Preview & Extract</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
