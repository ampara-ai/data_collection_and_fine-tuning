#!/usr/bin/env bash
# Fine-tuning de BGE-M3 con la configuración de la Tabla 6 del artículo. Requiere GPU NVIDIA (CUDA): DeepSpeed y el
# entrenamiento en FP16 de FlagEmbedding no corren en Mac. La evaluación de los checkpoints sí corre en Mac (ver README).
#
# Uso (una corrida por semilla; todas las variables tienen el valor de la Tabla 6 por defecto):
#   SEED=42 bash entrenamiento/v2/run_training.sh
#   SEED=1  TRAIN_FILE=entrenamiento/v2/data/training_naive.json OUTPUT_DIR=entrenamiento/v2/runs/naive_seed1 bash entrenamiento/v2/run_training.sh
#
# Requisitos en la máquina con GPU:  pip install FlagEmbedding deepspeed  (las versiones usadas quedan en pip_freeze.txt)
set -euo pipefail
trap '[ -n "${META:-}" ] && [ -d "$META" ] && echo "Registro y procedencia de la corrida: $META" >&2' ERR

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

SEED="${SEED:-42}"
TRAIN_FILE="${TRAIN_FILE:-$REPO/generacion_dataset/data/output/dataset_v2/training.json}"
OUTPUT_DIR="${OUTPUT_DIR:-$HERE/runs/full_seed${SEED}}"
BASE_MODEL="${BASE_MODEL:-BAAI/bge-m3}"
LR="${LR:-5e-6}"
TEMPERATURE="${TEMPERATURE:-0.05}"
GROUP_SIZE="${GROUP_SIZE:-9}"          # 1 positivo + 8 negativos
EPOCHS="${EPOCHS:-5}"
BATCH="${BATCH:-1}"
GRAD_ACCUM="${GRAD_ACCUM:-16}"         # lote efectivo 16
MAX_LEN="${MAX_LEN:-2048}"
WARMUP_RATIO="${WARMUP_RATIO:-0.1}"
N_GPUS="${N_GPUS:-1}"

command -v nvidia-smi >/dev/null 2>&1 || { echo "Se necesita una GPU NVIDIA (CUDA). En Mac solo se evalúa." >&2; exit 1; }
[ -f "$TRAIN_FILE" ] || { echo "No existe TRAIN_FILE=$TRAIN_FILE" >&2; exit 1; }
# FlagEmbedding no entrena sobre una carpeta con contenido: la procedencia se escribe aparte y se mueve al terminar.
if [ -d "$OUTPUT_DIR" ] && [ -n "$(ls -A "$OUTPUT_DIR")" ]; then
  echo "$OUTPUT_DIR no está vacía; usa otro OUTPUT_DIR o bórrala" >&2; exit 1
fi
META="$(mktemp -d)"

N_RECORDS=$(grep -c . "$TRAIN_FILE")
STEPS_PER_EPOCH=$(( (N_RECORDS + BATCH * GRAD_ACCUM * N_GPUS - 1) / (BATCH * GRAD_ACCUM * N_GPUS) ))
TOTAL_STEPS=$(( STEPS_PER_EPOCH * EPOCHS ))
WARMUP_STEPS=$(python -c "print(max(1, int($TOTAL_STEPS * $WARMUP_RATIO)))")
# Un checkpoint por época, aproximadamente: con 2,057 filas da 128 pasos (129 por época), como en el artículo.
SAVE_STEPS="${SAVE_STEPS:-$(( STEPS_PER_EPOCH - 1 ))}"

python -m pip freeze > "$META/pip_freeze.txt"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv > "$META/gpu.txt"
python - "$META/provenance.json" <<EOF
import hashlib, json, subprocess, sys, datetime
sha = hashlib.sha256(open("$TRAIN_FILE", "rb").read()).hexdigest()
commit = subprocess.run(["git", "-C", "$REPO", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = bool(subprocess.run(["git", "-C", "$REPO", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
json.dump({"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "data_repo_commit": commit, "dirty": dirty,
           "train_file": "$TRAIN_FILE", "train_file_sha256": sha, "records": $N_RECORDS, "base_model": "$BASE_MODEL",
           "seed": $SEED, "learning_rate": float("$LR"), "temperature": float("$TEMPERATURE"), "train_group_size": $GROUP_SIZE,
           "epochs": $EPOCHS, "per_device_batch": $BATCH, "grad_accum": $GRAD_ACCUM, "n_gpus": $N_GPUS,
           "max_len": $MAX_LEN, "steps_per_epoch": $STEPS_PER_EPOCH, "total_steps": $TOTAL_STEPS,
           "warmup_steps": $WARMUP_STEPS, "save_steps": $SAVE_STEPS, "precision": "fp16", "deepspeed": "ZeRO stage 0",
           "loss": "InfoNCE", "pooling": "cls", "gradient_checkpointing": True}, open(sys.argv[1], "w"), indent=1)
EOF
echo "Registros: $N_RECORDS | pasos/época: $STEPS_PER_EPOCH | total: $TOTAL_STEPS | warmup: $WARMUP_STEPS | checkpoint cada $SAVE_STEPS"

PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True BASE_MODEL="$BASE_MODEL" \
torchrun --nproc_per_node "$N_GPUS" "$HERE/train_m3.py" \
  --model_name_or_path "$BASE_MODEL" \
  --cache_dir "$OUTPUT_DIR/.cache/model" \
  --train_data "$TRAIN_FILE" \
  --cache_path "$OUTPUT_DIR/.cache/data" \
  --train_group_size "$GROUP_SIZE" \
  --query_max_len "$MAX_LEN" \
  --passage_max_len "$MAX_LEN" \
  --pad_to_multiple_of 8 \
  --same_dataset_within_batch True \
  --small_threshold 0 \
  --drop_threshold 0 \
  --output_dir "$OUTPUT_DIR" \
  --learning_rate "$LR" \
  --fp16 \
  --num_train_epochs "$EPOCHS" \
  --per_device_train_batch_size "$BATCH" \
  --gradient_accumulation_steps "$GRAD_ACCUM" \
  --dataloader_drop_last True \
  --warmup_steps "$WARMUP_STEPS" \
  --gradient_checkpointing \
  --deepspeed "$HERE/ds_config_zero0.json" \
  --logging_steps 10 \
  --save_steps "$SAVE_STEPS" \
  --negatives_cross_device \
  --temperature "$TEMPERATURE" \
  --sentence_pooling_method cls \
  --normalize_embeddings True \
  --unified_finetuning False \
  --use_self_distill False \
  --fix_encoder False \
  --self_distill_start_step "$WARMUP_STEPS" \
  --seed "$SEED" \
  2>&1 | tee "$META/train.log"

mkdir -p "$OUTPUT_DIR" && mv "$META"/* "$OUTPUT_DIR"/ && rmdir "$META"
echo "Listo: $OUTPUT_DIR. Siguiente: elegir el checkpoint en dev (README, paso 3)."
