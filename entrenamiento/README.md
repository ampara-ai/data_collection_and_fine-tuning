# Entrenamiento y evaluación

Esta fase prepara los archivos consumidos por el fine-tuning de embeddings y los notebooks de evaluación.

## Regla central del split

La unidad de separación es la sentencia (`case_id`), no la pregunta. Todas las preguntas provenientes de una sentencia quedan exclusivamente en train o exclusivamente en test.

```text
train_cases ∩ test_cases = ∅
```

Esto evita que una formulación del mismo caso aparezca durante el entrenamiento y otra durante la evaluación.

## Entrada

```text
generacion_dataset/data/output/legal_questions_dataset/training_triples.jsonl
```

Cada fila debe contener al menos:

- `query`;
- `pos` como lista de textos;
- `neg` como lista de textos;
- `case_id`;
- `dataset_id`.

## Salidas

| Archivo | Uso |
|---|---|
| `data/training.json` | ejemplos de entrenamiento en formato compatible con FlagEmbedding |
| `data/corpus.jsonl` | documentos positivos indexables |
| `data/test_queries.jsonl` | consultas reservadas para evaluación |
| `data/test_qrels.jsonl` | relevancia query-documento |
| `data/split_manifest.json` | estrategia, semilla y sentencias de cada partición |

El snapshot actual contiene 800 filas de train y 100 queries de test, repartidas entre 160 y 18 sentencias respectivamente.

## Construir el split

Este comando reemplaza los archivos de `entrenamiento/data/`:

```bash
uv run --frozen python entrenamiento/scripts/preprocesing_dataset.py \
  --input generacion_dataset/data/output/legal_questions_dataset/training_triples.jsonl \
  --output entrenamiento/data \
  --test_size 0.1 \
  --seed 520
```

El script falla si falta `case_id`, existen menos de dos sentencias o se detecta fuga entre particiones.

## Comprobación sin modificar datos

```bash
uv run --frozen python entrenamiento/scripts/audit_training_split.py
```

El comando verifica:

- cero sentencias compartidas;
- coincidencia con `split_manifest.json`;
- presencia de todos los `qid` y `docid`;
- coherencia de `case_id` entre query, qrel y documento;
- IDs duplicados y campos faltantes.

## Notebooks

- `notebooks/eda_dataset_ampara.ipynb`: análisis exploratorio;
- `notebooks/finetuning_bge_m3_ampara.ipynb`: fine-tuning;
- `notebooks/benchmark_finetuning_bge_m3_ampara.ipynb`: comparación y evaluación.

Los notebooks son consumidores de los artefactos, no la fuente de verdad del split. La fuente reproducible es `preprocesing_dataset.py` junto con `split_manifest.json`.
