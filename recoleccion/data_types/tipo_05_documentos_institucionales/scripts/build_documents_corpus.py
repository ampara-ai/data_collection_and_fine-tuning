#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from legal_data.collector import extract_readable_content, fetch_html, load_inventory
from legal_data.storage import write_json, write_text

INVENTORY = "recoleccion/data_types/tipo_05_documentos_institucionales/data/state/source_inventory.json"
RAW_DIR = Path("recoleccion/data_types/tipo_05_documentos_institucionales/data/raw/html")
PROCESSED_PATH = "recoleccion/data_types/tipo_05_documentos_institucionales/data/processed/documents_corpus.json"
SUMMARY_PATH = "recoleccion/data_types/tipo_05_documentos_institucionales/data/processed/documents_summary.json"


def main() -> None:
    inventory = load_inventory(INVENTORY)
    corpus = []
    for item in inventory:
        html = fetch_html(item["url"])
        raw_path = RAW_DIR / f"{item['id']}.html"
        write_text(raw_path, html)
        parsed = extract_readable_content(html)
        corpus.append(
            {
                **item,
                "raw_html_path": str(raw_path),
                "page_title": parsed["title"],
                "text": parsed["text"],
            }
        )

    summary = {
        "documents_collected": len(corpus),
        "high_priority": sum(1 for x in corpus if x.get("priority") == "high"),
        "medium_priority": sum(1 for x in corpus if x.get("priority") == "medium"),
    }

    write_json(PROCESSED_PATH, corpus)
    write_json(SUMMARY_PATH, summary)
    print(summary)


if __name__ == "__main__":
    main()
