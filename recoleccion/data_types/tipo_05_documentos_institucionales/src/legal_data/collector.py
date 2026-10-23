from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}


def load_inventory(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fetch_html(url: str) -> str:
    with requests.Session() as session:
        response = session.get(url, timeout=30, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        return response.text


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_readable_content(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    body = soup.get_text("\n", strip=True)
    body = normalize_text(body)
    return {
        "title": title,
        "text": body,
    }
