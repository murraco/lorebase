import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, RouteReuseStrategy, type Routes } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { describe, expect, it } from 'vitest';

import { ChatRouteReuseStrategy } from './chat-route-reuse-strategy';

@Component({ selector: 'lorebase-route-stub', template: '' })
class StubComponent {}

const routes: Routes = [
  { path: 'chat', component: StubComponent },
  { path: 'chat/:conversationId', component: StubComponent },
  { path: 'corpus', component: StubComponent },
];

function configure(): void {
  TestBed.configureTestingModule({
    providers: [
      provideRouter(routes),
      { provide: RouteReuseStrategy, useClass: ChatRouteReuseStrategy },
    ],
  });
}

describe('ChatRouteReuseStrategy', () => {
  it('reuses the component instance moving from /chat to /chat/:conversationId', async () => {
    configure();
    const harness = await RouterTestingHarness.create();

    const beforeSending = await harness.navigateByUrl('/chat', StubComponent);
    // What ensureConversation() triggers once a new conversation gets an
    // id — the exact navigation that used to orphan an in-flight answer.
    const afterConversationCreated = await harness.navigateByUrl(
      '/chat/11111111-1111-1111-1111-111111111111',
      StubComponent,
    );

    expect(afterConversationCreated).toBe(beforeSending);
  });

  it('reuses the instance moving between two different conversations', async () => {
    configure();
    const harness = await RouterTestingHarness.create();

    const first = await harness.navigateByUrl(
      '/chat/11111111-1111-1111-1111-111111111111',
      StubComponent,
    );
    const second = await harness.navigateByUrl(
      '/chat/22222222-2222-2222-2222-222222222222',
      StubComponent,
    );

    expect(second).toBe(first);
  });

  it('does not reuse the instance moving to an unrelated route', async () => {
    configure();
    const harness = await RouterTestingHarness.create();

    const onChat = await harness.navigateByUrl('/chat', StubComponent);
    const onCorpus = await harness.navigateByUrl('/corpus', StubComponent);

    expect(onCorpus).not.toBe(onChat);
  });
});
