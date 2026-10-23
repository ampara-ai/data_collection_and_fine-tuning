#!/usr/bin/env bash
# Prueba de punta a punta del pipeline con respuestas SINTÉTICAS (backend mock). No genera datos reales ni llama
# a ninguna API. Escribe en un directorio temporal. Uso: bash run_mock_e2e.sh [DIR_SALIDA]
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-$(mktemp -d)/dataset_v2_mock}"
PY="${PYTHON:-../../.venv/bin/python}"
echo "salida: $OUT"
$PY 01_split_chunks.py --out-dir "$OUT" | tail -3
$PY 02_case_questions.py --backend mock --out-dir "$OUT" --limit 8 --max-overlap 1.0 | tail -3
$PY 03_chunk_questions.py --backend mock --out-dir "$OUT" --limit-chunks 120 --max-overlap 1.0 | tail -3
$PY 04_select_negatives.py --out-dir "$OUT" | tail -8
$PY 05_judge.py --backend mock --out-dir "$OUT" --neg-fraction 1.0 | tail -6
$PY 06_build_dataset.py --out-dir "$OUT" --no-fail | tail -40
