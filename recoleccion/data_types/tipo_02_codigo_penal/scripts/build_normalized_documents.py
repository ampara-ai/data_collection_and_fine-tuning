#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Any

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_text

INPUT_JSON = PROCESSED_DIR / "candidate_articles.json"
OUTPUT_JSONL = PROCESSED_DIR / "normalized_documents.jsonl"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _doc(article: dict[str, Any]) -> dict[str, Any]:
    article_id = str(article.get("article_id") or "sin_id")
    doc_id = f"tipo02_cp_art_{article_id.lower().replace(' ', '_').replace('.', '_')}"
    text = article.get("text") or ""
    candidate_status = article.get("candidate_status")
    topic_tags = ["codigo_penal", "articulo"]
    if candidate_status:
        topic_tags.append(str(candidate_status).lower())

    return {
        "doc_id": doc_id,
        "doc_type": "codigo_penal_article",
        "source_type": "tipo_02_codigo_penal",
        "source_trace": {
            "source_url": article.get("source_url"),
            "source_path": None,
            "source_entity": "lpderecho",
            "index_page_id": None,
            "index_page_url": None,
            "entry_id": None,
            "entry_url": article.get("jurisprudence_url"),
            "pdf_url": None,
            "pdf_sha256": None,
            "collected_at": _now_iso(),
        },
        "document_metadata": {
            "title": article.get("title") or article.get("heading") or article_id,
            "short_title": article.get("heading") or article.get("title"),
            "language": "es",
            "jurisdiction": "Perú",
            "issuing_body": "Código Penal",
            "publication_date": None,
            "document_date_text": None,
            "resolution_reference": None,
            "resolution_type": None,
            "article_id": article.get("article_id"),
            "article_heading": article.get("heading"),
            "chapter": None,
            "section": None,
            "topic_tags": topic_tags,
        },
        "content_units": [
            {
                "unit_id": f"{doc_id}_article_text",
                "unit_type": "structured_article_text",
                "text": text,
                "order": 1,
            }
        ] if text else [],
        "normalization_signals": {
            "normalization_status": "success" if text else "missing_text",
            "summary_status": "pending",
            "chunking_ready": bool(text),
            "needs_review": not bool(text),
            "notes": candidate_status,
        },
    }


def main() -> None:
    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    docs = [_doc(item) for item in items]
    write_text(OUTPUT_JSONL, "\n".join(json.dumps(d, ensure_ascii=False) for d in docs) + "\n")
    print(json.dumps({"documents_total": len(docs), "output_path": str(OUTPUT_JSONL)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
