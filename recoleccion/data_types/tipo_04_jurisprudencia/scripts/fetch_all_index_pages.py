#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from legal_data.paths import PROCESSED_DIR, RAW_DIR
from legal_data.storage import write_json, write_text

INPUT_JSON = PROCESSED_DIR / "jurisprudence_seed_urls.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_index_pages.json"
RAW_HTML_DIR = RAW_DIR / "index_html_full"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def main() -> None:
    seeds = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    results = []
    for idx, item in enumerate(seeds, start=1):
        url = item["seed_url"]
        index_page_id = f"jp_{idx:05d}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            html = response.text
            raw_path = RAW_HTML_DIR / f"{index_page_id}.html"
            write_text(raw_path, html)
            soup = BeautifulSoup(html, "lxml")
            canonical = soup.find("link", rel="canonical")
            results.append(
                {
                    "index_page_id": index_page_id,
                    "index_page_url": url,
                    "canonical_url": canonical.get("href") if canonical else url,
                    "title": soup.title.get_text(" ", strip=True) if soup.title else None,
                    "sha256": _sha256_text(html),
                    "fetch_status": "ok",
                    "raw_html_path": str(raw_path),
                    "provenance_sources": item.get("provenance_sources", []),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "index_page_id": index_page_id,
                    "index_page_url": url,
                    "canonical_url": url,
                    "title": None,
                    "sha256": None,
                    "fetch_status": f"error: {exc}",
                    "raw_html_path": None,
                    "provenance_sources": item.get("provenance_sources", []),
                }
            )
    write_json(OUTPUT_JSON, results)
    print(json.dumps({"pages_total": len(results), "fetched_ok": sum(1 for x in results if x.get('fetch_status') == 'ok'), "output_path": str(OUTPUT_JSON)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
