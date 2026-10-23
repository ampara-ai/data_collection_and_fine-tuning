#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chunk_cleaning import clean_chunks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA_TYPES_DIR = ROOT / "data_types"
OUTPUT_DIR = ROOT / "data" / "processed"
OUTPUT_JSONL = OUTPUT_DIR / "document_chunks_all.jsonl"            # corpus FINAL (limpio): lo que usan la generación y la indexación
OUTPUT_RAW = OUTPUT_DIR / "document_chunks_all.raw.jsonl"          # concatenación de los chunks de cada tipo, sin limpiar
OUTPUT_CLEANING_REPORT = OUTPUT_DIR / "document_chunks_cleaning_report.json"
OUTPUT_SUMMARY = OUTPUT_DIR / "document_chunks_summary.json"

TYPE_PATHS = {
    "tipo_01_ley_30364": DATA_TYPES_DIR / "tipo_01_ley_30364" / "data" / "processed" / "document_chunks.jsonl",
    "tipo_02_codigo_penal": DATA_TYPES_DIR / "tipo_02_codigo_penal" / "data" / "processed" / "document_chunks.jsonl",
    "tipo_03_codigo_procesal_penal": DATA_TYPES_DIR / "tipo_03_codigo_procesal_penal" / "data" / "processed" / "document_chunks.jsonl",
    "tipo_04_jurisprudencia": DATA_TYPES_DIR / "tipo_04_jurisprudencia" / "data" / "processed" / "document_chunks.jsonl",
    "tipo_05_documentos_institucionales": DATA_TYPES_DIR / "tipo_05_documentos_institucionales" / "data" / "processed" / "document_chunks.jsonl",
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks = []
    per_type = {}
    missing = []

    for type_name, path in TYPE_PATHS.items():
        rows = read_jsonl(path)
        # Artículos citados por las sentencias que el filtro heurístico dejó fuera (los genera
        # generacion_dataset/pipeline_v2/add_cited_articles.py). Si un chunk_id ya existe, gana el del corpus base.
        cited = read_jsonl(path.with_name("document_chunks_cited.jsonl"))
        known = {r["chunk_id"] for r in rows}
        rows = rows + [r for r in cited if r["chunk_id"] not in known]
        if not rows:
            missing.append(type_name)
        per_type[type_name] = len(rows)
        all_chunks.extend(rows)

    dump = lambda rows: "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else "")
    OUTPUT_RAW.write_text(dump(all_chunks), encoding="utf-8")
    cleaned, cleaning_report = clean_chunks(all_chunks)       # ver chunk_cleaning.py: quita ruido que no aporta contenido
    OUTPUT_JSONL.write_text(dump(cleaned), encoding="utf-8")
    OUTPUT_CLEANING_REPORT.write_text(json.dumps(cleaning_report, ensure_ascii=False, indent=2), encoding="utf-8")
    per_type = {k: sum(1 for c in cleaned if c.get("source_type") == k) for k in per_type}
    summary = {
        "chunks_total": len(cleaned),
        "chunks_antes_de_limpiar": len(all_chunks),
        "per_type": per_type,
        "missing_or_empty": missing,
        "output_path": str(OUTPUT_JSONL),
    }
    OUTPUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
