import { Component, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';

import type { Source } from '../../core/models';

/** The Sources group in the sidebar: rows, indexing state, and the two
 * actions a source affords. Split out of the shell, which had become a
 * layout container carrying the styling of everything inside it.
 */
@Component({
  selector: 'lorebase-source-list',
  imports: [RouterLink],
  templateUrl: './source-list.component.html',
  styleUrl: './source-list.component.css',
})
export class SourceListComponent {
  readonly sources = input.required<Source[]>();
  readonly collapsed = input(false);
  readonly loading = input(false);
  readonly hasError = input(false);
  readonly syncingId = input<string | null>(null);

  readonly toggled = output<void>();
  readonly add = output<void>();
  readonly sync = output<Source>();
  readonly remove = output<Source>();
  readonly navigated = output<void>();

  /** "pending" is deliberately not in flight: it means the source was
   * created and never synced, so nothing is happening and nothing will
   * unless someone starts it. */
  protected isInFlight(source: Source): boolean {
    if (source.status === 'syncing') return true;
    return source.chunk_count > 0 && source.embedded_chunk_count < source.chunk_count;
  }

  protected embeddingProgress(source: Source): number | null {
    if (source.chunk_count === 0) return null;
    if (source.embedded_chunk_count >= source.chunk_count) return null;
    return Math.floor((source.embedded_chunk_count / source.chunk_count) * 100);
  }

  protected statusLabel(source: Source): string | null {
    if (source.status === 'error') return 'Failed';
    if (source.status === 'pending') return 'Not synced yet';
    if (source.status === 'syncing') return 'Syncing…';
    const progress = this.embeddingProgress(source);
    return progress === null ? null : `Indexing ${progress}%`;
  }
}
