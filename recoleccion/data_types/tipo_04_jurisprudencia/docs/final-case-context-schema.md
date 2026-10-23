# Final case + context schema for tipo de dato 04

## Objetivo

Definir una unidad final útil para construcción de dataset sintético orientado a contrastive learning de embeddings. Esta unidad no representa solo una resolución o solo una norma, sino un **caso jurisprudencial con su contexto jurídico asociado**.

## Principio de diseño

La unidad final debe servir para:

- preservar trazabilidad hacia LP Derecho y la resolución fuente,
- representar el caso de forma comprensible para generación de queries cotidianas,
- asociar normas ancla y concordancias explícitas,
- dejar señales útiles para construir positivos y hard negatives.

## Estructura general

```json
{
  "unit_id": "case_ctx_000001",
  "source_type": "jurisprudencia",
  "source_trace": {},
  "case_record": {},
  "legal_context": {},
  "dataset_signals": {}
}
```

## 1. source_trace

Preserva la trazabilidad al índice jurisprudencial, al entry original y a la resolución individual.

### Campos sugeridos
- `index_page_id`
- `index_page_url`
- `entry_category`
- `entry_title_raw`
- `entry_url`
- `pdf_url`
- `resolution_reference_raw`

## 2. case_record

Contiene la representación del caso o criterio jurisprudencial, con suficiente densidad semántica para retrieval y generación sintética.

### Campos sugeridos
- `title`
- `resolution_reference`
- `resolution_type`
- `court`
- `chamber`
- `date_text`
- `judge_rapporteur`
- `topic_label`
- `sumilla`
- `highlighted_holding`
- `facts_background`
- `legal_issue`
- `reasoning_summary`
- `decision_summary`
- `participants`

### participants
Subobjeto opcional con:
- `victim_or_claimant`
- `accused_or_investigated`
- `third_parties`

## 3. legal_context

Representa la relación del caso con normas explícitas e inferidas.

### Campos sugeridos
- `anchor_norm`
- `explicit_concordances`
- `inferred_related_norms`
- `institutional_context`

### anchor_norm
Norma principal desde la cual se llegó a la jurisprudencia.

Campos:
- `code`
- `article_id`
- `heading`
- `relation_type`
- `confidence`

### explicit_concordances
Lista de concordancias explícitas obtenidas del índice de LP Derecho.

Campos:
- `code`
- `article_id`
- `relation_type`
- `confidence`

### inferred_related_norms
Normas inferidas posteriormente por LLM o heurística.

Campos:
- `code`
- `article_id`
- `relation_type`
- `confidence`
- `reason`

### institutional_context
Documentos institucionales opcionales vinculados a la necesidad informativa del caso.

Campos:
- `data_type`
- `doc_id`
- `relation_type`
- `confidence`

## 4. dataset_signals

Campos orientados a generación de queries, positivos y hard negatives.

### Campos sugeridos
- `domain_relevance`
- `query_generation_ready`
- `query_generation_source`
- `positive_context_ready`
- `positive_context_strategy`
- `hard_negative_group_keys`
- `needs_human_review`
- `notes_for_generation`

### domain_relevance
Subobjeto con señales como:
- `violencia_familiar`
- `violencia_genero`
- `proteccion_victima`
- `procedural_guidance`

## Recomendación metodológica

### Para generación de queries
Usar principalmente:
- `facts_background`
- `legal_issue`
- `topic_label`

### Para positivos
Usar combinación de:
- `highlighted_holding`
- `sumilla`
- `anchor_norm`
- `explicit_concordances` cuando aporten contexto útil

### Para hard negatives
Agrupar por:
- misma familia temática,
- mismo artículo ancla,
- misma categoría de procedimiento,
- pero distinto problema jurídico o distinta respuesta sustantiva.

## Distinción crítica

No mezclar en un mismo nivel:
- relaciones normativas explícitas,
- relaciones inferidas,
- y contexto institucional opcional.

Estas deben conservarse separadas para evitar contaminar el dataset con asociaciones débiles o arbitrarias.
