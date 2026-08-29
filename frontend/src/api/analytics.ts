import { AnalyticsSummary, FunnelStageItem, BottleneckItem } from './types';

const API_BASE = '/api/analytics';

export type TimeRangeOption = 'TODAY' | 'LAST_7_DAYS' | 'LAST_30_DAYS' | 'LAST_90_DAYS' | 'THIS_YEAR' | 'CUSTOM';

export interface AnalyticsQuery {
  time_range?: TimeRangeOption;
  date_from?: string;
  date_to?: string;
  period?: 'daily' | 'weekly' | 'monthly';
}

function buildParams(query?: AnalyticsQuery): string {
  const q = new URLSearchParams();
  if (query?.time_range) q.append('time_range', query.time_range);
  if (query?.date_from) q.append('date_from', query.date_from);
  if (query?.date_to) q.append('date_to', query.date_to);
  if (query?.period) q.append('period', query.period);
  const str = q.toString();
  return str ? `?${str}` : '';
}

async function analyticsRequest<T>(endpoint: string, query?: AnalyticsQuery): Promise<T> {
  const url = `${API_BASE}${endpoint}${buildParams(query)}`;
  const headers = { 'Content-Type': 'application/json' };

  const res = await fetch(url, { method: 'GET', headers });
  if (!res.ok) {
    let errBody;
    try {
      errBody = await res.json();
    } catch {
      errBody = await res.text();
    }
    const msg = typeof errBody === 'object' && errBody?.detail
      ? errBody.detail
      : `Analytics request failed with status ${res.status}`;
    throw new Error(msg);
  }
  return await res.json();
}

export const analyticsApi = {
  getSummary: (query?: AnalyticsQuery) => analyticsRequest<AnalyticsSummary>('/summary', query),
  getOutcomes: (query?: AnalyticsQuery) => analyticsRequest<any>('/outcomes', query),
  getEvidence: (query?: AnalyticsQuery) => analyticsRequest<any>('/evidence', query),
  getMatching: (query?: AnalyticsQuery) => analyticsRequest<any>('/matching', query),
  getPolicy: (query?: AnalyticsQuery) => analyticsRequest<any>('/policy', query),
  getDrafts: (query?: AnalyticsQuery) => analyticsRequest<any>('/drafts', query),
  getSubmissions: (query?: AnalyticsQuery) => analyticsRequest<any>('/submissions', query),
  getOperations: (query?: AnalyticsQuery) => analyticsRequest<any>('/operations', query),
  getSLA: (query?: AnalyticsQuery) => analyticsRequest<any>('/sla', query),
  getFunnel: (query?: AnalyticsQuery) => analyticsRequest<{ funnel: FunnelStageItem[] }>('/funnel', query),
  getBottlenecks: (query?: AnalyticsQuery) => analyticsRequest<{ bottlenecks: BottleneckItem[] }>('/bottlenecks', query),
  getFailures: (query?: AnalyticsQuery) => analyticsRequest<any>('/failures', query),
  getSecurity: (query?: AnalyticsQuery) => analyticsRequest<any>('/security', query),
  getFinancialIntegrity: (query?: AnalyticsQuery) => analyticsRequest<any>('/financial-integrity', query),
  getExport: (query?: AnalyticsQuery) => analyticsRequest<any>('/export', query),
};
