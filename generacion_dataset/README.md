# Generación del dataset

Esta fase transforma jurisprudencia con hechos suficientemente detallados en ejemplos para entrenamiento contrastivo. Cada ejemplo contiene una pregunta coloquial, uno o más documentos positivos y hard negatives.

## Flujo

| Orden | Script | Función | Red/API | Modifica datos |
|---:|---|---|---:|---:|
| 1 | `prepare_base_inputs.py` | copia snapshots de `recoleccion/` | no | sí |
| 2 | `filter_jurisprudence_candidates.py` | filtra casos de violencia con hechos | no | sí |
| 3 | `download_pdf_candidates.py` | descarga resoluciones | sí | sí |
| 4 | `test_resumeai_sample.py` | prueba un PDF contra ResumeAI-Legal | servicio externo | sí |
| 5 | `run_resumeai_batch.py` | resume el lote y calcula elegibilidad | servicio externo | sí |
| 6 | `audit_candidate_resolution.py` | verifica candidatos sin LLM | no | no por defecto |
| 7 | `generate_colloquial_legal_questions.py` | genera preguntas y selecciona positivos | LLM externo | sí |

`apply_chunk_text_updates.py` y `patch_dataset_chunk_texts.py` son utilidades de migración del pipeline anterior. No forman parte del recorrido limpio recomendado para una ejecución nueva.

## Directorios

- `data/input/`: snapshot copiado desde recolección;
- `data/intermediate/`: filtros, manifiestos de PDF, resúmenes de casos e índice BM25;
- `data/output/legal_questions_dataset/`: preguntas, candidatos, errores, manifiesto y triples;
- `scripts/`: ejecutables y resolver determinístico;
- `tests/`: pruebas sin red;

## Construcción de candidatos

Para cada `case_id`, `legal_candidate_resolver.py` combina:

1. la jurisprudencia del caso;
2. los artículos CP/CPP desde los que fue encontrada;
3. las normas citadas en el resumen de la resolución;
4. las concordancias de todas las páginas ancla.

Los artículos se resuelven contra los archivos completos de Ley 30364, CP y CPP. El LLM recibe el texto literal y solo puede devolver IDs existentes. La jurisprudencia y las concordancias no son positivos automáticos.

Además, se recupera un pool cerrado de 20 distractores BM25. El LLM selecciona
por pregunta únicamente los documentos cercanos que no aportan la respuesta.
El generador rechaza colisiones con los positivos por ID, documento, texto o
referencia de resolución y reintenta hasta tres veces las respuestas inválidas.
Las combinaciones entre sentencias históricas y artículos del snapshot legal
actual quedan etiquetadas para revisión temporal.

## Comprobación local

No requiere dependencias externas, claves ni escritura:

```bash
uv run --frozen python -m unittest discover -s generacion_dataset/tests -v
uv run --frozen python generacion_dataset/scripts/audit_candidate_resolution.py
uv run --frozen python generacion_dataset/scripts/audit_candidate_resolution.py \
  --case-id jp_00008_e0002
```

Después de generar un dataset:

```bash
uv run --frozen python generacion_dataset/scripts/audit_generated_dataset.py
```

En el snapshot actual, la comprobación considera 178 casos elegibles. El CPP ya
incluye sus dos partes (artículos 1-566) y la resolución determinística alcanza
100 % para jurisprudencia del caso, artículos citados, concordancias y artículos
ancla. El informe reproducible se guarda en
`data/intermediate/candidate_resolution_report.json`.

## Ejecución del generador

Requiere entorno instalado y `OPENROUTER_API_KEY`:

```bash
uv sync --frozen
uv run python generacion_dataset/scripts/generate_colloquial_legal_questions.py
```

Por defecto se solicitan hasta cinco preguntas por sentencia, por lo que 178
casos elegibles producen entre 712 y 890 preguntas si todos se procesan.

Advertencia: el comando elimina/reemplaza outputs anteriores de la carpeta `legal_questions_dataset`, reconstruye el índice BM25 en memoria y puede tener costo de API.

Una ejecución completa debe conservar:

- `candidate_sets.jsonl`;
- `questions_with_positive_context.jsonl`;
- `training_triples.jsonl`;
- `generation_errors.jsonl`, si existe;
- `run_manifest.json` con configuración, entradas y conteos;
- `jurisprudencia_chunk_updates.jsonl`.

## Paso siguiente

Después de revisar los outputs, preparar el split:

```bash
uv run --frozen python entrenamiento/scripts/preprocesing_dataset.py \
  --input generacion_dataset/data/output/legal_questions_dataset/training_triples.jsonl \
  --output entrenamiento/data \
  --test_size 0.1 \
  --seed 520
```
