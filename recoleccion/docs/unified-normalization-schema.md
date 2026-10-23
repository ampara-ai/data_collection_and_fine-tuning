# Schema unificado de normalización y chunking para la fase de recolección

## Objetivo

Definir una estructura común para todos los tipos de dato de `recoleccion/` de modo que la base documental resultante sea:

- trazable,
- consistente entre fuentes,
- fácil de chunkear,
- portable a cualquier PC,
- separada de la etapa posterior de construcción de casos reales y generación de dataset.

---

# 1. Principio metodológico

La fase de recolección debe producir una **base documental limpia y chunked**. Esta base es independiente de la fase posterior donde se seleccionan jurisprudencias con hechos ricos, se descargan PDFs y se usa `ResumeAI-Legal`.

Por tanto, la salida esperada aquí es una base homogénea de documentos normalizados y chunks, no todavía preguntas ni casos finales.

---

# 2. Schema unificado de normalización

Cada documento fuente debe normalizarse a una unidad `normalized_document`.

```json
{
  "doc_id": "tipo04_jp_000123",
  "doc_type": "jurisprudencia_lp",
  "source_type": "tipo_04_jurisprudencia",
  "source_trace": {},
  "document_metadata": {},
  "content_units": [],
  "normalization_signals": {}
}
```

## 2.1 Campos obligatorios

### `doc_id`
Identificador único y estable del documento normalizado.

Ejemplos:
- `tipo01_ley30364_art_07`
- `tipo02_cp_art_121_b`
- `tipo03_cpp_art_242`
- `tipo04_jp_0001_e0012`
- `tipo05_doc_mimp_guia_001_sec_03`

### `doc_type`
Tipo documental unificado.

Valores recomendados:
- `ley_article`
- `codigo_penal_article`
- `codigo_procesal_penal_article`
- `jurisprudencia_lp`
- `institutional_document_section`

### `source_type`
Tipo de dato de origen dentro de `recoleccion/data_types/`.

Valores:
- `tipo_01_ley_30364`
- `tipo_02_codigo_penal`
- `tipo_03_codigo_procesal_penal`
- `tipo_04_jurisprudencia`
- `tipo_05_documentos_institucionales`

---

## 2.2 `source_trace`

Preserva la trazabilidad a la fuente original.

```json
{
  "source_url": "https://...",
  "source_path": "data/raw/...",
  "source_entity": "spij|lpderecho|mimp|pnp|mp|pj|otro",
  "index_page_id": null,
  "index_page_url": null,
  "entry_id": null,
  "entry_url": null,
  "pdf_url": null,
  "pdf_sha256": null,
  "collected_at": "2026-04-23T00:00:00Z"
}
```

No todos los campos aplican a todos los tipos, pero la estructura debe mantenerse estable.

---

## 2.3 `document_metadata`

Metadatos descriptivos y jurídicos mínimos.

```json
{
  "title": "...",
  "short_title": "...",
  "language": "es",
  "jurisdiction": "Perú",
  "issuing_body": "...",
  "publication_date": "...",
  "document_date_text": "...",
  "resolution_reference": null,
  "resolution_type": null,
  "article_id": null,
  "article_heading": null,
  "chapter": null,
  "section": null,
  "topic_tags": []
}
```

---

## 2.4 `content_units`

Lista de unidades textuales del documento ya limpias.

```json
[
  {
    "unit_id": "tipo04_jp_0001_e0012_clean_md",
    "unit_type": "clean_markdown",
    "text": "...",
    "order": 1
  },
  {
    "unit_id": "tipo04_jp_0001_e0012_summary",
    "unit_type": "retrieval_summary",
    "text": "...",
    "order": 2
  }
]
```

### `unit_type` permitidos
- `clean_markdown`
- `clean_text`
- `retrieval_summary`
- `structured_article_text`
- `section_summary`

---

## 2.5 `normalization_signals`

Señales útiles para revisión y chunking.

```json
{
  "normalization_status": "success",
  "summary_status": "pending",
  "chunking_ready": true,
  "needs_review": false,
  "notes": null
}
```

---

# 3. Schema unificado de chunk

La unidad final para embeddings debe ser `document_chunk`.

```json
{
  "chunk_id": "chunk_tipo04_jp_0001_e0012_01",
  "doc_id": "tipo04_jp_0001_e0012",
  "doc_type": "jurisprudencia_lp",
  "source_type": "tipo_04_jurisprudencia",
  "chunk_type": "retrieval_summary",
  "title": "...",
  "text": "...",
  "order": 1,
  "metadata": {},
  "retrieval_tags": []
}
```

## 3.1 Campos obligatorios

- `chunk_id`
- `doc_id`
- `doc_type`
- `source_type`
- `chunk_type`
- `title`
- `text`
- `order`
- `metadata`
- `retrieval_tags`

## 3.2 `chunk_type`

Valores recomendados:
- `article_full`
- `article_subchunk`
- `jurisprudence_summary`
- `jurisprudence_excerpt`
- `institutional_section`
- `institutional_summary`

## 3.3 `metadata`

```json
{
  "source_url": "...",
  "article_id": null,
  "resolution_reference": null,
  "resolution_type": null,
  "issuing_body": null,
  "topic_tags": [],
  "parent_unit_type": "retrieval_summary"
}
```

---

# 4. Mapeo por tipo de dato

## 4.1 tipo_01_ley_30364

### Unidad de normalización
- un documento por artículo

### doc_type
- `ley_article`

### content_units
- `structured_article_text`
- opcional `retrieval_summary`

### chunk recomendado
- `article_full`
- subchunks solo si el artículo es muy largo

---

## 4.2 tipo_02_codigo_penal

### Unidad de normalización
- un documento por artículo del Código Penal

### doc_type
- `codigo_penal_article`

### content_units
- `structured_article_text`
- opcional `retrieval_summary`

### chunk recomendado
- `article_full`
- `article_subchunk` cuando corresponda

---

## 4.3 tipo_03_codigo_procesal_penal

### Unidad de normalización
- un documento por artículo del Código Procesal Penal

### doc_type
- `codigo_procesal_penal_article`

### content_units
- `structured_article_text`
- opcional `retrieval_summary`

### chunk recomendado
- `article_full`
- `article_subchunk` cuando corresponda

---

## 4.4 tipo_04_jurisprudencia

### Unidad de normalización
- un documento por entry individual de LP Derecho

### doc_type
- `jurisprudencia_lp`

### Decisión metodológica clave
Todas las jurisprudencias deben entrar a la base documental chunked, tengan o no hechos ricos, tengan o no PDF descargado, y tengan o no antecedentes procesales suficientes para el dataset final.

### content_units
- `clean_markdown` derivado del HTML detail page
- `retrieval_summary` generado desde ese markdown limpio

### chunk recomendado
- `jurisprudence_summary`
- opcional `jurisprudence_excerpt` si luego se necesita granularidad adicional

### Nota crítica
Este resumen base documental **no** es el de `ResumeAI-Legal`.
Es un resumen de retrieval hecho desde el HTML de LP Derecho.

---

## 4.5 tipo_05_documentos_institucionales

### Unidad de normalización
- un documento por sección/bloque temático

### doc_type
- `institutional_document_section`

### content_units
- `clean_text` o `clean_markdown`
- `section_summary`

### chunk recomendado
- `institutional_section`
- `institutional_summary`

---

# 5. Orden del pipeline base documental

Este pipeline debe quedar separado de la fase de construcción de casos reales.

## Etapa 1. Recolección y limpieza por tipo
- tipo 01: Ley 30364 por artículos
- tipo 02: Código Penal por artículos
- tipo 03: Código Procesal Penal por artículos
- tipo 04: jurisprudencias LP por entry detail page
- tipo 05: documentos institucionales por sección/bloque

## Etapa 2. Normalización unificada
Cada tipo produce `normalized_document` con la misma estructura.

## Etapa 3. Resumen base documental
Generar `retrieval_summary` o `section_summary` según corresponda.

## Etapa 4. Chunking unificado
Transformar `normalized_document` a `document_chunk`.

## Etapa 5. Consolidación
Unir todos los chunks en una sola base documental reproducible.

---

# 6. Artefactos recomendados

## Por tipo de dato
- `data/processed/normalized_documents.jsonl`
- `data/processed/document_chunks.jsonl`

## Consolidado global de recolección
- `recoleccion/data/processed/unified_normalized_documents.jsonl`
- `recoleccion/data/processed/unified_document_chunks.jsonl`

---

# 7. Alcance explícito

Este pipeline llega hasta:
- documentos limpios,
- documentos resumidos para retrieval,
- chunks listos para embeddings.

No incluye todavía:
- filtrado final de casos reales,
- descarga obligatoria de PDFs para todas las jurisprudencias,
- enriquecimiento con `ResumeAI-Legal`,
- generación de preguntas,
- armado del dataset contrastivo.

Esas tareas pertenecen a una fase posterior.
