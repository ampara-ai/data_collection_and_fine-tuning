#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from legal_data import (
    ResumeAILegalAnalysisRequest,
    analyze_pdf_with_resumeai_legal,
    persist_enriched_case,
)

PDF_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/raw/sample_case.pdf")
OUTPUT_PATH = Path(
    "recoleccion/data_types/tipo_04_jurisprudencia/data/processed/resumeai_enriched_case_sample.json"
)


def main() -> None:
    request = ResumeAILegalAnalysisRequest(
        pdf_path=PDF_PATH,
        source_url="https://ejemplo.local/caso",
        title="Caso de muestra",
        resolution_reference_raw="Exp. 00000-2023",
        jurisprudence_type="juzgado_familia",
        verbose=False,
        similarity_threshold=0.85,
    )
    enriched = analyze_pdf_with_resumeai_legal(request)
    persist_enriched_case(enriched, output_path=OUTPUT_PATH)
    print(json.dumps(enriched.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
