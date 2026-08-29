import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileSpreadsheet,
  FileSearch,
  UserCheck,
  Activity,
  BarChart3,
  ShieldCheck,
  ShieldAlert,
  Play,
  Presentation,
  HeartPulse,
} from 'lucide-react';

const navigationItems = [
  { name: 'Overview', path: '/', icon: LayoutDashboard },
  { name: 'Disputes', path: '/disputes', icon: FileSpreadsheet },
  { name: 'Evidence', path: '/evidence', icon: FileSearch },
  { name: 'Human Review', path: '/review', icon: UserCheck },
  { name: 'Operations', path: '/operations', icon: Activity },
  { name: 'System Health', path: '/observability', icon: HeartPulse },
  { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  { name: 'Audit & Compliance', path: '/audit', icon: ShieldCheck },
  { name: 'Demo Mode', path: '/demo', icon: Play, tag: 'DEMO' },
  { name: 'Presentation', path: '/presentation', icon: Presentation, tag: 'DECK' },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-slate-900/90 border-r border-slate-800/80 flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none z-30">
      <div>
        {/* Brand Header */}
        <div className="h-16 px-6 flex items-center gap-3 border-b border-slate-800/80">
          <div className="p-2 bg-brand-600/20 border border-brand-500/30 rounded-lg text-brand-500 glow-blue">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
              CHARGEBACK <span className="text-brand-500 font-extrabold">SHIELD</span>
            </h1>
            <p className="text-[10px] text-slate-400 font-mono">v1.0.0 • PROD CONTROL CENTER</p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-4 space-y-1.5">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30 shadow-md glow-blue font-semibold'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="flex-1">{item.name}</span>
                {item.tag && (
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold ${
                    item.tag === 'DEMO' ? 'bg-amber-950 text-amber-300 border border-amber-800' : 'bg-purple-950 text-purple-300 border border-purple-800'
                  }`}>
                    {item.tag}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/40 text-xs text-slate-500 space-y-1">
        <div className="flex items-center justify-between font-mono">
          <span>BACKEND REST</span>
          <span className="text-emerald-400 font-bold">CONNECTED</span>
        </div>
        <p className="text-[10px] text-slate-500 truncate font-mono">http://localhost:8000/api</p>
      </div>
    </aside>
  );
};
