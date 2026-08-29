import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center space-y-5 font-mono">
      <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-2xl text-rose-400 glow-rose">
        <ShieldAlert className="w-12 h-12" />
      </div>

      <div className="space-y-2">
        <span className="text-xs text-rose-400 font-bold uppercase tracking-widest">HTTP 404 • NOT FOUND</span>
        <h1 className="text-3xl font-extrabold text-slate-100">Requested Page Does Not Exist</h1>
        <p className="text-slate-400 text-xs font-sans max-w-md mx-auto">
          The requested route was not found in the Chargeback Shield platform registry.
        </p>
      </div>

      <Link
        to="/"
        className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-bold font-sans shadow glow-blue flex items-center gap-2 transition-all"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Return to Executive Control Center</span>
      </Link>
    </div>
  );
};
