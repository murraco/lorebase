import { Injectable } from '@angular/core';

import { readCookie } from '../api/cookies';
import type { Citation } from '../models';

export interface ChatDeltaEvent {
  delta: string;
}

export interface ChatDoneEvent {
  done: true;
  message_id: string;
  citations: Citation[];
}

export type ChatEvent = ChatDeltaEvent | ChatDoneEvent;

@Injectable({ providedIn: 'root' })
export class ChatService {
  /** The chat endpoint isn't a DRF view and streams Server-Sent Events
   * over a POST response, which the browser's native EventSource can't
   * do (it only supports GET) — so this reads and frames the stream by
   * hand instead.
   */
  async *ask(conversationId: string, question: string): AsyncGenerator<ChatEvent> {
    const response = await fetch(`/api/conversations/${conversationId}/chat/`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': readCookie('csrftoken') ?? '',
      },
      body: JSON.stringify({ question }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Chat request failed (${response.status}).`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const dataLine = rawEvent.split('\n').find((line) => line.startsWith('data: '));
        if (dataLine) {
          yield JSON.parse(dataLine.slice('data: '.length)) as ChatEvent;
        }
        boundary = buffer.indexOf('\n\n');
      }
    }
  }
}
