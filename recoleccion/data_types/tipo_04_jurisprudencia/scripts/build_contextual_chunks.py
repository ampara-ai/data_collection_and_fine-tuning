#!/usr/bin/env python3
from __future__ import annotations

import json

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_text

INPUT_JSON = PROCESSED_DIR / "jurisprudence_context_units.json"
OUTPUT_JSONL = PROCESSED_DIR / "document_chunks.jsonl"


def _render_text(unit: dict) -> str:
    parts = []
    title = unit.get("title")
    if title:
        parts.append(f"Título: {title}")
    
    # Añadimos el tipo de documento estandarizado al texto del chunk para darle más contexto al LLM en el retrieval
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
        
    # --- ACTUALIZACIÓN DE NORMAS ---
    norms = unit.get("applicable_norms") or []
    if norms:
        norm_parts = []
        for n in norms:
            # Usamos el nombre estandarizado (o el raw si por alguna razón falla)
            norm_name = n.get("norm_standardized") or n.get("norm_raw_text") or "Norma no especificada"
            articles_list = n.get("articles") or []
            
            if articles_list:
                # Unimos la lista de artículos con comas
                art_text = f"art(s). {', '.join(articles_list)}"
                norm_parts.append(f"{norm_name} {art_text}")
            else:
                norm_parts.append(norm_name)
                
        norm_text = "; ".join(norm_parts)
        parts.append(f"Normas aplicables: {norm_text}")
        
    return "\n".join(parts)


def main() -> None:
    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    chunks = []
    for item in items:
        if item.get("status") != "success" or not item.get("context_unit"):
            continue
        unit = item["context_unit"]
        keywords = unit.get("keywords") or []
        chunks.append(
            {
                "chunk_id": f"chunk_{item['entry_id']}",
                "doc_id": f"tipo04_{item['entry_id']}",
                "doc_type": "jurisprudencia_contextualizada",
                "source_type": "tipo_04_jurisprudencia",
                "chunk_type": "jurisprudence_context_unit",
                "title": unit.get("title") or item.get("entry_id"),
                "text": _render_text(unit),
                "order": 1,
                "metadata": {
                    "source_url": item.get("entry_url"),
                    "article_id": None,
                    "resolution_reference": unit.get("detected_case_number") or unit.get("detected_resolution_label"),
                    "resolution_type": unit.get("document_kind_standardized"),
                    "issuing_body": unit.get("document_kind_raw") or unit.get("document_kind_standardized"),
                    "topic_tags": keywords,
                    "parent_unit_type": "jurisprudence_context_unit",
                    "entry_id": item.get("entry_id"),
                    "index_page_id": item.get("index_page_id"),
                    "entry_url": item.get("entry_url"),
                    "pdf_url": item.get("pdf_url"),
                    "pdf_url_mapped": unit.get("pdf_url_mapped"),
                    "document_kind_standardized": unit.get("document_kind_standardized"),
                    "document_kind_raw": unit.get("document_kind_raw"),
                    "detected_resolution_label": unit.get("detected_resolution_label"),
                    "detected_case_number": unit.get("detected_case_number"),
                    "applicable_norms": unit.get("applicable_norms") or [],
                    "keywords": keywords,
                    "source_provenance": item.get("provenance_sources") or [],
                    "llm_relevance_score": unit.get("llm_relevance_score"),
                    "needs_review": unit.get("needs_review"),
                    "antecedent_signals": unit.get("antecedent_signals") or {},
                },
                "retrieval_tags": keywords,
            }
        )
    write_text(OUTPUT_JSONL, "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks) + ("\n" if chunks else ""))
    print(json.dumps({"chunks_total": len(chunks), "output_path": str(OUTPUT_JSONL)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()