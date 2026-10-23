#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

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
SAMPLE_DIR = INTERMEDIATE_DIR / "resumeai_sample"
INPUT_JSON = INTERMEDIATE_DIR / "pdf_download_manifest_217.json"
SUMMARY_JSON = SAMPLE_DIR / "resumeai_sample_summary.json"


def pick_target(items: list[dict], entry_id: str | None = None) -> dict:
    success_items = [x for x in items if x.get("download_status") == "success" and x.get("local_pdf_path")]
    if entry_id:
        for item in success_items:
            if item.get("entry_id") == entry_id:
                return item
        raise ValueError(f"No se encontró entry_id exitoso: {entry_id}")
    if not success_items:
        raise ValueError("No hay PDFs descargados con éxito en el manifiesto")
    return success_items[0]


def main() -> None:
    entry_id = sys.argv[1] if len(sys.argv) > 1 else None
    api_base_url = os.environ.get("RESUMEAI_API_BASE_URL", "http://127.0.0.1:8000")
    similarity_threshold = float(os.environ.get("RESUMEAI_SIMILARITY_THRESHOLD", "0.85"))

    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    target = pick_target(items, entry_id=entry_id)

    request = ResumeAILegalAnalysisRequest(
        pdf_path=target["local_pdf_path"],
        source_url=target.get("entry_url"),
        title=target.get("title"),
        resolution_reference_raw=target.get("detected_case_number"),
        jurisprudence_type=target.get("document_kind_standardized"),
        verbose=False,
        similarity_threshold=similarity_threshold,
    )

    enriched = analyze_pdf_with_resumeai_legal(
        request,
        api_base_url=api_base_url,
        timeout_sec=1800,
    )

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SAMPLE_DIR / f"{target['entry_id']}.json"
    persist_enriched_case(enriched, output_path=output_path)

    summary = {
        "entry_id": target.get("entry_id"),
        "title": target.get("title"),
        "local_pdf_path": target.get("local_pdf_path"),
        "api_base_url": api_base_url,
        "output_path": str(output_path),
        "factual_density_signals": enriched.factual_density_signals,
        "resumeai_status": enriched.resumeai_run.status,
        "run_id": enriched.resumeai_run.run_id,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
