# Tipo de dato 03: Código Procesal Penal peruano

Este subárbol contiene el trabajo de recolección orientado a identificar artículos del **Código Procesal Penal peruano** potencialmente relevantes para violencia familiar y violencia de género.

## Clasificación metodológica

Según `recoleccion/METODOLOGIA_DATOS.md`, este tipo de dato corresponde a:

- **normativa procesal penal complementaria**

## Función en el sistema

- explicar denuncia, investigación y actuación institucional,
- complementar la dimensión sustantiva con procedimiento,
- responder dudas sobre trámite penal aplicable.

## Objetivo inmediato

Sin usar LLM todavía:

1. parsear el HTML del CPP desde LP Derecho,
2. extraer todos los artículos,
3. aplicar heurísticas deterministas para reducir candidatos,
4. dejar sobrevivientes en JSON para revisión humana.

## Fuentes operativas actuales

- parte 1, título preliminar-artículo 445: `https://lpderecho.pe/nuevo-codigo-procesal-penal-peruano-actualizado/`
- parte 2, artículo 446-artículo 566: `https://lpderecho.pe/nuevo-codigo-procesal-penal/`

LP Derecho divide el código en esas dos páginas. El recolector exige que, tras
fusionarlas, estén presentes todos los identificadores numéricos del 1 al 566;
también conserva el título preliminar y artículos insertados como `201-A`.

## Criterio de inclusión

- artículos relacionados con víctima, agraviado, denuncia, medidas de protección, prueba anticipada, investigación preliminar o preparatoria, actuación fiscal y policial,
- selección mediante heurísticas deterministas,
- revisión humana posterior.

## Flujo de esta etapa

- descarga de las dos partes → `data/raw/codigo_procesal_penal_lpderecho_parte_{1,2}.html`
- resumen de la descarga → `data/raw/collection_summary.json`
- parsing y fusión con validación 1-566 → `all_articles.json`
- scoring heurístico → `candidate_articles.json`
- revisión manual humana de sobrevivientes

## Ejecución

Desde la raíz del repositorio:

```bash
PYTHONPATH=recoleccion/data_types/tipo_03_codigo_procesal_penal/src \
  uv run python \
  recoleccion/data_types/tipo_03_codigo_procesal_penal/scripts/fetch_and_filter_cpp.py
```

Este paso no usa LLM. La jurisprudencia enlazada se conserva únicamente como
metadato; no se vuelve a buscar ni procesar.
