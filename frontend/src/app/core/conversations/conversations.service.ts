import { Injectable, signal } from '@angular/core';

import { apiClient } from '../api/client';
import type { Conversation, Feedback, FeedbackRating, Message } from '../models';

@Injectable({ providedIn: 'root' })
export class ConversationsService {
  /** Shared with the sidebar, which lists past conversations. Kept here
   * rather than in the shell so the chat page can refresh it after a new
   * conversation gets created (and titled) by its first question. */
  readonly conversations = signal<Conversation[]>([]);

  async refresh(): Promise<void> {
    const { data, error } = await apiClient.GET('/api/conversations/');
    if (error) throw new Error('Failed to load conversations.');
    this.conversations.set(data.results);
  }

  async create(workspace: string): Promise<Conversation> {
    const { data, error } = await apiClient.POST('/api/conversations/', { body: { workspace } });
    if (error) throw new Error('Failed to create conversation.');
    return data;
  }

  async delete(id: string): Promise<void> {
    const { error } = await apiClient.DELETE('/api/conversations/{id}/', {
      params: { path: { id } },
    });
    if (error) throw new Error('Failed to delete conversation.');
    this.conversations.update((current) => current.filter((c) => c.id !== id));
  }

  async listMessages(conversationId: string): Promise<Message[]> {
    const { data, error } = await apiClient.GET('/api/messages/', {
      params: { query: { conversation: conversationId } },
    });
    if (error) throw new Error('Failed to load messages.');
    return data.results;
  }

  /** Sending the same rating twice, or a changed one, always replaces
   * the message's single Feedback row rather than adding another —
   * mirrors the backend's OneToOneField, not something enforced here. */
  async giveFeedback(
    messageId: string,
    rating: FeedbackRating,
    comment?: string,
  ): Promise<Feedback> {
    const { data, error } = await apiClient.POST('/api/messages/{message_id}/feedback/', {
      params: { path: { message_id: messageId } },
      body: { rating, comment },
    });
    if (error) throw new Error('Failed to save feedback.');
    return data;
  }
}
