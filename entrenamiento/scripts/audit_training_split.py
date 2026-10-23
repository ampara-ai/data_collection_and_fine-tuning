#!/usr/bin/env python3
"""Audita los artefactos de train/test sin entrenar ningún modelo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "entrenamiento" / "data"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def audit(data_dir: Path) -> dict[str, Any]:
    paths = {
        "training": data_dir / "training.json",
        "corpus": data_dir / "corpus.jsonl",
        "test_queries": data_dir / "test_queries.jsonl",
        "test_qrels": data_dir / "test_qrels.jsonl",
        "manifest": data_dir / "split_manifest.json",
    }
    missing_files = [str(path) for path in paths.values() if not path.exists()]
    if missing_files:
        raise FileNotFoundError(f"Faltan artefactos de entrenamiento: {missing_files}")

    training = read_jsonl(paths["training"])
    corpus = read_jsonl(paths["corpus"])
    queries = read_jsonl(paths["test_queries"])
    qrels = read_jsonl(paths["test_qrels"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    errors: list[str] = []
    train_cases = {str(row.get("case_id") or "") for row in training}
    test_cases = {str(row.get("case_id") or "") for row in queries}
    train_cases.discard("")
    test_cases.discard("")

    rows_without_case_id = {
        "training": sum(not row.get("case_id") for row in training),
        "test_queries": sum(not row.get("case_id") for row in queries),
        "corpus": sum(not row.get("case_id") for row in corpus),
        "test_qrels": sum(not row.get("case_id") for row in qrels),
    }
    if any(rows_without_case_id.values()):
        errors.append(f"Hay filas sin case_id: {rows_without_case_id}")

    overlap = sorted(train_cases & test_cases)
    if overlap:
        errors.append(f"Fuga entre train/test: {len(overlap)} case_id compartidos.")

    corpus_by_id = {str(row.get("id")): row for row in corpus}
    queries_by_id = {str(row.get("id")): row for row in queries}
    duplicate_corpus_ids = duplicate_values([str(row.get("id")) for row in corpus])
    duplicate_query_ids = duplicate_values([str(row.get("id")) for row in queries])
    if duplicate_corpus_ids:
        errors.append(f"IDs duplicados en corpus: {duplicate_corpus_ids[:5]}")
    if duplicate_query_ids:
        errors.append(f"IDs duplicados en test_queries: {duplicate_query_ids[:5]}")

    missing_docids = sorted(
        {str(row.get("docid")) for row in qrels if str(row.get("docid")) not in corpus_by_id}
    )
    missing_qids = sorted(
        {str(row.get("qid")) for row in qrels if str(row.get("qid")) not in queries_by_id}
    )
    if missing_docids:
        errors.append(f"Qrels con docid ausente del corpus: {missing_docids[:5]}")
    if missing_qids:
        errors.append(f"Qrels con qid ausente de test_queries: {missing_qids[:5]}")

    inconsistent_qrels = []
    for row in qrels:
        query = queries_by_id.get(str(row.get("qid")))
        document = corpus_by_id.get(str(row.get("docid")))
        expected_case = str(row.get("case_id") or "")
        if query and str(query.get("case_id") or "") != expected_case:
            inconsistent_qrels.append(str(row.get("qid")))
        if document and str(document.get("case_id") or "") != expected_case:
            inconsistent_qrels.append(str(row.get("qid")))
    if inconsistent_qrels:
        errors.append(
            f"Qrels con case_id inconsistente respecto a query/corpus: "
            f"{sorted(set(inconsistent_qrels))[:5]}"
        )

    manifest_train = {str(value) for value in manifest.get("train_cases", [])}
    manifest_test = {str(value) for value in manifest.get("test_cases", [])}
    if train_cases != manifest_train:
        errors.append("Los case_id de training.json no coinciden con split_manifest.json.")
    if test_cases != manifest_test:
        errors.append("Los case_id de test_queries.jsonl no coinciden con split_manifest.json.")
    if manifest_train & manifest_test:
        errors.append("El manifiesto contiene case_id tanto en train como en test.")

    expected_counts = {
        "train_records": len(training),
        "test_records": len(queries),
        "total_records": len(training) + len(queries),
        "total_cases": len(train_cases) + len(test_cases),
    }
    manifest_count_mismatches = {
        key: {"manifest": manifest.get(key), "observed": observed}
        for key, observed in expected_counts.items()
        if manifest.get(key) != observed
    }
    if manifest_count_mismatches:
        errors.append(f"Conteos distintos del manifiesto: {manifest_count_mismatches}")

    return {
        "check_type": "training_split_integrity",
        "status": "ok" if not errors else "error",
        "split_strategy": manifest.get("strategy"),
        "seed": manifest.get("seed"),
        "counts": {
            "training_rows": len(training),
            "corpus_documents": len(corpus),
            "test_queries": len(queries),
            "test_qrels": len(qrels),
            "train_cases": len(train_cases),
            "test_cases": len(test_cases),
            "case_overlap": len(overlap),
        },
        "rows_without_case_id": rows_without_case_id,
        "missing_docids": missing_docids,
        "missing_qids": missing_qids,
        "manifest_count_mismatches": manifest_count_mismatches,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica separación por sentencia e integridad de corpus, queries y qrels."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = audit(args.data_dir)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    if report["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
