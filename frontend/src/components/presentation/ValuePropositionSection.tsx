import React from 'react';
import { Award, ShieldCheck, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export const ValuePropositionSection: React.FC = () => {
  return (
    <div className="glass-panel p-8 space-y-6 border-l-4 border-l-purple-500 text-center font-mono">
      <div className="space-y-2">
        <Award className="w-10 h-10 text-purple-400 mx-auto glow-purple" />
        <h2 className="text-xl font-extrabold text-slate-100 uppercase tracking-wider">
          F. Final Value Proposition
        </h2>
        <p className="text-xs text-purple-300">
          PRODUCION-GRADE DISPUTE AUTOMATION FOR RAZORPAY MERCHANTS
        </p>
      </div>

      <div className="p-6 bg-purple-950/40 border border-purple-800/80 rounded-2xl max-w-3xl mx-auto shadow-2xl">
        <p className="text-base sm:text-lg font-bold text-slate-100 font-sans leading-relaxed">
          "Generate locally → Review locally → Authorize locally → Submit through one controlled boundary → Reconcile safely → Audit everything."
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-4 pt-2 font-sans">
        <Link
          to="/demo"
          className="px-6 py-3 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded-xl shadow-lg glow-amber transition-all flex items-center gap-2"
        >
          <span>Explore Guided Demo Mode</span>
          <ArrowRight className="w-4 h-4" />
        </Link>

        <Link
          to="/"
          className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-colors flex items-center gap-2"
        >
          <span>Open Live Control Center</span>
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
        </Link>
      </div>
    </div>
  );
};
