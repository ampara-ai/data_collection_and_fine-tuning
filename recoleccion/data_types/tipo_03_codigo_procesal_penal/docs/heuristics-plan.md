# Plan heurístico inicial para Código Procesal Penal

## Objetivo

Reducir el universo total de artículos del CPP a un subconjunto útil para violencia familiar / violencia de género, con foco en procedimiento, denuncia, investigación, protección de víctimas y actuación institucional.

## Observación del HTML

La estructura en LP Derecho replica el patrón útil ya visto:

- `h4` para inicio de artículo
- `p` consecutivos para el contenido
- `p` final con `Ver jurisprudencia aquí.` y enlace asociado

## Estrategia

### Capa 1 — extracción total

Extraer cada artículo con:

- `article_id`
- `heading`
- `title`
- `text`
- `jurisprudence_url`
- `source_url`

### Capa 2 — scoring heurístico

Se priorizan artículos vinculados a:

- víctima / agraviado
- denuncia
- policía / fiscal
- medidas de protección / coerción
- investigación preparatoria
- prueba anticipada
- declaración de víctimas vulnerables
- cámara Gesell / protección especial (si aparece)
- principios de oportunidad y actuación urgente cuando afecte protección de víctimas

### Capa 3 — clasificación preliminar

- `candidate_strong`
- `candidate_medium`
- `candidate_weak`
- `discarded`

## Salidas esperadas

- `data/processed/all_articles.json`
- `data/processed/candidate_articles.json`
- `data/processed/heuristics_summary.json`
