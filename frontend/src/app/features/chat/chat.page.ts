import { Location } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { ChatService } from '../../core/chat/chat.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import { MarkdownPipe } from '../../core/markdown/markdown.pipe';
import type { Citation } from '../../core/models';

interface ThreadMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
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
  private readonly location = inject(Location);

  protected readonly messages = signal<ThreadMessage[]>([]);
  protected readonly sending = signal(false);
  protected readonly loading = signal(false);
  protected readonly loadError = signal<string | null>(null);
  protected readonly expandedCitationId = signal<string | null>(null);
  protected readonly suggestions = SUGGESTIONS;
  protected question = '';

  // Null until this conversation actually has a question. Creating it
  // eagerly on page load (as this used to) left an empty, untitled
  // Conversation row behind every time the page was opened and abandoned
  // — invisible before there was a history list, obvious noise now.
  private conversationId: string | null = null;

  async ngOnInit(): Promise<void> {
    const conversationId = this.route.snapshot.paramMap.get('conversationId');
    if (conversationId) {
      await this.loadConversation(conversationId);
    }
  }

  private async loadConversation(conversationId: string): Promise<void> {
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
          pending: false,
        })),
      );
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
    this.expandedCitationId.update((current) => (current === citationId ? null : citationId));
  }

  protected useSuggestion(suggestion: string): void {
    this.question = suggestion;
  }

  protected onEnter(event: Event): void {
    // Angular types (keydown.enter)'s $event as the generic Event, even
    // though it's always a KeyboardEvent at runtime.
    if ((event as KeyboardEvent).shiftKey) return; // let the textarea insert the newline
    event.preventDefault();
    void this.send();
  }

  protected async send(): Promise<void> {
    const question = this.question.trim();
    if (!question || this.sending()) return;

    const conversationId = await this.ensureConversation();
    if (!conversationId) return;

    this.question = '';
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

    try {
      for await (const event of this.chatService.ask(conversationId, question)) {
        if ('delta' in event) {
          this.appendDelta(assistantId, event.delta);
        } else {
          this.finalizeAnswer(assistantId, event.message_id, event.citations);
        }
      }
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
    this.conversationId = conversation.id;
    // replaceState, not router.navigate: the URL should become
    // shareable/reloadable immediately, but actually routing here would
    // re-instantiate this component mid-send and drop the in-flight
    // stream.
    this.location.replaceState(`/chat/${conversation.id}`);
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

  private finalizeAnswer(assistantId: string, messageId: string, citations: Citation[]): void {
    this.messages.update((current) =>
      current.map((message) =>
        message.id === assistantId
          ? { ...message, id: messageId, citations, pending: false }
          : message,
      ),
    );
  }
}
