# Schema plan para tipo de dato 04: jurisprudencia relevante

## Objetivo

Evolucionar el tipo 04 desde una colección de páginas LP Derecho hacia un dataset estructurado en dos capas que permita:

- preservar el índice jurisprudencial por artículo,
- representar cada entry jurisprudencial como unidad independiente,
- seguir luego el link individual para extraer detalles del caso,
- construir pares y triples para contrastive learning de embeddings.

## Capa 1: index-entry layer

Esta capa representa la información disponible en las páginas índice de LP Derecho organizadas por artículo.

### Archivo sugerido
- `data/processed/jurisprudence_entries_structured.json`

### Unidad
Una fila por entry individual bajo una categoría (Corte Suprema, Corte Superior, Legislación, etc.).

### Campos
- `entry_id`
- `page_id`
- `page_source_url`
- `entry_category`
- `entry_type`
- `entry_prefix_flags`
- `entry_text`
- `entry_title_candidate`
- `resolution_reference_raw`
- `resolution_type`
- `resolution_number`
- `resolution_year`
- `resolution_jurisdiction`
- `lp_entry_url`
- `short_link_url`
- `page_anchor_code`
- `page_anchor_article_id`
- `page_anchor_article_heading`
- `page_concordances`
- `related_norms`
- `domain_relevance_candidate`

### Tipos de relación normativa
- `page_anchor`
- `page_concordance`
- `content_inference`

## Capa 2: case-detail layer

Esta capa representa la información obtenida al seguir el link individual de cada entry.

### Archivo sugerido
- `data/processed/jurisprudence_case_details.json`

### Unidad
Una fila por página individual de jurisprudencia / doctrina / resolución publicada por LP Derecho.

### Campos
- `entry_id`
- `lp_case_url`
- `page_title`
- `h1_title`
- `highlighted_holding`
- `sumilla`
- `court_name`
- `chamber_name`
- `resolution_reference`
- `resolution_type`
- `resolution_number`
- `resolution_year`
- `resolution_jurisdiction`
- `date_text`
- `reporting_judge`
- `facts_text`
- `background_text`
- `legal_reasoning_text`
- `decision_text`
- `pdf_url`
- `noise_flags`
- `detail_parse_status`

## Uso metodológico

### Para retrieval
- usar `entry_text`, `highlighted_holding`, `sumilla` y `facts_text` como fuentes principales de recuperación.

### Para synthetic dataset
- generar queries cotidianas desde `facts_text` o `background_text`,
- usar como positivo principal el `highlighted_holding` o `sumilla`,
- usar como contexto complementario `related_norms`.

## Uso de LLM recomendado

### No usar LLM para
- parsear categorías,
- extraer concordancias,
- separar entries,
- extraer links,
- extraer metadatos básicos de resolución si regex basta.

### Sí usar LLM para
- resumir hechos desde resoluciones largas,
- clasificar relevancia fina al dominio,
- generar queries cotidianas,
- inferir relaciones adicionales con Ley 30364 cuando no sean explícitas.
