#!/usr/bin/env python3
from __future__ import annotations

import requests

from legal_data.config import SOURCE_URL
from legal_data.heuristics import score_article, summarize_scored_articles
from legal_data.parser import parse_penal_code_html
from legal_data.storage import write_json, write_text


RAW_HTML_PATH = "recoleccion/data_types/tipo_02_codigo_penal/data/raw/codigo_penal_lpderecho.html"
ALL_ARTICLES_PATH = "recoleccion/data_types/tipo_02_codigo_penal/data/processed/all_articles.json"
CANDIDATES_PATH = "recoleccion/data_types/tipo_02_codigo_penal/data/processed/candidate_articles.json"
SUMMARY_PATH = "recoleccion/data_types/tipo_02_codigo_penal/data/processed/heuristics_summary.json"


def main() -> None:
    response = requests.get(SOURCE_URL, timeout=60)
    response.raise_for_status()
    html = response.text
    write_text(RAW_HTML_PATH, html)

    articles = parse_penal_code_html(html, SOURCE_URL)
    scored = [score_article(article) for article in articles]

    all_articles = [article.to_dict() for article in scored]
    candidates = [
        article.to_dict()
        for article in scored
        if article.candidate_status in {"candidate_strong", "candidate_medium", "candidate_weak"}
    ]
    summary = summarize_scored_articles(scored)

    write_json(ALL_ARTICLES_PATH, all_articles)
    write_json(CANDIDATES_PATH, candidates)
    write_json(SUMMARY_PATH, summary)

    print(summary)


if __name__ == "__main__":
    main()
