"""
Parchea los textos de chunks en el dataset ya generado y regenera training_triples.

Problema: el run completo de generate_colloquial_legal_questions.py guardó en
questions_with_positive_context.jsonl los textos de jurisprudencia en su versión
original (verbose), no la síntesis generada por el LLM. Los chunks en disco ya
están actualizados (via apply_chunk_text_updates.py). Este script mapea los
chunk_ids del dataset contra el texto actual en disco y reemplaza in-place.

Luego regenera training_triples.jsonl con los textos corregidos.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "input" / "document_chunks_all.jsonl"
DEFAULT_DATASET_PATH = (
    PROJECT_ROOT / "data" / "output" / "legal_questions_dataset" / "questions_with_positive_context.jsonl"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "legal_questions_dataset"

FINETUNING_PROMPT = "Represent this sentence for searching relevant passages: "


def load_chunk_texts(chunks_path: Path) -> dict[str, str]:
    """Devuelve {chunk_id: text} con los textos actuales en disco."""
    lookup: dict[str, str] = {}
    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            cid = chunk.get("chunk_id")
            text = chunk.get("text", "").strip()
            if cid and text:
                lookup[cid] = text
    return lookup


def build_positive_context_text(chunks: list[dict[str, Any]]) -> str:
    blocks = []
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        block = {
            "chunk_id": chunk.get("chunk_id"),
            "source_type": chunk.get("source_type"),
            "title": chunk.get("title"),
            "article_id": metadata.get("article_id"),
            "resolution_reference": metadata.get("resolution_reference"),
            "text": chunk.get("text"),
        }
        blocks.append(json.dumps(block, ensure_ascii=False))
    return "\n\n".join(blocks)


def patch_chunks(chunks: list[dict[str, Any]], lookup: dict[str, str]) -> tuple[list[dict[str, Any]], int]:
    """Reemplaza text en cada chunk usando el lookup. Retorna (chunks_parcheados, n_actualizados)."""
    updated = 0
    patched = []
    for chunk in chunks:
        cid = chunk.get("chunk_id")
        if cid and cid in lookup and lookup[cid] != chunk.get("text", ""):
            chunk = dict(chunk)
            chunk["text"] = lookup[cid]
            updated += 1
        patched.append(chunk)
    return patched, updated


def build_training_records(records: list[dict[str, Any]], max_negatives: int = 10) -> list[dict[str, Any]]:
    training = []
    for idx, record in enumerate(records):
        positives = record.get("positive_chunks", [])
        negatives = record.get("hard_negative_chunks", [])
        if not positives or not negatives:
            continue
        training.append(
            {
                "id": str(idx),
                "query": record["query"],
                "pos": [c["text"] for c in positives if c.get("text")],
                "neg": [c["text"] for c in negatives[:max_negatives] if c.get("text")],
                "prompt": FINETUNING_PROMPT,
                "dataset_id": record["dataset_id"],
                "case_id": record["case_id"],
                "topic": record["topic"],
                "barrier": record["barrier"],
            }
        )
    return training


def main() -> None:
    parser = argparse.ArgumentParser(description="Parchea chunk texts en el dataset y regenera training_triples.")
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    chunks_path: Path = args.chunks_path
    dataset_path: Path = args.dataset_path
    output_dir: Path = args.output_dir

    if not chunks_path.exists():
        print(f"[ERROR] No se encontró chunks: {chunks_path}")
        return
    if not dataset_path.exists():
        print(f"[ERROR] No se encontró dataset: {dataset_path}")
        return

    print(f"[INFO] Cargando textos de chunks desde: {chunks_path}")
    lookup = load_chunk_texts(chunks_path)
    print(f"[INFO] Chunks cargados: {len(lookup)}")

    # Parchear dataset
    print(f"[INFO] Parcheando dataset: {dataset_path}")
    all_records: list[dict[str, Any]] = []
    total = 0
    pos_updated_total = 0
    neg_updated_total = 0

    with dataset_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            total += 1

            pos_chunks, pos_upd = patch_chunks(record.get("positive_chunks", []), lookup)
            neg_chunks, neg_upd = patch_chunks(record.get("hard_negative_chunks", []), lookup)

            record["positive_chunks"] = pos_chunks
            record["hard_negative_chunks"] = neg_chunks
            pos_updated_total += pos_upd
            neg_updated_total += neg_upd

            if pos_upd:
                record["positive_context_text"] = build_positive_context_text(pos_chunks)

            all_records.append(record)

    print(f"[INFO] Registros procesados: {total}")
    print(f"[INFO] positive_chunks actualizados: {pos_updated_total}")
    print(f"[INFO] hard_negative_chunks actualizados: {neg_updated_total}")

    # Sobrescribir dataset
    tmp = dataset_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(dataset_path)
    print(f"[OK] Dataset parcheado → {dataset_path}")

    # Regenerar training_triples
    training = build_training_records(all_records, max_negatives=10)
    triples_path = output_dir / "training_triples.jsonl"
    output_dir.mkdir(parents=True, exist_ok=True)
    with triples_path.open("w", encoding="utf-8") as f:
        for triple in training:
            f.write(json.dumps(triple, ensure_ascii=False) + "\n")
    print(f"[OK] training_triples regenerado ({len(training)} filas) → {triples_path}")

    print("\n[DONE]")


if __name__ == "__main__":
    main()
