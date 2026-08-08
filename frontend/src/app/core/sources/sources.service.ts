import { Injectable, signal } from '@angular/core';

import { apiClient } from '../api/client';
import type { Source, SourceType } from '../models';

@Injectable({ providedIn: 'root' })
export class SourcesService {
  readonly sources = signal<Source[]>([]);

  async refresh(): Promise<void> {
    const { data, error } = await apiClient.GET('/api/sources/');
    if (error) throw new Error('Failed to load sources.');
    this.sources.set(data.results);
  }

  async create(input: {
    workspace: string;
    name: string;
    type: SourceType;
    config?: unknown;
  }): Promise<Source> {
    const { data, error } = await apiClient.POST('/api/sources/', { body: input });
    if (error) throw new Error('Failed to create source.');
    this.sources.update((current) => [...current, data]);
    return data;
  }

  async sync(id: string): Promise<void> {
    const { error } = await apiClient.POST('/api/sources/{id}/sync/', {
      params: { path: { id } },
    });
    if (error) throw new Error('Failed to queue sync.');
  }

  /** Replaces one source in the local list with a freshly fetched copy —
   * used while polling for sync status instead of a full refresh(), so an
   * in-flight edit to another source in the list isn't clobbered. */
  async refreshOne(id: string): Promise<void> {
    const { data, error } = await apiClient.GET('/api/sources/{id}/', {
      params: { path: { id } },
    });
    if (error) throw new Error('Failed to load source.');
    this.sources.update((current) => current.map((source) => (source.id === id ? data : source)));
  }
}
