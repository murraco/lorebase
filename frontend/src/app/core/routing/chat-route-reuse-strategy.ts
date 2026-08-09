import { ActivatedRouteSnapshot, BaseRouteReuseStrategy } from '@angular/router';

const CHAT_PATHS = new Set(['chat', 'chat/:conversationId']);

function isChatRoute(snapshot: ActivatedRouteSnapshot): boolean {
  return CHAT_PATHS.has(snapshot.routeConfig?.path ?? '');
}

/** Angular's default strategy only reuses a component across navigations
 * within the *same* route config entry — `chat` and `chat/:conversationId`
 * are two separate entries (both lazy-loading ChatPage), so it destroys
 * and recreates the component when moving between them, even though nothing
 * about the component itself changed.
 *
 * That destruction lands at the worst possible moment: sending the first
 * message of a new conversation calls `router.navigate(['/chat', id])`
 * once the id exists, *while the answer is still streaming*. The default
 * strategy tears the component down mid-stream, orphaning that in-flight
 * request — its continuation keeps running and updates a signal nothing
 * renders anymore. Nothing appears on screen until a manual refresh loads
 * the by-then-finished conversation from scratch.
 *
 * Extending reuse across just these two paths is enough: ChatPage already
 * handles route reuse correctly elsewhere (its ngOnInit subscribes to
 * paramMap rather than reading a snapshot once, precisely because Angular
 * already reuses it across /chat/:id1 -> /chat/:id2). This only makes that
 * same, already-correct handling also apply to the chat -> chat/:id case.
 */
export class ChatRouteReuseStrategy extends BaseRouteReuseStrategy {
  override shouldReuseRoute(future: ActivatedRouteSnapshot, curr: ActivatedRouteSnapshot): boolean {
    if (isChatRoute(future) && isChatRoute(curr)) return true;
    return super.shouldReuseRoute(future, curr);
  }
}
