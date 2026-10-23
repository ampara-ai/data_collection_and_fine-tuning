#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

from legal_data.elperuano_client import ElPeruanoClient
from legal_data.pdf_tools import extract_text_from_pdf, mentions_law_30364
from legal_data.storage import write_bytes, write_json, write_text

DEFAULT_TYPES = [
    "LEY",
    "DECRETO SUPREMO",
    "DECRETO LEGISLATIVO",
    "RESOLUCION MINISTERIAL",
]


def scan_date(date_yyyymmdd: str) -> dict:
    client = ElPeruanoClient()

    summary: dict = {
        "date": date_yyyymmdd,
        "scanned_at_utc": datetime.now(UTC).isoformat(),
        "device_types": DEFAULT_TYPES,
        "results": [],
    }

    for tipo in DEFAULT_TYPES:
        result = client.search_publications(
            fecha_ini=date_yyyymmdd,
            fecha_fin=date_yyyymmdd,
            tipo_publicacion="NL",
            tipo_dispositivo=tipo,
            start=0,
            ci="ONLY",
        )
        hits = result.get("hits", [])
        summary["results"].append(
            {
                "tipoDispositivo": tipo,
                "totalHits": result.get("totalHits", 0),
                "hasNext": result.get("hasNext", False),
                "sampleOps": [h.get("op") for h in hits[:5]],
            }
        )

    return summary


def fetch_candidates_by_query(date_yyyymmdd: str, query: str = "30364") -> dict:
    client = ElPeruanoClient()
    result = client.search_publications(
        fecha_ini=date_yyyymmdd,
        fecha_fin=date_yyyymmdd,
        tipo_publicacion="NL",
        query=query,
        start=0,
        ci="ONLY",
    )
    return result


def process_candidates(date_yyyymmdd: str, out_dir: Path) -> dict:
    client = ElPeruanoClient()
    result = fetch_candidates_by_query(date_yyyymmdd)
    hits = result.get("hits", [])

    processed = []
    for hit in hits:
        op = hit.get("op")
        pdf_url = hit.get("urlPDF")
        item_dir = out_dir / (op or "unknown")

        entry = {
            "op": op,
            "tipoDispositivo": hit.get("tipoDispositivo"),
            "sumilla": hit.get("sumilla"),
            "fechaPublicacion": hit.get("fechaPublicacion"),
            "urlPDF": pdf_url,
            "pdfDownloaded": False,
            "textExtracted": False,
            "extractor": None,
            "mentionsLaw30364": False,
            "error": None,
        }

        try:
            if pdf_url:
                pdf_bytes = client.download_pdf(pdf_url)
                write_bytes(item_dir / "document.pdf", pdf_bytes)
                entry["pdfDownloaded"] = True

                text, extractor = extract_text_from_pdf(pdf_bytes)
                write_text(item_dir / "document.txt", text)
                entry["textExtracted"] = True
                entry["extractor"] = extractor
                entry["mentionsLaw30364"] = mentions_law_30364(text)

            write_json(item_dir / "metadata.json", hit)
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)

        processed.append(entry)

    return {
        "date": date_yyyymmdd,
        "query": "30364",
        "totalHits": result.get("totalHits", 0),
        "processed": processed,
    }


def main() -> None:
    date_yyyymmdd = sys.argv[1] if len(sys.argv) > 1 else datetime.now(UTC).strftime("%Y%m%d")
    base_dir = Path("data/elperuano") / date_yyyymmdd
    summary = scan_date(date_yyyymmdd)
    candidates = process_candidates(date_yyyymmdd, base_dir / "candidates")

    write_json(base_dir / "scan_summary.json", summary)
    write_json(base_dir / "query_30364_results.json", candidates)

    print(json.dumps({"summary": summary, "candidates": candidates}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
