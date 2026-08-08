import { Injectable, signal } from '@angular/core';

import { apiClient } from '../api/client';
import type { Conversation, Message } from '../models';

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

  async listMessages(conversationId: string): Promise<Message[]> {
    const { data, error } = await apiClient.GET('/api/messages/', {
      params: { query: { conversation: conversationId } },
    });
    if (error) throw new Error('Failed to load messages.');
    return data.results;
  }
}
