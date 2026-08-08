import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth/auth.service';
import type { ChatEvent } from '../../core/chat/chat.service';
import { ChatService } from '../../core/chat/chat.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import { ChatPage } from './chat.page';

async function setup(events: ChatEvent[]) {
  async function* fakeAsk(): AsyncGenerator<ChatEvent> {
    for (const event of events) yield event;
  }

  await TestBed.configureTestingModule({
    imports: [ChatPage],
    providers: [
      {
        provide: AuthService,
        useValue: { primaryWorkspace: () => ({ id: 'ws-1', name: 'Workspace' }) },
      },
      {
        provide: ConversationsService,
        useValue: { create: vi.fn().mockResolvedValue({ id: 'conv-1' }) },
      },
      { provide: ChatService, useValue: { ask: vi.fn().mockImplementation(() => fakeAsk()) } },
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(ChatPage);
  fixture.detectChanges();
  await fixture.whenStable();
  return { fixture, page: fixture.componentInstance };
}

describe('ChatPage', () => {
  it('streams deltas into the assistant message and renders citation chips', async () => {
    const { fixture, page } = await setup([
      { delta: 'Hello ' },
      { delta: 'world' },
      {
        done: true,
        message_id: 'm1',
        citations: [
          {
            id: 'c1',
            chunk: 'ch1',
            path: 'note.md',
            start_line: 1,
            end_line: 2,
            content: 'the cited fragment',
          },
        ],
      },
    ]);

    page['question'] = 'What is this about?';
    await page['send']();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Hello world');
    expect(el.textContent).toContain('note.md');
    expect(el.textContent).not.toContain('the cited fragment');

    (el.querySelector('.cite') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(el.textContent).toContain('the cited fragment');
    fixture.destroy();
  });

  it('shows a typing indicator until the first delta arrives, then hides it', async () => {
    let releaseFirstDelta!: () => void;
    const gate = new Promise<void>((resolve) => (releaseFirstDelta = resolve));

    async function* controlledAsk(): AsyncGenerator<ChatEvent> {
      await gate;
      yield { delta: 'Hello' };
      yield { done: true, message_id: 'm1', citations: [] };
    }

    await TestBed.configureTestingModule({
      imports: [ChatPage],
      providers: [
        {
          provide: AuthService,
          useValue: { primaryWorkspace: () => ({ id: 'ws-1', name: 'Workspace' }) },
        },
        {
          provide: ConversationsService,
          useValue: { create: vi.fn().mockResolvedValue({ id: 'conv-1' }) },
        },
        { provide: ChatService, useValue: { ask: () => controlledAsk() } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ChatPage);
    fixture.detectChanges();
    await fixture.whenStable();

    const page = fixture.componentInstance;
    page['question'] = 'question';
    const sendPromise = page['send']();
    // Let the microtask queue drain enough for the placeholder messages
    // (user + pending assistant) to be pushed onto the signal, without
    // resolving `gate` yet — the generator is still parked on `await gate`.
    await Promise.resolve();
    await Promise.resolve();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.typing-indicator')).toBeTruthy();

    releaseFirstDelta();
    await sendPromise;
    fixture.detectChanges();

    expect(el.querySelector('.typing-indicator')).toBeFalsy();
    expect(el.textContent).toContain('Hello');
    fixture.destroy();
  });

  it('shows a fallback message when the chat request fails', async () => {
    async function* failingAsk(): AsyncGenerator<ChatEvent> {
      yield { delta: 'partial answer, then ' };
      throw new Error('network error');
    }

    await TestBed.configureTestingModule({
      imports: [ChatPage],
      providers: [
        {
          provide: AuthService,
          useValue: { primaryWorkspace: () => ({ id: 'ws-1', name: 'Workspace' }) },
        },
        {
          provide: ConversationsService,
          useValue: { create: vi.fn().mockResolvedValue({ id: 'conv-1' }) },
        },
        { provide: ChatService, useValue: { ask: () => failingAsk() } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ChatPage);
    fixture.detectChanges();
    await fixture.whenStable();

    const page = fixture.componentInstance;
    page['question'] = 'question';
    await page['send']();
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Something went wrong answering that.',
    );
    fixture.destroy();
  });
});
