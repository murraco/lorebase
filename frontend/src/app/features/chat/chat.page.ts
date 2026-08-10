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
import type { Citation, FeedbackRating } from '../../core/models';
import { AnswerActionsComponent } from './answer-actions.component';

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
  // undefined while a freshly-streamed answer hasn't been rated yet in
  // this session; null/'up'/'down' once loaded from a saved conversation,
  // where the server has an actual answer (including "never rated").
  feedbackRating?: FeedbackRating | null;
  feedbackComment?: string;
}

const SUGGESTIONS = [
  'What did I write about last week?',
  'Summarize my notes on a topic',
  'What decisions did I record in July?',
];

@Component({
  selector: 'lorebase-chat-page',
  imports: [FormsModule, MarkdownPipe, AnswerActionsComponent],
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

  // A send() keeps streaming in the background regardless of navigation
  // (chatService.ask() isn't tied to an AbortSignal), but `messages` gets
  // replaced wholesale by loadConversation()/resetToNewConversation() the
  // moment the user looks elsewhere. Without this, appendDelta/
  // finalizeAnswer keep updating a turn that no longer exists in the
  // visible array -- the answer is computed and persisted, but silently
  // never rendered, even on navigating back before the stream finished.
  // loadConversation() re-attaches to this if its conversationId matches.
  private inFlight: {
    conversationId: string;
    userMessage: ThreadMessage;
    assistantMessage: ThreadMessage;
  } | null = null;

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
      const loaded: ThreadMessage[] = messages.map((message) => ({
        id: message.id,
        role: message.role as 'user' | 'assistant',
        content: message.content,
        citations: message.citations,
        latencyMs: message.latency_ms,
        cost: message.cost === null ? null : Number(message.cost),
        retrievedCount: message.retrieved_count,
        pending: false,
        feedbackRating: message.feedback?.rating ?? null,
        feedbackComment: message.feedback?.comment ?? '',
      }));
      // The stream that's still filling this in hasn't persisted anything
      // yet (see the `inFlight` field's comment) -- the fetch above can
      // only have found the turns that existed before it started.
      if (this.inFlight?.conversationId === conversationId) {
        loaded.push(this.inFlight.userMessage, this.inFlight.assistantMessage);
      }
      this.messages.set(loaded);
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

  /** Optimistic: the button reflects the click immediately rather than
   * waiting on the request, and reverts only if it actually failed —
   * rating an answer is low-stakes enough that a request in flight
   * shouldn't make a button feel unresponsive. */
  protected async rate(message: ThreadMessage, rating: FeedbackRating): Promise<void> {
    const previous = message.feedbackRating;
    this.setFeedback(message.id, rating, message.feedbackComment ?? '');
    try {
      await this.conversationsService.giveFeedback(message.id, rating, message.feedbackComment);
    } catch {
      this.setFeedback(message.id, previous ?? null, message.feedbackComment ?? '');
    }
  }

  protected async saveComment(message: ThreadMessage, comment: string): Promise<void> {
    const rating = message.feedbackRating;
    if (!rating) return; // the editor only ever shows for a rated message
    const previous = message.feedbackComment ?? '';
    this.setFeedback(message.id, rating, comment);
    try {
      await this.conversationsService.giveFeedback(message.id, rating, comment);
    } catch {
      this.setFeedback(message.id, rating, previous);
    }
  }

  private setFeedback(messageId: string, rating: FeedbackRating | null, comment: string): void {
    this.messages.update((current) =>
      current.map((m) =>
        m.id === messageId ? { ...m, feedbackRating: rating, feedbackComment: comment } : m,
      ),
    );
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
    const userMessage: ThreadMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      citations: [],
      pending: false,
    };
    this.messages.update((current) => [...current, userMessage]);

    const assistantId = crypto.randomUUID();
    const assistantMessage: ThreadMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      citations: [],
      pending: true,
    };
    this.messages.update((current) => [...current, assistantMessage]);
    this.inFlight = { conversationId, userMessage, assistantMessage };
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
      this.inFlight = null;
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
    if (this.inFlight?.assistantMessage.id === assistantId) {
      this.inFlight.assistantMessage.content += delta;
      this.inFlight.assistantMessage.pending = false;
    }
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
    // Cleared here rather than left to send()'s finally: the turn is
    // complete and persisted server-side from this point on, so a
    // loadConversation() racing right after this should trust its own
    // fetch instead of appending a now-redundant copy of this message.
    if (this.inFlight?.assistantMessage.id === assistantId) {
      this.inFlight = null;
    }
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
