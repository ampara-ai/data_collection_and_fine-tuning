#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from legal_data.parser import parse_jurisprudence_file
from legal_data.storage import write_json

METADATA_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_metadata.json")
PARSED_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_parsed.json")
SUMMARY_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_parsed_summary.json")


def main() -> None:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    parsed = []

    for item in metadata:
        raw_path = item["raw_html_path"]
        parsed_item = parse_jurisprudence_file(
            raw_path,
            source_url=item["jurisprudence_url"],
            linked_articles=item.get("linked_articles", []),
        )
        parsed_item["id"] = item["id"]
        parsed_item["sha256"] = item["sha256"]
        parsed.append(parsed_item)

    summary = {
        "parsed_documents": len(parsed),
        "documents_with_entries": sum(1 for p in parsed if p.get("jurisprudence_entries")),
    }

    write_json(PARSED_PATH, parsed)
    write_json(SUMMARY_PATH, summary)
    print(summary)


if __name__ == "__main__":
    main()
