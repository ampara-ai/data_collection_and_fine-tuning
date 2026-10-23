#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Any

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_text

INPUT_JSON = PROCESSED_DIR / "documents_corpus.json"
OUTPUT_JSONL = PROCESSED_DIR / "normalized_documents.jsonl"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _doc(item: dict[str, Any]) -> dict[str, Any]:
    raw_id = str(item.get("id") or "sin_id")
    doc_id = f"tipo05_{raw_id}"
    text = item.get("text") or ""
    topic_tags = ["documento_institucional", str(item.get("institution") or "institucion_desconocida").lower().replace(" ", "_")]
    subtype = item.get("subtype")
    if subtype:
        topic_tags.append(str(subtype).lower().replace(" ", "_"))

    return {
        "doc_id": doc_id,
        "doc_type": "institutional_document_section",
        "source_type": "tipo_05_documentos_institucionales",
        "source_trace": {
            "source_url": item.get("url"),
            "source_path": item.get("raw_html_path"),
            "source_entity": str(item.get("institution") or "otro").lower().replace(" ", "_"),
            "index_page_id": None,
            "index_page_url": None,
            "entry_id": item.get("id"),
            "entry_url": item.get("url"),
            "pdf_url": None,
            "pdf_sha256": None,
            "collected_at": _now_iso(),
        },
        "document_metadata": {
            "title": item.get("title") or raw_id,
            "short_title": item.get("page_title") or item.get("title"),
            "language": "es",
            "jurisdiction": "Perú",
            "issuing_body": item.get("institution"),
            "publication_date": None,
            "document_date_text": None,
            "resolution_reference": None,
            "resolution_type": item.get("document_type"),
            "article_id": None,
            "article_heading": None,
            "chapter": None,
            "section": item.get("subtype"),
            "topic_tags": topic_tags,
        },
        "content_units": [
            {
                "unit_id": f"{doc_id}_clean_text",
                "unit_type": "clean_text",
                "text": text,
                "order": 1,
            }
        ] if text else [],
        "normalization_signals": {
            "normalization_status": "success" if text else "missing_text",
            "summary_status": "pending",
            "chunking_ready": bool(text),
            "needs_review": not bool(text),
            "notes": item.get("access"),
        },
    }


def main() -> None:
    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    docs = [_doc(item) for item in items]
    write_text(OUTPUT_JSONL, "\n".join(json.dumps(d, ensure_ascii=False) for d in docs) + "\n")
    print(json.dumps({"documents_total": len(docs), "output_path": str(OUTPUT_JSONL)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
