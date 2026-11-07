#!/usr/bin/env bash
# Export del checkpoint elegido a ONNX y cuantización dinámica INT8, como en la sección 3.5 del artículo (Optimum,
# feature-extraction; ONNX Runtime quantize_dynamic, pesos QInt8, datos externos, sin calibración). Corre en Mac o Linux.
#
# Uso: bash entrenamiento/v2/export_onnx_int8.sh <carpeta del checkpoint> <carpeta de salida>
# Requisitos: pip install "optimum[onnxruntime]" onnxruntime
set -euo pipefail
CKPT="$1"; OUT="$2"
optimum-cli export onnx --model "$CKPT" --task feature-extraction "$OUT/fp32"
python - "$OUT" <<'EOF'
import shutil, sys
from pathlib import Path
from onnxruntime.quantization import QuantType, quantize_dynamic
out = Path(sys.argv[1]); src = out / "fp32"; dst = out / "int8"; dst.mkdir(parents=True, exist_ok=True)
quantize_dynamic(str(src / "model.onnx"), str(dst / "model_quantized.onnx"), weight_type=QuantType.QInt8,
                 use_external_data_format=True)
for f in src.iterdir():  # tokenizer y configuración, para que el model service y local_retrieval (onnx:) lo carguen
    if f.suffix in {".json", ".txt", ".model"}:
        shutil.copy(f, dst / f.name)
print(f"INT8 -> {dst}")
EOF
shasum -a 256 "$OUT"/int8/model_quantized.onnx* | tee "$OUT/int8/SHA256SUMS"
