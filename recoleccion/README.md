# Fase: Recolección

Esta fase agrupa todo el trabajo relacionado con la **adquisición, extracción, normalización y actualización de datos fuente** para la tesis.

## Objetivo

Construir pipelines confiables para obtener datos jurídicos peruanos y documentos procedimentales útiles para el dominio de violencia familiar, preservando trazabilidad y preparando insumos limpios para las fases posteriores de:

- generación de dataset
- entrenamiento

## Referencia metodológica principal

Antes de revisar los tipos de dato, conviene leer:

- `METODOLOGIA_DATOS.md`

Ese archivo define la clasificación funcional de fuentes usada en la fase de recolección.

## Organización interna

Dentro de esta fase, cada tipo de dato vive en su propio subárbol.

## Tipos de dato implementados

- `data_types/tipo_01_ley_30364/` → normativa principal del dominio
- `data_types/tipo_02_codigo_penal/` → normativa penal sustantiva complementaria
- `data_types/tipo_03_codigo_procesal_penal/` → normativa procesal penal complementaria
- `data_types/tipo_04_jurisprudencia/` → resoluciones y relaciones con artículos
- `data_types/tipo_05_documentos_institucionales/` → orientación y rutas de atención

## Artefactos canónicos

- `data/processed/document_chunks_all.jsonl`: corpus consolidado consumido por generación;
- `data/processed/document_chunks_summary.json`: conteos por tipo y control de vacíos;
- `data_types/*/data/processed/normalized_documents.jsonl`: documentos normalizados por familia;
- `data_types/*/data/processed/document_chunks.jsonl`: chunks antes de consolidar;
- `data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_context_units.json`: casos, procedencia y relaciones jurídicas.

El snapshot consolidado contiene 757 chunks.

## Reproducción desde la raíz del repo

Desde `/` del repositorio:

```bash
uv sync
uv run --frozen python run_recoleccion.py collect
```

O con fecha explícita:

```bash
uv run --frozen python run_recoleccion.py collect 20250914
```

Para modo worker:

```bash
uv run --frozen python run_recoleccion.py worker
```

## Pipeline base documental unificado

Desde `recoleccion/` o desde la raíz del repo se debe poder invocar un runner reproducible para la base documental.

Desde la raíz del repo:

```bash
uv run --frozen python recoleccion/run_base_documental.py plan
```

`plan` es de solo lectura. Los demás subcomandos reconstruyen o descargan artefactos y algunos requieren red o `OPENROUTER_API_KEY`.

Para ejecutar la muestra reproducible actual de jurisprudencia tipo 04:

```bash
uv run --frozen python recoleccion/run_base_documental.py tipo04-sample10
```

Comandos disponibles actualmente para artefactos reales:

```bash
uv run --frozen python recoleccion/run_base_documental.py tipo01-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo01-chunk
uv run --frozen python recoleccion/run_base_documental.py tipo02-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo02-chunk
uv run --frozen python recoleccion/run_base_documental.py tipo03-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo03-chunk
uv run --frozen python recoleccion/run_base_documental.py tipo04-build-seeds
uv run --frozen python recoleccion/run_base_documental.py tipo04-fetch-indexes
uv run --frozen python recoleccion/run_base_documental.py tipo04-parse-entries
uv run --frozen python recoleccion/run_base_documental.py tipo04-resolve-content
uv run --frozen python recoleccion/run_base_documental.py tipo04-summarize
uv run --frozen python recoleccion/run_base_documental.py tipo04-build-contextual-chunks
uv run --frozen python recoleccion/run_base_documental.py tipo04-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo04-chunk
uv run --frozen python recoleccion/run_base_documental.py tipo05-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo05-chunk
uv run --frozen python recoleccion/run_base_documental.py consolidate-chunks
```

Además, sigue disponible la muestra reproducible actual de tipo 04:

```bash
uv run --frozen python recoleccion/run_base_documental.py tipo04-sample10
```

Pipeline recomendado nuevo para tipo 04:

```bash
uv run --frozen python recoleccion/run_base_documental.py tipo04-build-seeds
uv run --frozen python recoleccion/run_base_documental.py tipo04-fetch-indexes
uv run --frozen python recoleccion/run_base_documental.py tipo04-parse-entries
uv run --frozen python recoleccion/run_base_documental.py tipo04-resolve-content
uv run --frozen python recoleccion/run_base_documental.py tipo04-summarize
uv run --frozen python recoleccion/run_base_documental.py tipo04-build-contextual-chunks
```

## Documentación del schema unificado

Ver:

- `recoleccion/docs/unified-normalization-schema.md`

Ese documento define:
- schema unificado de `normalized_document`
- schema unificado de `document_chunk`
- mapeo de `tipo_01` a `tipo_05`
- orden del pipeline base documental

## Principio de diseño

La fase de recolección **no** debería mezclar objetivos de entrenamiento ni de generación de dataset. Aquí se resuelve principalmente:

- de dónde sale la data,
- cómo se descarga,
- cómo se limpia,
- cómo se mantiene actualizada,
- cómo se clasifica según su función jurídica,
- cómo se conserva en formatos humano/máquina.
