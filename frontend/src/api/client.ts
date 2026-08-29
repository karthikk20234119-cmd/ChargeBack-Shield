import {
  DashboardSummaryResponse,
  DisputeListResponse,
  OperationalHealthResponse,
  AlertSummaryResponse,
  ContestDraft,
  ContestDraftReviewRequest,
  ContestDraftReviewResponse,
  AnalyticsSummary,
  FunnelStageItem,
  BottleneckItem,
  DisputeAuditTimeline,
  OperationalAlert,
} from './types';

const API_BASE = '/api';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options?.headers || {}),
  };

  try {
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
        : `API request failed with status ${res.status}`;
      
      throw new ApiError(msg, res.status, errBody);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err.message || 'Network connection failed', 500);
  }
}

export const api = {
  // Dashboard & Disputes
  getDashboardSummary: () => request<DashboardSummaryResponse>('/dashboard/summary'),
  getDashboardOutcomes: () => request<Record<string, number>>('/dashboard/outcomes'),
  getDisputes: (params?: { page?: number; page_size?: number; search?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.page) q.append('page', params.page.toString());
    if (params?.page_size) q.append('page_size', params.page_size.toString());
    if (params?.search) q.append('search', params.search);
    if (params?.status) q.append('status', params.status);
    return request<DisputeListResponse>(`/dashboard/disputes?${q.toString()}`);
  },
  getDisputeDetail: (disputeId: string) => request<any>(`/dashboard/disputes/${disputeId}`),

  // Operations & Health
  getOperationalHealth: () => request<OperationalHealthResponse>('/operations/health'),
  getAlertsSummary: () => request<AlertSummaryResponse>('/operations/alerts/summary'),
  getAlerts: () => request<OperationalAlert[]>('/operations/alerts'),
  acknowledgeAlert: (alertId: string, acknowledgedBy: string = 'merchant_admin') =>
    request<OperationalAlert>(`/operations/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
    }),

  // Contest Draft & Human Review
  getContestDraft: (disputeId: string) => request<ContestDraft>(`/disputes/${disputeId}/contest-draft`),
  submitDraftReview: (disputeId: string, payload: ContestDraftReviewRequest) => {
    // SECURITY GUARANTEE: Payload contains ONLY decision, comment, and reviewer_reference.
    // Financial and policy fields are NEVER sent in request body.
    const cleanPayload: ContestDraftReviewRequest = {
      decision: payload.decision,
      comment: payload.comment,
      reviewer_reference: payload.reviewer_reference || 'merchant_admin',
    };
    return request<ContestDraftReviewResponse>(`/disputes/${disputeId}/contest-draft/review`, {
      method: 'POST',
      body: JSON.stringify(cleanPayload),
    });
  },

  // Analytics
  getAnalyticsSummary: () => request<AnalyticsSummary>('/analytics/summary'),
  getAnalyticsFunnel: () => request<{ funnel: FunnelStageItem[] }>('/analytics/funnel'),
  getAnalyticsBottlenecks: () => request<{ bottlenecks: BottleneckItem[] }>('/analytics/bottlenecks'),
  getAnalyticsExport: () => request<any>('/analytics/export'),

  // Audit
  getDisputeAuditTimeline: (disputeId: string) => request<DisputeAuditTimeline>(`/audit/disputes/${disputeId}/timeline`),
};
