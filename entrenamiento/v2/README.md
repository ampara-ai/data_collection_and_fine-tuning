# Entrenamiento v2 (artículo, revisión Q1)

Entrena BGE-M3 con el dataset del artículo (`generacion_dataset/data/output/dataset_v2/training.json`, 2,057 filas, split por
chunk) y con las líneas de base de la revisión. La configuración por defecto es la de la Tabla 6. El material v1 (split por
sentencia, notebook de junio) está en [`../legacy_v1/`](../legacy_v1/README.md) y no corresponde al artículo.

| Paso | Dónde corre | Comando |
| --- | --- | --- |
| 1. Archivos de la línea de base | cualquier máquina | `python entrenamiento/v2/build_naive_dataset.py` |
| 2. Entrenamiento | GPU NVIDIA (CUDA) | `SEED=<s> TRAIN_FILE=<archivo> OUTPUT_DIR=<carpeta> bash entrenamiento/v2/run_training.sh` |
| 3. Elegir checkpoint en dev | Mac (MPS), CUDA o CPU | `select_checkpoint` del backend |
| 4. Evaluar en Test A y Test B | Mac (MPS), CUDA o CPU | `local_retrieval` y `compare` del backend |
| 5. Export ONNX INT8 (opcional) | Mac o Linux | `bash entrenamiento/v2/export_onnx_int8.sh <checkpoint> <salida>` |

DeepSpeed y el entrenamiento FP16 de FlagEmbedding necesitan CUDA; en Mac solo se evalúa. Una corrida de 2,057 filas tomó
≈2 h 26 min en una L4.

## 1. Archivos de entrenamiento

`build_naive_dataset.py` escribe en `entrenamiento/v2/data/` (deterministas, semilla 520; no se versionan, solo
`build_report.json` con sus SHA-256):

| Archivo | Filas | Qué es |
| --- | --- | --- |
| `generacion_dataset/data/output/dataset_v2/training.json` | 2,057 | Protocolo completo: el modelo principal |
| `training_full_matched.json` | 1,376 | Protocolo completo submuestreado al tamaño de la línea de base |
| `training_naive.json` | 1,376 | Línea de base ingenua: preguntas desde chunks sin juez, positivo = chunk de origen, negativos al azar |

H2 compara `training_full_matched` contra `training_naive` (mismo tamaño), tres semillas cada uno.

## 2. Corridas

```bash
for s in 42 1 2 3 4; do SEED=$s bash entrenamiento/v2/run_training.sh; done                       # modelo principal (H1, MAJOR #5)
for s in 42 1 2; do
  SEED=$s TRAIN_FILE=entrenamiento/v2/data/training_full_matched.json OUTPUT_DIR=entrenamiento/v2/runs/full_matched_seed$s bash entrenamiento/v2/run_training.sh
  SEED=$s TRAIN_FILE=entrenamiento/v2/data/training_naive.json        OUTPUT_DIR=entrenamiento/v2/runs/naive_seed$s        bash entrenamiento/v2/run_training.sh
done
```

Las corridas son independientes: conviene repartirlas en varias GPU a la vez. Cada carpeta queda con `provenance.json`
(hiperparámetros efectivos, SHA-256 del archivo de entrenamiento, commit), `pip_freeze.txt` (versiones exactas), `gpu.txt` y
`train.log`. Todos los hiperparámetros se pueden cambiar por variable de entorno (`LR`, `TEMPERATURE`, `GROUP_SIZE`, `EPOCHS`,
`GRAD_ACCUM`, `MAX_LEN`, `SAVE_STEPS`, `N_GPUS`).

**Pendiente antes de entrenar:** confirmar que la configuración de checkpoint-256 es la de la Tabla 6. El notebook v1
publicado usaba LR 1e-5, temperatura 0.02, grupo de 11 y sin semilla. Si no se puede confirmar, estas corridas con la
Tabla 6 pasan a ser el modelo principal del artículo.

`train_m3.py` aplica en memoria la corrección del guardado de checkpoints que el notebook v1 hacía editando el paquete
instalado de FlagEmbedding.

## 3. Elegir el checkpoint (solo con dev)

Desde el repo del backend, con este repo clonado al lado (o `AMPARA_DATA_REPO=<ruta>`):

```bash
uv run python -m quantitative_experiments.revision.select_checkpoint --run-dir <OUTPUT_DIR> --include-base
```

Elige el de mayor NDCG@10 estricto en las 130 preguntas de desarrollo y lo escribe en `<OUTPUT_DIR>/selected_checkpoint.txt`.
El conjunto de prueba no interviene.

## 4. Evaluar

```bash
uv run python -m quantitative_experiments.revision.local_retrieval --model cls:$(cat <OUTPUT_DIR>/selected_checkpoint.txt) --name ft_seed42
uv run python -m quantitative_experiments.revision.compare --system base=<run base> --system finetuned=<run seed42>,<run seed1>,... --reference base
```

El detalle de cada experimento está en `quantitative_experiments/revision/README.md` del backend.
