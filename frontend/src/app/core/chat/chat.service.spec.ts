import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatService } from './chat.service';

function streamingResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

describe('ChatService', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('yields delta events followed by the done event', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          streamingResponse([
            'data: {"delta":"Hello "}\n\n',
            'data: {"delta":"world"}\n\n',
            'data: {"done":true,"message_id":"m1","citations":[]}\n\n',
          ]),
        ),
    );

    const received = [];
    for await (const event of new ChatService().ask('conv-1', 'question')) {
      received.push(event);
    }

    expect(received).toEqual([
      { delta: 'Hello ' },
      { delta: 'world' },
      { done: true, message_id: 'm1', citations: [] },
    ]);
  });

  it('reassembles an SSE event split across multiple stream chunks', async () => {
    // Regression guard: the parser buffers across reads instead of
    // assuming one `data: ...\n\n` frame arrives per chunk — a real risk
    // with a hand-rolled SSE reader, since TCP/HTTP chunking has no
    // obligation to respect frame boundaries.
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          streamingResponse(['data: {"del', 'ta":"Hello"}\n\ndata: {"delta":" world"}\n\n']),
        ),
    );

    const received = [];
    for await (const event of new ChatService().ask('conv-1', 'question')) {
      received.push(event);
    }

    expect(received).toEqual([{ delta: 'Hello' }, { delta: ' world' }]);
  });

  it('throws when the response is not ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

    await expect(new ChatService().ask('conv-1', 'question').next()).rejects.toThrow(
      'Chat request failed (500).',
    );
  });
});
