#!/usr/bin/env bash
# Prueba de las OLAS con respuestas sintéticas (mock): fracciones acumuladas 0.2 -> 0.5 -> 1.0. Cada ola debe hacer solo
# las tareas nuevas (el resto sale de la caché). Uso: bash run_mock_waves.sh [DIR_SALIDA]
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-$(mktemp -d)/dataset_v2_waves}"; PY="${PYTHON:-../../.venv/bin/python}"
$PY 01_split_chunks.py --out-dir "$OUT" > /dev/null
for F in 0.2 0.5 1.0; do
  echo "=== OLA acumulada $F"
  $PY 02_case_questions.py  --backend mock --out-dir "$OUT" --fraction $F --max-overlap 1.0 | grep -E "^\[02|casos_en_esta_ola"
  $PY 03_chunk_questions.py --backend mock --out-dir "$OUT" --fraction $F --max-overlap 1.0 | grep -E "^\[03"
  $PY 04_select_negatives.py --out-dir "$OUT" > /dev/null
  $PY 05_judge.py --backend mock --out-dir "$OUT" | grep -E "^\[05"
  $PY 06_build_dataset.py --out-dir "$OUT" --no-fail --snapshot "ola_$F" | grep -E "snapshot|\"filas\"|\"preguntas\"|AUDITOR"
done
