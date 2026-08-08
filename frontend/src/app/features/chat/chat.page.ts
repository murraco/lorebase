import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AuthService } from '../../core/auth/auth.service';
import { ChatService } from '../../core/chat/chat.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import type { Citation } from '../../core/models';

interface ThreadMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
}

@Component({
  selector: 'lorebase-chat-page',
  imports: [FormsModule],
  templateUrl: './chat.page.html',
  styleUrl: './chat.page.css',
})
export class ChatPage implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly conversationsService = inject(ConversationsService);
  private readonly chatService = inject(ChatService);

  protected readonly messages = signal<ThreadMessage[]>([]);
  protected readonly sending = signal(false);
  protected readonly expandedCitationId = signal<string | null>(null);
  protected question = '';

  private conversationId: string | null = null;

  async ngOnInit(): Promise<void> {
    const workspace = this.auth.primaryWorkspace();
    if (!workspace) return;
    const conversation = await this.conversationsService.create(workspace.id);
    this.conversationId = conversation.id;
  }

  protected toggleCitation(citationId: string): void {
    this.expandedCitationId.update((current) => (current === citationId ? null : citationId));
  }

  protected async send(): Promise<void> {
    const question = this.question.trim();
    if (!question || !this.conversationId || this.sending()) return;

    this.question = '';
    this.messages.update((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', content: question, citations: [] },
    ]);

    const assistantId = crypto.randomUUID();
    this.messages.update((current) => [
      ...current,
      { id: assistantId, role: 'assistant', content: '', citations: [] },
    ]);
    this.sending.set(true);

    try {
      for await (const event of this.chatService.ask(this.conversationId, question)) {
        if ('delta' in event) {
          this.appendDelta(assistantId, event.delta);
        } else {
          this.finalizeAnswer(assistantId, event.message_id, event.citations);
        }
      }
    } catch {
      this.appendDelta(assistantId, 'Something went wrong answering that.');
    } finally {
      this.sending.set(false);
    }
  }

  private appendDelta(assistantId: string, delta: string): void {
    this.messages.update((current) =>
      current.map((message) =>
        message.id === assistantId ? { ...message, content: message.content + delta } : message,
      ),
    );
  }

  private finalizeAnswer(assistantId: string, messageId: string, citations: Citation[]): void {
    this.messages.update((current) =>
      current.map((message) =>
        message.id === assistantId ? { ...message, id: messageId, citations } : message,
      ),
    );
  }
}
