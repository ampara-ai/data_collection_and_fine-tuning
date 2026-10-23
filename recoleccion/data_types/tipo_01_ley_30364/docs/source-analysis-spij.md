# Análisis de fuente: SPIJ libre

Fuente objetivo inicial:

- Página humana: `https://spij.minjus.gob.pe/spij-ext-web/#/detallenorma/H1141065`
- Norma: Ley N.º 30364

## Qué se observó

La página pública de SPIJ **no trae el texto completo directamente renderizado en el HTML inicial**. La app es una SPA (Angular) y luego consulta un backend.

### Frontend detectado

- App Angular
- JS principal referencia backend en:
  - `https://spijwsii.minjus.gob.pe/spij-ext-back/`
  - `https://spijwsii.minjus.gob.pe/spij-ext-solr/`

### Descubrimiento clave

El frontend contiene una ruta de autenticación pública para acceso libre. La app usa credenciales guest embebidas para obtener un token temporal y luego pedir el detalle normativo.

Se identificó este patrón en el JS:

1. `POST https://spijwsii.minjus.gob.pe/spij-ext-back/authenticate`
2. payload público:

```json
{
  "usuario": "spijext",
  "clave": "password",
  "tipo": 0
}
```

3. Respuesta: JSON con `value` = bearer token
4. Luego:
   `GET https://spijwsii.minjus.gob.pe/spij-ext-back/api/detallenorma/H1141065`
   con header:

```http
Authorization: Bearer <token>
```

## Resultado real verificado

El endpoint devuelve JSON con campos útiles:

- `id`
- `codigoNorma`
- `fechaPublicacion`
- `sector`
- `dispositivoLegal`
- `sumilla`
- `textoCompleto`
- `ruta`

Para `H1141065`:

- `codigoNorma`: `Nº 30364`
- `fechaPublicacion`: `2015-11-23`
- `dispositivoLegal`: `LEY`
- `textoCompleto`: HTML largo (~477 KB)

## Implicancia práctica

Esto es bastante mejor que hacer scraping visual del DOM renderizado por navegador. Lo correcto aquí es:

- autenticarse como acceso libre,
- pedir el JSON del detalle,
- almacenar el HTML crudo de `textoCompleto`,
- luego procesarlo offline.

## Ventajas de este enfoque

- Menos frágil que scraping del DOM en navegador
- Más rápido
- Menos dependiente de cambios cosméticos del frontend
- Conserva marcadores de modificaciones `(*)` y referencias cruzadas dentro del HTML

## Riesgos / puntos a vigilar

- El token guest podría cambiar o expirar con distinto comportamiento en el tiempo
- El HTML `textoCompleto` viene mezclado con markup legacy y enlaces internos de SPIJ
- La actualización del texto consolidado puede no ser inmediata respecto a El Peruano

## Recomendación técnica

Para la Ley 30364, usar SPIJ como **fuente base consolidada** y El Peruano como **fuente de vigilancia de cambios recientes**.
