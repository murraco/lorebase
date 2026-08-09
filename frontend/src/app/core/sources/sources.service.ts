import { Injectable, signal } from '@angular/core';

import { apiClient } from '../api/client';
import type { DirectoryListing, IndexedChunk, Source, SourceDocument, SourceType } from '../models';

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

  /** Turns a source on or off for retrieval. Nothing is re-indexed
   * either way — the chunks stay, so flipping it back is instant. */
  async setEnabled(id: string, enabled: boolean): Promise<void> {
    const { error } = await apiClient.PATCH('/api/sources/{id}/', {
      params: { path: { id } },
      body: { enabled },
    });
    if (error) throw new Error('Failed to update the source.');
    this.sources.update((current) =>
      current.map((source) => (source.id === id ? { ...source, enabled } : source)),
    );
  }

  async sync(id: string): Promise<void> {
    const { error } = await apiClient.POST('/api/sources/{id}/sync/', {
      params: { path: { id } },
    });
    if (error) throw new Error('Failed to queue sync.');
  }

  /** Cooperative: the worker stops between documents rather than being
   * killed outright, so this resolves once the request is accepted, not
   * once the sync has actually stopped — pollUntilDone() (already in
   * progress for any caller that started the sync) picks up the moment
   * it does. */
  async cancelSync(id: string): Promise<void> {
    const { error } = await apiClient.POST('/api/sources/{id}/cancel_sync/', {
      params: { path: { id } },
    });
    if (error) throw new Error('Failed to cancel sync.');
  }

  async delete(id: string): Promise<void> {
    const { error } = await apiClient.DELETE('/api/sources/{id}/', {
      params: { path: { id } },
    });
    if (error) throw new Error('Failed to delete source.');
    this.sources.update((current) => current.filter((source) => source.id !== id));
  }

  async documents(sourceId: string): Promise<SourceDocument[]> {
    const { data, error } = await apiClient.GET('/api/documents/', {
      params: { query: { source: sourceId } },
    });
    if (error) throw new Error('Failed to load documents.');
    return data.results;
  }

  /** The chunks a document was split into — what the retriever actually
   * searches, rather than the file on disk. Paginated because a single
   * document can split into hundreds, each carrying its full text. */
  async chunks(documentId: string, page = 1): Promise<{ chunks: IndexedChunk[]; total: number }> {
    const { data, error } = await apiClient.GET('/api/documents/{id}/chunks/', {
      params: { path: { id: documentId }, query: { page } },
    });
    if (error) throw new Error('Failed to load chunks.');
    return { chunks: data.results, total: data.count };
  }

  async browse(path: string): Promise<DirectoryListing> {
    const { data, error } = await apiClient.GET('/api/sources/browse/', {
      params: { query: { path } },
    });
    if (error) throw new Error('Failed to list that folder.');
    return data;
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

  /** Refreshes a source repeatedly until its sync has actually left the
   * queue — resolving right after `sync()` reads the pre-Celery state,
   * since the 202 response races the worker picking the job up. Callers
   * that need the row's own count to catch up further (embeddings finish
   * after status flips to "ready") don't have to wait on this: the shared
   * `sources` signal it updates is also what the sidebar's own background
   * poller reads, so that keeps going on its own. */
  async pollUntilDone(id: string, intervalMs = 1500): Promise<void> {
    for (;;) {
      await this.refreshOne(id);
      const source = this.sources().find((s) => s.id === id);
      if (!source || (source.status !== 'pending' && source.status !== 'syncing')) return;
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  }
}
