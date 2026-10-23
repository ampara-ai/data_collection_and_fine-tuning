# Pipeline inicial para tipo de dato 04

## Objetivo

Materializar como tipo de dato independiente la jurisprudencia que ya fue descubierta indirectamente a través de los artículos del Código Penal y del Código Procesal Penal.

## Fuente de entrada

- `tipo_02_codigo_penal/data/processed/candidate_articles.json`
- `tipo_03_codigo_procesal_penal/data/processed/candidate_articles.json`

Ambos contienen `jurisprudence_url` asociada a artículos candidatos.

## Flujo

1. leer candidatos de tipos 02 y 03,
2. extraer `jurisprudence_url`,
3. deduplicar por URL,
4. descargar HTML,
5. guardar:
   - raw HTML,
   - índice de enlaces,
   - metadata mínima por pieza jurisprudencial.

## Resultado esperado

- corpus inicial de jurisprudencia enlazada
- asociación con artículo origen
- base suficiente para clasificación o filtrado posterior
