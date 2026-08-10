import { Component, computed, inject, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AuthService } from '../../core/auth/auth.service';
import type { DirectoryListing, Source, SourceType } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';

type Step = 'type' | 'browse' | 'github' | 'progress';

@Component({
  selector: 'lorebase-add-source-modal',
  imports: [FormsModule],
  templateUrl: './add-source-modal.component.html',
  styleUrl: './add-source-modal.component.css',
})
export class AddSourceModalComponent {
  private readonly sourcesService = inject(SourcesService);
  private readonly auth = inject(AuthService);

  readonly closed = output<void>();

  protected readonly step = signal<Step>('type');
  protected readonly listing = signal<DirectoryListing | null>(null);
  protected readonly browsing = signal(false);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected sectionBoundaryPattern = '';
  protected githubRepos = '';
  protected githubBranch = '';
  protected githubPathPrefixes = '';

  private readonly createdSourceId = signal<string | null>(null);
  /** Reads live off the shared sources list rather than polling on its
   * own — the shell's ambient poller and the pollUntilDone() call below
   * already keep that list current while a sync is in flight, so a
   * second polling loop here would just be a duplicate of one that
   * already exists. */
  protected readonly source = computed(() => {
    const id = this.createdSourceId();
    return id ? (this.sourcesService.sources().find((s) => s.id === id) ?? null) : null;
  });

  protected selectType(type: SourceType): void {
    this.error.set(null);
    if (type === 'local_folder') {
      this.step.set('browse');
      void this.browseTo('');
    } else {
      this.step.set('github');
    }
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
    const listing = this.listing();
    if (!listing) return;

    const name = listing.path === '' ? 'root' : (listing.path.split('/').pop() ?? listing.path);
    const config: Record<string, string> = { path: listing.absolute_path };
    const pattern = this.sectionBoundaryPattern.trim();
    if (pattern) {
      config['section_boundary_pattern'] = pattern;
    }
    await this.submitNewSource(name, 'local_folder', config);
  }

  protected async useGithubConfig(): Promise<void> {
    const repos = this.githubRepos
      .split(/[\n,]/)
      .map((repo) => repo.trim())
      .filter((repo) => repo.length > 0);
    if (repos.length === 0) return;

    const config: Record<string, unknown> = { repos };
    const branch = this.githubBranch.trim();
    if (branch) config['branch'] = branch;
    const pathPrefixes = this.githubPathPrefixes
      .split(',')
      .map((prefix) => prefix.trim())
      .filter((prefix) => prefix.length > 0);
    if (pathPrefixes.length > 0) config['path_prefixes'] = pathPrefixes;

    const name = repos.length === 1 ? repos[0] : `${repos[0]} +${repos.length - 1} more`;
    await this.submitNewSource(name, 'github', config);
  }

  private async submitNewSource(
    name: string,
    type: SourceType,
    config: Record<string, unknown>,
  ): Promise<void> {
    const workspace = this.auth.primaryWorkspace();
    if (!workspace) return;

    this.submitting.set(true);
    this.error.set(null);
    try {
      const created = await this.sourcesService.create({ workspace: workspace.id, name, type, config });
      this.createdSourceId.set(created.id);
      this.step.set('progress');
      await this.sourcesService.sync(created.id);
      await this.sourcesService.pollUntilDone(created.id);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to add source.');
    } finally {
      this.submitting.set(false);
    }
  }

  protected close(): void {
    this.closed.emit();
  }
}
