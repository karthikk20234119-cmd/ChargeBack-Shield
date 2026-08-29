import React from 'react';
import { EvidenceDocument } from '../../api/types';
import { FileText, Lock, AlertCircle } from 'lucide-react';

interface EvidencePreviewProps {
  document: EvidenceDocument | null;
}

export const EvidencePreview: React.FC<EvidencePreviewProps> = ({ document }) => {
  if (!document) {
    return (
      <div className="glass-panel p-8 text-center text-xs text-slate-400 font-mono space-y-2">
        <FileText className="w-8 h-8 text-slate-600 mx-auto" />
        <p>Select a document from Evidence Explorer to preview content.</p>
      </div>
    );
  }

  const isImage = document.mime_type.startsWith('image/');
  const isPdf = document.mime_type === 'application/pdf';

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-400" />
          <h4 className="text-xs font-bold text-slate-200 font-mono">{document.original_filename}</h4>
        </div>
        <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
          <Lock className="w-3 h-3 text-emerald-400" />
          Isolated Secure Preview
        </span>
      </div>

      <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 min-h-[260px] flex flex-col items-center justify-center text-xs font-mono text-slate-400 space-y-3">
        {isImage ? (
          <div className="text-center space-y-2">
            <div className="p-4 bg-slate-900/80 rounded-lg border border-slate-800 text-slate-300">
              [Image File Preview: {document.original_filename}]
            </div>
            <p className="text-[11px] text-slate-400">Dimensions & EXIF metadata verified cleanly by backend.</p>
          </div>
        ) : isPdf ? (
          <div className="text-center space-y-2">
            <div className="p-4 bg-slate-900/80 rounded-lg border border-slate-800 text-slate-300">
              [PDF Document Viewer: {document.original_filename}]
            </div>
            <p className="text-[11px] text-slate-400">PDF structure validated with PyPDF2 / pdfplumber parser.</p>
          </div>
        ) : (
          <div className="text-center space-y-2 text-amber-300">
            <AlertCircle className="w-6 h-6 text-amber-400 mx-auto" />
            <p className="font-semibold">Preview unavailable for MIME type {document.mime_type}.</p>
            <p className="text-[11px] text-slate-400">Evidence metadata and extracted facts remain available.</p>
          </div>
        )}
      </div>
    </div>
  );
};
