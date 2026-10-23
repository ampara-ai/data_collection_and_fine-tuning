# Schema del subpipeline de prueba para 10 índices jurisprudenciales

## Objetivo

Llegar de forma controlada hasta este punto:

1. seleccionar 10 páginas índice de jurisprudencia por artículo,
2. parsearlas con LLM para extraer categorías y entries,
3. aplanar las entradas,
4. clasificar cuáles son relevantes para casos con antecedentes,
5. resolver y descargar los PDFs de las entradas aceptadas.

Todavía no incluye:
- resumen con ResumeAI-Legal,
- construcción del JSON final `case + context`,
- generación de dataset.

---

# Etapa 0. `input_indices_10.json`

## Propósito
Representar la muestra de 10 páginas índice que se usarán en la prueba.

## Unidad
Una fila por página índice LP Derecho asociada a un artículo.

## Schema
```json
{
  "index_page_id": "jp_0001",
  "index_page_url": "https://lpderecho.pe/...",
  "article_id": "323-b",
  "article_heading": "Violencia psicológica",
  "source_dataset": "tipo_02_codigo_penal",
  "anchor_code": "CP",
  "selection_reason": "sample_batch_10"
}
```

## Campos
- `index_page_id`
- `index_page_url`
- `article_id`
- `article_heading`
- `source_dataset`
- `anchor_code`
- `selection_reason`

---

# Etapa 1. `jurisprudence_index_llm_10.json`

## Propósito
Guardar la salida estructurada por página índice después del parseo LLM.

## Unidad
Una fila por página índice procesada.

## Schema
```json
{
  "index_page_id": "jp_0001",
  "index_page_url": "https://lpderecho.pe/...",
  "article_id": "323-b",
  "article_heading": "Violencia psicológica",
  "llm_parse_status": "success",
  "article": {
    "code": "CP",
    "article_id": "323-b",
    "heading": "Violencia psicológica"
  },
  "categories": [
    {
      "name": "Corte Superior",
      "entries": [
        {
          "title": "Exp. 05935-2021-84 ...",
          "matched_url": "https://lpderecho.pe/..."
        }
      ]
    }
  ],
  "notes": "..."
}
```

## Campos clave
- `index_page_id`
- `index_page_url`
- `article_id`
- `article_heading`
- `llm_parse_status`
- `article`
- `categories`
- `notes`

---

# Etapa 2. `jurisprudence_entries_llm_10.json`

## Propósito
Aplanar todas las entradas de los 10 índices en una lista única de entries.

## Unidad
Una fila por entry jurisprudencial individual.

## Schema
```json
{
  "entry_id": "jp_0001_e0001",
  "index_page_id": "jp_0001",
  "index_page_url": "https://lpderecho.pe/...",
  "article_id": "323-b",
  "article_heading": "Violencia psicológica",
  "entry_category": "Corte Superior",
  "entry_title_raw": "Exp. 05935-2021-84 ...",
  "entry_url": "https://lpderecho.pe/...",
  "resolution_reference_raw": "Exp. 05935-2021-84",
  "jurisprudence_type_hint": "expediente",
  "parse_confidence": "high"
}
```

## Campos
- `entry_id`
- `index_page_id`
- `index_page_url`
- `article_id`
- `article_heading`
- `entry_category`
- `entry_title_raw`
- `entry_url`
- `resolution_reference_raw`
- `jurisprudence_type_hint`
- `parse_confidence`

---

# Etapa 3. `jurisprudence_entries_filtered_10.json`

## Propósito
Clasificar las entradas en aceptadas, condicionales o rechazadas para el objetivo de casos con antecedentes.

## Unidad
Una fila por entry ya clasificado.

## Schema
```json
{
  "entry_id": "jp_0001_e0001",
  "entry_title_raw": "Exp. 05935-2021-84 ...",
  "entry_url": "https://lpderecho.pe/...",
  "entry_category": "Corte Superior",
  "resolution_reference_raw": "Exp. 05935-2021-84",
  "jurisprudence_type_predicted": "sala_superior",
  "relevance_status": "accepted",
  "relevance_reason": "expediente de sala superior con alta probabilidad de contener hechos del caso",
  "needs_llm_review": false
}
```

## Reglas iniciales sugeridas

### `accepted`
- `Exp.` / `Expediente`
- `Sala Superior`
- `Sala Penal Superior`
- `Juzgado Mixto`
- `Juzgado de Familia`
- `Juzgado Penal`

### `conditional`
- `Casación`
- `R.N.` / `Recurso de Nulidad`

### `rejected`
- `Acuerdo Plenario`
- `Doctrina`
- `Doctrina vinculante`
- casación doctrinal sin hechos

---

# Etapa 4. `jurisprudence_pdf_candidates_10.json`

## Propósito
Registrar el intento de resolver el PDF de cada entry aceptado o condicional.

## Unidad
Una fila por entry intentado.

## Schema
```json
{
  "entry_id": "jp_0001_e0001",
  "entry_url": "https://lpderecho.pe/...",
  "relevance_status": "accepted",
  "pdf_url": "https://img.lpderecho.pe/wp-content/...pdf",
  "pdf_found": true,
  "pdf_resolution_status": "success",
  "detail_page_title": "...",
  "resolution_reference_raw": "Exp. 05935-2021-84"
}
```

## Campos
- `entry_id`
- `entry_url`
- `relevance_status`
- `pdf_url`
- `pdf_found`
- `pdf_resolution_status`
- `detail_page_title`
- `resolution_reference_raw`

---

# Etapa 5. `pdf_download_manifest_10.json`

## Propósito
Registrar qué PDFs se descargaron exitosamente en local.

## Unidad
Una fila por PDF descargado o intentado.

## Schema
```json
{
  "entry_id": "jp_0001_e0001",
  "pdf_url": "https://img.lpderecho.pe/...pdf",
  "download_status": "success",
  "local_pdf_path": "recoleccion/data_types/tipo_04_jurisprudencia/data/raw/pdfs/jp_0001_e0001.pdf",
  "sha256": "...",
  "bytes": 1234567
}
```

## Campos
- `entry_id`
- `pdf_url`
- `download_status`
- `local_pdf_path`
- `sha256`
- `bytes`

---

# Resultado esperado de la prueba

Al final de esta corrida de 10 índices deberíamos tener:

- muestra controlada de índices,
- parseo LLM estructurado por índice,
- entries aplanados,
- entries filtrados por relevancia,
- URLs PDF resueltas,
- PDFs locales descargados.

Ese es el punto correcto antes de pasar a resumen con ResumeAI-Legal.
