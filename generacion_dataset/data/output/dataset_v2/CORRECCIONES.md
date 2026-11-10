# Correcciones de procedencia del dataset v2

## 2026-11-06 – juez registrado en los conjuntos de evaluación y en el manifiesto

**Qué cambió.** `06_build_dataset.py` escribía en `generation.judge` de `eval_dev_dataset.jsonl` y `eval_test_dataset.jsonl`, y en
`manifest.json`, el valor por defecto de `config.JUDGE_MODEL` (`anthropic/claude-sonnet-5.5`). Los 9,011 veredictos de
`judgments.jsonl` los emitió `gpt-6.1-sol`. El script ahora toma el juez de cada veredicto y el manifiesto lista los modelos
realmente usados; `config.JUDGE_MODEL` pasa a `openai/gpt-6.1-sol`.

**Qué no cambió.** Se regeneró con `python generacion_dataset/pipeline_v2/06_build_dataset.py` (auditoría OK). Solo cambiaron
el campo `generation.judge` de los dos conjuntos de evaluación y el manifiesto; preguntas, ids, chunks de origen, qrels y
`training.json` son idénticos (`training.json`: `c9b9a95f…`, sin cambios).

| Archivo | SHA-256 antes | SHA-256 después |
| --- | --- | --- |
| `eval_test_dataset.jsonl` | `3c0ba866…` | `2f91f07e…` |
| `eval_dev_dataset.jsonl` | `6dc639ee…` | `4c0dfb4b…` |

**Generadores.** Las preguntas las escribieron sesiones de agente que registraron su modelo en la clave `_model` (procedencia
autodeclarada). Claude Sonnet 4.5 escribió 690 de 1,970 preguntas de entrenamiento, 48 de 198 de prueba y 43 de 130 de
desarrollo; el resto, Claude Sonnet 5.5 (registrado como `claude-sonnet-5-5` y como `anthropic/claude-sonnet-5.5`).

**Copia del backend.** `quantitative_experiments/test_set/eval_test_dataset.jsonl` del backend se restauró desde este archivo:
la copia anterior había cambiado a `claude-sonnet-5-5` el generador de esas 48 preguntas.
