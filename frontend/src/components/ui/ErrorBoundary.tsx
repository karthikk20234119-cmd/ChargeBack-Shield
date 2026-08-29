import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-8 space-y-4 font-mono">
          <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-2xl text-rose-400 glow-rose">
            <AlertTriangle className="w-12 h-12" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-extrabold text-slate-100 font-sans">
              Control Center Interface Exception
            </h2>
            <p className="text-xs text-rose-400 max-w-md mx-auto">
              {this.state.error?.message || 'An unexpected client-side error occurred.'}
            </p>
          </div>

          <button
            onClick={this.handleReset}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-lg shadow-md glow-blue transition-all flex items-center gap-2 font-sans"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Reload Interface</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
