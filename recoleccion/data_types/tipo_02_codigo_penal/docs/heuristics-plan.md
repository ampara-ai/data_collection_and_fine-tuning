# Plan heurístico inicial para Código Penal

## Objetivo

Reducir ~400 artículos del Código Penal a un subconjunto manejable de candidatos relacionados con violencia familiar / violencia de género, sin usar LLM en esta fase.

## Estructura de extracción observada en LP Derecho

La página del código presenta una estructura parseable:

- cada artículo inicia en un `h4`
- el contenido del artículo aparece en `p` consecutivos
- al final suele aparecer un `p` con el texto `Ver jurisprudencia aquí.` y un enlace asociado

## Estrategia

### Capa 1 — extracción total

Extraer todos los artículos con:

- `article_id`
- `heading`
- `title`
- `text`
- `jurisprudence_url` (si existe)
- `source_url`

### Capa 2 — scoring heurístico

Asignar puntaje por coincidencias en:

- título del artículo
- texto
- URL/anchor de jurisprudencia (si aporta contexto)

### Capa 3 — clasificación determinista preliminar

Etiquetas posibles:

- `candidate_strong`
- `candidate_medium`
- `candidate_weak`
- `discarded`

## Grupos de keywords

### Grupo fuerte

- violencia familiar
- grupo familiar
- mujer
- mujeres
- feminicidio
- agresiones contra las mujeres
- violencia contra la mujer
- conviviente
- ex conviviente
- cónyuge
- expareja
- pareja
- violencia sexual
- violación
- tocamientos
- menor de edad
- niño
- niña
- adolescente

### Grupo medio

- lesiones
- amenaza
- coacción
- acoso
- hostigamiento
- desobediencia
- resistencia a la autoridad
- vulnerabilidad
- dependencia
- maltrato

### Grupo contextual

- familiar
- hogar
- doméstico
- protección
- víctima
- agravio

## Regla inicial de scoring

- keyword fuerte en título: +7
- keyword fuerte en texto: +5
- keyword media en título: +4
- keyword media en texto: +3
- keyword contextual en título: +2
- keyword contextual en texto: +1
- bonus si hay varias familias de términos relevantes: +3
- bonus si aparecen términos de mujer + violencia / lesiones / amenaza en combinación: +4

## Umbrales preliminares

- `score >= 12` → `candidate_strong`
- `score 7-11` → `candidate_medium`
- `score 4-6` → `candidate_weak`
- `score < 4` → `discarded`

## Salidas esperadas

- `data/processed/all_articles.json`
- `data/processed/candidate_articles.json`
- `data/processed/heuristics_summary.json`
