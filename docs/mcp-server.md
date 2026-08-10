# Servidor MCP

Expone el retrieval de Lorebase (`search_knowledge`, `get_document`,
`list_sources`) como herramientas MCP, para consultar tus notas desde
Claude Code o Claude Desktop. Corre como un servicio más de Docker Compose
(`mcp_server`), sobre Streamable HTTP — ver `docs/roadmap.md` (Etapa 17) y
`docs/learning-notes.md` para la explicación conceptual de por qué HTTP y
no stdio, y cómo funciona la autenticación por token.

## 1. Levantar el servicio

Ya forma parte de `infra/docker-compose.yml`:

```bash
docker compose -f infra/docker-compose.yml up -d mcp_server
```

Queda escuchando en `http://localhost:8001/mcp`.

## 2. Generar una API key

Cada key está atada a una `Membership` (un usuario en un workspace) —
hereda exactamente los mismos permisos que esa persona ya tiene ahí.

```bash
docker compose -f infra/docker-compose.yml exec backend \
  python manage.py create_mcp_api_key --membership <membership-id> --name "Claude Code"
```

Encontrá tu `membership-id` en el admin de Django (`/admin/core/membership/`)
o por shell:

```bash
docker compose -f infra/docker-compose.yml exec backend python manage.py shell -c "
from core.models import Membership
for m in Membership.objects.select_related('user', 'workspace'):
    print(m.id, '-', m.user.username, '@', m.workspace.name)
"
```

**La key se muestra una sola vez.** Copiala antes de cerrar la terminal —
solo se guarda su hash, no hay forma de recuperarla después.

## 3. Configurar Claude Code

```bash
claude mcp add --transport http lorebase http://localhost:8001/mcp \
  --header "Authorization: Bearer <la-key-que-generaste>"
```

Confirmá que quedó conectado:

```bash
claude mcp list
```

## 4. Notas

- `MCP_SERVER_URL` (en `infra/.env`) tiene que ser la URL donde el
  *cliente* alcanza al servidor (`http://localhost:8001` en un setup
  local), no una dirección interna de Docker — es la que se publica en
  la metadata de autenticación del servidor.
- Una key revocada/borrada (`ApiKey.objects.filter(...).delete()`, o desde
  el admin) deja de autenticar en el próximo pedido — no hace falta
  reiniciar el servicio.
- La primera llamada a `search_knowledge` en un proceso recién arrancado
  tarda varios segundos más de lo normal: carga en memoria los modelos
  locales de embedding y reranking, que después quedan cacheados para el
  resto de la vida del proceso.
