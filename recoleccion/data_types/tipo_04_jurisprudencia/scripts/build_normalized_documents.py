#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Any

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_text

INPUT_JSON = PROCESSED_DIR / "jurisprudence_context_units.json"
OUTPUT_JSONL = PROCESSED_DIR / "normalized_documents.jsonl"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_topic_tags(item: dict[str, Any], unit: dict[str, Any]) -> list[str]:
    tags = ["jurisprudencia", "lp_derecho"]
    for source in item.get("provenance_sources") or []:
        article_id = source.get("source_article_id")
        source_type = source.get("source_type")
        candidate_status = source.get("candidate_status")
        if source_type:
            tags.append(str(source_type).lower())
        if article_id:
            tags.append(f"articulo_{str(article_id).lower().replace(' ', '_')}")
        if candidate_status:
            tags.append(str(candidate_status).lower())
    doc_kind = unit.get("document_kind_standardized")
    if doc_kind:
        tags.append(str(doc_kind).lower().replace(" ", "_"))
    for kw in unit.get("keywords") or []:
        if kw:
            tags.append(str(kw).lower().replace(" ", "_"))
    deduped = []
    seen = set()
    for tag in tags:
        if tag not in seen:
            deduped.append(tag)
            seen.add(tag)
    return deduped


def _render_text(unit: dict[str, Any]) -> str:
    parts = []
    title = unit.get("title")
    if title:
        parts.append(f"Título: {title}")
    doc_kind = unit.get("document_kind_standardized")
    if doc_kind:
        parts.append(f"Tipo de resolución: {doc_kind}")
    if unit.get("facts_summary"):
        parts.append(f"Hechos relevantes: {unit['facts_summary']}")
    if unit.get("legal_issue"):
        parts.append(f"Problema jurídico: {unit['legal_issue']}")
    if unit.get("holding"):
        parts.append(f"Criterio principal: {unit['holding']}")
    if unit.get("reasoning_summary"):
        parts.append(f"Fundamentación resumida: {unit['reasoning_summary']}")
    if unit.get("outcome"):
        parts.append(f"Decisión o resultado: {unit['outcome']}")
    if unit.get("violence_family_relevance"):
        parts.append(f"Relevancia para violencia familiar: {unit['violence_family_relevance']}")
    if unit.get("procedural_relevance"):
        parts.append(f"Relevancia procesal: {unit['procedural_relevance']}")
    if unit.get("practical_context_summary"):
        parts.append(f"Contexto práctico: {unit['practical_context_summary']}")
    norms = unit.get("applicable_norms") or []
    if norms:
        norm_parts = []
        for n in norms:
            norm_name = n.get("norm_standardized") or n.get("norm_raw_text") or "Norma no especificada"
            articles_list = n.get("articles") or []
            if articles_list:
                norm_parts.append(f"{norm_name} art(s). {', '.join(articles_list)}")
            else:
                norm_parts.append(norm_name)
        parts.append(f"Normas aplicables: {'; '.join(norm_parts)}")
    return "\n".join(parts)


def _normalized_doc(item: dict[str, Any]) -> dict[str, Any]:
    unit = item.get("context_unit") or {}
    doc_id = f"tipo04_{item['entry_id']}"
    rendered_text = _render_text(unit)
    topic_tags = _build_topic_tags(item, unit)

    return {
        "doc_id": doc_id,
        "doc_type": "jurisprudencia_contextualizada",
        "source_type": "tipo_04_jurisprudencia",
        "source_trace": {
            "source_url": item.get("entry_url"),
            "source_path": None,
            "source_entity": "lpderecho",
            "index_page_id": item.get("index_page_id"),
            "index_page_url": None,
            "entry_id": item.get("entry_id"),
            "entry_url": item.get("entry_url"),
            "pdf_url": unit.get("pdf_url_mapped") or item.get("pdf_url"),
            "pdf_sha256": None,
            "collected_at": _now_iso(),
        },
        "document_metadata": {
            "title": unit.get("title") or item.get("entry_id"),
            "short_title": unit.get("title") or item.get("entry_id"),
            "language": "es",
            "jurisdiction": "Perú",
            "issuing_body": unit.get("document_kind_standardized"),
            "publication_date": None,
            "document_date_text": None,
            "resolution_reference": unit.get("detected_case_number") or unit.get("detected_resolution_label"),
            "resolution_type": unit.get("document_kind_standardized"),
            "article_id": None,
            "article_heading": None,
            "chapter": None,
            "section": unit.get("document_kind_raw"),
            "topic_tags": topic_tags,
        },
        "content_units": [
            {
                "unit_id": f"{doc_id}_context_unit",
                "unit_type": "jurisprudence_context_unit",
                "text": rendered_text,
                "order": 1,
                "structured_data": unit,
            }
        ] if rendered_text else [],
        "normalization_signals": {
            "normalization_status": "success" if rendered_text else "missing_context_unit",
            "summary_status": "success" if item.get("status") == "success" else item.get("status"),
            "chunking_ready": bool(rendered_text),
            "needs_review": bool(unit.get("needs_review")),
            "notes": None,
        },
    }


def main() -> None:
    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    docs = [_normalized_doc(item) for item in items if item.get("status") == "success" and item.get("context_unit")]
    write_text(OUTPUT_JSONL, "\n".join(json.dumps(doc, ensure_ascii=False) for doc in docs) + ("\n" if docs else ""))
    print(json.dumps({
        "documents_total": len(docs),
        "chunking_ready": sum(1 for d in docs if d["normalization_signals"]["chunking_ready"]),
        "needs_review": sum(1 for d in docs if d["normalization_signals"]["needs_review"]),
        "output_path": str(OUTPUT_JSONL),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
