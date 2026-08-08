import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import type { Conversation, Source } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';
import { AddSourceModalComponent } from './add-source-modal.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { ThemeService } from '../../core/theme/theme.service';
import { SystemStatusModalComponent } from './system-status-modal.component';

const POLL_INTERVAL_MS = 4000;
const SIDEBAR_COLLAPSED_KEY = 'lorebase.sidebarCollapsed';
// Matches the breakpoint in shell.component.css. Below it the rail stops
// being a column of the layout and becomes an overlay drawer, because a
// 250px sidebar on a narrow screen leaves nothing for the conversation.
const NARROW_QUERY = '(max-width: 900px)';

@Component({
  selector: 'lorebase-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    AddSourceModalComponent,
    ConfirmDialogComponent,
    SystemStatusModalComponent,
  ],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.css',
})
export class ShellComponent implements OnInit, OnDestroy {
  protected readonly auth = inject(AuthService);
  protected readonly sourcesService = inject(SourcesService);
  protected readonly conversationsService = inject(ConversationsService);
  protected readonly theme = inject(ThemeService);
  private readonly router = inject(Router);
  private pollHandle?: ReturnType<typeof setInterval>;

  // Collapses to a narrow icon rail rather than hiding outright, so the
  // primary actions (new chat, add source) stay one click away. Persisted
  // because a layout preference that resets on every reload is worse than
  // not having the toggle at all.
  protected readonly collapsed = signal(this.readCollapsedPreference());

  /** Narrow viewports get a drawer instead of a column. Tracked as a
   * signal rather than read from CSS so the template can close the drawer
   * on navigation, which only matters in that mode. */
  protected readonly narrow = signal(false);
  protected readonly drawerOpen = signal(false);
  private mediaQuery?: MediaQueryList;
  private readonly onMediaChange = (event: MediaQueryListEvent | MediaQueryList) => {
    this.narrow.set(event.matches);
    if (!event.matches) this.drawerOpen.set(false);
  };

  protected readonly showAddSourceModal = signal(false);
  protected readonly showSystemStatus = signal(false);
  protected readonly syncingSourceId = signal<string | null>(null);
  protected readonly sourcePendingDeletion = signal<Source | null>(null);
  protected readonly conversationPendingDeletion = signal<Conversation | null>(null);
  protected readonly deleting = signal(false);
  protected readonly deleteError = signal<string | null>(null);
  protected readonly loadingLists = signal(true);
  protected readonly listError = signal<string | null>(null);

  /** A source is only genuinely done when its sync finished AND every one
   * of its chunks has an embedding. Those are two separate phases —
   * sync_source_task flips status to "ready" and only then queues
   * backfill_embeddings_task — so "ready" alone would show a green dot
   * while dense retrieval still can't find anything in it. */
  protected readonly anyInFlight = computed(() =>
    this.sourcesService.sources().some((source) => this.isInFlight(source)),
  );

  async ngOnInit(): Promise<void> {
    // Previously unguarded: if either request failed the rejection went
    // unhandled and the sidebar simply stayed empty, which is
    // indistinguishable from "you have nothing yet".
    try {
      await Promise.all([this.sourcesService.refresh(), this.conversationsService.refresh()]);
    } catch {
      this.listError.set("Couldn't load your sources and conversations.");
    } finally {
      this.loadingLists.set(false);
    }
    // The interval runs for the component's lifetime but only issues a
    // request while something is actually in flight, so it costs nothing
    // when idle and restarts on its own once a new source is added.
    this.pollHandle = setInterval(() => {
      if (this.anyInFlight()) void this.sourcesService.refresh();
    }, POLL_INTERVAL_MS);

    this.mediaQuery = window.matchMedia(NARROW_QUERY);
    this.onMediaChange(this.mediaQuery);
    this.mediaQuery.addEventListener('change', this.onMediaChange);
  }

  ngOnDestroy(): void {
    if (this.pollHandle) clearInterval(this.pollHandle);
    this.mediaQuery?.removeEventListener('change', this.onMediaChange);
  }

  /** In drawer mode the rail covers the conversation, so following a link
   * has to dismiss it — otherwise you navigate to something you can't
   * see. On wide screens the rail is always visible and this is a no-op. */
  protected closeDrawerIfNarrow(): void {
    if (this.narrow()) this.drawerOpen.set(false);
  }

  /** "pending" is deliberately NOT in flight: it means the source was
   * created and never synced, so nothing is happening and nothing will
   * unless someone starts it. Treating it as in-flight showed a permanent
   * "Syncing…" on a source that had never run, and kept the poll below
   * firing every few seconds forever. */
  protected isInFlight(source: Source): boolean {
    if (source.status === 'syncing') return true;
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
    if (source.status === 'pending') return 'Not synced yet';
    if (source.status === 'syncing') return 'Syncing…';
    const progress = this.embeddingProgress(source);
    return progress === null ? null : `Indexing ${progress}%`;
  }

  /** A "pending" source has no way forward from the UI otherwise — the
   * sync endpoint existed from the start but nothing ever called it
   * outside the add-source flow. */
  protected async syncSource(source: Source): Promise<void> {
    this.syncingSourceId.set(source.id);
    try {
      await this.sourcesService.sync(source.id);
      await this.sourcesService.refreshOne(source.id);
    } catch {
      // The next poll reflects whatever actually happened; a failed
      // enqueue surfaces as the source's own error status.
    } finally {
      this.syncingSourceId.set(null);
    }
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

  protected async confirmDeleteConversation(): Promise<void> {
    const conversation = this.conversationPendingDeletion();
    if (!conversation) return;
    this.deleteError.set(null);
    this.deleting.set(true);
    try {
      await this.conversationsService.delete(conversation.id);
      this.conversationPendingDeletion.set(null);
      // Deleting the conversation currently open would otherwise leave the
      // chat pointing at an id the API no longer serves.
      if (this.router.url === `/chat/${conversation.id}`) {
        await this.router.navigateByUrl('/chat');
      }
    } catch (err) {
      this.deleteError.set(err instanceof Error ? err.message : 'Failed to delete conversation.');
    } finally {
      this.deleting.set(false);
    }
  }

  protected cancelDelete(): void {
    this.sourcePendingDeletion.set(null);
    this.conversationPendingDeletion.set(null);
    this.deleteError.set(null);
  }

  protected toggleCollapsed(): void {
    this.collapsed.update((value) => !value);
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(this.collapsed()));
    } catch {
      // Private browsing or a storage quota error — the toggle still
      // works for this session, it just won't be remembered.
    }
  }

  private readCollapsedPreference(): boolean {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
    } catch {
      return false;
    }
  }

  /** First letter of the username, for the collapsed rail's avatar. */
  protected userInitial(): string {
    return (this.auth.currentUser()?.username ?? '?').charAt(0).toUpperCase();
  }

  protected themeLabel(): string {
    const value = this.theme.preference();
    if (value === 'light') return 'Light';
    if (value === 'dark') return 'Dark';
    return 'System';
  }

  protected async retryLoad(): Promise<void> {
    this.listError.set(null);
    this.loadingLists.set(true);
    try {
      await Promise.all([this.sourcesService.refresh(), this.conversationsService.refresh()]);
    } catch {
      this.listError.set("Couldn't load your sources and conversations.");
    } finally {
      this.loadingLists.set(false);
    }
  }

  protected async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/login');
  }
}
