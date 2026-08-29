import React, { useState } from 'react';
import { ExtractedEvidence } from '../../api/types';
import { FileCode, Tag } from 'lucide-react';

interface FactViewerProps {
  evidenceList: ExtractedEvidence[];
}

const CATEGORIES = [
  'ALL',
  'TRANSACTION',
  'CUSTOMER',
  'SHIPPING',
  'INVOICE',
  'REFUND',
  'COMMUNICATION',
  'SERVICE',
  'POLICY',
];

export const FactViewer: React.FC<FactViewerProps> = ({ evidenceList }) => {
  const [selectedCategory, setSelectedCategory] = useState('ALL');

  if (evidenceList.length === 0) {
    return (
      <div className="glass-panel p-6 text-center text-xs text-slate-400 font-mono">
        No extracted fact records found for this dispute.
      </div>
    );
  }

  // Combine all extracted facts from evidence records
  const allFacts: { name: string; val: any; confidence: number; category: string; source: string }[] = [];
  evidenceList.forEach((e) => {
    const data = e.extracted_data || {};
    Object.entries(data).forEach(([key, val]) => {
      let cat = 'TRANSACTION';
      if (key.includes('customer') || key.includes('email') || key.includes('phone') || key.includes('name')) cat = 'CUSTOMER';
      if (key.includes('shipping') || key.includes('awb') || key.includes('delivery') || key.includes('courier')) cat = 'SHIPPING';
      if (key.includes('invoice') || key.includes('price') || key.includes('tax')) cat = 'INVOICE';
      if (key.includes('refund') || key.includes('credit')) cat = 'REFUND';

      allFacts.push({
        name: key,
        val,
        confidence: e.confidence_score || 0.95,
        category: cat,
        source: e.schema_version || 'v1.0',
      });
    });
  });

  const filteredFacts = allFacts.filter(
    (f) => selectedCategory === 'ALL' || f.category === selectedCategory
  );

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
          <FileCode className="w-4 h-4 text-emerald-400" />
          <span>Extracted Structured Facts ({filteredFacts.length})</span>
        </h3>

        {/* Category Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 font-mono text-[11px]">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-2 py-0.5 rounded font-semibold transition-all ${
                selectedCategory === cat
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 text-[11px]">
            <tr>
              <th className="py-2.5 px-3">Fact Name</th>
              <th className="py-2.5 px-3">Category</th>
              <th className="py-2.5 px-3">Observed Value</th>
              <th className="py-2.5 px-3">Confidence</th>
              <th className="py-2.5 px-3">Extraction Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredFacts.map((f, i) => (
              <tr key={i} className="hover:bg-slate-900/50">
                <td className="py-2.5 px-3 font-bold text-slate-200">{f.name}</td>
                <td className="py-2.5 px-3">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px]">
                    {f.category}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-emerald-400">{String(f.val)}</td>
                <td className="py-2.5 px-3 font-bold text-brand-400">{(f.confidence * 100).toFixed(0)}%</td>
                <td className="py-2.5 px-3 text-slate-400 text-[11px]">{f.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
