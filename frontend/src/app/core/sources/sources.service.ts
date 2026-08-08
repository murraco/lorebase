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

  async sync(id: string): Promise<void> {
    const { error } = await apiClient.POST('/api/sources/{id}/sync/', {
      params: { path: { id } },
    });
    if (error) throw new Error('Failed to queue sync.');
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
}
