# Lorebase

AI-powered knowledge platform with RAG, hybrid search, and verifiable citations.

Lorebase indexes personal knowledge — plain Markdown notes, PDFs, and GitHub
repositories — so you can ask questions like *"what did I write about X?"*
and get answers with citations that point back to the exact file and line
they came from. The architecture is plugin-first: sources, embedding
providers, and LLM providers are all swappable implementations behind small
interfaces, so the same backend can later scale from a personal "second
brain" to a team knowledge wiki without a redesign.

## Stack

- **Backend:** Django + Django REST Framework, Celery, PostgreSQL with
  pgvector (vector search) and native full-text search (lexical search).
- **Embeddings & reranking:** Voyage AI.
- **LLM:** Anthropic.
- **Frontend:** Angular.
- **Infra:** Docker Compose.

See [`docs/plan-ai-knowledge-platform.md`](docs/plan-ai-knowledge-platform.md)
for the full design document.

## Getting started

```bash
docker compose -f infra/docker-compose.yml up --build
```

Then open [http://localhost:8080](http://localhost:8080) — Nginx serves the
Angular app and proxies `/api` to the backend, so it's all one origin (the
session cookie just works). The API on its own is also reachable directly
at `http://localhost:8000` (Swagger UI at `/api/schema/swagger-ui/`).

> See [`docs/roadmap.md`](docs/roadmap.md) for the implementation roadmap
> and current progress.

## License

MIT — see [LICENSE](LICENSE).
