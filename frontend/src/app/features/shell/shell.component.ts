import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import type { Source } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';
import { AddSourceModalComponent } from './add-source-modal.component';

const POLL_INTERVAL_MS = 4000;

@Component({
  selector: 'lorebase-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, AddSourceModalComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.css',
})
export class ShellComponent implements OnInit, OnDestroy {
  protected readonly auth = inject(AuthService);
  protected readonly sourcesService = inject(SourcesService);
  protected readonly conversationsService = inject(ConversationsService);
  private readonly router = inject(Router);
  private pollHandle?: ReturnType<typeof setInterval>;

  protected readonly showAddSourceModal = signal(false);
  protected readonly sourcePendingDeletion = signal<Source | null>(null);
  protected readonly deleting = signal(false);
  protected readonly deleteError = signal<string | null>(null);

  /** A source is only genuinely done when its sync finished AND every one
   * of its chunks has an embedding. Those are two separate phases —
   * sync_source_task flips status to "ready" and only then queues
   * backfill_embeddings_task — so "ready" alone would show a green dot
   * while dense retrieval still can't find anything in it. */
  protected readonly anyInFlight = computed(() =>
    this.sourcesService.sources().some((source) => this.isInFlight(source)),
  );

  async ngOnInit(): Promise<void> {
    await Promise.all([this.sourcesService.refresh(), this.conversationsService.refresh()]);
    // The interval runs for the component's lifetime but only issues a
    // request while something is actually in flight, so it costs nothing
    // when idle and restarts on its own once a new source is added.
    this.pollHandle = setInterval(() => {
      if (this.anyInFlight()) void this.sourcesService.refresh();
    }, POLL_INTERVAL_MS);
  }

  ngOnDestroy(): void {
    if (this.pollHandle) clearInterval(this.pollHandle);
  }

  protected isInFlight(source: Source): boolean {
    if (source.status === 'syncing' || source.status === 'pending') return true;
    return source.chunk_count > 0 && source.embedded_chunk_count < source.chunk_count;
  }

  /** Percentage of this source's chunks that are embedded, or null when
   * there's nothing meaningful to report (no chunks yet, or all done). */
  protected embeddingProgress(source: Source): number | null {
    if (source.chunk_count === 0) return null;
    if (source.embedded_chunk_count >= source.chunk_count) return null;
    return Math.floor((source.embedded_chunk_count / source.chunk_count) * 100);
  }

  protected statusLabel(source: Source): string | null {
    if (source.status === 'error') return 'Failed';
    if (source.status === 'syncing' || source.status === 'pending') return 'Syncing…';
    const progress = this.embeddingProgress(source);
    return progress === null ? null : `Indexing ${progress}%`;
  }

  protected async confirmDelete(): Promise<void> {
    const source = this.sourcePendingDeletion();
    if (!source) return;
    this.deleteError.set(null);
    this.deleting.set(true);
    try {
      await this.sourcesService.delete(source.id);
      this.sourcePendingDeletion.set(null);
    } catch (err) {
      this.deleteError.set(err instanceof Error ? err.message : 'Failed to delete source.');
    } finally {
      this.deleting.set(false);
    }
  }

  protected cancelDelete(): void {
    this.sourcePendingDeletion.set(null);
    this.deleteError.set(null);
  }

  protected async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/login');
  }
}
