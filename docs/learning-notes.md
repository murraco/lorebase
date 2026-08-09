# Notas para el documento educacional

Borrador acumulativo de explicaciones que fuimos armando durante la
construcción de Lorebase, pensadas para terminar en un documento
educacional aparte una vez cerrado el roadmap completo (ver deuda técnica
en `roadmap.md`). No es el documento final — es dónde quedan "pineadas"
las explicaciones para no perderlas mientras se sigue construyendo.

---

## RAGAS: qué mide cada métrica y por qué separarlas importa

_(Etapa 16 — Observabilidad y evaluación, 2026-08)_

RAGAS son 4 métricas separadas, y cada una mide una cosa distinta que
puede fallar de forma independiente — vale la pena entender la diferencia
antes de verlas como un solo "score":

- **Context precision** — de los chunks que el retriever trajo, ¿cuántos
  eran realmente relevantes? Si trae 5 chunks y solo 2 sirven, la
  precisión es baja aunque la respuesta final haya salido bien de
  casualidad. Mide *ruido* en el retrieval.

- **Context recall** — de todo lo que hacía falta para responder bien,
  ¿cuánto trajo el retriever? Si la respuesta necesitaba 3 notas y solo
  trajo 1, el recall es bajo aunque esa nota que trajo sea perfectamente
  relevante. Mide *lo que se perdió*.

- **Faithfulness** — la respuesta final, ¿se sostiene en lo que dicen los
  chunks recuperados, o el modelo inventó/extrapoló algo que no está ahí?
  Esto es lo más cercano a medir alucinación directamente.

- **Answer relevancy** — la respuesta, ¿contesta lo que se preguntó?
  Podés tener una respuesta 100% fiel a las fuentes (faithfulness
  perfecto) que igual no responde la pregunta porque se fue por la
  tangente.

**Por qué importan las 4 por separado**: te dicen *dónde* está el
problema. Si el context recall es bajo, el problema es el retriever (hay
que ajustar chunking o el algoritmo de búsqueda). Si el recall es alto
pero el faithfulness es bajo, el problema es el LLM inventando cosas —
ajustar el retriever no serviría de nada. Tratarlas como un solo número
promedio esconde justamente la información que las hace útiles.

---

## Retrieval directo vs. retrieval agéntico: qué son y cómo decidir entre los dos

_(Etapa 16 — Observabilidad y evaluación, 2026-08)_

**Retrieval directo** (lo que Lorebase hace hoy): el pipeline decide qué
buscar *antes* de que el LLM que responde vea la pregunta. El flujo es
fijo — reescribir la query si hay historial, buscar exactamente una vez
con la estrategia configurada, armar el contexto, y recién ahí llamar al
LLM, que responde solo con lo que ya le sirvieron. El LLM nunca controla
la búsqueda.

**Retrieval agéntico**: en vez de buscar antes de llamar al LLM, se le da
al LLM una herramienta de búsqueda (además de la herramienta de
responder) y se deja que él decida si busca, con qué query, y si una
búsqueda alcanza o hace falta otra con un ángulo distinto. Es el patrón
ReAct (Reason → Act → Observe, repetir) aplicado a RAG: la búsqueda pasa
de ser un paso fijo del pipeline a ser parte del razonamiento del propio
modelo.

**El trade-off, sin ganador de antemano:**

| | Directo | Agéntico |
|---|---|---|
| Costo/latencia | Predecible (llamadas fijas) | Variable (0 a N búsquedas) |
| Debuggability | El contexto es fijo y se puede inspeccionar antes de responder | Hay que trazar toda la secuencia de decisiones |
| Preguntas simples | Sin overhead | Puede gastar una búsqueda de más |
| Preguntas multi-hop | Si la primera búsqueda no alcanza, no hay recuperación | Puede reintentar con otro ángulo |
| Riesgo nuevo | Ninguno | El LLM puede buscar mal, de más, o conformarse con poco |

Es un patrón real y cada vez más común en la industria (soporte de
primera clase en LangChain/LlamaIndex), pero no es una mejora gratuita —
la única forma honesta de decidir es medirlo en el propio corpus y las
propias preguntas, con un harness real, no copiar lo que dice un blog.

**Cómo se lee la comparación**: se corre el mismo golden set contra las
dos versiones del pipeline con las mismas métricas — manzanas con
manzanas. `context_precision`/`context_recall` dicen si el agéntico trae
mejor contexto (menos ruido, más completo). `faithfulness`/
`answer_relevancy` dicen si eso se traduce en mejores respuestas, no solo
mejor contexto. Y hace falta medir también lo que las métricas de calidad
no capturan: número de llamadas por pregunta y latencia — el costo real
del riesgo "impredecible" de la tabla. Agéntico "gana" solo si la mejora
de calidad es real (con pocas preguntas y un juez LLM no-determinístico,
hay que ser escéptico de diferencias chicas) *y* el costo extra es
aceptable para esa mejora. El resultado más útil casi nunca es un solo
número ("agéntico es X% mejor") sino un patrón: ¿gana específicamente en
preguntas multi-hop o ambiguas y empata en las simples? Esa granularidad
es la que realmente sirve para decidir en un sistema de producción.

**El resultado real, medido en Lorebase** (30 preguntas, mismo golden
set, mismo juez, ambas corridas con el mismo formato de reporte):

| Métrica | Directo | Agéntico |
|---|---|---|
| Hit-rate | 30/30 | 30/30 |
| `context_precision` | 0.809 | 0.724 |
| `context_recall` | 0.900 | 0.928 |
| `faithfulness` | 0.950 | 0.930 |
| `answer_relevancy` | 0.924 | 0.928 |
| Latencia promedio | 3.6s | 14.4s |
| Tokens de entrada promedio | 2658 | 4348 |

Ninguna diferencia de calidad supera el ruido: `faithfulness` del directo
solo, corrido dos veces en momentos distintos, salió 0.906 y 0.950 — una
variación de ±0.05 entre dos corridas del *mismo* pipeline, sin cambiar
una sola línea de código. Es la prueba concreta de por qué hay que
desconfiar de diferencias chicas con pocas preguntas y un juez
no-determinístico. La única diferencia con margen real y consistente es
`context_precision`, y favorece al directo. Del lado del costo no hay
ambigüedad: agéntico es 4x más lento y consume ~40% más tokens, sin
ninguna ganancia de calidad que lo justifique.

**Veredicto para este corpus: gana el directo.** Pero la salvedad importa
tanto como el resultado — las 30 preguntas del golden set son
mayormente de un solo hecho, donde el directo ya acierta en el primer
intento. Ninguna es genuinamente multi-hop, así que el agéntico nunca
tuvo la oportunidad de mostrar su ventaja teórica (recuperarse de una
primera búsqueda que no alcanzó). El hallazgo real es más angosto y más
honesto que "el agéntico no sirve": *no hace falta pagar su costo cuando
el retrieval directo ya funciona bien sobre este corpus* — que es
exactamente el tipo de conclusión medida, no adivinada, que este bloque
entero existía para poder sacar.
