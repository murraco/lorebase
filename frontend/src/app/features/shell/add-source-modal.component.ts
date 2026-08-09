import { Component, inject, OnDestroy, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AuthService } from '../../core/auth/auth.service';
import type { DirectoryListing, Source } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';

type Step = 'browse' | 'progress';

@Component({
  selector: 'lorebase-add-source-modal',
  imports: [FormsModule],
  templateUrl: './add-source-modal.component.html',
  styleUrl: './add-source-modal.component.css',
})
export class AddSourceModalComponent implements OnInit, OnDestroy {
  private readonly sourcesService = inject(SourcesService);
  private readonly auth = inject(AuthService);
  private pollHandle?: ReturnType<typeof setInterval>;

  readonly closed = output<void>();

  protected readonly step = signal<Step>('browse');
  protected readonly listing = signal<DirectoryListing | null>(null);
  protected readonly browsing = signal(false);
  protected readonly source = signal<Source | null>(null);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected sectionBoundaryPattern = '';

  async ngOnInit(): Promise<void> {
    await this.browseTo('');
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  protected async browseTo(path: string): Promise<void> {
    this.browsing.set(true);
    this.error.set(null);
    try {
      this.listing.set(await this.sourcesService.browse(path));
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to list that folder.');
    } finally {
      this.browsing.set(false);
    }
  }

  /** How much of the new source is searchable yet. Chunks exist before
   * their embeddings do, so this climbs after parsing finishes. */
  protected embeddedPercent(source: Source): number {
    if (!source.chunk_count) return 0;
    return Math.floor((source.embedded_chunk_count / source.chunk_count) * 100);
  }

  protected async useCurrentFolder(): Promise<void> {
    const workspace = this.auth.primaryWorkspace();
    const listing = this.listing();
    if (!workspace || !listing) return;

    const name = listing.path === '' ? 'root' : (listing.path.split('/').pop() ?? listing.path);
    const config: Record<string, string> = { path: listing.absolute_path };
    const pattern = this.sectionBoundaryPattern.trim();
    if (pattern) {
      config['section_boundary_pattern'] = pattern;
    }

    this.submitting.set(true);
    this.error.set(null);
    try {
      const created = await this.sourcesService.create({
        workspace: workspace.id,
        name,
        type: 'local_folder',
        config,
      });
      this.source.set(created);
      this.step.set('progress');
      await this.sourcesService.sync(created.id);
      this.pollUntilDone(created.id);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to add source.');
    } finally {
      this.submitting.set(false);
    }
  }

  protected close(): void {
    this.stopPolling();
    this.closed.emit();
  }

  private pollUntilDone(id: string): void {
    this.pollHandle = setInterval(async () => {
      await this.sourcesService.refreshOne(id);
      const updated = this.sourcesService.sources().find((s) => s.id === id) ?? null;
      this.source.set(updated);
      if (updated && updated.status !== 'pending' && updated.status !== 'syncing') {
        this.stopPolling();
      }
    }, 1500);
  }

  private stopPolling(): void {
    if (this.pollHandle !== undefined) {
      clearInterval(this.pollHandle);
      this.pollHandle = undefined;
    }
  }
}
