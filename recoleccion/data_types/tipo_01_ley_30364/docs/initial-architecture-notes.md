# Notas iniciales de arquitectura de recolección

## Objetivo real

Mantener una versión final y actualizada de la Ley 30364 y, después, extender el mismo patrón a otras normas y fuentes jurídicas peruanas relevantes para el sistema RAG.

## Estrategia base propuesta

### Capa 1: fuente consolidada base

Para una norma principal como la Ley 30364:

- usar SPIJ libre como snapshot consolidado de referencia,
- guardar:
  - metadata JSON,
  - HTML crudo de `textoCompleto`,
  - hash del contenido,
  - fecha de extracción.

### Capa 2: vigilancia incremental

Usar El Peruano diariamente para detectar nueva normativa potencialmente relevante:

- Ley
- Decreto Supremo
- Decreto Legislativo
- eventualmente Resolución Ministerial, si impacta interpretación operativa o denominaciones relevantes

### Capa 3: triage documental

Por cada publicación candidata:

1. metadata desde GraphQL
2. descarga del PDF
3. extracción de texto
4. detección de mención a Ley 30364 o artículos relevantes
5. clasificación preliminar:
   - modifica directamente
   - reglamenta
   - precisa/renombra
   - menciona sin modificar
   - irrelevante

### Capa 4: consolidación

No hacer consolidación automática a ciegas.
Primero conviene producir un artefacto estructurado de cambios detectados y recién luego aplicar LLMs o reglas para actualizar la versión final.

## Por qué esta arquitectura tiene sentido

Porque mezcla lo mejor de ambos mundos:

- SPIJ da texto consolidado usable
- El Peruano da inmediatez y trazabilidad oficial de publicación

Si intentaras depender solo de SPIJ, vas a llegar tarde a cambios nuevos.
Si dependieras solo de PDFs de El Peruano, la consolidación sería más pesada y frágil.

## Siguiente entregable técnico razonable

Un pequeño cliente reproducible con scripts para:

- obtener token guest de SPIJ,
- descargar detalle de una norma por id,
- consultar El Peruano por fecha/tipo,
- descargar PDFs candidatos.

Todavía sin LLM. Solo adquisición confiable de datos crudos.
