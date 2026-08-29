import React from 'react';
import { AlertCircle, CheckCircle, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 space-y-3 max-w-md w-full">
      {toasts.map((t) => {
        let style = 'bg-slate-900 border-slate-700 text-slate-100';
        let Icon = Info;

        if (t.type === 'success') {
          style = 'bg-emerald-950/90 border-emerald-700 text-emerald-100 glow-emerald';
          Icon = CheckCircle;
        } else if (t.type === 'error') {
          style = 'bg-rose-950/90 border-rose-700 text-rose-100 glow-rose';
          Icon = AlertCircle;
        } else if (t.type === 'warning') {
          style = 'bg-amber-950/90 border-amber-700 text-amber-100';
          Icon = AlertCircle;
        }

        return (
          <div
            key={t.id}
            className={`p-4 rounded-xl border backdrop-blur-md shadow-2xl flex items-start gap-3 transition-all transform translate-y-0 ${style}`}
          >
            <Icon className="w-5 h-5 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-semibold">{t.title}</h4>
              {t.message && <p className="text-xs opacity-90 mt-0.5">{t.message}</p>}
            </div>
            <button
              onClick={() => onDismiss(t.id)}
              className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
