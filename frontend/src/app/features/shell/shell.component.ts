import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import type { Conversation, Source } from '../../core/models';
import { SourcesService } from '../../core/sources/sources.service';
import { AddSourceModalComponent } from './add-source-modal.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { MetricsBarComponent } from './metrics-bar.component';
import { SourceListComponent } from './source-list.component';
import { ThemeService } from '../../core/theme/theme.service';
import { SystemStatusModalComponent } from './system-status-modal.component';

const POLL_INTERVAL_MS = 4000;
const SIDEBAR_COLLAPSED_KEY = 'lorebase.sidebarCollapsed';
// Matches the breakpoint in shell.component.css. Below it the rail stops
// being a column of the layout and becomes an overlay drawer, because a
// 250px sidebar on a narrow screen leaves nothing for the conversation.
const NARROW_QUERY = '(max-width: 900px)';
const COLLAPSED_SECTIONS_KEY = 'lorebase.collapsedSections';

@Component({
  selector: 'lorebase-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    AddSourceModalComponent,
    ConfirmDialogComponent,
    MetricsBarComponent,
    SourceListComponent,
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

  /** Which sidebar sections are folded away. Persisted for the same
   * reason the rail's own collapsed state is: a layout preference that
   * resets on reload is worse than not offering it. */
  protected readonly collapsedSections = signal<Set<string>>(this.readCollapsedSections());

  protected readonly showAddSourceModal = signal(false);
  protected readonly showSystemStatus = signal(false);
  protected readonly syncingSourceId = signal<string | null>(null);
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
  private isInFlight(source: Source): boolean {
    if (source.status === 'syncing') return true;
    return source.chunk_count > 0 && source.embedded_chunk_count < source.chunk_count;
  }

  /** A "pending" source has no way forward from the UI otherwise — the
   * sync endpoint existed from the start but nothing ever called it
   * outside the add-source flow. */
  protected async syncSource(source: Source): Promise<void> {
    this.syncingSourceId.set(source.id);
    try {
      await this.sourcesService.sync(source.id);
      await this.sourcesService.pollUntilDone(source.id);
    } catch {
      // The next poll reflects whatever actually happened; a failed
      // enqueue surfaces as the source's own error status.
    } finally {
      this.syncingSourceId.set(null);
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
    this.conversationPendingDeletion.set(null);
    this.deleteError.set(null);
  }

  protected isSectionCollapsed(name: string): boolean {
    return this.collapsedSections().has(name);
  }

  protected toggleSection(name: string): void {
    this.collapsedSections.update((current) => {
      const next = new Set(current);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      try {
        localStorage.setItem(COLLAPSED_SECTIONS_KEY, JSON.stringify([...next]));
      } catch {
        // Private browsing: the fold still works for this session.
      }
      return next;
    });
  }

  private readCollapsedSections(): Set<string> {
    try {
      const stored = localStorage.getItem(COLLAPSED_SECTIONS_KEY);
      const parsed: unknown = stored ? JSON.parse(stored) : [];
      return new Set(Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'string') : []);
    } catch {
      return new Set();
    }
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

  /** Names the destination, not the current state: a control should say
   * what it will do. */
  protected themeLabel(): string {
    return this.theme.preference() === 'dark' ? 'Switch to light' : 'Switch to dark';
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
