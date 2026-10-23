#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from legal_data.paths import PROCESSED_DIR, RAW_DIR
from legal_data.storage import write_json, write_text

INPUT_JSON = PROCESSED_DIR / "jurisprudence_index_llm_10.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_entry_detail_pages_10.json"
RAW_HTML_DIR = RAW_DIR / "entry_detail_html_10"
HEADERS = {"User-Agent": "Mozilla/5.0"}
SKIP_NON_HTML_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _html_to_markdown_like(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.td-post-content")
    if not content:
        return ""

    lines = []
    for tag in content.find_all(["h2", "h3", "h4", "p", "li", "strong", "a"], limit=260):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if not text:
            continue
        if any(noise in text.lower() for noise in ["inscríbete aquí", "más información", "matricúlate", "diplomado"]):
            continue
        if tag.name == "a":
            href = tag.get("href")
            if href and href.endswith(".pdf"):
                lines.append(f"[pdf] {href}")
            continue
        lines.append(f"[{tag.name}] {text}")
    return "\n".join(lines)


def _is_html_candidate(url: str) -> bool:
    lowered = url.lower().split("?", 1)[0]
    return not any(lowered.endswith(ext) for ext in SKIP_NON_HTML_EXTENSIONS)


def _iter_entries(parsed_pages: list[dict]) -> list[dict]:
    rows = []
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
                rows.append(
                    {
                        "entry_id": f"{page['index_page_id']}_e{counter:04d}",
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
                )
    return rows


def main() -> None:
    parsed_pages = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    entries = _iter_entries(parsed_pages)

    results = []
    for item in entries:
        entry_url = item.get("entry_url")
        if not entry_url:
            results.append(
                {
                    **item,
                    "detail_fetch_status": "missing_entry_url",
                    "detail_raw_html_path": None,
                    "detail_page_title": None,
                    "detail_markdown": None,
                    "detail_sha256": None,
                }
            )
            continue
        if not _is_html_candidate(entry_url):
            results.append(
                {
                    **item,
                    "detail_fetch_status": "skipped_non_html_entry_url",
                    "detail_raw_html_path": None,
                    "detail_page_title": None,
                    "detail_markdown": None,
                    "detail_sha256": None,
                }
            )
            continue
        entry_id = item["entry_id"]
        try:
            response = requests.get(entry_url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            html = response.text
            raw_path = RAW_HTML_DIR / f"{entry_id}.html"
            write_text(raw_path, html)
            results.append(
                {
                    **item,
                    "detail_fetch_status": "success",
                    "detail_raw_html_path": str(raw_path),
                    "detail_page_title": BeautifulSoup(html, "lxml").title.get_text(" ", strip=True) if BeautifulSoup(html, "lxml").title else None,
                    "detail_markdown": _html_to_markdown_like(html),
                    "detail_sha256": _sha256_text(html),
                }
            )
        except Exception as exc:
            results.append(
                {
                    **item,
                    "detail_fetch_status": f"error: {exc}",
                    "detail_raw_html_path": None,
                    "detail_page_title": None,
                    "detail_markdown": None,
                    "detail_sha256": None,
                }
            )

    write_json(OUTPUT_JSON, results)
    print(json.dumps({
        "entries_total": len(results),
        "fetched_success": sum(1 for x in results if x.get("detail_fetch_status") == "success"),
        "missing_entry_url": sum(1 for x in results if x.get("detail_fetch_status") == "missing_entry_url"),
        "skipped_non_html": sum(1 for x in results if x.get("detail_fetch_status") == "skipped_non_html_entry_url"),
        "errors": sum(1 for x in results if str(x.get("detail_fetch_status", "")).startswith("error:")),
        "output_path": str(OUTPUT_JSON),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
