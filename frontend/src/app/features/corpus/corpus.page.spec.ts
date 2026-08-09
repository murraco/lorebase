import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { SourcesService } from '../../core/sources/sources.service';
import type { Source, SourceDocument } from '../../core/models';
import { CorpusPage } from './corpus.page';

function makeSource(overrides: Partial<Source> = {}): Source {
  return {
    id: 'source-1',
    workspace: 'ws-1',
    name: 'Notes',
    type: 'local_folder',
    status: 'ready',
    enabled: true,
    chunk_count: 1,
    embedded_chunk_count: 1,
    last_synced_at: null,
    last_error: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeDocument(overrides: Partial<SourceDocument> = {}): SourceDocument {
  return {
    id: 'doc-1',
    source: 'source-1',
    external_id: 'a.md',
    path: 'a.md',
    title: 'a',
    chunk_count: 0,
    embedded_chunk_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

async function setup(sourcesServiceStub: Partial<SourcesService>) {
  await TestBed.configureTestingModule({
    imports: [CorpusPage],
    providers: [
      { provide: SourcesService, useValue: sourcesServiceStub },
      {
        provide: ActivatedRoute,
        useValue: { queryParamMap: of(convertToParamMap({ source: 'source-1' })) },
      },
      { provide: Router, useValue: { navigate: vi.fn().mockResolvedValue(true) } },
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(CorpusPage);
  fixture.detectChanges();
  await fixture.whenStable();
  return { fixture, page: fixture.componentInstance };
}

describe('CorpusPage', () => {
  it('re-fetches the document list once a sync finishes', async () => {
    const documentsBeforeSync = [makeDocument({ id: 'doc-1', external_id: 'a.md' })];
    const documentsAfterSync = [
      makeDocument({ id: 'doc-1', external_id: 'a.md' }),
      makeDocument({ id: 'doc-2', external_id: 'b.md' }),
    ];
    const documents = vi
      .fn()
      .mockResolvedValueOnce(documentsBeforeSync)
      .mockResolvedValueOnce(documentsAfterSync);

    const { fixture, page } = await setup({
      sources: signal([makeSource()]),
      documents,
      chunks: vi.fn().mockResolvedValue({ chunks: [], total: 0 }),
      sync: vi.fn().mockResolvedValue(undefined),
      pollUntilDone: vi.fn().mockResolvedValue(undefined),
    });

    expect(documents).toHaveBeenCalledTimes(1);
    expect(page['documents']()).toEqual(documentsBeforeSync);

    await page['syncSelected']();
    fixture.detectChanges();

    expect(documents).toHaveBeenCalledTimes(2);
    expect(page['documents']()).toEqual(documentsAfterSync);
  });

  it('keeps the currently open document selected across a sync, if it still exists', async () => {
    const original = [
      makeDocument({ id: 'doc-1', external_id: 'a.md' }),
      makeDocument({ id: 'doc-2', external_id: 'b.md' }),
    ];
    // Same two documents, "b.md" reordered first — the point is that
    // re-syncing must not silently jump back to whichever is now first.
    const afterSync = [
      makeDocument({ id: 'doc-2', external_id: 'b.md' }),
      makeDocument({ id: 'doc-1', external_id: 'a.md' }),
    ];
    const documents = vi.fn().mockResolvedValueOnce(original).mockResolvedValueOnce(afterSync);

    const { page } = await setup({
      sources: signal([makeSource()]),
      documents,
      chunks: vi.fn().mockResolvedValue({ chunks: [], total: 0 }),
      sync: vi.fn().mockResolvedValue(undefined),
      pollUntilDone: vi.fn().mockResolvedValue(undefined),
    });

    // The initial load selects the first document, "a.md".
    expect(page['selectedDocumentId']()).toBe('doc-1');

    await page['syncSelected']();

    expect(page['selectedDocumentId']()).toBe('doc-1');
  });

  it('falls back to the first document when the one open was removed by the sync', async () => {
    const original = [
      makeDocument({ id: 'doc-1', external_id: 'a.md' }),
      makeDocument({ id: 'doc-2', external_id: 'b.md' }),
    ];
    // "a.md" — the one selected — is gone after this sync.
    const afterSync = [makeDocument({ id: 'doc-2', external_id: 'b.md' })];
    const documents = vi.fn().mockResolvedValueOnce(original).mockResolvedValueOnce(afterSync);

    const { page } = await setup({
      sources: signal([makeSource()]),
      documents,
      chunks: vi.fn().mockResolvedValue({ chunks: [], total: 0 }),
      sync: vi.fn().mockResolvedValue(undefined),
      pollUntilDone: vi.fn().mockResolvedValue(undefined),
    });

    expect(page['selectedDocumentId']()).toBe('doc-1');

    await page['syncSelected']();

    expect(page['selectedDocumentId']()).toBe('doc-2');
  });
});
