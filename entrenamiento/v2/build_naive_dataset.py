#!/usr/bin/env python
"""Archivos de entrenamiento para la línea de base "sintética ingenua" (H2 del registro, MAJOR #2 y #3).

  training_naive.json         Receta InPars/Promptagator: solo las preguntas generadas desde un chunk (antes del juez), con su
                              chunk de origen como único positivo y negativos al azar de la partición de entrenamiento (sin BM25,
                              sin juez, sin balance por tipo de fuente, sin preguntas basadas en sentencias).
  training_full_matched.json  El protocolo completo (dataset_v2/training.json) submuestreado al MISMO número de filas, para que
                              la comparación naive vs completo no se confunda con la cantidad de datos.

Mismo formato que dataset_v2/training.json (FlagEmbedding): query, pos [1 texto], neg [N textos], con sus chunk_id. Todo es
determinista (semilla 520). Auditorías (el script falla si alguna se rompe): todos los chunks pertenecen a la partición de
entrenamiento, ningún positivo aparece entre sus negativos (ni sus casi duplicados) y cada texto es idéntico al del corpus.

Uso (desde la raíz del repo de datos):
    python entrenamiento/v2/build_naive_dataset.py [--n-neg 10] [--out-dir entrenamiento/v2/data]
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DV2 = REPO / "generacion_dataset" / "data" / "output" / "dataset_v2"
CORPUS = REPO / "recoleccion" / "data" / "processed" / "document_chunks_all.jsonl"
CORPUS_SHA256 = "790ad3769a5ab139555c78e64daa87134161aa69c9604aeabef6f97e3de788f0"  # el corpus congelado de 893 chunks
SEED = 520


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-neg", type=int, default=10, help="negativos por fila (FlagEmbedding toma group_size - 1 al azar)")
    ap.add_argument("--out-dir", type=Path, default=REPO / "entrenamiento" / "v2" / "data")
    args = ap.parse_args()

    if sha256(CORPUS) != CORPUS_SHA256:
        sys.exit("el corpus no es el congelado de 893 chunks (SHA-256 distinto)")
    corpus = {c["chunk_id"]: c for c in read_jsonl(CORPUS)}
    split = json.loads((DV2 / "chunk_split.json").read_text(encoding="utf-8"))
    train_chunks = sorted(c for c, s in split["assignments"].items() if s == "train")
    group = {c: set(g) for g in split["duplicate_groups"] for c in g}
    full = read_jsonl(DV2 / "training.json")
    prompt = full[0].get("prompt")

    naive, problems = [], []
    for q in sorted(read_jsonl(DV2 / "chunk_questions_train.jsonl"), key=lambda r: r["dataset_id"]):
        pos = q["origin_chunk_id"]
        banned = group.get(pos, {pos})
        rng = random.Random(f"{SEED}:{q['dataset_id']}")
        neg = rng.sample([c for c in train_chunks if c not in banned], args.n_neg)
        row = {"id": f"naive::{q['dataset_id']}", "dataset_id": q["dataset_id"], "query": q["query"],
               "pos": [corpus[pos]["text"]], "neg": [corpus[c]["text"] for c in neg],
               "pos_chunk_ids": [pos], "neg_chunk_ids": neg, "source": "naive_chunk"}
        if prompt is not None:
            row["prompt"] = prompt  # misma clave que training.json (FlagEmbedding la ignora sin query_instruction_for_retrieval)
        naive.append(row)

    rng = random.Random(SEED)
    matched = sorted(rng.sample(full, len(naive)), key=lambda r: r["id"])

    for name, rows in (("naive", naive), ("full_matched", matched)):
        for r in rows:
            ids = r["pos_chunk_ids"] + r["neg_chunk_ids"]
            if any(split["assignments"].get(c) != "train" for c in ids):
                problems.append(f"{name} {r['id']}: chunk fuera de la partición de entrenamiento")
            if set(r["pos_chunk_ids"]) & set(r["neg_chunk_ids"]):
                problems.append(f"{name} {r['id']}: positivo entre los negativos")
            if any(t != corpus[c]["text"] for t, c in zip(r["pos"] + r["neg"], ids)):
                problems.append(f"{name} {r['id']}: texto distinto del corpus")
    if problems:
        sys.exit("AUDITORÍA FALLIDA:\n  " + "\n  ".join(problems[:20]))

    out = args.out_dir
    write_jsonl(out / "training_naive.json", naive)
    write_jsonl(out / "training_full_matched.json", matched)
    report = {
        "seed": SEED, "rows": len(naive), "n_neg": args.n_neg,
        "naive": {"questions": len({r["dataset_id"] for r in naive}), "distinct_positives": len({r["pos_chunk_ids"][0] for r in naive}),
                  "positive_source_types": dict(Counter(corpus[r["pos_chunk_ids"][0]]["source_type"] for r in naive))},
        "full_matched": {"from": "dataset_v2/training.json", "full_rows": len(full),
                         "origin": dict(Counter(r.get("source") for r in matched))},
        "inputs_sha256": {"corpus": CORPUS_SHA256, "chunk_split": sha256(DV2 / "chunk_split.json"),
                          "chunk_questions_train": sha256(DV2 / "chunk_questions_train.jsonl"), "training": sha256(DV2 / "training.json")},
        "outputs_sha256": {n: sha256(out / n) for n in ("training_naive.json", "training_full_matched.json")},
    }
    (out / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
