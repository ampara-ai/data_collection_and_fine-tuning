# Tipo de dato 04: Jurisprudencia relevante

Este subárbol contiene la recolección inicial de jurisprudencia relevante asociada a los artículos identificados como candidatos en otras fuentes normativas.

## Clasificación metodológica

Según `recoleccion/METODOLOGIA_DATOS.md`, este tipo de dato corresponde a:

- **jurisprudencia relevante**

## Función en el sistema

- aportar contexto interpretativo,
- reforzar criterios de aplicación práctica,
- asociar resoluciones relevantes a artículos normativos previamente seleccionados,
- servir como proxy de casos jurídicos reales para la futura construcción de dataset sintético orientado a retrieval.

## Alcance actual

Este subárbol ya no debe leerse solo como una recolección plana de URLs. La dirección actual del trabajo es:

1. recolectar páginas índice de jurisprudencia detectadas en tipos 02 y 03,
2. parsear sus entries de forma estructurada,
3. clasificar cuáles entries sí apuntan a casos con antecedentes útiles,
4. resolver y descargar sus PDFs,
5. recién después enriquecer esos PDFs con `ResumeAI-Legal`.

## Estado actual

La prueba inicial de 10 índices se conserva como mecanismo de desarrollo, pero el repositorio ya contiene el pipeline ampliado: construcción de semillas desde CP/CPP, descarga de páginas índice, parseo de entradas, resolución de contenido/PDF, resumen y construcción de unidades contextuales.

El artefacto clave para fases posteriores es `data/processed/jurisprudence_context_units.json`, donde cada `entry_id` conserva sus URLs, artículos de procedencia y contexto jurídico estructurado.

## Prueba local reducida

Desde esta misma carpeta puede correrse la prueba completa de 10 índices con un único runner:

```bash
cd recoleccion/data_types/tipo_04_jurisprudencia
uv run python run_sample_10_pipeline.py
```

Esto ejecuta una muestra, no el corpus completo:
- sample de 10 índices,
- parseo LLM-first,
- clasificación de entries,
- resolución y descarga de PDFs.

## Scripts activos vs experimentales

### Scripts activos
Se consideran parte del flujo principal o reutilizable:
- `build_jurisprudence_corpus.py`
- `parse_jurisprudence_corpus.py`
- `build_index_entries.py`
- `show_index_entries_stats.py`
- `show_jurisprudence_stats.py`
- `show_parsed_jurisprudence_stats.py`
- `enrich_case_with_resumeai_api_sample.py`
- `build_seed_urls_from_tipo_02_03.py`
- `fetch_all_index_pages.py`
- `llm_parse_index_entries.py`
- `resolve_entry_content.py`
- `llm_summarize_jurisprudence.py`
- `build_contextual_chunks.py`

### Scripts experimentales
Los scripts de pruebas LLM o samples ad hoc fueron movidos a:
- `scripts/experimental/`

La idea es separar mejor:
- pipeline reutilizable,
- pruebas exploratorias,
- experimentos de prompting.
