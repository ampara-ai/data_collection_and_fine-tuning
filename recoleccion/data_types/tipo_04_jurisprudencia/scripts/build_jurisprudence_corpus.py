#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from legal_data.collector import collect_jurisprudence_sources, deduplicate_by_url, fetch_jurisprudence_page
from legal_data.storage import write_json, write_text

PENAL_CANDIDATES = "recoleccion/data_types/tipo_02_codigo_penal/data/processed/candidate_articles.json"
CPP_CANDIDATES = "recoleccion/data_types/tipo_03_codigo_procesal_penal/data/processed/candidate_articles.json"

INDEX_PATH = "recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_index.json"
METADATA_PATH = "recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_metadata.json"
RAW_DIR = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/raw/html")


def main() -> None:
    collected = collect_jurisprudence_sources([PENAL_CANDIDATES, CPP_CANDIDATES])
    deduped = deduplicate_by_url(collected)

    metadata = []
    for idx, item in enumerate(deduped, start=1):
        page = fetch_jurisprudence_page(item["jurisprudence_url"])
        slug = f"jp_{idx:04d}"
        raw_path = RAW_DIR / f"{slug}.html"
        write_text(raw_path, page["html"])
        metadata.append(
            {
                "id": slug,
                "jurisprudence_url": item["jurisprudence_url"],
                "title": page["title"],
                "sha256": page["sha256"],
                "raw_html_path": str(raw_path),
                "linked_articles": item["linked_articles"],
            }
        )

    write_json(INDEX_PATH, deduped)
    write_json(METADATA_PATH, metadata)
    print({"raw_links": len(collected), "unique_links": len(deduped), "downloaded": len(metadata)})


if __name__ == "__main__":
    main()
