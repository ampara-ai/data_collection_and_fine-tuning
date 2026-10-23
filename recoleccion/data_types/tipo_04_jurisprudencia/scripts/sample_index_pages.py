#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from legal_data.collector import collect_jurisprudence_sources, deduplicate_by_url, fetch_jurisprudence_page
from legal_data.paths import PROCESSED_DIR, RAW_DIR, TIPO_02_CANDIDATES, TIPO_03_CANDIDATES
from legal_data.storage import write_json, write_text

SAMPLE_SIZE = 10
OUTPUT_JSON = PROCESSED_DIR / "input_indices_10.json"
RAW_HTML_DIR = RAW_DIR / "html_sample_10"


def main() -> None:
    collected = collect_jurisprudence_sources([TIPO_02_CANDIDATES, TIPO_03_CANDIDATES])
    deduped = deduplicate_by_url(collected)
    sampled = deduped[:SAMPLE_SIZE]

    result = []
    for idx, item in enumerate(sampled, start=1):
        page = fetch_jurisprudence_page(item["jurisprudence_url"])
        index_page_id = f"jp_{idx:04d}"
        raw_path = RAW_HTML_DIR / f"{index_page_id}.html"
        write_text(raw_path, page["html"])
        first_link = item.get("linked_articles", [{}])[0]
        result.append(
            {
                "index_page_id": index_page_id,
                "index_page_url": item["jurisprudence_url"],
                "article_id": first_link.get("article_id"),
                "article_heading": first_link.get("heading"),
                "source_dataset": first_link.get("source_dataset"),
                "anchor_code": None,
                "selection_reason": f"sample_batch_{SAMPLE_SIZE}",
                "raw_html_path": str(raw_path),
                "linked_articles": item.get("linked_articles", []),
                "source_title": page.get("title"),
                "source_sha256": page.get("sha256"),
            }
        )

    write_json(OUTPUT_JSON, result)
    print(json.dumps({"sample_size": len(result), "output_path": str(OUTPUT_JSON)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
