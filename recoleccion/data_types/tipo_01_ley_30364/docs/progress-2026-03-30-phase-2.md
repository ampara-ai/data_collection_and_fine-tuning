# Progreso 2026-03-30 — Fase 2

## Qué se completó

Después de la investigación inicial, se avanzó a una segunda fase práctica: dejar un pipeline base reproducible para adquisición de datos.

### 1. Git configurado localmente para este repo

Configuración aplicada al repositorio:

- `user.name = RenatoVA`
- `user.email = renato.vivas2001@gmail.com`

Primer commit realizado:

- `ae18697` — `feat: document legal data source extraction research`

### 2. Cliente reusable para SPIJ

Se creó `legal_data/spij_client.py` con:

- autenticación guest reutilizable,
- manejo básico de token,
- método para pedir detalle por `norm_id`.

### 3. Cliente reusable para El Peruano

Se creó `legal_data/elperuano_client.py` con:

- búsqueda GraphQL,
- descarga de PDF,
- corrección importante: **no enviar variables GraphQL en `null` cuando el backend se rompe con eso**.

Este detalle era sutil y molesto. El backend puede responder con errores como:

```json
{
  "errors": [{"message": "'hits'"}],
  "data": {"results": null}
}
```

si se mandan ciertos parámetros en `null`. Ya quedó corregido omitiendo variables opcionales ausentes.

### 4. Snapshot de SPIJ para Ley 30364

Se ejecutó snapshot inicial exitoso de `H1141065`.

Salida principal en:

- `data/spij/H1141065/detail.json`
- `data/spij/H1141065/texto_completo.html`
- `data/spij/H1141065/snapshot_meta.json`

Resumen relevante:

- `codigoNorma`: `Nº 30364`
- `fechaPublicacion`: `2015-11-23`
- `textoCompleto_len`: `476996`
- `textoCompleto_sha256`: `49818ceea35eaf6d4917698124b003c17fce44035d70c36e407253af45654c73`

### 5. Escaneo inicial de El Peruano

Se creó `scripts/daily_elperuano_scan.py`.

Qué hace por ahora:

- consulta por fecha y tipos de dispositivo relevantes,
- genera resumen de conteos,
- corre una búsqueda exploratoria con query `30364`,
- descarga PDFs candidatos,
- guarda metadata por documento.

Salida de prueba en:

- `data/elperuano/20250914/scan_summary.json`
- `data/elperuano/20250914/query_30364_results.json`
- `data/elperuano/20250914/candidates/*/document.pdf`

## Resultado de la prueba exploratoria

Con fecha `20250914` y query `30364`, se detectaron 4 candidatos y se descargaron sus PDFs.

Entre ellos apareció uno claramente relevante:

- `2438329-1`
- `RESOLUCION MINISTERIAL`
- sumilla sobre cambio de denominación del servicio CEM → Centro Emergencia Mujer y Familia

Esto es valioso porque conecta con la nota ya visible en el texto consolidado de SPIJ.

## Limitación actual

La extracción automática de texto desde PDF quedó preparada, pero **no pudo ejecutarse** porque en esta máquina no está instalado `pdftotext`.

Error observado:

- `[Errno 2] No such file or directory: 'pdftotext'`

## Conclusión técnica

La parte de adquisición cruda ya está bastante bien encaminada:

- SPIJ: OK
- El Peruano GraphQL: OK
- descarga de PDF: OK
- almacenamiento local estructurado: OK
- extracción de texto PDF: pendiente por dependencia del sistema

## Próximo paso recomendado

Elegir una de estas rutas:

### Ruta A — mantener todo con herramientas del sistema

Instalar `pdftotext`/poppler y seguir con parsing local de PDFs.

Ventajas:
- simple,
- rápido,
- sin dependencias Python extra.

### Ruta B — mover extracción a Python puro

Agregar parser PDF en Python (`pypdf` o similar) para reducir dependencia del host.

Ventajas:
- más portable dentro del repo.

Desventaja:
- la calidad de extracción puede variar.

### Ruta C — enfoque híbrido

- intentar `pdftotext` si existe,
- si no, fallback a parser Python,
- si ambos fallan, dejar PDF crudo y marcarlo para procesamiento posterior.

Esta tercera ruta probablemente es la más sensata.
