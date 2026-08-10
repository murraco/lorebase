# Lorebase como preparación para una entrevista de Software Engineer (Applied AI)

Este documento consolida todo lo que se explicó y se aprendió construyendo
Lorebase, organizado por **concepto** en vez de por etapa del roadmap —
pensado para repasar antes de una entrevista, no para reconstruir la
historia del proyecto (eso ya lo hace `docs/roadmap.md`).

Cada sección sigue la misma estructura: **qué es**, **por qué importa**,
**cómo lo resolvió Lorebase** (con archivos reales, no genérico), y cuando
hubo un bug real en el camino, **qué se rompió y cómo se encontró** — esas
historias son las que mejor responden "contame de un bug difícil que
resolviste" en una entrevista real. Cierra con unas preguntas tipo por
sección para practicar recuperar la info de memoria, no solo reconocerla
leyendo.

Reemplaza a `docs/learning-notes.md` (borrador acumulativo durante la
construcción, ahora consolidado acá) y es la referencia primero cuando se
retome algo de este proyecto para estudiar.

---

## Índice

0. [Cómo son las entrevistas de Applied AI Engineer](#0-cómo-son-las-entrevistas-de-applied-ai-engineer)
1. [RAG: la idea central y por qué las citas son el punto](#1-rag-la-idea-central-y-por-qué-las-citas-son-el-punto)
2. [Ingestion y chunking](#2-ingestion-y-chunking)
3. [Embeddings](#3-embeddings)
4. [Búsqueda léxica (BM25 / Postgres FTS)](#4-búsqueda-léxica-bm25--postgres-fts)
5. [Búsqueda densa (vector search)](#5-búsqueda-densa-vector-search)
6. [Hybrid search y Reciprocal Rank Fusion](#6-hybrid-search-y-reciprocal-rank-fusion)
7. [Reranking](#7-reranking)
8. [Citas verificables vía structured tool-use](#8-citas-verificables-vía-structured-tool-use)
9. [Conversación multi-turno sin estado](#9-conversación-multi-turno-sin-estado)
10. [Retrieval directo vs. agéntico](#10-retrieval-directo-vs-agéntico)
11. [Evaluación de sistemas RAG (RAGAS)](#11-evaluación-de-sistemas-rag-ragas)
12. [Observabilidad para aplicaciones de LLM](#12-observabilidad-para-aplicaciones-de-llm)
13. [Model Context Protocol (MCP)](#13-model-context-protocol-mcp)
14. [Resiliencia contra APIs externas de IA](#14-resiliencia-contra-apis-externas-de-ia)
15. [Auth, multi-tenancy y rate limiting](#15-auth-multi-tenancy-y-rate-limiting)
16. [Pensar en trade-offs: las ADRs como práctica](#16-pensar-en-trade-offs-las-adrs-como-práctica)
17. [Temas que Lorebase no cubre, pero conviene saber](#17-temas-que-lorebase-no-cubre-pero-conviene-saber)
18. [Mapa práctico del ecosistema](#18-mapa-práctico-del-ecosistema)

---

## 0. Cómo son las entrevistas de Applied AI Engineer

Lo que sigue es un patrón general observado en la industria, no un
proceso verificado de una empresa puntual — cada compañía arma el suyo,
pero estas piezas se repiten lo suficiente como para prepararse por
default. Tomalo como una guía de qué tipo de práctica priorizar, no como
un libreto exacto.

**Rondas típicas:**

1. **Screening con recruiter o hiring manager.** No técnico en
   profundidad — encaje de rol, expectativas, a veces un resumen a alto
   nivel de proyectos. Acá conviene poder resumir Lorebase en 30 segundos
   ("un sistema RAG self-hosted que indexa mis notas y repos, con citas
   verificadas server-side y una evaluación medida contra un golden set")
   antes de entrar en detalle.

2. **Ronda conceptual / técnica en vivo.** Te piden explicar conceptos en
   voz alta — a veces sobre un documento compartido, a veces solo
   hablando: "explicame qué es hybrid search", "¿cómo evaluás la calidad
   de un sistema RAG?", "¿qué es un embedding y por qué serviría acá?".
   No están buscando la definición de diccionario — están viendo si
   entendés el *por qué*, si podés dar un ejemplo concreto, y si sabés
   nombrar el trade-off de lo que proponés. Este documento está pensado
   sobre todo para esta ronda.

3. **Coding / live-coding o take-home.** Formatos comunes: implementar
   una pieza chica de un pipeline RAG (un chunker, una función de
   retrieval, armar un prompt con contexto numerado), debuggear un
   pipeline que existe y anda mal (por ejemplo "esta búsqueda no
   encuentra lo obvio, ¿por qué?" — la sección 2/4/5 de este documento
   son literalmente ejemplos reales de ese ejercicio), o un take-home más
   largo armando un mini-RAG de punta a punta contra un corpus dado.
   A veces piden escribir un harness de evaluación chico en vez de (o
   además de) el pipeline en sí.

4. **Ronda de system design.** La más específica del rol: "diseñá un
   sistema de Q&A sobre la documentación interna de la empresa" o
   "diseñá un asistente que responda preguntas sobre nuestro código".
   Se espera que cubras, en algún orden: cómo se ingestan los datos y con
   qué frecuencia, estrategia de chunking, qué embeddings usar y por qué,
   qué base de datos vectorial (o si hace falta una dedicada), estrategia
   de retrieval (¿denso solo? ¿híbrido? ¿reranking?), cómo se arma el
   prompt y cómo se garantizan citas verificables, cómo evaluarías la
   calidad, cómo lo observarías en producción, costo/latencia esperados,
   y qué pasa si el corpus tiene datos de distinto nivel de acceso
   (seguridad/permisos). La sección 18 de este documento está armada
   específicamente para tener respuesta a cada una de esas piezas.

5. **Deep-dive de portfolio/proyecto.** Contás un proyecto real, y te
   empujan sobre las decisiones: "¿por qué pgvector y no Qdrant acá?",
   "¿qué harías distinto si esto tuviera que soportar 1000 usuarios?".
   Lorebase — y particularmente las 7 ADRs (sección 16) — es material
   armado exactamente para esta ronda: cada decisión ya tiene su
   justificación *y* su condición de migración explícita, que es
   precisamente la forma de respuesta que un entrevistador senior busca.

6. **Ronda de comportamiento (behavioral).** Suele incluir una variante
   IA-específica de las preguntas clásicas: "contame de una vez que un
   sistema de IA dio una respuesta mal y cómo lo manejaste" — la sección
   14 (resiliencia) y los bugs reales de las secciones 2/3/9/11 son
   material directo para esto.

**Qué evalúan realmente, más allá del contenido puntual:** si podés
razonar sobre trade-offs en vivo (no solo recitar una arquitectura de
memoria), si distinguís una decisión bien fundada de una moda ("usé
Pinecone porque es lo que usa todo el mundo" responde peor que "empecé
con pgvector porque no justificaba infra nueva a esta escala, y sé
exactamente cuándo migraría"), y si tenés vocabulario preciso del campo
sin sonar a que estás repitiendo buzzwords sin entenderlos — la sección
18 de acá abajo existe específicamente para cerrar esa brecha de
vocabulario/panorama.

---

## 1. RAG: la idea central y por qué las citas son el punto

**Qué es.** RAG (Retrieval-Augmented Generation) le da a un LLM contexto
recuperado de una fuente externa *antes* de que genere una respuesta, en
vez de depender solo de lo que memorizó en entrenamiento. El paper
original (Lewis et al., 2020, Facebook AI Research) lo propuso como una
forma de combinar la fluidez de un modelo generativo con la precisión
factual de un sistema de recuperación — no reemplazar uno con el otro,
sino encadenarlos: un componente *retriever* que busca en una base de
conocimiento externa, y un componente *generator* que produce texto
condicionado en lo que el retriever trajo. Resuelve dos problemas a la
vez: el modelo no sabe nada de tus datos privados (nunca los vio en
entrenamiento), y un LLM sin contexto real alucina con la misma confianza
que cuando dice la verdad — no tiene manera interna de distinguir "sé
esto" de "estoy completando un patrón que suena plausible".

**Por qué importa.** La mayoría de los demos de RAG se quedan en "el chat
responde algo relacionado" — el salto real está en poder **verificar** que
la respuesta viene de donde dice que viene, no solo confiar en que "suena
bien". Ahí es donde vive la diferencia entre un demo y un sistema que
alguien usaría para algo que importa. Un sistema RAG bien construido tiene
tres puntos de falla independientes, y hay que poder aislar cuál falló: el
retriever no trajo lo necesario (falla de *recall*), trajo cosas
irrelevantes que confunden al generador (falla de *precision*), o trajo
lo correcto pero el generador lo ignoró o lo malinterpretó (falla de
*faithfulness* — sección 11). Diagnosticar "la respuesta está mal" sin
poder separar estas tres causas es adivinar, no debuggear.

**Cómo lo resolvió Lorebase.** Cada respuesta pasa por: reescritura de
query (si hay historial) → retrieval híbrido → reranking → LLM con los
chunks numerados como contexto → **validación server-side de las citas**
antes de guardar nada (sección 8). El pipeline entero vive en
`rag/chat/service.py` (`ask()`), y ninguna capa de abajo (retrieval, LLM)
sabe nada de las de arriba — cada una es una interfaz intercambiable
(`Retriever`, `LLMProvider`, `EmbeddingProvider`).

**Preguntas tipo:**
- ¿Qué problema resuelve RAG que fine-tuning no resuelve (y viceversa)?
- ¿Por qué "el LLM cita sus fuentes" no es lo mismo que "las fuentes citadas son reales"?

---

## 2. Ingestion y chunking

**Qué es.** Convertir documentos crudos (Markdown, texto plano, PDF) en
fragmentos ("chunks") lo bastante chicos para embeder y pasarle a un LLM,
pero lo bastante grandes para conservar sentido.

**Por qué importa.** El chunking es, en la práctica, donde más falla un
sistema RAG — no en el modelo. Un chunk mal cortado (a la mitad de una
idea, sin su encabezado) hace que el retrieval encuentre texto que no
sirve, aunque el embedding y el reranker sean perfectos. Hay una tensión
de fondo que no tiene una respuesta única: chunks chicos dan embeddings
más "enfocados" (un vector que representa una sola idea, no un promedio
diluido de varias) y permiten citas más precisas, pero fragmentan
contexto — una idea que necesita el párrafo de arriba para tener sentido
puede quedar aislada. Chunks grandes conservan más contexto pero diluyen
el embedding (mezclan varios temas en un solo vector, lo que empeora la
precisión del matching) y hacen la cita menos específica. No existe un
tamaño "correcto" en abstracto — depende de la estructura real del
contenido, que es exactamente por qué cortar por encabezado (una unidad
de sentido que el propio autor ya delimitó) es mejor punto de partida que
un tamaño fijo de tokens.

**Cómo lo resolvió Lorebase.** `HeadingChunker` (`ingestion/chunking/`)
corta por encabezado Markdown, fusiona secciones cortas y parte las
largas por presupuesto de tokens. Cada chunk guarda `heading_path`,
`start_line`/`end_line` — **nunca reconstruidos concatenando texto**,
siempre un slice directo del archivo original, porque las citas dependen
de que esos números sean exactos y reconstruir texto a partir de
fragmentos es exactamente cómo aparecen bugs de off-by-one.

**Dos bugs reales, dos lecciones distintas:**

1. **Off-by-line por front matter.** `LocalFolderConnector` le pasaba al
   parser el contenido *sin* el front matter YAML (ya extraído por la
   librería `python-frontmatter`) — así que todos los números de línea
   quedaban corridos respecto al archivo real en disco. Una cita a "línea
   5" podía estar en realidad en la línea 9. Fix: pasar el texto completo
   (con front matter) al parser, y usar la librería de front matter *solo*
   para metadata, nunca para recortar contenido. **Lección:** cualquier
   transformación de texto antes de calcular offsets es un bug de citas
   esperando pasar.

2. **`heading_path` calculado, guardado, y leído por nadie.** Ni el
   embedding ni el prompt al LLM usaban `heading_path` — solo
   `chunk.content`. Como `HeadingChunker` corta cualquier sección larga en
   pedazos, y **solo el primer pedazo contiene el encabezado**, un archivo
   tipo diario (miles de líneas, sin headings, una fecha suelta por
   entrada) terminaba con la mayoría de sus chunks *sin la fecha en
   ningún lugar que el sistema realmente usara* — preguntar por una fecha
   puntual no tenía forma de funcionar. Fix: una propiedad derivada
   `Chunk.content_with_heading` (breadcrumb + contenido) usada por
   embedding y prompt — pero `content` se deja intacto a propósito, porque
   ese es el que mantiene `start_line`/`end_line` exactos. **Lección:**
   un dato que se calcula pero no se conecta a ningún consumidor real es
   peor que no calcularlo — parece que el problema está resuelto y no lo
   está.

**Chunking configurable, no hardcodeado:** para archivos sin headings pero
con un patrón repetido (fechas de un diario), `Source.config` acepta un
`section_boundary_pattern` (regex) que trata cualquier línea que matchee
como límite de sección informal — generalización, no un caso especial
hardcodeado para "diarios".

**Preguntas tipo:**
- ¿Por qué cortar por encabezado en vez de por cantidad fija de caracteres/tokens?
- Si un chunk pierde su contexto de sección al partirse, ¿qué estrategias existen para no perderlo?

---

## 3. Embeddings

**Qué es.** Un modelo que convierte texto en un vector de números reales
tal que textos con significado similar quedan geométricamente cerca —
la base de la búsqueda "semántica" (a diferencia de la búsqueda por
palabra exacta).

**Cómo se entrena, a grandes rasgos.** Los modelos de embedding modernos
(E5, BGE, Voyage, los de OpenAI) son transformers — la misma arquitectura
que un LLM — pero entrenados con un objetivo distinto: **aprendizaje
contrastivo**. En vez de predecir la siguiente palabra, se les entrena con
pares (o tríos) de textos: uno de referencia (anchor), uno que debería
quedar cerca (positivo — una paráfrasis, una pregunta y su respuesta) y
uno o más que deberían quedar lejos (negativos). El loss empuja al modelo
a acercar geométricamente los positivos y alejar los negativos. El
resultado no es "un LLM al que le preguntás y te da un vector" — es un
modelo optimizado específicamente para que la distancia geométrica en su
espacio de salida refleje similitud semántica. Por eso un modelo de
embedding no sirve para generar texto, y un LLM generativo (sin
fine-tuning específico) no da buenos embeddings de forma directa: cada uno
está optimizado para un objetivo distinto.

**Por qué importa.** Es lo que le permite a un sistema encontrar "cómo
funciona la reconexión automática" cuando el chunk real dice "retry con
backoff exponencial" — sin que ninguna palabra coincida literalmente.

**Cómo lo resolvió Lorebase.** `EmbeddingProvider` es una interfaz con dos
implementaciones intercambiables por settings: `VoyageEmbeddingProvider`
(API, `voyage-4`, 1024 dimensiones) y `LocalEmbeddingProvider`
(`intfloat/multilingual-e5-large`, corre en el propio proceso vía
`sentence-transformers`, sin API key ni rate limit). Un tercer
`FakeEmbeddingProvider` (hash SHA-256 determinístico, sin relación
semántica real) existe solo para que CI corra sin red ni costo.

**Detalle técnico real: embeddings asimétricos.** E5 y Voyage tratan
distinto un *query* de una *pregunta* que un *passage* de un documento —
E5 con un prefijo explícito (`"query: "` / `"passage: "`), Voyage con un
prompt interno (`input_type`). La interfaz `EmbeddingProvider` ya reflejaba
esa asimetría desde el diseño (`embed_query()` vs. `embed_documents()`),
antes incluso de implementar el segundo provider — la interfaz estaba
pensada para el caso general, no ajustada después a un proveedor puntual.

**Detalle real: la dimensión queda fija para siempre.** pgvector fija la
dimensión del vector al crear la columna — cambiarla en una base ya
poblada significa migración *y* re-embeder todo. Por eso `e5-large`
(1024 dimensiones) se eligió sobre `e5-base`/`e5-small` de la misma
familia: no por ser mejor en abstracto, sino por ser el único que calza
exacto con la dimensión ya fijada, evitando la migración.

**El bug más caro de todo el proyecto:** `EMBEDDING_PROVIDER=fake` quedó
activo en el entorno real (no solo en tests) durante una sesión entera de
debugging — así que **todo el retrieval denso corrió sobre vectores
pseudo-aleatorios** sin que nadie lo notara hasta revisar el `.env` por
otro motivo. El diagnóstico "los embeddings no distinguen bien entradas
similares", hecho mientras este bug estaba activo, quedó confirmado como
inevitable con vectores random — no una conclusión válida sobre la
calidad real de Voyage. **Lección, la más transferible de todo el
proyecto:** medir sobre una configuración rota da una conclusión que
suena razonable y es completamente falsa. Antes de confiar en una
medición, verificar que lo que se está midiendo es lo que se cree que es.

**Preguntas tipo:**
- ¿Qué es un embedding asimétrico y por qué importa para retrieval (a diferencia de, por ejemplo, clustering)?
- ¿Qué se pierde al mover embeddings de una API a un modelo local, y qué se gana?

---

## 4. Búsqueda léxica (BM25 / Postgres FTS)

**Qué es.** Búsqueda por coincidencia de palabras (con variantes:
stemming, stopwords), no por significado — lo que la mayoría de los
motores de búsqueda "clásicos" hacían antes de que existieran embeddings.
**BM25** (Best Matching 25) es el algoritmo de scoring detrás de la
mayoría de estos sistemas (Elasticsearch, OpenSearch, y conceptualmente
`ts_rank_cd` de Postgres): puntúa un documento más alto cuanto más
seguido aparece un término de la query en él (frecuencia del término),
pero con retornos decrecientes (la palabra 10 no suma tanto como la
segunda) y penalizando documentos más largos (para que un documento largo
no gane solo por tener más texto donde aparecer). Términos raros en el
corpus completo (baja frecuencia global) pesan más que términos comunes —
la misma intuición que "stopwords" pero de forma continua en vez de una
lista fija de palabras a ignorar.

**Por qué importa.** Los embeddings pierden contra una búsqueda literal en
casos muy concretos: un nombre de archivo exacto, un identificador
(`ENG-2277`), una fecha ISO. Un sistema que confía solo en denso falla
justo en las preguntas donde el usuario ya sabe exactamente qué palabra
busca.

**Cómo lo resolvió Lorebase.** `LexicalRetriever` usa `tsvector` +
`websearch_to_tsquery` + `ts_rank_cd` (Postgres FTS nativo) — no
Elasticsearch/OpenSearch (ver ADR 0002: se construyó como la mitad léxica
*definitiva* del hybrid search desde el primer código de retrieval, no
como un placeholder a reemplazar). `search_vector` es un
`models.GeneratedField` (Postgres 12+/Django 5+): la base de datos lo
recalcula sola en cada write, con la garantía de la propia base de que
nunca queda desincronizado del `content` — no un trigger manual, no un
`.update()` aparte en el pipeline que alguien podría olvidar llamar.

**Limitación real, medida en el corpus:** `websearch_to_tsquery` usa
semántica **AND** — todos los términos de la query tienen que matchear.
Con contenido en inglés y una pregunta en español, **cero** de las
palabras en español matchean nunca, así que lexical devuelve 0 resultados
— no solo para fechas, para cualquier pregunta en un idioma distinto al
del contenido. Y hasta en el mismo idioma, una pregunta en lenguaje
natural sobre una fecha (`"What did I do on July 21 2025?"`) da 0
resultados porque el contenido dice `2025-07-21`, no "July" — la fecha
ISO sola como query sí acierta. **Lección:** la mitad léxica sirve para
búsquedas literales, no para preguntas en lenguaje natural — por eso hace
falta la mitad densa, no como redundancia sino como complemento real.

**Preguntas tipo:**
- ¿Por qué `tsvector`/BM25 puede ganarle a un embedding en casos concretos?
- ¿Qué significa que `websearch_to_tsquery` use AND, y qué tipo de pregunta rompe con eso?

---

## 5. Búsqueda densa (vector search)

**Qué es.** Buscar los vectores más cercanos al vector de la pregunta —
"cercano" en el espacio de embeddings, no coincidencia de palabras.

**Distancia coseno vs. producto punto vs. distancia euclídea:** las tres
son válidas y aparecen en distintos sistemas. Coseno mide el *ángulo*
entre dos vectores, ignorando su magnitud — dos vectores que apuntan en
la misma dirección son "iguales" para coseno aunque uno sea más largo que
el otro. Producto punto (dot product) sí pesa la magnitud — más rápido de
calcular, y equivalente a coseno si los vectores ya están normalizados a
longitud 1 (lo que muchos modelos de embedding hacen por diseño,
precisamente para poder usar dot product como atajo). Euclídea mide
distancia "en línea recta" en el espacio — más intuitiva geométricamente,
pero más sensible a la magnitud que coseno. En la práctica, para
embeddings de texto normalizados, coseno y dot product dan el mismo
ranking — la elección suele ser de conveniencia/performance, no de
calidad.

**Qué es HNSW, mecánicamente:** Hierarchical Navigable Small World —
un índice aproximado (ANN, *approximate nearest neighbor*), no exacto.
Construye varias capas de un grafo donde cada nodo es un vector; la capa
superior tiene pocos nodos con conexiones "largas" (saltos grandes por el
espacio), y cada capa inferior tiene más nodos con conexiones más
"cortas" — como un mapa de rutas con autopistas arriba y calles locales
abajo. Buscar significa entrar por la capa superior, moverse hacia el
vector más cercano disponible, y bajar de capa progresivamente,
refinando. Es *aproximado* porque no garantiza encontrar el vecino más
cercano real en el 100% de los casos — a cambio, es sublineal en tiempo
de búsqueda (no compara contra todos los vectores), lo que lo hace viable
a millones de vectores donde una búsqueda exacta (fuerza bruta) sería
demasiado lenta.

**Cómo lo resolvió Lorebase.** `DenseRetriever` usa el operador `<=>`
(distancia coseno) de pgvector sobre `Chunk.embedding`, con un índice HNSW.
**pgvector en vez de un vector DB dedicado (Qdrant)** — ver ADR 0001: cero
infraestructura nueva, `Chunk` y su embedding se escriben en la misma
transacción (no pueden desincronizarse por construcción), y a la escala de
un caso de uso personal el rendimiento no es una limitación real. El
`Retriever` queda detrás de una interfaz, así que migrar a un vector DB
dedicado más adelante es una implementación nueva, no un rediseño.

**Limitación real, medida:** denso tampoco alcanza solo para preguntas de
fecha — la fecha correcta ni aparecía en el top-10 por similitud pura,
porque cientos de entradas de un diario técnico son semánticamente
parecidas entre sí (todas son bullets tipo ticket), y nada en el embedding
de la pregunta las distingue por fecha específica.

**Preguntas tipo:**
- ¿Qué es HNSW y qué trade-off hace (velocidad/memoria) frente a una búsqueda exacta?
- ¿Cuándo pgvector deja de alcanzar y hace falta un vector DB dedicado?

---

## 6. Hybrid search y Reciprocal Rank Fusion

**Qué es.** Combinar los rankings de lexical y denso en uno solo — cada
mitad falla en casos distintos (sección 4-5), así que combinarlas cubre
más que cualquiera de las dos sola.

**El problema de fondo:** los scores de las dos mitades viven en escalas
incomparables — `ts_rank_cd` es un valor sin cota (depende de frecuencia
de términos), similitud coseno está acotada a `[-1, 1]`. Sumarlos
directamente (`w1*score_lex + w2*score_dense`) exige normalizar dos
escalas que no son comparables entre sí, y elegir pesos de entrada.

**Cómo lo resolvió Lorebase (ADR 0006):** Reciprocal Rank Fusion —
`score(chunk) = Σ 1/(RRF_K + rank_en_esa_lista)`, sumado sobre cada lista
en la que el chunk aparece. **Usa solo la posición en el ranking, ignora
el score crudo por completo.** `RRF_K = 60`, la constante del paper
original (Cormack, Clarke & Grossman, SIGIR 2009, verificado contra el
paper, no citado de memoria) — hoy un default de facto en la industria.

**Trade-off honesto:** RRF tira info real a la basura — un chunk que ganó
por poco y uno que dominó contribuyen igual si terminan en el mismo rank.
No hay fusión aprendida entre las dos señales. La ganancia a cambio: cero
normalización, cero pesos que tunear, y agregar una tercera señal de
ranking más adelante es sumar un término más, no rediseñar el esquema de
scoring.

**Preguntas tipo:**
- ¿Por qué RRF usa solo el rank y no el score crudo?
- ¿Qué información se pierde al usar RRF en vez de una fusión ponderada, y cuándo importaría?

---

## 7. Reranking

**Qué es.** Un segundo modelo, más caro pero más preciso, que re-ordena el
top-N de la fusión antes de pasarle el top-k final al LLM.

**Por qué un segundo modelo, no uno solo.** Un embedding (bi-encoder)
codifica pregunta y documento *por separado* — rápido, escala a millones
de documentos, pero no puede razonar sobre la interacción específica entre
ambos. Un cross-encoder (reranker) concatena pregunta y documento en un
solo input (típicamente `[CLS] pregunta [SEP] documento [SEP]`) y hace
**una sola pasada conjunta** por el transformer — cada token de la
pregunta puede "atender" directamente a cada token del documento (y
viceversa) en las capas de atención, lo que le permite captar interacción
fina entre ambos que dos vectores calculados por separado no pueden
capturar. La salida no es un vector, es un único score de relevancia
(0 a 1) para ese par puntual. Es mucho más preciso, pero no se puede
precalcular ni indexar — hay que correrlo en el momento, para cada par
pregunta-documento, lo que lo hace demasiado lento para correr sobre todo
el corpus. La arquitectura en dos etapas (bi-encoder para recall amplio y
barato, cross-encoder para precisión final sobre un conjunto chico) es un
patrón estándar de sistemas de retrieval en producción, no una
particularidad de este proyecto.

**Cómo lo resolvió Lorebase.** `RerankingRetriever` envuelve *cualquier*
`Retriever` (patrón decorator/composición, no herencia) — el mismo patrón
que `DateAwareRetriever` (sección 8/14). Dos implementaciones
intercambiables: `VoyageReranker` (API) y `LocalReranker` (cross-encoder
vía `sentence-transformers`, sin red ni rate limit).

**Elección de modelo local, con dos intentos reales, no una elección
directa:**
- Primer intento (`jinaai/jina-reranker-v2-base-multilingual`) descartado
  por dos `ImportError` reales encadenados: el modelo usa
  `trust_remote_code=True` (código custom del repo del modelo, no de la
  librería `transformers`), y ese código dependía de una función interna
  de `transformers` que una versión más nueva de la librería ya no
  exponía. **Riesgo real de `trust_remote_code`:** el código vive fuera de
  la librería, así que puede romperse contra versiones nuevas sin ningún
  pin coordinado entre ambos repos.
- Elección final: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` —
  arquitectura estándar (sin `trust_remote_code`), multilingüe (14
  idiomas), más chico (~100M parámetros vs. 278M), licencia Apache 2.0
  (sin la restricción no-comercial del otro modelo).

**Preguntas tipo:**
- ¿Por qué no usar un cross-encoder para el retrieval completo, si es más preciso?
- ¿Qué riesgo concreto trae `trust_remote_code=True` más allá de seguridad?

---

## 8. Citas verificables vía structured tool-use

**Qué es.** El mecanismo (ADR 0004) que hace que una cita sea una
garantía y no una promesa del prompt: el LLM no escribe texto con citas
inline — llama a una tool estructurada que devuelve `answer` +
`cited_chunk_ids`. El servidor **intersecta** esa lista contra
`chunks_by_id`, el conjunto exacto de chunks que de verdad se mandaron
como contexto en ese turno. Cualquier id que no esté ahí — inventado, de
un turno anterior, un typo — se descarta en silencio, nunca se persiste
como `Citation`.

**Por qué importa tanto en una entrevista.** Es la respuesta concreta a
"¿cómo evitás que el modelo alucine una fuente?" — la respuesta genérica
("le pedimos citas en el prompt") no tiene mecanismo de verificación; esta
sí, y es barata (un chequeo de membership en un dict, no una llamada más
al LLM).

**Cómo lo resolvió Lorebase.** `rag/chat/service.py`: los ids sobrevivientes
se reordenan por posición de retrieval real (no por el orden en que el
modelo los mencionó), así que el número que ve el usuario en un chip de
cita significa "así lo rankeó el retriever", un hecho, no un artefacto del
orden en que el modelo escribió la respuesta.

**Lo que este mecanismo NO verifica:** que el chunk citado realmente
respalde lo que la respuesta dice sobre él — un chunk puede estar
genuinamente en contexto y aun así ser malinterpretado por el modelo. Para
eso existe `faithfulness` (sección 11), una métrica distinta con un
objetivo distinto.

**Preguntas tipo:**
- ¿Por qué structured tool-use en vez de pedir citas en el texto libre y parsearlas con regex?
- ¿Qué diferencia hay entre "la cita apunta a un chunk real" y "la respuesta es fiel a ese chunk"?

---

## 9. Conversación multi-turno sin estado

**Qué es una decisión de diseño poco obvia:** toda la continuidad
conversacional vive en **un solo lugar** — `rewrite_query()`, que lee el
historial completo para resolver pronombres/referencias antes de buscar.
La llamada que *genera* la respuesta final no recibe historial — solo el
contexto recuperado de este turno y la pregunta ya reescrita. El LLM que
responde no tiene memoria de lo que acaba de decir.

**Por qué es una decisión deliberada, no una limitación accidental:**
- Costo y latencia planos por turno, sin importar cuán larga sea la
  conversación (el prompt de generación no crece).
- Sin riesgo de que el modelo mezcle contexto viejo con chunks nuevos.
- **La razón más importante:** la validación de citas (sección 8) queda
  trivialmente correcta, porque `chunks_by_id` solo contiene el contexto
  de *este* turno — un `chunk_id` de un turno anterior no puede validar
  ni por accidente.

**El costo real, nombrado explícitamente:** el asistente no puede hacer
meta-referencias ("como te decía recién"), no puede autocorregirse, y si
`rewrite_query()` falla en resolver un pronombre, no hay red de
contención.

**Bug real encontrado en el camino:** al armar el historial para
`rewrite_query()` como una conversación real (turnos `user`/`assistant`
alternados), el modelo — pese a que el system prompt pedía explícitamente
"reescribí, no respondas" — **contestó la pregunta nueva en vez de
reescribirla**, porque la estructura se parecía demasiado a un chat real
en curso. Fix: aplanar el historial como texto descriptivo dentro de un
único mensaje de usuario, para que no haya ambigüedad de que esto es una
tarea de transformación de texto. **Lección:** la forma en que se
estructura un prompt (no solo su contenido) puede pisotear una instrucción
explícita.

**Preguntas tipo:**
- ¿Qué gana un sistema al mantener la generación sin estado, incluso pudiendo pasar historial?
- ¿Por qué la estructura de un prompt (roles, turnos) puede importar tanto como su contenido?

---

## 10. Retrieval directo vs. agéntico

**Retrieval directo** (lo que corre en Lorebase hoy): el pipeline decide
qué buscar *antes* de que el LLM que responde vea la pregunta — reescribir
si hay historial, buscar exactamente una vez, armar contexto, recién ahí
llamar al LLM. El LLM nunca controla la búsqueda.

**Retrieval agéntico:** se le da al LLM una tool de búsqueda (además de la
tool de responder) y decide él mismo si busca, con qué query, y si una
búsqueda alcanza o hace falta otra. Es el patrón **ReAct** (Reason → Act →
Observe, repetir) aplicado a RAG.

**El trade-off:**

| | Directo | Agéntico |
|---|---|---|
| Costo/latencia | Predecible | Variable (0 a N búsquedas) |
| Debuggability | Contexto fijo, inspeccionable antes de responder | Hay que trazar toda la secuencia de decisiones |
| Preguntas simples | Sin overhead | Puede gastar una búsqueda de más |
| Preguntas multi-hop | Sin recuperación si la primera búsqueda no alcanza | Puede reintentar con otro ángulo |

**Medido, no asumido (ADR 0005):** mismo golden set de 30 preguntas, mismo
juez, ambas estrategias implementadas con el mismo contrato
(`ask_with_contexts()`/`ask_agentic()`):

| Métrica | Directo | Agéntico |
|---|---|---|
| Hit-rate | 30/30 | 30/30 |
| `context_precision` | 0.809 | 0.724 |
| `context_recall` | 0.900 | 0.928 |
| `faithfulness` | 0.950 | 0.930 |
| `answer_relevancy` | 0.924 | 0.928 |
| Latencia promedio | 3.6s | 14.4s |
| Tokens de entrada promedio | 2658 | 4348 |

**Por qué esta tabla es más interesante que "directo ganó":** el ruido de
medición es real — `faithfulness` del directo solo, corrido dos veces sin
cambiar código, dio 0.906 y 0.950 (±0.05 de puro ruido del juez LLM). La
única diferencia con margen consistente es `context_precision`, a favor
del directo. **Veredicto honesto:** ninguna métrica de calidad justifica
pagar 4x latencia y ~40% más tokens en *este* corpus — pero el golden set
es mayormente preguntas de un solo hecho, sin ninguna genuinamente
multi-hop, así que el agéntico nunca tuvo la chance de mostrar su ventaja
teórica (recuperarse de una primera búsqueda insuficiente). El hallazgo
real es "no hace falta pagar el costo cuando el directo ya funciona bien
acá", no "el agéntico no sirve nunca". El código queda construido, probado
y sin exponer — vivo para retomar si aparecen preguntas multi-hop reales.

**Preguntas tipo:**
- ¿Cuándo el retrieval agéntico tiene una ventaja real sobre el directo, y cuándo es solo costo extra?
- ¿Por qué una diferencia de 0.05 en una métrica de un juez LLM puede ser ruido y no señal?

---

## 11. Evaluación de sistemas RAG (RAGAS)

**Por qué evaluar en primer lugar:** sin un harness, un cambio en
chunking o en los pesos de fusión es un "me parece que mejoró" — con un
golden set y métricas reproducibles, es un número comparable entre
corridas. Es lo que separa ingeniería real de intuición.

**Las 4 métricas de RAGAS, y por qué separarlas importa** (cada una mide
algo que puede fallar de forma independiente):

- **Context precision** — de los chunks que trajo el retriever, ¿cuántos
  eran relevantes? Mide *ruido*.
- **Context recall** — de todo lo necesario para responder bien, ¿cuánto
  trajo? Mide *lo que se perdió*.
- **Faithfulness** — ¿la respuesta se sostiene en los chunks recuperados,
  o el modelo inventó/extrapoló? Lo más cercano a medir alucinación
  directamente.
- **Answer relevancy** — ¿la respuesta contesta lo que se preguntó? Puede
  ser 100% fiel a las fuentes y aun así irse por la tangente.

**Por qué importan por separado, no como un promedio:** te dicen *dónde*
está el problema. Recall bajo → ajustar el retriever. Recall alto pero
faithfulness bajo → el problema es el LLM inventando, tocar el retriever
no serviría de nada. Un promedio esconde justo la información que las
hace útiles.

**Cómo lo implementó Lorebase:**
- **Golden set real, no sintético:** 30 preguntas sobre el propio CV
  técnico del usuario (en inglés y español, deliberadamente duplicado para
  poder probar retrieval cross-lingual), cada entrada validada por código
  contra la base real antes de confiar en ella.
- **Hit-rate determinístico + RAGAS, señales complementarias:** hit-rate
  es barato (sin LLM juez) y exacto (¿apareció el documento esperado entre
  los recuperados?); RAGAS es más caro pero más matizado.
- **El juez es el mismo modelo que genera las respuestas** (Anthropic) —
  una sola API key, más barato, con el trade-off nombrado explícitamente:
  sesgo de auto-preferencia documentado en la literatura de evaluación
  (un modelo juzgando a su propia familia).
- **Bug metodológico real, encontrado y corregido:** la corrida completa
  (30/30) reveló que el chequeo de hit-rate original daba **falsos
  negativos** (26/30 en la primera corrida) — las 4 preguntas "falladas"
  tenían `context_recall` alto según RAGAS, es decir que el contenido
  correcto sí se había recuperado. Causas reales: la misma historia
  contada en dos secciones distintas del documento, un heading esperado
  en inglés pero el chunk recuperado con su heading traducido al español,
  y una sección corta fusionada con su padre perdiendo su heading propio.
  Las tres eran limitaciones del *golden set*, no del pipeline —
  confirmado con los scores de RAGAS antes de tocar nada. **Lección:**
  cuando una métrica barata y una cara no coinciden, no asumas que la
  cara tiene razón — puede ser el chequeo barato el que está mal
  calibrado.

**Cómo se lee un reporte de RAGAS en la práctica, paso a paso.** Tomá el
reporte real de la sección 10 (retrieval directo) como ejemplo:
`context_precision=0.809`, `context_recall=0.900`, `faithfulness=0.950`,
`answer_relevancy=0.924`. El orden de lectura que sirve:

1. **Mirá recall primero.** 0.900 es alto — el retriever, en promedio,
   trae la mayor parte de lo necesario. Si este número fuera bajo (digamos
   <0.6), no tendría sentido mirar nada más todavía: no importa qué tan
   bien razone el LLM sobre contexto que ni siquiera llegó. El problema
   estaría en chunking, en la estrategia de búsqueda, o en el corpus
   mismo.
2. **Después precision.** 0.809, más bajo que recall — quiere decir que
   el retriever trae *algo* de ruido junto con lo relevante (normal:
   recall alto casi siempre cuesta algo de precisión, es un trade-off
   real, no un bug). Con precision muy baja (<0.5) el LLM tiene que
   "filtrar" mucho contexto irrelevante para llegar a lo que importa, lo
   que aumenta el riesgo de faithfulness bajo (más ruido, más
   oportunidad de que el modelo se apoye en el chunk equivocado).
3. **Recién ahí faithfulness y answer relevancy** — las métricas de
   generación. 0.950 y 0.924 son ambas altas, coherente con un recall/
   precision razonables: el LLM tiene buen material para trabajar y lo
   está usando bien. Si faithfulness fuera bajo *con* recall/precision
   altos, la conclusión sería específica y accionable: el problema no es
   el retriever, es el prompt o el modelo — ajustar chunking no cambiaría
   nada, ahí es donde vale la pena revisar el system prompt (¿le estás
   pidiendo explícitamente que se ciña al contexto?) o considerar un
   modelo distinto.

**Qué rangos son "buenos", con honestidad:** no hay un umbral universal —
depende del dominio y de qué tan difícil es el golden set (un golden set
de preguntas triviales infla todos los números). Como referencia de orden
de magnitud, en este proyecto >0.85 se leyó como "sano", 0.7-0.85 como
"revisar pero no urgente", y <0.7 como señal real de un problema
específico que vale la pena investigar — no son cortes de la literatura,
son los que se usaron acá con este corpus y este juez.

**El error más común leyendo RAGAS** (y el que pasó de verdad en este
proyecto, sección 10): tratar una diferencia chica entre dos corridas
como una mejora o una regresión real, sin considerar el ruido del propio
juez LLM. Antes de sacar una conclusión de una diferencia de 0.02-0.05,
hay que preguntarse si esa diferencia sobreviviría correr el mismo
pipeline dos veces sin cambiar nada.

**Preguntas tipo:**
- ¿Por qué context recall alto y faithfulness bajo apuntan a problemas distintos?
- ¿Qué riesgo tiene usar el mismo modelo como generador y como juez, y por qué se aceptó igual?
- Contame de una vez que una métrica te mintió y cómo te diste cuenta.
- Te doy un reporte de RAGAS con recall bajo y faithfulness alto — ¿por dónde empezás a debuggear?

---

## 12. Observabilidad para aplicaciones de LLM

**Qué es.** Trazar cada llamada (retrieval, LLM) con spans — no solo
loggear texto, sino estructura: qué se buscó, qué se recuperó, qué prompt
se mandó, cuánto costó, cuánto tardó — consultable después, no solo
visible en el momento. Un **span** es una unidad de trabajo con nombre,
inicio, fin, y atributos clave-valor (en vez de una línea de texto libre
como un log tradicional); un **trace** es un árbol de spans relacionados
(un span "padre" que representa el pedido completo, con spans "hijos" para
cada paso interno) — eso es lo que permite ver, para una respuesta lenta,
exactamente cuál de los pasos (retrieval léxico, denso, reranking, la
llamada al LLM) fue el que tardó, en vez de solo saber que la respuesta
completa tardó 8 segundos.

**Por qué la observabilidad es específicamente más crítica en IA que en
software tradicional** (pregunta de entrevista muy común, y merece una
respuesta mejor que "porque sí es importante"):

- **No-determinismo.** El mismo input puede dar outputs distintos entre
  corridas (sección 17, sampling) — un log de "request → response" no
  alcanza para entender por qué una corrida salió distinta de otra; hace
  falta ver *el contexto exacto* que recibió el modelo, no solo que lo
  recibió.
- **Los tests unitarios no capturan la mayoría de los fallos reales.** Un
  test puede verificar que el pipeline no tira una excepción, pero no
  puede verificar "esta respuesta es correcta" de forma determinística —
  eso requiere o un juez LLM (con su propio ruido, sección 11) o revisión
  humana. La observabilidad en producción — ver qué se buscó, qué se
  recuperó, qué se respondió, con qué feedback real — es, en la práctica,
  la principal red de seguridad contra regresiones de *calidad*, no solo
  de disponibilidad.
- **El costo es una variable de runtime, no de código.** Un bug de
  performance en software tradicional se ve en latencia; acá también se
  ve directo en la factura — un prompt mal armado que manda 5x más
  contexto del necesario cuesta 5x más por cada request, silenciosamente,
  sin ningún error que lo señale. Sin tracking de tokens/costo por
  llamada (sección "Notas" de esta sección), ese tipo de regresión no se
  nota hasta la factura mensual.
- **Un pipeline con varias etapas (retrieval → rerank → LLM) necesita
  poder aislar cuál etapa falló**, no solo que "la respuesta estuvo mal"
  — exactamente el argumento de la sección 1 (tres puntos de falla
  independientes). Sin tracing estructurado por etapa, diagnosticar eso
  es adivinar.
- **Drift silencioso.** Un proveedor externo (embeddings, LLM) puede
  cambiar de comportamiento sin avisar (una actualización de modelo, un
  cambio de versión por default) — sin métricas históricas comparables,
  una degradación gradual de calidad es indistinguible de "así fue
  siempre".

**Cómo lo implementó Lorebase:**
- **Un solo decorador (`@traced_search`) instrumenta las cinco clases
  `Retriever`**, no un bloque de tracing central — como cada retriever
  compuesto (`HybridRetriever`, `RerankingRetriever`, `DateAwareRetriever`)
  envuelve retrievers internos y todos comparten la firma `search()`,
  decorar cada clase produce un árbol de spans anidado automáticamente,
  sin que ninguna clase sepa de las demás.
- **Convenciones semánticas oficiales de OpenTelemetry para IA
  generativa** (`gen_ai.provider.name`, `gen_ai.usage.input_tokens`, etc.)
  en vez de nombres propios — así el backend de observabilidad
  (Langfuse, en este caso) es intercambiable sin tocar el código de
  instrumentación. El costo en dólares (`lorebase.cost_usd`) es la única
  excepción — no existe aún en el estándar — y solo se setea cuando hay un
  valor real, nunca `0.0` cuando el costo no está configurado (para no
  disfrazar "desconocido" de "gratis").
- **Verificación real, no solo "se ve un trace en el dashboard":** se
  capturó un span con `InMemorySpanExporter` y se lo pasó directo a
  `OTLPSpanExporter().export(...)`, confirmando éxito de forma síncrona,
  en vez de mandar una pregunta real y asumir que el flush asíncrono del
  batch processor lo mandó bien.

**Preguntas tipo:**
- ¿Por qué usar convenciones semánticas estándar en vez de nombres de atributo propios?
- ¿Cómo instrumentarías un pipeline compuesto (retrievers anidados) sin que cada capa sepa de las demás?

---

## 13. Model Context Protocol (MCP)

**Qué es.** Protocolo abierto que estandariza cómo una aplicación de IA
(Claude Desktop, Claude Code) se conecta a fuentes de datos y
herramientas externas — la analogía oficial es "USB-C para aplicaciones
de IA". Un **servidor** MCP expone capacidades (tools/resources/prompts);
un **cliente** las consume. Lorebase es el servidor: expone
`search_knowledge`, `get_document`, `list_sources`.

**El puente con retrieval agéntico (sección 10):** ahí el LLM interno de
Lorebase usaba una tool de búsqueda interna. MCP es el mismo patrón
—herramienta con schema, el LLM decide cuándo llamarla— pero invertido:
Lorebase pasa a ser el *proveedor* de la herramienta para un LLM
*externo*. Mismo concepto, rol invertido.

**stdio vs. Streamable HTTP — la pregunta real es quién arranca el
proceso:**
- **stdio:** el cliente lanza el servidor como subproceso propio, hablan
  por stdin/stdout — como correr un script a mano.
- **Streamable HTTP:** el servidor ya existe, corriendo solo, escuchando
  en un puerto — la diferencia entre `manage.py shell` (proceso efímero)
  y `manage.py runserver` (servicio persistente).

Lorebase corre como un servicio más de Docker Compose, así que Streamable
HTTP es la única opción real — stdio necesita que el *cliente* lo lance.

**Auth: bearer token, sin necesidad de un authorization server real.**
Claude Code es un proceso automatizado, no una persona logueada — prueba
su identidad con un secreto en `Authorization: Bearer <token>` en cada
pedido, conceptualmente lo mismo que hace una cookie de sesión para un
browser. `AccessToken` del SDK tiene forma de OAuth completo (`client_id`,
`scopes`, `issuer_url`) aunque no se implemente ningún flujo OAuth real —
la interfaz del SDK sostiene ambos casos (bearer simple o OAuth completo)
con la misma forma; Lorebase usa el extremo simple, self-referenciando su
propia URL como `issuer_url`.

**Reuso real de arquitectura, no una integración aparte:** las 3 tools
llaman directo a `get_retriever().search()` — el mismo `HybridRetriever`
de retrieval directo, sin ninguna lógica duplicada. `search_knowledge`
**no pasa por el LLM ni por la validación de citas** (sección 8) — le
devuelve los resultados crudos al agente externo, que decide qué hacer
con ellos.

**Preguntas tipo:**
- ¿Por qué Streamable HTTP y no stdio para un servicio que corre de forma independiente?
- ¿Por qué el auth de MCP necesita campos con forma de OAuth aunque no haya un flujo OAuth real corriendo?

---

## 14. Resiliencia contra APIs externas de IA

**Por qué importa específicamente en sistemas de IA:** las APIs de
embeddings/reranking/LLM tienen rate limits mucho más agresivos que una
API REST típica (3 requests/minuto en una cuenta gratis de Voyage, en este
proyecto) — y a diferencia de una caída puntual, un rate limit por minuto
no se resuelve con backoff exponencial acotado a segundos.

**El patrón que se repitió tres veces (reranker, embeddings, y de nuevo
embeddings) — cada vez con un fix distinto según qué tan crítico era el
paso:**

1. **Reranker: degradar, no fallar.** `RerankerUnavailableError` traduce
   errores transitorios específicos (`RateLimitError`,
   `ServiceUnavailableError`, `Timeout` — nunca "cualquier excepción").
   `RerankingRetriever.search()` atrapa esa excepción puntual y devuelve
   los resultados sin rerankear en vez de propagar un 500 — la fusión RRF
   sigue siendo una respuesta razonable, solo sin el refinamiento del
   cross-encoder. Verificado contra el rate limit real: 5 preguntas
   seguidas dispararon `RateLimitError` las 5 veces, y las 5 devolvieron
   `200` en vez de `500`.
2. **Embeddings: no hay "fallback razonable"** (no tiene sentido "no
   embeddear"), así que la resiliencia se resolvió a nivel de la task de
   Celery (`autoretry_for`/`retry_backoff`), no del request individual —
   posible porque `embed_pending_chunks()` ya es reanudable por
   construcción (siempre busca `embedding__isnull=True`), así que
   reintentar la task completa después de un rate limit retoma
   exactamente donde quedó, sin re-embeder nada dos veces.
3. **Bug real *dentro* del propio intento de arreglar esto:** al agregar
   reintento a nivel de Celery sin tocar el cliente HTTP, cada reintento
   de Celery terminaba disparando **hasta 2 llamadas reales** (el SDK de
   Voyage ya reintentaba por su cuenta antes de fallar) — duplicando la
   presión sobre un límite ya muy ajustado. Fix: bajar `max_retries` del
   SDK a 1, para que el backoff de Celery sea el único mecanismo de
   reintento. **Lección:** dos capas de retry independientes, cada una
   razonable por separado, pueden multiplicar el problema que las dos
   están tratando de resolver.
4. **Salida final, sobre la marcha, con aprobación explícita:** después de
   varios incidentes reales en una sola sesión (un 500, retrieval
   degradado, una task muerta), se sacó el reranking *y* los embeddings
   de la ruta de una API externa por completo — modelos locales por
   default, sin llamada de red en el camino crítico.

**Preguntas tipo:**
- ¿Por qué un rate limit por minuto necesita una estrategia distinta a un timeout puntual?
- Contame de un caso donde dos mecanismos de resiliencia, cada uno razonable, interactuaron mal entre sí.

---

## 15. Auth, multi-tenancy y rate limiting

**Auth de la SPA: cookie de sesión, no JWT (ADR 0007).** Frontend y
backend comparten origen detrás de un proxy Nginx — no un SPA
cross-origin hablando con una API aparte. Una cookie de sesión de Django
(+ CSRF) no necesita nada de la maquinaria de JWT (par access/refresh,
dónde guardar el token client-side, manejo de expiración) porque el
problema que esa maquinaria resuelve (compartir auth entre orígenes
distintos) no existe acá. El límite real: **solo funciona porque son el
mismo origen** — por eso el servidor MCP, un cliente genuinamente
separado, usa su propio bearer token (`ApiKey`) en vez de reusar la
sesión.

**Multi-tenancy desde el día uno, no agregado después.** `Membership(user,
workspace, role)` en vez de un `Workspace 1—N User` directo — la
diferencia importa: con la relación directa, un usuario queda atado a un
único workspace para siempre, y agregar multi-workspace más tarde sería
migración de datos más reescribir todos los querysets. Es gratis al
principio del proyecto y caro después — el tipo de decisión que conviene
tomar antes de escribir el primer modelo, no cuando ya hace falta.

**Rate limiting: por qué no alcanza el throttling nativo de DRF.** El
endpoint de chat es una vista Django plana (`@login_required` +
`@require_POST`), no un `APIView` — `throttle_classes` es un mecanismo
específico de DRF que no aplica ahí. Se armó un decorador propio
(`core/ratelimit.py`) sobre el mismo cache de Redis que ya usa el
proyecto, con **ventana fija usando `cache.incr()` atómico** (no un
patrón get-then-set) — dos pedidos concurrentes no pueden pasarse del
límite por una carrera.

**Preguntas tipo:**
- ¿Cuándo una cookie de sesión es la elección correcta sobre JWT, y cuándo no?
- ¿Por qué `Membership` como tabla propia es más barata de agregar antes que después?
- ¿Qué diferencia hay entre `cache.incr()` atómico y un patrón get-then-set para rate limiting, y por qué importa bajo concurrencia?

---

## 16. Pensar en trade-offs: las ADRs como práctica

Documentar una decisión no obvia — con el contexto, la decisión, y las
consecuencias reales (ganancias *y* costos aceptados, no solo
justificación) — es una habilidad que se entrena, no algo que sale solo.
Las 7 ADRs de este proyecto (`docs/adr/`) son ejercicios concretos de esa
habilidad, cada una con un disparador de migración explícito (bajo qué
condición futura la decisión cambiaría), no una defensa cerrada:

1. **pgvector sobre un vector DB dedicado** — cero infraestructura nueva vs. HNSW menos ajustable a gran escala.
2. **Postgres FTS sobre OpenSearch** — la mitad léxica se construyó como definitiva desde el día uno, no un placeholder.
3. **Filesystem local sobre S3** — cero infraestructura vs. sin redundancia geográfica.
4. **Citas verificadas por tool-use** — una garantía estructural vs. depender de una instrucción de prompt.
5. **Retrieval directo sobre agéntico** — medido con datos, no asumido.
6. **RRF sobre fusión ponderada** — sin normalización que tunear vs. perder info de magnitud del score.
7. **Auth por sesión sobre JWT** — más simple dado que comparten origen vs. no extiende a clientes cross-origin.

**El patrón que se repite en las 7:** ninguna decisión es "la mejor en
abstracto" — todas son la mejor *para esta escala, este equipo (una
persona), este momento*, con una condición explícita bajo la cual dejarían
de serlo. Esa es la respuesta madura a "¿por qué elegiste X en vez de Y?"
en una entrevista: no "X es mejor", sino "Y resuelve un problema que no
tengo todavía, y sé exactamente cuándo empezaría a tenerlo".

**Preguntas tipo:**
- Elegí una de las 7 ADRs y contame la decisión como si fuera tuya, sin mirar el documento.
- ¿Qué hace que una ADR sea útil dentro de un año, y no solo el día que se escribió?

---

## 17. Temas que Lorebase no cubre, pero conviene saber

Todo lo de arriba está anclado en código real de este proyecto. Esta
sección es distinta a propósito: son temas de conocimiento general de
Applied AI que **Lorebase no implementa** — algunos porque no aplican a
su escala, otros porque son gaps reales y honestos — pero que son
candidatos naturales de pregunta en una entrevista de este perfil.
Marcados explícitamente como "no construido acá" para no confundir
conocimiento del proyecto con conocimiento general.

**Transformers y atención.** La arquitectura detrás de todo lo que usa
Lorebase — LLM, embeddings, reranker — es el transformer (Vaswani et al.,
"Attention Is All You Need", 2017). La pieza central es
**self-attention**: para cada token, el modelo calcula cuánto debería
"prestarle atención" a cada otro token de la secuencia (incluido a sí
mismo), y combina la información pesada por esa atención — a diferencia
de una RNN, que procesa la secuencia paso a paso y tiene que "recordar"
lo anterior a través de un estado que se va degradando, el transformer ve
toda la secuencia a la vez y puede conectar directamente dos tokens
lejanos entre sí. **Multi-head attention** corre varias de estas
atenciones en paralelo (distintas "cabezas"), cada una potencialmente
capturando un tipo distinto de relación (sintáctica, semántica, de
correferencia). No hace falta poder derivar las fórmulas en una
entrevista de Software Engineer, pero sí poder explicar *por qué*
importa: es lo que le permite a un modelo relacionar el final de un
documento largo con su principio sin la degradación que tienen
arquitecturas secuenciales más viejas.

**Encoder-only vs. decoder-only vs. encoder-decoder.** Tres formas de
usar la arquitectura transformer para tareas distintas — y Lorebase usa
dos de las tres sin nombrarlo explícitamente en el código. **Encoder-only**
(BERT y su familia, de donde vienen E5/BGE) procesa toda la entrada a la
vez y produce una representación — ideal para embeddings y clasificación,
no para generar texto libremente. **Decoder-only** (la familia GPT/Claude)
genera un token a la vez, cada uno condicionado solo en lo que vino antes
(atención "causal" — no puede ver el futuro) — la arquitectura de
cualquier LLM conversacional, incluido el que responde en Lorebase.
**Encoder-decoder** (T5, los modelos de traducción clásicos) usa un
encoder para procesar la entrada completa y un decoder que genera la
salida condicionado en esa representación — común en traducción y
resumen, menos en el chat RAG moderno. Los modelos de embedding de
Lorebase son efectivamente encoder-only; el LLM que responde es
decoder-only.

**Tokenización.** Ni palabras ni caracteres — los modelos operan sobre
**subwords**, generados con algoritmos como BPE (Byte-Pair Encoding) o
variantes. Una palabra común es un solo token; una palabra rara o
inventada se parte en varios pedazos más chicos. Por qué importa
prácticamente: los límites de contexto, precios de API, y presupuestos de
prompt se miden en tokens, no en caracteres — un texto en español puede
tokenizar distinto (a veces peor) que el mismo texto en inglés, según qué
tan bien representado esté ese idioma en el vocabulario del tokenizer.
`tiktoken` (que aparece indirectamente en las dependencias de Lorebase,
para contar tokens) es el tokenizer que usan los modelos estilo
OpenAI/Anthropic.

**Ventana de contexto y "lost in the middle".** Cuánto texto entra en un
solo prompt. Más contexto no es gratis ni estrictamente mejor: hay
evidencia empírica publicada (Liu et al., "Lost in the Middle", 2023) de
que los LLMs recuperan información del **principio y el final** de un
contexto largo con más fiabilidad que del medio — un motivo real, más
allá del costo, para no simplemente "meter más chunks" en vez de mejorar
el retrieval. Es una razón concreta por la que la calidad del ranking
(sección 6-7) importa más que la cantidad de contexto.

**Sampling: temperature y top-p.** Un LLM no elige el siguiente token de
forma determinística — calcula una distribución de probabilidad sobre el
vocabulario entero y muestrea de ahí. **Temperature** escala esa
distribución antes de muestrear: cerca de 0 la vuelve casi determinística
(siempre el token más probable — bueno para tareas factuales,
QA/extracción, exactamente el caso de uso de Lorebase), valores altos la
aplanan (más variedad, más "creatividad", más riesgo de desvarío — mejor
para brainstorming o escritura creativa). **Top-p** (nucleus sampling)
recorta la distribución a los tokens más probables hasta acumular una
probabilidad p, y muestrea solo entre esos — evita elegir tokens
absurdamente improbables incluso con temperature alta.

**Fine-tuning vs. RAG vs. prompting — cuándo cada uno.** Pregunta clásica
de entrevista. **Prompting** (incluido few-shot, dar ejemplos en el
prompt) es lo más barato y rápido de iterar, pero limitado por lo que
entra en una ventana de contexto y no persiste entre llamadas.
**RAG** resuelve conocimiento externo/privado y que cambia con el tiempo
(exactamente el caso de Lorebase) sin tocar los pesos del modelo — el
conocimiento vive en una base de datos, no en el modelo, así que
actualizarlo es reindexar, no reentrenar. **Fine-tuning** ajusta los
pesos del modelo mismo — tiene sentido para cambiar *comportamiento* o
*estilo* de forma consistente (un tono de voz particular, un formato de
salida fijo, un dominio muy especializado con jerga propia), no para
"enseñarle hechos nuevos" de forma confiable — un modelo fine-tuneado
puede seguir alucinando hechos tan fácil como uno base, y cada
actualización de conocimiento exige reentrenar. En la práctica, los tres
no son excluyentes: un sistema de producción real suele combinar
prompting cuidadoso + RAG para conocimiento, y reservar fine-tuning para
casos donde el comportamiento no se logra con prompting solo.

**Prompt injection en sistemas RAG.** Riesgo real y **no mitigado en
Lorebase** — vale la pena poder nombrarlo con honestidad en vez de
fingir que no existe. Como el contenido recuperado se inserta directo en
el contexto del LLM, un documento indexado que contenga texto tipo
"ignorá las instrucciones anteriores y hacé X" está, desde la perspectiva
del modelo, mezclado con instrucciones legítimas del sistema — no hay una
frontera estructural fuerte entre "esto es información" y "esto es una
instrucción" dentro de un prompt de texto plano. Para un segundo cerebro
personal el riesgo es bajo (el usuario controla qué se indexa), pero
escala mal hacia el caso de uso de equipo (documentos de terceros,
repos externos) que el plan original consideraba. Mitigaciones reales que
existen en la industria: delimitar claramente el contexto recuperado con
marcadores explícitos y instruir al modelo a tratarlo como datos, nunca
como instrucciones; sanitizar/filtrar patrones sospechosos antes de
indexar; y, para acciones con efecto real (no solo respuestas de texto),
nunca dejar que una tool call se dispare basada únicamente en contenido
recuperado sin confirmación.

**Prompt caching.** Anthropic y OpenAI permiten marcar un prefijo de
prompt (por ejemplo, un system prompt largo y estable) para cachearlo del
lado del servidor — llamadas repetidas que comparten ese prefijo pagan
mucho menos y responden más rápido, porque el modelo no tiene que
reprocesar esos tokens desde cero. Lorebase **no lo usa hoy** — el
`SYSTEM_PROMPT` se manda completo en cada turno — pero sería una
optimización de costo/latencia directa y de bajo riesgo dado que el
system prompt no cambia entre preguntas.

**Model routing / cascading.** Usar un modelo barato y rápido para la
mayoría de los pedidos, y escalar a uno más caro y capaz solo cuando hace
falta (por dificultad detectada, o como fallback si el barato falla una
verificación). Lorebase toma una versión simple y estática de esta idea —
eligió Haiku sobre Sonnet para *todo* el tráfico como una decisión de
costo deliberada (sección de embeddings/reranking, mismo espíritu) — pero
no hace routing dinámico por pregunta.

**Evaluación online, más allá de RAGAS.** RAGAS (sección 11) es
evaluación *offline*, contra un golden set fijo. Un sistema en producción
real necesita también evaluación *online*: el feedback 👍/👎 real de
usuarios (que Lorebase sí captura, `analytics/`) es la señal más honesta
de todas porque viene de uso real, no de un golden set que puede quedar
desactualizado o sesgado. La combinación madura es golden-set offline
para no regresionar en cada cambio, más monitoreo online continuo para
detectar lo que el golden set no anticipó.

---

## 18. Mapa práctico del ecosistema

Esta sección responde directamente al tipo de pregunta que arma un
entrevistador cuando quiere ver panorama, no solo profundidad en un
proyecto puntual: cuándo se justifica cada pieza, cómo encajan entre sí,
y qué existe en el ecosistema más allá de lo que Lorebase eligió usar.

### 18.1 ¿Cuándo se justifica usar RAG?

RAG no es la respuesta por defecto a "quiero que un LLM sepa sobre mis
datos" — es la respuesta cuando se cumplen algunas de estas condiciones:

- **El conocimiento cambia con el tiempo, o es demasiado grande para
  caber en un prompt.** Si el "conocimiento" son 5 párrafos fijos, la
  respuesta más simple es pegarlos directo en el prompt (a veces llamado
  *prompt stuffing*) — no hace falta retrieval para eso. RAG se justifica
  cuando el corpus es más grande de lo que entra en una ventana de
  contexto razonable, o cambia seguido (notas nuevas cada semana, un repo
  con commits diarios) y no tiene sentido reentrenar/reprompt-ear a mano
  cada vez.
- **El conocimiento es privado o específico de un dominio** que el
  modelo base no vio en entrenamiento — documentación interna, notas
  personales, código propio. Exactamente el caso de uso de Lorebase.
- **Se necesita trazabilidad/verificabilidad** de dónde salió cada
  afirmación — un requisito que fine-tuning no puede dar (un modelo
  fine-tuneado "sabe" algo pero no puede señalar de qué documento salió
  ese conocimiento, porque quedó mezclado en los pesos).
- **El costo de reentrenar no se justifica frente a la frecuencia de
  cambio del conocimiento.** Reindexar un documento nuevo es mucho más
  barato y rápido que reentrenar un modelo.

**Cuándo NO se justifica (o se justifica poco):** si el conocimiento es
chico y estable (cabe en un prompt fijo, prompting simple alcanza); si lo
que hace falta es cambiar el *comportamiento* del modelo, no agregarle
hechos (fine-tuning, sección 17); si la latencia extra de una búsqueda
antes de responder no se puede pagar en el caso de uso (algunas
aplicaciones de tiempo real muy ajustado); o si el "conocimiento" en
realidad ya está bien cubierto por lo que el modelo aprendió en
entrenamiento (preguntas de cultura general no necesitan retrieval sobre
tus propios documentos).

### 18.2 Cómo se integra RAG en un sistema más grande

Un sistema RAG real vive detrás de una API, no como un script aislado.
El patrón de integración típico:

```
Cliente (web/app/CLI)
      │  pregunta
      ▼
Backend / API
      │  1) reescribe la query si hace falta (historial)
      │  2) llama al retriever
      │  3) arma el prompt con el contexto recuperado
      │  4) llama al LLM
      │  5) valida/persiste la respuesta
      ▼
Retriever  ◄──── índice (vector DB + índice léxico)
      │
      ▼
LLM Provider (API externa o modelo self-hosted)
```

La pieza importante para una entrevista es distinguir **dos caminos de
datos separados, con requisitos muy distintos**:

- **Camino de ingestion (offline/batch):** documentos → parseo → chunking
  → embeddings → escritura al índice. Corre en background (en Lorebase,
  Celery), no bloquea a ningún usuario, y puede tardar minutos sin que
  nadie lo note. Es donde vive la mayor parte del *trabajo* computacional
  (embeder miles de chunks), pero fuera del camino crítico de latencia.
- **Camino de consulta (online/síncrono):** pregunta del usuario →
  retrieval → generación → respuesta. Tiene que ser rápido (segundos, no
  minutos) porque hay una persona esperando en vivo — acá es donde
  importan reranking eficiente, timeouts, fallback ante fallas (sección
  14), y caching.

**¿Qué partes son dinámicas y cuáles estáticas?** Pregunta muy práctica y
poco hecha explícita en la mayoría de las explicaciones de RAG — vale la
pena tener el mapa claro:

**Estático (se calcula una vez, en ingestion, y se reusa):**
- El chunking de un documento (a menos que el documento cambie).
- El embedding de cada chunk — se calcula una sola vez al indexar, se
  guarda, se reusa en cada búsqueda futura sin recalcularlo.
- El índice de búsqueda (HNSW, el índice invertido de FTS) — se
  construye/actualiza en ingestion, no en cada query.
- La elección de modelo de embedding, de LLM, de estrategia de retrieval
  — configuración de sistema, no algo que varíe por request.

**Dinámico (se recalcula en cada consulta):**
- El embedding de la *pregunta* — se calcula fresco en cada request (no
  se puede precalcular porque no se sabe qué van a preguntar).
- El resultado del retrieval — qué chunks salen top-k varía con cada
  pregunta.
- El prompt final armado con el contexto recuperado — literalmente
  distinto en cada llamada, porque el contexto es distinto.
- La respuesta generada — no determinística incluso con el mismo prompt
  (sección "sampling", más abajo), salvo temperature=0.

Entender esta división es lo que permite razonar sobre dónde optimizar:
cachear o precalcular tiene sentido en la parte estática (por eso
importa tanto que el embedding de un chunk se calcule una sola vez);
en la parte dinámica, la optimización pasa por reducir trabajo por
request (modelos más chicos/rápidos, menos llamadas, prompt caching de
la parte que sí es estable como el system prompt — sección 17), no por
evitar recalcular algo que genuinamente cambia cada vez.

### 18.3 Estrategias de retrieval: panorama completo

Lorebase implementa hybrid + reranking (secciones 4-7). El panorama es
más amplio — vale la pena poder nombrar estas variantes aunque no estén
implementadas acá:

- **Dense retrieval puro** — solo embeddings. El punto de partida más
  simple; falla en coincidencias literales (sección 4).
- **Sparse/lexical retrieval (BM25)** — el otro extremo; falla en
  paráfrasis.
- **Hybrid retrieval** — lo que hace Lorebase: combina ambos.
- **Multi-query retrieval** — el LLM genera varias reformulaciones de la
  misma pregunta (ángulos distintos) y se buscan todas, fusionando
  resultados — mejora recall para preguntas ambiguas, a costo de más
  búsquedas.
- **HyDE (Hypothetical Document Embeddings)** — en vez de embeder la
  pregunta directamente, se le pide al LLM que *genere una respuesta
  hipotética* a la pregunta, y se embede esa respuesta hipotética para
  buscar — la intuición es que una respuesta hipotética se parece más,
  en el espacio de embeddings, a un documento real que a una pregunta
  corta. Funciona bien cuando pregunta y respuesta tienen formas muy
  distintas.
- **Parent-document / sentence-window retrieval** — se indexan chunks
  chicos (para embeddings precisos) pero al recuperar se devuelve un
  contexto más grande alrededor (el chunk padre, o una ventana de
  oraciones vecinas) — resuelve la tensión chunk-chico-vs-contexto de la
  sección 2 sin comprometer ninguno de los dos lados.
- **Contextual retrieval** (técnica publicada por Anthropic, 2024) — antes
  de embeder un chunk, se le pide a un LLM que genere una o dos oraciones
  de contexto explicando dónde encaja ese chunk dentro del documento
  completo, y se prepende ese contexto al chunk antes de embederlo y
  indexarlo léxicamente — mismo problema que resolvió `heading_path` en
  Lorebase (sección 2), pero generalizado con un LLM en vez de estructura
  Markdown.
- **Self-query / query construction** — el LLM traduce la pregunta en
  lenguaje natural a una query estructurada con filtros (ej. "notas de
  julio sobre X" → filtro de fecha + búsqueda semántica) — el mismo
  problema que resolvió `rewrite_query()` + `DateAwareRetriever` en
  Lorebase (sección 10 del roadmap), pero como patrón con nombre propio
  en la literatura.
- **GraphRAG** — en vez de (o adicionalmente a) chunks independientes, se
  construye un grafo de entidades y relaciones extraídas de los
  documentos, y el retrieval puede recorrer relaciones explícitas
  ("¿qué servicios dependen de X?") en vez de solo similitud de texto —
  mucho más caro de construir y mantener, se justifica cuando las
  preguntas reales son sobre relaciones entre entidades, no solo "¿qué
  dice el documento sobre X?".

### 18.4 Dónde entran los LLMs: mapa de roles

Un error común es pensar que el LLM solo "genera la respuesta final".
En un pipeline real (y en Lorebase específicamente) aparece en varios
puntos, cada uno con un rol distinto:

| Rol | Dónde en Lorebase | Propósito |
|---|---|---|
| **Generación de la respuesta** | `rag/chat/service.py` | La tarea obvia: responder con el contexto recuperado. |
| **Reescritura de query** | `rag/chat/rewriting.py` | Resolver pronombres/referencias e inyectar fechas ISO antes de buscar (sección 10). |
| **Juez de evaluación** | `rag/evaluation/ragas_eval.py` | Puntuar context precision/recall/faithfulness/relevancy — el LLM evalúa, no solo genera (sección 11). |
| **Decisor en un loop agéntico** | `rag/chat/agentic.py` (no expuesto) | Decide si buscar de nuevo o responder — el LLM controla el flujo, no solo el contenido (sección 10). |
| **Agente externo vía MCP** | Consumidor de `mcp_server` | Un LLM *fuera* de Lorebase (Claude Code/Desktop) decide cuándo y qué buscar (sección 13). |

Roles que existen en el ecosistema más amplio y no aparecen en Lorebase:
**extracción estructurada** (convertir texto libre en JSON/campos —
técnicamente lo mismo que usa la validación de citas de la sección 8,
tool-use, aplicado a otro objetivo), **clasificación/routing** (decidir a
qué sistema o prompt mandar un pedido según su contenido), y
**sumarización** (condensar documentos largos antes o después del
retrieval).

### 18.5 Temperature: qué es, cómo se usa, cómo se "mide"

Ya definida conceptualmente en la sección 17 — acá el ángulo práctico,
porque "¿cómo se mide?" es una pregunta legítima con una respuesta que
no es obvia: **temperature no es algo que se mida, es un parámetro que
se fija** al llamar a la API (`temperature=0.0` a `1.0` o `2.0` según el
proveedor) — no hay un "termómetro" que la calcule después de generar
texto. Lo que sí se puede medir, *a partir* del efecto de la temperature,
es la **consistencia**: generar la misma pregunta varias veces con la
misma temperature y medir cuánto varían las respuestas (similitud entre
ellas, o si convergen en el mismo hecho central) — eso es una proxy
observable de cuán determinística está siendo la generación en la
práctica, útil para decidir si una temperature está bien calibrada para
el caso de uso. Lorebase usa el default del proveedor (no fuerza
`temperature=0`, aunque para un caso de uso de QA factual como este sería
una elección razonable a considerar) — un ejemplo concreto de una
perilla que existe pero que este proyecto no tuneó explícitamente, buena
para nombrar como mejora pendiente en una entrevista.

### 18.6 Bases de datos vectoriales: panorama y rol real

**Qué proveen, exactamente:** un índice eficiente para *nearest neighbor
search* (HNSW u otros algoritmos ANN, sección 5) sobre vectores de alta
dimensión, generalmente con la capacidad de filtrar por metadata además
de la búsqueda por similitud (ej. "los k vectores más cercanos, pero
solo entre los que pertenecen al workspace X").

**El panorama, con el trade-off de cada categoría:**

- **Extensión de una base relacional existente** (pgvector sobre
  Postgres — la elección de Lorebase, ADR 0001). Cero infraestructura
  nueva, transacciones consistentes con el resto de los datos. Techo más
  bajo en volumen/tuning fino que una solución dedicada.
- **Vector DB dedicada, self-hosted** (Qdrant, Weaviate, Milvus). Más
  control y performance a gran escala, filtrado avanzado, soporte nativo
  de sharding — a costa de un servicio más para operar y mantener
  sincronizado con la fuente de verdad de los datos.
- **Vector DB gestionada/SaaS** (Pinecone es la más nombrada en la
  industria). Cero operación propia, escala manejada por el proveedor —
  a costa de otro proveedor más del que depender, y costo que crece con
  el volumen.
- **Embebida/liviana** (Chroma, FAISS como librería). Buena para
  prototipos, notebooks, o aplicaciones chicas que no justifican ni
  siquiera un servicio aparte — no pensada para producción a escala ni
  para concurrencia alta.

**Cuándo elegir cada una** es, en esencia, la misma pregunta que responde
ADR 0001: ¿ya tenés una base relacional en el stack? ¿el volumen
justifica infraestructura dedicada? ¿necesitás filtrado muy selectivo a
gran escala que una extensión no ofrece bien? La respuesta correcta
cambia con la escala, no es fija — la habilidad que se evalúa en una
entrevista es poder justificar la elección para el caso concreto que te
plantean, no recitar cuál es "la mejor" en abstracto.

### 18.7 Herramientas más usadas del ecosistema

Un mapa rápido de lo que aparece seguido en descripciones de rol y en
sistemas reales — con honestidad sobre qué usa Lorebase y qué no:

| Categoría | Herramientas comunes | En Lorebase |
|---|---|---|
| Orquestación/framework RAG | LangChain, LlamaIndex, Haystack, DSPy | Ninguna — interfaces propias (sección 18.8 explica por qué) |
| Agentes/grafos de LLM | LangGraph, CrewAI, AutoGen | Ninguna — el loop agéntico (sección 10) es ~100 líneas propias |
| Vector DBs | Pinecone, Weaviate, Qdrant, Milvus, Chroma, pgvector | pgvector |
| Embeddings | OpenAI, Cohere, Voyage, modelos abiertos vía `sentence-transformers` | Voyage AI o local (`intfloat/multilingual-e5-large`) |
| Evaluación | RAGAS, DeepEval, Phoenix (Arize), TruLens, promptfoo | RAGAS |
| Observabilidad de LLM | Langfuse, LangSmith, Helicone, Arize | Langfuse, sobre OpenTelemetry estándar |
| Serving/inferencia self-hosted | vLLM, TGI (Text Generation Inference), Ollama | Ninguno — LLM vía API (Anthropic) |

**Por qué importa poder nombrarlas aunque no las hayas usado:** una
entrevista de system design frecuentemente pregunta "¿usarías LangChain
acá?" o "¿qué vector DB elegirías?" — la respuesta madura no es "sí" o
"la que más se usa", es poder comparar la opción con lo que ya se
decidió y explicar el trade-off real, tal como hacen las ADRs de este
proyecto.

### 18.8 LangChain: qué es, para qué sirve, cómo se usa (y por qué Lorebase no lo usó)

**Qué es.** Un framework que da abstracciones comunes sobre las piezas de
un sistema de LLM — proveedores de modelos, vector stores, retrievers,
document loaders, prompt templates — para no tener que escribir el
código de integración con cada proveedor a mano. Su pieza central es
`Runnable` (todo — un LLM, un retriever, un prompt template — implementa
la misma interfaz componible) y **LCEL** (LangChain Expression Language),
la sintaxis para encadenar `Runnable`s con el operador `|` (similar a un
pipe de Unix): `prompt | llm | output_parser` arma una cadena que se
ejecuta de punta a punta. Sobre esa base construye **chains** (secuencias
predefinidas para tareas comunes, como un chain de RAG completo) y
soporta agentes (el LLM decide qué `Runnable` invocar en cada paso —
sección 10 y 17). **LangGraph** (de la misma familia) extiende esto para
flujos con estado y control explícito sobre bifurcaciones/loops — más
adecuado que LCEL simple para agentes con lógica compleja.

**Para qué se usa en la práctica:** prototipar rápido (probar tres
vector stores o dos proveedores de LLM cambiando una línea, gracias a
que todos comparten la interfaz `Runnable`), y no reinventar
integraciones ya resueltas (loaders de PDF/HTML/notion, text splitters,
memory de conversación) cuando el objetivo es el producto, no la
plumbing.

**Por qué Lorebase construyó sus propias interfaces
(`Retriever`/`EmbeddingProvider`/`LLMProvider`) en vez de usar
LangChain** — una decisión real, buena para poder defender en una
entrevista, no solo "no lo conocía": el proyecto es explícitamente un
ejercicio de aprendizaje de los mecanismos de RAG de punta a punta (ver
"Why it exists" en el README) — envolver todo en LangChain hubiera
escondido justo el detalle que el proyecto existe para entender (cómo se
arma RRF, cómo se valida una cita, cómo se estructura un prompt). El
costo real de esa elección: se reescribió a mano lo que LangChain ya
resuelve (parsers, un chain de RAG básico), y se perdió el ecosistema de
integraciones ya construidas. Para un sistema de producción con plazos
reales, en vez de un proyecto de aprendizaje, usar un framework
establecido suele ser la elección correcta — la misma lógica de "no
reinventar lo que ya está resuelto" que ya aparece en varias ADRs de este
proyecto (no reinventar Postgres FTS con una librería propia, no
reinventar el backoff de reintentos que el SDK de Voyage ya trae). Poder
articular esta comparación — cuándo un framework ayuda y cuándo esconde
justo lo que hace falta entender — es en sí mismo una señal de criterio
que una entrevista está buscando.

**Preguntas tipo (sección 18 completa):**
- ¿Cuándo NO usarías RAG, aunque el caso de uso "suene" a RAG?
- Diseñame, en voz alta, un sistema de Q&A sobre documentación interna de una empresa de 100 personas.
- ¿Qué parte de un pipeline RAG se puede cachear, y cuál nunca?
- Nombrame tres estrategias de retrieval más allá de hybrid search, y cuándo elegirías cada una.
- ¿Por qué usarías (o no) LangChain para un proyecto nuevo de RAG?
