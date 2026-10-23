#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

from legal_data.paths import PROCESSED_DIR
from legal_data.spij_parser import parse_spij_detail_to_law
from legal_data.storage import write_json, write_text

DEFAULT_INPUT = Path("data/raw/spij/H1141065/detail.json")
OUTPUT_JSON = PROCESSED_DIR / "law_30364_structured.json"
OUTPUT_JSONL = PROCESSED_DIR / "normalized_documents.jsonl"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    detail = json.loads(input_path.read_text(encoding="utf-8"))
    law = parse_spij_detail_to_law(detail)
    structured = law.to_dict()
    write_json(OUTPUT_JSON, structured)

    docs = []
    for article in structured.get("articles", []):
        article_id = str(article.get("article_id") or "sin_id")
        doc_id = f"tipo01_ley30364_art_{article_id.lower().replace(' ', '_').replace('.', '_')}"
        text = article.get("text") or ""
        docs.append(
            {
                "doc_id": doc_id,
                "doc_type": "ley_article",
                "source_type": "tipo_01_ley_30364",
                "source_trace": {
                    "source_url": None,
                    "source_path": str(input_path),
                    "source_entity": "spij",
                    "index_page_id": None,
                    "index_page_url": None,
                    "entry_id": structured.get("norm_id"),
                    "entry_url": None,
                    "pdf_url": None,
                    "pdf_sha256": None,
                    "collected_at": _now_iso(),
                },
                "document_metadata": {
                    "title": article.get("heading") or article_id,
                    "short_title": article.get("heading") or article_id,
                    "language": "es",
                    "jurisdiction": "Perú",
                    "issuing_body": structured.get("metadata", {}).get("sector") or structured.get("code"),
                    "publication_date": structured.get("metadata", {}).get("fechaPublicacion"),
                    "document_date_text": structured.get("metadata", {}).get("fechaPublicacion"),
                    "resolution_reference": structured.get("code"),
                    "resolution_type": structured.get("metadata", {}).get("dispositivoLegal"),
                    "article_id": article.get("article_id"),
                    "article_heading": article.get("heading"),
                    "chapter": None,
                    "section": None,
                    "topic_tags": ["ley_30364", "violencia_familiar", "articulo"],
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
                    "notes": None,
                },
            }
        )

    write_text(OUTPUT_JSONL, "\n".join(json.dumps(d, ensure_ascii=False) for d in docs) + "\n")
    print(json.dumps({"articles_total": len(structured.get('articles', [])), "documents_total": len(docs), "output_path": str(OUTPUT_JSONL)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
