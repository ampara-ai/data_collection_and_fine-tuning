#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from legal_data.paths import PROCESSED_DIR, RAW_DIR
from legal_data.storage import write_json

FILTERED_INPUT = PROCESSED_DIR / "jurisprudence_entry_detail_classification_10.json"
PDF_CANDIDATES_OUTPUT = PROCESSED_DIR / "jurisprudence_pdf_candidates_10.json"
PDF_MANIFEST_OUTPUT = PROCESSED_DIR / "pdf_download_manifest_10.json"
PDF_DIR = RAW_DIR / "pdfs_sample_10"

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_pdf_url(entry_url: str) -> tuple[str | None, str | None]:
    response = requests.get(entry_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    title = soup.title.get_text(" ", strip=True) if soup.title else None

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if ".pdf" in href.lower():
            return urljoin(entry_url, href), title

    return None, title


def _download_pdf(pdf_url: str, output_path: Path) -> dict[str, Any]:
    response = requests.get(pdf_url, headers=HEADERS, timeout=60)
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
    items = json.loads(FILTERED_INPUT.read_text(encoding="utf-8"))
    targets = [
        x for x in items
        if (x.get("detail_llm") or {}).get("relevance_status") in {"accepted", "conditional"} and x.get("entry_url")
    ]

    pdf_candidates = []
    manifest = []

    for item in targets:
        entry_id = item["entry_id"]
        entry_url = item["entry_url"]
        detail_llm = item.get("detail_llm") or {}
        try:
            pdf_url = detail_llm.get("pdf_url")
            detail_page_title = item.get("detail_page_title")
            if not pdf_url:
                pdf_url, detail_page_title = _resolve_pdf_url(entry_url)
            candidate = {
                "entry_id": entry_id,
                "entry_url": entry_url,
                "relevance_status": detail_llm.get("relevance_status"),
                "pdf_url": pdf_url,
                "pdf_found": bool(pdf_url),
                "pdf_resolution_status": "success" if pdf_url else "not_found",
                "detail_page_title": detail_page_title,
                "resolution_reference_raw": item.get("resolution_reference_raw"),
            }
            pdf_candidates.append(candidate)

            if pdf_url and detail_llm.get("relevance_status") == "accepted":
                output_path = PDF_DIR / f"{entry_id}.pdf"
                downloaded = _download_pdf(pdf_url, output_path)
                manifest.append(
                    {
                        "entry_id": entry_id,
                        "pdf_url": pdf_url,
                        **downloaded,
                    }
                )
        except Exception as exc:
            pdf_candidates.append(
                {
                    "entry_id": entry_id,
                    "entry_url": entry_url,
                    "relevance_status": detail_llm.get("relevance_status"),
                    "pdf_url": None,
                    "pdf_found": False,
                    "pdf_resolution_status": f"error: {exc}",
                    "detail_page_title": item.get("detail_page_title"),
                    "resolution_reference_raw": item.get("resolution_reference_raw"),
                }
            )
            manifest.append(
                {
                    "entry_id": entry_id,
                    "pdf_url": None,
                    "download_status": f"error: {exc}",
                    "local_pdf_path": None,
                    "sha256": None,
                    "bytes": None,
                }
            )

    write_json(PDF_CANDIDATES_OUTPUT, pdf_candidates)
    write_json(PDF_MANIFEST_OUTPUT, manifest)
    print(json.dumps({
        "targets": len(targets),
        "pdf_candidates": len(pdf_candidates),
        "downloaded": sum(1 for x in manifest if x.get("download_status") == "success"),
        "manifest_path": str(PDF_MANIFEST_OUTPUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
