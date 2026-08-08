import { Injectable } from '@angular/core';

import { apiClient } from '../api/client';
import type { SystemStatus } from '../models';

@Injectable({ providedIn: 'root' })
export class SystemService {
  async status(): Promise<SystemStatus> {
    const { data, error } = await apiClient.GET('/api/system/status/');
    if (error) throw new Error('Failed to load system status.');
    return data;
  }
}
