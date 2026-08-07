# Lorebase — Roadmap de implementación

> Documento vivo: se actualiza a medida que avanzamos o cambian decisiones.
> Es una re-división más fina de todo el roadmap de `plan-ai-knowledge-platform.md`
> (no solo su Fase 1), e incorpora las correcciones señaladas en la sección
> "Hallazgos" más abajo. La sección 7.1 de ese documento ("Hitos") queda como
> referencia histórica; **las "Etapas" de acá son las que efectivamente se
> están implementando.**

## Estado actual

| Etapa | Estado |
|---|---|
| 0 — `.gitignore` e higiene del repo | ✅ Hecha |
| 1 — Esqueleto del backend con `uv` | ✅ Hecha |
| 2 — Docker Compose y CI | ✅ Hecha |
| 3 — Modelos core (`Workspace`, `User`, `Membership`) | ✅ Hecha |
| 4 — Modelos `Source` y `Document` | ✅ Hecha |
| 5 — Interfaz de conectores y carpeta local | ✅ Hecha |
| 6 — Pipeline de ingestion y modelo `Chunk` | ✅ Hecha |
| 7 — Ingestion asíncrona con Celery | ✅ Hecha |
| 8 en adelante | Pendiente |

## Deuda técnica y pendientes conocidos

Cosas identificadas y **deliberadamente pospuestas**, no descubiertas después. Se van registrando acá a medida que aparecen, para no perderlas entre las notas de cada etapa.

- **Selección de un único archivo en `LocalFolderConnector`** (surgió en la Etapa 5). Hoy `config["path"]` tiene que ser una carpeta; no hay forma de indexar un archivo puntual de una carpeta que por lo demás no querés indexar entera. Es un caso de uso real, pendiente de implementar. Extenderlo no debería tocar la interfaz `Connector` ni la reconciliación — queda acotado a `LocalFolderConnector.fetch_documents()`.
- **`HeadingChunker` solo fusiona secciones cortas hacia adelante** (surgió en la Etapa 6). El último chunk de un documento puede quedar por debajo de `min_tokens` si es el que sobra al cierre del merge greedy — no hay un segundo paso que lo fusione hacia atrás con el chunk anterior. No es incorrecto (el chunk existe y es citable), solo un candidato más débil para retrieval. El mismo mecanismo tiene un efecto secundario en `heading_path`: si una sección sin heading (ej. el bloque de front matter, que se preserva en el texto — ver el punto de line numbers más abajo) se fusiona hacia adelante con secciones que sí tienen heading, el chunk resultante hereda el `heading_path` vacío de la primera pieza, no el de las secciones que absorbió. Las líneas siguen siendo correctas (la cita abre en el lugar justo), solo el breadcrumb queda menos informativo en ese caso puntual. Si se vuelve un problema real, agregar el paso de fusión hacia atrás es un cambio acotado a `HeadingChunker._merge_short_pieces`.
- **`Chunk.search_vector` usa `config="english"` fijo**, aunque las notas reales sean una mezcla de español e inglés (surgió en la Etapa 6). El stemming y las stopwords de Postgres son específicos de idioma — con `english` fijo, el retrieval léxico sobre texto en español pierde precisión (no matchea "buscando" con "buscar", no filtra stopwords en español). La solución correcta es un config dinámico por documento (columna `language` + detección de idioma), pospuesta hasta ver en la Etapa 16 si el retrieval léxico en español rinde mal en la práctica — la mitad densa del hybrid search (embeddings, multilingües por defecto) compensa bastante mientras tanto.

## Context

El objetivo es llevar el diseño de `plan-ai-knowledge-platform.md` a código siguiendo etapas pequeñas y verificables, evitando retrabajo. El plan cubre hasta **Fase 4 + servidor MCP**: un segundo cerebro personal completo (conectores local/PDF/GitHub, hybrid search con reranker, chat con citas verificables, feedback, dashboard, observabilidad y evaluación) más exposición del retrieval vía Model Context Protocol.

### Decisiones de alcance

- **Alcance:** Fases 1–4 del documento + servidor MCP. Fase 5 (ACLs por documento, API pública, webhooks, SDK) queda fuera.
- **Idioma:** todo el código, identificadores, comentarios y documentación técnica en **inglés**. Los textos visibles de la UI también en **inglés**. La conversación con Claude se mantiene en español.
- **Toolchain backend:** `uv` gestionando intérprete (Python 3.13) y dependencias (`pyproject.toml` + `uv.lock`).
- **Testing/CI:** `pytest-django` desde la etapa 1, tests por etapa sobre la lógica de negocio, GitHub Actions con lint + tests desde temprano.

---

## Hallazgos previos al plan

Esto es lo que surgió al analizar el documento de diseño y el entorno antes de arrancar a codear. Cada punto ya está incorporado en las etapas correspondientes.

### Bloqueantes de entorno (verificados en esta máquina)

| Problema | Detalle | Solución en el plan |
|---|---|---|
| **Python 3.9.1** en el host | Django 6.1 requiere Python 3.12+ | `uv python install 3.13`, misma versión en la imagen Docker (Etapa 1) |
| **Node 25.8.1** en el host | Angular CLI 22 declara `node: ^22.22.3 \|\| ^24.15.0 \|\| >=26.0.0`. **25.x no está soportado** y el CLI va a fallar o advertir | Fijar **Node 24 LTS** con `.nvmrc` en `frontend/` (Etapa 13) |
| `uv` no instalado | — | Paso explícito en Etapa 1 |

### Errores y contradicciones en el documento de diseño

1. **`latency_ms` y `cost` colgando de `Feedback` (§4.11) es un error de modelado.** Esas métricas existen para *toda* respuesta, no solo para las que reciben pulgar arriba/abajo. Si viven en `Feedback`, el dashboard de costos solo ve los mensajes calificados. → Van en `Message` (o una tabla `MessageMetrics` 1--1); `Feedback` guarda solo `rating` + `comment`.
2. **`Workspace 1--N User` (§4.11) cierra la puerta al multi-workspace de Fase 5.** Un usuario quedaría atado a un único workspace. → Tabla `Membership(user, workspace, role)` desde el día uno. Es gratis ahora y caro después (migración de datos + reescritura de todos los querysets).
3. **El "keyword search placeholder" del Hito 7 es retrabajo evitable.** El documento lo asume descartable, pero no hace falta: la búsqueda léxica de Postgres (`tsvector` + `websearch_to_tsquery` + `ts_rank`) **ya es la mitad léxica del hybrid search final**. → La primera implementación de retrieval se escribe con la interfaz definitiva (`Retriever`), y la Fase 2 solo suma la mitad densa y la fusión. Cero código tirado.
4. **Agregar pgvector tarde obliga a una migración + reindexado completo.** La dimensión del vector se fija al crear la columna. → La extensión `vector` y la columna `Chunk.embedding` (nullable) entran en la **primera** migración de `Chunk`, aunque los embeddings se calculen recién en la Etapa 9.
5. **Contradicción de alcance de conectores:** §2.1 pone Notion/Confluence/Drive "dentro del MVP" pero §7 los manda a Fase 3. → Se respeta el roadmap: MVP = carpeta local + PDF + GitHub.
6. **Contradicción en el flujo de consulta:** §5 dibuja "el LLM decide qué buscar" (retrieval agéntico con tool use) mientras §4.12 describe retrieval directo. → MVP con retrieval directo + query rewriting; el retrieval agéntico se evalúa como mejora *medible* en la Etapa 16, no a ciegas.
7. **"Citations obligatorias" no tiene mecanismo, solo intención.** Pedirlas en el prompt no las garantiza. → El LLM devuelve salida estructurada con `chunk_id`s vía tool use, y el servidor **valida que cada id citado estuviera realmente en el contexto** antes de persistir la respuesta. Una cita que no valida se descarta. Esto es lo que hace que las citas sean verificables por construcción y no una promesa del prompt.
8. **`StorageProvider` propio (§4.6) es código innecesario.** Django ya trae una API de storages pluggable (setting `STORAGES` + `django.core.files.storage`). Migrar a Garage/S3 después es instalar `django-storages` y cambiar un setting. → Se usa la de Django.
9. **Soft delete sin purga de índice.** `Document.deleted = True` deja los `Chunk` vivos y siguen apareciendo en retrieval. → Borrado físico de chunks al marcar el documento como borrado; el `Document` queda como tombstone.
10. **Faltantes no mencionados en el documento:** estrategia de tests, CI, gestión de configuración/secretos, `.env.example`, esquema OpenAPI, diseño del streaming (DRF no lo maneja bien), y locking de jobs de sync concurrentes sobre la misma fuente. Todo cubierto en las etapas.
11. **Naming inconsistente:** el repo y el README dicen `lorebase`; el wireframe dice "Cuaderno". → Se adopta **Lorebase** en todo (marca de UI incluida).
12. **`.gitignore` con patrones sin anclar.** `lib/`, `var/`, `build/`, `dist/`, `target/` vienen de la plantilla Python y matchean *cualquier* directorio con ese nombre a cualquier profundidad: van a ignorar silenciosamente carpetas legítimas del frontend Angular (`frontend/src/app/lib/`, por ejemplo). → Se anclan a la raíz o a `backend/`.

### Elecciones técnicas que el documento dejó abiertas

- **Parser de PDF:** `pymupdf4llm`, que extrae **a Markdown**. Así el PDF entra al *mismo* chunker que las notas: un solo camino de código en vez de dos.
- **Reranker:** Voyage (mismo vendor que embeddings ⇒ una sola API key y un solo cliente).
- **Auth SPA:** sesión de Django con cookies `SameSite` (mismo origen detrás del reverse proxy). Evita toda la lógica de refresh de tokens del MVP.
- **Streaming:** DRF para el CRUD; el endpoint de chat es una vista Django async con `StreamingHttpResponse` (SSE), fuera de DRF.
- **Cliente API tipado:** `drf-spectacular` genera OpenAPI y de ahí se genera el cliente TypeScript de Angular. Elimina el mantenimiento manual de modelos duplicados.

---

## Convenciones del proyecto

- Código, identificadores, comentarios, documentación técnica y textos de UI: **inglés**.
- Python: `ruff` (lint + format), `mypy` en modo gradual sobre `core/` y `rag/`.
- TypeScript: ESLint + Prettier, strict mode.
- Commits: título corto en modo imperativo (sin prefijo `feat:`/`chore:`), sin cuerpo salvo que agregue algo que el diff no explique.
- Toda etapa termina con tests verdes y CI en verde.

## Stack fijado

| Capa | Elección | Versión verificada |
|---|---|---|
| Runtime backend | Python | 3.13 |
| Framework | Django + DRF | 6.1 / 3.17 |
| Workers / broker | Celery + Redis | 5.6 |
| Base de datos | PostgreSQL + pgvector | 17 / `pgvector` 0.5 |
| Búsqueda léxica | Postgres FTS (`tsvector`) | nativo |
| Embeddings + rerank | Voyage AI | `voyageai` 0.5 |
| LLM | Anthropic | `anthropic` 0.120 |
| PDF | `pymupdf4llm` | 1.28 |
| Config | `django-environ` | 0.14 |
| Esquema API | `drf-spectacular` | 0.30 |
| Frontend | Angular (Node 24 LTS) | 22.1 |
| Contenedores | Docker Compose | v5 |

> Los identificadores exactos de modelo de Voyage y Anthropic se confirman contra la documentación del proveedor al llegar a las Etapas 9 y 11. Se exponen como settings (`EMBEDDING_MODEL`, `EMBEDDING_DIM`, `RERANK_MODEL`, `LLM_MODEL`), nunca hardcodeados.

## Estructura del repositorio

```
lorebase/
├── backend/
│   ├── pyproject.toml, uv.lock, Dockerfile, manage.py
│   ├── config/                 # settings/, urls, celery, asgi/wsgi
│   ├── core/                   # Workspace, User, Membership
│   ├── sources/                # Source, Document, connectors/
│   ├── ingestion/              # parsers/, chunking/, pipeline, tasks
│   ├── rag/                    # embeddings/, retrieval/, llm/, chat
│   ├── analytics/              # Feedback, metrics, dashboard
│   ├── mcp_server/             # servidor MCP (Etapa 17)
│   └── tests/
├── frontend/                   # workspace Angular, .nvmrc
├── infra/                      # docker-compose.yml, .env.example, init scripts
├── docs/                       # el plan de diseño + roadmap + ADRs
└── .github/workflows/
```

---

## Roadmap

Las etapas son secuenciales salvo donde se indique. Cada una es un PR.

---

### Bloque A — Fundaciones

#### Etapa 0 — `.gitignore` e higiene del repo ✅

**Objetivo:** que ningún artefacto generado, secreto o archivo de sistema pueda entrar al repo, antes de escribir la primera línea de código.

**Tareas** (en orden):
1. **Anclar** los patrones de packaging Python que hoy están sueltos, para que no pisen carpetas del frontend: `/backend/build/`, `/backend/dist/`, `/backend/lib/`, `/backend/var/`, `/backend/target/`, `/backend/share/python-wheels/`.
2. Agregar **Node/Angular**: `node_modules/`, `frontend/dist/`, `.angular/`, `frontend/coverage/`, `*.tsbuildinfo`, `.eslintcache`.
3. Agregar **macOS/IDE**: `.DS_Store` (hoy aparece sin trackear en `git status`), `._*`, `.idea/`, `.vscode/*` con excepción `!.vscode/extensions.json`.
4. Agregar **Docker/infra**: `infra/data/`, `*.local.yml`.
5. Agregar **runtime de Django**: `/backend/media/`, `/backend/staticfiles/`, `/backend/storage/` (cache de PDFs originales).
6. Agregar **variantes de entorno** manteniendo el ejemplo: `.env.*` + `!.env.example`.
7. Confirmar que `uv.lock` **NO** se ignora (la plantilla lo trae comentado; se versiona).
8. Agregar `.dockerignore` en `backend/` y `frontend/`.
9. Reescribir `README.md`: qué es Lorebase, stack, arranque rápido.
10. Mover el documento de diseño y el wireframe a `docs/`, versionados.

**Dependencias:** ninguna.
**Hecho cuando:** `git status --ignored` no lista ningún archivo generado como trackeable; `git check-ignore -v .DS_Store` acierta; `git check-ignore backend/uv.lock` no matchea.

---

#### Etapa 1 — Esqueleto del monorepo y toolchain del backend ✅

**Objetivo:** un proyecto Django que arranca, con dependencias reproducibles, lint y tests configurados.

**Tareas:**
1. Instalar `uv`; `uv python install 3.13`.
2. `backend/pyproject.toml` con Django, DRF, `django-environ`, `psycopg[binary]`, `celery[redis]`, y grupo dev (`pytest`, `pytest-django`, `pytest-cov`, `ruff`, `mypy`, `factory-boy`).
3. `django-admin startproject config backend/` con settings dividido: `config/settings/{base,dev,test,prod}.py`, todos los secretos vía `django-environ`.
4. `infra/.env.example` con cada variable documentada y sin valores reales.
5. `pytest.ini`/`pyproject` con `DJANGO_SETTINGS_MODULE=config.settings.test`; un test smoke.
6. `ruff` + `mypy` configurados; `Makefile` con `make lint test migrate run`.

**Dependencias:** Etapa 0.
**Hecho cuando:** `make lint` y `make test` pasan en verde; `uv sync` reproduce el entorno desde cero; ningún secreto en el código.

---

#### Etapa 2 — Docker Compose y CI ✅

**Objetivo:** infraestructura local levantable con un comando y pipeline de CI operativo.

**Tareas:**
1. `infra/docker-compose.yml`: `db` (imagen `pgvector/pgvector:pg17`), `redis`, `backend`, `worker`. Volúmenes nombrados, healthchecks.
2. `backend/Dockerfile` multi-stage sobre Python 3.13, instalando con `uv`.
3. Script de init de Postgres que ejecuta `CREATE EXTENSION IF NOT EXISTS vector;` — en la base de la app **y en `template1`** (para que la base de test de Django, creada a partir de `template1`, también la herede).
4. Cablear Celery (`config/celery.py`) contra Redis; una task `ping` de prueba.
5. `.github/workflows/ci.yml`: servicios postgres+redis, `ruff check`, `mypy`, `pytest --cov`.

**Dependencias:** Etapa 1.
**Hecho cuando:** `docker compose up` deja los 4 servicios healthy; la task `ping` se ejecuta en el worker; el CI corre verde en un PR.

**Notas de la implementación real:**
- El puerto 5432 del contenedor `db` se publica como **5434** en el host: había un Postgres nativo de macOS ya escuchando en 5432, ajeno al proyecto.
- La secret key de Django no puede generarse con `get_random_secret_key()` para un `.env` que lee Docker Compose: su charset incluye `$`, que Compose interpreta como referencia a otra variable (`${VAR}`) y lo corrompe en silencio. Se usa `secrets.token_urlsafe()` en su lugar.
- `astral-sh/setup-uv` no publica tags flotantes por versión mayor (`v9`) como sí hace `actions/checkout` — hay que pinearlo a la versión exacta (`v9.0.0`).

---

### Bloque B — Dominio e ingestion

#### Etapa 3 — Modelos core ✅

**Objetivo:** base multi-tenant correcta desde el inicio, aunque hoy sea mono-usuario.

**Tareas:**
1. App `core`: `User` custom (`AbstractUser`, **obligatorio hacerlo antes de la primera migración**), `Workspace`, `Membership(user, workspace, role)` — ver hallazgo 2.
2. Modelo base abstracto con `id` UUID, `created_at`, `updated_at`.
3. Registro en Django Admin.
4. Factories de `factory-boy` + tests de las reglas de membresía.

**Dependencias:** Etapa 2.
**Hecho cuando:** migraciones aplican en limpio; se puede crear un superusuario y ver las tres entidades en el admin; tests verdes.

> Riesgo: sustituir `AUTH_USER_MODEL` después de la primera migración es doloroso. Por eso esta etapa va antes que cualquier otro modelo.

**Notas de la implementación real:**
- `User` hereda tanto `AbstractUser` como el `BaseModel` propio, para que **toda** entidad del schema (`User` incluido) use UUID como PK — importa para la Etapa 12, donde la API expone IDs de forma consistente.
- El riesgo del recuadro de arriba se concretó: la base de Docker ya tenía migraciones de `auth`/`admin`/`sessions` aplicadas desde la Etapa 2 (con el `User` default de Django, PK entero). Cambiar `AUTH_USER_MODEL` después de eso no reescribe ese DDL ya aplicado. Se resolvió reseteando la base de dev (`DROP DATABASE` + `CREATE DATABASE`) y migrando de cero — válido porque no había datos reales, y confirma que el fix de `template1` de la Etapa 2 no hay que repetirlo: la base nueva heredó `vector` sola.
- `tests/` quedó excluido de `mypy`: `factory_boy` arma sus factories con metaclases que devuelven instancias del modelo en runtime, algo que mypy no puede inferir (ve el tipo `SomeFactory`, no el modelo real). El plan ya scopeaba mypy a `core/`/`rag/` en modo gradual, así que la exclusión es consistente, no una concesión nueva.

---

#### Etapa 4 — Modelos `Source` y `Document` ✅

**Objetivo:** representar fuentes y documentos con soporte de reindexado incremental.

**Tareas:**
1. `Source`: `workspace`, `name`, `type` (choices), `config` (JSONField), `status`, `last_synced_at`, `last_error`.
2. `Document`: `source`, `external_id`, `path`, `title`, `content_hash`, `version`, `deleted`, `metadata` (JSONField). Unique en `(source, external_id)`.
3. Índices sobre `(source, content_hash)` y `(source, deleted)`.
4. Admin con filtros por fuente y estado.

**Dependencias:** Etapa 3.
**Hecho cuando:** se pueden crear fuentes y documentos desde el admin; el constraint de unicidad se verifica con un test.

**Notas de la implementación real:**
- `Source.type` por ahora solo tiene `local_folder` y `github` como choices (lo único planificado hasta la Etapa 14); sumar un conector nuevo es agregar un valor acá **y** su implementación en el registry de la Etapa 5, no tocar el modelo de datos.
- El constraint de unicidad es `(source, external_id)`, no `external_id` global — un mismo `external_id` puede repetirse entre fuentes distintas sin problema (cubierto por test explícito).

---

#### Etapa 5 — Interfaz de conectores y conector de carpeta local ✅

**Objetivo:** la abstracción plugin-first funcionando, validada con el primer conector real.

**Tareas** (en orden):
1. `sources/connectors/base.py`: ABC `Connector` con `validate_config()`, `test_connection()`, `fetch_documents() -> Iterator[RawDocument]`. `RawDocument` es un dataclass (`external_id`, `path`, `title`, `content` o `binary`, `metadata`).
2. `sources/connectors/registry.py`: registro por `source.type` mediante decorador; resolución de la implementación en runtime.
3. `LocalFolderConnector`: recorre el directorio, lee `.md`, parsea front-matter YAML, calcula hash del contenido.
4. Reconciliación: comparar el conjunto entrante contra los `Document` existentes → altas / cambios (hash distinto) / bajas (ausentes ⇒ `deleted=True`).
5. `manage.py sync_source <id>` (síncrono todavía).
6. Tests con un directorio temporal: alta, modificación, borrado, y **no-op cuando nada cambió**.

**Dependencias:** Etapa 4.
**Hecho cuando:** correr el comando dos veces seguidas sin tocar archivos no genera ninguna escritura; agregar/editar/borrar un `.md` se refleja correctamente; tests verdes.

**Notas de la implementación real:**
- `RawDocument.content_hash` es un campo explícito del dataclass, no algo que la reconciliación calcule — cada conector lo genera como mejor le convenga (sha256 del archivo para `local_folder`; será el SHA de git para GitHub en la Etapa 14). La reconciliación solo compara strings, nunca sabe cómo se generaron.
- **Bug real encontrado y corregido:** el registro de conectores (`@register_connector`) es un efecto secundario de *importar* el módulo del conector. Sin nada que fuerce esa importación, `sync_source()` fallaba con `No connector registered` en cualquier proceso donde nadie hubiera importado `local_folder.py` antes — lo cual incluía el comando `manage.py sync_source` real, no solo un test aislado. Se resolvió importando los conectores desde `SourcesConfig.ready()`, el hook de Django pensado exactamente para este tipo de registro-al-arrancar.
- La reconciliación también contempla "revivir" un `Document` soft-deleted cuyo archivo vuelve a aparecer — sin este caso, se violaba el constraint de unicidad `(source, external_id)` al intentar crear un duplicado. Cubierto con test explícito.
- Selección de un archivo único (en vez de una carpeta entera) quedó **pendiente**, a pedido explícito: es un caso real para el uso personal, pero se prefirió no anticiparlo sin necesidad inmediata. Extenderlo más adelante no debería tocar la interfaz `Connector` ni la reconciliación — es un cambio acotado a `LocalFolderConnector.fetch_documents()`.
- **Guarda de tamaño máximo** (agregada después, al arrancar la Etapa 7, pero pertenece acá): todo el pipeline de parsing/chunking trabaja en memoria, sin streaming. `LocalFolderConnector` ahora chequea `file_path.stat().st_size` **antes** de leer el archivo, y salta (con warning en el log) cualquiera que supere `settings.MAX_DOCUMENT_SIZE_BYTES` (10 MB por defecto) — para no arriesgar cargar algo patológicamente grande completo en RAM solo para descartarlo después.

---

#### Etapa 6 — Pipeline de ingestion y modelo `Chunk` ✅

**Objetivo:** convertir documentos en chunks consultables, con el esquema de búsqueda ya listo para las dos mitades del hybrid search.

**Tareas** (en orden):
1. `ingestion/parsers/base.py` (ABC `Parser`) + `MarkdownParser` → texto limpio conservando la jerarquía de encabezados.
2. `ingestion/chunking/`: `HeadingChunker` (por encabezado, con merge de secciones cortas y split de las largas por tokens). Interfaz `Chunker` para poder alternar estrategias.
3. Modelo `Chunk`: `document`, `index`, `content`, `heading_path`, `start_line`, `end_line`, `token_count`, `metadata`, **`embedding` (`VectorField`, nullable) y `search_vector` (`SearchVectorField`)** — ver hallazgo 4. Migración con `CREATE EXTENSION vector`, índice GIN sobre `search_vector` e índice HNSW sobre `embedding`.
4. `search_vector` poblado por trigger o por `SearchVector` en el save del pipeline.
5. `ingestion/pipeline.py`: `document → parse → chunk → persist`. En cambio de hash: **reemplazar todos los chunks del documento**. En `deleted=True`: **borrado físico de sus chunks** (hallazgo 9).
6. Tests: chunking de notas cortas y largas, exactitud de `start_line`/`end_line` (las citas dependen de esto), y purga de chunks al borrar.

**Dependencias:** Etapa 5.
**Hecho cuando:** un directorio real de notas produce chunks con line ranges correctos; reindexar sin cambios no reescribe nada; borrar una nota elimina sus chunks; `search_vector` poblado en todos.

**Notas de la implementación real:**
- `ParsedSection`/chunking nunca reconstruyen texto concatenando fragmentos — todo se expresa como rangos `(start_line, end_line)` sobre el texto original, y el contenido siempre se obtiene con un slice directo. Es deliberado: las citas dependen de números de línea exactos, y reconstruir texto a partir de fragmentos copiados es exactamente cómo aparecen los bugs de off-by-one.
- `search_vector` se implementó con `models.GeneratedField` (Postgres 12+/Django 5+), no con un trigger manual ni con un `.update()` en el pipeline — la columna se recalcula sola, adentro de la base, con la garantía de la propia base de datos de que nunca queda desincronizada de `content`.
- `config="english"` fijo para `search_vector`, aunque las notas reales sean español + inglés mezclado — ver "Deuda técnica" más arriba.
- **Bug real encontrado y corregido:** `LocalFolderConnector` pasaba `post.content` (con el front matter YAML ya extraído por `python-frontmatter`) en vez del texto completo del archivo. Eso desplazaba todos los números de línea calculados respecto al archivo real en disco — una cita a "línea 5" podía en realidad estar en la línea 9 si el archivo tenía 4 líneas de front matter arriba. Se corrigió pasando el texto completo (front matter incluido) al parser, y usando `frontmatter.loads()` solo para extraer metadata/título, nunca para recortar el contenido.
- La integración quedó en `sources/sync.py`, no como un paso separado: `sync_source()` ahora también dispara `ingestion.pipeline.process_document()` para altas/cambios y `purge_chunks_for_documents()` para bajas, usando el contenido que el conector ya trajo en memoria (sin releer el archivo).

---

#### Etapa 7 — Ingestion asíncrona con Celery ✅

**Objetivo:** que las sincronizaciones corran en background, con estado observable y sin pisarse entre sí.

**Tareas:**
1. Task `sync_source(source_id)` envolviendo el pipeline.
2. **Lock por fuente** vía Redis, para que dos syncs concurrentes de la misma `Source` no se pisen (hallazgo 10).
3. Modelo `SyncRun`: `source`, `started_at`, `finished_at`, `status`, contadores (added/updated/deleted), `error`.
4. Actualización de `Source.status` y `last_error`; reintentos con backoff.
5. Tests con `CELERY_TASK_ALWAYS_EAGER` + un test de contención del lock.

**Dependencias:** Etapa 6.
**Hecho cuando:** encolar un sync desde el shell lo ejecuta en el worker y produce un `SyncRun` con contadores correctos; el segundo sync concurrente sobre la misma fuente no arranca.

**Notas de la implementación real:**
- La lógica se separó en tres capas para que sea testeable sin depender de Celery: `sync_source()` (reconciliación pura, Etapa 5), `sync_source_with_tracking()` (agrega el `SyncRun` y el estado de `Source`, sigue sin saber nada de Celery) y `sync_source_task` (la task en sí, solo agrega el lock y `autoretry_for`/`retry_backoff`). El management command y la task comparten exactamente el mismo lock y la misma función de tracking — no hay dos caminos con comportamiento distinto según se dispare a mano o desde un worker.
- El lock usa `cache.add()` de Django (backend nativo de Redis, sin paquete extra desde Django 4) — es un `SET NX` atómico: solo el primero en pedirlo lo consigue.
- Redis quedó separado en dos índices de base de datos: `/0` para el broker de Celery, `/1` para el cache (el lock). No hacía falta por corrección (las claves no chocan), pero mantiene separados dos usos distintos del mismo Redis.
- **Gotcha real encontrado en Docker:** el volumen nombrado `backend_venv` (pensado para no pisar el entorno del contenedor con el bind-mount de código, ver Etapa 2) persiste *entre* reconstrucciones de imagen — así que había quedado con el `.venv` de antes de agregar `pgvector`/`tiktoken`/`python-frontmatter`, y el contenedor `backend` estaba `unhealthy` por `ModuleNotFoundError`. Hubo que borrar ese volumen a mano (`docker volume rm infra_backend_venv`) para que se repoblara desde la imagen nueva. Vale la pena recordarlo: **cualquier cambio de dependencias exige resetear ese volumen**, no alcanza con `--build`.
- Otro gotcha de Docker: el worker corre *adentro* del contenedor, que no tiene montado `/tmp` del host — solo `backend/` (como `/app`). Verificar contra una fuente `local_folder` desde el worker real requiere que la carpeta viva dentro de `backend/` (mapea a una ruta válida en ambos lados), no en cualquier lado del host.

---

#### Etapa 8 — Soporte de PDFs y storage

**Objetivo:** ingerir PDFs reutilizando el mismo pipeline, guardando el original para poder citarlo.

**Tareas:**
1. `PdfParser` con `pymupdf4llm` → **Markdown**, reutilizando el `HeadingChunker` existente (hallazgo/elección arriba).
2. Storage vía el setting `STORAGES` de Django (backend filesystem en `backend/storage/`) — **no** una interfaz propia (hallazgo 8).
3. `Document.original_file` (`FileField`) para el binario cacheado.
4. `LocalFolderConnector` extendido para detectar `.pdf` además de `.md`; selección de parser por extensión.
5. Metadata de página en los chunks de PDF, para que la cita apunte a página además de línea.
6. Tests con un PDF fixture chico.

**Dependencias:** Etapa 6 (puede ir en paralelo con la 7).
**Hecho cuando:** un PDF ingerido produce chunks con número de página; el original queda en storage; el mismo chunker sirvió a ambos formatos.

---

### Bloque C — Retrieval y chat

#### Etapa 9 — Embeddings

**Objetivo:** vectorizar chunks detrás de una interfaz intercambiable.

**Tareas:**
1. `rag/embeddings/base.py`: ABC `EmbeddingProvider` con `embed_documents()`, `embed_query()`, `dimensions`.
2. `VoyageEmbeddingProvider` con batching, retry y rate limiting. Modelo y dimensión desde settings.
3. `FakeEmbeddingProvider` determinístico para tests (sin llamadas de red en CI).
4. Paso de embedding integrado en el pipeline + task `backfill_embeddings` para chunks pendientes.
5. Tracking de costo por llamada de embedding.

**Dependencias:** Etapa 6.
**Hecho cuando:** todos los chunks tienen embedding no nulo; el CI corre sin API key gracias al provider fake; cambiar de provider es una línea de settings.

---

#### Etapa 10 — Módulo de retrieval

**Objetivo:** hybrid search real, aislado detrás de una interfaz única.

**Tareas** (en orden):
1. `rag/retrieval/base.py`: ABC `Retriever` con `search(query, workspace, filters, top_k) -> list[RetrievalResult]`.
2. `LexicalRetriever`: Postgres FTS (`websearch_to_tsquery` + `ts_rank_cd`) — la mitad léxica **definitiva**, no un placeholder (hallazgo 3).
3. `DenseRetriever`: `<=>` de pgvector sobre `Chunk.embedding`.
4. `HybridRetriever`: fusión por **Reciprocal Rank Fusion** de ambos.
5. `VoyageReranker` sobre el top-N fusionado → top-k final.
6. Filtros por metadata (source, fecha, tipo) aplicables en las tres estrategias.
7. Tests sobre un corpus fixture: casos donde léxico gana (nombre exacto de archivo), donde denso gana (paráfrasis), y que el híbrido cubre ambos.

**Dependencias:** Etapas 8 y 9.
**Hecho cuando:** una batería de ~15 preguntas conocidas sobre notas reales devuelve el chunk esperado en el top-3; cada estrategia es seleccionable por settings.

---

#### Etapa 11 — Chat con citas verificables

**Objetivo:** respuestas generadas cuyas citas están validadas contra el contexto real, con streaming.

**Tareas** (en orden):
1. `rag/llm/base.py`: ABC `LLMProvider` (`chat`, `stream`, `tools`) + `AnthropicProvider`. Modelo desde settings.
2. Modelos `Conversation`, `Message`, `Citation(message, chunk, quote, char_range)`. **`Message` lleva `latency_ms`, `input_tokens`, `output_tokens`, `cost`** — ver hallazgo 1.
3. Construcción de prompt con los chunks numerados y su `chunk_id`.
4. **Salida estructurada vía tool use**: el modelo devuelve `answer` + lista de `chunk_id` citados. El servidor **rechaza cualquier id que no estuviera en el contexto** antes de persistir (hallazgo 7).
5. Query rewriting con historial de conversación para preguntas de seguimiento.
6. Streaming SSE desde una vista async de Django (fuera de DRF), persistiendo el mensaje completo al cerrar el stream.
7. `manage.py ask "<question>"` para probar sin UI.
8. Tests con un `FakeLLMProvider`, incluyendo el caso de cita inválida rechazada.

**Dependencias:** Etapa 10.
**Hecho cuando:** `manage.py ask` responde con citas que apuntan a archivo + línea reales; una cita fabricada por el modelo nunca se persiste; latencia, tokens y costo quedan registrados en cada `Message`.

---

### Bloque D — API y frontend

#### Etapa 12 — Capa de API

**Objetivo:** exponer todo con un contrato tipado y autenticación.

**Tareas:**
1. DRF viewsets: `sources` (CRUD + acción `sync`), `documents` (read-only), `conversations`/`messages`.
2. Endpoint SSE de chat (vista async de la Etapa 11).
3. Auth por sesión con CSRF + `SameSite`; permisos filtrando por `Membership`.
4. `drf-spectacular` sirviendo `/api/schema/` y Swagger UI.
5. Paginación, throttling, manejo consistente de errores.
6. Tests de API por endpoint, incluyendo aislamiento entre workspaces.

**Dependencias:** Etapa 11.
**Hecho cuando:** el OpenAPI generado valida; un usuario no puede leer datos de otro workspace (test explícito); el flujo completo funciona vía HTTP.

---

#### Etapa 13 — Frontend Angular

**Objetivo:** portar el wireframe a una app real conectada al backend.

**Tareas** (en orden):
1. `.nvmrc` con **Node 24 LTS** (el 25.8.1 del host no está soportado por Angular 22 — ver bloqueantes); scaffolding con `npx @angular/cli@22 new`, standalone components + signals.
2. Generar el cliente TypeScript desde el OpenAPI de la Etapa 12 (script en `package.json`).
3. Portar el design system del wireframe (paleta papel/musgo/ámbar, tipografías) a tokens CSS. Textos en **inglés**; marca **Lorebase**.
4. Vista de chat: thread, composer, chips de citas clicables que abren el fragmento de origen. Consumo del SSE.
5. Sidebar de fuentes con estado real (polling o SSE del `SyncRun`), modal de alta de fuente con progreso real.
6. Nginx sirviendo el frontend y proxeando `/api` (mismo origen ⇒ las cookies de sesión funcionan).
7. Tests de componentes con Vitest.

**Dependencias:** Etapa 12.
**Hecho cuando:** `docker compose up` levanta el sistema entero; se puede agregar una carpeta local, verla sincronizar y preguntarle, con las citas abriendo el chunk correcto.

---

### Bloque E — Conectores adicionales

#### Etapa 14 — Conector de GitHub

**Objetivo:** demostrar que la abstracción plugin-first se sostiene con una fuente remota.

**Tareas:**
1. `GitHubConnector` con personal access token (no OAuth): repos configurables, filtros de path.
2. `fetch_documents()` sobre Markdown y READMEs; `external_id` = `repo@path`; detección de cambios por SHA de git en vez de hash de contenido.
3. Metadata: repo, branch, último commit, autor.
4. Manejo de rate limit de la API.
5. Tests con respuestas HTTP mockeadas.

**Dependencias:** Etapa 13.
**Hecho cuando:** un repo propio sincroniza y sus documentos son consultables desde el chat; **no hizo falta tocar el pipeline ni el retrieval** (esa es la prueba real de la arquitectura).

---

### Bloque F — Calidad, métricas y operación

#### Etapa 15 — Feedback y dashboard

**Objetivo:** cerrar el loop de calidad y hacer visibles costo y uso.

**Tareas:**
1. Modelo `Feedback(message, rating, comment)` — **sin** métricas, que ya viven en `Message` (hallazgo 1).
2. Endpoints de feedback + UI de 👍/👎 con comentario.
3. Endpoint de métricas agregadas: documentos, queries por día, costo mensual, latencia p50/p95, % de feedback positivo.
4. Vista Panel del wireframe conectada a datos reales.
5. Métrica propia del caso de uso: notas **nunca recuperadas** (señal de conocimiento huérfano, §3.2 del diseño).

**Dependencias:** Etapa 13.
**Hecho cuando:** el panel muestra números reales; el costo acumulado coincide con lo facturado por el proveedor.

---

#### Etapa 16 — Observabilidad y evaluación

**Objetivo:** poder medir si un cambio en el retrieval mejora o empeora, en vez de suponerlo.

**Tareas** (en orden):
1. OpenTelemetry sobre el pipeline y el camino de query.
2. Langfuse trazando cada llamada a LLM (prompt, contexto, respuesta, costo).
3. **Golden set**: ~30 preguntas sobre tus notas reales con el chunk esperado, versionado en el repo.
4. RAGAS: context precision/recall, faithfulness, answer relevancy.
5. `manage.py evaluate` produciendo un reporte comparable entre corridas.
6. Con el harness ya montado, **evaluar el retrieval agéntico** (§5 del diseño, hallazgo 6) contra el directo y decidir con datos.

**Dependencias:** Etapa 15.
**Hecho cuando:** `manage.py evaluate` da un score reproducible; un cambio en chunking o en pesos del RRF se puede comparar objetivamente contra el baseline.

---

#### Etapa 17 — Servidor MCP

**Objetivo:** exponer el retrieval de Lorebase como herramienta para Claude Desktop / Claude Code.

**Tareas:**
1. App `mcp_server` con el SDK oficial de MCP en Python.
2. Tools: `search_knowledge(query, filters)`, `get_document(id)`, `list_sources()`.
3. Autenticación por API key ligada a `Membership`.
4. Reutilización directa del `HybridRetriever` de la Etapa 10 — **sin lógica de retrieval duplicada**.
5. Servicio propio en Docker Compose; instrucciones de configuración en `docs/`.

**Dependencias:** Etapa 10 (funcionalmente); se agenda después de la 16 para exponer un retrieval ya evaluado.
**Hecho cuando:** Claude Code consulta tus notas vía MCP y devuelve respuestas citadas.

---

#### Etapa 18 — Hardening, deploy y documentación

**Objetivo:** dejar el proyecto presentable y operable.

**Tareas:**
1. Settings de producción: `DEBUG=False`, headers de seguridad, CORS, secretos por entorno.
2. `docker-compose.prod.yml` con gunicorn/uvicorn + nginx; healthchecks y logging estructurado.
3. Comandos de backup/restore de Postgres (incluyendo los vectores).
4. Rate limiting por usuario en los endpoints que cuestan dinero.
5. README final: arquitectura, decisiones y capturas. ADRs en `docs/adr/` para las decisiones no obvias (pgvector sobre Qdrant, FTS sobre OpenSearch, filesystem sobre S3).
6. `docs/` actualizado con el estado final de este roadmap.

**Dependencias:** Etapa 17.
**Hecho cuando:** el deploy de producción arranca limpio desde cero; un lector del README entiende la arquitectura sin leer código.

---

## Grafo de dependencias

```
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 ─┐
                          └→ 8 ─┴→ 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18
                          └→ 9 ──┘
```

Las Etapas 7, 8 y 9 pueden solaparse una vez cerrada la 6.

## Verificación end-to-end (a partir de la Etapa 13)

1. `docker compose -f infra/docker-compose.yml up --build` → 5 servicios healthy.
2. `make test` en `backend/` y `npm test` en `frontend/` → verde. CI verde en el PR.
3. Crear una fuente "local folder" apuntando a un directorio real de notas `.md` desde la UI.
4. Ver el `SyncRun` progresar en el sidebar hasta "ready"; verificar en el admin el conteo de `Document` y `Chunk`.
5. Preguntar algo cuya respuesta esté en una nota concreta → verificar que la cita apunta al archivo y líneas correctos, y que abrir el chip muestra ese texto.
6. Repetir el sync sin cambios → `SyncRun` con 0 added / 0 updated / 0 deleted.
7. Borrar una nota, resincronizar → el documento queda como tombstone y sus chunks desaparecen del retrieval.
8. `manage.py evaluate` → score sobre el golden set (Etapa 16).
9. Configurar el MCP en Claude Code y consultar las notas desde ahí (Etapa 17).

## Fuera de alcance

Fase 5 completa (ACLs por documento, API pública, webhooks, SDK), conectores de Notion/Confluence/Drive/Slack, migración a Qdrant/OpenSearch/Garage, y todo lo listado en §2.2 del diseño (multi-agent, voz, OCR, fine-tuning).
