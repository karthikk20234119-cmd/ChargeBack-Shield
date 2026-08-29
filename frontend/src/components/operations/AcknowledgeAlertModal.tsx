import React from 'react';
import { OperationalAlert } from '../../api/types';
import { Modal } from '../ui/Modal';
import { CheckCircle2, AlertTriangle } from 'lucide-react';

interface AcknowledgeAlertModalProps {
  alert: OperationalAlert | null;
  isOpen: boolean;
  submitting: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export const AcknowledgeAlertModal: React.FC<AcknowledgeAlertModalProps> = ({
  alert,
  isOpen,
  submitting,
  onConfirm,
  onClose,
}) => {
  if (!isOpen || !alert) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Acknowledge Operational Alert"
      maxWidth="md"
    >
      <div className="space-y-4 font-mono text-xs">
        <div className="p-4 bg-emerald-950/60 border border-emerald-800 rounded-xl text-emerald-200 flex items-start gap-3">
          <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-bold text-sm font-sans">Mark this alert as acknowledged?</h4>
            <p className="text-[11px] opacity-90 font-sans">
              This action modifies ONLY the operational alert status to ACKNOWLEDGED. Dispute state and financial identity remain untouched.
            </p>
          </div>
        </div>

        <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1 text-[11px]">
          <div>Alert Code: <span className="text-slate-200 font-bold">{alert.code}</span></div>
          <div>Dispute ID: <span className="text-brand-400 font-bold">{alert.dispute_id}</span></div>
          <div>Message: <span className="text-slate-300 font-sans">{alert.message}</span></div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2 font-sans">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={submitting}
            onClick={onConfirm}
            className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-lg glow-emerald transition-all"
          >
            {submitting ? 'Acknowledging...' : 'Confirm Acknowledgment'}
          </button>
        </div>
      </div>
    </Modal>
  );
};
