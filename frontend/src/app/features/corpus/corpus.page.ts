import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';

import type { IndexedChunk, Source, SourceDocument } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';
import { ConfirmDialogComponent } from '../shell/confirm-dialog.component';

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
  imports: [ConfirmDialogComponent],
  templateUrl: './corpus.page.html',
  styleUrl: './corpus.page.css',
})
export class CorpusPage implements OnInit {
  protected readonly sourcesService = inject(SourcesService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly router = inject(Router);

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
  /** Chunks are collapsed to a preview until opened. Expanding in place
   * instead of scrolling inside each card is what removes the nested
   * scroll: a card is either short, or tall and scrolled by the page. */
  protected readonly expandedChunkId = signal<string | null>(null);

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

  /** Called from the corpus's own source list. Goes through the router
   * so the URL carries the selection — otherwise reloading or sharing
   * the page silently lands on a different source than the one on
   * screen. The queryParamMap subscription above does the actual work. */
  protected async openSource(sourceId: string): Promise<void> {
    await this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { source: sourceId },
      replaceUrl: true,
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

  protected readonly syncing = signal(false);

  protected sourceStateLabel(source: { status: string }): string {
    if (source.status === 'error') return 'last sync failed';
    if (source.status === 'pending') return 'never synced';
    if (source.status === 'syncing') return 'syncing now';
    return 'ready';
  }

  protected readonly pendingDeletion = signal<Source | null>(null);
  protected readonly deleting = signal(false);
  protected readonly deleteError = signal<string | null>(null);

  /** Deletion lives here rather than in the sidebar because this is the
   * screen that shows what it would take with it — the documents, the
   * chunks, and the citations in past answers that point at them. */
  protected async confirmDelete(): Promise<void> {
    const source = this.pendingDeletion();
    if (!source) return;
    this.deleteError.set(null);
    this.deleting.set(true);
    try {
      await this.sourcesService.delete(source.id);
      this.pendingDeletion.set(null);
      this.documents.set([]);
      this.chunks.set([]);
      const next = this.sourcesService.sources()[0];
      if (next) {
        await this.openSource(next.id);
      } else {
        this.selectedSourceId.set(null);
      }
    } catch (err) {
      this.deleteError.set(err instanceof Error ? err.message : 'Failed to delete source.');
    } finally {
      this.deleting.set(false);
    }
  }

  /** Says what is actually lost. The generic "your files are not
   * touched" was true about the files and misleading about everything
   * else: citations point at chunks, and chunks go with the source. */
  protected deletionWarning(source: Source): string {
    const chunks = source.chunk_count;
    const scale = chunks > 0 ? `its ${chunks} indexed chunks` : 'anything indexed from it';
    return (
      `This removes the source and ${scale}. Answers that cited it keep their text ` +
      `but lose those citations. Your original files are not touched. ` +
      `To stop using it for answers without losing any of this, turn it off instead.`
    );
  }

  protected async toggleEnabled(): Promise<void> {
    const source = this.selectedSource();
    if (!source) return;
    try {
      await this.sourcesService.setEnabled(source.id, !source.enabled);
    } catch {
      this.error.set("Couldn't change whether that source is used.");
    }
  }

  protected async syncSelected(): Promise<void> {
    const sourceId = this.selectedSourceId();
    if (!sourceId || this.syncing()) return;
    this.syncing.set(true);
    try {
      await this.sourcesService.sync(sourceId);
      await this.sourcesService.pollUntilDone(sourceId);
    } catch {
      this.error.set("Couldn't queue a sync for that source.");
    } finally {
      this.syncing.set(false);
    }
  }

  protected toggleChunk(chunkId: string): void {
    this.expandedChunkId.update((current) => (current === chunkId ? null : chunkId));
  }

  protected async selectDocument(documentId: string): Promise<void> {
    this.selectedDocumentId.set(documentId);
    this.expandedChunkId.set(null);
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

  protected readonly selectedSource = computed(() =>
    this.sourcesService.sources().find((s) => s.id === this.selectedSourceId()),
  );

  /** A document is only fully searchable once every chunk has a vector. */
  protected coverage(document: SourceDocument): number | null {
    if (!document.chunk_count) return null;
    return Math.floor((document.embedded_chunk_count / document.chunk_count) * 100);
  }
}
