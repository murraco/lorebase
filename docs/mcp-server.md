# MCP server

Exposes Lorebase's retrieval (`search_knowledge`, `get_document`,
`list_sources`) as MCP tools, so you can query your notes from Claude Code
or Claude Desktop. It runs as one more Docker Compose service
(`mcp_server`), over Streamable HTTP — see `docs/roadmap.md` (stage 17) and
`docs/applied-ai-interview-prep.md` for the conceptual explanation of why
HTTP rather than stdio, and how token authentication works.

## 1. Start the service

It's already part of `infra/docker-compose.yml`:

```bash
docker compose -f infra/docker-compose.yml up -d mcp_server
```

It listens on `http://localhost:8001/mcp`.

## 2. Generate an API key

Each key is tied to a `Membership` (one user in one workspace) — it
inherits exactly the same permissions that person already has there.

```bash
docker compose -f infra/docker-compose.yml exec backend \
  python manage.py create_mcp_api_key --membership <membership-id> --name "Claude Code"
```

Find your `membership-id` in the Django admin (`/admin/core/membership/`)
or through the shell:

```bash
docker compose -f infra/docker-compose.yml exec backend python manage.py shell -c "
from core.models import Membership
for m in Membership.objects.select_related('user', 'workspace'):
    print(m.id, '-', m.user.username, '@', m.workspace.name)
"
```

**The key is shown only once.** Copy it before closing the terminal — only
its hash is stored, so there's no way to recover it afterwards.

## 3. Configure Claude Code

```bash
claude mcp add --transport http lorebase http://localhost:8001/mcp \
  --header "Authorization: Bearer <the-key-you-generated>"
```

Confirm it connected:

```bash
claude mcp list
```

## 4. Notes

- `MCP_SERVER_URL` (in `infra/.env`) has to be the URL where the *client*
  reaches the server (`http://localhost:8001` in a local setup), not an
  internal Docker address — it's what gets published in the server's
  authentication metadata.
- A revoked/deleted key (`ApiKey.objects.filter(...).delete()`, or from the
  admin) stops authenticating on the next request — no need to restart the
  service.
- The first `search_knowledge` call in a freshly started process takes
  several seconds longer than usual: it loads the local embedding and
  reranking models into memory, which then stay cached for the rest of the
  process's life.
