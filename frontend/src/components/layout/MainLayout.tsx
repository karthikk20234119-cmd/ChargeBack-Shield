import React from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ToastContainer, ToastMessage } from '../ui/ToastContainer';

interface MainLayoutProps {
  children: React.ReactNode;
  toasts: ToastMessage[];
  onDismissToast: (id: string) => void;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children, toasts, onDismissToast }) => {
  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 p-6 md:p-8 space-y-6 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
      <ToastContainer toasts={toasts} onDismiss={onDismissToast} />
    </div>
  );
};
