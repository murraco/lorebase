import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth/auth.service';
import type { ChatDoneEvent, ChatEvent } from '../../core/chat/chat.service';
import { ChatService } from '../../core/chat/chat.service';
import { ConversationsService } from '../../core/conversations/conversations.service';
import type { Citation } from '../../core/models';
import { ChatPage } from './chat.page';

function doneEvent(overrides: Partial<ChatDoneEvent> = {}): ChatDoneEvent {
  return {
    done: true,
    message_id: 'm1',
    latency_ms: null,
    input_tokens: null,
    output_tokens: null,
    cost: null,
    retrieved_count: 0,
    citations: [],
    ...overrides,
  };
}

// ChatPage reads the conversation id from the route and navigates to the
// one it creates for a new question — every instantiation needs both, not
// just the tests that care about routing. A function, not a constant: each
// test gets its own `navigate` mock rather than sharing call history.
function routeProviders() {
  return [
    // No conversationId param: every test here starts a fresh conversation.
    { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({})) } },
    { provide: Router, useValue: { navigate: vi.fn().mockResolvedValue(true) } },
  ];
}

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
      ...routeProviders(),
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(ChatPage);
  fixture.detectChanges();
  await fixture.whenStable();
  return { fixture, page: fixture.componentInstance };
}

describe('ChatPage', () => {
  it('streams deltas into the assistant message and renders citation chips', async () => {
    const citation: Citation = {
      id: 'c1',
      chunk: 'ch1',
      path: 'note.md',
      // Empty, not 'Section': the chip label falls back to `path` only
      // when there's no heading, and this test wants that fallback.
      heading_path: '',
      source_name: 'note.md',
      start_line: 1,
      end_line: 2,
      content: 'the cited fragment',
    };
    const { fixture, page } = await setup([
      { delta: 'Hello ' },
      { delta: 'world' },
      doneEvent({ retrieved_count: 1, citations: [citation] }),
    ]);

    page['question'] = 'What is this about?';
    await page['send']();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Hello world');
    expect(el.textContent).toContain('note.md');
    expect(el.textContent).not.toContain('the cited fragment');

    (el.querySelector('.source-chip') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(el.textContent).toContain('the cited fragment');
    fixture.destroy();
  });

  it('renders the assistant answer as actual markdown, not literal asterisks', async () => {
    const { fixture, page } = await setup([{ delta: '**bold claim**' }, doneEvent()]);

    page['question'] = 'question';
    await page['send']();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.rendered-markdown strong')?.textContent).toBe('bold claim');
    fixture.destroy();
  });

  it('sends on Enter but inserts a newline on Shift+Enter', async () => {
    const { fixture, page } = await setup([doneEvent()]);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sendSpy = vi.spyOn(page as any, 'send');

    const shiftEnter = { shiftKey: true, preventDefault: vi.fn() } as unknown as Event;
    page['onEnter'](shiftEnter);
    expect(shiftEnter.preventDefault).not.toHaveBeenCalled();
    expect(sendSpy).not.toHaveBeenCalled();

    const plainEnter = { shiftKey: false, preventDefault: vi.fn() } as unknown as Event;
    page['onEnter'](plainEnter);
    expect(plainEnter.preventDefault).toHaveBeenCalled();
    expect(sendSpy).toHaveBeenCalled();

    fixture.destroy();
  });

  it('shows a typing indicator until the first delta arrives, then hides it', async () => {
    let releaseFirstDelta!: () => void;
    const gate = new Promise<void>((resolve) => (releaseFirstDelta = resolve));

    async function* controlledAsk(): AsyncGenerator<ChatEvent> {
      await gate;
      yield { delta: 'Hello' };
      yield doneEvent();
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
        ...routeProviders(),
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ChatPage);
    fixture.detectChanges();
    await fixture.whenStable();

    const page = fixture.componentInstance;
    page['question'] = 'question';
    const sendPromise = page['send']();
    const el = fixture.nativeElement as HTMLElement;

    // Let the microtask queue drain enough for the placeholder messages
    // (user + pending assistant) to be pushed onto the signal, without
    // resolving `gate` yet — the generator is still parked on `await gate`.
    // Polled rather than a fixed number of ticks: `send()` awaits
    // `ensureConversation()`, whose own chain of awaits (create the
    // conversation, then navigate to it) is an implementation detail
    // that has already changed shape once and could again.
    let indicatorShown = false;
    for (let i = 0; i < 10 && !indicatorShown; i++) {
      await Promise.resolve();
      fixture.detectChanges();
      indicatorShown = el.querySelector('.typing-indicator') !== null;
    }
    expect(indicatorShown).toBeTruthy();

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
        ...routeProviders(),
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
