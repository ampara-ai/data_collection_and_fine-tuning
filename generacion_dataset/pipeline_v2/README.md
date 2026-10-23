# Pipeline v2 de generación de datasets (entrenamiento + evaluación)

Reemplaza a `scripts/generate_colloquial_legal_questions.py` **sin tocarlo** (el v1 borra sus salidas al arrancar; v2
escribe en `data/output/dataset_v2/`). Reutiliza del v1 solo el resolutor de candidatos y los helpers de lectura.

Se puede ejecutar con la API (`--backend openrouter`) o **sin API, con una sesión de Claude Code** (`--backend session`):
el script escribe cada petición en un archivo y consume la respuesta que deje otra sesión; los dos modos comparten la
misma caché y producen los mismos archivos.

## Qué corrige respecto de v1 (y por qué)

| Problema detectado en el dataset v1 | Evidencia | Cambio en v2 |
|---|---|---|
| El tipo de fuente delata la etiqueta: 0 % de los negativos eran de la Ley 30364 (45 % de los positivos), 32 % CPP (3 % de los positivos) | análisis de `training.json` | Paso 4: negativos del mismo tipo que los positivos; el paso 6 exige AUC del tipo ≤ 0,55 |
| El pool de negativos excluía toda la norma (`resolution_reference`) de **cualquier** candidato del caso | `build_negative_candidate_pool` | Se excluyen solo los positivos, sus duplicados, los artículos hermanos (22-A/22) y los casi idénticos |
| Los positivos de los artículos más citados eran textos inflados/duplicados/de otra versión (33 % de las filas) | 16 textos que no calzan con ningún chunk | Los textos salen del corpus por `chunk_id`; el paso 6 comprueba que son idénticos |
| Solo 3 % de positivos del CPP (50 % del corpus); unos pocos artículos concentran cientos de filas | art. 8: 131 filas, art. 5: 96 | Preguntas generadas desde chunks (cobertura total), topes por chunk y cuota de CPP/jurisprudencia |
| Un mismo LLM escribe la pregunta, elige positivos y negativos (circularidad); sin verificación | — | Paso 5: juez independiente, ciego al rol; negativos "sí" se promueven, "parcial" se descartan |
| Partición por sentencia: los chunks de test ya estaban en el entrenamiento | 37 de 37 positivos del test | Paso 1: partición **por chunk** antes de generar; dev/test no aparecen ni como negativo |
| Preguntas con mucho solapamiento léxico con el chunk (0,27) | set unseen original | Instrucciones anti-solapamiento + filtro (`MAX_LEXICAL_OVERLAP = 0.30`) |
| Sin trazabilidad (`temperature=0.3`, sin semilla ni hashes) | — | `manifest.json` con semilla, parámetros, modelos y SHA256 de entradas/salidas |

## Pasos

```
01_split_chunks.py      partición train/dev/test por chunk (estable, agrupa duplicados). Sin LLM.
02_case_questions.py    preguntas basadas en casos (resumen + candidatos cerrados), solo candidatos de train.   [LLM]
03_chunk_questions.py   preguntas basadas en chunks: train (4 por chunk), dev y test (2 por chunk).            [LLM]
04_select_negatives.py  hard negatives del mismo tipo de fuente (BM25), solo de train. Sin LLM.
05_judge.py             juez independiente de positivos / negativos / chunk de origen.                         [LLM]
06_build_dataset.py     training.json + eval_{dev,test}_* + auditorías + manifest.json. Sin LLM.
07_pool_eval.py         completa los qrels de dev/test por pooling (export -> juez -> ingest). Formato = quantitative_experiments.
pending_tasks.py        lista/reparte (--shard K/N) las tareas pendientes de un paso entre varios agentes.
AGENT_RUNBOOK.md        instrucciones para el agente que responde las tareas (Claude Code, Codex...).
run_mock_e2e.sh         prueba de punta a punta con respuestas sintéticas (no genera datos reales).
```

Cada paso que usa LLM acepta `--backend openrouter | session | mock`. Las salidas viven en `data/output/dataset_v2/`.

## Ejecución

```bash
cd generacion_dataset/pipeline_v2
PY=../../.venv/bin/python

$PY 01_split_chunks.py                       # 1. partición (revisar la lista de chunks excluidos que imprime)
$PY 02_case_questions.py  --backend session  # 2. casos
$PY 03_chunk_questions.py --backend session  # 3. chunks (train + dev + test)
#   -> con --backend session cada comando termina con código 3 y la lista de respuestas pendientes (ver abajo)
$PY 04_select_negatives.py                   # 4. negativos (necesita 02 y 03 completos)
$PY 05_judge.py --backend session            # 5. juez
$PY 06_build_dataset.py                      # 6. dataset final + auditorías (código 2 si alguna falla)

# 7. qrels de test por pooling (tras fijar modelos y parámetros). Los rankings salen de backend/quantitative_experiments:
$PY 07_pool_eval.py export --split test --runs <runs/*.json> --depth 10   # arma el pool y las peticiones del juez
$PY pending_tasks.py --out-dir ../data/output/dataset_v2 --step 07_pool_test --shard 1/3   # repartir entre agentes
$PY 07_pool_eval.py ingest --split test      # convierte respuestas -> qrels ampliados + muestra humana
```

### Modo `session` (sin API)

1. El paso escribe una petición por tarea en `data/output/dataset_v2/work/<paso>/requests/<task_id>.json`
   (`system`, `user`, `write_response_to`).
2. Una sesión de Claude Code reparte los archivos entre subagentes. Cada subagente lee `system` + `user`, produce **solo
   el JSON** que pide el formato de salida del prompt y lo guarda en la ruta `write_response_to`.
3. Se vuelve a ejecutar el mismo paso: lee las respuestas, valida, y deja lo que falte como pendiente. Es reanudable;
   una respuesta inválida se corrige borrando su archivo y repitiendo la tarea.

Tamaño por tarea (para repartir): casos ≈ 9.000 tokens de entrada; chunks (6 por tarea) ≈ 10.000; juez (5 preguntas)
≈ 6.000. Con los valores por defecto: 132 tareas de casos, 124 de chunks y ~700 del juez (más ~100 de pooling por split).

## Ejecución por olas (ver resultados antes de generar todo)

Las olas son **fracciones acumuladas** de casos y de chunks (`--fraction 0.2`, luego `0.5`, `0.8`, `1.0`). Cada ola es un prefijo de
un orden aleatorio estable, así que la de 20 % queda contenida en la de 50 % y **lo ya generado y juzgado se reutiliza**.
Cada ola recorre los seis pasos y deja una foto en `snapshots/ola_<fracción>/` para compararlas.

```bash
F=0.2
$PY 01_split_chunks.py                                   # una sola vez; congela corpus y prompts (freeze.json)
$PY 02_case_questions.py  --backend session --fraction $F
$PY 03_chunk_questions.py --backend session --fraction $F
#   -> los agentes responden las tareas pendientes (pending_tasks.py --shard K/N); repetir 02 y 03 hasta 0 pendientes
$PY 04_select_negatives.py
$PY 05_judge.py --backend session                        # solo pide los PARES que faltan (almacén judgments_store.jsonl)
#   -> el juez (Codex) responde; repetir 05 hasta 0 pendientes
$PY 06_build_dataset.py --snapshot ola_$F --no-fail      # --no-fail en olas parciales: las auditorías se informan sin abortar
```

Notas: (1) los negativos del paso 4 se recalculan en cada ola porque dependen de la distribución por tipo de todos los
positivos; ~15 % de lo juzgado en una ola queda obsoleto en la siguiente (el resto se reutiliza). (2) Con pocos datos el AUC
del tipo de fuente y las tasas de omisión son ruidosos: se leen en las olas grandes. (3) El corpus y los prompts no pueden
cambiar entre olas (`CONGELADO ROTO`).
`run_mock_waves.sh` prueba el mecanismo completo con respuestas sintéticas.

## Parámetros importantes (`config.py`)

| Parámetro | Valor | Qué controla |
|---|---|---|
| `TEST_FRAC` / `DEV_FRAC` | 0,20 / 0,10 | fracción de chunks reservados para evaluación / ajuste |
| `CHUNK_QUESTIONS` | train 6, dev 3, test 2 | preguntas por chunk |
| `CASE_QUESTIONS_MIN/MAX` | 5–10 | preguntas por caso |
| `MAX_LEXICAL_OVERLAP` | 0,30 | solapamiento máximo pregunta–positivo (set unseen original: 0,27 de media; preguntas reales de casos: 0,12) |
| `N_NEG_SELECT` / `N_NEG_FINAL` | 12 / 10 | negativos elegidos / que quedan tras el juez (10 = `train_group_size` 11 − 1) |
| `MAX_NEG_USES` | 150 | veces máximas que un chunk puede ser negativo |
| `NEG_MIN_RANK` / `NEG_MAX_SCORE_RATIO` | 5 / 0,9 | no se usan como negativos los 5 primeros del BM25 ni los de puntaje cercano al positivo (en el piloto, 17 % de los puestos 0–4 eran "si" y 0 % de los puestos 20+) |
| `CASE_CANDIDATE_NEGS` | 0 | candidatos del caso no elegidos como negativos: 0 (44 % eran "parcial" según el juez) |
| `NEG_JUDGE_FRACTION` | 0,25 | fracción de preguntas cuyos negativos se juzgan todos (estima la tasa de falsos negativos; 1,0 = todas) |
| `MAX_ROWS_PER_POSITIVE` | 12 | tope de filas de entrenamiento por chunk positivo |
| `MAX_TYPE_AUC` | 0,55 | el tipo de fuente no puede predecir positivo/negativo |

## Resultado de la prueba piloto (3 casos + 6 chunks por partición, 34 preguntas)

* Solapamiento léxico medio de las preguntas aceptadas: 0,09–0,13 (máx. 0,30); 5 de 39 propuestas se rechazaron por solapamiento.
* El juez confirmó el 100 % de los positivos (28) y de los chunks de origen (17).
* Negativos juzgados (116): 75 % "no", 20 % "parcial", 4 % "si". Los falsos negativos se concentran en el top-5 del BM25 y en los
  candidatos del caso: de ahí `NEG_MIN_RANK`, `NEG_MAX_SCORE_RATIO` y `CASE_CANDIDATE_NEGS = 0`.
* Hasta 3 de 6 chunks de la muestra de test se omitieron por no ser "preguntables" por una víctima: revisar la tasa de
  omisión por tipo (`chunk_questions_skipped.jsonl`) antes de fiarse del tamaño de dev/test.

## Tamaño esperado (corpus limpio de 751 chunks; estimación con las dos pruebas piloto)

Chunks por partición (duplicados contados una vez): train 533, dev 67, test 136. El CPP (~50 % del corpus) pierde ~40 % de
sus chunks por "trámite técnico interno" (colaboración eficaz, formación de expediente, custodia de bienes...): es lo esperado.
Meta del proyecto: **al menos 3.000 filas de entrenamiento**; por eso train pide hasta 6 preguntas por chunk (con ángulos
distintos) y los casos 5–10.

| | Preguntas generadas | Tras el juez | Filas de `training.json` |
|---|---|---|---|
| Train, desde chunks (hasta 6 por chunk, ~4,6 efectivas) | ~1.930 | | |
| Train, desde casos (132 casos, 5–10 c/u) | ~900 | | |
| **Train total** | **~2.830** | **~2.720** | **~3.400** (rango 3.000–3.800) |
| Dev (3 por chunk) | ~140 | ~135 | — |
| Test (2 por chunk) | ~195 | ~187 | — |

Si pese a esto una prueba mostrara que faltan filas, la siguiente palanca es una segunda ronda de train con otro estilo
(relatos largos con contexto / consultas muy cortas): el pipeline es reanudable y deduplica por similitud.

## Antes de generar (lista de verificación)

1. El corpus que usa el pipeline es `recoleccion/data/processed/document_chunks_all.jsonl` (`config.CHUNKS_PATH`), ya LIMPIO:
   `consolidate_document_chunks.py` quita enlaces acortados, notas de historial legislativo, encabezados de capítulo pegados al
   final de un artículo, boilerplate de gob.pe y el marcador "NUEVO:" (ver `recoleccion/scripts/chunk_cleaning.py` y
   `document_chunks_cleaning_report.json`; el corpus sin limpiar queda en `document_chunks_all.raw.jsonl`). Si se
   regenera (parser de la Ley 30364, CPP), volver a consolidarlo con `recoleccion/scripts/consolidate_document_chunks.py`
   y repetir el paso 1.
2. Correr el paso 1 y revisar la lista de chunks excluidos (muy largos = probable error de parseo; muy cortos).
   Con el corpus limpio actual (751 chunks) no queda ningún chunk excluido por largo.
3. `bash run_mock_e2e.sh` debe terminar con `AUDITORÍA: OK`.
4. Los candidatos del resolutor que no existen en el corpus se descartan: sin su texto en el corpus no se puede resolver
   su contenido ni indexarlo. `case_questions_report.json` cuenta cuántos se pierden.
5. Las preguntas basadas en casos omiten los casos cuya sentencia (chunk de jurisprudencia) cayó en dev/test, para que
   el resumen del caso no describa contenido que se evalúa (`caso_omitido_su_sentencia_esta_en_dev_o_test` en el reporte).
6. Si cambia el corpus **después** de generar, volver a correr el paso 1: los chunks existentes conservan su partición
   (depende solo del texto y de la semilla); los nuevos se asignan de forma estable.

## Después del dataset

* Entrenamiento: `training.json` (JSONL con `query`, `pos`, `neg`, `prompt`, más `pos_chunk_ids` / `neg_chunk_ids`).
* Evaluación: `eval_test_dataset.jsonl` (+ `_qrels`, `_queries`) tiene el mismo formato que el set unseen y sirve
  tal cual en `backend/quantitative_experiments/` (`--dataset-path`). Los qrels son estrictos (`qrels_complete: false`):
  completarlos por pooling como en ese experimento.
* Reportar siempre el recall por tipo de fuente del positivo.
