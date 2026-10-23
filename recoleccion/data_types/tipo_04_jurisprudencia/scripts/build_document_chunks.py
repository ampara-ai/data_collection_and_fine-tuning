#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_text

INPUT_JSONL = PROCESSED_DIR / "normalized_documents.jsonl"
OUTPUT_JSONL = PROCESSED_DIR / "document_chunks.jsonl"


def _read_jsonl(path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _build_chunk(doc: dict[str, Any], unit: dict[str, Any], order: int) -> dict[str, Any]:
    metadata = doc.get("document_metadata") or {}
    source_trace = doc.get("source_trace") or {}
    topic_tags = metadata.get("topic_tags") or []
    structured_data = unit.get("structured_data") or {}

    return {
        "chunk_id": f"chunk_{doc['doc_id']}_{order:02d}",
        "doc_id": doc["doc_id"],
        "doc_type": doc["doc_type"],
        "source_type": doc["source_type"],
        "chunk_type": "jurisprudence_context_unit",
        "title": metadata.get("title") or doc["doc_id"],
        "text": unit.get("text") or "",
        "order": order,
        "metadata": {
            "source_url": source_trace.get("source_url"),
            "article_id": metadata.get("article_id"),
            "resolution_reference": metadata.get("resolution_reference"),
            "resolution_type": metadata.get("resolution_type"),
            "issuing_body": metadata.get("issuing_body"),
            "topic_tags": topic_tags,
            "parent_unit_type": unit.get("unit_type"),
            "pdf_url": source_trace.get("pdf_url"),
            "detected_resolution_label": structured_data.get("detected_resolution_label"),
            "detected_case_number": structured_data.get("detected_case_number"),
            "antecedent_signals": structured_data.get("antecedent_signals") or {},
        },
        "retrieval_tags": topic_tags,
    }


def main() -> None:
    docs = _read_jsonl(INPUT_JSONL)
    chunks = []
    violence_non_null = 0
    filtered_out_null_relevance = 0

    for doc in docs:
        if not (doc.get("normalization_signals") or {}).get("chunking_ready"):
            continue
        content_units = doc.get("content_units") or []
        chunkable_units = [u for u in content_units if u.get("unit_type") == "jurisprudence_context_unit" and u.get("text")]
        for idx, unit in enumerate(chunkable_units, start=1):
            structured_data = unit.get("structured_data") or {}
            if structured_data.get("violence_family_relevance") is None:
                filtered_out_null_relevance += 1
                continue
            violence_non_null += 1
            chunks.append(_build_chunk(doc, unit, idx))

    write_text(OUTPUT_JSONL, "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + ("\n" if chunks else ""))
    print(json.dumps({
        "documents_total": len(docs),
        "chunks_total": len(chunks),
        "violence_family_relevance_non_null": violence_non_null,
        "filtered_out_null_relevance": filtered_out_null_relevance,
        "output_path": str(OUTPUT_JSONL),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
