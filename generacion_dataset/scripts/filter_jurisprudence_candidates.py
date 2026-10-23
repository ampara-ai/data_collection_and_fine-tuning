#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "generacion_dataset"
INPUT_DIR = GEN_DIR / "data" / "input"
INTERMEDIATE_DIR = GEN_DIR / "data" / "intermediate"

INPUT_CONTEXT = INPUT_DIR / "jurisprudence_context_units.json"
INPUT_CHUNKS_TIPO04 = INPUT_DIR / "document_chunks_tipo04.jsonl"

OUT_VF_NON_NULL = INTERMEDIATE_DIR / "jurisprudence_vf_non_null.json"
OUT_VF_FACTRICH = INTERMEDIATE_DIR / "jurisprudence_vf_factrich.json"
OUT_PDF_CANDIDATES = INTERMEDIATE_DIR / "jurisprudence_pdf_candidates_217.json"
OUT_CHUNKS_TIPO04_VF = INTERMEDIATE_DIR / "document_chunks_tipo04_vf.jsonl"
OUT_SUMMARY = INTERMEDIATE_DIR / "preparation_summary.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def main() -> None:
    items = json.loads(INPUT_CONTEXT.read_text(encoding="utf-8"))
    chunks_tipo04 = read_jsonl(INPUT_CHUNKS_TIPO04)

    vf_non_null = []
    vf_factrich = []
    pdf_candidates = []
    entry_ids_vf = set()

    for item in items:
        if item.get("status") != "success" or not item.get("context_unit"):
            continue
        cu = item["context_unit"]
        antecedent = cu.get("antecedent_signals") or {}
        rel_non_null = cu.get("violence_family_relevance") is not None
        factual = antecedent.get("has_factual_background") is True
        pdf_score = antecedent.get("pdf_utility_score")
        pdf_url = cu.get("pdf_url_mapped") or item.get("pdf_url")

        if rel_non_null:
            vf_non_null.append(item)
            entry_ids_vf.add(item.get("entry_id"))
        if rel_non_null and factual:
            vf_factrich.append(item)
        if rel_non_null and factual and pdf_score in {"alta", "media"}:
            pdf_candidates.append(
                {
                    "entry_id": item.get("entry_id"),
                    "index_page_id": item.get("index_page_id"),
                    "entry_url": item.get("entry_url"),
                    "pdf_url": pdf_url,
                    "title": cu.get("title"),
                    "document_kind_standardized": cu.get("document_kind_standardized"),
                    "detected_case_number": cu.get("detected_case_number"),
                    "violence_family_relevance": cu.get("violence_family_relevance"),
                    "antecedent_signals": antecedent,
                    "provenance_sources": item.get("provenance_sources") or [],
                }
            )

    chunks_tipo04_vf = []
    for chunk in chunks_tipo04:
        metadata = chunk.get("metadata") or {}
        chunk_entry_id = metadata.get("entry_id")
        if not chunk_entry_id:
            doc_id = chunk.get("doc_id") or ""
            if doc_id.startswith("tipo04_"):
                chunk_entry_id = doc_id.removeprefix("tipo04_")
        if chunk_entry_id in entry_ids_vf:
            chunks_tipo04_vf.append(chunk)

    write_json(OUT_VF_NON_NULL, vf_non_null)
    write_json(OUT_VF_FACTRICH, vf_factrich)
    write_json(OUT_PDF_CANDIDATES, pdf_candidates)
    write_jsonl(OUT_CHUNKS_TIPO04_VF, chunks_tipo04_vf)

    summary = {
        "jurisprudence_context_units_total": len(items),
        "vf_non_null": len(vf_non_null),
        "vf_factrich": len(vf_factrich),
        "pdf_candidates": len(pdf_candidates),
        "chunks_tipo04_vf": len(chunks_tipo04_vf),
        "outputs": {
            "vf_non_null": str(OUT_VF_NON_NULL),
            "vf_factrich": str(OUT_VF_FACTRICH),
            "pdf_candidates": str(OUT_PDF_CANDIDATES),
            "chunks_tipo04_vf": str(OUT_CHUNKS_TIPO04_VF),
        },
    }
    write_json(OUT_SUMMARY, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
