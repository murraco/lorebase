# ADR 0007 — Django session-cookie auth instead of JWT/OAuth

**Status:** Accepted

## Context

The SPA needs to authenticate its requests to the API. A common default for
a decoupled frontend is token-based auth (JWT, typically with an
access/refresh pair) so the API stays statelessly verifiable and
cookie/origin concerns don't come up. Lorebase's frontend and backend,
though, are deployed behind one reverse proxy (`frontend/nginx.conf`
proxies `/api/*`) — same origin, not a cross-origin SPA talking to a
separately-hosted API.

## Decision

Use Django's built-in session auth: a `sessionid` cookie plus CSRF
protection (`csrftoken` cookie, `X-CSRFToken` header attached by
`frontend/src/app/core/api/client.ts`), both `SameSite`, both marked
`Secure` in production (`config/settings/prod.py`). No JWT library, no
access/refresh token pair, no token storage or refresh scheduling in the
frontend at all.

## Consequences

**Gains:**
- No refresh-token machinery to build: no silent-refresh timer, no
  race between an expiring access token and an in-flight request, no
  decision about where to store a token client-side (`localStorage` is
  XSS-exposed; an httpOnly cookie is effectively reinventing session auth
  under a different name).
- CSRF is the only cross-request forgery concern to reason about — a
  session cookie sent automatically by the browser is exactly the case
  Django's CSRF middleware is built for, so protection is a settings flag
  and a header, not custom logic.
- Login/logout is a plain server-side state change (`core/views.py`), not a
  client-side token lifecycle the frontend has to manage correctly.

**Costs / accepted limitations:**
- Only works because frontend and backend are same-origin behind one
  proxy. A separately-hosted frontend (a different domain, a mobile app, a
  third-party client) couldn't authenticate this way — this is *why* the
  MCP server (Etapa 17), a genuinely separate client, uses its own bearer
  API-key auth (`ApiKey` model) instead of reusing session cookies.
- Doesn't extend to any future non-browser, non-same-origin client without
  adding a second auth mechanism for it, the way MCP already needed one.

**Migration trigger:** a client that can't share the browser's cookie jar
with the API's origin — a mobile app, a third-party integration, or a
frontend hosted on a different domain. At that point the precedent is
already in the codebase: add token-based auth for that specific client
(as MCP's `ApiKey` already does), rather than replacing session auth for
the SPA that doesn't need it.
