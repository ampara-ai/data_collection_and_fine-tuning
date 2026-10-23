#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "generacion_dataset"
INTERMEDIATE_DIR = GEN_DIR / "data" / "intermediate"
RAW_DIR = GEN_DIR / "data" / "raw"
PDF_DIR = RAW_DIR / "pdf_candidates"

INPUT_JSON = INTERMEDIATE_DIR / "jurisprudence_pdf_candidates_217.json"
OUTPUT_JSON = INTERMEDIATE_DIR / "pdf_download_manifest_217.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_pdf(pdf_url: str, output_path: Path) -> dict[str, Any]:
    response = requests.get(pdf_url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return {
        "download_status": "success",
        "local_pdf_path": str(output_path),
        "sha256": _sha256_file(output_path),
        "bytes": output_path.stat().st_size,
    }


def main() -> None:
    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    manifest = []

    for idx, item in enumerate(items, start=1):
        entry_id = item.get("entry_id") or f"entry_{idx:04d}"
        pdf_url = item.get("pdf_url")
        title = item.get("title")
        print(f"[{idx}/{len(items)}] downloading {entry_id}", flush=True)

        if not pdf_url:
            manifest.append(
                {
                    "entry_id": entry_id,
                    "index_page_id": item.get("index_page_id"),
                    "title": title,
                    "entry_url": item.get("entry_url"),
                    "pdf_url": None,
                    "download_status": "missing_pdf_url",
                    "local_pdf_path": None,
                    "sha256": None,
                    "bytes": None,
                    "document_kind_standardized": item.get("document_kind_standardized"),
                    "detected_case_number": item.get("detected_case_number"),
                    "antecedent_signals": item.get("antecedent_signals") or {},
                    "provenance_sources": item.get("provenance_sources") or [],
                }
            )
            continue

        try:
            output_path = PDF_DIR / f"{entry_id}.pdf"
            downloaded = _download_pdf(pdf_url, output_path)
            manifest.append(
                {
                    "entry_id": entry_id,
                    "index_page_id": item.get("index_page_id"),
                    "title": title,
                    "entry_url": item.get("entry_url"),
                    "pdf_url": pdf_url,
                    **downloaded,
                    "document_kind_standardized": item.get("document_kind_standardized"),
                    "detected_case_number": item.get("detected_case_number"),
                    "antecedent_signals": item.get("antecedent_signals") or {},
                    "provenance_sources": item.get("provenance_sources") or [],
                }
            )
        except Exception as exc:
            manifest.append(
                {
                    "entry_id": entry_id,
                    "index_page_id": item.get("index_page_id"),
                    "title": title,
                    "entry_url": item.get("entry_url"),
                    "pdf_url": pdf_url,
                    "download_status": f"error: {exc}",
                    "local_pdf_path": None,
                    "sha256": None,
                    "bytes": None,
                    "document_kind_standardized": item.get("document_kind_standardized"),
                    "detected_case_number": item.get("detected_case_number"),
                    "antecedent_signals": item.get("antecedent_signals") or {},
                    "provenance_sources": item.get("provenance_sources") or [],
                }
            )

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "targets": len(items),
        "downloaded": sum(1 for x in manifest if x.get("download_status") == "success"),
        "errors": sum(1 for x in manifest if str(x.get("download_status", "")).startswith("error:")),
        "missing_pdf_url": sum(1 for x in manifest if x.get("download_status") == "missing_pdf_url"),
        "manifest_path": str(OUTPUT_JSON),
        "pdf_dir": str(PDF_DIR),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
