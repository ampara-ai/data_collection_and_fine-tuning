from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_main_text_blocks(content: Tag) -> list[str]:
    blocks: list[str] = []
    for node in content.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = normalize_text(node.get_text(" ", strip=True))
        if text:
            blocks.append(text)
    return blocks


def parse_jurisprudence_html(html: str, source_url: str, linked_articles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    h1 = soup.find("h1")
    h1_text = normalize_text(h1.get_text(" ", strip=True)) if h1 else ""
    subtitle = soup.find("p", class_="td-post-sub-title")
    subtitle_text = normalize_text(subtitle.get_text(" ", strip=True)) if subtitle else ""

    content = soup.select_one("div.td-post-content")
    blocks = extract_main_text_blocks(content) if content else []

    article_heading = blocks[0] if blocks else ""

    jurisprudence_entries = []
    in_jurisprudence_section = False
    for block in blocks:
        lower = block.lower()
        if lower.startswith("jurisprudencia del artículo") or lower.startswith("jurisprudencia del articulo"):
            in_jurisprudence_section = True
            continue
        if in_jurisprudence_section:
            jurisprudence_entries.append(block)

    jurisprudence_entries = [b for b in jurisprudence_entries if b not in {"Corte Suprema", "NUEVO:"}]

    return {
        "source_url": source_url,
        "page_title": title,
        "entry_title": h1_text,
        "subtitle": subtitle_text,
        "article_heading": article_heading,
        "linked_articles": linked_articles or [],
        "blocks": blocks,
        "jurisprudence_entries": jurisprudence_entries,
    }


def parse_jurisprudence_file(path: str | Path, source_url: str, linked_articles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_jurisprudence_html(html, source_url=source_url, linked_articles=linked_articles)
