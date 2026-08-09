import {
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { ChatService, type ChatDoneEvent } from '../../core/chat/chat.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import { MarkdownPipe } from '../../core/markdown/markdown.pipe';
import type { Citation } from '../../core/models';

interface ThreadMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  /** Retrieval provenance for the answer. Rendered as the memo's header,
   * which is what turns a reply into a document that shows its work. */
  latencyMs?: number | null;
  cost?: number | null;
  retrievedCount?: number | null;
  // True from the moment the assistant's turn starts until its first
  // delta arrives. The backend computes the whole answer (retrieval,
  // rerank, LLM call) before streaming anything, so there's a real gap —
  // often a second or more — with nothing to show yet.
  pending: boolean;
}

const SUGGESTIONS = [
  'What did I write about last week?',
  'Summarize my notes on a topic',
  'What decisions did I record in July?',
];

@Component({
  selector: 'lorebase-chat-page',
  imports: [FormsModule, MarkdownPipe],
  templateUrl: './chat.page.html',
  styleUrl: './chat.page.css',
})
export class ChatPage implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly conversationsService = inject(ConversationsService);
  private readonly chatService = inject(ChatService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly threadRef = viewChild<ElementRef<HTMLElement>>('thread');

  protected readonly messages = signal<ThreadMessage[]>([]);
  protected readonly sending = signal(false);
  protected readonly loading = signal(false);
  protected readonly loadError = signal<string | null>(null);
  protected readonly expandedCitationId = signal<string | null>(null);
  /** Which margin note is highlighted while hovered. */
  protected readonly focusedCitationId = signal<string | null>(null);
  protected readonly suggestions = SUGGESTIONS;
  protected question = '';

  /** Drives the hero-vs-docked composer layout. Also false while a
   * conversation is still loading, so the hero doesn't flash before the
   * existing messages arrive. */
  protected readonly isEmpty = computed(
    () => this.messages().length === 0 && !this.loading() && !this.loadError(),
  );

  // Null until this conversation actually has a question. Creating it
  // eagerly on page load (as this used to) left an empty, untitled
  // Conversation row behind every time the page was opened and abandoned
  // — invisible before there was a history list, obvious noise now.
  private conversationId: string | null = null;

  ngOnInit(): void {
    // Subscribed, not read once from `snapshot`. Angular reuses this
    // component when navigating between two /chat/:id routes, so
    // ngOnInit does not run again and a snapshot read leaves the
    // previous conversation on screen forever.
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const conversationId = params.get('conversationId');
      if (conversationId) {
        void this.loadConversation(conversationId);
      } else {
        this.resetToNewConversation();
      }
    });
  }

  /** Navigating to /chat with a thread already on screen has to clear it,
   * otherwise "New chat" shows the previous conversation and the next
   * question appends to it. */
  private resetToNewConversation(): void {
    this.conversationId = null;
    this.messages.set([]);
    this.loadError.set(null);
    this.expandedCitationId.set(null);
    this.focusedCitationId.set(null);
  }

  private async loadConversation(conversationId: string): Promise<void> {
    // Already on screen. This fires when we navigate to the id we just
    // created for an answer that is still streaming; refetching would
    // replace the in-flight message with the server's copy of a
    // conversation that doesn't have it yet.
    if (conversationId === this.conversationId) return;

    this.loading.set(true);
    this.loadError.set(null);
    try {
      const messages = await this.conversationsService.listMessages(conversationId);
      this.conversationId = conversationId;
      this.messages.set(
        messages.map((message) => ({
          id: message.id,
          role: message.role as 'user' | 'assistant',
          content: message.content,
          citations: message.citations,
          latencyMs: message.latency_ms,
          cost: message.cost === null ? null : Number(message.cost),
          retrievedCount: message.retrieved_count,
          pending: false,
        })),
      );
      // Jump, not smooth: this is the initial position of a conversation
      // being opened, not a movement the reader should watch.
      this.scrollToLatest('auto');
    } catch {
      // Deliberately leaves conversationId null: a conversation that
      // couldn't be loaded (deleted, or another user's, which the API
      // scopes away) must not become the target of the next question.
      this.loadError.set("That conversation couldn't be loaded.");
    } finally {
      this.loading.set(false);
    }
  }

  protected toggleCitation(citationId: string): void {
    const opening = this.expandedCitationId() !== citationId;
    this.expandedCitationId.set(opening ? citationId : null);
    // A passage opened at the foot of a long answer can still land below
    // the fold; nudge it into view rather than leaving the reader to
    // wonder whether the click did anything.
    if (opening) {
      requestAnimationFrame(() => {
        this.threadRef()
          ?.nativeElement.querySelector('.passage')
          ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    }
  }

  protected useSuggestion(suggestion: string): void {
    this.question = suggestion;
  }

  /** Clearing the model does not undo an inline height set by autoGrow,
   * so the box would stay tall after sending a long question. */
  private resetComposerHeight(): void {
    const textarea = document.querySelector<HTMLTextAreaElement>('.composer textarea');
    if (textarea) textarea.style.height = '';
  }

  protected onEnter(event: Event): void {
    // Angular types (keydown.enter)'s $event as the generic Event, even
    // though it's always a KeyboardEvent at runtime.
    if ((event as KeyboardEvent).shiftKey) return; // let the textarea insert the newline
    event.preventDefault();
    void this.send();
  }

  /** Pins the thread to the newest content. Called when a question is
   * sent and again when its answer lands, because the answer changes the
   * height after the fact — scrolling only on send would leave the reply
   * itself below the fold.
   *
   * requestAnimationFrame so the DOM has the new message in it: reading
   * scrollHeight in the same tick returns the old height. */
  private scrollToLatest(behavior: ScrollBehavior = 'smooth'): void {
    requestAnimationFrame(() => {
      const thread = this.threadRef()?.nativeElement;
      if (thread) thread.scrollTo({ top: thread.scrollHeight, behavior });
    });
  }

  protected async send(): Promise<void> {
    const question = this.question.trim();
    if (!question || this.sending()) return;

    const conversationId = await this.ensureConversation();
    if (!conversationId) return;

    this.question = '';
    this.resetComposerHeight();
    this.messages.update((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', content: question, citations: [], pending: false },
    ]);

    const assistantId = crypto.randomUUID();
    this.messages.update((current) => [
      ...current,
      { id: assistantId, role: 'assistant', content: '', citations: [], pending: true },
    ]);
    this.sending.set(true);
    this.scrollToLatest();

    try {
      for await (const event of this.chatService.ask(conversationId, question)) {
        if ('delta' in event) {
          this.appendDelta(assistantId, event.delta);
        } else {
          this.finalizeAnswer(assistantId, event);
        }
      }
      this.scrollToLatest();
      // The backend titles a conversation from its first question, so the
      // sidebar entry only becomes meaningful once that answer is done.
      await this.conversationsService.refresh();
    } catch {
      this.appendDelta(assistantId, 'Something went wrong answering that.');
    } finally {
      this.sending.set(false);
    }
  }

  private async ensureConversation(): Promise<string | null> {
    if (this.conversationId) return this.conversationId;

    const workspace = this.auth.primaryWorkspace();
    if (!workspace) return null;

    const conversation = await this.conversationsService.create(workspace.id);
    // Set before navigating so loadConversation's guard sees it and skips
    // the refetch. A real navigation (rather than Location.replaceState)
    // is what keeps the router's own URL in sync — otherwise it still
    // believes it is on /chat, and clicking "New chat" afterwards is a
    // no-op that leaves this conversation on screen.
    this.conversationId = conversation.id;
    await this.router.navigate(['/chat', conversation.id], { replaceUrl: true });
    return conversation.id;
  }

  private appendDelta(assistantId: string, delta: string): void {
    this.messages.update((current) =>
      current.map((message) =>
        message.id === assistantId
          ? { ...message, content: message.content + delta, pending: false }
          : message,
      ),
    );
  }

  private finalizeAnswer(assistantId: string, event: ChatDoneEvent): void {
    this.messages.update((current) =>
      current.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              id: event.message_id,
              citations: event.citations,
              latencyMs: event.latency_ms,
              cost: event.cost,
              retrievedCount: event.retrieved_count,
              pending: false,
            }
          : message,
      ),
    );
  }

  /** A citation's score drawn against the best score in the same answer.
   * Absolute scores mean nothing across strategies — a cross-encoder
   * logit and an RRF sum are different units — but within one answer the
   * ranking is real, so a relative bar is the honest way to show "how
   * strong a match this was" without implying a probability. */
  protected relativeMatch(
    message: ThreadMessage,
    citation: Citation,
  ): { percent: number; score: string } | null {
    if (citation.score === null || citation.score === undefined) return null;
    const scores = message.citations
      .map((c) => c.score)
      .filter((s): s is number => s !== null && s !== undefined);
    if (scores.length === 0) return null;
    const best = Math.max(...scores);
    const worst = Math.min(...scores, 0);
    const span = best - worst;
    return {
      percent: span === 0 ? 100 : Math.round(((citation.score - worst) / span) * 100),
      score: citation.score.toFixed(3),
    };
  }

  /** The citation currently open in the reader, looked up across every
   * message so the panel survives scrolling past its own answer. */
  protected readonly expandedCitation = computed<Citation | null>(() => {
    const id = this.expandedCitationId();
    if (!id) return null;
    for (const message of this.messages()) {
      const found = message.citations.find((c) => c.id === id);
      if (found) return found;
    }
    return null;
  });

  /** Its number within its own answer, matching the margin note. */
  protected readonly expandedIndex = computed(() => {
    const id = this.expandedCitationId();
    for (const message of this.messages()) {
      const index = message.citations.findIndex((c) => c.id === id);
      if (index >= 0) return index + 1;
    }
    return null;
  });

  /** Grows the composer with its content up to the CSS max-height, so a
   * long question stays readable while it is being written instead of
   * scrolling inside a one-line box. */
  protected autoGrow(event: Event): void {
    const textarea = event.target as HTMLTextAreaElement;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }

  protected latencySeconds(ms: number | null | undefined): string | null {
    return ms === null || ms === undefined ? null : (ms / 1000).toFixed(2);
  }

  /** Four decimals because a single answer costs fractions of a cent;
   * rounding to two would print $0.00 for every turn. */
  protected formatCost(cost: number | null | undefined): string | null {
    return cost === null || cost === undefined ? null : `$${cost.toFixed(4)}`;
  }
}
