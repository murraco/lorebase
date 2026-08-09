import { Injectable } from '@angular/core';

import { apiClient } from '../api/client';
import type { DashboardMetrics } from '../models';

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  async dashboard(): Promise<DashboardMetrics> {
    const { data, error } = await apiClient.GET('/api/analytics/dashboard/');
    if (error) throw new Error('Failed to load dashboard metrics.');
    return data;
  }
}
