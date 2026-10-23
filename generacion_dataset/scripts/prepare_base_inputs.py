#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "generacion_dataset"
INPUT_DIR = GEN_DIR / "data" / "input"
INTERMEDIATE_DIR = GEN_DIR / "data" / "intermediate"
OUTPUT_DIR = GEN_DIR / "data" / "output"
DOCS_DIR = GEN_DIR / "docs"

RECOLECCION_DIR = ROOT / "recoleccion"
SRC_CONTEXT = RECOLECCION_DIR / "data_types" / "tipo_04_jurisprudencia" / "data" / "processed" / "jurisprudence_context_units.json"
SRC_CHUNKS_ALL = RECOLECCION_DIR / "data" / "processed" / "document_chunks_all.jsonl"
SRC_CHUNKS_TIPO04 = RECOLECCION_DIR / "data_types" / "tipo_04_jurisprudencia" / "data" / "processed" / "document_chunks.jsonl"
SRC_SUMMARY = RECOLECCION_DIR / "data" / "processed" / "document_chunks_summary.json"


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    copy_file(SRC_CONTEXT, INPUT_DIR / "jurisprudence_context_units.json")
    copy_file(SRC_CHUNKS_ALL, INPUT_DIR / "document_chunks_all.jsonl")
    copy_file(SRC_CHUNKS_TIPO04, INPUT_DIR / "document_chunks_tipo04.jsonl")
    copy_file(SRC_SUMMARY, INPUT_DIR / "document_chunks_summary.json")

    summary = {
        "copied": {
            "jurisprudence_context_units": str(INPUT_DIR / "jurisprudence_context_units.json"),
            "document_chunks_all": str(INPUT_DIR / "document_chunks_all.jsonl"),
            "document_chunks_tipo04": str(INPUT_DIR / "document_chunks_tipo04.jsonl"),
            "document_chunks_summary": str(INPUT_DIR / "document_chunks_summary.json"),
        }
    }
    (INTERMEDIATE_DIR / "prepare_base_inputs_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
