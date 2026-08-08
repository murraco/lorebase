import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import type { IndexedChunk, SourceDocument } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';

/** Browse what was actually indexed: source → document → chunks.
 *
 * This is the screen that makes Lorebase a knowledge base you can audit
 * rather than a chat with a hidden index. Retrieval only ever sees
 * chunks, so being able to read them — with their heading path, line
 * range, token count and embedding state — is the difference between
 * trusting the answers and hoping.
 */
@Component({
  selector: 'lorebase-corpus-page',
  templateUrl: './corpus.page.html',
  styleUrl: './corpus.page.css',
})
export class CorpusPage implements OnInit {
  protected readonly sourcesService = inject(SourcesService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly documents = signal<SourceDocument[]>([]);
  protected readonly chunks = signal<IndexedChunk[]>([]);
  protected readonly selectedSourceId = signal<string | null>(null);
  protected readonly selectedDocumentId = signal<string | null>(null);
  protected readonly loadingDocuments = signal(false);
  protected readonly loadingChunks = signal(false);
  protected readonly totalChunks = signal(0);
  private nextPage = 1;
  protected readonly error = signal<string | null>(null);
  /** Chunks whose raw text differs from what was embedded — the pieces
   * split off below a heading. Worth isolating: those are the ones that
   * carry no date or section of their own in `content`. */
  protected readonly onlyDerived = signal(false);

  protected readonly selectedDocument = computed(() =>
    this.documents().find((d) => d.id === this.selectedDocumentId()),
  );

  protected readonly visibleChunks = computed(() =>
    this.onlyDerived()
      ? this.chunks().filter((c) => c.content_with_heading !== c.content)
      : this.chunks(),
  );

  /** Of the chunks loaded so far, not of the document — labelled as
   * such in the template so a partial page never reads as a total. */
  protected readonly loadedTokens = computed(() =>
    this.chunks().reduce((sum, chunk) => sum + chunk.token_count, 0),
  );

  async ngOnInit(): Promise<void> {
    if (this.sourcesService.sources().length === 0) {
      await this.sourcesService.refresh().catch(() => undefined);
    }
    // Subscribed rather than read once from `snapshot`: clicking another
    // source in the sidebar only changes the query parameter, and Angular
    // reuses this component for that, so ngOnInit never runs again and a
    // snapshot read would leave the previous source selected forever.
    // Same failure the chat page had with its route parameter.
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const requested = params.get('source');
      const sources = this.sourcesService.sources();
      // Falls back to the first source so arriving without a parameter
      // never lands on an empty screen.
      const target = sources.find((s) => s.id === requested) ?? sources[0];
      if (target && target.id !== this.selectedSourceId()) void this.selectSource(target.id);
    });
  }

  protected async selectSource(sourceId: string): Promise<void> {
    this.selectedSourceId.set(sourceId);
    this.selectedDocumentId.set(null);
    this.chunks.set([]);
    this.loadingDocuments.set(true);
    this.error.set(null);
    try {
      const documents = await this.sourcesService.documents(sourceId);
      this.documents.set(documents);
      if (documents.length > 0) await this.selectDocument(documents[0].id);
    } catch {
      this.error.set("Couldn't load the documents for that source.");
    } finally {
      this.loadingDocuments.set(false);
    }
  }

  protected async selectDocument(documentId: string): Promise<void> {
    this.selectedDocumentId.set(documentId);
    this.chunks.set([]);
    this.nextPage = 1;
    await this.loadMore();
  }

  protected async loadMore(): Promise<void> {
    const documentId = this.selectedDocumentId();
    if (!documentId || this.loadingChunks()) return;
    this.loadingChunks.set(true);
    this.error.set(null);
    try {
      const { chunks, total } = await this.sourcesService.chunks(documentId, this.nextPage);
      this.totalChunks.set(total);
      this.chunks.update((current) => [...current, ...chunks]);
      this.nextPage += 1;
    } catch {
      this.error.set("Couldn't load the chunks for that document.");
    } finally {
      this.loadingChunks.set(false);
    }
  }

  protected readonly hasMore = computed(() => this.chunks().length < this.totalChunks());

  /** A document is only fully searchable once every chunk has a vector. */
  protected coverage(document: SourceDocument): number | null {
    if (!document.chunk_count) return null;
    return Math.floor((document.embedded_chunk_count / document.chunk_count) * 100);
  }
}
