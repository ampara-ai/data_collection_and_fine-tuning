# Tipo de dato 01: Ley 30364

Este subárbol contiene todo el trabajo de la fase de **recolección** relacionado con la **Ley N.° 30364** y su actualización incremental.

## Clasificación metodológica

Según `recoleccion/METODOLOGIA_DATOS.md`, este tipo de dato corresponde a:

- **normativa principal**

## Función en el sistema

- servir como fuente normativa central del dominio,
- definir conceptos, medidas e instituciones principales,
- actuar como base primaria de grounding para consultas especializadas.

## Alcance

Incluye:

- snapshot base desde SPIJ
- vigilancia incremental desde El Peruano
- extracción de PDFs y texto
- conversión PDF → imagen para clasificación con LLM cuando aplique
- bootstrap de una versión estructurada local de la ley
- estado del worker y artefactos canónicos de salida

## Estructura

- `docs/` → investigación, decisiones y progreso
- `src/legal_data/` → código reusable del dominio Ley 30364
- `scripts/` → scripts ejecutables para bootstrap, exploración y worker
- `data/raw/` → fuentes crudas descargadas
- `data/processed/` → artefactos estructurados y consolidados
- `data/state/` → estado persistente del worker

## Artefactos principales

- `data/raw/spij/H1141065/` → snapshot bruto de SPIJ
- `data/raw/elperuano/` → candidatos y escaneos diarios desde El Peruano
- `data/processed/ley_30364/current/articles.json` → versión máquina canónica
- `data/processed/ley_30364/current/consolidated.md` → versión humana derivada
- `data/state/worker_state.json` → estado del worker

## Reproducción desde la raíz del repo

El entrypoint recomendado es:

```bash
uv sync
uv run --frozen python run_recoleccion.py collect
```

Con fecha explícita:

```bash
uv run --frozen python run_recoleccion.py collect 20250914
```

Para iniciar el worker:

```bash
uv run --frozen python run_recoleccion.py worker
```

## Ejecución manual avanzada

Si quieres ejecutar scripts sueltos, usa como `PYTHONPATH` la carpeta `src/` de este tipo de dato:

- bootstrap inicial:
  - `PYTHONPATH=recoleccion/data_types/tipo_01_ley_30364/src uv run python recoleccion/data_types/tipo_01_ley_30364/scripts/bootstrap_law_30364.py`
- escaneo exploratorio de El Peruano:
  - `PYTHONPATH=recoleccion/data_types/tipo_01_ley_30364/src uv run --frozen python recoleccion/data_types/tipo_01_ley_30364/scripts/daily_elperuano_scan.py 20250914`
- clasificación vision de un PDF:
  - `PYTHONPATH=recoleccion/data_types/tipo_01_ley_30364/src uv run python recoleccion/data_types/tipo_01_ley_30364/scripts/classify_pdf_with_llm.py <pdf_path>`
- loop diario del worker:
  - `PYTHONPATH=recoleccion/data_types/tipo_01_ley_30364/src uv run python recoleccion/data_types/tipo_01_ley_30364/scripts/run_daily_worker_loop.py`

## Criterio de inclusión

- texto vigente consolidado,
- modificaciones relevantes incorporadas,
- prioridad frente a otras normas cuando exista regulación específica de violencia familiar.

## Nota

Este bloque corresponde únicamente a la fase de recolección. La generación de dataset y el entrenamiento deben vivir fuera de aquí para no contaminar responsabilidades.
