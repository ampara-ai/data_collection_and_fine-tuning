# Integración con SummaryService API

## Objetivo

Usar `SummaryService` como motor externo de análisis de PDFs jurídicos escaneados sin depender de paths compartidos entre máquinas.

## Contrato de integración

`peru-legal-rag-data` envía:
- el PDF por `multipart/form-data`
- flags simples (`verbose`, `similarity_threshold`)

`SummaryService` responde con JSON que incluye:
- `status`
- `run_id`
- `warnings`
- `errors`
- `metrics`
- `report`

## Cliente implementado

Archivo:
- `src/legal_data/summary_service_client.py`

Funciones principales:
- `analyze_pdf_with_summary_service(...)`
- `persist_enriched_case(...)`

## Output enriquecido local

El cliente construye un objeto `SummaryEnrichedCase` con:
- `source_trace`
- `summary_service_run`
- `report`
- `metrics`
- `factual_density_signals`

## Señales de riqueza fáctica

Se calculan heurísticas simples a partir de `legal_analysis`:
- `has_case_background`
- `has_reported_acts`
- `has_evidence_summary`
- `has_legal_reasoning`
- `has_procedural_outcomes`
- `norms_count`
- `factual_richness_score`
- `is_fact_rich_minimum`
- `is_dataset_candidate`

## Uso esperado en pipeline

1. filtrar tipos de jurisprudencia útiles,
2. descargar PDF,
3. enviar PDF a SummaryService API,
4. persistir respuesta enriquecida en `tipo_04`,
5. decidir si el caso entra al JSON final `case + context`.

## Nota metodológica

La API de `SummaryService` enriquece y resume.
La decisión final de aceptar o rechazar una jurisprudencia para dataset debe seguir viviendo en `peru-legal-rag-data`.
