# Metodología de tipos de dato para la fase de recolección

## 1. Propósito de la fase de recolección

La fase de recolección tiene como objetivo construir un corpus jurídico especializado, trazable y útil para un sistema RAG orientado a consultas sobre violencia familiar en el contexto peruano. Esta fase no consiste únicamente en reunir documentos, sino en clasificar las fuentes según la función que cumplen dentro del sistema y del problema jurídico abordado.

## 2. Principio de organización

Los datos se organizan de acuerdo con su **función jurídica y funcional**. Esta decisión metodológica permite:

- justificar la inclusión de cada fuente,
- definir estrategias de extracción específicas,
- establecer criterios de filtrado diferenciados,
- mantener trazabilidad entre fuente, procesamiento y uso posterior.

## 3. Categorías funcionales de datos

### 3.1. Normativa principal

Corresponde al núcleo normativo directamente orientado al dominio del problema. En esta investigación, la fuente principal es la **Ley N.° 30364**, por regular de forma específica la prevención, sanción y erradicación de la violencia contra las mujeres y los integrantes del grupo familiar.

**Función:**
- servir como base normativa central del sistema,
- definir conceptos, medidas e instituciones principales,
- actuar como fuente prioritaria en las respuestas especializadas.

**Criterio de inclusión:**
- texto vigente consolidado,
- modificaciones relevantes incorporadas,
- prioridad frente a normas complementarias cuando exista regulación específica.

### 3.2. Normativa penal sustantiva complementaria

Incluye artículos relevantes del **Código Penal peruano** vinculados con violencia familiar, violencia contra la mujer, lesiones, feminicidio, violencia sexual y conductas relacionadas.

**Función:**
- complementar la Ley 30364 en la dimensión penal sustantiva,
- identificar delitos y consecuencias penales aplicables,
- ampliar la cobertura jurídica del sistema.

**Criterio de inclusión:**
- artículos directa o temáticamente vinculados al dominio,
- selección mediante heurísticas deterministas,
- validación por revisión humana.

### 3.3. Normativa procesal penal complementaria

Comprende artículos relevantes del **Código Procesal Penal peruano** relacionados con denuncia, investigación, actuación fiscal y policial, protección de víctimas y reglas procesales aplicables.

**Función:**
- responder dudas sobre trámite penal,
- explicar actuación institucional,
- complementar la dimensión sustantiva con procedimiento.

**Criterio de inclusión:**
- artículos vinculados a víctima, agraviado, denuncia, medidas de protección, prueba anticipada, investigación preliminar o preparatoria, actuación fiscal y policial,
- selección mediante heurísticas deterministas,
- validación por revisión humana.

### 3.4. Jurisprudencia relevante

Corresponde a resoluciones judiciales, acuerdos plenarios, casaciones u otros criterios interpretativos relevantes para el dominio.

**Función:**
- aportar contexto interpretativo,
- reforzar criterios de aplicación práctica,
- enriquecer respuestas complejas cuando el texto normativo no sea suficiente.

**Criterio de inclusión:**
- resoluciones con utilidad interpretativa general,
- prioridad para criterios no excesivamente localistas,
- asociación con normas o artículos previamente identificados como relevantes.

### 3.5. Documentos institucionales procedimentales

Incluye protocolos, manuales, guías e instructivos emitidos por entidades como PNP, MIMP, Ministerio Público, Poder Judicial u otras instituciones competentes.

**Función:**
- traducir el marco normativo a rutas prácticas de actuación,
- responder consultas operativas,
- complementar la dimensión jurídica con la dimensión institucional.

**Criterio de inclusión:**
- origen oficial o institucionalmente reconocido,
- aplicabilidad práctica al dominio,
- utilidad para orientación procedimental y acceso a servicios.

## 4. Justificación metodológica

La clasificación por tipos de dato responde a la necesidad de separar normas centrales, normas complementarias, criterios interpretativos y documentos operativos, evitando mezclar fuentes de distinta naturaleza en un solo bloque indiferenciado. Esto mejora la calidad del corpus, permite distintas estrategias de extracción y hace más defendible la metodología de recolección.

## 5. Estrategias de recolección según tipo de dato

- **Normativa principal:** extracción consolidada y actualización incremental.
- **Normativa penal sustantiva:** extracción amplia, filtrado heurístico y revisión humana.
- **Normativa procesal penal:** extracción amplia, filtrado heurístico y revisión humana.
- **Jurisprudencia:** recolección asociada a artículos o normas previamente seleccionados.
- **Documentos institucionales:** extracción centrada en procedimientos, actores y rutas de atención.

## 6. Uso posterior en el sistema RAG

- la normativa principal actúa como fuente de grounding central,
- la normativa complementaria amplía cobertura penal y procesal,
- la jurisprudencia aporta interpretación,
- los documentos institucionales permiten respuestas prácticas y accionables.

## 7. Consideración metodológica sobre las fuentes

En algunos casos se emplean fuentes operativas estructuradas como LP Derecho para facilitar la extracción y actualización. Cuando sea necesario comprobar el texto vigente, estas fuentes deben contrastarse con la publicación oficial correspondiente.
