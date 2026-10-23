# Pipeline híbrido propuesto para Ley 30364

## Objetivo

Mantener una versión consolidada y actualizada de la Ley 30364, usando:

- SPIJ como fuente base consolidada inicial
- El Peruano como vigilancia incremental
- LLM por visión para PDFs de El Peruano
- estado estructurado local para aplicar cambios

## Decisiones tomadas

- Fuente canónica de salida: JSON estructurado
- Salida humana derivada: Markdown
- Log de cambios: JSONL
- PDFs de El Peruano → visión por imágenes
- Ley base de SPIJ → procesamiento estructurado desde HTML/texto, no visión
- Worker diario a las 10:00 AM hora Perú
- También guardar cambios regulatorios relacionados aparte

## Artefactos principales

- `data/processed/ley_30364/current/articles.json`
- `data/processed/ley_30364/current/consolidated.md`
- `data/processed/ley_30364/change_log.jsonl`
- `data/processed/ley_30364/related_updates.json`
- `data/state/worker_state.json`

## Tipos de cambios estructurados

- `replace_article`
- `add_article`
- `repeal_article`
- `replace_block`
- `global_reference_rename`
- `related_regulatory_update`

## Flujo resumido

1. bootstrap de Ley 30364 desde SPIJ
2. parsing local inicial
3. consolidación asistida por LLM si hay ruido histórico o ambigüedad
4. guardar estado canónico
5. cada día a las 10:00 AM (Lima):
   - consultar El Peruano
   - bajar PDFs candidatos
   - convertir PDF a imágenes (2 páginas por imagen)
   - pedir clasificación/extracción estructurada al LLM
   - aplicar cambios si corresponden
   - guardar actualizaciones relacionadas aparte
