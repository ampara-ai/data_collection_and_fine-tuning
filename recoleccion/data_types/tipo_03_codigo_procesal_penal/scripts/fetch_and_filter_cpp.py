#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import requests

from legal_data.collector import (
    merge_articles,
    validate_complete_numeric_coverage,
    validate_part,
)
from legal_data.config import (
    EXPECTED_FIRST_NUMERIC_ARTICLE,
    EXPECTED_LAST_NUMERIC_ARTICLE,
    SOURCE_PAGES,
)
from legal_data.heuristics import score_article, summarize_scored_articles
from legal_data.parser import parse_cpp_html
from legal_data.storage import write_json, write_text


TYPE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = TYPE_DIR / "data" / "raw"
PROCESSED_DIR = TYPE_DIR / "data" / "processed"
ALL_ARTICLES_PATH = PROCESSED_DIR / "all_articles.json"
CANDIDATES_PATH = PROCESSED_DIR / "candidate_articles.json"
SUMMARY_PATH = PROCESSED_DIR / "heuristics_summary.json"
COLLECTION_SUMMARY_PATH = RAW_DIR / "collection_summary.json"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    fetched_at = _now_iso()
    parsed_parts = []
    raw_snapshots = []

    for source in SOURCE_PAGES:
        response = requests.get(
            source["url"],
            timeout=60,
            headers={"User-Agent": "peru-legal-rag-data/0.1 (research dataset collector)"},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        html = response.text
        articles = parse_cpp_html(html, source["url"])
        validate_part(
            articles,
            part_id=source["part_id"],
            required_article_ids=source["required_article_ids"],
        )
        parsed_parts.append(articles)
        raw_snapshots.append(
            {
                "part_id": source["part_id"],
                "url": source["url"],
                "final_url": response.url,
                "raw_filename": source["raw_filename"],
                "html": html,
                "bytes_utf8": len(html.encode("utf-8")),
                "article_count": len(articles),
                "first_article_id": articles[0].article_id,
                "last_article_id": articles[-1].article_id,
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
            }
        )

    articles = merge_articles(parsed_parts)
    coverage = validate_complete_numeric_coverage(
        articles,
        first_article=EXPECTED_FIRST_NUMERIC_ARTICLE,
        last_article=EXPECTED_LAST_NUMERIC_ARTICLE,
    )
    scored = [score_article(article) for article in articles]

    all_articles = [article.to_dict() for article in scored]
    candidates = [
        article.to_dict()
        for article in scored
        if article.candidate_status in {"candidate_strong", "candidate_medium", "candidate_weak"}
    ]
    summary = summarize_scored_articles(scored)
    summary["coverage"] = coverage

    collection_summary = {
        "fetched_at": fetched_at,
        "collection_method": "two_part_lp_derecho_html_merge",
        "pages": [
            {key: value for key, value in snapshot.items() if key != "html"}
            for snapshot in raw_snapshots
        ],
        "coverage": coverage,
    }

    for snapshot in raw_snapshots:
        write_text(RAW_DIR / snapshot["raw_filename"], snapshot["html"])
    write_json(COLLECTION_SUMMARY_PATH, collection_summary)
    write_json(ALL_ARTICLES_PATH, all_articles)
    write_json(CANDIDATES_PATH, candidates)
    write_json(SUMMARY_PATH, summary)

    print(summary)


if __name__ == "__main__":
    main()
