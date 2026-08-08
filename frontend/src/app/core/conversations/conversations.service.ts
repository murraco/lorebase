import { Injectable } from '@angular/core';

import { apiClient } from '../api/client';
import type { Conversation, Message } from '../models';

@Injectable({ providedIn: 'root' })
export class ConversationsService {
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
