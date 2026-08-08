import { Component, inject, OnDestroy, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AuthService } from '../../core/auth/auth.service';
import type { Source } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';

@Component({
  selector: 'lorebase-add-source-modal',
  imports: [FormsModule],
  templateUrl: './add-source-modal.component.html',
  styleUrl: './add-source-modal.component.css',
})
export class AddSourceModalComponent implements OnDestroy {
  private readonly sourcesService = inject(SourcesService);
  private readonly auth = inject(AuthService);
  private pollHandle?: ReturnType<typeof setInterval>;

  readonly closed = output<void>();

  protected path = '';
  protected readonly step = signal<'form' | 'progress'>('form');
  protected readonly source = signal<Source | null>(null);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async createAndSync(): Promise<void> {
    const workspace = this.auth.primaryWorkspace();
    const path = this.path.trim();
    if (!workspace || !path) return;

    this.submitting.set(true);
    this.error.set(null);
    try {
      const created = await this.sourcesService.create({
        workspace: workspace.id,
        name: path,
        type: 'local_folder',
        config: { path },
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

  ngOnDestroy(): void {
    this.stopPolling();
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
