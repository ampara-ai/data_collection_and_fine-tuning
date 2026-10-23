#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_json

SEEDS_JSON = PROCESSED_DIR / "jurisprudence_seed_urls.json"
ENTRIES_RAW_JSON = PROCESSED_DIR / "jurisprudence_entries_raw.json"
ENTRIES_DEDUPED_JSON = PROCESSED_DIR / "jurisprudence_entries_deduped.json"
INDEX_PAGES_JSON = PROCESSED_DIR / "jurisprudence_index_pages.json"
OUT_RAW = PROCESSED_DIR / "jurisprudence_entries_raw_candidates_only.json"
OUT_DEDUPED = PROCESSED_DIR / "jurisprudence_entries_deduped_candidates_only.json"
OUT_INDEX = PROCESSED_DIR / "jurisprudence_index_pages_candidates_only.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    seeds = _load(SEEDS_JSON)
    allowed_urls = {item["seed_url"].rstrip("/") for item in seeds}

    index_pages = _load(INDEX_PAGES_JSON) if INDEX_PAGES_JSON.exists() else []
    allowed_index_ids = {
        item["index_page_id"]
        for item in index_pages
        if (item.get("index_page_url") or "").rstrip("/") in allowed_urls
    }

    raw_entries = _load(ENTRIES_RAW_JSON)
    filtered_raw = [item for item in raw_entries if item.get("index_page_id") in allowed_index_ids]

    filtered_deduped = []
    if ENTRIES_DEDUPED_JSON.exists():
        deduped_entries = _load(ENTRIES_DEDUPED_JSON)
        filtered_deduped = [item for item in deduped_entries if item.get("index_page_id") in allowed_index_ids]

    filtered_index_pages = [item for item in index_pages if item.get("index_page_id") in allowed_index_ids]

    write_json(OUT_RAW, filtered_raw)
    write_json(OUT_DEDUPED, filtered_deduped)
    write_json(OUT_INDEX, filtered_index_pages)

    print(json.dumps({
        "allowed_seed_urls": len(allowed_urls),
        "allowed_index_pages": len(filtered_index_pages),
        "raw_entries_filtered": len(filtered_raw),
        "deduped_entries_filtered": len(filtered_deduped),
        "outputs": {
            "raw": str(OUT_RAW),
            "deduped": str(OUT_DEDUPED),
            "index_pages": str(OUT_INDEX),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
