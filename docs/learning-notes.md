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
