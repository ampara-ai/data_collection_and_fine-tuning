#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import OrderedDict

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_json

INPUT_JSON = PROCESSED_DIR / "jurisprudence_entries_raw.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_entries_deduped.json"


def _key(item: dict) -> str:
    return (item.get("entry_url") or item.get("pdf_url") or f"{item.get('index_page_id')}::{item.get('entry_title_raw')}").strip()


def main() -> None:
    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    deduped = OrderedDict()
    for item in items:
        key = _key(item)
        if key not in deduped:
            deduped[key] = item
        else:
            prev = deduped[key]
            merged_sources = (prev.get("provenance_sources") or []) + (item.get("provenance_sources") or [])
            prev["provenance_sources"] = merged_sources
    output = list(deduped.values())
    write_json(OUTPUT_JSON, output)
    print(json.dumps({"entries_total": len(items), "entries_deduped": len(output), "output_path": str(OUTPUT_JSON)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
