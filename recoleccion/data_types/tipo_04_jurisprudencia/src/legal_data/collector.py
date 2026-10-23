from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def collect_jurisprudence_sources(paths: list[str | Path]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for path in paths:
        items = load_json(path)
        for item in items:
            url = item.get("jurisprudence_url")
            if not url:
                continue
            collected.append(
                {
                    "source_dataset": str(path),
                    "article_id": item.get("article_id"),
                    "heading": item.get("heading"),
                    "jurisprudence_url": url,
                }
            )
    return collected


def deduplicate_by_url(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for item in items:
        url = item["jurisprudence_url"]
        if url not in by_url:
            by_url[url] = {
                "jurisprudence_url": url,
                "linked_articles": [],
            }
        by_url[url]["linked_articles"].append(
            {
                "source_dataset": item["source_dataset"],
                "article_id": item.get("article_id"),
                "heading": item.get("heading"),
            }
        )
    return list(by_url.values())


def fetch_jurisprudence_page(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    return {
        "url": url,
        "title": title,
        "html": html,
        "sha256": hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest(),
    }
