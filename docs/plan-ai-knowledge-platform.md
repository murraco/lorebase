# AI Knowledge Platform — Documento de Planificación

**Estado:** Diseño cerrado para el MVP — listo para empezar a codear el Hito 1.
**Propósito:** Proyecto de portfolio personal para adquirir experiencia práctica en RAG, LLMs e ingeniería de aplicaciones de IA modernas.

## 0. Resumen para retomar el proyecto (leer primero)

Este documento es el plan completo de una plataforma de RAG empresarial (tipo "wiki inteligente"), adaptada primero a un caso de uso personal. Si estás retomando este proyecto en una conversación nueva (por ejemplo en Claude Code), esto es lo que ya está decidido — no hace falta volver a discutirlo salvo que algo cambie:

- **Caso de uso ancla:** "segundo cerebro personal" — indexar notas en Markdown plano (sin app específica), PDFs y repos de GitHub propios, para preguntar cosas como "¿qué escribí sobre X?" con respuestas citadas. Ver sección 3.
- **Objetivo dual:** el mismo sistema debe poder escalar más adelante a una wiki inteligente de equipo/empresa (documentación + Slack), gracias a que los conectores son plugins intercambiables. Ver sección 1.3.
- **Modelo de despliegue:** aplicación web (no de escritorio), self-hosteada con Docker Compose para uso personal hoy; el mismo backend se puede desplegar en un servidor compartido para uso en equipo mañana. Ver sección 4.0.
- **Stack decidido:** Django + DRF + Celery + Redis + **PostgreSQL con pgvector** (vectores) y **full-text search nativo** (búsqueda léxica) — sin Qdrant ni OpenSearch en el MVP. Storage en filesystem local (no MinIO — dejó de mantenerse en 2026 — ni S3 todavía). LLM: Anthropic directo. Embeddings: Voyage AI. Auth nativa de Django. Frontend: Angular. Ver sección 4.10 para la tabla completa y sus disparadores de migración (cuándo sí sumar Qdrant/OpenSearch/Garage/OAuth).
- **Modelo de datos:** ver sección 4.11 y el ERD — entidades `Workspace, User, Source, Document, Chunk, Conversation, Message, Citation, Feedback`. `Chunk` guarda su embedding directamente en Postgres. `Citation` vincula `Message ↔ Chunk` para que las citas sean verificables, no texto libre.
- **UI mínima:** ya hay un wireframe funcional construido — ver el archivo `demo-second-brain.html` (HTML/JS autocontenido, sin backend real) que acompaña a este plan. Sirve como punto de partida visual y de comportamiento (chat con citas, sidebar de fuentes, panel de métricas, flujo de "agregar fuente").
- **Roadmap y hitos:** Fase 1 ya está desglosada en 8 hitos concretos y accionables — ver sección 7.1. Es el punto de partida recomendado para empezar a codear.
- **Pendiente de decidir:** nada bloqueante para arrancar el Hito 1. Quedan como decisiones abiertas para más adelante: si migrar a Qdrant/OpenSearch, cuándo sumar Slack como conector (Fase 3), y los detalles finos de UI más allá del wireframe.

---

## 1. Visión

### 1.1 Problema

El conocimiento empresarial vive disperso en múltiples sistemas (GitHub, Jira, Confluence, Slack, Notion, Drive, SharePoint, wikis, APIs internas, bases de datos, PDFs, runbooks, ADRs). Encontrar información requiere saber de antemano **dónde buscar**, y los LLMs por sí solos no resuelven ese problema de fragmentación.

### 1.2 Objetivo

Construir una **plataforma** —no un chatbot— que permita a un LLM consultar información empresarial de forma segura, rápida y verificable, con fuentes citables en cada respuesta.

### 1.3 Objetivo dual: personal hoy, laboral a futuro

El MVP se construye y valida sobre el caso de uso personal (sección 3), pero la arquitectura debe quedar lista para un segundo escenario: una **wiki inteligente de equipo/empresa**, conectada a documentación interna y Slack, para resolver preguntas del tipo "¿qué se decidió sobre X?", "¿dónde está documentado este proceso?" o "¿cómo se hace tal tarea?".

Como los conectores ya están diseñados como plugins (sección 4.7 y `Connector` en el documento original), sumar Slack o un wiki corporativo más adelante es, en principio, agregar una implementación nueva de esa interfaz — no rediseñar el núcleo. Se agrega **Slack** como conector futuro en el roadmap (sección 7, Fase 3).

### 1.4 Por qué este proyecto destaca

La mayoría de los portfolios de IA generativa muestran un chat conectado a una base vectorial; es un patrón ya muy visto. Este proyecto se diferencia por:

- **Arquitectura plugin-first**: agregar un conector (Linear, SharePoint) o un proveedor de LLM/embeddings no requiere tocar el núcleo, solo implementar una interfaz y registrar el plugin.
- **Pipelines desacoplados** con versionado e indexación incremental.
- **Observabilidad y evaluación** integradas desde el diseño, no como añadido tardío.
- **Potencial de exponerse vía MCP** (Model Context Protocol) en una segunda etapa, convirtiendo la plataforma en infraestructura reutilizable por Claude Desktop, Cursor, VS Code u otros clientes compatibles.

Esto demuestra criterio de arquitectura de software, no solo conocimiento de IA.

---

## 2. Alcance

### 2.1 Dentro del MVP

| Área | Contenido |
|---|---|
| Workspace | Usuarios, fuentes de datos, modelos, permisos, conversaciones, evaluaciones |
| Conectores | GitHub, Notion, Confluence, Google Drive, carpeta local |
| Ingestion pipeline | Parser → Cleaning → Metadata → Chunking → Embeddings → Indexación |
| Versionado | hash, versión, `updated_at`, `deleted` — reindexado incremental, no total |
| Búsqueda | Hybrid search: BM25 + dense search + reranking |
| Chat | Cliente sobre el pipeline de retrieval, no el producto en sí |
| Citations | Fuente, página/archivo, línea, autor, fecha de última actualización — sin excepciones |
| Feedback | 👍/👎 + comentario, guardando query, contexto, respuesta, rating, latencia, tokens, costo |
| Dashboard | Costo, tokens, queries, tiempo, documentos, precisión, feedback |

### 2.2 Fuera del MVP (por ahora)

Multi-agent, voz, video, OCR avanzado, fine-tuning/training, browser automation, agentes autónomos, generación de código, workflow builders.

Estas capacidades quedan como posibles fases futuras, no como parte del alcance inicial.

---

## 3. Caso de uso personal — **Decidido: Segundo cerebro personal**

La plataforma está pensada para organizaciones, pero para que sea útil como proyecto individual (y no solo una demo vacía) se ancla a un caso de uso real de uso propio.

**Caso de uso elegido:** indexar el conocimiento personal disperso — notas en **Markdown plano organizadas en carpetas** (sin app específica), PDFs guardados y repos de GitHub propios — para poder preguntar cosas como *"¿qué escribí sobre X?"*, *"¿dónde definí esta idea?"* o *"¿en qué proyecto resolví un problema parecido?"*, con la respuesta citando la nota, archivo o commit exacto.

### 3.1 Fuentes de datos para este caso de uso

| Fuente | Contenido típico | Prioridad |
|---|---|---|
| Notas en Markdown plano (carpetas locales) | Apuntes, ideas, resúmenes de lectura | Alta — núcleo del "segundo cerebro" y primer conector a construir |
| PDFs guardados | Papers, libros, documentación técnica | Alta |
| Repos de GitHub propios | READMEs, decisiones de diseño, comentarios de commits | Media — conecta con la idea de "memoria de desarrollador" sin ser el eje central |
| Google Drive | Documentos sueltos, planillas de seguimiento | Baja, opcional |

Al no depender de una app específica (Obsidian, Notion), el conector de **"carpeta local"** cubre directamente la fuente principal sin necesidad de integrarse a una API externa ni manejar autenticación OAuth — esto simplifica bastante la Fase 1: es leer archivos `.md` del filesystem, parsear front-matter si existe, y detectar cambios por hash/mtime para el reindexado incremental.

### 3.2 Qué cambia en el producto por este caso de uso

- El **conector de "carpeta local"** es el primero a construir en la Fase 1 (antes incluso que GitHub, si se prioriza por impacto en el caso de uso personal): recorre un directorio, lee archivos `.md`, y detecta altas/bajas/cambios.
- Las **citations** deben poder señalar el archivo `.md` exacto y, si es posible, el encabezado o sección dentro de la nota, no solo "el documento" en general.
- El **chunking** necesita respetar la estructura de notas cortas (por encabezado o por nota completa si son breves), distinto al chunking de documentación larga tipo Confluence.
- Al no haber vault ni backlinks de una app específica, cualquier vínculo entre notas (por ejemplo referencias tipo `[[nota]]` si las usás) puede tratarse como metadata simple de grafo, sin depender de una API externa.
- El dashboard personal puede mostrar métricas más simples: documentos indexados, preguntas más frecuentes, notas menos "recuperadas" (posible señal de conocimiento huérfano).

---

## 4. Arquitectura

## 4.0 Modelo de despliegue y componentes de alto nivel

**Es una aplicación web**, no una app de escritorio nativa. Corre self-hosteada (Docker Compose) para el uso personal de hoy, y el mismo backend puede desplegarse en un servidor compartido para el escenario de equipo/empresa — sin reescribir la aplicación.

Componentes y responsabilidades:

| Componente | Responsabilidad |
|---|---|
| Cliente web | Interfaz de chat, gestión de fuentes, dashboard — sin lógica de negocio |
| Backend (Django) | API REST, orquesta el retrieval, decide qué necesita el LLM, expone `EmbeddingProvider`/`LLMProvider` |
| Workers (Celery) | Ejecutan los conectores, corren el pipeline de ingestion, no bloquean al usuario |
| Datos | Postgres (metadata, usuarios, chats, y vectores vía pgvector), Redis (cache/colas), filesystem local (archivos originales) |
| Fuentes externas | Sistemas de terceros consultados solo por los workers, nunca directamente por el cliente |

**Copia local vs referencia:** para fuentes remotas (GitHub, Notion, Confluence, Drive) la plataforma sincroniza y guarda una copia procesada del contenido (texto extraído, chunks, embeddings, metadata) — no alcanza con guardar solo la URL, porque el retrieval necesita embeddings precalculados. Para archivos locales (notas Markdown) no hay copia del original, pero sí se guarda el contenido procesado igual que con cualquier otra fuente. El binario original completo (por ejemplo un PDF) se cachea en storage cuando conviene poder mostrarlo o citarlo con precisión.

**Flujo de alta de una fuente:** el usuario elige tipo y ubicación/credenciales → se encola un job de sync en Celery → el conector hace `fetch_documents()` → pipeline de parser/chunking/embeddings solo sobre lo nuevo o cambiado → la fuente queda disponible en el chat. Todo el trabajo pesado ocurre en background, sin bloquear al usuario.

**Flujo de una consulta:** pregunta → retriever híbrido (BM25 + dense en pgvector) → reranker (top-k chunks) → LLM con esos chunks como contexto → respuesta con cada afirmación vinculada a su chunk de origen (archivo, línea).

---



Django + Django REST Framework, con Admin, Auth, ORM, Celery y Postgres. Se mantiene esta base por ser el stack que ya conocés.

### 4.2 Workers

Procesos separados (Celery, con Dramatiq o RQ como alternativas) encargados de embeddings, sync, parsing e indexing — desacoplados del ciclo request/response.

### 4.3 Cache

Redis para sesiones, prompts, respuestas y rate limiting.

### 4.4 Base de datos relacional

PostgreSQL: usuarios, chats, documentos, metadata, métricas.

### 4.5 Vector database

**pgvector** para arrancar (extensión de PostgreSQL — cero infraestructura nueva, aprovecha lo que ya conocés, y para el volumen de un caso de uso personal el rendimiento no es una limitación real). Migrar a **Qdrant** queda como paso natural si el proyecto escala hacia el caso de uso empresarial (más datos, filtros muy selectivos por tenant/canal/fecha) — viable sin rediseñar nada porque el acceso a la vector DB ya está aislado detrás del módulo de Retrieval. Alternativas: Weaviate, Milvus.

### 4.6 Storage

**Filesystem local** para el MVP (el volumen de un segundo cerebro personal no justifica un object store dedicado), detrás de una interfaz `StorageProvider` propia para no acoplarse.

⚠️ **MinIO Community Edition ya no es una opción recomendable** (actualizado 2026): pasó a licencia AGPL-3.0, dejó de distribuir binarios precompilados para la versión open source, y su repositorio fue archivado en febrero de 2026 sin mantenimiento activo ni parches de seguridad.

Si más adelante hace falta algo S3-compatible self-hosted (por ejemplo al escalar al caso de uso empresarial), **Garage** es la alternativa recomendada hoy: binario único en Go, licencia Apache 2.0, activamente mantenido, pensado para este perfil de escala pequeña. **S3** de AWS queda como opción gestionada si se prioriza no operar infraestructura propia, con el costo de transferencia saliente como principal desventaja a volumen alto.

### 4.7 Proveedores intercambiables

Ambos definidos como interfaces, para no acoplarse a un vendor:

```python
EmbeddingProvider
    embed()
    dimensions()
    batch()

LLMProvider
    chat()
    stream()
    tools()
    vision()
```

Implementaciones de embeddings: OpenAI, Gemini, Voyage, Cohere, BAAI, Nomic.
Implementaciones de LLM: OpenAI, Anthropic, Gemini, OpenRouter, Ollama, vLLM.

### 4.8 Retrieval

Módulo propio: dense, sparse, hybrid, filtros por metadata, reranker.

### 4.9 Parser

Separado por tipo de documento: PDF, Markdown, HTML, DOCX, CSV, JSON.

### 4.10 Stack tecnológico recomendado

| Capa | Recomendación | Alternativas |
|---|---|---|
| Backend | Django + DRF | FastAPI (para microservicios puntuales) |
| Workers | Celery | Dramatiq, RQ |
| Broker | Redis | RabbitMQ |
| Base relacional | PostgreSQL | MySQL |
| Vector DB | pgvector (arranque) → Qdrant (si escala) | Weaviate, Milvus |
| Object storage | Filesystem local (MVP) → Garage si se necesita S3-compatible | S3 |
| Búsqueda léxica | Postgres full-text search (tsvector) | OpenSearch si escala al caso empresarial |
| Embeddings | Voyage AI | OpenAI, Nomic, BAAI, Cohere |
| LLM | Anthropic directo (MVP) | OpenRouter si querés multi-proveedor fácil, Gemini, Ollama, vLLM |
| Observabilidad | OpenTelemetry + Langfuse | LangSmith, Helicone |
| Evaluación | RAGAS | DeepEval, Phoenix |
| Frontend | Angular (ya lo conocés) | React + Next.js, Vue, SvelteKit |
| Autenticación | Auth nativo de Django (MVP) | Django OAuth Toolkit / Authlib en Fase 5 |
| Contenedores | Docker Compose | Kubernetes (más adelante) |

---

## 4.11 Modelo de datos (borrador)

Entidades principales y relaciones:

```
Workspace 1--N User
Workspace 1--N Source
Source    1--N Document
Document  1--N Chunk
User      1--N Conversation
Conversation 1--N Message
Message   1--N Citation      (N--1 Chunk)
Message   1--N Feedback
```

Decisiones clave:

- `Chunk` guarda su `embedding` directamente en Postgres vía **pgvector** — no hay una base de datos separada que sincronizar.
- `Citation` es una tabla propia entre `Message` y `Chunk`, no un campo de texto libre: así cada afirmación de una respuesta queda vinculada a un chunk real, consultable y con su archivo/línea de origen.
- `Document` lleva `hash`, `version` y `deleted` para soportar el reindexado incremental (sección 2.1, versionado).
- `Feedback` guarda `rating`, `latency_ms` y `cost` junto al mensaje, para alimentar el dashboard sin joins costosos.

## 4.12 Diagramas de secuencia end-to-end

**Agregar una fuente:** Cliente → API (agrega fuente) → Worker (encola job) → Datos (parse/chunk/embed/guarda) → API (marca lista) → Cliente (actualiza UI). El trabajo pesado corre en el Worker sin bloquear al Cliente.

**Responder una consulta:** Cliente → API (pregunta) → Datos (retrieval híbrido) → API (top-k chunks) → LLM (prompt con contexto) → API (respuesta) → Cliente (respuesta + citas).

---



```
Pregunta del usuario
      ↓
LLM decide qué necesita buscar
      ↓
Retriever (hybrid search)
      ↓
Reranker
      ↓
LLM genera respuesta con contexto
      ↓
Respuesta + Citations obligatorias
```

Ninguna respuesta se acepta sin fuente verificable.

---

## 6. Casos de uso empresariales (referencia)

| Área | Pregunta ejemplo | Fuentes consultadas |
|---|---|---|
| Ingeniería | "¿Quién usa PaymentService?" | GitHub |
| DevOps | "¿Cómo desplegamos staging?" | Runbooks, Confluence |
| Producto | "¿Qué se decidió sobre onboarding?" | ADRs, Slack, Notion |
| Soporte | "¿Qué clientes tuvieron este error?" | Jira, Zendesk, Confluence |
| RRHH | "¿Cuál es la política de vacaciones?" | Handbook |

---

## 7. Roadmap por fases

| Fase | Contenido |
|---|---|
| **1** | Usuarios, Auth, Django Admin, **conector de carpeta local (Markdown)**, conector GitHub, soporte de PDFs, chat básico |
| **2** | pgvector, hybrid search, citations, streaming, feedback |
| **3** | Notion, Confluence, Google Drive, **Slack**, sync incremental |
| **4** | Evaluación, dashboard, métricas, costos, observabilidad |
| **5** | ACLs por documento, multi-workspace, API pública, webhooks, SDK |

### 7.1 Fase 1 — hitos concretos

**Hito 1 — Base del proyecto**
- Repositorio con estructura Django + `docker-compose.yml` (Postgres, Redis desde el principio)
- App `core` con modelos base: `Workspace`, `User` (aunque sea mono-usuario al inicio)
- Django Admin habilitado para inspeccionar datos durante el desarrollo

**Hito 2 — Modelo de datos de fuentes y documentos**
- Modelos `Source` (tipo, config, estado) y `Document` (`hash`, `version`, `updated_at`, `deleted`, `source_id`)
- Migraciones y admin para poder ver fuentes/documentos cargados manualmente

**Hito 3 — Conector de carpeta local**
- Implementar la interfaz `Connector` (`connect() / sync() / fetch_documents()`) para una carpeta de archivos `.md`
- Detección de altas/bajas/cambios por hash — no reprocesar lo que no cambió
- Comando de management (`manage.py sync_source <id>`) para probarlo sin UI todavía

**Hito 4 — Pipeline de ingestion (mínimo)**
- Parser de Markdown → texto limpio
- Chunking simple (por nota completa o por encabezado)
- Guardar chunks en Postgres con su metadata (`source`, `path`, `line_range`)
- *(Embeddings y vector DB quedan para la Fase 2 — en la Fase 1 el chunk existe pero todavía no es buscable semánticamente)*

**Hito 5 — Soporte de PDFs**
- Parser de PDF (extracción de texto) reutilizando el mismo pipeline de chunking
- Cache del PDF original en storage local (antecede a MinIO/S3, que llega en fases posteriores)

**Hito 6 — Conector de GitHub**
- Autenticación con token personal (no OAuth completo todavía)
- `fetch_documents()` sobre READMEs y archivos Markdown de uno o más repos propios

**Hito 7 — Chat básico**
- Endpoint que recibe una pregunta y hace *keyword search* simple sobre los chunks guardados (placeholder de retrieval real, que llega en Fase 2)
- Integración con `LLMProvider` (implementación inicial: Anthropic) para generar la respuesta con los chunks encontrados como contexto
- Citations obligatorias desde el día uno: cada respuesta debe indicar `archivo` y `línea` de origen, aunque el retrieval todavía sea simple

**Hito 8 — Interfaz mínima**
- Conectar el wireframe/demo ya construido a los endpoints reales
- Vista de chat funcional + sidebar de fuentes con estado real (no simulado)

Al cerrar estos 8 hitos, el sistema ya es usable de punta a punta con tus notas y PDFs, aunque el retrieval sea todavía básico — eso es intencional: Fase 2 reemplaza el keyword search por hybrid search real sin tocar el resto del sistema, gracias a que retrieval ya está aislado como módulo propio (sección 4.0).

---

## 8. Próximos pasos

1. ~~Diseñar la interfaz de usuario mínima~~ — wireframe y demo interactivo ya construidos.
2. ~~Dividir la Fase 1 en hitos concretos~~ — ver sección 7.1.
3. ~~Decidir vector DB~~ — arrancamos con **pgvector** para el MVP (aprovechando lo que ya conocés), y eventualmente evaluaremos si conviene migrar a **Qdrant** si el caso de uso lo justifica (ver comparación en la conversación). `EmbeddingProvider`/retrieval ya están aislados como módulo propio, así que la migración no rediseña nada.
4. Cerrar el resto del stack de tecnologías (sección 4.10) al mismo tiempo que se detalla la arquitectura de cada componente.
5. Configurar el repositorio base siguiendo el Hito 1 de la Fase 1.

---

*Este documento es la base de trabajo inicial. Se irá refinando a medida que avancemos con la arquitectura, los hitos y el diseño de la interfaz.*
