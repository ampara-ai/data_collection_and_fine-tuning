#!/usr/bin/env python3
"""Valida IDs, colisiones positivo/negativo y metadatos del dataset generado."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from generate_colloquial_legal_questions import (
    normalized_chunk_resolution,
    normalized_chunk_text,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "output" / "legal_questions_dataset"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit(dataset_dir: Path) -> dict[str, Any]:
    candidate_sets = load_jsonl(dataset_dir / "candidate_sets.jsonl")
    questions = load_jsonl(dataset_dir / "questions_with_positive_context.jsonl")
    triples = load_jsonl(dataset_dir / "training_triples.jsonl")
    generation_errors = load_jsonl(dataset_dir / "generation_errors.jsonl")
    candidates_by_case = {str(row.get("case_id")): row for row in candidate_sets}
    errors: list[dict[str, Any]] = []
    temporal_statuses: Counter[str] = Counter()

    for row in questions:
        dataset_id = str(row.get("dataset_id") or "<missing>")
        case_id = str(row.get("case_id") or "")
        candidate_set = candidates_by_case.get(case_id)
        if candidate_set is None:
            errors.append({"dataset_id": dataset_id, "error": "missing_candidate_set"})
            continue

        allowed_positive = {
            str(candidate.get("candidate_id"))
            for candidate in candidate_set.get("candidates") or []
        }
        allowed_negative = {
            str(candidate.get("candidate_id"))
            for candidate in candidate_set.get("negative_candidate_pool") or []
        }
        positive_ids = set(map(str, row.get("positive_candidate_ids") or []))
        negative_ids = set(map(str, row.get("hard_negative_candidate_ids") or []))
        if not positive_ids or not positive_ids <= allowed_positive:
            errors.append({"dataset_id": dataset_id, "error": "invalid_positive_ids"})
        if not negative_ids or not negative_ids <= allowed_negative:
            errors.append({"dataset_id": dataset_id, "error": "invalid_negative_ids"})
        if positive_ids & negative_ids:
            errors.append({"dataset_id": dataset_id, "error": "positive_negative_id_overlap"})

        positives = row.get("positive_chunks") or []
        negatives = row.get("hard_negative_chunks") or []
        positive_doc_ids = {str(item.get("doc_id")) for item in positives if item.get("doc_id")}
        positive_texts = {normalized_chunk_text(item) for item in positives if normalized_chunk_text(item)}
        positive_resolutions = {
            normalized_chunk_resolution(item)
            for item in positives
            if normalized_chunk_resolution(item)
        }
        for negative in negatives:
            if negative.get("doc_id") and str(negative["doc_id"]) in positive_doc_ids:
                errors.append({"dataset_id": dataset_id, "error": "same_document_as_positive"})
            if normalized_chunk_text(negative) in positive_texts:
                errors.append({"dataset_id": dataset_id, "error": "same_text_as_positive"})
            resolution = normalized_chunk_resolution(negative)
            if resolution and resolution in positive_resolutions:
                errors.append({"dataset_id": dataset_id, "error": "same_resolution_as_positive"})

        temporal = row.get("temporal_context") or {}
        status = str(temporal.get("status") or "missing")
        temporal_statuses[status] += 1
        if status == "missing":
            errors.append({"dataset_id": dataset_id, "error": "missing_temporal_context"})

    exact_triple_collisions = 0
    for triple in triples:
        positives = {normalized_chunk_text({"text": text}) for text in triple.get("pos") or []}
        negatives = {normalized_chunk_text({"text": text}) for text in triple.get("neg") or []}
        if positives & negatives:
            exact_triple_collisions += 1
            errors.append({"dataset_id": triple.get("dataset_id"), "error": "triple_text_collision"})

    return {
        "check_type": "generated_dataset_integrity",
        "status": "ok" if not errors else "error",
        "dataset_dir": str(dataset_dir),
        "counts": {
            "candidate_sets": len(candidate_sets),
            "questions": len(questions),
            "training_triples": len(triples),
            "generation_errors": len(generation_errors),
            "exact_triple_collisions": exact_triple_collisions,
        },
        "temporal_statuses": dict(sorted(temporal_statuses.items())),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    args = parser.parse_args()
    report = audit(args.dataset_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
