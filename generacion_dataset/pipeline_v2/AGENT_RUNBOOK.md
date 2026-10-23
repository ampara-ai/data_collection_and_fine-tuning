# Runbook para el agente que responde las tareas (Claude Code, Codex u otro)

Los pasos 02, 03, 05 y 07 (pooling) del pipeline dejan **una petición por tarea** en
`<out-dir>/work/<paso>/requests/<task_id>.json` y esperan la respuesta en
`<out-dir>/work/<paso>/responses/<task_id>.json`. Cualquier agente con acceso al sistema de archivos sirve.

## Qué hacer con cada petición
1. Lee el JSON de la petición: `system` (instrucciones y formato de salida), `user` (la entrada) y
   `write_response_to` (ruta ABSOLUTA donde escribir).
2. Aplica `system` al pie de la letra sobre `user` y produce el objeto JSON que pide el formato de salida.
3. Añade la clave `"_model"` con el nombre real del modelo que responde (queda registrado como procedencia).
4. Escribe SOLO ese objeto JSON (válido, sin markdown) en `write_response_to`. No modifiques ningún otro archivo.

## Reglas que cambian la calidad
* **Pasos 02 y 03 (generación):** voz ciudadana, sin citar artículos ni leyes, parafrasea (menos del 20 % de las palabras de
  contenido de la pregunta pueden estar en el chunk). Mide el solapamiento con
  `from common import lexical_overlap` (carpeta `pipeline_v2/`) y reescribe lo que pase de 0,25.
* **Paso 05 (juez):** lee el texto COMPLETO de cada chunk; sé estricto con "si"; no asumas por qué un chunk está en la lista.
  Debes dar un veredicto por cada par (dataset_id, chunk_id) pedido, copiando los ids exactos.
* No juzgues con otra vara en medio del lote: si dudas entre "si" y "parcial", elige "parcial".

## Reparto entre varios agentes
`python pending_tasks.py --out-dir <DIR> --step <paso> --shard K/N` imprime las rutas que le tocan al agente K de N
(solo las que aún no tienen respuesta). Tras terminar, vuelve a ejecutar el paso del pipeline para validar: dirá cuántas
respuestas faltan o están mal formadas, y se corrige borrando ese archivo de `responses/` y repitiendo la tarea.

## Recomendación sobre quién hace qué
* Generación (pasos 02 y 03) y juez (paso 05) conviene que los haga **un modelo distinto cada uno**: así el juez es
  independiente del generador. No mezcles dos jueces en el mismo lote sin registrarlo: `_model` queda en
  `judgments.jsonl` y en `manifest.json` (`provenance`).
* Para estimar el acuerdo entre jueces, haz juzgar una muestra (~100 pares) a ambos y compara.
