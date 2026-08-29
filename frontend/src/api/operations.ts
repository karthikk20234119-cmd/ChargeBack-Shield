import {
  AlertSummaryResponse,
  OperationalAlert,
  OperationalHealthResponse,
} from './types';

const API_BASE = '/api/operations';

export interface SLAItem {
  id: string;
  dispute_id: string;
  category: string;
  status: 'ON_TRACK' | 'DUE_SOON' | 'OVERDUE' | 'UNKNOWN';
  severity: string;
  due_time: string;
  elapsed_hours: number;
  remaining_hours: number;
}

export interface SLAReport {
  total_tracked: number;
  on_track_count: number;
  due_soon_count: number;
  overdue_count: number;
  unknown_count: number;
  items: SLAItem[];
}

export interface ExceptionItem {
  id: string;
  category: string;
  severity: string;
  dispute_id: string;
  reason: string;
  current_state: string;
  required_action: string;
  created_at: string;
}

export interface ExceptionsReport {
  total_exceptions: number;
  critical_exceptions: number;
  high_exceptions: number;
  exceptions: ExceptionItem[];
}

export interface ActionRequiredDispute {
  dispute_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  reason_code: string;
  action_type: string;
  description: string;
  severity: string;
  created_at: string;
}

export interface ReconciliationRequiredDispute {
  dispute_id: string;
  submission_id?: string;
  submission_status: string;
  last_razorpay_status?: string;
  reconciliation_state: string;
  age_hours: number;
  required_action: string;
}

export interface AlertDetectionResponse {
  detected_count: number;
  new_alerts: OperationalAlert[];
  timestamp: string;
}

async function opRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options?.headers || {}),
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let errBody;
    try {
      errBody = await res.json();
    } catch {
      errBody = await res.text();
    }
    const msg = typeof errBody === 'object' && errBody?.detail
      ? errBody.detail
      : `Operational request failed with status ${res.status}`;
    throw new Error(msg);
  }
  return await res.json();
}

export const operationsApi = {
  getAlertsSummary: () => opRequest<AlertSummaryResponse>('/alerts/summary'),
  getAlerts: (params?: { status?: string; severity?: string; category?: string; dispute_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append('status', params.status);
    if (params?.severity) q.append('severity', params.severity);
    if (params?.category) q.append('category', params.category);
    if (params?.dispute_id) q.append('dispute_id', params.dispute_id);
    return opRequest<OperationalAlert[]>(`/alerts?${q.toString()}`);
  },
  getDisputeAlerts: (disputeId: string) => opRequest<any>(`/disputes/${disputeId}/alerts`),
  getSLA: () => opRequest<SLAReport>('/sla'),
  getExceptions: () => opRequest<ExceptionsReport>('/exceptions'),
  getHealth: () => opRequest<OperationalHealthResponse>('/health'),
  getActionRequired: () => opRequest<ActionRequiredDispute[]>('/action-required'),
  getReconciliationRequired: () => opRequest<ReconciliationRequiredDispute[]>('/reconciliation-required'),
  detectAlerts: () => opRequest<AlertDetectionResponse>('/alerts/detect', {
    method: 'POST',
    body: JSON.stringify({}),
  }),
  acknowledgeAlert: (alertId: string) => opRequest<OperationalAlert>(`/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    body: JSON.stringify({}),
  }),
};
