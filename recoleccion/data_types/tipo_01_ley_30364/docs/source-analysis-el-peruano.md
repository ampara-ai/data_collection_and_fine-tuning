# Análisis de fuente: Búsquedas El Peruano

Fuente objetivo:

- `https://busquedas.elperuano.pe/`

## Qué se observó

La web actual está montada con **Next.js + Apollo Client**.
No depende exclusivamente de scraping visual del HTML. El frontend consulta una API GraphQL pública.

## Endpoint descubierto

En el bundle de la app se identificó explícitamente:

- `https://busquedas.elperuano.pe/api/graphql`

Además, los resultados devuelven URLs de PDF descargables vía:

- `https://busquedas.elperuano.pe/api/media/...`

## Query principal identificada

El frontend usa una query GraphQL llamada `Generic` que llama a:

- `getGenericPublication`

Variables observadas:

- `fechaIni`
- `fechaFin`
- `institucion`
- `op`
- `paginatedBy`
- `query`
- `start`
- `tipoDispositivo`
- `tipoPublicacion`
- `ci`

Campos de salida relevantes:

- `totalHits`
- `start`
- `hasNext`
- `paginatedBy`
- `hits[].fechaPublicacion`
- `hits[].op`
- `hits[].sumilla`
- `hits[].tipoDispositivo`
- `hits[].tipoPublicacion`
- `hits[].urlPDF`
- `hits[].nombreDispositivo`

## Resultado real verificado

Probamos requests directos a GraphQL y respondieron correctamente con JSON.
También probamos descarga directa de PDF desde `urlPDF` y entregó `application/pdf` sin necesidad de navegador.

## Ejemplo útil para vigilancia diaria

Se puede pedir algo como:

- fecha de hoy
- `tipoPublicacion = NL`
- `tipoDispositivo` en conjunto de interés: `LEY`, `DECRETO SUPREMO`, `DECRETO LEGISLATIVO`, etc.

Luego, por cada hit:

- revisar `sumilla`
- descargar PDF
- extraer texto
- detectar si menciona `Ley N° 30364`, `Ley 30364` o variantes
- clasificar si modifica, precisa, reglamenta, renombra o solo menciona

## Observaciones importantes

### 1. El filtro `query=30364` no es suficiente

Sí devuelve resultados, pero puede traer menciones incidentales, anexos o publicaciones relacionadas pero no modificatorias.
No sirve como único mecanismo de detección.

### 2. Conviene combinar filtros estructurados + lectura del PDF

Mejor estrategia:

1. filtrar por fecha
2. filtrar por tipos normativos de interés
3. traer metadata de hits
4. descargar PDFs candidatos
5. extraer texto y verificar mención real a la Ley 30364

### 3. No vimos bloqueo anti-bot fuerte

Hasta ahora, requests HTTP normales funcionaron para:

- GraphQL
- descarga de PDF

Igual conviene:

- rate limiting moderado
- retries con backoff
- cache local
- logs de errores por si cambian comportamiento

## Recomendación técnica

Usar El Peruano como **fuente de vigilancia incremental diaria** para detectar nuevas normas que puedan afectar la versión consolidada almacenada desde SPIJ.
