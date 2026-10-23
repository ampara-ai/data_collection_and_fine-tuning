#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TIPO04_SRC = ROOT / "recoleccion" / "data_types" / "tipo_04_jurisprudencia" / "src"
if str(TIPO04_SRC) not in sys.path:
    sys.path.insert(0, str(TIPO04_SRC))

from legal_data.resumeai_client import (  # type: ignore
    ResumeAILegalAnalysisRequest,
    analyze_pdf_with_resumeai_legal,
    persist_enriched_case,
)

GEN_DIR = ROOT / "generacion_dataset"
INTERMEDIATE_DIR = GEN_DIR / "data" / "intermediate"
BATCH_DIR = INTERMEDIATE_DIR / "resumeai_batch"
OUTPUT_CASES_DIR = BATCH_DIR / "cases"
INPUT_JSON = INTERMEDIATE_DIR / "pdf_download_manifest_217.json"
MANIFEST_JSON = BATCH_DIR / "resumeai_batch_manifest.json"
SUMMARY_JSON = BATCH_DIR / "resumeai_batch_summary.json"


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_summary(manifest: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_records": len(manifest),
        "success": sum(1 for x in manifest if x.get("status") == "success"),
        "error": sum(1 for x in manifest if x.get("status") == "error"),
        "skipped": sum(1 for x in manifest if x.get("status") == "skipped"),
        "dataset_candidates": sum(1 for x in manifest if (x.get("factual_density_signals") or {}).get("is_dataset_candidate") is True),
        "fact_rich_minimum": sum(1 for x in manifest if (x.get("factual_density_signals") or {}).get("is_fact_rich_minimum") is True),
        "output_cases_dir": str(OUTPUT_CASES_DIR),
        "manifest_path": str(MANIFEST_JSON),
    }


def main() -> None:
    api_base_url = os.environ.get("RESUMEAI_API_BASE_URL", "http://127.0.0.1:8000")
    similarity_threshold = float(os.environ.get("RESUMEAI_SIMILARITY_THRESHOLD", "0.85"))
    timeout_sec = int(os.environ.get("RESUMEAI_TIMEOUT_SEC", "1800"))

    items = load_json(INPUT_JSON, [])
    previous_manifest = load_json(MANIFEST_JSON, [])
    previous_by_entry = {item.get("entry_id"): item for item in previous_manifest}

    targets = [x for x in items if x.get("download_status") == "success" and x.get("local_pdf_path")]
    manifest = list(previous_manifest)

    OUTPUT_CASES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"ResumeAI batch: {len(targets)} PDFs descargados elegibles")
    print(f"Resultados previos detectados: {len(previous_manifest)}")
    print("-" * 60)

    for idx, item in enumerate(targets, start=1):
        entry_id = item.get("entry_id")
        if entry_id in previous_by_entry and previous_by_entry[entry_id].get("status") == "success":
            print(f"[{idx}/{len(targets)}] {entry_id} -> skipped (ya procesado con success)", flush=True)
            continue

        print(f"[{idx}/{len(targets)}] {entry_id} -> processing", flush=True)
        try:
            request = ResumeAILegalAnalysisRequest(
                pdf_path=item["local_pdf_path"],
                source_url=item.get("entry_url"),
                title=item.get("title"),
                resolution_reference_raw=item.get("detected_case_number"),
                jurisprudence_type=item.get("document_kind_standardized"),
                verbose=False,
                similarity_threshold=similarity_threshold,
            )
            enriched = analyze_pdf_with_resumeai_legal(
                request,
                api_base_url=api_base_url,
                timeout_sec=timeout_sec,
            )
            output_path = OUTPUT_CASES_DIR / f"{entry_id}.json"
            persist_enriched_case(enriched, output_path=output_path)

            record = {
                "entry_id": entry_id,
                "index_page_id": item.get("index_page_id"),
                "title": item.get("title"),
                "entry_url": item.get("entry_url"),
                "pdf_url": item.get("pdf_url"),
                "local_pdf_path": item.get("local_pdf_path"),
                "resumeai_output_path": str(output_path),
                "status": "success",
                "run_id": enriched.resumeai_run.run_id,
                "resumeai_status": enriched.resumeai_run.status,
                "factual_density_signals": enriched.factual_density_signals,
                "document_kind_standardized": item.get("document_kind_standardized"),
                "detected_case_number": item.get("detected_case_number"),
                "antecedent_signals": item.get("antecedent_signals") or {},
                "provenance_sources": item.get("provenance_sources") or [],
            }
            previous_by_entry[entry_id] = record
            manifest = list(previous_by_entry.values())
            save_json(MANIFEST_JSON, manifest)
            save_json(SUMMARY_JSON, build_summary(manifest))
            print(f"[{idx}/{len(targets)}] {entry_id} -> success | dataset_candidate={(enriched.factual_density_signals or {}).get('is_dataset_candidate')}", flush=True)
        except Exception as exc:
            record = {
                "entry_id": entry_id,
                "index_page_id": item.get("index_page_id"),
                "title": item.get("title"),
                "entry_url": item.get("entry_url"),
                "pdf_url": item.get("pdf_url"),
                "local_pdf_path": item.get("local_pdf_path"),
                "resumeai_output_path": None,
                "status": "error",
                "error": str(exc),
                "document_kind_standardized": item.get("document_kind_standardized"),
                "detected_case_number": item.get("detected_case_number"),
                "antecedent_signals": item.get("antecedent_signals") or {},
                "provenance_sources": item.get("provenance_sources") or [],
            }
            previous_by_entry[entry_id] = record
            manifest = list(previous_by_entry.values())
            save_json(MANIFEST_JSON, manifest)
            save_json(SUMMARY_JSON, build_summary(manifest))
            print(f"[{idx}/{len(targets)}] {entry_id} -> error | {exc}", flush=True)

    print("-" * 60)
    final_summary = build_summary(list(previous_by_entry.values()))
    save_json(SUMMARY_JSON, final_summary)
    print(json.dumps(final_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
