# Tipo de dato 02: Código Penal peruano

Este subárbol contiene el trabajo de recolección orientado a identificar artículos del **Código Penal peruano** potencialmente relacionados con violencia familiar y violencia de género.

## Clasificación metodológica

Según `recoleccion/METODOLOGIA_DATOS.md`, este tipo de dato corresponde a:

- **normativa penal sustantiva complementaria**

## Función en el sistema

- complementar la Ley 30364 en la dimensión penal sustantiva,
- identificar delitos y sanciones relevantes,
- ampliar cobertura jurídica del sistema.

## Objetivo inmediato

No usar LLM todavía.
Primero se busca:

1. parsear el HTML de la fuente seleccionada,
2. extraer todos los artículos,
3. aplicar filtros heurísticos deterministas,
4. generar un subconjunto de candidatos para revisión humana.

## Fuente operativa actual

- `https://lpderecho.pe/codigo-penal-peruano-actualizado/`

## Flujo de esta etapa

- parsing HTML → `all_articles.json`
- scoring heurístico → `candidate_articles.json`
- revisión manual humana de sobrevivientes

## Criterio de inclusión

- artículos directa o temáticamente vinculados con violencia familiar, violencia contra la mujer, lesiones, feminicidio, violencia sexual o conductas conexas,
- selección mediante heurísticas deterministas,
- revisión humana posterior.

## Nota metodológica

La fuente actual es operativa y útil para extracción estructurada, pero no sustituye por sí sola la fuente oficial del Estado. En esta etapa se prioriza eficiencia de recolección y reducción de candidatos.
