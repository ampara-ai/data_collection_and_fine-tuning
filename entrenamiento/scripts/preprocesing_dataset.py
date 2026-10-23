"""
preprocesing_dataset.py
========================
Prepara el dataset de fine-tuning de embeddings a partir de training_triples.jsonl.

Estructura de entrada (training_triples.jsonl):
    {"id": str, "query": str, "pos": List[str] | str, "neg": List[str],
     "prompt": str, "case_id": str, ...campos_extra}

Archivos de salida en entrenamiento/data/:
    training.json       → casos de entrenamiento (formato FlagEmbedding)
    test_queries.jsonl  → queries de casos de test  {"id", "text", "case_id"}
    corpus.jsonl        → todos los positivos       {"id", "text", "case_id"}
    test_qrels.jsonl    → mapeo qid→docid           {"qid", "docid", "relevance", "case_id"}
    split_manifest.json → metadatos y case_id asignados a cada partición

El split se realiza por ``case_id``: todas las preguntas derivadas de una misma
sentencia quedan exclusivamente en entrenamiento o exclusivamente en test.

Uso:
    python entrenamiento/scripts/preprocesing_dataset.py \
        --input  generacion_dataset/data/output/legal_questions_dataset/training_triples.jsonl \
        --output entrenamiento/data \
        --test_size 0.1 \
        --seed 520
"""

import json
import random
import argparse
from pathlib import Path


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    """Carga un archivo .jsonl o .json (una lista o línea por objeto)."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Intentar como JSON array primero
    if content.startswith("["):
        records = json.loads(content)
    else:
        # JSONL: una línea por objeto
        for line in content.splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))

    return records


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  ✓ {path}  ({len(records)} filas)")


def normalize_pos(pos_field) -> list[str]:
    """Garantiza que 'pos' sea siempre una lista de strings."""
    if isinstance(pos_field, str):
        return [pos_field]
    if isinstance(pos_field, list):
        # Aplanar si algún elemento es lista (raro pero posible)
        flat = []
        for item in pos_field:
            if isinstance(item, list):
                flat.extend(item)
            else:
                flat.append(item)
        return flat
    return [str(pos_field)]


def split_by_case_id(
    records: list[dict], test_size: float, seed: int
) -> tuple[list[dict], list[dict], list[str], list[str]]:
    """Divide casos completos, sin mezclar preguntas de una sentencia."""
    if not 0 < test_size < 1:
        raise ValueError("test_size debe ser un valor mayor que 0 y menor que 1.")

    missing_case_id = [
        str(r.get("id", "<sin id>")) for r in records if not r.get("case_id")
    ]
    if missing_case_id:
        examples = ", ".join(missing_case_id[:5])
        raise ValueError(
            f"{len(missing_case_id)} registros no tienen case_id. "
            f"Ejemplos: {examples}. No es seguro hacer el split por sentencia."
        )

    case_ids = sorted({str(r["case_id"]) for r in records})
    if len(case_ids) < 2:
        raise ValueError("Se necesitan al menos dos case_id distintos para crear train y test.")

    rng = random.Random(seed)
    rng.shuffle(case_ids)

    n_test_cases = round(len(case_ids) * test_size)
    n_test_cases = min(max(1, n_test_cases), len(case_ids) - 1)
    test_case_ids = sorted(case_ids[:n_test_cases])
    test_case_set = set(test_case_ids)
    train_case_ids = sorted(set(case_ids) - test_case_set)

    # Se conserva el orden original. La aleatoriedad solo decide qué
    # sentencias pertenecen a cada partición.
    train_records = [r for r in records if str(r["case_id"]) not in test_case_set]
    test_records = [r for r in records if str(r["case_id"]) in test_case_set]

    return train_records, test_records, train_case_ids, test_case_ids


# ─────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────

def main(input_path: Path, output_dir: Path, test_size: float, seed: int) -> None:

    print(f"\n{'='*55}")
    print(f"  Dataset preparation — FlagEmbedding fine-tuning")
    print(f"{'='*55}\n")

    # 1. Cargar dataset ──────────────────────────────────────
    print(f"[1/5] Cargando dataset desde: {input_path}")
    records = load_jsonl(input_path)
    print(f"      Total de filas: {len(records)}")

    # Normalizar 'pos' a lista en todos los registros
    for r in records:
        r["pos"] = normalize_pos(r["pos"])

    # 2. Split train / test ──────────────────────────────────
    print(f"\n[2/5] Dividiendo por case_id (test_size={test_size}, seed={seed})")
    train_records, test_records, train_case_ids, test_case_ids = split_by_case_id(
        records, test_size, seed
    )

    print(f"      Train: {len(train_records)} filas de {len(train_case_ids)} sentencias")
    print(f"      Test : {len(test_records)} filas de {len(test_case_ids)} sentencias")

    # 3. Guardar training.json ───────────────────────────────
    print(f"\n[3/5] Guardando training.json")

    # Campos esperados por FlagEmbedding; los extra se conservan
    training_out = output_dir / "training.json"
    training_out.parent.mkdir(parents=True, exist_ok=True)
    with open(training_out, "w", encoding="utf-8") as f:
        for rec in train_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  ✓ {training_out}  ({len(train_records)} filas)")

    # 4. Construir corpus.jsonl ──────────────────────────────
    # El corpus usa TODOS los positivos del dataset completo
    # (igual que el notebook: corpus = ds.select_columns(["id","pos"]))
    print(f"\n[4/5] Construyendo corpus.jsonl (positivos de todo el dataset)")

    corpus_records = []
    seen_ids = set()
    for rec in records:
        rec_id = str(rec["id"])
        if rec_id in seen_ids:
            continue
        seen_ids.add(rec_id)

        # Un positivo por fila (el primero si hay varios)
        # Si necesitas indexar múltiples positivos, duplifica el id
        pos_texts = rec["pos"]
        if len(pos_texts) == 1:
            corpus_records.append({
                "id": rec_id,
                "text": pos_texts[0],
                "case_id": str(rec["case_id"]),
            })
        else:
            for i, txt in enumerate(pos_texts):
                corpus_records.append({
                    "id": f"{rec_id}_{i}",
                    "text": txt,
                    "case_id": str(rec["case_id"]),
                })

    write_jsonl(corpus_records, output_dir / "corpus.jsonl")

    # 5. Construir test_queries.jsonl y test_qrels.jsonl ─────
    print(f"\n[5/5] Construyendo archivos de evaluación")

    test_queries = []
    test_qrels   = []

    for rec in test_records:
        qid = str(rec["id"])
        case_id = str(rec["case_id"])
        test_queries.append({"id": qid, "text": rec["query"], "case_id": case_id})

        # qrels: cada query apunta a su positivo en el corpus
        pos_texts = rec["pos"]
        if len(pos_texts) == 1:
            test_qrels.append({
                "qid": qid,
                "docid": qid,
                "relevance": 1,
                "case_id": case_id,
            })
        else:
            for i in range(len(pos_texts)):
                test_qrels.append({
                    "qid": qid,
                    "docid": f"{qid}_{i}",
                    "relevance": 1,
                    "case_id": case_id,
                })

    write_jsonl(test_queries, output_dir / "test_queries.jsonl")
    write_jsonl(test_qrels,   output_dir / "test_qrels.jsonl")

    manifest = {
        "strategy": "group_by_case_id",
        "seed": seed,
        "requested_test_size": test_size,
        "total_records": len(records),
        "total_cases": len(train_case_ids) + len(test_case_ids),
        "train_records": len(train_records),
        "test_records": len(test_records),
        "train_cases": train_case_ids,
        "test_cases": test_case_ids,
    }
    manifest_path = output_dir / "split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(
        f"  ✓ {manifest_path}  "
        f"({len(train_case_ids)} train / {len(test_case_ids)} test)"
    )

    # ── Resumen ─────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  Resumen final")
    print(f"{'='*55}")
    print(f"  training.json       → {len(train_records):>5} filas")
    print(f"  corpus.jsonl        → {len(corpus_records):>5} documentos")
    print(f"  test_queries.jsonl  → {len(test_queries):>5} queries")
    print(f"  test_qrels.jsonl    → {len(test_qrels):>5} relaciones")
    print(f"  split_manifest.json → {len(train_case_ids):>5} / {len(test_case_ids)} sentencias")
    print(f"\n  Todos los archivos en: {output_dir.resolve()}\n")

    # Verificación rápida de integridad
    _verify(train_records, test_records, test_queries, test_qrels, corpus_records)


def _verify(train: list, test: list, queries: list, qrels: list, corpus: list) -> None:
    """Comprueba la integridad documental y la separación estricta por caso."""
    corpus_ids = {r["id"] for r in corpus}
    missing = [q["docid"] for q in qrels if q["docid"] not in corpus_ids]
    if missing:
        raise RuntimeError(
            f"{len(missing)} docids de qrels no existen en el corpus. "
            f"Primeros 5: {missing[:5]}"
        )

    train_cases = {str(r["case_id"]) for r in train}
    test_cases = {str(r["case_id"]) for r in test}
    overlap = train_cases & test_cases
    if overlap:
        raise RuntimeError(
            f"Fuga de datos: {len(overlap)} case_id aparecen en train y test. "
            f"Primeros 5: {sorted(overlap)[:5]}"
        )

    query_cases = {str(r["case_id"]) for r in queries}
    if query_cases != test_cases:
        raise RuntimeError("Los case_id de test_queries no coinciden con la partición de test.")

    print("  ✓ Integridad OK: todos los docids del qrel están en el corpus.")
    print("  ✓ Split OK: 0 sentencias compartidas entre train y test.")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepara dataset para fine-tuning de modelos de embedding."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("generacion_dataset/data/output/legal_questions_dataset/training_triples.jsonl"),
        help="Ruta al archivo training_triples.jsonl de entrada.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("entrenamiento/data"),
        help="Directorio de salida para los archivos generados.",
    )
    parser.add_argument(
        "--test_size",
        type=float,
        default=0.1,
        help="Fracción de sentencias para test (default: 0.1 → 10%%).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=520,
        help="Semilla para reproducibilidad del shuffle (default: 520).",
    )

    args = parser.parse_args()
    main(
        input_path=args.input,
        output_dir=args.output,
        test_size=args.test_size,
        seed=args.seed,
    )
