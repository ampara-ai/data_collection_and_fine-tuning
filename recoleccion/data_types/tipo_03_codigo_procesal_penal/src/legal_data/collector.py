from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from legal_data.models import ProcessArticle

def merge_articles(article_groups: Iterable[Iterable[ProcessArticle]]) -> list[ProcessArticle]:
    """Fusiona las partes del CPP sin ocultar contradicciones entre fuentes."""
    merged: dict[str, ProcessArticle] = {}
    for articles in article_groups:
        for article in articles:
            current = merged.get(article.article_id)
            if current is None:
                merged[article.article_id] = article
                continue
            if (
                current.heading != article.heading
                or current.text != article.text
                or current.jurisprudence_url != article.jurisprudence_url
            ):
                raise ValueError(
                    "Artículo duplicado con contenido contradictorio: "
                    f"{article.article_id} ({current.source_url} vs. {article.source_url})"
                )
    return list(merged.values())


def validate_part(
    articles: list[ProcessArticle],
    *,
    part_id: str,
    required_article_ids: Iterable[str],
) -> None:
    if not articles:
        raise ValueError(f"{part_id}: el parser no extrajo artículos")
    article_ids = {article.article_id for article in articles}
    missing = sorted(set(required_article_ids) - article_ids)
    if missing:
        raise ValueError(f"{part_id}: faltan artículos límite requeridos: {missing}")


def validate_complete_numeric_coverage(
    articles: list[ProcessArticle],
    *,
    first_article: int,
    last_article: int,
) -> dict[str, Any]:
    article_ids = [article.article_id for article in articles]
    duplicated = sorted(
        article_id for article_id in set(article_ids) if article_ids.count(article_id) > 1
    )
    if duplicated:
        raise ValueError(f"IDs de artículo duplicados después de fusionar: {duplicated}")

    article_id_set = set(article_ids)
    missing_numeric = [
        str(number)
        for number in range(first_article, last_article + 1)
        if str(number) not in article_id_set
    ]
    if missing_numeric:
        raise ValueError(
            f"Cobertura incompleta del CPP {first_article}-{last_article}; "
            f"faltan: {missing_numeric}"
        )

    numeric_ids = [int(article_id) for article_id in article_ids if article_id.isdigit()]
    return {
        "total_articles": len(articles),
        "numeric_articles": len(numeric_ids),
        "non_numeric_or_inserted_articles": len(articles) - len(numeric_ids),
        "first_numeric_article": min(numeric_ids),
        "last_numeric_article": max(numeric_ids),
        "missing_numeric_articles": [],
        "duplicate_article_ids": [],
    }
