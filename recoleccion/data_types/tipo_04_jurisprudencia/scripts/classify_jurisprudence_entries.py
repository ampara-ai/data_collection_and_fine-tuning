#!/usr/bin/env python3
from __future__ import annotations

import json

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_json

INPUT_JSON = PROCESSED_DIR / "jurisprudence_index_llm_10.json"
ENTRIES_OUTPUT = PROCESSED_DIR / "jurisprudence_entries_llm_10.json"
FILTERED_OUTPUT = PROCESSED_DIR / "jurisprudence_entries_filtered_10.json"


def main() -> None:
    parsed_pages = json.loads(INPUT_JSON.read_text(encoding="utf-8"))

    llm_entries = []

    for page in parsed_pages:
        parsed = page.get("parsed") or {}
        categories = parsed.get("categories") or []
        counter = 0
        for category in categories:
            category_name = category.get("name")
            for entry in category.get("entries") or []:
                title = (entry.get("title") or "").strip()
                entry_url = entry.get("matched_url") or entry.get("url")
                if not title:
                    continue
                counter += 1
                entry_id = f"{page['index_page_id']}_e{counter:04d}"
                row = {
                    "entry_id": entry_id,
                    "index_page_id": page["index_page_id"],
                    "index_page_url": page["index_page_url"],
                    "article_id": page.get("article_id"),
                    "article_heading": page.get("article_heading"),
                    "entry_category": category_name,
                    "entry_title_raw": title,
                    "entry_url": entry_url,
                    "resolution_reference_raw": None,
                    "parse_confidence": "high" if entry_url else "medium",
                }
                llm_entries.append(row)

    write_json(ENTRIES_OUTPUT, llm_entries)
    write_json(FILTERED_OUTPUT, llm_entries)
    summary = {
        "entries_total": len(llm_entries),
        "with_entry_url": sum(1 for x in llm_entries if x.get("entry_url")),
        "without_entry_url": sum(1 for x in llm_entries if not x.get("entry_url")),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
