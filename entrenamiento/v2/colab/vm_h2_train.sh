#!/usr/bin/env bash
# Se ejecuta DENTRO de la VM de Colab (lo lanza launch.sh). Entrena las corridas de H2 una por una con los mismos parámetros que
# quantitative_experiments/revision/run_h2.sh del backend (rama del PR #3), pero cada corrida termina y se copia a Drive antes de empezar la
# siguiente. Si la VM se cae, las corridas ya copiadas a Drive se saltan al relanzar, así que no se pierde lo hecho.
#
# Variables:  DATA_COMMIT (obligatoria; la pone launch.sh)   RUNS="full_matched:42 full_matched:1 ..." (por defecto las seis)
#             DRIVE_DIR (por defecto /content/drive/MyDrive/ampara_h2)
# Estado en /content/h2.status:  RUNNING <corrida> | FAILED <motivo> | ALL_DONE
set -uo pipefail
RUNS="${RUNS:-full_matched:42 full_matched:1 full_matched:2 naive:42 naive:1 naive:2}"
DRIVE="${DRIVE_DIR:-/content/drive/MyDrive/ampara_h2}"
W=/content/h2
STATUS=/content/h2.status
: "${DATA_COMMIT:?define DATA_COMMIT (commit del repo de datos, ya subido a GitHub)}"
BASE_REV=5617a9f61b028005a4858fdac845db406aefb181              # BAAI/bge-m3
BASE_SHA=b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38   # pytorch_model.bin

fail() { echo "FAILED $*" > "$STATUS"; echo "FAILED $*" >&2; exit 1; }
[ -d /content/drive/MyDrive ] || fail "Drive no está montado (colab drivemount)"
mkdir -p "$W" "$DRIVE/training" "$DRIVE/training_data" "$DRIVE/logs"
echo "RUNNING preparación" > "$STATUS"

# --- código del repo de datos (público), en el commit fijado
if [ ! -d "$W/data/.git" ]; then
  git clone -q https://github.com/ampara-ai/data_collection_and_fine-tuning "$W/data" || fail "clone"
fi
git -C "$W/data" checkout -q "$DATA_COMMIT" || fail "checkout $DATA_COMMIT"

# --- dependencias de entrenamiento; las versiones se congelan en Drive para que las seis corridas usen el mismo entorno
PINS="$DRIVE/train_env_pins.txt"
# Con varias VMs a la vez, solo una instala y congela las versiones; las demás esperan ese archivo (mkdir es atómico).
if [ ! -f "$PINS" ] && mkdir "$DRIVE/.pins_lock" 2>/dev/null; then
  pip install -q FlagEmbedding deepspeed || fail "pip install"
  pip freeze | grep -iE '^(flagembedding|deepspeed|transformers|peft|datasets|accelerate|sentence-transformers|torch)==' > "$PINS.tmp" && mv "$PINS.tmp" "$PINS"
else
  for _ in $(seq 1 120); do [ -f "$PINS" ] && break; sleep 10; done
  [ -f "$PINS" ] || fail "no aparecieron las versiones congeladas (train_env_pins.txt)"
  pip install -q -r "$PINS" || fail "pip install -r pins"
fi
nvidia-smi > "$DRIVE/logs/gpu_$(date +%Y%m%d_%H%M%S).txt" || fail "no hay GPU"

# --- snapshot del modelo base (sin safetensors) y verificación de hash
if [ ! -f "$W/bge-m3/pytorch_model.bin" ]; then
  python - "$W/bge-m3" "$BASE_REV" <<'PY' || fail "descarga del modelo base"
import sys
from huggingface_hub import snapshot_download
snapshot_download("BAAI/bge-m3", revision=sys.argv[2], local_dir=sys.argv[1],
                  ignore_patterns=["*.safetensors", "onnx/*", "*.onnx", "imgs/*"])
PY
fi
echo "$BASE_SHA  $W/bge-m3/pytorch_model.bin" | sha256sum -c --status || fail "hash del modelo base distinto"

# --- datos de entrenamiento (deterministas) y comprobación de los hashes congelados
python "$W/data/entrenamiento/v2/build_naive_dataset.py" --n-neg 10 --out-dir "$W/training_data" > "$DRIVE/logs/build_data.log" 2>&1 || fail "build_naive_dataset"
python - "$W/training_data" <<'PY' || fail "los datos no coinciden con el diseño congelado de H2"
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1]); report = json.loads((root / "build_report.json").read_text())
if report["rows"] != 1376 or report["seed"] != 520 or report["n_neg"] != 10: raise SystemExit("build_report distinto")
expected = {"training_naive.json": "da592f14d196e0d25f682ced9b71511f77cc891e8704386757dbc03863c974f0",
            "training_full_matched.json": "69cfa3d702aa983544385e1e5f48df4061f551064acaa7c6ef17bc560aa80702"}
prefix = ""   # sin prefijo de consulta (prompt vacío), como en producción
for name, digest in expected.items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest: raise SystemExit(f"hash distinto: {name}")
    rows = [json.loads(l) for l in (root / name).read_text().splitlines() if l.strip()]
    if any(r.get("prompt") != prefix for r in rows): raise SystemExit(f"prefijo distinto: {name}")
PY
cp -n "$W"/training_data/* "$DRIVE/training_data/"

# --- una corrida por vez; cada una se copia a Drive al terminar
for run in $RUNS; do
  arm="${run%%:*}"; seed="${run##*:}"; name="${arm}_seed${seed}"
  if [ -f "$DRIVE/training/$name/DONE" ]; then echo "ya hecha, se salta: $name"; continue; fi
  echo "RUNNING $name" > "$STATUS"
  out="$W/training/$name"; rm -rf "$out"; mkdir -p "$W/training"
  env BASE_MODEL="$W/bge-m3" SEED="$seed" TRAIN_FILE="$W/training_data/training_${arm}.json" OUTPUT_DIR="$out" \
      LR=5e-6 TEMPERATURE=0.05 GROUP_SIZE=9 EPOCHS=5 BATCH=1 GRAD_ACCUM=16 MAX_LEN=2048 WARMUP_RATIO=0.1 SAVE_STEPS=85 N_GPUS=1 \
      bash "$W/data/entrenamiento/v2/run_training.sh" > "$DRIVE/logs/${name}.log" 2>&1 || fail "$name: entrenamiento (ver logs/${name}.log)"
  rm -rf "$DRIVE/training/$name.tmp" "$DRIVE/training/$name"
  cp -r "$out" "$DRIVE/training/$name.tmp" && mv "$DRIVE/training/$name.tmp" "$DRIVE/training/$name" || fail "$name: copia a Drive"
  touch "$DRIVE/training/$name/DONE"
  rm -rf "$out"
done
echo "ALL_DONE" > "$STATUS"
