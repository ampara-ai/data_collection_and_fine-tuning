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


def main() -> None:
    docs = _read_jsonl(INPUT_JSONL)
    chunks = []
    for doc in docs:
        if not (doc.get("normalization_signals") or {}).get("chunking_ready"):
            continue
        metadata = doc.get("document_metadata") or {}
        source_trace = doc.get("source_trace") or {}
        for idx, unit in enumerate(doc.get("content_units") or [], start=1):
            if unit.get("unit_type") not in {"clean_text", "clean_markdown"} or not unit.get("text"):
                continue
            topic_tags = metadata.get("topic_tags") or []
            chunks.append(
                {
                    "chunk_id": f"chunk_{doc['doc_id']}_{idx:02d}",
                    "doc_id": doc["doc_id"],
                    "doc_type": doc["doc_type"],
                    "source_type": doc["source_type"],
                    "chunk_type": "institutional_section",
                    "title": metadata.get("title") or doc["doc_id"],
                    "text": unit.get("text"),
                    "order": idx,
                    "metadata": {
                        "source_url": source_trace.get("source_url"),
                        "article_id": None,
                        "resolution_reference": None,
                        "resolution_type": metadata.get("resolution_type"),
                        "issuing_body": metadata.get("issuing_body"),
                        "topic_tags": topic_tags,
                        "parent_unit_type": unit.get("unit_type"),
                    },
                    "retrieval_tags": topic_tags,
                }
            )
    write_text(OUTPUT_JSONL, "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks) + "\n")
    print(json.dumps({"documents_total": len(docs), "chunks_total": len(chunks), "output_path": str(OUTPUT_JSONL)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
