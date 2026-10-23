#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from legal_data.index_parser import load_json, parse_index_entries
from legal_data.storage import write_json

PARSED_PAGES_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_metadata.json")
ENTRIES_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_entries_structured.json")
SUMMARY_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_entries_summary.json")


def main() -> None:
    parsed_pages = load_json(PARSED_PAGES_PATH)
    entries = parse_index_entries(parsed_pages)
    summary = {
        "entries_total": len(entries),
        "entries_with_lp_url": sum(1 for x in entries if x.get("lp_entry_url")),
        "categories": sorted({x["entry_category"] for x in entries if x.get("entry_category")}),
    }
    write_json(ENTRIES_PATH, entries)
    write_json(SUMMARY_PATH, summary)
    print(summary)


if __name__ == "__main__":
    main()
